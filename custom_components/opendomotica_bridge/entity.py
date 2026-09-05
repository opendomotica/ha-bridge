"""Base entity for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator


def parse_bool_status(value: Any) -> bool | None:
    """Best-effort conversion of a raw status_value (e.g. port_status) to a boolean."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "off")
    return bool(value)


class OpenDomoticaBridgeEntity(CoordinatorEntity[OpenDomoticaDataUpdateCoordinator]):
    """Base entity backed by a device exposed by the domotica server."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpenDomoticaDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._device_name,
            manufacturer="OpenDomotica",
            model=self.device.get("type"),
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return the raw device data from the coordinator."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def _device_name(self) -> str:
        """Prefer the user-editable gui_description, fall back to device_description."""
        return (
            self.device.get("gui_description")
            or self.device.get("device_description")
            or self._device_id
        )

    @property
    def available(self) -> bool:
        """Return True if the device is still reported by the coordinator."""
        return super().available and self._device_id in self.coordinator.data
