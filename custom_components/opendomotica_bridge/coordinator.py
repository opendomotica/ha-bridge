"""DataUpdateCoordinator for the OpenDomotica Bridge integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenDomoticaApiClient, OpenDomoticaApiError
from .const import ATTR_PORT_STATUS, DEVICE_STATUS_ATTRIBUTE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OpenDomoticaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the domotica server for all devices and their attribute values."""

    def __init__(self, hass: HomeAssistant, client: OpenDomoticaApiClient, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.async_get_devices_full()
        except OpenDomoticaApiError as err:
            _LOGGER.error("Failed to poll devices from the domotica server: %s", err)
            raise UpdateFailed(str(err)) from err

        result: dict[str, dict[str, Any]] = {}
        for device in devices:
            expected_attribute = DEVICE_STATUS_ATTRIBUTE.get(device.get("type"), ATTR_PORT_STATUS)
            # Some servers serialize an empty attributes map as [] instead of {}.
            attributes = device.get("attributes")
            if not isinstance(attributes, dict):
                attributes = {}
            attribute = attributes.get(expected_attribute)
            if not isinstance(attribute, dict):
                attribute = {}
            result[device["device_id"]] = {**device, "status_value": attribute.get("value")}
        return result

    def async_handle_push_update(self, device_id: str, attribute: str, value: Any) -> None:
        """Apply a status update pushed by the domotica server via webhook."""
        if not self.data or device_id not in self.data:
            _LOGGER.warning("Ignoring push update for unknown device %s", device_id)
            return

        device = self.data[device_id]
        expected_attribute = DEVICE_STATUS_ATTRIBUTE.get(device.get("type"), ATTR_PORT_STATUS)
        if attribute != expected_attribute:
            _LOGGER.warning(
                "Ignoring push update for device %s: got attribute %s, expected %s",
                device_id,
                attribute,
                expected_attribute,
            )
            return

        new_data = {**self.data, device_id: {**device, "status_value": value}}
        # Update data/listeners directly instead of via async_set_updated_data,
        # which would reset the periodic refresh timer on every push and could
        # starve the update_interval polling if pushes arrive frequently.
        self.data = new_data
        self.last_update_success = True
        self.async_update_listeners()
