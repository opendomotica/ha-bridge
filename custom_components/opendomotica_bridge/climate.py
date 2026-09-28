"""Climate zones for the OpenDomotica Bridge integration."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenDomoticaApiError
from .const import DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TARGET_TEMPERATURE = 20.0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up climate zones, adding new ones as they are discovered."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaClimate(coordinator, zone_id)
            for zone_id in coordinator.climate_zones
            if zone_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._zone_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaClimate(CoordinatorEntity[OpenDomoticaDataUpdateCoordinator], ClimateEntity):
    """Representation of a server-managed heating zone."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_has_entity_name = True

    def __init__(self, coordinator: OpenDomoticaDataUpdateCoordinator, zone_id: str) -> None:
        super().__init__(coordinator)
        self._zone_id = str(zone_id)
        self._attr_unique_id = f"{DOMAIN}_climate_zone_{self._zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"climate_zone_{self._zone_id}")},
            name=self.zone.get("description") or f"Climate zone {self._zone_id}",
            manufacturer="OpenDomotica",
            model="Climate zone",
        )

    @property
    def zone(self) -> dict[str, Any]:
        """Return the latest zone data from the coordinator."""
        return self.coordinator.climate_zones.get(self._zone_id, {})

    @property
    def available(self) -> bool:
        """Return whether this climate zone is still reported by the server."""
        return super().available and self._zone_id in self.coordinator.climate_zones

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self.zone.get("mode")
        if mode == "auto":
            return HVACMode.AUTO
        if mode in ("manual", "timer"):
            return HVACMode.HEAT
        if mode in ("off", "disabled"):
            return HVACMode.OFF
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Report whether the zone's valve is currently heating."""
        mode = self.hvac_mode
        if mode is None:
            return None
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        heating = self.zone.get("heating")
        for association in self.zone.get("devices", []):
            if str(association.get("type")) != "1":
                continue
            device = self.coordinator.data.get(str(association.get("device_id")))
            status = device.get("status_value") if device else None
            if isinstance(status, str):
                normalized = status.strip().lower()
                if normalized in ("open", "opening"):
                    heating = True
                elif normalized in ("close", "closing"):
                    heating = False
                elif normalized in ("1", "true", "on"):
                    heating = True
                elif normalized in ("", "0", "false", "off"):
                    heating = False
            elif isinstance(status, (bool, int, float)):
                heating = bool(status)
            if heating is not None:
                break
        return HVACAction.HEATING if heating is True else HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature reported by the zone sensor."""
        for association in self.zone.get("devices", []):
            if str(association.get("type")) != "0":
                continue
            device = self.coordinator.data.get(str(association.get("device_id")))
            if device and device.get("status_value") is not None:
                return self._temperature_value(device["status_value"])
        return self._temperature_value(self.zone.get("temperature"))

    @property
    def target_temperature(self) -> float | None:
        """Return the active threshold or an editable value when heating is off."""
        attributes = self.zone.get("attributes")
        value = self._temperature_value(
            attributes.get("heating_threshold") if isinstance(attributes, dict) else None
        )
        if value is not None and value > 0:
            return value

        current_temperature = self.current_temperature
        fallback = (
            current_temperature if current_temperature is not None else _DEFAULT_TARGET_TEMPERATURE
        )
        return min(max(fallback, self.min_temp), self.max_temp)

    @staticmethod
    def _temperature_value(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            temperature = float(value)
        except (TypeError, ValueError):
            return None
        return temperature if math.isfinite(temperature) else None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = {
            HVACMode.OFF: "off",
            HVACMode.HEAT: "manual",
            HVACMode.AUTO: "auto",
        }.get(hvac_mode)
        if mode is not None:
            await self._async_update_zone({"mode": mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._async_update_zone(
            {"mode": "manual", "attributes": {"heating_threshold": temperature}}
        )

    async def _async_update_zone(self, data: dict[str, Any]) -> None:
        """Apply a mode or target-temperature change to the OpenDomotica server."""
        try:
            await self.coordinator.client.async_update_climate_zone(self._zone_id, data)
            await self.coordinator.async_request_refresh()
        except OpenDomoticaApiError as err:
            _LOGGER.error("Failed to update climate zone %s: %s", self._zone_id, err)
            raise HomeAssistantError(
                f"Failed to update climate zone {self._zone_id}: {err}"
            ) from err

