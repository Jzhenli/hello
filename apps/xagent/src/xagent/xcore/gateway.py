"""XAgent Gateway Core

网关协调器，负责协调各服务层的工作。
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from .core.container import Container
from .core.config import ConfigManager
from .core.plugin_loader import PluginLoader, PluginType
from .core.interfaces import ILifecycle
from .core.scheduler import Scheduler, TaskType
from .services.orchestration import PluginOrchestrator
from .services.initialization import GatewayInitializer, DeviceLoader
from .services.monitoring import HealthMonitor
from .storage import DataCleanupTask
from .api.dependencies import set_gateway_storage

if TYPE_CHECKING:
    from .rule_engine.orchestrator import RuleEngineOrchestrator

logger = logging.getLogger(__name__)


class Gateway(ILifecycle):
    """网关协调器
    
    负责协调初始化服务、插件编排服务和健康监控服务的工作。
    实现ILifecycle接口，提供统一的启动和停止方法。
    """
    
    DEFAULT_CONFIG_CHECK_INTERVAL = 5
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化网关
        
        Args:
            config_manager: 可选的外部配置管理器实例
        """
        self.container = Container()
        self._external_config_manager = config_manager
        
        # 服务层
        self._initializer: Optional[GatewayInitializer] = None
        self._orchestrator: Optional[PluginOrchestrator] = None
        self._health_monitor: Optional[HealthMonitor] = None
        self._device_loader: Optional[DeviceLoader] = None
        
        # 组件引用（从容器获取）
        self.config_manager: Optional[ConfigManager] = None
        self.plugin_loader: Optional[PluginLoader] = None
        self.cleanup_task: Optional[DataCleanupTask] = None
        self.rule_engine: Optional["RuleEngineOrchestrator"] = None
        
        # 状态
        self._running: bool = False
        self._core_started: bool = False
        self._plugins_started: bool = False
        self._cleanup_scheduler_task_id: Optional[str] = None
        self._config_watcher_task_id: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    @property
    def storage(self) -> Any:
        """获取存储对象（向后兼容）"""
        from .storage import SQLiteStorage
        return self.container.try_resolve(SQLiteStorage)
    
    @property
    def buffer(self) -> Any:
        """获取缓冲对象（向后兼容）"""
        from .storage import WriteBehindBuffer
        return self.container.try_resolve(WriteBehindBuffer)
    
    @property
    def metadata_manager(self) -> Any:
        """获取元数据管理器（向后兼容）"""
        from .core.metadata import MetadataManager
        return self.container.try_resolve(MetadataManager)
    
    async def initialize(self) -> None:
        """初始化网关
        
        使用初始化服务初始化所有组件。
        """
        logger.info("Initializing XAgent Gateway...")
        
        # 使用初始化服务
        self._initializer = GatewayInitializer(self.container, config_manager=self._external_config_manager)
        await self._initializer.start()
        
        # 从容器获取组件引用
        self.config_manager = self.container.resolve(ConfigManager)
        self.plugin_loader = self.container.resolve(PluginLoader)
        
        # 创建服务层
        self._orchestrator = PluginOrchestrator(
            plugin_loader=self.plugin_loader,
            config_manager=self.config_manager
        )
        
        self._health_monitor = HealthMonitor(self.plugin_loader)
        await self._health_monitor.start()
        
        # 初始化数据清理任务
        await self._initialize_cleanup_task()
        
        # 初始化规则引擎
        await self._initialize_rule_engine()
        
        # 设置API依赖
        from .storage import SQLiteStorage, WriteBehindBuffer
        from .core.metadata import MetadataManager
        from .api.services.command_executor import CommandExecutor
        
        set_gateway_storage(
            storage=self.container.resolve(SQLiteStorage),
            buffer=self.container.resolve(WriteBehindBuffer),
            metadata_manager=self.container.resolve(MetadataManager),
            command_executor=self.container.resolve(CommandExecutor),
            gateway=self,
            cleanup_task=self.cleanup_task
        )
        
        logger.info("XAgent Gateway initialized successfully")
    
    async def _initialize_cleanup_task(self) -> None:
        """初始化数据清理任务"""
        config = self.config_manager.config
        
        if config.storage.retention_days > 0:
            from .storage import SQLiteStorage
            storage = self.container.resolve(SQLiteStorage)
            
            self.cleanup_task = DataCleanupTask(
                storage=storage,
                retention_days=config.storage.retention_days,
                cleanup_batch_size=config.storage.cleanup_batch_size
            )
            self.container.register_instance(DataCleanupTask, self.cleanup_task)
            
            logger.info(
                f"Data cleanup task initialized: retention_days={config.storage.retention_days}"
            )
    
    async def _initialize_rule_engine(self) -> None:
        """初始化规则引擎"""
        from .rule_engine.orchestrator import RuleEngineOrchestrator
        from .rule_engine.persistence import RulePersistenceManager
        from .api.routers.rules import set_rule_engine
        from .core.event_bus import EventBus
        
        event_bus = self.container.try_resolve(EventBus)
        
        base_path = Path(__file__).parent.parent / "plugins"
        plugin_dirs = [
            str(base_path / "rule"),
            str(base_path / "filter"),
            str(base_path / "delivery"),
        ]
        
        config = self.config_manager.config
        db_path = config.storage.database if hasattr(config.storage, 'database') else "./data/xagent.db"
        
        persistence_manager = RulePersistenceManager(db_path=db_path)
        await persistence_manager.initialize()
        
        self.rule_engine = RuleEngineOrchestrator(
            event_bus=event_bus,
            plugin_dirs=plugin_dirs,
            persistence_manager=persistence_manager,
        )
        
        self.container.register_instance(RuleEngineOrchestrator, self.rule_engine)
        self.container.register_instance(RulePersistenceManager, persistence_manager)
        
        set_rule_engine(self.rule_engine)
        
        logger.info("Rule Engine initialized with persistence")
    
    async def start(self) -> None:
        """启动网关
        
        使用插件编排服务启动所有插件。
        这是完整启动方法，兼容旧代码。
        """
        await self.start_core()
        await self.start_plugins()
    
    async def start_core(self) -> None:
        """启动核心服务（不含插件）
        
        先启动核心服务，让API等服务就绪，
        插件将在后台异步启动。
        """
        if self._core_started:
            return
        
        if not self._initializer:
            await self.initialize()
        
        logger.info("Starting XAgent Gateway core services...")
        
        # 启动清理任务
        if self.cleanup_task:
            await self._start_cleanup_task()
        
        # 启动配置监控
        await self._start_config_watcher()
        
        # 启动规则引擎
        if self.rule_engine:
            await self.rule_engine.start()
            logger.info("Rule Engine started")
        
        self._core_started = True
        logger.info("XAgent Gateway core services started")
    
    async def start_plugins(self) -> None:
        """启动插件
        
        从设备文件加载设备并启动插件实例。
        可以在核心服务启动后异步调用。
        """
        if self._plugins_started:
            return
        
        if not self._core_started:
            await self.start_core()
        
        await asyncio.sleep(0)
        
        logger.info("Starting XAgent Gateway plugins...")
        
        config = self.config_manager.config.plugins
        self._orchestrator.clear_results()
        
        try:
            self._device_loader = DeviceLoader(
                config_manager=self.config_manager,
                metadata_manager=self.metadata_manager,
                plugin_loader=self.plugin_loader,
                orchestrator=self._orchestrator
            )
            
            await self._device_loader.load_all_devices()
            
            await self._orchestrator.start_plugins_with_strategy(
                PluginType.SOUTH,
                config.failure_strategy
            )
            
            await self._orchestrator.start_plugins_with_strategy(
                PluginType.NORTH,
                config.failure_strategy
            )
            
            if not config.allow_partial_startup:
                failed_plugins = [
                    r for r in self._orchestrator.get_startup_results() 
                    if not r.success
                ]
                if failed_plugins:
                    raise RuntimeError(
                        f"Partial startup not allowed, but the following plugins failed: "
                        f"{[p.name for p in failed_plugins]}"
                    )
            
            self._orchestrator.report_startup_status()
            
            self._plugins_started = True
            self._running = True
            logger.info("XAgent Gateway plugins started")
            
        except Exception as e:
            logger.error(f"Plugin startup failed: {e}")
            await self._orchestrator.rollback_startup()
            raise
    
    def get_plugin_startup_status(self) -> Dict[str, Any]:
        """获取插件启动状态
        
        Returns:
            包含启动状态的字典
        """
        if not self._orchestrator:
            return {
                "core_started": self._core_started,
                "plugins_started": False,
                "total_plugins": 0,
                "load_success": 0,
                "start_success": 0,
                "failed": []
            }
        
        results = self._orchestrator.get_startup_results()
        
        return {
            "core_started": self._core_started,
            "plugins_started": self._plugins_started,
            "total_plugins": len(set(r.plugin_id for r in results if r.plugin_id) or 
                                set(r.name for r in results)),
            "load_success": sum(1 for r in results if r.stage == "load" and r.success),
            "start_success": sum(1 for r in results if r.stage == "start" and r.success),
            "failed": [
                {"name": r.name, "stage": r.stage, "error": r.error_message}
                for r in results if not r.success
            ]
        }
    
    async def _start_cleanup_task(self) -> None:
        """启动清理任务"""
        scheduler = self.container.resolve(Scheduler)
        
        self._cleanup_scheduler_task_id = scheduler.add_task(
            name="data_cleanup",
            callback=self.cleanup_task.execute,
            task_type=TaskType.MAINTENANCE,
            interval=self.config_manager.config.storage.cleanup_interval,
            initial_delay=60
        )
        await scheduler.start_task(self._cleanup_scheduler_task_id)
        
        logger.info(f"Data cleanup scheduler task started: {self._cleanup_scheduler_task_id}")
    
    async def _start_config_watcher(self) -> None:
        """启动配置文件监控任务"""
        scheduler = self.container.resolve(Scheduler)
        
        interval = self.DEFAULT_CONFIG_CHECK_INTERVAL
        
        self._config_watcher_task_id = scheduler.add_task(
            name="config_watcher",
            callback=self._check_config_changes,
            task_type=TaskType.MAINTENANCE,
            interval=interval,
            initial_delay=10
        )
        await scheduler.start_task(self._config_watcher_task_id)
        
        logger.info(f"Config watcher task started (interval: {interval}s)")
    
    async def _check_config_changes(self) -> None:
        """检查配置文件变更"""
        if self.config_manager:
            try:
                self.config_manager.reload()
            except Exception as e:
                logger.error(f"Error checking config changes: {e}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态
        
        Returns:
            系统健康状态字典
        """
        if not self._health_monitor:
            return {"status": "not_initialized"}
        
        return self._health_monitor.get_system_health()
    
    async def stop(self) -> None:
        """停止网关"""
        if not self._core_started and not self._plugins_started:
            return
        
        logger.info("Stopping XAgent Gateway...")
        self._running = False
        self._plugins_started = False
        self._core_started = False
        
        # 停止规则引擎
        if self.rule_engine:
            try:
                await self.rule_engine.stop()
                logger.info("Rule Engine stopped")
            except Exception as e:
                logger.error(f"Error stopping rule engine: {e}")
        
        # 关闭持久化管理器
        from .rule_engine.persistence import RulePersistenceManager
        persistence_manager = self.container.try_resolve(RulePersistenceManager)
        if persistence_manager:
            try:
                await persistence_manager.close()
                logger.info("Rule Persistence Manager closed")
            except Exception as e:
                logger.error(f"Error closing persistence manager: {e}")
        
        # 停止配置监控
        if self._config_watcher_task_id:
            scheduler = self.container.try_resolve(Scheduler)
            if scheduler:
                try:
                    await scheduler.stop_task(self._config_watcher_task_id)
                    logger.info("Config watcher task stopped")
                except Exception as e:
                    logger.error(f"Error stopping config watcher task: {e}")
        
        # 停止清理任务
        if self._cleanup_scheduler_task_id:
            scheduler = self.container.try_resolve(Scheduler)
            if scheduler:
                try:
                    await scheduler.stop_task(self._cleanup_scheduler_task_id)
                    logger.info("Data cleanup scheduler task stopped")
                except Exception as e:
                    logger.error(f"Error stopping cleanup task: {e}")
        
        # 停止健康监控
        if self._health_monitor:
            try:
                await self._health_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping health monitor: {e}")
        
        # 停止初始化服务（会关闭所有组件）
        if self._initializer:
            try:
                await self._initializer.stop()
            except Exception as e:
                logger.error(f"Error stopping initializer: {e}")
        
        logger.info("XAgent Gateway stopped")
