"""Experimental native Home Assistant WebRTC camera for Matter.js schema 14+."""

from __future__ import annotations

import asyncio
import base64
import logging

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from webrtc_models import RTCIceCandidateInit

from .api import async_matter_request
from .const import CONF_CAMERA_NAME, CONF_ENDPOINT_ID, CONF_NODE_ID, CONF_URL, DOMAIN
from .video import MatterVideoSession

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create camera only when server supports the new camera capability API."""
    node_id = entry.data[CONF_NODE_ID]
    endpoint_id = entry.data[CONF_ENDPOINT_ID]
    try:
        capabilities = await async_matter_request(
            hass,
            entry.data[CONF_URL],
            "camera_get_capabilities",
            {"node_id": node_id, "endpoint_id": endpoint_id},
        )
    except HomeAssistantError as exc:
        _LOGGER.info("Native Matter video unavailable: %s", exc)
        return
    if not isinstance(capabilities, dict) or "Video" not in capabilities.get("features", []):
        _LOGGER.info("Matter PTZ endpoint %s does not advertise Video", endpoint_id)
        return
    async_add_entities([MatterNativeCamera(hass, entry, capabilities)])


class MatterNativeCamera(Camera):
    """Expose a Matter endpoint as a Home Assistant camera entity."""

    _attr_has_entity_name = True
    _attr_name = "Live"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, capabilities: dict):
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_live"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.data[CONF_CAMERA_NAME],
            "manufacturer": "Matter",
            "model": "Camera PTZ",
        }
        self._supports_snapshots = "Snapshot" in capabilities.get("features", [])
        self._sessions: dict[str, MatterVideoSession] = {}
        self._closing_tasks: set[asyncio.Task] = set()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return still photo from the camera when it advertises Snapshot."""
        if not self._supports_snapshots:
            return None
        args = {
            "node_id": self._entry.data[CONF_NODE_ID],
            "endpoint_id": self._entry.data[CONF_ENDPOINT_ID],
        }
        resolution = {}
        if width is not None and width > 0:
            resolution["width"] = width
        if height is not None and height > 0:
            resolution["height"] = height
        if resolution:
            args["resolution"] = resolution
        result = await async_matter_request(
            self._hass, self._entry.data[CONF_URL], "camera_snapshot", args
        )
        if not isinstance(result, dict) or not isinstance(result.get("data"), str):
            raise HomeAssistantError("Invalid Matter snapshot response")
        return base64.b64decode(result["data"])

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Pass HA SDP offer to Matter and forward camera responses."""
        old = self._sessions.pop(session_id, None)
        if old is not None:
            await old.close()
        session = MatterVideoSession(
            self._hass,
            self._entry.data[CONF_URL],
            self._entry.data[CONF_NODE_ID],
            self._entry.data[CONF_ENDPOINT_ID],
            session_id,
            send_message,
        )
        self._sessions[session_id] = session
        try:
            await session.start(offer_sdp)
        except Exception as exc:
            self._sessions.pop(session_id, None)
            send_message(WebRTCError("matter_webrtc_failed", str(exc)))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Forward the browser's trickled ICE candidates."""
        if session := self._sessions.get(session_id):
            await session.add_candidate(candidate)

    def close_webrtc_session(self, session_id: str) -> None:
        """Schedule teardown for this WebRTC session."""
        if session := self._sessions.pop(session_id, None):
            task = self._hass.async_create_task(session.close())
            self._closing_tasks.add(task)
            task.add_done_callback(self._closing_tasks.discard)

    async def async_will_remove_from_hass(self) -> None:
        """Stop sessions when the integration is unloaded."""
        for session_id in list(self._sessions):
            self.close_webrtc_session(session_id)
        if self._closing_tasks:
            await asyncio.gather(*self._closing_tasks, return_exceptions=True)
