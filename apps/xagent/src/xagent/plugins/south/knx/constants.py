"""KNX Constants - Data type mappings and protocol constants"""

DATA_TYPE_MAPPING = {
    "switch": {"device_class": "Switch", "value_attr": "state", "dpt": 1, "data_type": "bool"},
    "binary": {"device_class": "BinarySensor", "value_attr": "state", "dpt": 1, "data_type": "bool"},
    "bool": {"device_class": "BinarySensor", "value_attr": "state", "dpt": 1, "data_type": "bool"},
    "temperature": {"device_class": "Climate", "value_attr": "temperature", "dpt": 9, "data_type": "float", "unit": "°C"},
    "percent": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 5, "data_type": "int", "unit": "%"},
    "brightness": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 5, "data_type": "int", "unit": "%"},
    "dimming": {"device_class": "Light", "value_attr": "current_brightness", "dpt": 5, "data_type": "int", "unit": "%"},
    "blinds": {"device_class": "Cover", "value_attr": "current_position", "dpt": 5, "data_type": "int", "unit": "%"},
    "color_rgb": {"device_class": "Light", "value_attr": "current_color", "dpt": 232, "data_type": "string"},
    "string": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 16, "data_type": "string"},
    "float": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float"},
    "scene": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 18, "data_type": "int"},
    "humidity": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "%"},
    "co2": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "ppm"},
    "voltage": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "V"},
    "current": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "A"},
    "power": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "W"},
    "energy": {"device_class": "Sensor", "value_attr": "resolve", "dpt": 9, "data_type": "float", "unit": "kWh"},
}

DEFAULT_GATEWAY_PORT = 3671
DEFAULT_RECONNECT_INTERVAL = 5
DEFAULT_RECONNECT_MAX_DELAY = 60
DEFAULT_POLL_INTERVAL = 5

ERROR_CODE_DEVICE_OFFLINE = 10

VALUE_RANGES = {
    "temperature": (-273.15, 1000),
    "humidity": (0, 100),
    "percent": (0, 100),
    "brightness": (0, 100),
    "dimming": (0, 100),
    "blinds": (0, 100),
    "co2": (0, 10000),
    "voltage": (0, 1000),
    "current": (0, 1000),
    "power": (0, 100000),
    "energy": (0, 1000000),
}
