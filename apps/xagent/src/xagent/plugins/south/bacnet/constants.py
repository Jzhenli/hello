"""BACnet Constants - Type mappings and protocol constants"""

BACNET_OBJECT_TYPE_MAPPINGS = {
    "analogInput": {"standard_type": "float", "object_type": "analogInput"},
    "analogOutput": {"standard_type": "float", "object_type": "analogOutput"},
    "analogValue": {"standard_type": "float", "object_type": "analogValue"},
    "binaryInput": {"standard_type": "bool", "object_type": "binaryInput"},
    "binaryOutput": {"standard_type": "bool", "object_type": "binaryOutput"},
    "binaryValue": {"standard_type": "bool", "object_type": "binaryValue"},
    "multiStateInput": {"standard_type": "int", "object_type": "multiStateInput"},
    "multiStateOutput": {"standard_type": "int", "object_type": "multiStateOutput"},
    "multiStateValue": {"standard_type": "int", "object_type": "multiStateValue"},
}

BACNET_PHYSICAL_QUANTITY_MAPPINGS = {
    "temperature": {"standard_type": "float", "unit": "°C"},
    "humidity": {"standard_type": "float", "unit": "%"},
    "pressure": {"standard_type": "float", "unit": "Pa"},
    "flow": {"standard_type": "float", "unit": "m³/h"},
    "power": {"standard_type": "float", "unit": "kW"},
    "energy": {"standard_type": "float", "unit": "kWh"},
    "voltage": {"standard_type": "float", "unit": "V"},
    "current": {"standard_type": "float", "unit": "A"},
    "frequency": {"standard_type": "float", "unit": "Hz"},
    "speed": {"standard_type": "float", "unit": "rpm"},
    "percent": {"standard_type": "float", "unit": "%"},
    "co2": {"standard_type": "float", "unit": "ppm"},
}

BACNET_DATA_TYPES = {**BACNET_OBJECT_TYPE_MAPPINGS, **BACNET_PHYSICAL_QUANTITY_MAPPINGS}

BACNET_OBJECT_TYPES = {
    "analogInput": 0,
    "analogOutput": 1,
    "analogValue": 2,
    "binaryInput": 3,
    "binaryOutput": 4,
    "binaryValue": 5,
    "multiStateInput": 13,
    "multiStateOutput": 14,
    "multiStateValue": 19,
}

BACNET_PROPERTY_IDS = {
    "presentValue": 85,
    "description": 28,
    "units": 117,
    "objectName": 77,
    "objectType": 79,
    "objectIdentifier": 75,
    "statusFlags": 111,
    "eventState": 36,
    "reliability": 103,
    "outOfService": 81,
    "priorityArray": 87,
    "relinquishDefault": 104,
    "covIncrement": 22,
}

DEFAULT_PORT = 47808
DEFAULT_DEVICE_ID = 100
DEFAULT_TIMEOUT = 3.0
DEFAULT_INTERVAL = 5
DEFAULT_RECONNECT_INTERVAL = 5

HEARTBEAT_MODE_DEVICE_OBJECT = "device_object"
HEARTBEAT_MODE_NONE = "none"

DEFAULT_HEARTBEAT_MODE = HEARTBEAT_MODE_DEVICE_OBJECT
DEFAULT_HEARTBEAT_PROPERTY = "objectName"
DEFAULT_HEARTBEAT_TIMEOUT = 5.0
DEFAULT_HEARTBEAT_RETRIES = 3

INTERNAL_ERROR_CODES = {
    0: "success",
    1: "invalid_parameter",
    2: "missing_parameter",
    3: "parameter_out_of_range",
    4: "too_many_arguments",
    5: "missing_required_parameter",
    6: "unsupported_parameter",
    7: "invalid_parameter_data_type",
    8: "property_is_not_a_list",
    9: "abort_buffer_overflow",
    10: "communication_disabled",
    11: "unknown_device",
    12: "unknown_object",
    13: "unknown_property",
    14: "read_access_denied",
    15: "write_access_denied",
    16: "value_not_initialized",
    17: "operational_problem",
    18: "out_of_resources",
    19: "configuration_in_progress",
    20: "device_busy",
    21: "abort_apdu_too_long",
    22: "abort_application_exceeded_reply_time",
    23: "abort_out_of_buffer",
    24: "abort_tsm_timeout",
    25: "abort_window_exceeded",
    26: "abort_unknown_apdu",
    27: "abort_unspecified",
    28: "abort_unrecognized_service",
    29: "abort_invalid_apdu",
    30: "abort_preempted_by_higher_priority_task",
    31: "abort_buffer_overflow",
}

BACNET_ERROR_CODES = INTERNAL_ERROR_CODES
