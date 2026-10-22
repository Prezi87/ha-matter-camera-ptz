"""Shared, read-only Matter camera privacy state and guarded software writes."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_matter_request
from .const import CONF_ENDPOINT_ID, CONF_NODE_ID, CONF_URL

_LOGGER = logging.getLogger(__name__)
AVSM_CLUSTER = 1361
SOFT_RECORDING_ATTRIBUTE = 19
SOFT_LIVESTREAM_ATTRIBUTE = 20

# The Matter HardwarePrivacyModeOn attribute is read-only (ID 21).
# It is NEVER written. G350 physically retracts the lens when both writable
# soft attributes are enabled, as verified with firmware in user's setup.
PRIVACY_NAMES = {
    "hard_mode_on": ("Hardware privacy", "mdi:shield-lock"),
    "soft_livestream_mode_enabled": ("Livestream privacy", "mdi:video-off"),
    "soft_recording_mode_enabled": ("Recording privacy", "mdi:record-circle-outline"),
    "live_view_blocked": ("Live view blocked", "mdi:eye-off"),
}
SOFT_FIELDS = (
    ("soft_recording_mode_enabled", SOFT_RECORDING_ATTRIBUTE),
    ("soft_livestream_mode_enabled", SOFT_LIVESTREAM_ATTRIBUTE),
)


class MatterPrivacyCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Poll subscription-backed AVSM privacy, shared between sensors and switch."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Matter privacy {entry.entry_id}",
            update_interval=timedelta(seconds=5),
        )
        self._entry = entry
        self._write_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, bool]:
        try:
            response = await async_matter_request(
                self.hass,
                self._entry.data[CONF_URL],
                "camera_get_capabilities",
                {
                    "node_id": self._entry.data[CONF_NODE_ID],
                    "endpoint_id": self._entry.data[CONF_ENDPOINT_ID],
                },
            )
        except HomeAssistantError as exc:
            raise UpdateFailed(f"Cannot read Matter privacy: {exc}") from exc

        if not isinstance(response, dict) or not isinstance(response.get("privacy"), dict):
            raise UpdateFailed("Matter Server omitted privacy capability data")

        flags = {
            key: value
            for key, value in response["privacy"].items()
            if key in PRIVACY_NAMES and key != "live_view_blocked"
            and isinstance(value, bool)
        }
        # Never infer OFF if one of the relevant flags is absent.
        hard = flags.get("hard_mode_on")
        livestream = flags.get("soft_livestream_mode_enabled")
        if hard is True or livestream is True:
            flags["live_view_blocked"] = True
        elif hard is False and livestream is False:
            flags["live_view_blocked"] = False
        return flags

    @property
    def supports_soft_privacy(self) -> bool:
        """Only create a writable switch when both optional attributes exist."""
        return bool(
            self.data is not None
            and all(isinstance(self.data.get(key), bool) for key, _ in SOFT_FIELDS)
        )

    async def async_set_soft_privacy(self, enabled: bool) -> None:
        """Write both AVSM soft flags. Physical privacy stays read-only.

        The camera decides whether changing software privacy moves its shutter.
        Writes to both attributes are separate Matter operations, so a partial
        failure is possible and is reported to Home Assistant.
        """
        if self._write_lock.locked():
            raise HomeAssistantError("Camera privacy operation already in progress")

        async with self._write_lock:
            if not self.last_update_success or not self.supports_soft_privacy:
                raise HomeAssistantError("Matter camera privacy state unavailable or not writable")

            for field, attr in SOFT_FIELDS:
                path = f"{self._entry.data[CONF_ENDPOINT_ID]}/{AVSM_CLUSTER}/{attr}"
                try:
                    result = await async_matter_request(
                        self.hass,
                        self._entry.data[CONF_URL],
                        "write_attribute",
                        {
                            "node_id": self._entry.data[CONF_NODE_ID],
                            "attribute_path": path,
                            "value": enabled,
                        },
                    )
                    if not (
                        isinstance(result, list)
                        and len(result) == 1
                        and isinstance(result[0], dict)
                        and result[0].get("Status") == 0
                    ):
                        raise HomeAssistantError(f"Matter rejected writing {field}: {result}")
                except HomeAssistantError:
                    await self.async_request_refresh()
                    raise HomeAssistantError(
                        f"Could not finish updating {field}. "
                        "Privacy may be partially changed; inspect the reported sensors."
                    ) from None

            # UI reflects actual Matter readback, not an optimistic assumed state.
            await self.async_request_refresh()
