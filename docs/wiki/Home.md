# Matter Camera PTZ — Wiki

Community integration for **Home Assistant**, providing local **Matter 1.5** camera live video (native WebRTC), PTZ and privacy controls. The reference hardware is **Aqara Camera Hub G350**.

> Documentation applies to **v0.3.1**. Support for other camera models is not yet verified. This project is not affiliated with Aqara, Home Assistant, or the Matter.js maintainers.

## Start here

- [[Installation]] — requirements, HACS installation and first pairing
- [[Lovelace-Card]] — integrated live video and circular PTZ joystick
- [[Privacy-and-PTZ]] — privacy behavior, movement settings and entity semantics
- [[Offline-G350-and-Networking]] — running G350 locally with WAN blocked
- [[Troubleshooting]] — diagnosing camera streams, ICE and entity issues
- [[FAQ]] — common questions and project scope

## What is supported

| Feature | Aqara G350 |
|---|---|
| Native camera entity with Matter WebRTC live view | Tested |
| Matter JPEG snapshot (1920×1080) | Tested |
| Pan / tilt / zoom (Matter cluster 1362) | Tested |
| Privacy switch and status sensors | Tested |
| Physical lens retracts on privacy ON | Observed on G350 only |
| Camera operation with WAN blocked | Tested; slower live start |

A functioning Matter Server (API schema **14+**) is required. Commission the camera with that server first; the integration does **not** perform pairing itself.

## Relevant links

- [Repository](https://github.com/Prezi87/ha-matter-camera-ptz)
- [Latest verified release (v0.3.1)](https://github.com/Prezi87/ha-matter-camera-ptz/releases/tag/v0.3.1)
- [Issues](https://github.com/Prezi87/ha-matter-camera-ptz/issues)
- [Source README](https://github.com/Prezi87/ha-matter-camera-ptz/blob/main/README.md)
