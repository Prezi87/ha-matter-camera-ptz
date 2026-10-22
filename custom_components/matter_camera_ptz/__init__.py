"""Matter Camera PTZ integration."""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .api import MatterCameraPTZ
from .const import (
    CONF_COOLDOWN,
    CONF_ENDPOINT_ID,
    CONF_NODE_ID,
    CONF_URL,
    DEFAULT_COOLDOWN,
    DIRECTIONS,
    DOMAIN,
)

PLATFORMS = [Platform.BUTTON]

MOVE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("direction"): vol.In(DIRECTIONS),
        vol.Required("delta"): vol.All(vol.Coerce(int), vol.Range(min=1, max=180)),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register custom action once for the whole integration."""
    hass.data.setdefault(DOMAIN, {})
    await hass.http.async_register_static_paths(
        [StaticPathConfig(
            "/matter_camera_ptz/matter-camera-ptz-card.js",
            str(Path(__file__).parent / "frontend" / "matter-camera-ptz-card.js"),
            False,
        )]
    )

    async def handle_move(call: ServiceCall) -> None:
        entity = er.async_get(hass).async_get(call.data["entity_id"])
        if entity is None or entity.config_entry_id not in hass.data[DOMAIN]:
            raise HomeAssistantError("Select a PTZ button entity from Matter Camera PTZ")
        ptz = hass.data[DOMAIN][entity.config_entry_id]
        await ptz.async_move(call.data["direction"], call.data["delta"])

    hass.services.async_register(DOMAIN, "move", handle_move, schema=MOVE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a configured Matter camera."""
    ptz = MatterCameraPTZ(
        hass,
        entry.data[CONF_URL],
        entry.data[CONF_NODE_ID],
        entry.data[CONF_ENDPOINT_ID],
        float(entry.options.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ptz
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply options after user changes step lengths."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a configured camera."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
