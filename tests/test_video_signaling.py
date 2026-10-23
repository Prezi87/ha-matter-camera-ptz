"""Regression tests for Matter WebRTC SDP/remote ICE ordering.

Runs without Home Assistant installed using minimal type stubs.
"""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def module(name, **names):
    result = types.ModuleType(name)
    for key, value in names.items():
        setattr(result, key, value)
    sys.modules[name] = result
    return result


class WebRTCAnswer:
    def __init__(self, sdp):
        self.sdp = sdp


class WebRTCCandidate:
    def __init__(self, candidate):
        self.candidate = candidate


class WebRTCError:
    def __init__(self, code, message):
        self.code = code
        self.message = message


class RTCIceCandidateInit:
    def __init__(self, candidate, *, sdp_mid=None, sdp_m_line_index=None):
        self.candidate = candidate
        self.sdp_mid = sdp_mid
        self.sdp_m_line_index = sdp_m_line_index


# Only need enough module symbols for importing video.py; never send network I/O.
module("aiohttp", ClientWebSocketResponse=object, WSMsgType=types.SimpleNamespace(TEXT=1))
module("homeassistant")
module("homeassistant.components")
module(
    "homeassistant.components.camera",
    WebRTCAnswer=WebRTCAnswer,
    WebRTCCandidate=WebRTCCandidate,
    WebRTCError=WebRTCError,
    WebRTCSendMessage=object,
)
module("homeassistant.core", HomeAssistant=object)
module("homeassistant.exceptions", HomeAssistantError=RuntimeError)
module("homeassistant.helpers")
module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: None)
module("webrtc_models", RTCIceCandidateInit=RTCIceCandidateInit)

source = Path(__file__).resolve().parents[1] / "custom_components/matter_camera_ptz/video.py"
spec = importlib.util.spec_from_file_location("standalone_matter_video", source)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)
video._REMOTE_SDP_GRACE_SECONDS = 0.01


class RemoteCandidateOrderingTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self):
        messages = []
        session = video.MatterVideoSession(
            None, "ws://localhost:5580/ws", 12, 2, "test-session-key", messages.append
        )
        return session, messages

    async def test_candidate_before_answer_is_held(self):
        session, out = self.make_session()
        session._handle_callback({
            "event_type": "ice_candidates",
            "data": {"ice_candidates": [{"candidate": "candidate:1 1 UDP 1 192.0.2.1 1000 typ host"}]},
        })
        self.assertEqual(out, [])

        session._handle_callback({
            "event_type": "answer", "data": {"sdp": "v=0\r\n"}
        })
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], WebRTCAnswer)
        await asyncio.sleep(0.03)
        self.assertEqual(len(out), 2)
        self.assertIsInstance(out[1], WebRTCCandidate)
        await session.close()

    async def test_candidate_after_answer_is_delayed(self):
        session, out = self.make_session()
        session._handle_callback({
            "event_type": "answer", "data": {"sdp": "v=0\r\n"}
        })
        session._handle_callback({
            "event_type": "ice_candidates",
            "data": {"ice_candidates": [{"candidate": "candidate:1 1 UDP 1 192.0.2.2 1000 typ host"}]},
        })
        self.assertEqual(len(out), 1)
        await asyncio.sleep(0.03)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[1].candidate.candidate.startswith("candidate:"), True)
        await session.close()

    async def test_close_drops_pending_candidates(self):
        session, out = self.make_session()
        session._handle_callback({
            "event_type": "answer", "data": {"sdp": "v=0\r\n"}
        })
        session._handle_callback({
            "event_type": "ice_candidates",
            "data": {"ice_candidates": [{"candidate": "candidate:1 1 UDP 1 192.0.2.3 1000 typ host"}]},
        })
        await session.close()
        await asyncio.sleep(0.03)
        self.assertEqual(len(out), 1)

    async def test_missing_sdp_does_not_flush_candidates(self):
        session, out = self.make_session()
        session._handle_callback({
            "event_type": "ice_candidates",
            "data": {"ice_candidates": [{"candidate": "candidate:1 1 UDP 1 192.0.2.4 1000 typ host"}]},
        })
        session._handle_callback({
            "event_type": "answer", "data": {}
        })
        await asyncio.sleep(0.03)
        self.assertEqual(out, [])
        await session.close()


if __name__ == "__main__":
    unittest.main()
