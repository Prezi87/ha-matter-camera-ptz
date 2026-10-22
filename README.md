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

### Automatic recovery after privacy mode (experimental)

If `native_camera_entity` and `privacy_entity` are set, this card now observes the
Home Assistant helper state. When the helper goes **OFF** (privacy), the card
removes its embedded live player and displays a privacy placeholder. When it
returns **ON**, the card waits for the camera to wake up and creates a **new**
picture-entity WebRTC session instead of keeping the failed previous one.

Optional setting: `privacy_resume_delay_ms: 5000` (default 5000, allowed 0–30000).
**Aqara G350 tested successfully with `privacy_resume_delay_ms: 1000`** after turning monitoring back on (one-second restart delay). Other cameras may need the longer default; increase to e.g. 7000–9000 if needed.
A small refresh icon in the card header manually restarts video without
reloading the entire Home Assistant dashboard.

This is based on the HA helper's **requested** state, not verified camera
privacy. A change made directly in the camera manufacturer app will not
automatically update a standalone helper. Other camera models can omit
`privacy_entity`, leaving video unchanged by vendor scenes.

### Read-only privacy state from Matter (experimental)

Matter.js Server API schema 14 exposes live AV Stream Management privacy flags
through `camera_get_capabilities`. The integration checks this every **5 seconds**
and adds read-only `binary_sensor` entities when reported by the camera:

- **Hardware privacy** → `hard_mode_on`
- **Livestream privacy** → `soft_livestream_mode_enabled`
- **Recording privacy** → `soft_recording_mode_enabled`
- **Live view blocked** → logical OR of hardware privacy and livestream privacy.

`ON` means the named privacy mode is active; `OFF` means it is not.
An unsupported/missing attribute is **not** reported as OFF, and a connection
failure marks sensors unavailable. The server returns a subscription-backed
state, which may lag slightly behind the actual camera.

To let the bundled card react when a camera's privacy mode changes **outside**
Home Assistant, set this optional parameter to the actual HA entity ID:

```yaml
privacy_status_entity: binary_sensor.YOUR_CAMERA_LIVE_VIEW_BLOCKED
```

The card will suppress the native picture-entity player when **either** the
user's `privacy_entity` helper is OFF **or** this reported privacy sensor
is ON. Once neither blocks video, a new WebRTC session starts after the
configurable resume delay. The Matter sensor is **read-only**; it does not
toggle a physical shutter, and the existing helper automation remains optional.

### Verified Aqara Camera Hub G350 physical shutter states (2026-10-22)

A user tested the G350 with its lens exposed, then physically retracted using
the existing Aqara privacy scene. After 10–15 seconds, Matter reporting showed:

| Matter privacy state | Lens exposed | Lens retracted |
|---|---|---|
| `hard_mode_on` | false | **true** |
| `soft_livestream_mode_enabled` | false | **true** |
| `soft_recording_mode_enabled` | false | **true** |
| Computed `live_view_blocked` | false | **true** |

This confirms **read-only detection** of the G350's physical privacy state
in this tested setup. It does **not** establish that Matter can actuate the
mechanical lens cover. Matter's `HardPrivacyModeOn` is a reported attribute,
not a universal writable command to retract a lens. Aqara scenes remain
optional external actions for physical actuation until verified otherwise.

For the G350, we recommend specifying the real `Live view blocked` binary
sensor entity ID as `privacy_status_entity` in the card, retaining
`privacy_entity` only if an input_boolean is currently used to trigger
manufacturer-specific scenes. The sensor is the *observed* state; the helper is
the *requested* state. Do not synchronize the helper back from the sensor
without guarding against automation loops.

For cameras other than G350, hardware-to-Matter privacy mapping remains
unverified. Sensor availability and polling delay must be considered.

Do not expose the Matter Server WebSocket outside your LAN. If isolating the
camera from the internet, test Matter video and PTZ separately from vendor
cloud scenes: vendor automations may depend on Aqara Home's connectivity.

## Native Matter video (work in progress — feature branch only)

This branch prototypes the built-in Home Assistant `camera` platform with
WebRTC negotiated over the Matter.js Server WebSocket API, **without RTSP or go2rtc**.
The native `camera` entity and live video were successfully tested on Aqara G350, but stability testing is incomplete. Do not replace the working
HACS release until the draft PR is validated.

- The backend probes `camera_get_capabilities` when the camera platform loads.
  Only a camera advertising the `Video` feature gets a `camera.*` entity.
  It requires **Matter Server API schema 14+**, independently of the Matter spec version.
- Home Assistant's `async_handle_async_webrtc_offer` and ICE callbacks relay
  signalling through a separate session-owning Matter Server WebSocket.
  The WebRTC media itself stays between browser and camera.
- If the camera advertises `Snapshot`, native HA thumbnails use
  `camera_snapshot`; otherwise the snapshot call returns no image.
- WebRTC connections are closed through `camera_stop_stream` on client close
  or integration removal. This needs real-world reconnection and teardown tests.
- To use a native HA camera entity in the bundled card, set
  `native_camera_entity: camera.your_matter_camera_live` instead of `stream`.
  The card then embeds HA's built-in picture-entity view (WebRTC).

**Privacy and Aqara scenes:** No Aqara-specific scenes are hardcoded.
The optional `privacy_entity` is a Home Assistant `input_boolean` and
needs its own automation. Matter-standard privacy attributes will be exposed
only when a camera advertises them; soft privacy != physical lens retraction.
The current preview card's center button stays entirely optional.

For now keep the existing Matter WebRTC Camera / go2rtc stream option as fallback.

Relevant docs:
- https://github.com/matter-js/matterjs-server/blob/main/docs/websockets_api.md
- https://github.com/matter-js/matterjs-server/blob/main/docs/websocket-api-schema-changelog.md
- https://developers.home-assistant.io/docs/core/entity/camera/

### Tested Aqara G350 native video example

The G350 restored its live WebRTC view automatically after turning monitoring ON with a one-second delay. To use a native Matter `camera` entity, see [the example card](examples/webrtc_ptz_card.yaml). This example does not require AlexxIT WebRTC Camera or go2rtc.

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

**Known limitation:** A user has tested the native video card and confirmed auto-recovery with a 1000 ms delay on Aqara G350; long-term stability, multi-viewer operation, and compatibility with other cameras remain untested.
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
- On the experimental branch, native Matter live video and JPEG snapshot work with Aqara G350; existing go2rtc fallback remains available.
- Other camera models have not been verified. Discovery relies on Matter PTZ cluster 1362.
- A bundled experimental joystick and native video card has been tested on Aqara G350, but requires more reliability testing; no Home Assistant Brands entry or formal HACS store approval yet.
- CI checks Python/JSON/YAML and JavaScript syntax plus privacy-toggle unit behavior; passing is **not** proof of broad runtime compatibility.

If you can test with a compatible camera, please open an issue with model, firmware,
Matter Server version, Home Assistant version and **redacted** logs.

## Security

Keep the Matter Server port 5580 confined to your trusted LAN.
The ws:// connection is unencrypted. Never publish access tokens, camera
credentials, fabric storage, chip.json, or private network secrets.

## API reference and license

Matter.js WebSocket API: https://github.com/matter-js/matterjs-server/blob/main/docs/websockets_api.md

MIT License. Contributions and issue reports welcome.
