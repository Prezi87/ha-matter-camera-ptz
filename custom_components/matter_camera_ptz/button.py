"""Six stateless movement buttons for one Matter camera."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CAMERA_NAME,
    CONF_ENDPOINT_ID,
    CONF_NODE_ID,
    CONF_PAN_STEP,
    CONF_TILT_STEP,
    CONF_URL,
    CONF_ZOOM_STEP,
    DEFAULT_PAN_STEP,
    DEFAULT_TILT_STEP,
    DEFAULT_ZOOM_STEP,
    DIRECTIONS,
    DOMAIN,
)

ICONS = {
    "left": "mdi:arrow-left-bold",
    "right": "mdi:arrow-right-bold",
    "up": "mdi:arrow-up-bold",
    "down": "mdi:arrow-down-bold",
    "zoom_in": "mdi:magnify-plus-outline",
    "zoom_out": "mdi:magnify-minus-outline",
}

NAMES = {
    "left": "Pan left",
    "right": "Pan right",
    "up": "Tilt up",
    "down": "Tilt down",
    "zoom_in": "Zoom in",
    "zoom_out": "Zoom out",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register movement entities for each configured camera."""
    async_add_entities([MatterPTZButton(hass, entry, direction) for direction in DIRECTIONS])


class MatterPTZButton(ButtonEntity):
    """Button that sends a relative Matter PTZ command."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, direction: str):
        self.hass = hass
        self.entry = entry
        self.direction = direction
        self._attr_name = NAMES[direction]
        self._attr_icon = ICONS[direction]
        self._attr_unique_id = f"{entry.unique_id}_{direction}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.data[CONF_CAMERA_NAME],
            "manufacturer": "Matter",
            "model": "Camera PTZ",
            "configuration_url": entry.data[CONF_URL].replace("ws://", "http://").replace("wss://", "https://").removesuffix("/ws"),
        }

    async def async_press(self) -> None:
        """Move the configured amount in this button's direction."""
        options = self.entry.options
        if self.direction in ("left", "right"):
            delta = int(options.get(CONF_PAN_STEP, DEFAULT_PAN_STEP))
        elif self.direction in ("up", "down"):
            delta = int(options.get(CONF_TILT_STEP, DEFAULT_TILT_STEP))
        else:
            delta = int(options.get(CONF_ZOOM_STEP, DEFAULT_ZOOM_STEP))
        await self.hass.data[DOMAIN][self.entry.entry_id].async_move(self.direction, delta)
