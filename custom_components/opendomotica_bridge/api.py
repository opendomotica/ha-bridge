"""API client for the OpenDomotica REST server.

Confirmed endpoint contract:
- GET  /api/v1/devices                                        -> list of devices (metadata only, no status)
- GET  /api/v1/devices/full                                   -> list of devices with all their attributes
  (used for polling: each device has an "attributes" dict keyed by attribute
  name, each entry shaped as {"value": ..., "readonly": ..., "historical": ...})
- GET  /api/v1/devices/{device_id}/attributes/{attribute}      -> current value of a single device attribute
  (attribute is one of: port_status, current_value, current_power, current_power_ac -
  see const.DEVICE_STATUS_ATTRIBUTE)
- POST /api/v1/devices/{device_id}/execute/turn_on             -> turn a device on
- POST /api/v1/devices/{device_id}/execute/turn_off            -> turn a device off
- POST /api/v1/devices/{device_id}/execute/toggle              -> toggle a device
- POST /api/v1/devices/{device_id}/execute/set_value           -> set a value (sent as the "value" query param)

Device list item shape (as returned by /devices; /devices/full adds "attributes"):
{
    "device_id": "178",
    "device_description": "Luce porta 128",
    "node_id": "2",
    "node_port": "128",
    "type": "10001",            # numeric device type code, see const.DEVICE_TYPE_MAP
    "group_id": "12",
    "gui_description": null,     # preferred display name when set
    "gui_icon": null,
    "update_timestamp": "1788109334",
    "event_timestamp": "1788109334"
}
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_KEY_HEADER

_LOGGER = logging.getLogger(__name__)

API_TIMEOUT = 10
API_BASE_PATH = "/api/v1"


class OpenDomoticaApiError(Exception):
    """Raised when communication with the domotica server fails."""


class OpenDomoticaApiClient:
    """Thin HTTP client for the OpenDomotica REST API."""

    def __init__(
        self,
        host: str,
        port: int | None,
        session: aiohttp.ClientSession,
        use_ssl: bool = False,
        api_key: str | None = None,
    ) -> None:
        self._session = session
        scheme = "https" if use_ssl else "http"
        netloc = f"{host}:{port}" if port else host
        self._base_url = f"{scheme}://{netloc}{API_BASE_PATH}"
        self._api_key = api_key

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the list of devices known by the domotica server (metadata only)."""
        return await self._request("GET", "/devices")

    async def async_get_devices_full(self) -> list[dict[str, Any]]:
        """Return all devices together with their full set of attributes (for polling)."""
        return await self._request("GET", "/devices/full")

    async def async_get_device_attribute(self, device_id: str, attribute: str) -> Any:
        """Return the current value of a device attribute (e.g. port_status, current_value)."""
        result = await self._request("GET", f"/devices/{device_id}/attributes/{attribute}")
        # Attribute values are always wrapped as {"value": ...}.
        if isinstance(result, dict):
            return result.get("value")
        return result

    async def async_turn_on(self, device_id: str) -> None:
        """Turn a device on."""
        await self._request("POST", f"/devices/{device_id}/execute/turn_on")

    async def async_turn_off(self, device_id: str) -> None:
        """Turn a device off."""
        await self._request("POST", f"/devices/{device_id}/execute/turn_off")

    async def async_toggle(self, device_id: str) -> None:
        """Toggle a device."""
        await self._request("POST", f"/devices/{device_id}/execute/toggle")

    async def async_set_value(self, device_id: str, value: Any) -> None:
        """Set a value on a device (e.g. brightness or position)."""
        await self._request(
            "POST", f"/devices/{device_id}/execute/set_value", params={"value": value}
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        if self._api_key:
            headers = {**kwargs.pop("headers", {}), API_KEY_HEADER: self._api_key}
            kwargs["headers"] = headers
        try:
            async with asyncio.timeout(API_TIMEOUT):
                response = await self._session.request(method, url, **kwargs)
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error calling %s %s: %s", method, url, err)
            raise OpenDomoticaApiError(f"Error communicating with {url}: {err}") from err
        except TimeoutError as err:
            _LOGGER.error("Timeout calling %s %s after %ss", method, url, API_TIMEOUT)
            raise OpenDomoticaApiError(f"Timeout communicating with {url}") from err
