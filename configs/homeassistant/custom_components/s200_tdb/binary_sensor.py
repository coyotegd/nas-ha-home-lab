"""Binary sensor platform for GL-S200 TDB Boards."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import S200TDBCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up S200 TDB binary sensors."""
    coordinator: S200TDBCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id, dev_info in coordinator.devices.items():
        entities.append(S200TDBConnected(coordinator, dev_id, dev_info["name"]))
        entities.append(S200TDBMotion(coordinator, dev_id, dev_info["name"]))
    async_add_entities(entities)


class S200TDBConnected(CoordinatorEntity, BinarySensorEntity):
    """Connectivity binary sensor for a TDB board."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, dev_id, dev_name):
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._attr_unique_id = f"s200_tdb_{dev_id}_connected"
        self._attr_name = "Connected"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="GL-iNet",
            model="Thread Dev Board",
        )

    @property
    def is_on(self):
        """Return True if the TDB board is connected."""
        return self.coordinator.data.get(self._dev_id, {}).get("connected", False)


class S200TDBMotion(CoordinatorEntity, BinarySensorEntity):
    """PIR motion binary sensor for a TDB board."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator, dev_id, dev_name):
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._attr_unique_id = f"s200_tdb_{dev_id}_motion"
        self._attr_name = "Motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="GL-iNet",
            model="Thread Dev Board",
        )

    @property
    def is_on(self):
        """Return True if PIR motion is detected."""
        return self.coordinator.data.get(self._dev_id, {}).get("motion", False)
