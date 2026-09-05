"""Webhook endpoint used to receive push status updates from the domotica server.

The domotica server should POST a JSON body to the webhook URL whenever a
device attribute changes:

{
    "device_id": "178",
    "attribute": {
        "port_status": "1"
    }
}

The update is only applied if the attribute name matches the attribute
normally polled for that device (see const.DEVICE_STATUS_ATTRIBUTE);
periodic polling keeps running as a fallback in case a push notification is
missed.

The webhook is secured only by its random webhook_id (a Home Assistant
convention); it does not require the api_key used for outgoing requests to
the domotica server, so the server can POST here without authenticating.
"""
from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.webhook import async_register, async_unregister
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def async_register_webhook(
    hass: HomeAssistant, webhook_id: str, coordinator: OpenDomoticaDataUpdateCoordinator
) -> None:
    """Register the webhook that receives push status updates."""

    async def _handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response | None:
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.warning("Ignoring webhook payload that is not valid JSON")
            return None

        device_id = payload.get("device_id")
        attribute_data = payload.get("attribute")
        if device_id is None or not isinstance(attribute_data, dict) or not attribute_data:
            _LOGGER.warning("Ignoring incomplete webhook payload: %s", payload)
            return None

        attribute, value = next(iter(attribute_data.items()))
        _LOGGER.debug("Received push update for device %s: %s=%s", device_id, attribute, value)
        coordinator.async_handle_push_update(str(device_id), attribute, value)
        return None

    async_register(
        hass, DOMAIN, "OpenDomotica Bridge", webhook_id, _handle_webhook, local_only=False
    )


def async_unregister_webhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Unregister the webhook."""
    async_unregister(hass, webhook_id)
