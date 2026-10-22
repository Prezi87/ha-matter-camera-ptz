"""UI configuration of Matter Camera PTZ."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .api import async_discover_cameras
from .const import (
    CONF_CAMERA_NAME,
    CONF_COOLDOWN,
    CONF_ENDPOINT_ID,
    CONF_NODE_ID,
    CONF_PAN_STEP,
    CONF_TILT_STEP,
    CONF_URL,
    CONF_ZOOM_STEP,
    DEFAULT_COOLDOWN,
    DEFAULT_PAN_STEP,
    DEFAULT_TILT_STEP,
    DEFAULT_URL,
    DEFAULT_ZOOM_STEP,
    DOMAIN,
)


class MatterCameraPTZConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Select a Matter server then a PTZ camera discovered there."""

    VERSION = 1

    def __init__(self):
        self._url: str | None = None
        self._cameras: dict[str, dict] = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if not (url.startswith("ws://") or url.startswith("wss://")):
                errors["base"] = "invalid_url"
            else:
                try:
                    cameras = await async_discover_cameras(self.hass, url)
                except HomeAssistantError:
                    errors["base"] = "cannot_connect"
                else:
                    if not cameras:
                        errors["base"] = "no_cameras"
                    else:
                        self._url = url
                        self._cameras = {
                            f"{camera['node_id']}:{camera['endpoint_id']}": camera
                            for camera in cameras
                        }
                        return await self.async_step_camera()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL, default=DEFAULT_URL): str}),
            errors=errors,
        )

    async def async_step_camera(self, user_input=None):
        if not self._cameras or self._url is None:
            return await self.async_step_user()
        if user_input is not None:
            camera = self._cameras[user_input["camera"]]
            await self.async_set_unique_id(
                f"{self._url}|{camera['node_id']}|{camera['endpoint_id']}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=camera["name"],
                data={
                    CONF_URL: self._url,
                    CONF_NODE_ID: camera["node_id"],
                    CONF_ENDPOINT_ID: camera["endpoint_id"],
                    CONF_CAMERA_NAME: camera["name"],
                },
            )

        choices = {
            key: (
                f"{camera['name']} — Node {camera['node_id']}, "
                f"Endpoint {camera['endpoint_id']}"
                + (" (offline)" if not camera["available"] else "")
            )
            for key, camera in self._cameras.items()
        }
        return self.async_show_form(
            step_id="camera", data_schema=vol.Schema({vol.Required("camera"): vol.In(choices)})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MatterCameraPTZOptionsFlow()


class MatterCameraPTZOptionsFlow(config_entries.OptionsFlow):
    """Configure the step lengths and minimum interval between movements."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_PAN_STEP, default=current.get(CONF_PAN_STEP, DEFAULT_PAN_STEP)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=180)),
                vol.Required(CONF_TILT_STEP, default=current.get(CONF_TILT_STEP, DEFAULT_TILT_STEP)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=40)),
                vol.Required(CONF_ZOOM_STEP, default=current.get(CONF_ZOOM_STEP, DEFAULT_ZOOM_STEP)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=81)),
                vol.Required(CONF_COOLDOWN, default=current.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)):
                    vol.All(vol.Coerce(float), vol.Range(min=0, max=15)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
