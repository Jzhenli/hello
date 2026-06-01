"""Storage Adapter - Adapts SQLiteStorage to ILifecycle interface"""

import logging
from typing import Dict, Any

from .sqlite import SQLiteStorage
from ..core.interfaces import ILifecycle

logger = logging.getLogger(__name__)


class StorageAdapter(ILifecycle):
    """SQLiteStorage 的生命周期适配器
    
    SQLiteStorage 使用 initialize/close 方法，而不是 start/stop。
    此适配器将其适配到 ILifecycle 接口。
    """
    
    def __init__(self, storage: SQLiteStorage):
        """初始化适配器
        
        Args:
            storage: SQLiteStorage 实例
        """
        self._storage = storage
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """检查存储是否正在运行"""
        return self._running
    
    async def start(self) -> None:
        """启动存储（空操作，因为 SQLiteStorage 在 initialize 时已启动）"""
        if self._running:
            return
        
        # SQLiteStorage 在 initialize() 时已经启动
        # 这里只设置状态标志
        self._running = True
        logger.debug("StorageAdapter started")
    
    async def stop(self) -> None:
        """停止存储"""
        if not self._running:
            return
        
        try:
            await self._storage.close()
            self._running = False
            logger.info("Storage stopped")
        except Exception as e:
            logger.error(f"Error stopping storage: {e}")
            raise
    
    @property
    def storage(self) -> SQLiteStorage:
        """获取底层存储实例"""
        return self._storage
