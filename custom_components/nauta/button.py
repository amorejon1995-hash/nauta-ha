"""Button platform for Nauta ETECSA Autologin."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nauta buttons."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        NautaConnectButton(manager),
        NautaDisconnectButton(manager),
    ])

class NautaConnectButton(ButtonEntity):
    """Button to manually trigger Nauta login."""

    _attr_has_entity_name = True
    _attr_name = "Conectar"

    def __init__(self, manager) -> None:
        """Initialize the button."""
        self._manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_connect_button"

    async def async_press(self) -> None:
        """Press the button."""
        await self._manager.async_handle_login_flow()

class NautaDisconnectButton(ButtonEntity):
    """Button to manually trigger Nauta logout."""

    _attr_has_entity_name = True
    _attr_name = "Desconectar"

    def __init__(self, manager) -> None:
        """Initialize the button."""
        self._manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_disconnect_button"

    async def async_press(self) -> None:
        """Press the button."""
        await self._manager.async_logout()