"""KNX Data Converter - Converts KNX device data to standard format"""

import logging
from typing import Any, Dict, List, Optional

from .constants import DATA_TYPE_MAPPING, ERROR_CODE_DEVICE_OFFLINE, VALUE_RANGES

logger = logging.getLogger(__name__)

KNX_ERROR_MESSAGES = {
    10: "device_offline",
}


class KNXConverter:
    """
    KNX 数据转换器 - 符合 DataConverter 协议

    将 KNX 设备原始数据转换为标准格式。
    """

    @staticmethod
    def _get_point_config(point: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取点位配置字段（优先从 config 子对象读取，兼容顶层读取）"""
        point_config = point.get("config", {})
        if key in point_config:
            return point_config[key]
        if key in point:
            return point[key]
        return default

    def convert(
        self,
        raw_data: Dict[str, Any],
        point_configs: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not raw_data or not point_configs:
            return []

        device_id = context.get("device_id", "unknown")
        connection_status = context.get("connection_status", "connected")
        timestamp = context.get("timestamp")

        points = []

        for point_config in point_configs:
            point_name = point_config.get("name")
            if not point_name:
                continue

            raw_value = raw_data.get(point_name)

            data_type_config = self._get_point_config(point_config, "data_type", "switch")
            type_info = DATA_TYPE_MAPPING.get(data_type_config, DATA_TYPE_MAPPING["switch"])

            standard_data_type = type_info.get("data_type", "string")
            unit = self._get_point_config(point_config, "unit", type_info.get("unit"))
            scale = self._get_point_config(point_config, "scale")
            offset = self._get_point_config(point_config, "offset")

            converted_value = None
            quality = "bad"
            error_code = None

            if connection_status != "connected":
                error_code = ERROR_CODE_DEVICE_OFFLINE
                if raw_value is not None:
                    converted_value = self._convert_value(raw_value, standard_data_type, scale, offset)
            elif raw_value is not None:
                converted_value = self._convert_value(raw_value, standard_data_type, scale, offset)
                quality = self._assess_quality(
                    converted_value,
                    point_config,
                    connection_status
                )
            else:
                error_code = ERROR_CODE_DEVICE_OFFLINE

            metadata = {
                "group_address": self._get_point_config(point_config, "group_address"),
                "status_address": self._get_point_config(point_config, "status_address"),
                "control_address": self._get_point_config(point_config, "control_address"),
                "writable": self._get_point_config(point_config, "writable", False),
                "dpt": type_info.get("dpt"),
                "device_class": type_info.get("device_class"),
                "raw_value": raw_value
            }

            if scale is not None:
                metadata["scale"] = scale
            if offset is not None:
                metadata["offset"] = offset
            if error_code is not None:
                metadata["error_code"] = error_code
                metadata["error_message"] = KNX_ERROR_MESSAGES.get(error_code, "unknown_error")

            point_data = {
                "device_id": device_id,
                "point_name": point_name,
                "value": converted_value,
                "data_type": data_type_config,
                "standard_data_type": standard_data_type,
                "unit": unit,
                "quality": quality,
                "metadata": metadata
            }

            if timestamp:
                point_data["timestamp"] = timestamp

            points.append(point_data)

        return points

    def _convert_value(
        self,
        raw_value: Any,
        data_type: str,
        scale: Optional[float] = None,
        offset: Optional[float] = None
    ) -> Any:
        if raw_value is None:
            return None

        try:
            if data_type == "int":
                value = int(raw_value)
            elif data_type == "float":
                value = float(raw_value)
            elif data_type == "bool":
                if isinstance(raw_value, bool):
                    value = raw_value
                elif isinstance(raw_value, (int, float)):
                    value = bool(raw_value)
                elif isinstance(raw_value, str):
                    value = raw_value.lower() in ("true", "1", "yes", "on")
                else:
                    value = bool(raw_value)
            elif data_type == "string":
                value = str(raw_value)
            else:
                value = raw_value

            if scale is not None and isinstance(value, (int, float)):
                value = value * scale
            if offset is not None and isinstance(value, (int, float)):
                value = value + offset

            return value
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert value {raw_value} to type {data_type}: {e}")
            return None

    def _assess_quality(
        self,
        value: Any,
        point_config: Dict[str, Any],
        connection_status: str
    ) -> str:
        if connection_status != "connected":
            return "bad"

        if value is None:
            return "bad"

        data_type = self._get_point_config(point_config, "data_type")
        if data_type in VALUE_RANGES:
            min_val, max_val = VALUE_RANGES[data_type]
            if isinstance(value, (int, float)) and not (min_val <= value <= max_val):
                return "uncertain"

        return "good"

    def get_type_info(self, data_type: str) -> Dict[str, Any]:
        return DATA_TYPE_MAPPING.get(data_type, DATA_TYPE_MAPPING["switch"])

    def get_standard_data_type(self, knx_data_type: str) -> str:
        type_info = self.get_type_info(knx_data_type)
        return type_info.get("data_type", "string")
