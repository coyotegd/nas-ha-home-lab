"""Light platform for GL-S200 TDB Boards."""

import colorsys

from homeassistant.components.light import ColorMode, LightEntity
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
    """Set up S200 TDB lights — one entity per physical LED pixel."""
    coordinator: S200TDBCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id, dev_info in coordinator.devices.items():
        entities.append(S200TDBLight(coordinator, dev_id, dev_info["name"], "led_left"))
        entities.append(S200TDBLight(coordinator, dev_id, dev_info["name"], "led_right"))
    async_add_entities(entities)


def _rgb_to_hs(r: int, g: int, b: int) -> tuple[float, float]:
    """Convert RGB (0-255) to HS (hue 0-360, saturation 0-100)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (round(h * 360, 2), round(s * 100, 2))


def _hs_to_full_rgb(hs: tuple[float, float]) -> tuple[int, int, int]:
    """Convert HS color to full-brightness RGB (0-255). Brightness is kept separate."""
    h = hs[0] / 360
    s = hs[1] / 100
    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)  # v=1.0; firmware controls brightness independently
    return (round(r * 255), round(g * 255), round(b * 255))


class S200TDBLight(CoordinatorEntity, LightEntity):
    """One physical RGB LED on a TDB board (led_left or led_right)."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

    _SIDE_NAMES = {"led_left": "LED Left", "led_right": "LED Right"}

    def __init__(self, coordinator, dev_id, dev_name, side: str):
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._side = side
        self._attr_unique_id = f"s200_tdb_{dev_id}_{side}"
        self._attr_name = self._SIDE_NAMES[side]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="GL-iNet",
            model="Thread Dev Board",
        )

    def _led(self) -> dict:
        """Return current state dict for this LED pixel."""
        return (
            self.coordinator.data
            .get(self._dev_id, {})
            .get("led", {})
            .get(self._side, {})
        )

    @property
    def is_on(self) -> bool | None:
        return self._led().get("on", False)

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255) from the firmware's independent brightness scaler."""
        return self._led().get("brightness", 255)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return HS color derived from the stored full-brightness target RGB."""
        led = self._led()
        if "r" in led:
            return _rgb_to_hs(led["r"], led["g"], led["b"])
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the LED, optionally changing color and/or brightness independently."""
        hs = kwargs.get("hs_color")
        brightness = kwargs.get("brightness")

        if brightness is not None:
            # Set brightness scaler first so color-on triggers at the right level
            await self.coordinator.send_command(
                self._dev_id, "led_level", {"level": brightness}, target=self._side
            )

        if hs is not None:
            # Send full-brightness RGB — firmware's brightness[] scaler handles dimming
            r, g, b = _hs_to_full_rgb(hs)
            await self.coordinator.send_command(
                self._dev_id, "led_color", {"r": r, "g": g, "b": b}, target=self._side
            )

        if hs is None and brightness is None:
            # Pure turn-on with no attribute changes
            await self.coordinator.send_command(
                self._dev_id, "led_on", target=self._side
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off this LED pixel."""
        await self.coordinator.send_command(
            self._dev_id, "led_off", target=self._side
        )
