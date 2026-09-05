"""The OpenDomotica Bridge integration."""
from __future__ import annotations

import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .api import OpenDomoticaApiClient
from .const import CONF_AREA_ID, CONF_WEBHOOK_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .webhook import async_register_webhook, async_unregister_webhook

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenDomotica Bridge from a config entry."""
    session = async_get_clientsession(hass)
    client = OpenDomoticaApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT),
        session=session,
        use_ssl=entry.data.get(CONF_SSL, False),
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = OpenDomoticaDataUpdateCoordinator(hass, client, scan_interval)

    # Name of the area (if any) suggested for every device created by this entry.
    area_id = entry.data.get(CONF_AREA_ID)
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    coordinator.suggested_area = area.name if area else None

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if webhook_id:
        async_register_webhook(hass, webhook_id, coordinator)
        entry.async_on_unload(lambda: async_unregister_webhook(hass, webhook_id))
        try:
            base_url = get_url(hass, prefer_external=False)
            webhook_url = f"{base_url}/api/webhook/{webhook_id}"
        except NoURLAvailableError:
            webhook_url = f"/api/webhook/{webhook_id}"
        _LOGGER.info(
            "OpenDomotica Bridge: configure the domotica server to POST status updates to %s",
            webhook_url,
        )
        # INFO logs are filtered out by Home Assistant's default log level, so
        # also surface the URL as a persistent notification in the UI.
        persistent_notification.async_create(
            hass,
            (
                "Configura il tuo server di domotica per inviare gli aggiornamenti di "
                f"stato (POST) a questo indirizzo:\n\n`{webhook_url}`"
            ),
            title="OpenDomotica Bridge: webhook per gli aggiornamenti push",
            notification_id=f"{DOMAIN}_webhook_{entry.entry_id}",
        )
        entry.async_on_unload(
            lambda: persistent_notification.async_dismiss(
                hass, f"{DOMAIN}_webhook_{entry.entry_id}"
            )
        )
    else:
        _LOGGER.warning(
            "OpenDomotica Bridge: no webhook id on this config entry, push updates are "
            "disabled (remove and re-add the integration to enable them)"
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
