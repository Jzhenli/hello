"""Simple Lifecycle Manager - Lightweight component lifecycle management"""

import logging
from typing import List, Tuple, Optional

from .interfaces import ILifecycle

logger = logging.getLogger(__name__)


class SimpleLifecycleManager(ILifecycle):
    """轻量级生命周期管理器
    
    只负责组件注册和统一停止，不处理复杂的依赖关系。
    适用于组件数量较少、依赖关系简单的场景。
    """
    
    def __init__(self):
        """初始化生命周期管理器"""
        self._components: List[Tuple[str, ILifecycle]] = []
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """检查管理器是否正在运行"""
        return self._running
    
    def register(self, component: ILifecycle, name: Optional[str] = None) -> None:
        """注册组件
        
        Args:
            component: 要注册的组件实例
            name: 组件名称（可选，默认使用类名）
            
        Raises:
            TypeError: 如果组件未实现 ILifecycle 接口
        """
        if not isinstance(component, ILifecycle):
            raise TypeError(f"Component must implement ILifecycle: {type(component)}")
        
        name = name or component.__class__.__name__
        self._components.append((name, component))
        logger.debug(f"Registered lifecycle component: {name}")
    
    async def start(self) -> None:
        """启动管理器（空操作，组件应该单独启动）"""
        if self._running:
            return
        
        self._running = True
        logger.info(f"Lifecycle Manager started with {len(self._components)} components")
    
    async def stop(self) -> None:
        """按注册逆序停止所有组件"""
        if not self._running:
            logger.warning("Lifecycle manager is not running, skip stop")
            return
        
        logger.info(f"Stopping {len(self._components)} components...")
        
        # 按注册逆序停止
        for name, component in reversed(self._components):
            try:
                await component.stop()
                logger.info(f"[OK] Stopped: {name}")
            except Exception as e:
                logger.error(f"[FAILED] Failed to stop {name}: {e}")
        
        self._running = False
        logger.info("All components stopped")
    
    def get_status(self) -> dict:
        """获取所有组件的状态
        
        Returns:
            包含所有组件状态的字典
        """
        return {
            "manager_running": self._running,
            "total_components": len(self._components),
            "components": [
                {
                    "name": name,
                    "is_running": component.is_running,
                    "class": component.__class__.__name__
                }
                for name, component in self._components
            ]
        }
    
    def clear(self) -> None:
        """清空所有注册的组件"""
        self._components.clear()
        logger.debug("Lifecycle Manager cleared")
