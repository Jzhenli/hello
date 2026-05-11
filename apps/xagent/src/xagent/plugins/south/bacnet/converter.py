"""BACnet Data Converter - Converts BACnet device data to standard format"""

import logging
from typing import Any, Dict, List, Optional

from .constants import BACNET_DATA_TYPES, INTERNAL_ERROR_CODES

logger = logging.getLogger(__name__)


class BACnetConverter:
    """
    BACnet 数据转换器 - 符合 DataConverter 协议
    
    将 BACnet 设备原始数据转换为标准格式。
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
    
    def __init__(self):
        self._type_mappings = BACNET_DATA_TYPES
    
    def convert(
        self,
        raw_data: Dict[str, Any],
        point_configs: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        转换原始数据为标准格式
        
        Args:
            raw_data: 原始数据字典
                格式: {point_name: value, ...}
            
            point_configs: 点位配置列表
                格式: [{"name": str, "data_type": str, ...}, ...]
            
            context: 上下文信息
                格式: {
                    "device_id": str,
                    "connection_status": str,
                    "timestamp": float (可选)
                }
        
        Returns:
            标准数据点字典列表
        """
        if not point_configs:
            return []
        
        device_id = context.get("device_id", "unknown")
        connection_status = context.get("connection_status", "connected")
        timestamp = context.get("timestamp")
        
        points = []
        
        for config in point_configs:
            point_name = config.get("name")
            if not point_name:
                continue
            
            raw_value = raw_data.get(point_name)
            data_type = self._get_point_config(config, "data_type", "analogInput")
            
            type_mapping = self._type_mappings.get(data_type, {})
            standard_type = type_mapping.get("standard_type", "float")
            default_unit = type_mapping.get("unit")
            
            converted_value = None
            quality = "bad"
            error_code = None
            
            if connection_status != "connected":
                error_code = 10
                if raw_value is not None:
                    converted_value = self._convert_value(
                        raw_value,
                        standard_type,
                        self._get_point_config(config, "scale"),
                        self._get_point_config(config, "offset")
                    )
            elif raw_value is not None:
                converted_value = self._convert_value(
                    raw_value,
                    standard_type,
                    self._get_point_config(config, "scale"),
                    self._get_point_config(config, "offset")
                )
                quality = self._assess_quality(
                    converted_value,
                    config,
                    connection_status
                )
            else:
                error_code = 10
            
            metadata = {
                "object_type": self._get_point_config(config, "object_type"),
                "object_instance": self._get_point_config(config, "object_instance"),
                "property_id": self._get_point_config(config, "property_id", "presentValue"),
                "writable": self._get_point_config(config, "writable", False),
                "raw_value": raw_value
            }
            
            if error_code is not None:
                metadata["error_code"] = error_code
                metadata["error_message"] = INTERNAL_ERROR_CODES.get(error_code, "unknown_error")
            
            point_data = {
                "device_id": device_id,
                "point_name": point_name,
                "value": converted_value,
                "data_type": data_type,
                "standard_data_type": standard_type,
                "unit": self._get_point_config(config, "unit", default_unit),
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
        standard_type: str,
        scale: Optional[float] = None,
        offset: Optional[float] = None
    ) -> Any:
        """
        转换值类型
        
        Args:
            raw_value: 原始值
            standard_type: 目标数据类型
            scale: 缩放因子
            offset: 偏移量
        
        Returns:
            转换后的值
        """
        if raw_value is None:
            return None
        
        try:
            if standard_type == "float":
                value = float(raw_value)
            elif standard_type == "int":
                value = int(raw_value)
            elif standard_type == "bool":
                if isinstance(raw_value, bool):
                    value = raw_value
                elif isinstance(raw_value, str):
                    value = raw_value.lower() in ("true", "1", "yes", "on", "active")
                elif isinstance(raw_value, (int, float)):
                    value = raw_value != 0
                else:
                    value = bool(raw_value)
            elif standard_type == "string":
                value = str(raw_value)
            else:
                value = raw_value
            
            if scale is not None and isinstance(value, (int, float)):
                value = value * scale
            if offset is not None and isinstance(value, (int, float)):
                value = value + offset
            
            return value
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Value conversion failed for {raw_value}: {e}")
            return None
    
    def _assess_quality(
        self,
        value: Any,
        config: Dict[str, Any],
        connection_status: str
    ) -> str:
        """
        评估数据质量
        
        Args:
            value: 转换后的值
            config: 点位配置
            connection_status: 连接状态
        
        Returns:
            质量状态: good/bad/uncertain
        """
        if connection_status != "connected":
            return "bad"
        
        if value is None:
            return "bad"
        
        metadata = config.get("metadata", {})
        point_config = config.get("config", {})
        
        min_val = self._get_range_value(metadata, point_config, "min_value", "min")
        max_val = self._get_range_value(metadata, point_config, "max_value", "max")
        
        if min_val is None and config.get("min_value") is not None:
            min_val = config["min_value"]
        if max_val is None and config.get("max_value") is not None:
            max_val = config["max_value"]
        
        if min_val is not None and max_val is not None:
            try:
                if not (min_val <= value <= max_val):
                    return "uncertain"
            except TypeError:
                pass
        
        return "good"
    
    @staticmethod
    def _get_range_value(
        metadata: Dict[str, Any],
        point_config: Dict[str, Any],
        primary_key: str,
        fallback_key: str
    ) -> Any:
        """
        安全获取范围值，避免 or 运算符在值为 0 时跳过的问题
        
        Args:
            metadata: 点位 metadata 子对象
            point_config: 点位 config 子对象
            primary_key: 主键名 (如 min_value, max_value)
            fallback_key: 备用键名 (如 min, max)
        
        Returns:
            范围值，未找到则返回 None
        """
        if primary_key in metadata and metadata[primary_key] is not None:
            return metadata[primary_key]
        if fallback_key in metadata and metadata[fallback_key] is not None:
            return metadata[fallback_key]
        if primary_key in point_config and point_config[primary_key] is not None:
            return point_config[primary_key]
        return None
    
    def get_type_mapping(self, data_type: str) -> Dict[str, Any]:
        """获取类型映射信息"""
        return self._type_mappings.get(data_type, {})
    
    def get_standard_data_type(self, bacnet_data_type: str) -> str:
        """获取标准数据类型"""
        type_mapping = self.get_type_mapping(bacnet_data_type)
        return type_mapping.get("standard_type", "float")
