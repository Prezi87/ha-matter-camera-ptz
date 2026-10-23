/* Matter Camera PTZ Card -- WebRTC lifecycle diagnostics (v0.3.1 candidate) */
let cardInstanceNumber = 0;
const VIDEO_SOURCE_KEYS = ["native_camera_entity","rtsp_camera_entity","camera_entity","stream","muted","video_controls"];
const directions = {
  left:["mdi:arrow-left-bold","Pan left"], right:["mdi:arrow-right-bold","Pan right"],
  up:["mdi:arrow-up-bold","Tilt up"], down:["mdi:arrow-down-bold","Tilt down"],
  zoom_in:["mdi:magnify-plus-outline","Zoom in"],
  zoom_out:["mdi:magnify-minus-outline","Zoom out"]
};
const css = [
  ":host{display:block}ha-card{overflow:hidden}",
  ".head{display:flex;justify-content:space-between;align-items:center;padding:12px 16px 8px}",
  ".head strong{font-size:1rem}.head small{color:var(--secondary-text-color)}",
  ".video{background:#111c26;overflow:hidden;min-height:100px}",
  ".video>*{display:block;width:100%}",
  ".error{padding:18px;color:#fff}",
  ".controls{display:grid;grid-template-columns:repeat(4,var(--ptz-size));grid-auto-rows:var(--ptz-size);gap:var(--ptz-gap);justify-content:center;padding:14px 8px 6px}",
  "button{border:1px solid var(--divider-color);border-radius:50%;width:var(--ptz-size);height:var(--ptz-size);padding:0;background:var(--secondary-background-color);color:var(--primary-text-color);display:flex;align-items:center;justify-content:center;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent}",
  "button ha-icon{--mdc-icon-size:28px}",
  "button:active,button.pressed{background:var(--primary-color);color:white}",
  "button:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}",
  "button.on{color:var(--state-icon-active-color,var(--primary-color))}",
  "button.off{color:var(--secondary-text-color)}",
  "button:disabled{opacity:.32;cursor:default}",
  ".head-actions{display:flex;align-items:center;gap:10px}",
  ".head .video-reload{width:30px;height:30px;background:transparent;border:1px solid var(--divider-color)}",
  ".head .video-reload ha-icon{--mdc-icon-size:17px}",
  ".status{text-align:center;font-size:0.75rem;min-height:18px;color:var(--secondary-text-color);padding:0 10px 9px}",
  "@media(max-width:340px){button ha-icon{--mdc-icon-size:23px}}"
].join("");

class MatterCameraPTZCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._instanceNumber = ++cardInstanceNumber;
    this._pressed = new Map();
    this._timers = new Map();
    this._token = 0;
    this._videoRestartTimer = null;
    this._rtspUnmaskTimer = null;
    this._rtspUnmaskAt = 0;
    this._privacyMode = undefined;
    this._resumeOnReconnect = false;
  }

  // HA can call setConfig again while entering dashboard edit mode, even
  // when neither the camera source nor the configuration actually changed.
  // Avoid tearing down the active nested picture-entity/WebRTC player.
  setConfig(config) {
    if (!config.ptz_entity) throw new Error("Matter PTZ: ptz_entity is required");
    if (!config.stream && !config.camera_entity && !config.native_camera_entity && !config.rtsp_camera_entity)
      throw new Error("Matter PTZ: native_camera_entity, rtsp_camera_entity, stream or camera_entity is required");

    const old = this._config;
    const changed = !old || JSON.stringify(old) !== JSON.stringify(config);
    const videoChanged = !old || VIDEO_SOURCE_KEYS.some(key => old[key] !== config[key]);
    this._config = {...config};

    if (!this.isConnected) {
      this._debug("setConfig while disconnected");
      return;
    }
    if (!this._built || videoChanged) {
      this._debug("setConfig: rebuild needed (video source changed or not built)");
      this._render();
    } else if (changed) {
      this._debug("setConfig: update controls in place; preserve WebRTC player");
      this._updateDisplay();
      this._syncPrivacyVideo();
      this._refreshPrivacy();
    } else {
      this._debug("setConfig: unchanged; keeping WebRTC session");
    }
  }

  _debug(message) {
    if (this._config?.debug === true) {
      console.info("[Matter Camera PTZ #"+this._instanceNumber+"] "+
        (typeof performance !== "undefined" ? performance.now().toFixed(0)+"ms " : "")+
        message);
    }
  }

  _updateDisplay() {
    const card = this.shadowRoot.querySelector("ha-card");
    const title = this.shadowRoot.querySelector(".title");
    if (card) {
      card.style.setProperty("--ptz-size", this._value("button_size",62,44,82)+"px");
      card.style.setProperty("--ptz-gap", this._value("gap",8,4,18)+"px");
    }
    if (title) title.textContent = this._config.title||"Matter Camera PTZ";
  }
  set hass(hass) {
    this._hass = hass;
    this._syncPrivacyVideo();
    this._refreshPrivacy();
    // Tear down a privacy-blocked player before updating its HA state.
    if (this._player) this._player.hass = hass;
  }
  getCardSize() { return 7; }
  getGridOptions() { return {columns:12,min_columns:6,rows:8}; }
  static getStubConfig() { return {ptz_entity:"button.replace_with_ptz_entity",stream:"go2rtc_stream_name"}; }

  connectedCallback() {
    this._debug("connected (built="+Boolean(this._built)+")");
    if (!this._config) return;
    if (!this._built) {
      this._render();
      return;
    }
    // Home Assistant reconnects its own ha-web-rtc-player when the existing
    // DOM is reattached. Do not delete and recreate picture-entity here.
    this._debug("reconnected: preserved embedded player DOM");
    if (this._config.rtsp_camera_entity && this._rtspUnmaskAt > Date.now()) this._scheduleRtspUnmask();
    const wasBlocked = this._privacyMode === "off";
    this._syncPrivacyVideo();
    this._refreshPrivacy();
    if (this._resumeOnReconnect) {
      this._resumeOnReconnect = false;
      if (this._privacyMode !== "off" && !this._videoRestartTimer)
        this._restartNativeVideo();
    } else if (!wasBlocked && !this._player && !this._videoRestartTimer &&
               (this._config.native_camera_entity || this._config.rtsp_camera_entity) && this._privacyMode !== "off") {
      // Initial asynchronous load was interrupted before the player existed.
      this._debug("reconnected: retry interrupted embedded player load");
      this._restartNativeVideo();
    }
  }
  disconnectedCallback() {
    this._debug("disconnected (HA WebRTC player manages its own cleanup)");
    this._stopAll();
    if (this._rtspUnmaskTimer !== null) { clearTimeout(this._rtspUnmaskTimer); this._rtspUnmaskTimer = null; }
    if (this._videoRestartTimer !== null) {
      this._resumeOnReconnect = true;
      this._cancelVideoRestart();
    }
    // Invalidate outstanding card helper loads, but preserve the nested player,
    // privacy status and shadow DOM. HA's ha-web-rtc-player already executes
    // its own _cleanUp() on detach and reconnects when reattached.
    this._token++;
  }

  _stopAll() {
    for (const timer of this._timers.values()) clearInterval(timer);
    this._timers.clear();
    this._pressed.clear();
  }

  _render() {
    this._debug("render: replacing embedded video player");
    this._stopAll();
    this._cancelVideoRestart();
    this._privacyMode = undefined;
    this._lastReportedPrivacyState = undefined;
    this._resumeOnReconnect = false;
    this._clearRtspUnmask();
    const token=++this._token;
    const size=this._value("button_size",62,44,82);
    const gap=this._value("gap",8,4,18);
    this._player=null;
    this.shadowRoot.innerHTML="<style>"+css+"</style>"+
      '<ha-card style="--ptz-size:'+size+'px;--ptz-gap:'+gap+'px">'+
      '<div class="head"><strong class="title"></strong><div class="head-actions"><small>WebRTC</small><button class="video-reload" type="button" title="Ponów podgląd" aria-label="Ponów podgląd"><ha-icon icon="mdi:refresh"></ha-icon></button></div></div>'+
      '<div class="video"><div class="error">Loading WebRTC video...</div></div>'+
      '<div class="controls" role="group" aria-label="Camera pan tilt zoom"></div>'+
      '<div class="status" role="status" aria-live="polite"></div></ha-card>';
    this.shadowRoot.querySelector(".title").textContent=this._config.title||"Matter Camera PTZ";
    this.shadowRoot.querySelector(".video-reload").addEventListener("click",()=>this._manualReloadVideo());
    const grid=this.shadowRoot.querySelector(".controls");
    for (const dir of [null,"up",null,"zoom_in","left","privacy","right","zoom_out",null,"down",null,null]) {
      if (!dir) { grid.appendChild(document.createElement("span")); continue; }
      const btn=document.createElement("button");
      btn.type="button";
      btn.dataset.direction=dir;
      btn.setAttribute("aria-label",dir==="privacy"?"Toggle monitoring and privacy":directions[dir][1]);
      const icon=document.createElement("ha-icon");
      icon.setAttribute("icon",dir==="privacy"?"mdi:cctv":directions[dir][0]);
      btn.appendChild(icon);
      grid.appendChild(btn);
      if (dir==="privacy") {
        btn.addEventListener("click",()=>this._togglePrivacy());
        continue;
      }
      btn.addEventListener("pointerdown",e=>{
        if(e.button!==0)return;
        e.preventDefault();
        if (!this._pressed.has(btn)) this._begin(btn,dir);
        try{btn.setPointerCapture(e.pointerId);}catch(_){}
      });
      btn.addEventListener("pointerup",e=>{
        e.preventDefault();
        this._end(btn,dir);
        try{if(btn.hasPointerCapture(e.pointerId))btn.releasePointerCapture(e.pointerId);}catch(_){}
      });
      btn.addEventListener("pointercancel",()=>this._cancel(btn));
      btn.addEventListener("lostpointercapture",()=>this._cancel(btn));
      btn.addEventListener("contextmenu",e=>e.preventDefault());
      btn.addEventListener("keydown",e=>{
        if(e.repeat||(e.key!==" "&&e.key!=="Enter"))return;
        e.preventDefault();this._begin(btn,dir);
      });
      btn.addEventListener("keyup",e=>{
        if(e.key!==" "&&e.key!=="Enter")return;
        e.preventDefault();this._end(btn,dir);
      });
      btn.addEventListener("blur",()=>this._cancel(btn));
    }
    this._built=true;
    this._refreshPrivacy();
    if (!this._syncPrivacyVideo()) this._loadVideo(token);
  }

  // The HA camera preview does not automatically renegotiate WebRTC after
  // a privacy-mode disconnect. Tear down the child and create a NEW instance.
  // Only the optional HA helper is used here; it stores the *requested* mode.
  _cancelVideoRestart() {
    if (this._videoRestartTimer !== null) clearTimeout(this._videoRestartTimer);
    this._videoRestartTimer = null;
  }
  _videoPlaceholder(message) {
    const slot = this.shadowRoot.querySelector(".video");
    if (!slot) return;
    const note = document.createElement("div");
    note.className = "error";
    note.textContent = message;
    slot.replaceChildren(note);
  }
  _pauseNativeVideo(message) {
    this._cancelVideoRestart();
    this._token++; // Invalidate any pending asynchronous card creation.
    this._player = null; // Disconnect existing picture-entity / WebRTC session.
    this._videoPlaceholder(message);
  }
  _restartNativeVideo() {
    if (!this.isConnected || !this._built) return;
    if (this._privacyMode === "off") {
      this._pauseNativeVideo("Tryb prywatności — transmisja wyłączona");
      return;
    }
    this._cancelVideoRestart();
    this._token++;
    this._player = null;
    this._videoPlaceholder("Nawiązywanie nowej sesji WebRTC...");
    this._loadVideo(this._token);
  }
  _manualReloadVideo() {
    if (this._privacyMode === "off") {
      this._status("Najpierw wyłącz tryb prywatności");
      return;
    }
    this._restartNativeVideo();
  }
  _syncPrivacyVideo() {
    if (!this._built || !(this._config?.native_camera_entity || this._config?.rtsp_camera_entity)) return false;

    // Optional native switch takes precedence over the old input_boolean.
    // A switch ON means privacy engaged; old helper OFF meant monitoring off.
    const controlId = this._config.privacy_switch_entity || this._config.privacy_entity;
    const nativeControl = Boolean(this._config.privacy_switch_entity);
    const sensorId = this._config.privacy_status_entity;
    if (!controlId && !sensorId) return false;

    const control = controlId && this._hass?.states?.[controlId]?.state;
    const reported = sensorId && this._hass?.states?.[sensorId]?.state;
    const controlKnown = control === "on" || control === "off";
    const sensorKnown = reported === "on" || reported === "off";

    // Keep the last observed privacy ON through temporary sensor outages.
    // Never translate "unavailable" into "off".
    if (sensorKnown) this._lastReportedPrivacyState = reported;
    else if (!sensorId && nativeControl && controlKnown)
      this._lastReportedPrivacyState = control;

    const reportedState = sensorKnown ? reported : this._lastReportedPrivacyState;
    if (!controlKnown && !sensorKnown)
      return this._privacyMode === "off";

    const privacyRequested = nativeControl ? control === "on" : control === "off";
    const state = (privacyRequested || reportedState === "on") ? "off" : "on";
    if (this._privacyMode === state) {
      if (this._config.rtsp_camera_entity) this._applyRtspPrivacyMask();
      return true;
    }

    const previous = this._privacyMode;
    this._privacyMode = state;
    if (this._config.rtsp_camera_entity) {
      // Keep RTSP running beneath the mask while Generic Camera awaits fresh
      // frames. Hide old frames for a configurable post-privacy grace period.
      if (state === "off") {
        this._clearRtspUnmask();
      } else if (previous === "off") {
        const delay = this._value("rtsp_resume_mask_ms", 5500, 0, 30000);
        this._rtspUnmaskAt = Date.now() + delay;
        this._scheduleRtspUnmask();
      }
      this._applyRtspPrivacyMask();
      return true;
    }
    if (state === "off") {
      this._pauseNativeVideo("Tryb prywatności — podgląd wyłączony");
    } else if (previous === "off") {
      const delay = this._value("privacy_resume_delay_ms", 5000, 0, 30000);
      this._pauseNativeVideo("Włączanie kamery — ponowne łączenie...");
      this._videoRestartTimer = setTimeout(() => {
        this._videoRestartTimer = null;
        if (this.isConnected && this._built && this._privacyMode === "on")
          this._restartNativeVideo();
      }, delay);
    } else {
      this._restartNativeVideo();
    }
    return true;
  }

  _clearRtspUnmask() {
    if (this._rtspUnmaskTimer !== null) clearTimeout(this._rtspUnmaskTimer);
    this._rtspUnmaskTimer = null;
    this._rtspUnmaskAt = 0;
  }

  _scheduleRtspUnmask() {
    if (this._rtspUnmaskTimer !== null) clearTimeout(this._rtspUnmaskTimer);
    this._rtspUnmaskTimer = null;
    if (!this._rtspUnmaskAt || !this.isConnected) return;
    const wait = Math.max(0, this._rtspUnmaskAt - Date.now());
    this._rtspUnmaskTimer = setTimeout(() => {
      this._rtspUnmaskTimer = null;
      if (this._privacyMode === "on" && this.isConnected && Date.now() >= this._rtspUnmaskAt) {
        this._rtspUnmaskAt = 0;
        this._applyRtspPrivacyMask();
      }
    }, wait);
  }

  _applyRtspPrivacyMask() {
    if (!this._config?.rtsp_camera_entity) return;
    const slot = this.shadowRoot.querySelector(".video");
    if (!slot) return;
    slot.style.position = "relative";
    let overlay = slot.querySelector(".rtsp-privacy-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "rtsp-privacy-overlay";
      overlay.textContent = "Tryb prywatności — podgląd ukryty";
      overlay.setAttribute("role", "status");
      overlay.style.cssText = "position:absolute;inset:0;background:#111c26;color:#fff;z-index:10;display:flex;align-items:center;justify-content:center;text-align:center;padding:20px;box-sizing:border-box;";
      slot.appendChild(overlay);
    }
    // Overlay hides stale RTSP frames; browser may keep decoding beneath.
    const blocked = this._privacyMode === "off" || this._rtspUnmaskAt > Date.now();
    overlay.textContent = this._privacyMode === "off"
      ? "Tryb prywatności — podgląd ukryty"
      : blocked ? "Oczekiwanie na świeży obraz…" : "";
    overlay.style.display = blocked ? "flex" : "none";
    this._debug("RTSP privacy overlay: "+(blocked ? "shown" : "hidden"));
  }

  async _loadVideo(token) {
    const slot=this.shadowRoot.querySelector(".video");
    try {
      if(typeof window.loadCardHelpers!=="function") throw new Error("Lovelace card helpers unavailable");
      const helpers=await window.loadCardHelpers();
      if(token!==this._token||!slot?.isConnected)return;
      const config = (this._config.native_camera_entity || this._config.rtsp_camera_entity) ? {
        type:"picture-entity",
        entity:this._config.rtsp_camera_entity || this._config.native_camera_entity,
        camera_view:"live",
        show_name:false,
        show_state:false
      } : {
        type:"custom:webrtc-camera",
        muted:this._config.muted!==false,
        ui:Boolean(this._config.video_controls),
        digital_ptz:false,
        ...(this._config.stream ? {url:this._config.stream} : {entity:this._config.camera_entity})
      };
      const player=helpers.createCardElement(config);
      this._player=player;
      if(this._hass)player.hass=this._hass;
      slot.replaceChildren(player);
      this._applyRtspPrivacyMask();
      this._debug("embedded picture-entity created");
    } catch(err) {
      if(token!==this._token)return;
      const label=document.createElement("div");
      label.className="error";
      label.textContent="WebRTC unavailable: "+String(err?.message||err);
      slot.replaceChildren(label);
    }
  }

  _value(key,fallback,min,max) {
    const n=Number(this._config[key]);
    return Number.isFinite(n)&&this._config[key]!==undefined ?
      Math.max(min,Math.min(max,Math.round(n))) : fallback;
  }
  _begin(btn,dir) {
    if(this._pressed.has(btn))return;
    this._pressed.set(btn,performance.now());
    btn.classList.add("pressed");
    if(dir.startsWith("zoom_")) {
      const delta=this._value("zoom_delta",5,1,81);
      this._send(dir,delta);
      const ms=this._value("zoom_repeat_ms",3500,1500,15000);
      this._timers.set(btn,setInterval(()=>{
        if(this._pressed.has(btn))this._send(dir,delta);
      },ms));
    }
  }
  _end(btn,dir) {
    if(!this._pressed.has(btn))return;
    const duration=Math.max(.05,(performance.now()-this._pressed.get(btn))/1000);
    this._cancel(btn);
    if(dir.startsWith("zoom_"))return;
    const pan=dir==="left"||dir==="right";
    const speed=this._value(pan?"pan_per_second":"tilt_per_second",pan?30:12,1,180);
    const limit=this._value(pan?"pan_max":"tilt_max",pan?90:24,1,180);
    const delta=Math.min(limit,Math.max(pan?8:2,Math.round(duration*speed)));
    this._send(dir,delta);
  }
  _cancel(btn) {
    if(this._timers.has(btn))clearInterval(this._timers.get(btn));
    this._timers.delete(btn);
    this._pressed.delete(btn);
    btn.classList.remove("pressed");
  }
  async _send(direction,delta) {
    if(!this._hass)return;
    this._status(direction.replace("_"," ")+" · "+delta);
    try {
      await this._hass.callService("matter_camera_ptz","move",{
        entity_id:this._config.ptz_entity,direction,delta
      });
    } catch(err) {this._status("PTZ error: "+String(err?.message||err));}
  }
  async _togglePrivacy() {
    if (!this._hass) return;
    const nativeId = this._config?.privacy_switch_entity;
    const legacyId = this._config?.privacy_entity;
    if (!nativeId && !legacyId) return;
    const domain = nativeId ? "switch" : "input_boolean";
    const entity_id = nativeId || legacyId;
    try {
      await this._hass.callService(domain, "toggle", {entity_id});
    } catch(err) {
      this._status("Privacy error: "+String(err?.message||err));
    }
  }

  _refreshPrivacy() {
    const btn = this.shadowRoot.querySelector('[data-direction="privacy"]');
    if (!btn) return;
    const nativeId = this._config?.privacy_switch_entity;
    const id = nativeId || this._config?.privacy_entity;
    const state = id && this._hass?.states?.[id];
    const blocked = this._privacyMode === "off" ||
      (nativeId ? state?.state === "on" : state?.state === "off");
    btn.disabled = !state || (state.state !== "on" && state.state !== "off");
    btn.classList.toggle("on", !blocked);
    btn.classList.toggle("off", blocked);
    btn.querySelector("ha-icon").setAttribute("icon", blocked ? "mdi:eye-off" : "mdi:cctv");
    btn.title = !id ? "No privacy control configured" :
      !state ? "Privacy control entity not found" :
      blocked ? "Privacy active" : "Monitoring active";
  }

  _status(value) {
    const el=this.shadowRoot.querySelector(".status");
    if(el)el.textContent=value;
  }
}
if(!customElements.get("matter-camera-ptz-card"))customElements.define("matter-camera-ptz-card",MatterCameraPTZCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(x=>x.type==="matter-camera-ptz-card")){
  window.customCards.push({type:"matter-camera-ptz-card",name:"Matter Camera PTZ Card",description:"WebRTC camera video with joystick and privacy helper."});
}
