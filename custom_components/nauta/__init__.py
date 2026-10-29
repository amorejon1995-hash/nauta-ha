"""The Nauta ETECSA Autologin integration."""
from __future__ import annotations

import os
import asyncio
import logging
import time
import urllib.request
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components import persistent_notification
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nauta ETECSA Autologin from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    interval = entry.data.get(CONF_INTERVAL, 60)

    manager = NautaAutologinManager(hass, entry, username, password, interval)
    hass.data[DOMAIN][entry.entry_id] = manager

    await manager.async_setup()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Se dispara cuando se guardan cambios desde el formulario de Opciones
    (ej: credenciales nuevas de una cuenta Nauta que reemplaza a la agotada)."""
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.apply_new_credentials(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        interval=entry.data.get(CONF_INTERVAL, 60),
    )
    await manager.async_check_and_login()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager = hass.data[DOMAIN].pop(entry.entry_id)
        manager.unload()

    return unload_ok


class NautaAutologinManager:
    """Manages the connection status and automated login flow using econnect."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        username: str,
        password: str,
        interval: int,
    ) -> None:
        """Initialize manager."""
        self.hass = hass
        self.entry = entry
        self.username = username
        self.password = password
        self.interval = interval
        self.is_connected = False
        self.autologin_enabled = True
        self._unsub_interval = None
        self.listeners = []
        self._lock = asyncio.Lock()
        self.session_file = hass.config.path("nauta_session.json")

        # --- Tiempo restante de la cuenta ---
        self.remaining_time_seconds: int | None = None
        self.remaining_time_raw: str | None = None
        self._remaining_captured_at: float | None = None
        self._unsub_time_interval = None
        self._unsub_countdown_interval = None
        self.account_exhausted = False
        self._time_listeners = []

    async def async_setup(self) -> None:
        """Set up periodic tracking."""
        # Initial check
        await self.async_check_and_login()

        # Track periodically (resilient to connection drops, modem reboots)
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_on_timer,
            timedelta(seconds=self.interval),
        )

        # Track remaining time separately, cada 5 minutos
        self._unsub_time_interval = async_track_time_interval(
            self.hass,
            self._async_on_time_timer,
            timedelta(seconds=300),
        )

        # Countdown local cada 1 segundo, sin consultar al servidor
        self._unsub_countdown_interval = async_track_time_interval(
            self.hass,
            self._async_on_countdown_tick,
            timedelta(seconds=1),
        )

    def unload(self) -> None:
        """Cleanup resources."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        if self._unsub_time_interval:
            self._unsub_time_interval()
            self._unsub_time_interval = None
        if self._unsub_countdown_interval:
            self._unsub_countdown_interval()
            self._unsub_countdown_interval = None

    async def _async_on_timer(self, _now) -> None:
        """Timer callback."""
        await self.async_check_and_login()

    async def _async_on_time_timer(self, _now) -> None:
        """Timer callback para consultar tiempo restante."""
        await self.async_get_remaining_time()

    async def _async_on_countdown_tick(self, _now) -> None:
        """Cada 1 segundo: solo recalcula localmente y notifica a los listeners
        del countdown (no toca conectividad ni otras entidades)."""
        if self.get_live_remaining_seconds() is not None:
            for cb in self._time_listeners:
                cb()

    def get_live_remaining_seconds(self) -> int | None:
        """Tiempo restante calculado localmente en tiempo real, sin llamar al servidor."""
        if self.remaining_time_seconds is None or self._remaining_captured_at is None:
            return self.remaining_time_seconds

        elapsed = time.monotonic() - self._remaining_captured_at
        live = self.remaining_time_seconds - int(elapsed)
        return max(0, live)

    def register_time_listener(self, callback_func) -> None:
        """Registrar listener del countdown (actualizacion cada 1s)."""
        self._time_listeners.append(callback_func)

    def remove_time_listener(self, callback_func) -> None:
        """Quitar listener del countdown."""
        if callback_func in self._time_listeners:
            self._time_listeners.remove(callback_func)

    def _check_real_internet(self) -> bool:
        """Synchronous check for real internet connectivity."""
        url = "http://clients3.google.com/generate_204"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 204:
                    return True
        except Exception:
            pass
        return False

    async def async_check_internet(self) -> bool:
        """Wrapper to run the connection test in the executor thread."""
        return await self.hass.async_add_executor_job(self._check_real_internet)

    async def async_check_and_login(self) -> None:
        """Verify connection and perform login if necessary, handling modem boots/drops."""
        if self._lock.locked():
            _LOGGER.debug("Connection check/login already in progress, skipping")
            return

        async with self._lock:
            # 1. Check if we already have working internet
            has_internet = await self.async_check_internet()

            if has_internet:
                if not self.is_connected:
                    _LOGGER.info("Internet connection is active.")
                    self.is_connected = True
                    self._notify_listeners()
                return

            # If we reach here, internet is down.
            if self.is_connected:
                _LOGGER.warning("Internet connection lost.")
                self.is_connected = False
                self._notify_listeners()

            # 2. If autologin is enabled (y la cuenta no esta agotada), try to log in
            if self.autologin_enabled and not self.account_exhausted:
                await self.async_handle_login_flow()

    async def async_handle_login_flow(self) -> bool:
        """Helper to run the login flow using the econnect library."""
        def _run_login() -> bool:
            try:
                from .econnect import nauta as EconnectNauta
                nauta = EconnectNauta()

                # Check if the ETECSA portal captive portal is reachable first
                if not nauta.test_net():
                    _LOGGER.debug("ETECSA portal captive portal not reachable. Modem might be rebooting or offline.")
                    return False

                _LOGGER.info("ETECSA portal detected. Attempting login...")
                # Try to log in
                res = nauta.login_net(self.username, self.password)
                if res is True:
                    _LOGGER.info("Nauta login request submitted successfully. Saving session data.")
                    # Persist session parameters to a json file to allow clean logout later
                    nauta.save_data(self.session_file)
                    return True
                else:
                    _LOGGER.warning("Nauta login request rejected: %s", res)
                    return False
            except Exception as err:
                _LOGGER.error("Error communicating with ETECSA portal via econnect: %s", err)
                return False

        success = await self.hass.async_add_executor_job(_run_login)
        if success:
            # Wait briefly for portal session to activate routing
            await asyncio.sleep(4)
            has_internet = await self.async_check_internet()
            if has_internet:
                _LOGGER.info("Internet restored successfully after auto-login.")
                self.is_connected = True
                self._notify_listeners()
                # Consultar tiempo restante de una vez, sin esperar al timer de 5 min
                await self.async_get_remaining_time()
                return True
        return False

    async def async_logout(self) -> bool:
        """Log out from ETECSA portal using persisted session variables."""
        if not os.path.exists(self.session_file):
            _LOGGER.warning("No active Nauta session file found. Cannot log out.")
            return False

        def _run_logout() -> bool:
            try:
                from .econnect import nauta as EconnectNauta
                nauta = EconnectNauta()

                # Check portal reachability
                if not nauta.test_net():
                    _LOGGER.error("Cannot contact ETECSA portal to perform logout.")
                    return False

                # Attempt logout using file data
                if nauta.logout_back(self.session_file):
                    _LOGGER.info("Logout performed successfully. Deleting session file.")
                    try:
                        os.remove(self.session_file)
                    except OSError:
                        pass
                    return True
                else:
                    _LOGGER.warning("Logout request failed.")
                    return False
            except Exception as err:
                _LOGGER.error("Error performing logout: %s", err)
                return False

        success = await self.hass.async_add_executor_job(_run_logout)

        # Verify internet is down
        await asyncio.sleep(2)
        has_internet = await self.async_check_internet()
        self.is_connected = has_internet
        self._notify_listeners()

        return success

    async def async_get_remaining_time(self) -> str | None:
        """Consulta el tiempo restante de la sesion Nauta activa, sin volver a loguear."""
        if not os.path.exists(self.session_file):
            _LOGGER.debug("No hay sesion guardada, no se puede consultar tiempo restante.")
            return None

        def _run_query():
            try:
                from .econnect import nauta as EconnectNauta
                nauta = EconnectNauta()
                result = nauta.reanude_login(self.session_file)
                _LOGGER.debug("Respuesta cruda de getLeftTime: %r", result)
                return result
            except Exception as err:
                _LOGGER.error("Error consultando tiempo restante: %s", err)
                return None

        result = await self.hass.async_add_executor_job(_run_query)

        if result and result != 'error_cargar_datos':
            self.remaining_time_raw = result
            self.remaining_time_seconds = self._parse_hms_to_seconds(result)
            self._remaining_captured_at = time.monotonic()
            self._notify_listeners()

            if (
                self.remaining_time_seconds is not None
                and self.remaining_time_seconds <= 0
                and not self.account_exhausted
            ):
                self._handle_account_exhausted()

        return result

    @staticmethod
    def _parse_hms_to_seconds(raw: str) -> int | None:
        """Convierte un string 'HH:MM:SS' a segundos totales."""
        try:
            parts = raw.strip().split(':')
            if len(parts) != 3:
                return None
            hours, minutes, seconds = (int(p) for p in parts)
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, AttributeError):
            return None

    def _handle_account_exhausted(self) -> None:
        """Se llama cuando el tiempo restante llega a 0. Apaga el autologin
        para no martillar el portal con una cuenta temporal ya sin saldo,
        y avisa que hace falta cargar una cuenta nueva."""
        self.account_exhausted = True
        self.autologin_enabled = False
        _LOGGER.warning(
            "La cuenta Nauta (%s) se quedo sin tiempo. Autologin desactivado "
            "automaticamente. Carga una cuenta nueva desde Configuracion > "
            "Dispositivos y Servicios > Nauta > Configurar.",
            self.username,
        )
        persistent_notification.create(
            self.hass,
            (
                f"La cuenta Nauta **{self.username}** se quedo sin tiempo.\n\n"
                "El autologin se desactivo automaticamente para evitar intentos "
                "inutiles. Ve a **Configuracion > Dispositivos y Servicios > "
                "Nauta ETECSA Autologin > Configurar** para cargar la cuenta nueva. "
                "Al guardar credenciales nuevas, el autologin se reactiva solo."
            ),
            title="Cuenta Nauta agotada",
            notification_id=f"nauta_exhausted_{self.entry.entry_id}",
        )
        self._notify_listeners()

    def apply_new_credentials(self, username: str, password: str, interval: int) -> None:
        """Aplica credenciales nuevas en caliente (llamado cuando se guardan las Opciones)."""
        self.username = username
        self.password = password
        self.interval = interval
        self.account_exhausted = False
        self.autologin_enabled = True
        self.remaining_time_seconds = None
        self.remaining_time_raw = None
        self._remaining_captured_at = None

        persistent_notification.dismiss(
            self.hass, f"nauta_exhausted_{self.entry.entry_id}"
        )

        # Reiniciar el timer con el nuevo intervalo por si cambio
        if self._unsub_interval:
            self._unsub_interval()
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_on_timer,
            timedelta(seconds=self.interval),
        )

        _LOGGER.info(
            "Credenciales de Nauta actualizadas (usuario: %s). Autologin reactivado.",
            username,
        )
        self._notify_listeners()

    def register_listener(self, callback_func) -> None:
        """Register entity listener."""
        self.listeners.append(callback_func)

    def remove_listener(self, callback_func) -> None:
        """Remove entity listener."""
        if callback_func in self.listeners:
            self.listeners.remove(callback_func)

    def _notify_listeners(self) -> None:
        """Notify entities of state change."""
        for listener in self.listeners:
            listener()