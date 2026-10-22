/* Matter Camera PTZ Card -- experimental v0.3.0-beta.2 */
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
    this._pressed = new Map();
    this._timers = new Map();
    this._token = 0;
    this._videoRestartTimer = null;
    this._privacyMode = undefined;
  }

  setConfig(config) {
    if (!config.ptz_entity) throw new Error("Matter PTZ: ptz_entity is required");
    if (!config.stream && !config.camera_entity && !config.native_camera_entity) throw new Error("Matter PTZ: native_camera_entity, stream or camera_entity is required");
    this._config = {...config};
    if (this.isConnected) this._render();
  }
  set hass(hass) {
    this._hass = hass;
    this._refreshPrivacy();
    this._syncPrivacyVideo();
    // Tear down a privacy-blocked player before updating its HA state.
    if (this._player) this._player.hass = hass;
  }
  getCardSize() { return 7; }
  getGridOptions() { return {columns:12,min_columns:6,rows:8}; }
  static getStubConfig() { return {ptz_entity:"button.replace_with_ptz_entity",stream:"go2rtc_stream_name"}; }

  connectedCallback() { if (this._config && !this._built) this._render(); }
  disconnectedCallback() {
    this._stopAll();
    this._cancelVideoRestart();
    this._token++;
    this._player = null;
    this._privacyMode = undefined;
    this._built = false;
  }

  _stopAll() {
    for (const timer of this._timers.values()) clearInterval(timer);
    this._timers.clear();
    this._pressed.clear();
  }

  _render() {
    this._stopAll();
    this._cancelVideoRestart();
    this._privacyMode = undefined;
    this._lastReportedPrivacyState = undefined;
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
    if (!this._built || !this._config?.native_camera_entity) return false;

    // The HA helper contains the requested action; the optional Matter sensor
    // reports the actual AVSM privacy state. Neither is manufacturer-specific.
    const helperId = this._config.privacy_entity;
    const sensorId = this._config.privacy_status_entity;
    if (!helperId && !sensorId) return false;
    const helper = helperId && this._hass?.states?.[helperId]?.state;
    const reported = sensorId && this._hass?.states?.[sensorId]?.state;

    // A previously observed privacy-ON must never become OFF merely because
    // a sensor lost availability. Require an explicit "off" report to clear it.
    const helperKnown = helper === "on" || helper === "off";
    const sensorKnown = reported === "on" || reported === "off";
    if (sensorKnown) this._lastReportedPrivacyState = reported;
    const effectiveReport = sensorKnown ? reported : this._lastReportedPrivacyState;
    if (!helperKnown && !sensorKnown) return this._privacyMode === "off";

    // OFF helper = user requested privacy; ON Matter sensor = camera reports
    // privacy engaged. Either should suppress the video player immediately.
    const state = (helper === "off" || effectiveReport === "on") ? "off" : "on";
    if (this._privacyMode === state) return true;
    const previous = this._privacyMode;
    this._privacyMode = state;
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

  async _loadVideo(token) {
    const slot=this.shadowRoot.querySelector(".video");
    try {
      if(typeof window.loadCardHelpers!=="function") throw new Error("Lovelace card helpers unavailable");
      const helpers=await window.loadCardHelpers();
      if(token!==this._token||!slot?.isConnected)return;
      const config = this._config.native_camera_entity ? {
        type:"picture-entity",
        entity:this._config.native_camera_entity,
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
    if(!this._config.privacy_entity||!this._hass)return;
    try {await this._hass.callService("input_boolean","toggle",{entity_id:this._config.privacy_entity});}
    catch(err){this._status("Privacy error: "+String(err?.message||err));}
  }
  _refreshPrivacy() {
    const btn=this.shadowRoot.querySelector('[data-direction="privacy"]');
    if(!btn)return;
    const id=this._config?.privacy_entity;
    const state=id&&this._hass?.states?.[id];
    const sensedId=this._config?.privacy_status_entity;
    const sensed=sensedId&&this._hass?.states?.[sensedId]?.state;
    const modeOff=state?.state==="off"||sensed==="on";
    // The button triggers only the user's HA helper; Matter reporting is
    // strictly read-only (particularly for physical privacy switches).
    btn.disabled=!(state && state.state!=="unavailable" && state.state!=="unknown");
    btn.classList.toggle("on",!modeOff);
    btn.classList.toggle("off",modeOff);
    btn.querySelector("ha-icon").setAttribute("icon",modeOff?"mdi:eye-off":"mdi:cctv");
    btn.title=sensed==="on"?"Matter reports privacy active":
      !id?"No privacy control configured (Matter state is read-only)":
      !state?"Helper not found":modeOff?"Privacy on":"Monitoring on";
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
