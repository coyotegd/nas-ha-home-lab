"""DataUpdateCoordinator for LD1125H Matter Radar."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ALL_VENDOR_ATTRS, CLUSTER_OCCUPANCY_SENSING, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=5)


def _attr_path(endpoint_id: int, attr_id: int) -> str:
    """Build a python-matter-server attribute path string."""
    return f"{endpoint_id}/{CLUSTER_OCCUPANCY_SENSING}/{attr_id}"


class LD1125HCoordinator(DataUpdateCoordinator[dict[int, Any]]):
    """Read vendor-specific attributes from the cached Matter node data."""

    def __init__(
        self,
        hass: HomeAssistant,
        node: Any,
        endpoint_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.node = node
        self.endpoint_id = endpoint_id

    async def _async_update_data(self) -> dict[int, Any]:
        """Return current values from the node's cached attribute dict."""
        result: dict[int, Any] = {}
        for attr_id in ALL_VENDOR_ATTRS:
            path = _attr_path(self.endpoint_id, attr_id)
            result[attr_id] = self.node.node_data.attributes.get(path)
        return result
