"""Data Transformer - Abstract base class for southbound data transformation"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from .standard_point import StandardDataPoint, DataQuality

logger = logging.getLogger(__name__)


class DataConverter(Protocol):
    """
    数据转换器协议
    
    任何实现此协议的类都可以作为数据转换器。
    不需要继承，只需要方法签名匹配即可。
    """
    
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
                    "device_id": str,           # 设备ID
                    "connection_status": str,   # 连接状态: connected/disconnected
                    "timestamp": float,         # 时间戳（可选）
                    ...                         # 其他自定义字段
                }
        
        Returns:
            标准数据点字典列表
            格式: [{
                "device_id": str,
                "point_name": str,
                "value": Any,
                "data_type": str,
                "unit": Optional[str],
                "quality": str,  # good/bad/uncertain
                "timestamp": float,
                "metadata": Dict[str, Any]
            }, ...]
        """
        ...


class DataTransformer(ABC):
    """
    数据转换器抽象基类
    
    提供数据转换的通用功能，子类可以继承此类复用代码。
    也可以直接实现 DataConverter Protocol。
    """
    
    __transformer_name__: str = ""
    
    @abstractmethod
    def transform(self, raw_data: Dict[str, Any], point_configs: List[Dict[str, Any]]) -> List[StandardDataPoint]:
        pass
    
    @abstractmethod
    def get_supported_data_types(self) -> List[str]:
        pass
    
    def get_transformer_name(self) -> str:
        return self.__transformer_name__ or self.__class__.__name__
    
    def validate_raw_data(self, raw_data: Dict[str, Any], point_configs: List[Dict[str, Any]]) -> bool:
        if not raw_data:
            logger.warning("Empty raw data provided")
            return False
        if not point_configs:
            logger.warning("No point configurations provided")
            return False
        return True
    
    def assess_quality(self, value: Any, point_config: Dict[str, Any]) -> str:
        if value is None:
            return DataQuality.BAD.value
        
        min_value = point_config.get("min_value")
        max_value = point_config.get("max_value")
        
        if min_value is not None and max_value is not None:
            try:
                if not (min_value <= value <= max_value):
                    return DataQuality.UNCERTAIN.value
            except TypeError:
                pass
        
        return DataQuality.GOOD.value
    
    def convert_value(self, raw_value: Any, data_type: str, scale: Optional[float] = None, offset: Optional[float] = None) -> Any:
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
            elif data_type == "uint16":
                value = int(raw_value) & 0xFFFF
            elif data_type == "int16":
                v = int(raw_value) & 0xFFFF
                value = v if v < 0x8000 else v - 0x10000
            elif data_type == "uint32":
                value = int(raw_value) & 0xFFFFFFFF
            elif data_type == "int32":
                v = int(raw_value) & 0xFFFFFFFF
                value = v if v < 0x80000000 else v - 0x100000000
            elif data_type == "uint64":
                value = int(raw_value) & 0xFFFFFFFFFFFFFFFF
            elif data_type == "int64":
                v = int(raw_value) & 0xFFFFFFFFFFFFFFFF
                value = v if v < 0x8000000000000000 else v - 0x10000000000000000
            elif data_type == "float32":
                value = float(raw_value)
            elif data_type == "float32_swap":
                import struct
                packed = struct.pack('>f', float(raw_value))
                value = struct.unpack('<f', packed)[0]
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
