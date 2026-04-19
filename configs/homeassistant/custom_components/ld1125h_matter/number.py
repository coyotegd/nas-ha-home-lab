"""Number platform for LD1125H Matter Radar — writable sensor settings."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_OCC_ST_MS,
    ATTR_RMAX_CM,
    ATTR_TH1_MOV,
    ATTR_TH1_OCC,
    ATTR_TH2_MOV,
    ATTR_TH2_OCC,
    ATTR_TH3_MOV,
    ATTR_TH3_OCC,
    CLUSTER_OCCUPANCY_SENSING,
    DOMAIN,
)
from .coordinator import LD1125HCoordinator

MATTER_DOMAIN = "matter"

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LD1125HNumberDescription(NumberEntityDescription):
    """Describe an LD1125H writable setting."""

    attribute_id: int
    scale: float = 1.0  # display = raw * scale


SETTINGS: tuple[LD1125HNumberDescription, ...] = (
    LD1125HNumberDescription(
        key="th1_mov",
        name="Zone 1 Motion Threshold",
        attribute_id=ATTR_TH1_MOV,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="th2_mov",
        name="Zone 2 Motion Threshold",
        attribute_id=ATTR_TH2_MOV,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="th3_mov",
        name="Zone 3 Motion Threshold",
        attribute_id=ATTR_TH3_MOV,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="th1_occ",
        name="Zone 1 Occupancy Threshold",
        attribute_id=ATTR_TH1_OCC,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="th2_occ",
        name="Zone 2 Occupancy Threshold",
        attribute_id=ATTR_TH2_OCC,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="th3_occ",
        name="Zone 3 Occupancy Threshold",
        attribute_id=ATTR_TH3_OCC,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    LD1125HNumberDescription(
        key="rmax",
        name="Max Detection Range",
        attribute_id=ATTR_RMAX_CM,
        native_min_value=0.4,
        native_max_value=12.0,
        native_step=0.1,
        native_unit_of_measurement="m",
        scale=0.01,  # raw value is cm, display in m
        mode=NumberMode.SLIDER,
    ),
    LD1125HNumberDescription(
        key="occ_st",
        name="Chirp Interval",
        attribute_id=ATTR_OCC_ST_MS,
        native_min_value=50,
        native_max_value=5000,
        native_step=50,
        native_unit_of_measurement="ms",
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LD1125H number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LD1125HNumber(data, entry, desc) for desc in SETTINGS
    )


class LD1125HNumber(CoordinatorEntity[LD1125HCoordinator], NumberEntity):
    """A writable radar setting exposed as a number entity."""

    _attr_has_entity_name = True
    entity_description: LD1125HNumberDescription

    def __init__(
        self,
        data: dict[str, Any],
        entry: ConfigEntry,
        description: LD1125HNumberDescription,
    ) -> None:
        """Initialize."""
        super().__init__(data["coordinator"])
        self.entity_description = description
        self._client = data["client"]
        self._node_id = data["node_id"]
        self._endpoint_id = data["endpoint_id"]
        self._attr_unique_id = (
            f"ld1125h_{self._node_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(MATTER_DOMAIN, data["matter_device_id"])},
        )

    @property
    def _matter_attr_path(self) -> str:
        """Attribute path for python-matter-server (decimal ints)."""
        return (
            f"{self._endpoint_id}/{CLUSTER_OCCUPANCY_SENSING}"
            f"/{self.entity_description.attribute_id}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update displayed value from coordinator data."""
        raw = self.coordinator.data.get(self.entity_description.attribute_id)
        if raw is not None:
            self._attr_native_value = raw * self.entity_description.scale
        else:
            self._attr_native_value = None
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the Matter device."""
        raw = int(round(value / self.entity_description.scale))
        try:
            await self._client.write_attribute(
                node_id=self._node_id,
                attribute_path=self._matter_attr_path,
                value=raw,
            )
        except Exception:
            _LOGGER.error(
                "Failed to write %s = %s (raw %d)",
                self.entity_description.key,
                value,
                raw,
                exc_info=True,
            )
            return

        self._attr_native_value = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
