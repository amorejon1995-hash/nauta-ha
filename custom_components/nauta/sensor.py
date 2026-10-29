"""Sensor platform for Nauta ETECSA Autologin."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nauta sensors."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NautaRemainingTimeSensor(manager)])


class NautaRemainingTimeSensor(SensorEntity):
    """Tiempo restante en el paquete Nauta, mostrado en formato legible."""

    _attr_has_entity_name = True
    _attr_name = "Tiempo restante"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, manager) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_remaining_time"

    @property
    def native_value(self) -> str | None:
        """Return remaining time formatted as 'Xd Xh Xmin Xs', calculado en vivo."""
        seconds_total = self._manager.get_live_remaining_seconds()
        if seconds_total is None:
            return None

        days, rem = divmod(seconds_total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        partes = []
        if days:
            partes.append(f"{days}d")
        if hours or days:
            partes.append(f"{hours}h")
        if minutes or hours or days:
            partes.append(f"{minutes}min")
        partes.append(f"{seconds}s")

        return " ".join(partes)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes: valores crudos para automatizaciones/graficas."""
        seconds_total = self._manager.get_live_remaining_seconds()
        attrs = {
            "raw_hh_mm_ss": self._manager.remaining_time_raw,
            "segundos_totales": seconds_total,
        }

        if seconds_total is not None:
            days, rem = divmod(seconds_total, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            attrs["dias"] = days
            attrs["horas"] = hours
            attrs["minutos"] = minutes
            attrs["segundos"] = seconds

        return attrs

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        self._manager.register_time_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners."""
        self._manager.remove_time_listener(self.async_write_ha_state)