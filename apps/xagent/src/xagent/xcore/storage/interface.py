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
