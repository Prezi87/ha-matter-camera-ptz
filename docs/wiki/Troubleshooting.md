# Troubleshooting

## Custom element doesn't exist: matter-camera-ptz-card

Confirm that the HACS installation includes `custom_components/matter_camera_ptz/frontend/matter-camera-ptz-card.js`. Register **one** Dashboard Resource:

```text
/matter_camera_ptz/matter-camera-ptz-card.js?v=0.3.1
```

Resource type: **JavaScript module**. Reopen or hard-refresh the browser. Avoid duplicate resources for different versions.

## Integration exists but no camera entity

Confirm Matter Server API schema **14+**, device capabilities `Video` and `Snapshot` as applicable, and that you selected the correct camera **endpoint**. The supported Aqara G350 camera is on an endpoint distinct from its aggregator. The server must have already commissioned the node.

Check Home Assistant integration logs and Matter Server logs with tokens, fabric identifiers and addresses redacted.

## Stream errors or `addIceCandidate` InvalidStateError

Update to v0.3.1, which includes the candidate-order mitigation (SDP answer before camera ICE plus a short grace interval). This was observed to remove the error in G350 testing, but is not a universal fix for every HA browser/version.

Check local IPv6 reachability and Matter Server WebSocket availability. Native WebRTC may reconnect if HA temporarily detaches the inner player when entering dashboard edit mode.

## Live view takes ~5–7 seconds with WAN blocked

Known G350 behavior: the firewall itself was responding in microseconds, yet the camera continued external STUN probes. Similar delays were seen with direct Matter Server Live View and fresh RTSP after privacy wake. See [[Offline-G350-and-Networking]]. No reliable speed workaround is included.

## PTZ commands do not work

Confirm the entity is one of the Matter Camera PTZ buttons, and avoid repeating commands more rapidly than the G350 can process (about 3 seconds in observed tests). Validate with HA's `matter_camera_ptz.move` action.

## Diagnostics

Enable timing logs via **Developer Tools → Actions**:

```yaml
action: logger.set_level
data:
  custom_components.matter_camera_ptz.video: info
```

Then inspect `/config/home-assistant.log` for `Matter video timing:` lines (WebSocket ready, SDP answer, ICE candidate and start_stream completion). Do not share SDP or raw ICE/network identifiers.

## Reporting a bug

[Open an issue](https://github.com/Prezi87/ha-matter-camera-ptz/issues) with HA version, Matter Server version/API schema, camera model/firmware, expected vs actual behavior and **redacted** logs. Never share credentials, Matter fabric files or tokens.
