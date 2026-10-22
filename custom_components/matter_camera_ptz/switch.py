"""A capability-gated Matter camera software privacy switch.

Switch ON = privacy enabled, camera view blocked.
Switch OFF = privacy disabled; camera may resume streaming.

Only Matter AVSM writable soft attributes 19 and 20 are written.
G350 has been confirmed to physically retract/open its lens as a side effect.
Other cameras may only block recording/live view without moving a lens.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CAMERA_NAME, DOMAIN
from .privacy import MatterPrivacyCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Only offer switch when both soft privacy attributes are reported."""
    coordinator: MatterPrivacyCoordinator = hass.data[f"{DOMAIN}_privacy"][entry.entry_id]
    if coordinator.supports_soft_privacy:
        async_add_entities([MatterPrivacySwitch(coordinator, entry)])


class MatterPrivacySwitch(CoordinatorEntity[MatterPrivacyCoordinator], SwitchEntity):
    """Privacy ON means Matter reports at least one privacy mode active."""

    _attr_has_entity_name = True
    _attr_name = "Privacy mode"
    _attr_icon = "mdi:eye-off"

    def __init__(self, coordinator: MatterPrivacyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_privacy_mode_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.data[CONF_CAMERA_NAME],
            "manufacturer": "Matter",
            "model": "Camera PTZ",
        }

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.supports_soft_privacy

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        if not self.coordinator.supports_soft_privacy:
            return None
        # Include hard privacy, but NEVER write its read-only Matter attribute.
        return any(
            data.get(key) is True
            for key in (
                "hard_mode_on",
                "soft_livestream_mode_enabled",
                "soft_recording_mode_enabled",
            )
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable recording and livestream privacy via Matter."""
        await self.coordinator.async_set_soft_privacy(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable recording and livestream privacy via Matter."""
        await self.coordinator.async_set_soft_privacy(False)
