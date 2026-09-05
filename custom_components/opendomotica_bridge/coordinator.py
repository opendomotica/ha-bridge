"""DataUpdateCoordinator for the OpenDomotica Bridge integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenDomoticaApiClient, OpenDomoticaApiError
from .const import ATTR_PORT_STATUS, DEVICE_STATUS_ATTRIBUTE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OpenDomoticaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the domotica server for the list of devices and their status attribute."""

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
            devices = await self.client.async_get_devices()
            statuses = await asyncio.gather(
                *(
                    self.client.async_get_device_attribute(
                        device["device_id"],
                        DEVICE_STATUS_ATTRIBUTE.get(device.get("type"), ATTR_PORT_STATUS),
                    )
                    for device in devices
                ),
                return_exceptions=True,
            )
        except OpenDomoticaApiError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[str, dict[str, Any]] = {}
        for device, status in zip(devices, statuses):
            if isinstance(status, OpenDomoticaApiError):
                _LOGGER.debug(
                    "Unable to read status of device %s: %s", device["device_id"], status
                )
                status = None
            elif isinstance(status, BaseException):
                raise status
            result[device["device_id"]] = {**device, "status_value": status}
        return result
