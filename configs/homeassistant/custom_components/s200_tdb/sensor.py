"""Sensor platform for GL-S200 TDB Boards."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import S200TDBCoordinator

SENSOR_TYPES = {
    "temperature": {
        "name": "Temperature",
        "unit": "°C",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "humidity": {
        "name": "Humidity",
        "unit": "%",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "pressure": {
        "name": "Pressure",
        "unit": "kPa",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "light": {
        "name": "Light",
        "unit": "lx",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery": {
        "name": "Battery",
        "unit": "%",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "temp_spl0601": {
        "name": "Barometric Temp",
        "unit": "°C",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up S200 TDB sensors."""
    coordinator: S200TDBCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id, dev_info in coordinator.devices.items():
        for sensor_key, sensor_meta in SENSOR_TYPES.items():
            entities.append(
                S200TDBSensor(coordinator, dev_id, dev_info["name"], sensor_key, sensor_meta)
            )
    async_add_entities(entities)


class S200TDBSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity for a TDB board measurement."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, dev_id, dev_name, sensor_key, sensor_meta):
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._sensor_key = sensor_key
        self._attr_unique_id = f"s200_tdb_{dev_id}_{sensor_key}"
        self._attr_name = sensor_meta["name"]
        self._attr_native_unit_of_measurement = sensor_meta["unit"]
        self._attr_device_class = sensor_meta["device_class"]
        self._attr_state_class = sensor_meta["state_class"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="GL-iNet",
            model="Thread Dev Board",
        )

    @property
    def native_value(self):
        """Return the sensor value."""
        data = self.coordinator.data.get(self._dev_id, {}).get("sensors", {})
        val = data.get(self._sensor_key)
        if val is not None and self._sensor_key in (
            "temperature", "humidity", "pressure", "temp_spl0601"
        ):
            return round(float(val), 1)
        return val
