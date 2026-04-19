"""LD1125H Matter Radar — expose vendor-specific radar attributes in HA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ENDPOINT_ID, CONF_NODE_ID, DOMAIN
from .coordinator import LD1125HCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number"]

MATTER_DOMAIN = "matter"
MATTER_ID_TYPE_DEVICE_ID = "deviceid"


def _get_matter_client(hass: HomeAssistant) -> Any | None:
    """Retrieve the MatterClient from the HA Matter integration."""
    matter_data = hass.data.get(MATTER_DOMAIN)
    if not matter_data:
        return None
    for entry_data in matter_data.values():
        if hasattr(entry_data, "adapter"):
            client = getattr(entry_data.adapter, "matter_client", None)
            if client is not None:
                return client
        if hasattr(entry_data, "matter_client"):
            return entry_data.matter_client
    return None


def _find_node(client: Any, node_id: int) -> Any | None:
    """Find a MatterNode by its node ID."""
    for node in client.get_nodes():
        if node.node_id == node_id:
            return node
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LD1125H Matter from a config entry."""
    node_id: int = entry.data[CONF_NODE_ID]
    endpoint_id: int = entry.data[CONF_ENDPOINT_ID]

    client = _get_matter_client(hass)
    if client is None:
        _LOGGER.error("Matter integration not available")
        return False

    node = _find_node(client, node_id)
    if node is None:
        _LOGGER.error("Matter node %s not found", node_id)
        return False

    coordinator = LD1125HCoordinator(hass, node, endpoint_id)
    await coordinator.async_config_entry_first_refresh()

    # Build the same device identifier the built-in Matter integration uses
    # so our entities merge onto its device card.
    server_info = client.server_info
    if server_info is None:
        _LOGGER.error("Matter server info not available")
        return False
    fabric_hex = f"{server_info.compressed_fabric_id:016X}"
    node_hex = f"{node_id:016X}"
    matter_device_id = (
        f"{MATTER_ID_TYPE_DEVICE_ID}_{fabric_hex}-{node_hex}-MatterNodeDevice"
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "node": node,
        "node_id": node_id,
        "endpoint_id": endpoint_id,
        "coordinator": coordinator,
        "matter_device_id": matter_device_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
