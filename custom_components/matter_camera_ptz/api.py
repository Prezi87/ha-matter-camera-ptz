"""Thin, stateless WebSocket client for the Open Home Foundation Matter Server.

Tested protocol: matterjs-server 1.5.0, schema version 14, Aqara G350.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from time import monotonic
from uuid import uuid4

from aiohttp import ClientError, WSMsgType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DIRECTION_ARGUMENT, PTZ_CLUSTER_ID, PTZ_COMMAND

_LOGGER = logging.getLogger(__name__)


async def async_matter_request(hass: HomeAssistant, url: str, command: str, args: dict | None = None):
    """Execute one OHF Matter WebSocket API request; ignore server push messages."""
    message_id = uuid4().hex
    request = {"message_id": message_id, "command": command, "args": args or {}}
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(25):
            async with session.ws_connect(url, heartbeat=15) as ws:
                await ws.send_json(request)
                while True:
                    message = await ws.receive()
                    if message.type == WSMsgType.TEXT:
                        payload = json.loads(message.data)
                        if not isinstance(payload, dict) or payload.get("message_id") != message_id:
                            continue
                        if "error_code" in payload:
                            raise HomeAssistantError(
                                f"Matter Server rejected {command}: "
                                f"{payload.get('details', payload.get('error_code'))}"
                            )
                        if "result" not in payload:
                            raise HomeAssistantError(f"Matter Server: invalid {command} response")
                        return payload["result"]
                    if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSE, WSMsgType.ERROR):
                        raise HomeAssistantError("Matter Server closed the WebSocket connection")
    except (asyncio.TimeoutError, ClientError, OSError, ValueError) as exc:
        raise HomeAssistantError(f"Cannot communicate with Matter Server: {exc}") from exc


async def async_discover_cameras(hass: HomeAssistant, url: str) -> list[dict]:
    """Discover commissioned Matter nodes with the MPTZ cluster on a camera endpoint."""
    nodes = await async_matter_request(hass, url, "get_nodes", {"only_available": False})
    if not isinstance(nodes, list):
        raise HomeAssistantError("Unexpected get_nodes response from Matter Server")

    found = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        attributes = node.get("attributes") or {}
        if not isinstance(attributes, dict):
            continue
        node_id = node.get("node_id")
        if node_id is None:
            continue
        endpoints = set()
        for path in attributes:
            match = re.fullmatch(r"(\d+)/1362/\d+", str(path))
            if match:
                endpoints.add(int(match.group(1)))

        node_name = (
            attributes.get("0/40/5")  # NodeLabel, when available
            or attributes.get("0/40/3")  # ProductName
            or f"Matter camera {node_id}"
        )
        for endpoint in sorted(endpoints):
            found.append(
                {
                    "node_id": int(node_id),
                    "endpoint_id": endpoint,
                    "name": str(node_name),
                    "available": bool(node.get("available", False)),
                }
            )
    return found


class MatterCameraPTZ:
    """Send rate-limited PTZ commands to one Matter camera."""

    def __init__(self, hass: HomeAssistant, url: str, node_id: int, endpoint_id: int, cooldown: float):
        self.hass = hass
        self.url = url
        self.node_id = node_id
        self.endpoint_id = endpoint_id
        self.cooldown = cooldown
        self._lock = asyncio.Lock()
        self._last_completed = -10_000.0

    async def async_move(self, direction: str, delta: int) -> None:
        """Issue one relative movement; do not flood a camera that is still moving."""
        if direction not in DIRECTION_ARGUMENT:
            raise HomeAssistantError(f"Unsupported PTZ direction: {direction}")
        if isinstance(delta, bool) or not isinstance(delta, int) or not 1 <= delta <= 180:
            raise HomeAssistantError("PTZ movement must be an integer from 1 to 180")

        if self._lock.locked():
            raise HomeAssistantError("Camera PTZ is busy; retry after the previous move")

        async with self._lock:
            remaining = self.cooldown - (monotonic() - self._last_completed)
            if remaining > 0:
                await asyncio.sleep(remaining)
            field, sign = DIRECTION_ARGUMENT[direction]
            await async_matter_request(
                self.hass,
                self.url,
                "device_command",
                {
                    "node_id": self.node_id,
                    "endpoint_id": self.endpoint_id,
                    "cluster_id": PTZ_CLUSTER_ID,
                    "command_name": PTZ_COMMAND,
                    "payload": {field: sign * delta},
                },
            )
            self._last_completed = monotonic()
            _LOGGER.debug("PTZ movement sent to node %s, endpoint %s", self.node_id, self.endpoint_id)
