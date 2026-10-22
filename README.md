# Matter Camera PTZ for Home Assistant

**Experimental community integration (v0.2.0-beta.1). Not production ready.**

Control Pan / Tilt / Zoom on compatible Matter cameras through the local
[Open Home Foundation Matter.js Server](https://github.com/matter-js/matterjs-server)
WebSocket API. No external cloud, Python shell commands, or additional container required.

This prototype was developed using an **Aqara Camera Hub G350** with a working
Matter.js Server 1.5.0 / Matter 1.5.1 connection, exposing PTZ cluster **1362 (0x0552)**.
**The custom Home Assistant integration has not yet been tested on a real HA installation.**
This project is unaffiliated with Aqara, Home Assistant, or Matter.js.

## Features

- UI config flow: enter the Matter Server WebSocket address, discover PTZ-capable camera endpoints, select the camera.
- Six Home Assistant button entities: pan left/right, tilt up/down, zoom in/out.
- Configure pan, tilt, and zoom steps as well as cooldown between commands.
- A custom action, **matter_camera_ptz.move**, for a one-time relative movement with caller-selected direction and step amount.
- Included custom:button-card example for distance proportional to how long a button is held.

### Prerequisites

- Home Assistant and HACS (for the easiest installation).
- A working, network-reachable OHF Matter.js Server with the camera already commissioned.
- Camera firmware that actually exposes PTZ via Matter.

**Note:** Home Assistant Matter Hub is a different application; this integration requires the actual **Matter.js Server**.

## Install through HACS as a custom repository

1. Open HACS, then Custom repositories.
2. Add **https://github.com/Prezi87/ha-matter-camera-ptz** with type **Integration**.
3. Install **Matter Camera PTZ** and restart Home Assistant.
4. Go to Settings → Devices & services → Add integration → Matter Camera PTZ.
5. Enter the Matter Server WebSocket address. Example on the same Docker host using host networking: **ws://127.0.0.1:5580/ws**.
6. Select the detected camera endpoint and configure step sizes. The integration should create six button entities.

Alternatively, copy the custom_components/matter_camera_ptz folder into your HA config/custom_components folder and restart HA.

## One card: WebRTC video + PTZ joystick (experimental)

**New in 0.2.0-beta.1:** A bundled Lovelace card displays a WebRTC live view above a compact PTZ joystick.
The backend still handles all PTZ via the local Matter.js Server.

**Video dependency:** Install AlexxIT WebRTC Camera separately from HACS.
WebRTC Camera uses go2rtc and is not bundled in this repository.
Verify first that an ordinary custom:webrtc-camera dashboard card already plays your stream.

### Installation

1. Update Matter Camera PTZ through HACS and restart Home Assistant.
2. Ensure AlexxIT WebRTC Camera is installed and working.
3. In Settings → Dashboards → ⋮ → Resources, add this JavaScript module:
   /matter_camera_ptz/matter-camera-ptz-card.js?v=0.2.0-beta.1
4. Refresh the browser, then add one Manual card using the sample below.

```yaml
type: custom:matter-camera-ptz-card
title: Aqara G350
ptz_entity: button.REPLACE_WITH_ANY_PTZ_BUTTON_FOR_THIS_CAMERA
stream: g350
privacy_entity: input_boolean.g350_monitoring
button_size: 62
gap: 8
pan_per_second: 30
pan_max: 90
tilt_per_second: 12
tilt_max: 24
zoom_delta: 5
zoom_repeat_ms: 3500
muted: true
video_controls: false
```

Set stream to a go2rtc stream name, or replace it with camera_entity: camera.your_camera.
The privacy_entity field is optional; if omitted, the center button is disabled.
The privacy helper only stores the requested state. An automation must map it to Aqara Scene Sync.
The card does not verify the physical position of the camera's privacy shutter.

- Left/right and up/down: one move on release, proportional to how long the button was held.
- Zoom: immediate move on press, then repeat while held, subject to backend cooldown.
- Keyboard, touch, and mouse actions are supported.
- The video display uses Home Assistant card helpers to embed custom:webrtc-camera.
- For YAML-mode dashboards, add the module URL to the Lovelace resources configuration instead.

**Security:** Prefer a go2rtc stream name instead of embedding RTSP credentials in the dashboard.
Restrict go2rtc's unauthenticated management port 1984 to trusted networks.

See also [the complete example](examples/webrtc_ptz_card.yaml).

**Known limitation:** This frontend card has not yet been tested in a live HA dashboard. The backend integration has been tested by an Aqara G350 user.
Report browser console errors with private IPs, passwords and tokens removed.

## Service / action for custom distance

Call **matter_camera_ptz.move** with:
- **entity_id**: any button entity created for the intended camera
- **direction**: left, right, up, down, zoom_in, or zoom_out
- **delta**: integer 1 to 180; the camera may clamp movements to its own range

Example in Home Assistant Actions:

    action: matter_camera_ptz.move
    data:
      entity_id: button.matter_camera_pan_left
      direction: left
      delta: 30

Replace the sample entity_id with the actual entity in your installation.
See [hold-release example](examples/hold_left.yaml) for a joystick that calculates delta on release.
This mechanism performs **one relative move after release**, not continuous motor drive.

## Cooldown

The Aqara G350 tested with a standalone script required approximately 3 seconds
between effective commands. The integration defaults to a 3.2 second minimum
gap after completing the previous command and rejects overlapping calls.
Tune this in Configure based on the hardware/firmware.

## Privacy mode

Privacy / lens retraction is **not part of this integration**. Aqara Home scenes
can be exported via Matter Scene Sync, but a UI helper only reports the
last requested setting, **not** the physical privacy state of the camera.

## Limitations and testing

- This is a **beta prototype**. Config flow, entity setup, options, and custom action require real HA testing.
- Video preview is not provided; retain your existing video integration.
- Other camera models have not been verified. Discovery relies on Matter PTZ cluster 1362.
- A bundled experimental joystick card is included, but has not yet been live-tested; no Home Assistant Brands entry or formal HACS store approval yet.
- CI checks Python/JSON/YAML syntax only; passing is **not** proof of runtime compatibility.

If you can test with a compatible camera, please open an issue with model, firmware,
Matter Server version, Home Assistant version and **redacted** logs.

## Security

Keep the Matter Server port 5580 confined to your trusted LAN.
The ws:// connection is unencrypted. Never publish access tokens, camera
credentials, fabric storage, chip.json, or private network secrets.

## API reference and license

Matter.js WebSocket API: https://github.com/matter-js/matterjs-server/blob/main/docs/websockets_api.md

MIT License. Contributions and issue reports welcome.
