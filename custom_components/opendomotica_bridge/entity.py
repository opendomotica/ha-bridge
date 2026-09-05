"""Base entity for the OpenDomotica Bridge integration."""
from __future__ import annotations

import logging
from typing import Any, Coroutine

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenDomoticaApiError
from .const import DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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
    return None


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
            suggested_area=self._suggested_area,
        )

    @property
    def _suggested_area(self) -> str | None:
        """Prefer the device's own group description, fall back to the configured area."""
        group = self.device.get("group")
        if isinstance(group, dict) and group.get("description"):
            return group["description"]
        return getattr(self.coordinator, "suggested_area", None)

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

    async def _async_execute(self, action: str, command: Coroutine[Any, Any, None]) -> None:
        """Run a client command, logging and surfacing failures.

        State is not refreshed here: it is updated by the next push
        notification or periodic poll, not by this call.
        """
        try:
            await command
        except OpenDomoticaApiError as err:
            _LOGGER.error("Failed to %s device %s: %s", action, self._device_id, err)
            raise HomeAssistantError(
                f"Failed to {action} device {self._device_id}: {err}"
            ) from err
