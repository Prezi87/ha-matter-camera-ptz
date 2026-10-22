# Matter Camera PTZ for Home Assistant

**Experimental community integration (v0.1.0-beta.1). Not production ready.**

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
- No built-in joystick card, Home Assistant Brands entry, or formal HACS store approval yet.
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
