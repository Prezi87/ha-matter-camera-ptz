"""Read-only Matter camera AV Stream Management privacy flags."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CAMERA_NAME, DOMAIN
from .privacy import MatterPrivacyCoordinator, PRIVACY_NAMES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create one sensor per supported, reported privacy attribute."""
    coordinator: MatterPrivacyCoordinator = hass.data[f"{DOMAIN}_privacy"][entry.entry_id]
    if not coordinator.data:
        return
    async_add_entities([
        MatterPrivacyBinarySensor(coordinator, entry, key)
        for key in PRIVACY_NAMES
        if key in coordinator.data
    ])


class MatterPrivacyBinarySensor(
    CoordinatorEntity[MatterPrivacyCoordinator], BinarySensorEntity
):
    """ON means the reported Matter privacy attribute is active."""

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
        return super().available and self.coordinator.data is not None and self._key in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._key) if self.coordinator.data else None
