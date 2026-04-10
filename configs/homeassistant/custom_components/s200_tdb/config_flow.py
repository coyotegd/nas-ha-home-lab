"""Config flow for GL-S200 TDB Boards."""

import asyncio
import json
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, CONF_DEVICES

_LOGGER = logging.getLogger(__name__)


async def _fetch_device_list(host: str, port: int) -> list[dict]:
    """Connect to bridge WS, receive device_list message, return devices."""
    devices = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                f"ws://{host}:{port}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as ws:
                # Read messages until we get device_list or timeout
                try:
                    async with asyncio.timeout(5):
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("type") == "device_list":
                                    devices = data.get("devices", [])
                                    break
                except TimeoutError:
                    pass
                await ws.close()
    except Exception as exc:
        _LOGGER.debug("Failed to fetch device list: %s", exc)
    return devices


class S200TDBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for S200 TDB Boards."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Validate by attempting a WebSocket connection to the bridge
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        f"ws://{host}:{port}",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as ws:
                        await ws.close()
                return self.async_create_entry(
                    title="S200 TDB Boards",
                    data=user_input,
                    options={CONF_DEVICES: {}},
                )
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return S200TDBOptionsFlow()


class S200TDBOptionsFlow(config_entries.OptionsFlow):
    """Handle options for S200 TDB — add/remove devices."""

    async def async_step_init(self, user_input=None):
        """Show menu: add or remove device."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_device", "remove_device"],
        )

    async def async_step_add_device(self, user_input=None):
        """Discover devices from bridge and let user select one to add."""
        errors = {}
        host = self.config_entry.data.get(CONF_HOST, DEFAULT_HOST)
        port = self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        current_devices = dict(self.config_entry.options.get(CONF_DEVICES, {}))

        discovered = await _fetch_device_list(host, port)
        if not discovered:
            return self.async_abort(reason="no_devices")

        # Filter out already-added devices
        available = {
            d["dev_id"]: d["name"]
            for d in discovered
            if d["dev_id"] not in current_devices
        }

        if not available:
            return self.async_abort(reason="no_new_devices")

        if user_input is not None:
            dev_id = user_input["device"]
            name = user_input.get("name", available.get(dev_id, dev_id))
            webhook_id = user_input.get(
                "webhook_id", f"tdb-{dev_id[-8:]}-pir-motion"
            )
            current_devices[dev_id] = {
                "name": name,
                "webhook_motion": webhook_id,
            }
            return self.async_create_entry(
                title="",
                data={CONF_DEVICES: current_devices},
            )

        device_options = {dev_id: name for dev_id, name in available.items()}
        first_id = next(iter(available))

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(device_options),
                    vol.Optional("name", default=available[first_id]): str,
                    vol.Optional(
                        "webhook_id",
                        default=f"tdb-{first_id[-8:]}-pir-motion",
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_device(self, user_input=None):
        """Let user remove a previously added device."""
        current_devices = dict(self.config_entry.options.get(CONF_DEVICES, {}))

        if not current_devices:
            return self.async_abort(reason="no_devices_to_remove")

        if user_input is not None:
            dev_id = user_input["device"]
            current_devices.pop(dev_id, None)
            return self.async_create_entry(
                title="",
                data={CONF_DEVICES: current_devices},
            )

        device_options = {
            dev_id: info["name"] for dev_id, info in current_devices.items()
        }

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
        )
