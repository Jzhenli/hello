"""Generic MQTT Cloud Adapter - Adapts data to standard MQTT format"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

logger = logging.getLogger(__name__)


class MQTTClientAdapter:
    """
    MQTT Client 数据适配器 - 符合 DataAdapter 协议

    将 Reading 数据适配为 MQTT 消息格式。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器

        Args:
            config: 适配器配置，支持 timestamp_format、include_metadata、
                    include_quality、property_mapping、device_name_mapping
        """
        self.config = config or {}
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
        self._property_mapping = self.config.get("property_mapping", {})
        self._device_name_mapping = self.config.get("device_name_mapping", {})

    def adapt_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any]
    ) -> Any:
        """
        适配上传数据

        Args:
            readings: Reading 对象列表
            context: 上下文信息，包含 device_status_map 等

        Returns:
            适配后的数据，单条返回字典，多条返回批量格式
        """
        try:
            if not readings:
                return None

            if len(readings) == 1:
                return self._adapt_single_reading(readings[0], context)
            else:
                return self._adapt_batch_readings(readings, context)
        except Exception as e:
            logger.error(f"Error adapting upload data: {e}")
            return None

    def adapt_command(
        self,
        command_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """
        适配下行命令数据

        Args:
            command_data: 命令数据，包含 asset、data 等
            context: 上下文信息

        Returns:
            适配后的命令数据
        """
        try:
            return {
                "asset": self._map_device_name(command_data.get("asset", "")),
                "data": self._map_properties(command_data.get("data", {})),
                "timestamp": context.get("timestamp")
            }
        except Exception as e:
            logger.error(f"Error adapting command: {e}")
            return command_data

    def parse_response(
        self,
        response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析响应数据

        Args:
            response: 原始响应（dict、bytes、str 或其他类型）
            context: 上下文信息

        Returns:
            解析后的字典，包含 device_id、data、status、error 等字段
        """
        try:
            if isinstance(response, dict):
                return response

            if isinstance(response, bytes):
                try:
                    return json.loads(response.decode("utf-8"))
                except json.JSONDecodeError:
                    return {"raw": response.decode("utf-8")}

            if isinstance(response, str):
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    return {"raw": response}

            return {"raw": str(response)}
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {"raw": str(response), "error": str(e)}

    def _adapt_single_reading(
        self,
        reading: Reading,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        适配单条 Reading 数据

        Args:
            reading: Reading 对象
            context: 上下文信息

        Returns:
            适配后的字典
        """
        context = context or {}
        device_status_map = context.get("device_status_map", {})

        payload = {
            "asset": self._map_device_name(reading.asset),
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": self._map_properties(reading.data),
        }

        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status

        if self._include_metadata:
            payload["tags"] = reading.tags
            if reading.standard_points:
                payload["standard_points"] = reading.standard_points

        if self._include_quality and reading.standard_points:
            quality_info = []
            for sp in reading.standard_points:
                if 'quality' in sp:
                    quality_info.append({
                        "point_name": sp.get("point_name"),
                        "quality": sp.get("quality")
                    })
            if quality_info:
                payload["quality"] = quality_info

        return payload

    def _adapt_batch_readings(
        self,
        readings: List[Reading],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        适配批量 Reading 数据

        Args:
            readings: Reading 对象列表
            context: 上下文信息

        Returns:
            批量格式的字典，包含 count、readings、timestamp
        """
        context = context or {}
        return {
            "count": len(readings),
            "readings": [
                self._adapt_single_reading(r, context) for r in readings
            ],
            "timestamp": self._format_timestamp(readings[0].timestamp)
            if readings else None
        }

    def _map_device_name(self, device_name: str) -> str:
        """
        映射设备名称

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
        映射属性名称

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

    def _format_timestamp(self, timestamp: float) -> Any:
        """
        格式化时间戳

        Args:
            timestamp: Unix 时间戳

        Returns:
            格式化后的时间戳（unix、iso8601 或 milliseconds）
        """
        if self._timestamp_format == "iso" or self._timestamp_format == "iso8601":
            return datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).isoformat()
        elif self._timestamp_format == "milliseconds":
            return int(timestamp * 1000)
        return timestamp

    def to_json(self, payload: Any) -> str:
        """
        将数据序列化为 JSON 字符串

        Args:
            payload: 待序列化的数据

        Returns:
            JSON 字符串
        """
        return json.dumps(payload, ensure_ascii=False)
