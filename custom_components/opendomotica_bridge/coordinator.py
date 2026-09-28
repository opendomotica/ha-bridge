"""DataUpdateCoordinator for the OpenDomotica Bridge integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenDomoticaApiClient, OpenDomoticaApiError
from .const import ATTR_PORT_STATUS, DEVICE_EXTRA_ATTRIBUTE, DEVICE_STATUS_ATTRIBUTE, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalize_port_status(device: dict[str, Any], value: Any) -> Any:
    """Invert binary port status for normally-closed devices."""
    wiring = device.get("wiring")
    if wiring is None:
        attributes = device.get("attributes")
        wiring_attribute = attributes.get("wiring") if isinstance(attributes, dict) else None
        wiring = wiring_attribute.get("value") if isinstance(wiring_attribute, dict) else wiring_attribute
    if not isinstance(wiring, str) or wiring.strip().lower() != "nc":
        return value

    if value in (0, "0"):
        return 1 if isinstance(value, int) else "1"
    if value in (1, "1"):
        return 0 if isinstance(value, int) else "0"
    return value


class OpenDomoticaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the OpenDomotica server for all devices and their attribute values."""

    def __init__(self, hass: HomeAssistant, client: OpenDomoticaApiClient, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.climate_zones: dict[str, dict[str, Any]] = {}
        self._consecutive_poll_failures = 0

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.async_get_devices_full()
        except OpenDomoticaApiError as err:
            self._consecutive_poll_failures += 1
            if self.data and self._consecutive_poll_failures == 1:
                _LOGGER.warning(
                    "Failed to poll devices from the OpenDomotica server; retaining cached data: %s",
                    err,
                )
                return self.data
            _LOGGER.exception(
                "Failed to poll devices from the OpenDomotica server %s consecutive times: %s",
                self._consecutive_poll_failures,
                err,
            )
            raise UpdateFailed(str(err)) from err

        self._consecutive_poll_failures = 0
        try:
            climate_zones = await self.client.async_get_climate_zones()
        except OpenDomoticaApiError as err:
            _LOGGER.warning("Failed to poll climate zones from the OpenDomotica server: %s", err)
        else:
            self.climate_zones = {
                str(zone["id"]): zone
                for zone in climate_zones
                if isinstance(zone, dict) and zone.get("id") is not None
            }

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
            status_value = attribute.get("value")
            if expected_attribute == ATTR_PORT_STATUS:
                status_value = _normalize_port_status(device, status_value)
            result[device["device_id"]] = {**device, "status_value": status_value}
        return result

    def async_handle_push_update(self, device_id: str, attribute: str, value: Any) -> None:
        """Apply a status update pushed by the OpenDomotica server via webhook."""
        if not self.data or device_id not in self.data:
            _LOGGER.warning("Ignoring push update for unknown device %s", device_id)
            return

        device = self.data[device_id]
        device_type = device.get("type")
        expected_attribute = DEVICE_STATUS_ATTRIBUTE.get(device_type, ATTR_PORT_STATUS)
        extra_attribute = DEVICE_EXTRA_ATTRIBUTE.get(device_type)

        if attribute == expected_attribute:
            if expected_attribute == ATTR_PORT_STATUS:
                value = _normalize_port_status(device, value)
            updated_device = {**device, "status_value": value}
        elif extra_attribute is not None and attribute == extra_attribute:
            attributes = device.get("attributes")
            attributes = dict(attributes) if isinstance(attributes, dict) else {}
            attributes[attribute] = {**attributes.get(attribute, {}), "value": value}
            updated_device = {**device, "attributes": attributes}
        else:
            _LOGGER.warning(
                "Ignoring push update for device %s: got attribute %s, expected %s",
                device_id,
                attribute,
                expected_attribute,
            )
            return

        new_data = {**self.data, device_id: updated_device}
        # Update data/listeners directly instead of via async_set_updated_data,
        # which would reset the periodic refresh timer on every push and could
        # starve the update_interval polling if pushes arrive frequently.
        self.data = new_data
        self._consecutive_poll_failures = 0
        self.last_update_success = True
        self.async_update_listeners()
