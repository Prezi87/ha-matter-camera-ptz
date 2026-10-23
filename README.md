# Matter Camera PTZ for Home Assistant

**Local Matter 1.5 camera video, PTZ and privacy controls for Home Assistant.**

This is a community integration, tested end-to-end on an **Aqara Camera Hub G350**.
Other Matter cameras may expose only some of the capabilities. The project is not
affiliated with Aqara, Home Assistant, HACS or the Matter.js maintainers.

## What works

| Capability | Aqara G350 | Other Matter cameras |
|---|---|---|
| Native HA `camera` with live WebRTC, no RTSP/go2rtc required | Tested | Requires `Video` support |
| JPEG snapshot | Tested (1920×1080) | Requires `Snapshot` |
| Pan / tilt / zoom | Tested | Requires Matter PTZ cluster 1362 |
| Read-only hardware / recording / live privacy flags | Tested | Capability-dependent |
| `Privacy mode` switch (ON = private) | Tested; physically retracts lens | Only if writable soft attributes are supported; physical shutter behavior not guaranteed |
| Integrated Lovelace card (live view + joystick) | Tested | Camera and PTZ entities required |

The Aqara G350 has also been tested behind an **OpenWrt firewall blocking camera WAN**:
video, PTZ, privacy sensor state, and native privacy switch continue to work
locally. When WAN was blocked, the first live image took approximately **7 seconds**;
the behavior appears linked to G350's WAN-dependent startup, and is documented in [issue #3](https://github.com/Prezi87/ha-matter-camera-ptz/issues/3).

## Requirements

