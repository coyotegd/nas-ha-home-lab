"""Coordinator for GL-S200 TDB bridge WebSocket connection."""

import asyncio
import json
import logging

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RECONNECT_INTERVAL = 5


class S200TDBCoordinator(DataUpdateCoordinator):
    """Manages WebSocket connection to s200-bridge and stores device state."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, devices: dict):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.host = host
        self.port = port
        self.devices = devices  # {dev_id: {"name": ..., "webhook_motion": ...}}
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._listener_task: asyncio.Task | None = None
        self.discovered_devices: list[dict] = []  # From bridge device_list

        # Initialize per-device data structure
        self.data = {}
        for dev_id in self.devices:
            self.data[dev_id] = self._empty_device_state()

    @staticmethod
    def _empty_device_state() -> dict:
        return {
            "sensors": {},
            "led": {
                "led_left":  {"on": False, "r": 255, "g": 255, "b": 255, "brightness": 255},
                "led_right": {"on": False, "r": 255, "g": 255, "b": 255, "brightness": 255},
            },
            "connected": False,
            "motion": False,
        }

    def update_devices(self, devices: dict):
        """Update device list (called when options change)."""
        # Add new devices
        for dev_id in devices:
            if dev_id not in self.data:
                self.data[dev_id] = self._empty_device_state()
        # Remove old devices
        for dev_id in list(self.data):
            if dev_id not in devices:
                del self.data[dev_id]
        self.devices = devices
        self.async_set_updated_data(self.data)

    async def _async_update_data(self):
        """Return current cached data (push-based, no polling)."""
        return self.data

    def start_ws_listener(self):
        """Start the background WebSocket listener task."""
        self._listener_task = self.hass.async_create_background_task(
            self._ws_listen(), f"{DOMAIN}_ws_listener"
        )

    def stop_ws_listener(self):
        """Cancel the WebSocket listener and close the session."""
        if self._listener_task:
            self._listener_task.cancel()
        if self._session and not self._session.closed:
            self.hass.async_create_task(self._session.close())

    async def _ws_listen(self):
        """Connect to bridge WebSocket and process messages with auto-reconnect."""
        while True:
            try:
                self._session = aiohttp.ClientSession()
                url = f"ws://{self.host}:{self.port}"
                _LOGGER.info("Connecting to s200-bridge at %s", url)
                self._ws = await self._session.ws_connect(url, heartbeat=30)
                _LOGGER.info("Connected to s200-bridge")

                async for msg in self._ws:
                    if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                        try:
                            data = json.loads(msg.data)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        self._handle_message(data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("WebSocket error: %s", self._ws.exception())
                        break

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.error("WebSocket connection failed: %s", exc)
            finally:
                if self._ws and not self._ws.closed:
                    await self._ws.close()
                if self._session and not self._session.closed:
                    await self._session.close()
                self._ws = None
                self._session = None

            _LOGGER.info("Reconnecting in %ds…", RECONNECT_INTERVAL)
            await asyncio.sleep(RECONNECT_INTERVAL)

    @callback
    def _handle_message(self, msg: dict):
        """Process a message from the bridge."""
        msg_type = msg.get("type")
        if msg_type == "device_list":
            self.discovered_devices = msg.get("devices", [])
            _LOGGER.debug("Bridge device list: %d devices", len(self.discovered_devices))
            return

        dev_id = msg.get("dev_id")
        data = msg.get("data", {})

        if dev_id not in self.data:
            return

        if msg_type == "sensor_update":
            self.data[dev_id]["sensors"] = {
                "temperature": data.get("temperature"),
                "humidity": data.get("humidity"),
                "pressure": data.get("press"),
                "light": data.get("light"),
                "battery": data.get("battery_level"),
                "temp_spl0601": data.get("temp_spl0601"),
            }
            self.data[dev_id]["connected"] = data.get("connected", False)
            self.async_set_updated_data(self.data)

        elif msg_type == "led_status":
            for obj_key, state in data.items():
                if obj_key in ("led_left", "led_right"):
                    self.data[dev_id]["led"][obj_key] = {
                        "on": bool(state.get("on_off", 0)),
                        "r": state.get("r", 0),
                        "g": state.get("g", 0),
                        "b": state.get("b", 0),
                        "brightness": state.get("brightness", 255),
                    }
            self.async_set_updated_data(self.data)

    @callback
    def set_motion(self, dev_id: str, state: bool):
        """Set PIR motion state (called from webhook handler)."""
        if dev_id in self.data:
            self.data[dev_id]["motion"] = state
            self.async_set_updated_data(self.data)

    async def send_command(
        self,
        dev_id: str,
        cmd: str,
        params: dict | None = None,
        target: str = "all",
    ):
        """Send a LED command to the bridge via WebSocket."""
        if not self._ws or self._ws.closed:
            _LOGGER.error("Bridge not connected, cannot send command")
            return

        msg = {"type": "command", "dev_id": dev_id, "cmd": cmd, "target": target}
        if params:
            msg["params"] = params

        # Optimistic state update — apply to targeted LED(s)
        update_keys = (
            [target] if target in ("led_left", "led_right") else ["led_left", "led_right"]
        )
        for key in update_keys:
            led = self.data[dev_id]["led"].setdefault(
                key, {"on": False, "r": 255, "g": 255, "b": 255, "brightness": 255}
            )
            if cmd == "led_on":
                led["on"] = True
            elif cmd == "led_off":
                led["on"] = False
            elif cmd == "led_color" and params:
                led.update({"r": params["r"], "g": params["g"], "b": params["b"], "on": True})
            elif cmd == "led_level" and params:
                led["brightness"] = params.get("level", 255)
                led["on"] = True

        self.async_set_updated_data(self.data)
        await self._ws.send_str(json.dumps(msg))
