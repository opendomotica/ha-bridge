"""Constants for the OpenDomotica Bridge integration."""
from homeassistant.const import Platform

DOMAIN = "opendomotica_bridge"

DEFAULT_SCAN_INTERVAL = 30

# Config entry data key holding the generated webhook id used to receive
# push status updates from the domotica server.
CONF_WEBHOOK_ID = "webhook_id"

# Config entry data key holding the area suggested for all devices at setup.
CONF_AREA_ID = "area_id"

PLATFORMS = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.COVER,
    Platform.CLIMATE,
]

# Internal device categories, one per supported HA platform.
CATEGORY_LIGHT = "light"
CATEGORY_SWITCH = "switch"
CATEGORY_SENSOR = "sensor"
CATEGORY_COVER = "cover"
CATEGORY_CLIMATE = "climate"

# Maps the numeric "type" code returned by the domotica server to an internal
# category. Adjust this table if your installation uses other type codes.
DEVICE_TYPE_MAP: dict[str, str] = {
    "10001": CATEGORY_LIGHT,   # Luce
    "10008": CATEGORY_LIGHT,   # Led strip WS2812B
    "10002": CATEGORY_SWITCH,  # Presa
    "10003": CATEGORY_SWITCH,  # Caldaia
    "10004": CATEGORY_SWITCH,  # Elettrovalvola riscaldamento
    "10005": CATEGORY_SWITCH,  # Elettrovalvola irrigazione
    "10006": CATEGORY_SWITCH,  # Alimentatore
    "10101": CATEGORY_SWITCH,  # Ricevitore AV
    "20005": CATEGORY_SWITCH,  # Interruttore
    "20006": CATEGORY_SWITCH,  # Interruttore virtuale
    "10007": CATEGORY_COVER,   # Motore apri/chiudi
    "20002": CATEGORY_SENSOR,  # Sensore temperatura
    "20003": CATEGORY_SENSOR,  # Contatore energia elettrica
    "20004": CATEGORY_SENSOR,  # Inverter SMA
    "30001": CATEGORY_SENSOR,  # UPS
    # "20001" (Pulsante) is a momentary input, not exposed by default: add it
    # here if you want to represent it (e.g. as CATEGORY_SENSOR).
}

# Attribute names exposed by the server under /devices/{id}/attributes/{name}.
ATTR_PORT_STATUS = "port_status"
ATTR_CURRENT_VALUE = "current_value"
ATTR_CURRENT_POWER = "current_power"
ATTR_CURRENT_POWER_AC = "current_power_ac"

# Attribute to poll for each device type code (defaults to ATTR_PORT_STATUS).
DEVICE_STATUS_ATTRIBUTE: dict[str, str] = {
    "10007": ATTR_CURRENT_VALUE,     # Motore apri/chiudi, scala 0 (chiuso) - 250 (aperto)
    "20002": ATTR_CURRENT_VALUE,     # Sensore temperatura
    "20003": ATTR_CURRENT_POWER,     # Contatore energia elettrica (assorbimento)
    "20004": ATTR_CURRENT_POWER_AC,  # Inverter SMA (produzione fotovoltaica)
}

# Motorised covers report their position on a 0 (closed) - 250 (open) scale.
COVER_MAX_VALUE = 250
