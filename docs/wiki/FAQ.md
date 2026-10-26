# FAQ

**Does this integration commission or pair the camera?**

No. Pair the camera to Matter Server first. This integration consumes the Matter Server API.

**Do I need RTSP, go2rtc or the Aqara cloud?**

No for the tested native Matter WebRTC path. Aqara G350 also exposes RTSP, but that fallback was not adopted into v0.3.1.

**Can I keep my G350 offline?**

Yes, tested with an OpenWrt WAN block while retaining LAN/IPv6 communication. Expect approximately 5–7 seconds until the first fresh frame after leaving privacy mode. See [[Offline-G350-and-Networking]].

**Does Privacy ON actually retract the G350 lens?**

It did on the tested G350. The integration writes soft privacy attributes; mechanical action is device-specific.

**Why does WebRTC reconnect when I edit a dashboard?**

HA may detach/recreate the inner video player. v0.3.1 prevents unnecessary rebuilding of the outer card where possible, but HA's own WebRTC component still handles session cleanup on detach.

**Does the joystick move continuously on hold?**

Pan/tilt translate hold duration into a delta and send a movement on release, rather than continuously sending motor commands. Zoom may repeat.

**Is the integration officially supported by Home Assistant or listed in HACS?**

It is a community integration distributed through a **custom HACS repository**. It is not currently presented as accepted into HACS's default catalog.

**Are other Matter cameras guaranteed to work?**

No. The physical tests were performed on Aqara G350 only; other devices expose different sets of capabilities. Generic compatibility remains a development goal.

**Where are releases and source code?**

[Releases](https://github.com/Prezi87/ha-matter-camera-ptz/releases) · [Repository](https://github.com/Prezi87/ha-matter-camera-ptz) · [Issues](https://github.com/Prezi87/ha-matter-camera-ptz/issues)
