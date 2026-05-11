"""Cloud Adapter - Data adapter protocol and utilities for northbound cloud adaptation"""

import logging
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from ..storage.interface import Reading

logger = logging.getLogger(__name__)


class DataAdapter(Protocol):
    """
    数据适配器协议
    
    任何实现此协议的类都可以作为数据适配器。
    不需要继承，只需要方法签名匹配即可。
    
    这是北向插件数据适配的统一接口，所有北向适配器
    （如 MQTTClientAdapter、XNCJsonAdapter、XNCProtobufAdapter）
    都遵循此协议。
    """
    
    def adapt_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any]
    ) -> Any:
        """
        适配上传数据
        
        Args:
            readings: Reading 对象列表
            
            context: 上下文信息
                格式: {
                    "device_status_map": Dict[str, str],  # 设备状态映射
                    "timestamp": float,                   # 时间戳
                    "batch_mode": bool,                   # 是否批量模式
                    ...                                   # 其他自定义字段
                }
        
        Returns:
            适配后的数据（格式由具体实现决定）
            - JSON 格式：返回 Dict 或 List[Dict]
            - Protobuf 格式：返回 Message 对象
            - 其他格式：返回对应的数据结构
        """
        ...
    
    def adapt_command(
        self,
        command_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """
        适配下行命令
        
        Args:
            command_data: 命令数据
                格式: {
                    "asset": str,           # 设备ID
                    "command": str,         # 命令类型
                    "data": Dict[str, Any]  # 命令数据
                }
            
            context: 上下文信息
        
        Returns:
            适配后的命令数据
        """
        ...
    
    def parse_response(
        self,
        response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析响应数据
        
        Args:
            response: 原始响应数据
            context: 上下文信息
        
        Returns:
            解析后的数据字典
            格式: {
                "device_id": str,
                "data": Dict[str, Any],
                "status": str,
                "error": Optional[str]
            }
        """
        ...


def validate_readings(readings: List[Reading]) -> bool:
    """验证 Reading 列表是否有效
    
    Args:
        readings: Reading 对象列表
    
    Returns:
        列表是否非空且有效
    """
    if not readings:
        logger.warning("Empty readings list provided")
        return False
    return True


def format_timestamp(timestamp: float, format_type: str = "unix") -> Any:
    """格式化时间戳
    
    Args:
        timestamp: Unix 时间戳
        format_type: 格式类型（unix/iso8601/milliseconds）
    
    Returns:
        格式化后的时间值
    """
    if format_type == "unix":
        return timestamp
    elif format_type == "iso8601":
        from datetime import datetime, timezone
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    elif format_type == "milliseconds":
        return int(timestamp * 1000)
    else:
        return timestamp


class CloudAdapter(ABC):
    """
    [DEPRECATED] 云适配器抽象基类
    
    此类已废弃，请直接实现 DataAdapter Protocol。
    DataAdapter 是北向插件数据适配的统一接口，
    支持 adapt_upload/adapt_command/parse_response 三个方法。
    
    如需 validate_readings 或 format_timestamp 等工具函数，
    请使用模块级的 validate_readings() 和 format_timestamp() 函数。
    """
    
    __adapter_name__: str = ""
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f"CloudAdapter is deprecated. "
            f"Please implement DataAdapter Protocol directly. "
            f"Use validate_readings() and format_timestamp() module-level functions instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    def adapt(self, readings: List[Reading]) -> Any:
        pass
    
    @abstractmethod
    def get_cloud_type(self) -> str:
        pass
    
    @abstractmethod
    def adapt_batch(self, readings: List[Reading]) -> List[Any]:
        pass
    
    def get_adapter_name(self) -> str:
        return self.__adapter_name__ or self.__class__.__name__
    
    def validate_readings(self, readings: List[Reading]) -> bool:
        return validate_readings(readings)
    
    def format_timestamp(self, timestamp: float, format_type: str = "unix") -> Any:
        return format_timestamp(timestamp, format_type)
