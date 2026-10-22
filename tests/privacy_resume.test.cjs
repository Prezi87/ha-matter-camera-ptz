"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const registry = new Map();
global.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = { querySelector: () => null };
  }
};
global.customElements = {
  get: (key) => registry.get(key),
  define: (key, cls) => registry.set(key, cls),
};
global.window = { customCards: [] };
const script = fs.readFileSync(
  path.join(__dirname, "../custom_components/matter_camera_ptz/frontend/matter-camera-ptz-card.js"),
  "utf8"
);
vm.runInThisContext(script, { filename: "matter-camera-ptz-card.js" });
const Card = registry.get("matter-camera-ptz-card");

test("privacy helper OFF pauses, ON recreates the video exactly once", async () => {
  const card = new Card();
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_entity: "input_boolean.g350_monitoring",
    privacy_resume_delay_ms: 0,
  };
  card._built = true;
  Object.defineProperty(card, "isConnected", { value: true });
  let paused = 0;
  let restarted = 0;
  card._refreshPrivacy = () => {};
  card._pauseNativeVideo = () => { paused++; };
  card._restartNativeVideo = () => { restarted++; };

  card.hass = { states: { "input_boolean.g350_monitoring": { state: "on" } } };
  assert.equal(restarted, 1);

  // Unrelated sensor refresh must not create another WebRTC stream.
  card.hass = {
    states: {
      "input_boolean.g350_monitoring": { state: "on" },
      "sensor.unrelated": { state: "22" }
    }
  };
  assert.equal(restarted, 1);

  card.hass = { states: { "input_boolean.g350_monitoring": { state: "off" } } };
  assert.equal(paused, 1);
  assert.equal(card._privacyMode, "off");

  card.hass = { states: { "input_boolean.g350_monitoring": { state: "on" } } };
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(restarted, 2);
  assert.equal(card._privacyMode, "on");
});

test("card does not depend on an Aqara-specific helper", () => {
  const card = new Card();
  card._built = true;
  card._config = { native_camera_entity: "camera.any_matter_camera" };
  assert.equal(card._syncPrivacyVideo(), false);
});


test("Matter privacy ON blocks video even if helper still requests monitoring", async () => {
  const card = new Card();
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_entity: "input_boolean.g350_monitoring",
    privacy_status_entity: "binary_sensor.g350_live_view_blocked",
    privacy_resume_delay_ms: 0,
  };
  card._built = true;
  Object.defineProperty(card, "isConnected", { value: true });
  let paused = 0, restarted = 0;
  card._refreshPrivacy = () => {};
  card._pauseNativeVideo = () => { paused++; };
  card._restartNativeVideo = () => { restarted++; };

  const ha = (helper, sensed) => ({
    states: {
      "input_boolean.g350_monitoring": { state: helper },
      "binary_sensor.g350_live_view_blocked": { state: sensed },
    }
  });

  card.hass = ha("on", "off");
  assert.equal(restarted, 1);
  card.hass = ha("on", "on");
  assert.equal(card._privacyMode, "off");
  assert.equal(paused, 1);

  card.hass = ha("on", "off");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(restarted, 2);
  assert.equal(card._privacyMode, "on");

  card.hass = ha("off", "off");
  assert.equal(card._privacyMode, "off");
  card.hass = ha("off", "off");
  assert.equal(restarted, 2, "no unintended restart while helper is OFF");
  card._cancelVideoRestart();
});

test("unknown Matter privacy is never treated as affirmative privacy-OFF", () => {
  const card = new Card();
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_status_entity: "binary_sensor.g350_live_view_blocked",
  };
  card._built = true;
  card._privacyMode = "off";
  card._hass = {
    states: {
      "binary_sensor.g350_live_view_blocked": { state: "unavailable" },
    },
  };
  assert.equal(card._syncPrivacyVideo(), true);
  assert.equal(card._privacyMode, "off");
});


test("last known privacy ON persists across Matter sensor outage until explicit OFF", async () => {
  const card = new Card();
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_entity: "input_boolean.g350_monitoring",
    privacy_status_entity: "binary_sensor.g350_live_view_blocked",
    privacy_resume_delay_ms: 0
  };
  card._built = true;
  Object.defineProperty(card, "isConnected", { value: true });
  let paused = 0, restarted = 0;
  card._refreshPrivacy = () => {};
  card._pauseNativeVideo = () => paused++;
  card._restartNativeVideo = () => restarted++;
  const state = (sensor) => ({
    states: {
      "input_boolean.g350_monitoring": {state: "on"},
      "binary_sensor.g350_live_view_blocked": {state: sensor}
    }
  });
  card.hass = state("off");
  assert.equal(restarted, 1);
  card.hass = state("on");
  assert.equal(paused, 1);
  card.hass = state("unavailable");
  assert.equal(restarted, 1);
  assert.equal(card._privacyMode, "off");
  card.hass = state("off");
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(restarted, 2);
  card._cancelVideoRestart();
});


test("native Matter privacy switch supersedes legacy Aqara helper", async () => {
  const card = new Card();
  const commands = [];
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_switch_entity: "switch.g350_privacy_mode",
    privacy_entity: "input_boolean.g350_monitoring",
    privacy_status_entity: "binary_sensor.g350_live_view_blocked",
    privacy_resume_delay_ms: 0
  };
  card._built = true;
  Object.defineProperty(card, "isConnected", {value:true});
  let paused = 0, restarted = 0;
  card._refreshPrivacy = () => {};
  card._pauseNativeVideo = () => paused++;
  card._restartNativeVideo = () => restarted++;
  const snapshot = (native,legacy,sensed) => ({
    states: {
      "switch.g350_privacy_mode": {state:native},
      "input_boolean.g350_monitoring": {state:legacy},
      "binary_sensor.g350_live_view_blocked": {state:sensed}
    },
    callService: async (domain, command, args) => commands.push([domain,command,args.entity_id])
  });
  // Even if the older helper is out of sync, the native switch is authoritative.
  card.hass = snapshot("off","off","off");
  assert.equal(card._privacyMode,"on");
  card.hass = snapshot("on","off","on");
  assert.equal(card._privacyMode,"off");
  await card._togglePrivacy();
  assert.deepEqual(commands,[["switch","toggle","switch.g350_privacy_mode"]]);
  card.hass = snapshot("off","off","off");
  await new Promise(resolve => setTimeout(resolve,20));
  assert.equal(card._privacyMode,"on");
  assert.equal(restarted,2);
  assert.equal(paused,2);
  card._cancelVideoRestart();
});

test("native Matter privacy works without any Aqara helper", async () => {
  const card = new Card();
  card._config = {
    native_camera_entity: "camera.g350_live",
    privacy_switch_entity: "switch.g350_privacy_mode",
    privacy_resume_delay_ms: 0
  };
  card._built = true;
  Object.defineProperty(card, "isConnected", {value:true});
  let pauses = 0, restarts = 0;
  card._refreshPrivacy = () => {};
  card._pauseNativeVideo = () => pauses++;
  card._restartNativeVideo = () => restarts++;
  const state = (value) => ({
    states: {"switch.g350_privacy_mode":{state:value}},
    callService: async()=>{}
  });
  card.hass = state("off");
  card.hass = state("on");
  assert.equal(pauses,1);
  card.hass = state("off");
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(restarts,2);
  card._cancelVideoRestart();
});
