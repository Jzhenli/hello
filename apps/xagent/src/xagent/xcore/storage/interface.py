"""Storage interface - Abstract storage layer for data persistence"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..domain.models.reading import Reading

logger = logging.getLogger(__name__)


class StorageInterface(ABC):
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    async def save_batch(self, readings: List[Reading]) -> int:
        pass
    
    @abstractmethod
    async def query(
        self,
        asset: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        active_only: bool = False
    ) -> List[Reading]:
        pass
    
    @abstractmethod
    async def delete_old_readings(self, before_timestamp: float) -> int:
        pass
    
    async def delete_old_readings_batch(
        self,
        before_timestamp: float,
        batch_size: int = 10000
    ) -> int:
        return await self.delete_old_readings(before_timestamp)
    
    async def get_storage_size(self) -> Dict[str, Any]:
        return {"status": "not_implemented"}
    
    async def vacuum(self) -> None:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass
    
    @abstractmethod
    async def get_stats(self, include_device_status: bool = False) -> Dict[str, Any]:
        pass

    async def get_latest_readings_by_device(self, active_only: bool = False) -> List["Reading"]:
        return []
    
    @abstractmethod
    async def get_quality_stats(self) -> Dict[str, Any]:
        """获取数据质量统计
        
        Returns:
            数据质量统计字典，包含:
            - good: 良好数据点数
            - bad: 不良数据点数
            - uncertain: 不确定数据点数
            - total: 总数据点数
        """
        pass
    
    @abstractmethod
    async def count_readings_since(self, timestamp: float) -> int:
        """统计指定时间后的采集量
        
        Args:
            timestamp: Unix时间戳
            
        Returns:
            采集量
        """
        pass
    
    @abstractmethod
    async def count_readings_in_range(
        self,
        start_time: float,
        end_time: float
    ) -> int:
        """统计时间范围内的采集量
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            采集量
        """
        pass
