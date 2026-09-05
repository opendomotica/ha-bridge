"""Switch platform for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_SWITCH, DEVICE_TYPE_MAP, DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .entity import OpenDomoticaBridgeEntity, parse_bool_status


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches, adding new ones as they are discovered by the coordinator."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaSwitch(coordinator, device_id)
            for device_id, device in coordinator.data.items()
            if DEVICE_TYPE_MAP.get(device.get("type")) == CATEGORY_SWITCH
            and device_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._device_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaSwitch(OpenDomoticaBridgeEntity, SwitchEntity):
    """Representation of a switch exposed by the domotica server."""

    @property
    def is_on(self) -> bool | None:
        return parse_bool_status(self.device.get("status_value"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_execute("turn on", self.coordinator.client.async_turn_on(self._device_id))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_execute("turn off", self.coordinator.client.async_turn_off(self._device_id))

