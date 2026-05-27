"""KNX Constants - Data type mappings and protocol constants"""

DATA_TYPE_MAPPING = {
    "switch": {
        "device_class": "Switch",
        "value_attr": "state",
        "value_type": "property",
        "dpt": 1,
        "data_type": "bool"
    },
    "binary": {
        "device_class": "BinarySensor",
        "value_attr": "state",
        "value_type": "property",
        "dpt": 1,
        "data_type": "bool"
    },
    "bool": {
        "device_class": "BinarySensor",
        "value_attr": "state",
        "value_type": "property",
        "dpt": 1,
        "data_type": "bool"
    },
    "temperature": {
        "device_class": "Climate",
        "value_attr": "temperature",
        "value_type": "property",
        "dpt": 9,
        "data_type": "float",
        "unit": "°C"
    },
    "percent": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": "5.001",
        "data_type": "int",
        "unit": "%",
        "writable_device_class": "Light",
        "writable_config": {
            "use_brightness": True,
            "description": "通用百分比控制（阀门、风机等）"
        }
    },
    "brightness": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": "5.001",
        "data_type": "int",
        "unit": "%",
        "writable_device_class": "Light",
        "writable_config": {
            "use_brightness": True,
            "description": "亮度传感器（可写时使用Light设备）"
        }
    },
    "dimming": {
        "device_class": "Light",
        "value_attr": "current_brightness",
        "value_type": "property",
        "dpt": "5.001",
        "data_type": "int",
        "unit": "%",
        "writable_config": {
            "use_brightness": True,
            "description": "可调光灯"
        }
    },
    "blinds": {
        "device_class": "Cover",
        "value_attr": "current_position",
        "value_type": "method",
        "dpt": "5.001",
        "data_type": "int",
        "unit": "%",
        "writable_config": {
            "description": "窗帘/百叶窗"
        }
    },
    "color_rgb": {
        "device_class": "Light",
        "value_attr": "current_color",
        "value_type": "property",
        "dpt": 232,
        "data_type": "string",
        "writable_config": {
            "use_color": True,
            "description": "RGB颜色灯"
        }
    },
    "string": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 16,
        "data_type": "string"
    },
    "float": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float"
    },
    "scene": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 18,
        "data_type": "int"
    },
    "humidity": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "%"
    },
    "co2": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "ppm"
    },
    "voltage": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "V"
    },
    "current": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "A"
    },
    "power": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "W"
    },
    "energy": {
        "device_class": "Sensor",
        "value_attr": "resolve",
        "value_type": "special",
        "dpt": 9,
        "data_type": "float",
        "unit": "kWh"
    },
}

DEFAULT_GATEWAY_PORT = 3671
DEFAULT_RECONNECT_INTERVAL = 5
DEFAULT_RECONNECT_MAX_DELAY = 60
DEFAULT_POLL_INTERVAL = 5

ERROR_CODE_DEVICE_OFFLINE = 10

VALUE_RANGES = {
    "temperature": (-40, 120),
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
