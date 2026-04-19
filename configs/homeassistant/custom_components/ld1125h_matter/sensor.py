"""Sensor platform for LD1125H Matter Radar — live distance reading."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DISTANCE_CM, DOMAIN
from .coordinator import LD1125HCoordinator

MATTER_DOMAIN = "matter"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LD1125H distance sensor."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LD1125HDistanceSensor(data, entry)])


class LD1125HDistanceSensor(CoordinatorEntity[LD1125HCoordinator], SensorEntity):
    """Distance to detected target (cm), read-only."""

    _attr_has_entity_name = True
    _attr_name = "Distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, data: dict[str, Any], entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(data["coordinator"])
        node_id = data["node_id"]
        self._attr_unique_id = f"ld1125h_{node_id}_distance"
        self._attr_device_info = DeviceInfo(
            identifiers={(MATTER_DOMAIN, data["matter_device_id"])},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state from coordinator data."""
        raw = self.coordinator.data.get(ATTR_DISTANCE_CM)
        if raw is None or raw >= 0xFFFF:
            self._attr_native_value = None
        else:
            self._attr_native_value = raw
        self.async_write_ha_state()
