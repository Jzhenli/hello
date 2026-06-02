"""插件加载器

整合插件发现、注册和生命周期管理的协调器。
使用 PluginDiscoveryService 实现一次性插件发现，避免重复扫描。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

from .types import PluginType, PluginStatus, PluginInfo, SystemHealthStatus
from .discovery import PluginDiscovery
from .discovery_service import PluginDiscoveryService
from .registry import PluginRegistry
from .lifecycle import PluginLifecycle
from ..config import ConfigManager, model_to_dict
from ..event_bus import EventBus, EventType, Event
from ..scheduler import Scheduler, TaskType
from ..interfaces import ILifecycle
from ..exceptions import PluginLoadError

logger = logging.getLogger(__name__)


class PluginLoader(ILifecycle):
    """插件加载器
    
    整合插件发现、注册和生命周期管理的主协调器。
    实现ILifecycle接口，支持统一的启动和停止。
    
    使用 PluginDiscoveryService 实现一次性插件发现，避免重复扫描文件系统。
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        event_bus: EventBus,
        scheduler: Scheduler,
        storage: Any = None,
        metadata_manager: Optional[Any] = None,
        plugin_dirs: Optional[List[str]] = None,
        discovery_service: Optional[PluginDiscoveryService] = None,
        registry: Optional[PluginRegistry] = None,
        stats_manager: Any = None
    ):
        """初始化插件加载器
        
        Args:
            config_manager: 配置管理器
            event_bus: 事件总线
            scheduler: 调度器
            storage: 存储对象
            metadata_manager: 元数据管理器
            plugin_dirs: 插件目录列表
            discovery_service: 插件发现服务（可选，用于共享发现结果）
            registry: 插件注册表（可选，用于共享注册表）
            stats_manager: 统计管理器
        """
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.scheduler = scheduler
        self.storage = storage
        self.metadata_manager = metadata_manager
        self._plugin_dirs = plugin_dirs
        
        # 使用注入的服务或创建默认实例
        self._discovery_service = discovery_service or PluginDiscoveryService()
        self.registry = registry or PluginRegistry()
        
        # 保留 discovery 属性以向后兼容
        self.discovery = PluginDiscovery(plugin_dirs)
        
        self.lifecycle = PluginLifecycle(
            registry=self.registry,
            event_bus=event_bus,
            scheduler=scheduler,
            storage=storage,
            stats_manager=stats_manager
        )
        
        self._running: bool = False
        self._recovery_task_id: Optional[str] = None
        self._discovery_done: bool = False
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    async def start(self) -> None:
        """启动插件加载器"""
        if self._running:
            return
        
        self._running = True
        self.event_bus.subscribe(EventType.CONFIG_RELOADED, self._on_config_reload)
        
        # 启动插件恢复任务
        self._recovery_task_id = self.scheduler.add_task(
            name="plugin_recovery",
            callback=self.lifecycle.recover_failed_plugins,
            task_type=TaskType.MAINTENANCE,
            interval=30,
            initial_delay=10
        )
        await self.scheduler.start_task(self._recovery_task_id)
        
        logger.info("Plugin Loader started")
    
    async def stop(self) -> None:
        """停止插件加载器"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止恢复任务
        if self._recovery_task_id:
            try:
                await self.scheduler.stop_task(self._recovery_task_id)
            except Exception as e:
                logger.error(f"Error stopping recovery task: {e}")
        
        # 停止所有插件
        await self.lifecycle.stop_all_plugins()
        
        logger.info("Plugin Loader stopped")
    
    def discover_plugins(self) -> Dict[str, Type]:
        """发现插件（同步版本，向后兼容）
        
        注意：推荐使用 discover_plugins_async() 以避免阻塞事件循环。
        
        Returns:
            发现的插件类字典
        """
        if self._discovery_done:
            logger.debug("Plugin discovery already done, returning cached results")
            return self.registry.plugin_classes
        
        # 使用旧的发现方式（向后兼容）
        discovered = self.discovery.discover_plugins()
        self.registry.set_plugin_classes(discovered)
        self._discovery_done = True
        return discovered
    
    async def discover_plugins_async(self) -> Dict[str, Type]:
        """异步发现插件（推荐）
        
        使用 PluginDiscoveryService 实现一次性发现，避免重复扫描。
        
        Returns:
            发现的插件类字典
        """
        if self._discovery_done:
            logger.debug("Plugin discovery already done, returning cached results")
            return self.registry.plugin_classes
        
        # 使用 PluginDiscoveryService 进行一次性发现
        plugin_dirs = self._plugin_dirs or [self.discovery._get_default_plugin_dir()]
        discovered = await self._discovery_service.discover_once(plugin_dirs)
        self.registry.set_plugin_classes(discovered)
        self._discovery_done = True
        return discovered
    
    def register_plugin_class(self, plugin_type: Any, name: str, plugin_class: Type) -> None:
        """注册插件类
        
        Args:
            plugin_type: 插件类型
            name: 插件名称
            plugin_class: 插件类
        """
        self.registry.register_plugin_class(plugin_type, name, plugin_class)
    
    async def load_plugin(
        self,
        plugin_type: Any,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PluginInfo]:
        """加载插件
        
        Args:
            plugin_type: 插件类型
            name: 插件名称
            config: 插件配置
            
        Returns:
            插件信息
        """
        # 确保插件类已发现
        if not self.registry.has_plugin_class(plugin_type, name):
            if not self._discovery_done:
                await self.discover_plugins_async()
        
        return await self.lifecycle.load_plugin(plugin_type, name, config)
    
    async def start_plugin(self, plugin_id: str) -> bool:
        """启动插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        return await self.lifecycle.start_plugin(plugin_id)
    
    async def stop_plugin(self, plugin_id: str) -> bool:
        """停止插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        return await self.lifecycle.stop_plugin(plugin_id)
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        return await self.lifecycle.unload_plugin(plugin_id)
    
    async def stop_all_plugins(self) -> None:
        """停止所有插件"""
        await self.lifecycle.stop_all_plugins()
    
    async def load_all_from_config(self) -> None:
        """从配置加载所有插件
        
        [DEPRECATED] 此方法已废弃，请使用 DeviceLoader 从设备文件加载设备。
        设备配置现在应该放在 config/devices/ 目录中。
        """
        import warnings
        warnings.warn(
            "load_all_from_config() is deprecated. Use DeviceLoader to load devices from config/devices/",
            DeprecationWarning,
            stacklevel=2
        )
        
        logger.warning("load_all_from_config() is deprecated. Devices should be loaded from config/devices/")
        
        config = self.config_manager.config.plugins
        
        load_order = [
            (PluginType.STORAGE, []),
            (PluginType.FILTER, config.filter),
            (PluginType.SOUTH, config.south),
            (PluginType.NORTH, config.north)
        ]
        
        for plugin_type, plugin_configs in load_order:
            for plugin_config in plugin_configs:
                if not plugin_config.enabled:
                    continue
                
                plugin_info = await self.load_plugin(
                    plugin_type,
                    plugin_config.name,
                    plugin_config.config
                )
                
                if plugin_info:
                    await self.start_plugin(plugin_info.plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件信息
        """
        return self.registry.get_plugin(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        """获取指定类型的插件
        
        Args:
            plugin_type: 插件类型
            
        Returns:
            插件列表
        """
        return self.registry.get_plugins_by_type(plugin_type)
    
    def get_all_plugins(self) -> List[PluginInfo]:
        """获取所有插件
        
        Returns:
            所有插件列表
        """
        return self.registry.get_all_plugins()
    
    def get_running_plugins(self) -> List[PluginInfo]:
        """获取运行中的插件
        
        Returns:
            运行中的插件列表
        """
        return self.registry.get_running_plugins()
    
    def get_failed_plugins(self) -> List[PluginInfo]:
        """获取失败的插件
        
        Returns:
            失败的插件列表
        """
        return self.registry.get_failed_plugins()
    
    def get_health_status(self) -> SystemHealthStatus:
        """获取系统健康状态
        
        Returns:
            系统健康状态
        """
        return self.registry.get_health_status()
    
    async def _on_config_reload(self, event: Event) -> None:
        """配置重载事件处理
        
        Args:
            event: 配置重载事件
        """
        logger.info("Config reloaded")
        
        logger.info("Note: Device configuration is now managed via device files in config/devices/")

    async def sync_plugin_registry(self) -> None:
        """将已发现的插件元信息同步到 plugin_registry 数据库表

        从每个插件类的 config_schema() 和 capabilities() 方法
        读取配置 Schema 和能力声明，写入数据库以便运行时查询。
        """
        if not self.metadata_manager:
            logger.debug("MetadataManager not available, skipping plugin registry sync")
            return

        from ...config.config_repository import ConfigRepository

        config_repo = ConfigRepository(self.metadata_manager.db)

        for key, plugin_class in self.registry.plugin_classes.items():
            try:
                parts = key.split(":", 1)
                plugin_type = parts[0] if len(parts) == 2 else ""
                plugin_name = parts[1] if len(parts) == 2 else parts[0]

                schema = None
                caps = None
                version = getattr(plugin_class, "__plugin_version__", "1.0.0")
                description = getattr(plugin_class, "__plugin_description__", None)

                if callable(getattr(plugin_class, "config_schema", None)):
                    schema = plugin_class.config_schema()

                if callable(getattr(plugin_class, "capabilities", None)):
                    caps = plugin_class.capabilities()

                defaults = self._extract_defaults_from_schema(schema) if schema else {}

                await config_repo.upsert_plugin_meta(
                    name=plugin_name,
                    plugin_type=plugin_type,
                    version=version,
                    description=description,
                    defaults=defaults,
                    capabilities=caps,
                )
            except Exception as e:
                logger.warning(f"Failed to sync plugin meta for {key}: {e}")

        await config_repo.commit()
        logger.info(f"Synced {len(self.registry.plugin_classes)} plugins to plugin_registry")

    @staticmethod
    def _extract_defaults_from_schema(schema: dict) -> dict:
        """从 JSON Schema 中提取默认值

        Args:
            schema: config_schema() 返回的 JSON Schema 字典

        Returns:
            字段名 -> 默认值的字典
        """
        defaults = {}
        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if "default" in field_schema:
                defaults[field_name] = field_schema["default"]
        return defaults
