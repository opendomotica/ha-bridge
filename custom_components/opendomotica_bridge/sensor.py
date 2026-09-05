"""Sensor platform for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_PORT_STATUS,
    CATEGORY_SENSOR,
    DEVICE_STATUS_ATTRIBUTE,
    DEVICE_TYPE_MAP,
    DOMAIN,
)
from .coordinator import OpenDomoticaDataUpdateCoordinator
from .entity import OpenDomoticaBridgeEntity

# Per-type-code device class / unit, since the "sensor" category covers
# different physical quantities depending on the device type.
_DEVICE_CLASS_BY_TYPE = {
    "20002": SensorDeviceClass.TEMPERATURE,  # Sensore temperatura
    "20003": SensorDeviceClass.ENERGY,       # Contatore energia elettrica (assorbimento)
    "20004": SensorDeviceClass.ENERGY,       # Inverter SMA (produzione fotovoltaica)
}
_UNIT_BY_TYPE = {
    "20002": UnitOfTemperature.CELSIUS,
    "20003": UnitOfEnergy.WATT_HOUR,
    "20004": UnitOfEnergy.WATT_HOUR,
}

# Maps the "historical" flag reported for an attribute to a state class.
_STATE_CLASS_BY_HISTORICAL = {
    "1": SensorStateClass.TOTAL_INCREASING,
    "2": SensorStateClass.MEASUREMENT,
}


def _resolve_state_class(device: dict[str, Any], expected_attribute: str) -> SensorStateClass | None:
    """Derive the state class from the device's attributes "historical" flag.

    An attribute with "historical" != "0" is one the server wants tracked over
    time. When more than one attribute qualifies, prefer the one already used
    as status_value for this device.
    """
    attributes = device.get("attributes")
    if not isinstance(attributes, dict):
        return None

    candidates = {
        name: data.get("historical")
        for name, data in attributes.items()
        if isinstance(data, dict) and data.get("historical") not in (None, "0", 0)
    }
    if not candidates:
        return None

    historical = candidates.get(expected_attribute, next(iter(candidates.values())))
    return _STATE_CLASS_BY_HISTORICAL.get(str(historical))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors, adding new ones as they are discovered by the coordinator."""
    coordinator: OpenDomoticaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_entities = [
            OpenDomoticaSensor(coordinator, device_id)
            for device_id, device in coordinator.data.items()
            if DEVICE_TYPE_MAP.get(device.get("type")) == CATEGORY_SENSOR
            and device_id not in known_ids
        ]
        if new_entities:
            known_ids.update(entity._device_id for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaSensor(OpenDomoticaBridgeEntity, SensorEntity):
    """Representation of a sensor exposed by the domotica server."""

    def __init__(self, coordinator: OpenDomoticaDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        device_type = self.device.get("type")
        self._attr_device_class = _DEVICE_CLASS_BY_TYPE.get(device_type)
        self._attr_native_unit_of_measurement = _UNIT_BY_TYPE.get(device_type)
        expected_attribute = DEVICE_STATUS_ATTRIBUTE.get(device_type, ATTR_PORT_STATUS)
        self._attr_state_class = _resolve_state_class(self.device, expected_attribute)

    @property
    def native_value(self):
        value = self.device.get("status_value")
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return value
