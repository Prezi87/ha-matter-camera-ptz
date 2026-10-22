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
