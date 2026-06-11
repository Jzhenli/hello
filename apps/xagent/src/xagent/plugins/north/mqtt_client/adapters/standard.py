"""MQTT标准适配器 - 默认格式

保持原有行为不变，继承 BaseAdapter，
增加设备名映射、属性映射、时间戳格式化等增强功能。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from .base import BaseAdapter
from .registry import register

logger = logging.getLogger(__name__)


@register("standard")
class StandardAdapter(BaseAdapter):
    """标准适配器 - 默认数据格式"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._timestamp_format = self._config.get("timestamp_format", "unix")
        self._include_metadata = self._config.get("include_metadata", True)
        self._include_quality = self._config.get("include_quality", True)
        self._property_mapping = self._config.get("property_mapping", {})
        self._device_name_mapping = self._config.get("device_name_mapping", {})

    # ===== Topic 上下文（协议特有变量） =====

    def _topic_context(
        self,
        upload_type: str,
        readings: Optional[List[Reading]] = None,
    ) -> Dict[str, str]:
        """标准适配器：添加 service_name, asset 等运行时变量"""
        context = super()._topic_context(upload_type, readings)
        if readings:
            context["service_name"] = readings[0].service_name or ""
            context["asset"] = readings[0].asset
        return context

    def _build_upload_payload(self, readings: List[Reading], upload_type: str) -> Dict[str, Any]:
        """构建标准格式payload"""
        if len(readings) == 1:
            return self._adapt_single_reading(readings[0])
        else:
            return {
                "count": len(readings),
                "readings": [self._adapt_single_reading(r) for r in readings],
                "timestamp": self._format_timestamp(readings[0].timestamp),
            }

    def _adapt_single_reading(self, reading: Reading) -> Dict[str, Any]:
        payload = {
            "asset": self._map_device_name(reading.asset),
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": self._map_properties(reading.data),
        }

        if reading.device_status:
            payload["device_status"] = reading.device_status

        if self._include_metadata:
            payload["tags"] = reading.tags
            if reading.standard_points:
                payload["standard_points"] = reading.standard_points

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

    def _format_timestamp(self, timestamp: float) -> float:
        """格式化时间戳

        根据配置返回不同格式：
        - "iso"/"iso8601": ISO 8601 字符串格式
        - "milliseconds": 毫秒级整数
        - 其他: 原始 Unix 时间戳（浮点数，秒）

        注意：返回类型根据配置不同而不同，消费者需根据 timestamp_format 配置处理。

        Args:
            timestamp: Unix 时间戳（秒）

        Returns:
            格式化后的时间戳（类型取决于配置）
        """
        if self._timestamp_format in ("iso", "iso8601"):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        elif self._timestamp_format == "milliseconds":
            return int(timestamp * 1000)
        return timestamp

    def _map_device_name(self, device_name: str) -> str:
        if self._device_name_mapping:
            return self._device_name_mapping.get(device_name, device_name)
        return device_name

    def _map_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._property_mapping:
            return data

        mapped_data = {}
        for key, value in data.items():
            mapped_key = self._property_mapping.get(key, key)
            mapped_data[mapped_key] = value

        return mapped_data
