"""Valve platform for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_VALVE, DEVICE_TYPE_MAP, DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .entity import OpenDomoticaBridgeEntity, parse_bool_status


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up valves, adding new ones as they are discovered by the coordinator."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaValve(coordinator, device_id)
            for device_id, device in coordinator.data.items()
            if DEVICE_TYPE_MAP.get(device.get("type")) == CATEGORY_VALVE
            and device_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._device_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaValve(OpenDomoticaBridgeEntity, ValveEntity):
    """Representation of an electrically controlled valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    @property
    def is_closed(self) -> bool | None:
        """Return whether the valve is closed."""
        status = self._valve_status
        if status in ("close", "closing"):
            return True
        if status in ("open", "opening"):
            return False
        return None

    @property
    def is_opening(self) -> bool:
        """Return whether the valve is opening."""
        return self._valve_status == "opening"

    @property
    def is_closing(self) -> bool:
        """Return whether the valve is closing."""
        return self._valve_status == "closing"

    @property
    def _valve_status(self) -> str | None:
        """Return a normalized valve status, supporting both device types."""
        value = self.device.get("status_value")
        if self.device.get("type") == "10004":
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in ("open", "close", "opening", "closing"):
                    return normalized
            return None

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "open":
                return "open"
            if normalized == "close":
                return "close"
        is_on = parse_bool_status(value)
        if is_on is not None:
            return "open" if is_on else "close"
        return None

    async def async_open_valve(self, **kwargs: Any) -> None:
        await self._async_execute("open", self.coordinator.client.async_turn_on(self._device_id))

    async def async_close_valve(self, **kwargs: Any) -> None:
        await self._async_execute("close", self.coordinator.client.async_turn_off(self._device_id))
