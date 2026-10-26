# PTZ and privacy

## PTZ action

The integration exposes a service/action:

```yaml
action: matter_camera_ptz.move
data:
  entity_id: button.YOUR_PAN_LEFT_BUTTON
  direction: left
  delta: 30
```

Directions: `left`, `right`, `up`, `down`, `zoom_in`, `zoom_out`. `delta` is an integer between **1 and 180**; actual device capabilities may impose narrower ranges.

The G350 has been observed to need around **3 seconds** between effective PTZ commands. The integration rate-limits commands; tune movement and cooldown based on device behavior. This is not continuous motor drive during a hold — the joystick calculates a delta and sends it upon release.

## Privacy

The native `Privacy mode` switch controls **soft recording** and **soft livestream privacy** (AV Stream Management cluster **1361**, attributes **19** and **20**). It **does not write** the read-only `HardPrivacyModeOn` attribute (**21**).

- **ON**: private; on the tested G350 the camera physically retracts its lens and blocks the live view.
- **OFF**: return to monitoring; the live view resumes through native Matter WebRTC.
- The card can observe `privacy_status_entity` to hide video while privacy is active.
- A partial write can occur if one of the two soft privacy writes fails. Verify the Matter-reported status sensors if behavior looks inconsistent.

**Do not assume physical shutter movement on other camera models.** Reported soft privacy capabilities do not by themselves guarantee a mechanical lens cover.

## Legacy vendor scenes

Where native writable privacy is unavailable, the repository includes an optional [legacy example](https://github.com/Prezi87/ha-matter-camera-ptz/blob/main/examples/legacy_vendor_scenes_card.yaml) using vendor-specific automations. This is **not necessary for G350** when the native Matter privacy switch works.
