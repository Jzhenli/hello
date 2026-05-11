"""轻量级依赖注入容器

提供简单的依赖注入功能，支持单例和工厂模式。
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ContainerError(Exception):
    """容器错误"""
    pass


class Container:
    """轻量级依赖注入容器
    
    支持以下注册方式：
    - 单例模式：整个应用生命周期内只创建一个实例
    - 工厂模式：每次解析时创建新实例
    - 实例注册：直接注册已创建的实例
    
    示例:
        container = Container()
        
        # 注册单例
        container.register_singleton(ConfigManager, lambda: ConfigManager.get_instance())
        
        # 注册工厂
        container.register_factory(Storage, lambda: SQLiteStorage())
        
        # 直接注册实例
        container.register_instance(EventBus, event_bus)
        
        # 解析依赖
        config = container.resolve(ConfigManager)
    """
    
    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._instances: Dict[Type, Any] = {}
        self._singleton_cache: Dict[Type, Any] = {}
    
    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> None:
        """注册单例
        
        注册一个类型，容器会在首次解析时创建实例并缓存。
        后续解析将返回同一个实例。
        
        Args:
            interface: 接口类型
            implementation: 实现类型
            
        Example:
            container.register_singleton(IStorage, SQLiteStorage)
        """
        if interface in self._singletons:
            logger.warning(f"Overwriting singleton registration for {interface.__name__}")
        
        self._singletons[interface] = implementation
        logger.debug(f"Registered singleton: {interface.__name__} -> {implementation.__name__}")
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """注册工厂
        
        注册一个工厂函数，每次解析时都会调用工厂创建新实例。
        
        Args:
            interface: 接口类型
            factory: 工厂函数，返回实现实例
            
        Example:
            container.register_factory(IStorage, lambda: SQLiteStorage())
        """
        if interface in self._factories:
            logger.warning(f"Overwriting factory registration for {interface.__name__}")
        
        self._factories[interface] = factory
        logger.debug(f"Registered factory for: {interface.__name__}")
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """注册实例
        
        直接注册一个已创建的实例。
        
        Args:
            interface: 接口类型
            instance: 实例对象
            
        Example:
            event_bus = EventBus()
            container.register_instance(IEventBus, event_bus)
        """
        if interface in self._instances:
            logger.warning(f"Overwriting instance registration for {interface.__name__}")
        
        self._instances[interface] = instance
        logger.debug(f"Registered instance for: {interface.__name__}")
    
    def resolve(self, interface: Type[T]) -> T:
        """解析依赖
        
        根据注册信息返回对应的实例。
        优先级：实例 > 单例 > 工厂
        
        Args:
            interface: 要解析的接口类型
            
        Returns:
            对应的实例
            
        Raises:
            ContainerError: 如果类型未注册
        """
        if interface in self._instances:
            return self._instances[interface]
        
        if interface in self._singletons:
            if interface in self._singleton_cache:
                return self._singleton_cache[interface]
            
            implementation = self._singletons[interface]
            try:
                instance = implementation()
                self._singleton_cache[interface] = instance
                logger.debug(f"Created singleton instance for: {interface.__name__}")
                return instance
            except Exception as e:
                raise ContainerError(
                    f"Failed to create singleton instance for {interface.__name__}: {e}"
                ) from e
        
        if interface in self._factories:
            factory = self._factories[interface]
            try:
                instance = factory()
                logger.debug(f"Created instance via factory for: {interface.__name__}")
                return instance
            except Exception as e:
                raise ContainerError(
                    f"Failed to create instance via factory for {interface.__name__}: {e}"
                ) from e
        
        raise ContainerError(
            f"No registration found for {interface.__name__}. "
            f"Please register it using register_singleton, register_factory, or register_instance."
        )
    
    def try_resolve(self, interface: Type[T]) -> Optional[T]:
        """尝试解析依赖
        
        尝试解析依赖，如果未注册则返回None而不抛出异常。
        
        Args:
            interface: 要解析的接口类型
            
        Returns:
            对应的实例，如果未注册则返回None
            
        Example:
            storage = container.try_resolve(IStorage)
            if storage:
                # 使用storage
                pass
        """
        try:
            return self.resolve(interface)
        except ContainerError:
            return None
    
    def is_registered(self, interface: Type) -> bool:
        """检查类型是否已注册
        
        Args:
            interface: 要检查的接口类型
            
        Returns:
            如果已注册返回True，否则返回False
        """
        return (
            interface in self._instances or
            interface in self._singletons or
            interface in self._factories
        )
    
    def clear(self) -> None:
        """清空所有注册
        
        清除所有已注册的单例、工厂和实例。
        主要用于测试场景。
        """
        self._singletons.clear()
        self._factories.clear()
        self._instances.clear()
        self._singleton_cache.clear()
        logger.debug("Container cleared")
    
    def get_registrations(self) -> Dict[str, List[str]]:
        """获取所有注册信息
        
        Returns:
            包含所有注册信息的字典
        """
        return {
            'singletons': [cls.__name__ for cls in self._singletons.keys()],
            'factories': [cls.__name__ for cls in self._factories.keys()],
            'instances': [cls.__name__ for cls in self._instances.keys()],
            'singleton_cache': [cls.__name__ for cls in self._singleton_cache.keys()],
        }
