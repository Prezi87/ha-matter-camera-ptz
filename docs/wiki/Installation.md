# Installation

## Prerequisites

- Home Assistant and HACS (recommended).
- Reachable Open Home Foundation Matter.js Server with WebSocket API **schema 14+** for video.
- A camera already commissioned to Matter Server; an endpoint exposing PTZ cluster **1362**.
- Reliable LAN and local IPv6 connectivity between Matter Server, camera, Home Assistant and the client browser.

Do not expose Matter Server port 5580 to the public internet.

## HACS custom repository

1. Open **HACS → Custom repositories**.
2. Add `https://github.com/Prezi87/ha-matter-camera-ptz` as an **Integration**.
3. Install **Matter Camera PTZ v0.3.1**.
4. Restart Home Assistant.
5. Navigate to **Settings → Devices & services → Add integration → Matter Camera PTZ**.
6. Provide the Matter Server WebSocket URL:
   - `ws://127.0.0.1:5580/ws` **only** when Home Assistant and Matter Server share host networking on the same host.
   - Otherwise use a server address reachable **from the HA runtime**, such as `ws://YOUR_MATTER_SERVER_IP:5580/ws`.
7. Select the camera endpoint. Supported PTZ buttons, camera and privacy entities are created according to reported capabilities.

## Upgrading from a manual or experimental installation

Before upgrading, back up HA configuration and `custom_components/matter_camera_ptz`. Install the HACS release, restart HA and verify the version:

```bash
docker exec homeassistant python3 -c 'import json; print(json.load(open("/config/custom_components/matter_camera_ptz/manifest.json"))["version"])'
```

Expected: `0.3.1`. Existing Matter fabric, Node ID and commissioning data must be kept; **do not delete Matter Server data or re-pair the camera**.

After upgrade, update the dashboard JavaScript resource to `/matter_camera_ptz/matter-camera-ptz-card.js?v=0.3.1` and refresh the browser. Keep just **one** instance of the resource.

Continue with [[Lovelace-Card]].

## Installation scope

This is presently a **custom HACS repository** and not a listing in the default HACS catalog. It is not a replacement Matter controller. Other Matter camera models have not yet been validated.