- Home Assistant with HACS (recommended).
- A running [Open Home Foundation Matter.js Server](https://github.com/matter-js/matterjs-server)
  exposing its WebSocket API. **Schema 14+ is required for native camera video.**
  Matter standard version and server API schema version are separate.
- A Matter-commissioned, reachable camera exposing **PTZ cluster 1362**.
- LAN connectivity between camera, Matter Server, Home Assistant and browser.
  Preserve local IPv6 and Matter discovery; do not expose Matter Server port 5580
  to the public internet.
- This integration is **not** Home Assistant Matter Hub, Aqara LANLink or
  an alternative Matter controller/commissioning tool. Pair your camera with
  Matter Server first.

## Install through HACS (custom repository)

1. Open **HACS → Custom repositories**.
2. Add `https://github.com/Prezi87/ha-matter-camera-ptz`, category **Integration**.
3. Download the latest `v0.3.1` release of **Matter Camera PTZ** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Matter Camera PTZ**.
5. Provide Matter Server WebSocket URL. For HA and Matter Server using Docker
   **host networking on the same host**, use `ws://127.0.0.1:5580/ws`.
   Otherwise, use an address reachable **from the HA container**, e.g.
   `ws://192.168.1.30:5580/ws` when that is the Matter Server host.
6. Select the detected Matter camera endpoint. Home Assistant creates
   six PTZ buttons, and additionally creates camera, privacy sensors and
   privacy switch **only if supported**.

To update an older manually copied installation, **make a backup of the
`custom_components/matter_camera_ptz` directory first**. Install with HACS,
restart HA, and verify the existing configuration entry and entity IDs;
do not re-pair or reset your Matter Server. HACS manages only the integration
files; it does not modify Matter Server fabric data.

Manual alternative: copy `custom_components/matter_camera_ptz` into your
Home Assistant `/config/custom_components/` and restart.

> **Important:** This repository is available as a **custom HACS repository**.
> It has not been submitted to or accepted into HACS's default catalog.

## Display a live picture

The integration creates a regular Home Assistant `camera` entity.
You can use a built-in card without any extra frontend installation:

```yaml
type: picture-entity
entity: camera.YOUR_CAMERA_LIVE
camera_view: live
show_name: false
show_state: false
```

Replace the placeholder with the actual camera entity ID from
**Settings → Devices & services → Matter Camera PTZ → your camera**.

### Bundled live-video + joystick card

Home Assistant does not automatically register custom dashboard cards
just because their backend files were installed. Register **one** JavaScript
module under **Settings → Dashboards → Resources**:

```text
/matter_camera_ptz/matter-camera-ptz-card.js?v=0.3.1
```

Resource type: **JavaScript module**. If an older version is already listed,
**edit the existing resource**; do not add a duplicate. Refresh your browser.

Next, add a **Manual** Lovelace card:

```yaml
type: custom:matter-camera-ptz-card
title: Aqara G350
native_camera_entity: camera.YOUR_CAMERA_LIVE
ptz_entity: button.YOUR_PAN_LEFT_BUTTON
privacy_switch_entity: switch.YOUR_PRIVACY_MODE
privacy_status_entity: binary_sensor.YOUR_LIVE_VIEW_BLOCKED
privacy_resume_delay_ms: 1000
button_size: 62
gap: 8
pan_per_second: 30
pan_max: 90
tilt_per_second: 12
tilt_max: 24
zoom_delta: 5
zoom_repeat_ms: 3500
```

Use **any one** PTZ `button` entity belonging to this integration for
`ptz_entity`. The card sends movement via `matter_camera_ptz.move`.
The privacy fields are **optional**: omit the switch if unsupported,
and omit the binary sensor if your camera does not provide it.
For G350, `privacy_resume_delay_ms: 1000` is tested; for other devices,
the default is 5000 ms.

With the native privacy switch, **ON means the camera is private**.
The card hides video while privacy is active and renegotiates WebRTC after
privacy clears. It will use the switch instead of any legacy
`privacy_entity` helper if both are provided.

Full example: [examples/webrtc_ptz_card.yaml](examples/webrtc_ptz_card.yaml).
The older `privacy_entity: input_boolean.*` scene/automation method remains
available when a camera does not support native privacy control:
[legacy example](examples/legacy_vendor_scenes_card.yaml).
An external WebRTC Camera/go2rtc stream can also be used as fallback by
setting `stream` or `camera_entity` instead of `native_camera_entity`.

## PTZ action

```yaml
action: matter_camera_ptz.move
data:
  entity_id: button.YOUR_PAN_LEFT_BUTTON
  direction: left
  delta: 30
```

Directions: `left`, `right`, `up`, `down`, `zoom_in`,
`zoom_out`. Delta is an integer from 1 to 180; supported ranges and actual
movement differ by camera. The G350 typically needs a cooldown of about
3 seconds between effective commands; tune this in integration options.

The Lovelace joystick calculates relative movement based on press duration
and sends one movement on release. Zoom begins on press and can repeat
while held. The backend rate-limits PTZ commands.

## Privacy and safety

The `Privacy mode` switch writes Matter AV Stream Management soft
recording and soft livestream privacy attributes (19 and 20 in cluster 1361).
The read-only `HardPrivacyModeOn` attribute (21) is **never written**.
Both directions caused physical G350 lens movement in tests, but **do not
assume this on other camera models**.

The privacy sensors reflect the Matter-reported state. The switch is created
when the G350-like writable soft attributes are reported, but real write
support must still be verified on each camera. Software privacy may block
streams without physically covering a lens. If one of the two writes fails,
check the sensors; a partial change is possible.

If you block the camera's access to the internet, preserve LAN, IPv6 and
local Matter connectivity. Vendor cloud scenes might no longer function.
The Matter Server WebSocket and any HA credentials should stay on a trusted
network. **Never post fabric files, tokens, passwords, SDP or ICE candidate IPs.**

### Experimental WebRTC lifecycle diagnostic (not in v0.3.1)

Editing a Lovelace dashboard may call `setConfig()` again on an existing card
or remove and recreate the entire card. Both cases can terminate the native
WebRTC session. In v0.3.1 the bundled joystick card unnecessarily rebuilt
its nested live view on **every** repeated `setConfig` call.

On the `fix/webrtc-card-lifecycle` test branch, the outer card now
preserves its embedded `picture-entity` DOM when **the same instance is
temporarily detached and reattached**. It also preserves the player for repeated
`setConfig()` calls with unchanged video source. Pending helper loads and
privacy restart timers are handled separately; privacy-blocked video remains
blocked.

**Important limitation confirmed in upstream HA frontend:** its
`ha-web-rtc-player` always calls `_cleanUp()` on DOM disconnect and
`_startWebRtc()` on reconnect. Retaining the card DOM therefore prevents
**redundant outer-card reconstruction**, but cannot guarantee that the
native WebRTC media connection stays open during dashboard edit mode.
Preserving orphaned players outside the DOM would risk leaking video sessions,
so this PR does not attempt it. The actual ~5–7s handshake must be
investigated separately.

To identify what Home Assistant is doing during dashboard edits, opt in on
the **test branch only**:

```yaml
debug: true
```

Open the browser's developer console, enter/exit dashboard edit mode, and
look for `[Matter Camera PTZ #N]` messages:

- `setConfig: unchanged` or `update controls in place`: same card, old
  v0.3.1 implementation would have restarted video.
- `disconnected` → `connected (built=true)` with the **same # number**:
  the test card reused its DOM; HA's inner WebRTC player may still reconnect.
- `disconnected` followed by a new `connected` with **a new # number**:
  HA recreated the custom element. The video session will necessarily be
  negotiated again, independently of `setConfig` optimizations.
- `render: replacing embedded video player`: video is being rebuilt by the
  card itself.

INFO-level `Matter video timing:` backend messages already exist in
v0.3.1 and can further separate SDP/ICE preparation from first-frame latency.
Never share raw SDP, ICE IPs, tokens, or fabric data. Restore the published
v0.3.1 frontend module if a test branch misbehaves.

## Diagnostics and known limitations

- The supported path was tested on **one Aqara G350** with Matter.js Server
  API schema 14. Compatibility with other manufacturers and long-running
  multi-viewer sessions needs additional testing.
- After OpenWrt WAN isolation, G350 WebRTC picture startup is about 7 seconds;
  lowering card restart delay to 0 ms did not help. Tracked in
  [#3](https://github.com/Prezi87/ha-matter-camera-ptz/issues/3).
- INFO logs can time Matter WebRTC setup (without logging SDP/ICE addresses).
  Enable from HA **Developer Tools → Actions**:

```yaml
action: logger.set_level
data:
  custom_components.matter_camera_ptz.video: info
```

Then check `/config/home-assistant.log` for `Matter video timing:`.
Keep any shared logs redacted.

Report a compatibility issue with camera model, firmware, HA and Matter Server
versions, feature list and redacted logs: [GitHub Issues](https://github.com/Prezi87/ha-matter-camera-ptz/issues).

## Contributing

This is a community-maintained project. Bug reports and compatible-camera
test results are welcome. CI runs syntax, frontend regression tests,
HACS repository validation and Hassfest on pull requests.

MIT License. See [LICENSE](LICENSE).
