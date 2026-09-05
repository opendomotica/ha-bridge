"""Sensor platform for the OpenDomotica Bridge integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_PORT_STATUS,
    ATTR_TODAY_ENERGY,
    ATTR_TODAY_PULSE_COUNTER,
    CATEGORY_SENSOR,
    DEVICE_EXTRA_ATTRIBUTE,
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
    "20003": SensorDeviceClass.POWER,        # Contatore energia elettrica (potenza istantanea)
    "20004": SensorDeviceClass.POWER,        # Inverter SMA (potenza AC istantanea)
}
_UNIT_BY_TYPE = {
    "20002": UnitOfTemperature.CELSIUS,
    "20003": UnitOfPower.WATT,
    "20004": UnitOfPower.WATT,
}

# Maps the "historical" flag reported for an attribute to a state class.
_STATE_CLASS_BY_HISTORICAL = {
    "1": SensorStateClass.TOTAL_INCREASING,
    "2": SensorStateClass.MEASUREMENT,
}

# Config (device_class, unit, state_class, name) for attributes exposed as an
# extra sensor entity alongside a device's main one (see DEVICE_EXTRA_ATTRIBUTE).
_EXTRA_ATTRIBUTE_CONFIG: dict[str, tuple[SensorDeviceClass, str, SensorStateClass, str]] = {
    ATTR_TODAY_PULSE_COUNTER: (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
        "Daily energy",
    ),
    ATTR_TODAY_ENERGY: (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
        "Daily energy",
    ),
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
    known_keys: set[tuple[str, str | None]] = set()

    def _add_new_entities() -> None:
        new_entities: list[OpenDomoticaSensor] = []
        for device_id, device in coordinator.data.items():
            if DEVICE_TYPE_MAP.get(device.get("type")) != CATEGORY_SENSOR:
                continue
            if (device_id, None) not in known_keys:
                new_entities.append(OpenDomoticaSensor(coordinator, device_id))
            extra_attribute = DEVICE_EXTRA_ATTRIBUTE.get(device.get("type"))
            if extra_attribute and (device_id, extra_attribute) not in known_keys:
                new_entities.append(OpenDomoticaSensor(coordinator, device_id, extra_attribute))
        if new_entities:
            known_keys.update((entity._device_id, entity._extra_attribute) for entity in new_entities)
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class OpenDomoticaSensor(OpenDomoticaBridgeEntity, SensorEntity):
    """Representation of a sensor exposed by the domotica server."""

    def __init__(
        self,
        coordinator: OpenDomoticaDataUpdateCoordinator,
        device_id: str,
        extra_attribute: str | None = None,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._extra_attribute = extra_attribute
        if extra_attribute is not None:
            device_class, unit, state_class, name = _EXTRA_ATTRIBUTE_CONFIG[extra_attribute]
            self._attr_unique_id = f"{self._attr_unique_id}_{extra_attribute}"
            self._attr_name = name
            self._attr_device_class = device_class
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = state_class
            return
        device_type = self.device.get("type")
        self._attr_device_class = _DEVICE_CLASS_BY_TYPE.get(device_type)
        self._attr_native_unit_of_measurement = _UNIT_BY_TYPE.get(device_type)
        expected_attribute = DEVICE_STATUS_ATTRIBUTE.get(device_type, ATTR_PORT_STATUS)
        self._attr_state_class = _resolve_state_class(self.device, expected_attribute)

    @property
    def native_value(self):
        if self._extra_attribute is not None:
            attributes = self.device.get("attributes")
            attribute = attributes.get(self._extra_attribute) if isinstance(attributes, dict) else None
            value = attribute.get("value") if isinstance(attribute, dict) else None
        else:
            value = self.device.get("status_value")
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return value
