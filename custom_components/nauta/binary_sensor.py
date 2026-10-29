"""Binary sensor platform for Nauta ETECSA Autologin."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nauta binary sensors."""
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NautaConnectivitySensor(manager)])

class NautaConnectivitySensor(BinarySensorEntity):
    """Representation of the Nauta internet connectivity sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Internet Status"

    def __init__(self, manager) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if internet is active."""
        return self._manager.is_connected

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        self._manager.register_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners."""
        self._manager.remove_listener(self.async_write_ha_state)
