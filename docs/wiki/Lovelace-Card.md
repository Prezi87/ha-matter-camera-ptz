# Live View + PTZ Lovelace card

The integration exposes a standard HA `camera` entity. Native live view is possible without a custom card:

```yaml
type: picture-entity
entity: camera.YOUR_CAMERA_LIVE
camera_view: live
show_name: false
show_state: false
```

## Register the bundled card

Under **Settings → Dashboards → Resources**, add/edit **one** JavaScript module:

```text
/matter_camera_ptz/matter-camera-ptz-card.js?v=0.3.1
```

Refresh or reopen your browser. Then add a **Manual** card:

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

Replace all placeholders with your **actual HA entity IDs**. The PTZ entity can be any one of the six PTZ buttons provided by the integration; the card calls the `matter_camera_ptz.move` action. Privacy fields are optional if the camera lacks those capabilities.

## How controls behave

- Pan and tilt: press duration controls the relative movement; a command is sent on release.
- Zoom: starts on press and can repeat while held; configure repeat interval.
- Privacy switch: **ON = private**; on G350 it was verified to retract the lens.
- For G350, `privacy_resume_delay_ms: 1000` has been tested.
- HA's embedded WebRTC player may still renegotiate when switching dashboard edit mode. The card preserves its DOM on a temporary detach, but cannot prevent native player cleanup.

See [[Privacy-and-PTZ]] and [[Troubleshooting]].

The published v0.3.1 uses **native Matter WebRTC** by default. RTSP is **not** required and the experimental RTSP privacy overlay was not merged.
