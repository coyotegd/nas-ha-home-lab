"""Config flow for LD1125H Matter Radar."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ENDPOINT_ID, CONF_NODE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NODE_ID): int,
        vol.Required(CONF_ENDPOINT_ID, default=2): int,
    }
)

MATTER_DOMAIN = "matter"


class LD1125HMatterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LD1125H Matter Radar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — ask for Matter node ID and endpoint."""
        errors: dict[str, str] = {}

        if user_input is not None:
            node_id = user_input[CONF_NODE_ID]
            endpoint_id = user_input[CONF_ENDPOINT_ID]

            matter_data = self.hass.data.get(MATTER_DOMAIN)
            if not matter_data:
                errors["base"] = "matter_not_ready"
            else:
                client = None
                for entry_data in matter_data.values():
                    if hasattr(entry_data, "adapter"):
                        client = getattr(
                            entry_data.adapter, "matter_client", None
                        )
                        if client:
                            break
                    if hasattr(entry_data, "matter_client"):
                        client = entry_data.matter_client
                        break

                if client is None:
                    errors["base"] = "matter_not_ready"
                else:
                    node = None
                    for n in client.get_nodes():
                        if n.node_id == node_id:
                            node = n
                            break

                    if node is None:
                        errors[CONF_NODE_ID] = "node_not_found"
                    elif endpoint_id not in node.endpoints:
                        errors[CONF_ENDPOINT_ID] = "endpoint_not_found"

            if not errors:
                await self.async_set_unique_id(
                    f"ld1125h_{node_id}_{endpoint_id}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"LD1125H Radar (Node {node_id})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
