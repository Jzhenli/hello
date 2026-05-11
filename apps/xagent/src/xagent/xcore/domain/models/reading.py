"""Reading领域模型

表示一次数据采集的完整记录。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Reading:
    """数据采集记录
    
    表示从设备采集的一次完整数据记录。
    此类为 Reading 的唯一定义，其他模块应从此处导入。
    
    Reading 与 ReadingSet 之间的转换由 rule_engine._core_compat 模块
    中的 reading_to_reading_set() 和 reading_set_to_reading() 函数负责，
    避免领域模型反向依赖业务层。
    
    Attributes:
        asset: 资产名称（设备名称）
        timestamp: 采集时间戳（Unix时间戳）
        service_name: 服务名称（插件名称）
        data: 采集的数据字典
        tags: 数据标签列表
        standard_points: 标准化数据点列表
        device_status: 设备状态（online/offline）
    """
    
    asset: str
    timestamp: float
    service_name: str
    data: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    standard_points: List[Dict[str, Any]] = field(default_factory=list)
    device_status: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "timestamp": self.timestamp,
            "service_name": self.service_name,
            "data": self.data,
            "tags": self.tags,
            "standard_points": self.standard_points,
            "device_status": self.device_status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reading":
        return cls(
            asset=data["asset"],
            timestamp=data["timestamp"],
            service_name=data["service_name"],
            data=data.get("data", {}),
            tags=data.get("tags", []),
            standard_points=data.get("standard_points", []),
            device_status=data.get("device_status")
        )
    
    def __repr__(self) -> str:
        return (
            f"Reading(asset={self.asset!r}, timestamp={self.timestamp}, "
            f"service_name={self.service_name!r}, data_keys={list(self.data.keys())})"
        )
