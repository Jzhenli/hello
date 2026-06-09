"""MQTT Client 标准适配器 - 默认格式

保持原有行为不变，继承 MQTTAdapterBase，
增加设备名映射、属性映射、时间戳格式化等增强功能。

设计要点：
- _map_device_name 和 _map_properties 仅用于上行方向（内部→客户）
- 下行 parse_command 不做映射，避免语义错误
- _format_timestamp 覆盖一处即可同时生效于单条和批量模式
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from ..adapter import MQTTAdapterBase
from . import register

logger = logging.getLogger(__name__)


@register("standard")
class MQTTClientAdapter(MQTTAdapterBase):
    """
    MQTT Client 标准适配器 - 默认格式

    保持原有行为不变，继承 MQTTAdapterBase，
    增加设备名映射、属性映射、时间戳格式化等增强功能。

    设计要点：
    - _map_device_name 和 _map_properties 仅用于上行方向（内部→客户）
    - 下行 parse_command 不做映射，避免语义错误
    - _format_timestamp 覆盖一处即可同时生效于单条和批量模式
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
        self._property_mapping = self.config.get("property_mapping", {})
        self._device_name_mapping = self.config.get("device_name_mapping", {})

    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        覆盖基类方法，增加 mapping 和 metadata 功能
        """
        context = context or {}
        device_status_map = context.get("device_status_map", {})

        payload = {
            "asset": self._map_device_name(reading.asset),
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": self._map_properties(reading.data),
        }

        # 添加设备状态
        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status

        # 添加 metadata
        if self._include_metadata:
            payload["tags"] = reading.tags
            if reading.standard_points:
                payload["standard_points"] = reading.standard_points

        # 添加 quality 信息
        if self._include_quality and reading.standard_points:
            quality_info = []
            for sp in reading.standard_points:
                if "quality" in sp:
                    quality_info.append({
                        "point_name": sp.get("point_name"),
                        "quality": sp.get("quality"),
                    })
            if quality_info:
                payload["quality"] = quality_info

        return payload

    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        覆盖基类方法，增加 mapping 功能

        注意：仅用于上行方向的命令构造
        """
        return {
            "asset": self._map_device_name(command_data.get("asset", "")),
            "data": self._map_properties(command_data.get("data", {})),
            "timestamp": context.get("timestamp"),
        }

    def _format_timestamp(self, timestamp: float) -> Any:
        """
        覆盖基类方法，支持多种时间戳格式
        """
        if self._timestamp_format in ("iso", "iso8601"):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        elif self._timestamp_format == "milliseconds":
            return int(timestamp * 1000)
        return timestamp

    def _map_device_name(self, device_name: str) -> str:
        """
        映射设备名称（内部名称 → 客户名称，仅用于上行方向）

        Args:
            device_name: 原始设备名称

        Returns:
            映射后的设备名称
        """
        if self._device_name_mapping:
            return self._device_name_mapping.get(device_name, device_name)
        return device_name

    def _map_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        映射属性名称（内部名称 → 客户名称，仅用于上行方向）

        Args:
            data: 原始属性字典

        Returns:
            映射后的属性字典
        """
        if not self._property_mapping:
            return data

        mapped_data = {}
        for key, value in data.items():
            mapped_key = self._property_mapping.get(key, key)
            mapped_data[mapped_key] = value

        return mapped_data
