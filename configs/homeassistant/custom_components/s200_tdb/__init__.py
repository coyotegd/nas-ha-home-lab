"""GL-S200 TDB Boards integration."""

import logging

from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, CONF_DEVICES, LEGACY_DEVICES
from . import config_flow as _  # noqa: F401 — force handler registration in HANDLERS
from .coordinator import S200TDBCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "light"]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry from v1 to v2."""
    if config_entry.version < 2:
        _LOGGER.info("Migrating s200_tdb config entry from v1 to v2")
        new_options = dict(config_entry.options)
        new_options[CONF_DEVICES] = dict(LEGACY_DEVICES)
        hass.config_entries.async_update_entry(
            config_entry,
            options=new_options,
            version=2,
        )
        _LOGGER.info(
            "Migration complete: %d legacy devices added to options",
            len(LEGACY_DEVICES),
        )
    return True


def _get_devices(entry: ConfigEntry) -> dict:
    """Return the devices dict from entry options."""
    return dict(entry.options.get(CONF_DEVICES, {}))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up S200 TDB from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    devices = _get_devices(entry)

    coordinator = S200TDBCoordinator(hass, host, port, devices)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register PIR motion webhooks for configured devices
    _register_webhooks(hass, coordinator, devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket listener (connects to s200-bridge)
    coordinator.start_ws_listener()

    # Listen for options updates (device add/remove)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Force re-evaluation of supports_options now that config_flow is loaded
    entry.clear_state_cache()

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration to pick up new devices."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: S200TDBCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator.stop_ws_listener()

    devices = _get_devices(entry)
    for dev_id, dev_info in devices.items():
        try:
            webhook_unregister(hass, dev_info["webhook_motion"])
        except KeyError:
            pass

    # Cancel any pending motion reset timers
    for dev_id in devices:
        cancel_key = f"{DOMAIN}_{dev_id}_motion_reset"
        cancel = hass.data.get(DOMAIN, {}).pop(cancel_key, None)
        if cancel:
            cancel()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _register_webhooks(hass, coordinator, devices):
    """Register PIR motion webhooks for all configured devices."""
    for dev_id, dev_info in devices.items():
        wh_id = dev_info["webhook_motion"]
        # Unregister any stale handler
        try:
            webhook_unregister(hass, wh_id)
        except KeyError:
            pass
        webhook_register(
            hass,
            DOMAIN,
            f"{dev_info['name']} PIR Motion",
            wh_id,
            _make_pir_handler(hass, coordinator, dev_id),
            local_only=True,
            allowed_methods=frozenset({"POST"}),
        )


def _make_pir_handler(hass, coordinator, dev_id):
    """Create a webhook handler for PIR motion events."""
    cancel_key = f"{DOMAIN}_{dev_id}_motion_reset"

    async def handle_webhook(hass_ref, webhook_id, request):
        _LOGGER.info("PIR motion: %s (webhook %s)", dev_id, webhook_id)
        coordinator.set_motion(dev_id, True)

        # Cancel previous auto-reset timer
        prev_cancel = hass.data.get(DOMAIN, {}).get(cancel_key)
        if prev_cancel:
            prev_cancel()

        # Schedule auto-reset to OFF after 30 seconds
        @callback
        def _reset_motion(_now):
            coordinator.set_motion(dev_id, False)

        cancel = async_call_later(hass, 30, _reset_motion)
        hass.data.setdefault(DOMAIN, {})[cancel_key] = cancel

    return handle_webhook
