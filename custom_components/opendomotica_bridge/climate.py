"""Climate platform for the OpenDomotica Bridge integration.

No type code in const.DEVICE_TYPE_MAP is currently mapped to CATEGORY_CLIMATE:
a thermostat needs current/target temperature and hvac mode attributes that
the confirmed API (a single status_value per device) does not expose.
Map a type code to CATEGORY_CLIMATE and adapt this file if your server
exposes those values through a different attribute/endpoint.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_CLIMATE, DEVICE_TYPE_MAP, DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .entity import OpenDomoticaBridgeEntity, parse_bool_status


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up thermostats, adding new ones as they are discovered by the coordinator."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaClimate(coordinator, device_id)
            for device_id, device in coordinator.data.items()
            if DEVICE_TYPE_MAP.get(device.get("type")) == CATEGORY_CLIMATE
            and device_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._device_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaClimate(OpenDomoticaBridgeEntity, ClimateEntity):
    """Representation of a thermostat exposed by the domotica server.

    Only on/off control is supported by the confirmed API: HVACMode.HEAT maps
    to turn_on, HVACMode.OFF maps to turn_off, and target_temperature (if
    used) is sent via set_value.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    @property
    def hvac_mode(self) -> HVACMode | None:
        is_on = parse_bool_status(self.device.get("status_value"))
        if is_on is None:
            return None
        return HVACMode.HEAT if is_on else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._async_execute("turn off", self.coordinator.client.async_turn_off(self._device_id))
        else:
            await self._async_execute("turn on", self.coordinator.client.async_turn_on(self._device_id))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._async_execute(
            "set temperature of",
            self.coordinator.client.async_set_value(self._device_id, temperature),
        )

