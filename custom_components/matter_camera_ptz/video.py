"""Experimental native WebRTC signaling using the Matter.js schema 14 API."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from aiohttp import ClientWebSocketResponse, WSMsgType
from homeassistant.components.camera import (
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from webrtc_models import RTCIceCandidateInit

_LOGGER = logging.getLogger(__name__)


class MatterVideoSession:
    """One active browser video session per Matter Server WebSocket."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        node_id: int,
        endpoint_id: int,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        self._hass = hass
        self._url = url
        self._node_id = node_id
        self._endpoint_id = endpoint_id
        self._key = session_id
        self._send_message = send_message
        self._ws: ClientWebSocketResponse | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()
        self._start_sent = False
        self._closing = False
        self._queued_candidates: list[dict[str, Any]] = []

    async def start(self, offer_sdp: str) -> None:
        """Ask camera to create live view with SDP offer from Home Assistant."""
        self._ws = await async_get_clientsession(self._hass).ws_connect(
            self._url, heartbeat=20, timeout=20
        )
        self._reader_task = asyncio.create_task(self._read_messages())
        args = {
            "node_id": self._node_id,
            "endpoint_id": self._endpoint_id,
            "client_session_key": self._key,
            "stream_usage": "LiveView",
            "sdp": offer_sdp,
        }
        try:
            result = await self._call("camera_start_stream", args, timeout=45)
            self._start_sent = True
            _LOGGER.debug(
                "Matter WebRTC start mode: %s",
                result.get("mode") if isinstance(result, dict) else result,
            )
            if self._queued_candidates:
                candidates = self._queued_candidates
                self._queued_candidates = []
                await self._submit_candidates(candidates)
        except Exception:
            await self.close()
            raise

    async def add_candidate(self, candidate: RTCIceCandidateInit) -> None:
        """Forward browser ICE candidates to the Matter WebRTC session."""
        item = {
            "candidate": candidate.candidate,
            "sdpMid": candidate.sdp_mid,
            "sdpMLineIndex": candidate.sdp_m_line_index,
        }
        if self._closing:
            return
        if not self._ws or not self._start_sent:
            self._queued_candidates.append(item)
            return
        await self._submit_candidates([item])

    async def _submit_candidates(self, candidates: list[dict[str, Any]]) -> None:
        await self._call(
            "camera_provide_ice_candidates",
            {
                "node_id": self._node_id,
                "endpoint_id": self._endpoint_id,
                "client_session_key": self._key,
                "ice_candidates": candidates,
            },
            timeout=20,
        )

    async def _call(
        self, command: str, args: dict[str, Any], timeout: int = 25
    ) -> Any:
        if not self._ws or self._ws.closed:
            raise HomeAssistantError("Matter WebRTC WebSocket is closed")
        ident = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[ident] = future
        try:
            async with self._send_lock:
                await self._ws.send_json(
                    {"message_id": ident, "command": command, "args": args}
                )
            async with asyncio.timeout(timeout):
                return await future
        finally:
            self._pending.pop(ident, None)

    async def _read_messages(self) -> None:
        error = HomeAssistantError("Matter WebRTC connection closed")
        try:
            assert self._ws is not None
            async for message in self._ws:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(message.data)
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                ident = payload.get("message_id")
                if ident in self._pending:
                    future = self._pending[ident]
                    if not future.done():
                        if "error_code" in payload:
                            future.set_exception(
                                HomeAssistantError(
                                    f"Matter Server {payload.get('error_code')}: "
                                    f"{payload.get('details', 'camera API error')}"
                                )
                            )
                        else:
                            future.set_result(payload.get("result"))
                    continue
                if payload.get("event") == "webrtc_callback":
                    event = payload.get("data") or {}
                    if event.get("client_session_key") == self._key:
                        self._handle_callback(event)
                elif payload.get("event") == "camera_session_ended":
                    event = payload.get("data") or {}
                    if event.get("client_session_key") == self._key:
                        self._send_message(
                            WebRTCError("matter_webrtc_ended", "Camera closed session")
                        )
                        break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = HomeAssistantError(f"Matter WebRTC connection failed: {exc}")
        finally:
            for future in tuple(self._pending.values()):
                if not future.done():
                    future.set_exception(error)
            if not self._closing:
                self._send_message(
                    WebRTCError("matter_webrtc_disconnected", str(error))
                )

    def _handle_callback(self, event: dict[str, Any]) -> None:
        kind = event.get("event_type")
        data = event.get("data") or {}
        if kind == "answer":
            if sdp := data.get("sdp"):
                self._send_message(WebRTCAnswer(sdp))
        elif kind == "ice_candidates":
            for candidate in data.get("ice_candidates") or []:
                self._send_message(
                    WebRTCCandidate(
                        RTCIceCandidateInit(
                            candidate["candidate"],
                            sdp_mid=candidate.get("sdpMid"),
                            sdp_m_line_index=candidate.get("sdpMLineIndex"),
                        )
                    )
                )
        elif kind == "end":
            self._send_message(
                WebRTCError("matter_webrtc_ended", "Camera ended stream")
            )

    async def close(self) -> None:
        """Stop session on camera and close the session-owning socket."""
        if self._closing:
            return
        self._closing = True
        if self._ws is not None and not self._ws.closed and self._start_sent:
            try:
                await self._call(
                    "camera_stop_stream",
                    {
                        "node_id": self._node_id,
                        "endpoint_id": self._endpoint_id,
                        "client_session_key": self._key,
                    },
                    timeout=10,
                )
            except (TimeoutError, HomeAssistantError) as exc:
                _LOGGER.debug("Cannot stop Matter video session: %s", exc)
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
