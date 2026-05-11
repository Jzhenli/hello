"""Modbus Common Constants - Type mappings and protocol constants shared by TCP and RTU"""

MODBUS_DATA_TYPES = {
    "bool": {"size": 1, "signed": False, "standard_type": "bool"},
    "uint16": {"size": 1, "signed": False, "standard_type": "int"},
    "int16": {"size": 1, "signed": True, "standard_type": "int"},
    "uint32": {"size": 2, "signed": False, "standard_type": "int"},
    "int32": {"size": 2, "signed": True, "standard_type": "int"},
    "float32": {"size": 2, "signed": True, "standard_type": "float"},
    "float32_swap": {"size": 2, "signed": True, "standard_type": "float"},
    "float64": {"size": 4, "signed": True, "standard_type": "float"},
    "uint64": {"size": 4, "signed": False, "standard_type": "int"},
    "int64": {"size": 4, "signed": True, "standard_type": "int"},
    "string": {"size": None, "signed": False, "standard_type": "string"},
}

MODBUS_TO_STANDARD_TYPE = {
    k: v["standard_type"] for k, v in MODBUS_DATA_TYPES.items()
}

BYTE_ORDER_BIG = "big"
BYTE_ORDER_LITTLE = "little"
WORD_ORDER_BIG = "big"
WORD_ORDER_LITTLE = "little"

DEFAULT_SLAVE_ID = 1
DEFAULT_TIMEOUT = 3
DEFAULT_RECONNECT_INTERVAL = 5
DEFAULT_MAX_GAP = 5
