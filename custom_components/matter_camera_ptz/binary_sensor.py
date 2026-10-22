"""Read-only Matter camera privacy flags.

The Matter.js camera_get_capabilities response uses a subscription-backed view.
It can lag briefly behind a physical hardware privacy switch.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import async_matter_request
from .const import CONF_CAMERA_NAME, CONF_ENDPOINT_ID, CONF_NODE_ID, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Do not guess the state of absent optional Matter attributes.
PRIVACY_NAMES = {
    "hard_mode_on": ("Hardware privacy", "mdi:shield-lock"),
    "soft_livestream_mode_enabled": ("Livestream privacy", "mdi:video-off"),
    "soft_recording_mode_enabled": ("Recording privacy", "mdi:record-circle-outline"),
    "live_view_blocked": ("Live view blocked", "mdi:eye-off"),
}


class MatterPrivacyCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Poll the Matter Server's cached subscribed AVSM privacy attributes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Matter privacy {entry.entry_id}",
            update_interval=timedelta(seconds=5),
        )
        self._entry = entry

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
            raise UpdateFailed(f"Cannot read Matter camera privacy: {exc}") from exc
        if not isinstance(response, dict) or not isinstance(
            response.get("privacy"), dict
        ):
            raise UpdateFailed("Matter Server omitted privacy capabilities")
        flags: dict[str, bool] = {
            key: value
            for key, value in response["privacy"].items()
            if key in PRIVACY_NAMES and key != "live_view_blocked"
            and isinstance(value, bool)
        }
        if (
            "hard_mode_on" in flags
            or "soft_livestream_mode_enabled" in flags
        ):
            flags["live_view_blocked"] = (
                flags.get("hard_mode_on", False)
                or flags.get("soft_livestream_mode_enabled", False)
            )
        return flags


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create sensors only for privacy attributes this camera exposes."""
    coordinator = MatterPrivacyCoordinator(hass, entry)
    # Failure to query optional diagnostics must not disable PTZ or native video.
    await coordinator.async_refresh()
    if not coordinator.data:
        _LOGGER.info(
            "No Matter privacy state currently available for node %s, endpoint %s",
            entry.data[CONF_NODE_ID],
            entry.data[CONF_ENDPOINT_ID],
        )
        return
    async_add_entities(
        [
            MatterPrivacyBinarySensor(coordinator, entry, key)
            for key in PRIVACY_NAMES
            if key in coordinator.data
        ]
    )


class MatterPrivacyBinarySensor(
    CoordinatorEntity[MatterPrivacyCoordinator], BinarySensorEntity
):
    """Read-only privacy state as last reported through Matter."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MatterPrivacyCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name, self._attr_icon = PRIVACY_NAMES[key]
        self._attr_unique_id = f"{entry.unique_id}_privacy_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.data[CONF_CAMERA_NAME],
            "manufacturer": "Matter",
            "model": "Camera PTZ",
        }

    @property
    def available(self) -> bool:
        """Unavailable is not the same as privacy OFF."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._key in self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """ON means the named privacy mode is active."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)
