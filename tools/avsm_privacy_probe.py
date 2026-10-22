#!/usr/bin/env python3
"""Read/test Matter 1.5 camera *soft* privacy flags using OHF Matter Server.

This is a manually invoked diagnostic, NOT a Home Assistant integration
service. It NEVER writes HardwarePrivacyModeOn (attribute 21, read-only).

Example inside a host-network Home Assistant Docker container:
    python3 /config/avsm_privacy_probe.py status --node 12 --endpoint 2
    python3 /config/avsm_privacy_probe.py soft-on --node 12 --endpoint 2 --execute
    python3 /config/avsm_privacy_probe.py soft-off --node 12 --endpoint 2 --execute
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

import aiohttp

AVSM_CLUSTER = 1361  # 0x0551, Camera AV Stream Management
SOFT_RECORDING = 19   # 0x0013, writable if device supports it
SOFT_LIVESTREAM = 20  # 0x0014, writable if device supports it
HARD_PRIVACY = 21     # 0x0015, read-only; never write
SOFT_KEYS = (
    ("soft_recording_mode_enabled", SOFT_RECORDING),
    ("soft_livestream_mode_enabled", SOFT_LIVESTREAM),
)


async def request(ws, command: str, args: dict):
    ident = uuid.uuid4().hex
    await ws.send_json({"message_id": ident, "command": command, "args": args})
    while True:
        message = await ws.receive(timeout=30)
        if message.type != aiohttp.WSMsgType.TEXT:
            raise RuntimeError(f"Matter websocket disconnected ({message.type})")
        response = json.loads(message.data)
        if not isinstance(response, dict) or response.get("message_id") != ident:
            continue
        if "error_code" in response:
            raise RuntimeError(
                f"Matter {command} failed: {response.get('error_code')} "
                f"{response.get('details', '')}"
            )
        if "result" not in response:
            raise RuntimeError(f"Matter {command} returned no result")
        return response["result"]


async def get_privacy(ws, node: int, endpoint: int) -> dict:
    capabilities = await request(
        ws, "camera_get_capabilities", {"node_id": node, "endpoint_id": endpoint}
    )
    if not isinstance(capabilities, dict):
        raise RuntimeError("Unexpected camera_get_capabilities response")
    privacy = capabilities.get("privacy")
    if not isinstance(privacy, dict):
        raise RuntimeError("No privacy dictionary in capabilities response")
    return privacy


def show_privacy(privacy: dict) -> None:
    for label in (
        "hard_mode_on",
        "soft_livestream_mode_enabled",
        "soft_recording_mode_enabled",
    ):
        print(f"  {label}: {privacy.get(label, 'NOT REPORTED')}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read or manually test local Matter camera privacy"
    )
    parser.add_argument("action", choices=["status", "soft-on", "soft-off"])
    parser.add_argument("--node", type=int, required=True)
    parser.add_argument("--endpoint", type=int, required=True)
    parser.add_argument("--url", default="ws://127.0.0.1:5580/ws")
    parser.add_argument(
        "--execute", action="store_true",
        help="REQUIRED to actually change soft privacy. Omit to preview actions.",
    )
    args = parser.parse_args()
    if args.node < 1 or not 0 <= args.endpoint <= 65534:
        parser.error("Invalid node or endpoint id")

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(args.url, heartbeat=15) as ws:
            await ws.receive_json(timeout=10)  # Matter server_info
            before = await get_privacy(ws, args.node, args.endpoint)
            print("Before (Matter-reported privacy):")
            show_privacy(before)
            if args.action == "status":
                return

            desired = args.action == "soft-on"
            print(
                f"\nRequested action: {'ENABLE' if desired else 'DISABLE'} "
                "SOFT livestream + recording privacy"
            )
            print("WARNING: This does not command the physical shutter directly.")
            if not args.execute:
                print("DRY RUN ONLY. Add --execute to write two soft attributes.")
                return

            for field, attribute_id in SOFT_KEYS:
                if not isinstance(before.get(field), bool):
                    raise RuntimeError(
                        f"{field} is not reported as a boolean; stopping without "
                        "writing any remaining attributes"
                    )
                attr_path = f"{args.endpoint}/{AVSM_CLUSTER}/{attribute_id}"
                response = await request(
                    ws, "write_attribute", {
                        "node_id": args.node,
                        "attribute_path": attr_path,
                        "value": desired,
                    }
                )
                if not isinstance(response, list) or len(response) != 1:
                    raise RuntimeError(
                        f"Unexpected write reply for {attr_path}: {response!r}"
                    )
                status = response[0].get("Status")
                print(f"Wrote {attr_path} = {desired}: Matter Status {status}")
                if status != 0:
                    raise RuntimeError(
                        f"Write to {attr_path} refused (Matter status={status}); "
                        "another attribute may already have been changed"
                    )
                await asyncio.sleep(0.5)

            await asyncio.sleep(2)
            after = await get_privacy(ws, args.node, args.endpoint)
            print("\nAfter (Matter-reported privacy):")
            show_privacy(after)
            if not all(after.get(key) is desired for key, _ in SOFT_KEYS):
                print(
                    "WARNING: readback not yet equal to request; the subscription "
                    "may lag or the device may reject/revert the state."
                )
            print(
                "\nObserve the physical lens separately; only HARD privacy can "
                "report its physical state, and it is read-only."
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
