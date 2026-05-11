"""网关初始化服务

负责网关组件的初始化和依赖注入配置。
"""

import logging
from typing import Optional

from ...core.config import ConfigManager, model_to_dict
from ...core.event_bus import EventBus
from ...core.scheduler import Scheduler
from ...core.plugin_loader import PluginLoader
from ...core.metadata import MetadataManager
from ...core.container import Container
from ...core.interfaces import ILifecycle
from ...storage import SQLiteStorage, WriteBehindBuffer
from ...api.services.command_executor import CommandExecutor
from ...core.exceptions import InitializationError

logger = logging.getLogger(__name__)


class GatewayInitializer(ILifecycle):
    """网关初始化服务
    
    负责初始化所有网关组件并配置依赖注入容器。
    实现ILifecycle接口，支持统一的启动和停止。
    """
    
    def __init__(self, container: Container, config_manager: Optional[ConfigManager] = None):
        """初始化网关初始化服务
        
        Args:
            container: 依赖注入容器
            config_manager: 可选的外部配置管理器实例
        """
        self.container = container
        self._running = False
        
        # 组件引用
        self.config_manager: Optional[ConfigManager] = config_manager
        self.event_bus: Optional[EventBus] = None
        self.scheduler: Optional[Scheduler] = None
        self.plugin_loader: Optional[PluginLoader] = None
        self.storage: Optional[SQLiteStorage] = None
        self.buffer: Optional[WriteBehindBuffer] = None
        self.command_executor: Optional[CommandExecutor] = None
        self.metadata_manager: Optional[MetadataManager] = None
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    async def start(self) -> None:
        """启动初始化服务"""
        if self._running:
            return
        
        await self.initialize_components()
        self._running = True
        logger.info("Gateway Initializer started")
    
    async def stop(self) -> None:
        """停止初始化服务"""
        if not self._running:
            return
        
        await self.shutdown_components()
        self._running = False
        logger.info("Gateway Initializer stopped")
    
    async def initialize_components(self) -> None:
        """初始化所有组件"""
        logger.info("Initializing XAgent Gateway components...")
        
        try:
            # 1. 初始化配置管理器
            await self._initialize_config_manager()
            
            # 2. 初始化事件总线
            await self._initialize_event_bus()
            
            # 3. 初始化调度器
            await self._initialize_scheduler()
            
            # 4. 初始化存储
            await self._initialize_storage()
            
            # 5. 初始化元数据管理器
            await self._initialize_metadata_manager()
            
            # 6. 初始化命令执行器
            await self._initialize_command_executor()
            
            # 7. 初始化插件加载器
            await self._initialize_plugin_loader()
            
            # 8. 配置依赖注入容器
            self._configure_container()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            await self.shutdown_components()
            raise InitializationError("Gateway", str(e)) from e
    
    async def _initialize_config_manager(self) -> None:
        """初始化配置管理器"""
        logger.debug("Initializing ConfigManager...")
        if self.config_manager is None:
            self.config_manager = ConfigManager()
        self.config_manager.load()
        logger.debug("ConfigManager initialized")
    
    async def _initialize_event_bus(self) -> None:
        """初始化事件总线"""
        logger.debug("Initializing EventBus...")
        self.event_bus = EventBus()
        await self.event_bus.start()
        logger.debug("EventBus initialized")
    
    async def _initialize_scheduler(self) -> None:
        """初始化调度器"""
        logger.debug("Initializing Scheduler...")
        config = self.config_manager.config
        self.scheduler = Scheduler(
            max_workers=config.scheduler.max_workers,
            task_timeout=config.scheduler.task_timeout
        )
        await self.scheduler.start()
        logger.debug("Scheduler initialized")
    
    async def _initialize_storage(self) -> None:
        """初始化存储"""
        logger.debug("Initializing Storage...")
        config = self.config_manager.config
        
        self.storage = SQLiteStorage()
        await self.storage.initialize(model_to_dict(config.storage))
        
        self.buffer = WriteBehindBuffer(
            storage=self.storage,
            batch_size=config.storage.batch_size,
            flush_interval=config.storage.flush_interval
        )
        await self.buffer.start()
        
        logger.debug("Storage initialized")
    
    async def _initialize_metadata_manager(self) -> None:
        """初始化元数据管理器"""
        logger.debug("Initializing MetadataManager...")
        self.metadata_manager = MetadataManager()
        await self.metadata_manager.initialize(storage=self.storage)
        logger.debug("MetadataManager initialized")
    
    async def _initialize_command_executor(self) -> None:
        """初始化命令执行器"""
        logger.debug("Initializing CommandExecutor...")
        self.command_executor = CommandExecutor()
        await self.command_executor.start()
        logger.debug("CommandExecutor initialized")
    
    async def _initialize_plugin_loader(self) -> None:
        """初始化插件加载器"""
        logger.debug("Initializing PluginLoader...")
        
        self.config_manager.set_event_bus(self.event_bus)
        
        self.plugin_loader = PluginLoader(
            config_manager=self.config_manager,
            event_bus=self.event_bus,
            scheduler=self.scheduler,
            storage=self.buffer,
            metadata_manager=self.metadata_manager
        )
        await self.plugin_loader.start()
        
        plugin_classes = self.plugin_loader.discover_plugins()
        logger.info(f"Discovered {len(plugin_classes)} plugin classes: {list(plugin_classes.keys())}")
        
        if self.command_executor:
            self.command_executor.set_plugin_loader(self.plugin_loader)
        
        logger.debug("PluginLoader initialized")
    
    def _configure_container(self) -> None:
        """配置依赖注入容器"""
        logger.debug("Configuring dependency injection container...")
        
        # 注册核心组件
        self.container.register_instance(ConfigManager, self.config_manager)
        self.container.register_instance(EventBus, self.event_bus)
        self.container.register_instance(Scheduler, self.scheduler)
        self.container.register_instance(PluginLoader, self.plugin_loader)
        self.container.register_instance(SQLiteStorage, self.storage)
        self.container.register_instance(WriteBehindBuffer, self.buffer)
        self.container.register_instance(CommandExecutor, self.command_executor)
        self.container.register_instance(MetadataManager, self.metadata_manager)
        
        logger.debug("Dependency injection container configured")
    
    async def shutdown_components(self) -> None:
        """关闭所有组件"""
        logger.info("Shutting down components...")
        
        # 按相反顺序关闭
        if self.plugin_loader:
            try:
                await self.plugin_loader.stop()
            except Exception as e:
                logger.error(f"Error stopping plugin loader: {e}")
        
        if self.command_executor:
            try:
                await self.command_executor.stop()
            except Exception as e:
                logger.error(f"Error stopping command executor: {e}")
        
        if self.buffer:
            try:
                await self.buffer.stop()
            except Exception as e:
                logger.error(f"Error stopping buffer: {e}")
        
        if self.storage:
            try:
                await self.storage.close()
            except Exception as e:
                logger.error(f"Error closing storage: {e}")
        
        if self.scheduler:
            try:
                await self.scheduler.stop()
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")
        
        if self.event_bus:
            try:
                await self.event_bus.stop()
            except Exception as e:
                logger.error(f"Error stopping event bus: {e}")
        
        logger.info("All components shut down")
