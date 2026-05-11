"""XAgent核心接口定义

定义系统核心组件的抽象接口，支持依赖注入和测试。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .event_bus import EventType, Event
    from .config import GatewayConfig
    from .scheduler import TaskType


class ILifecycle(ABC):
    """生命周期接口
    
    所有需要启动和停止的组件都应实现此接口。
    提供统一的生命周期管理方法。
    """
    
    @abstractmethod
    async def start(self) -> None:
        """启动组件
        
        启动组件并初始化必要的资源。
        如果组件已经在运行，应该直接返回而不抛出异常。
        
        Raises:
            InitializationError: 如果启动失败
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止组件
        
        停止组件并释放资源。
        如果组件已经停止，应该直接返回而不抛出异常。
        
        Raises:
            Exception: 如果停止过程中发生错误
        """
        pass
    
    @property
    @abstractmethod
    def is_running(self) -> bool:
        """检查组件是否正在运行
        
        Returns:
            bool: 如果组件正在运行返回True，否则返回False
        """
        pass


class IPlugin(ABC):
    """插件接口
    
    所有插件都必须实现的基础接口。
    统一了核心插件和规则引擎插件的生命周期管理。
    """
    
    @property
    @abstractmethod
    def plugin_type(self) -> str:
        """获取插件类型
        
        Returns:
            str: 插件类型（south, north, filter, rule, delivery等）
        """
        pass
    
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """获取插件名称
        
        Returns:
            str: 插件名称
        """
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件
        
        Args:
            config: 插件配置字典
            
        Raises:
            ValidationError: 如果配置无效
            InitializationError: 如果初始化失败
        """
        pass
    
    def shutdown(self) -> None:
        """关闭插件，释放资源
        
        默认空实现，子类可按需覆盖。
        """
        pass


class IStorage(ABC):
    """存储接口
    
    定义数据存储的基本操作。
    """
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化存储
        
        Args:
            config: 存储配置
            
        Raises:
            InitializationError: 如果初始化失败
        """
        pass
    
    @abstractmethod
    async def save(self, data: Any) -> None:
        """保存数据
        
        Args:
            data: 要保存的数据
            
        Raises:
            StorageError: 如果保存失败
        """
        pass
    
    @abstractmethod
    async def query(self, **kwargs) -> List[Any]:
        """查询数据
        
        Args:
            **kwargs: 查询参数
            
        Returns:
            List[Any]: 查询结果列表
            
        Raises:
            StorageError: 如果查询失败
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭存储连接
        
        释放所有资源。
        """
        pass


class IEventBus(ABC):
    """事件总线接口
    
    定义事件发布和订阅的基本操作。
    """
    
    @abstractmethod
    async def publish(self, event: Event) -> None:
        """发布事件
        
        Args:
            event: 要发布的事件对象
        """
        pass
    
    @abstractmethod
    def subscribe(self, event_type: EventType, callback: Callable[[Event], Any]) -> None:
        """订阅事件
        
        Args:
            event_type: 要订阅的事件类型
            callback: 事件回调函数
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], Any]) -> None:
        """取消订阅事件
        
        Args:
            event_type: 要取消订阅的事件类型
            callback: 要移除的回调函数
        """
        pass


class IScheduler(ABC):
    """调度器接口
    
    定义任务调度的基本操作。
    """
    
    @abstractmethod
    def add_task(
        self,
        name: str,
        callback: Callable[..., Any],
        task_type: TaskType,
        interval: float,
        initial_delay: float = 0
    ) -> str:
        """添加定时任务
        
        Args:
            name: 任务名称
            callback: 任务回调函数
            task_type: 任务类型
            interval: 执行间隔（秒）
            initial_delay: 初始延迟（秒）
            
        Returns:
            str: 任务ID
        """
        pass
    
    @abstractmethod
    async def start_task(self, task_id: str) -> None:
        """启动任务
        
        Args:
            task_id: 任务ID
            
        Raises:
            KeyError: 如果任务不存在
        """
        pass
    
    @abstractmethod
    async def stop_task(self, task_id: str) -> None:
        """停止任务
        
        Args:
            task_id: 任务ID
            
        Raises:
            KeyError: 如果任务不存在
        """
        pass


class IConfigManager(ABC):
    """配置管理器接口
    
    定义配置管理的基本操作。
    """
    
    @abstractmethod
    def load(self) -> GatewayConfig:
        """加载配置
        
        Returns:
            配置对象
            
        Raises:
            ConfigurationError: 如果配置加载失败
        """
        pass
    
    @abstractmethod
    def reload(self) -> GatewayConfig:
        """重新加载配置
        
        Returns:
            配置对象
            
        Raises:
            ConfigurationError: 如果配置加载失败
        """
        pass
    
    @property
    @abstractmethod
    def config(self) -> GatewayConfig:
        """获取当前配置
        
        Returns:
            当前配置对象
        """
        pass
