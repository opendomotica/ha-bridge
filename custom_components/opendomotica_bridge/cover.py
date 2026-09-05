"""Cover platform for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_COVER, COVER_MAX_VALUE, DEVICE_TYPE_MAP, DOMAIN
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .entity import OpenDomoticaBridgeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up covers, adding new ones as they are discovered by the coordinator."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaCover(coordinator, device_id)
            for device_id, device in coordinator.data.items()
            if DEVICE_TYPE_MAP.get(device.get("type")) == CATEGORY_COVER
            and device_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._device_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaCover(OpenDomoticaBridgeEntity, CoverEntity):
    """Representation of a motorised cover exposed by the domotica server.

    The device reports its position via current_value on a 0 (closed) - 250
    (open) scale, rescaled here to HA's 0-100 percentage range. Open/close are
    sent as set_value at the scale extremes (0/250); there is no known "stop"
    command, so CoverEntityFeature.STOP is not advertised.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int | None:
        try:
            raw_value = float(self.device.get("status_value"))
        except (TypeError, ValueError):
            return None
        return round(raw_value / COVER_MAX_VALUE * 100)

    @property
    def is_closed(self) -> bool | None:
        position = self.current_cover_position
        return position == 0 if position is not None else None

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._async_execute(
            "open", self.coordinator.client.async_set_value(self._device_id, COVER_MAX_VALUE)
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._async_execute("close", self.coordinator.client.async_set_value(self._device_id, 0))

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        raw_value = round(kwargs["position"] / 100 * COVER_MAX_VALUE)
        raw_value = max(0, min(COVER_MAX_VALUE, raw_value))
        await self._async_execute(
            "set position of", self.coordinator.client.async_set_value(self._device_id, raw_value)
        )

