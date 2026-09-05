"""Config flow for the OpenDomotica Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .api import OpenDomoticaApiClient, OpenDomoticaApiError
from .const import CONF_API_KEY, CONF_AREA_ID, CONF_WEBHOOK_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT): int,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_API_KEY): str,
        vol.Optional(CONF_AREA_ID): selector.AreaSelector(),
    }
)


class OpenDomoticaBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenDomotica Bridge."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step: ask for host/port and validate connectivity."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input.get(CONF_PORT)}
            )
            session = async_get_clientsession(self.hass)
            client = OpenDomoticaApiClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT),
                session=session,
                use_ssl=user_input[CONF_SSL],
                api_key=user_input.get(CONF_API_KEY),
            )
            try:
                await client.async_get_devices()
            except OpenDomoticaApiError as err:
                _LOGGER.error(
                    "Unable to connect to domotica server at %s: %s", user_input[CONF_HOST], err
                )
                errors["base"] = "cannot_connect"
            else:
                title = user_input[CONF_HOST]
                if user_input.get(CONF_PORT):
                    title = f"{title}:{user_input[CONF_PORT]}"
                data = {**user_input, CONF_WEBHOOK_ID: async_generate_id()}
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return OpenDomoticaBridgeOptionsFlow(config_entry)


class OpenDomoticaBridgeOptionsFlow(OptionsFlow):
    """Handle options (e.g. polling interval) for OpenDomotica Bridge."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        CONF_API_KEY,
                        default=self._config_entry.options.get(
                            CONF_API_KEY, self._config_entry.data.get(CONF_API_KEY, "")
                        ),
                    ): str,
                }
            ),
            description_placeholders={"webhook_url": self._webhook_url},
        )

    @property
    def _webhook_url(self) -> str:
        """Return the full webhook URL to display to the user, if one was generated."""
        webhook_id = self._config_entry.data.get(CONF_WEBHOOK_ID)
        if not webhook_id:
            return "non disponibile: rimuovi e ri-aggiungi l'integrazione per abilitarlo"
        try:
            base_url = get_url(self.hass, prefer_external=False)
        except NoURLAvailableError:
            base_url = ""
        return f"{base_url}/api/webhook/{webhook_id}"
