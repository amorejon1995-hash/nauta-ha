"""Switch platform for Nauta ETECSA Autologin."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nauta switch."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NautaAutologinSwitch(manager)])

class NautaAutologinSwitch(SwitchEntity):
    """Switch to enable or disable automatic login."""

    _attr_has_entity_name = True
    _attr_name = "Autologin Enabled"

    def __init__(self, manager) -> None:
        """Initialize the switch."""
        self._manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_autologin"

    @property
    def is_on(self) -> bool:
        """Return true if autologin is active."""
        return self._manager.autologin_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._manager.autologin_enabled = True
        self.async_write_ha_state()
        # Trigger an immediate check and login
        self.hass.async_create_task(self._manager.async_check_and_login())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._manager.autologin_enabled = False
        self.async_write_ha_state()
