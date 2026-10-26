# Aqara G350 without internet

G350 has been tested locally with **OpenWrt blocking camera WAN access** while preserving local Matter connectivity. Native video, PTZ and Matter privacy continue to work.

## Important network requirements

- Permit camera ↔ Matter Server communication on LAN, including **local IPv6**.
- Preserve local discovery/multicast where required by your Matter setup.
- Do not expose Matter Server port **5580** on the internet.
- Use a persistent IP/DHCP lease for predictable firewall matching, and confirm the device MAC and IP on **your** network.
- Block only **camera → WAN**, rather than all traffic from camera.

## Observed limitation: first live frame

After leaving privacy mode, the first current video frame generally took approximately **5–7 seconds** with G350 WAN blocked. With WAN allowed it appeared almost immediately.

Tests included direct Matter Server Live View and Generic Camera RTSP, both exhibiting delayed **fresh video** after privacy wake with WAN blocked. An OpenWrt `REJECT` rule returned ICMP unreachable quickly, but G350 continued attempts to external STUN endpoints. Supplying `ice_servers: []` to the stream request did not help. These results **suggest** camera/firmware WAN-dependent startup behavior; the root cause was **not conclusively established**.

**The project accepts this delay for offline G350 operation**. See [issue #3](https://github.com/Prezi87/ha-matter-camera-ptz/issues/3).

## OpenWrt verification (illustrative)

Review actual rules before changing anything:

```sh
fw4 print | grep -C 3 'Block_Aqara_G350_Internet'
nft list chain inet fw4 reject_to_wan
nft list chain inet fw4 handle_reject
```

Standard fw4 reject handling normally uses TCP reset for TCP and `reject` for other protocols. Rule counters for a shared chain do **not** prove how many packets are specific to G350.

Never copy fixed device identifiers or IP addresses from someone else's setup. If you use `tcpdump`, treat captures as sensitive networking data.

## Design decision

The v0.3.1 integration stays with native Matter WebRTC. RTSP was evaluated but not adopted for this workflow because fresh frames after privacy OFF were similarly delayed.
