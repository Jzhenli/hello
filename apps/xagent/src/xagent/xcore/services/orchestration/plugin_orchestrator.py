"""插件编排服务

负责插件的策略化加载、启动和管理。
"""

import logging
from typing import List, Set, Optional

from ...core.plugin_loader import PluginLoader, PluginType
from ...core.config import (
    ConfigManager, 
    PluginInstanceConfig,
    PluginFailureStrategy,
    PluginImportance
)
from ...core.exceptions import PluginLoadError, PluginStartError, PluginDependencyError
from ...domain.models import PluginStartupResult

logger = logging.getLogger(__name__)


class PluginOrchestrator:
    """插件编排服务
    
    负责根据配置策略编排插件的加载和启动过程。
    支持依赖管理、失败策略和回滚机制。
    """
    
    def __init__(
        self,
        plugin_loader: PluginLoader,
        config_manager: ConfigManager
    ):
        """初始化插件编排服务
        
        Args:
            plugin_loader: 插件加载器
            config_manager: 配置管理器
        """
        self.plugin_loader = plugin_loader
        self.config_manager = config_manager
        self._startup_results: List[PluginStartupResult] = []
        self._started_plugin_ids: Set[str] = set()
    
    async def load_plugins_with_strategy(
        self,
        plugin_configs: List[PluginInstanceConfig],
        plugin_type: str,
        global_strategy: PluginFailureStrategy
    ) -> None:
        """根据策略加载插件
        
        [DEPRECATED] 此方法已废弃，请使用 DeviceLoader 从设备文件加载设备。
        设备配置现在应该放在 config/devices/ 目录中。
        
        Args:
            plugin_configs: 插件配置列表
            plugin_type: 插件类型
            global_strategy: 全局失败策略
            
        Raises:
            PluginLoadError: 如果关键插件加载失败且策略为FAIL_FAST
        """
        import warnings
        warnings.warn(
            "load_plugins_with_strategy() is deprecated. Use DeviceLoader to load devices from config/devices/",
            DeprecationWarning,
            stacklevel=2
        )
        
        logger.warning("load_plugins_with_strategy() is deprecated. Devices should be loaded from config/devices/")
        for plugin_config in plugin_configs:
            if not plugin_config.enabled:
                continue
            
            if not await self._check_dependencies(plugin_config):
                result = PluginStartupResult(
                    name=plugin_config.name,
                    plugin_type=plugin_type,
                    success=False,
                    error_message="Dependencies not satisfied",
                    stage="load"
                )
                self._startup_results.append(result)
                
                strategy = plugin_config.failure_strategy or global_strategy
                if strategy == PluginFailureStrategy.FAIL_FAST:
                    raise PluginDependencyError(
                        plugin_config.name,
                        "dependencies",
                        "Dependencies not satisfied"
                    )
                continue
            
            try:
                plugin_info = await self.plugin_loader.load_plugin(
                    plugin_type,
                    plugin_config.name,
                    plugin_config.config
                )
                
                if plugin_info:
                    self._startup_results.append(PluginStartupResult(
                        name=plugin_config.name,
                        plugin_type=plugin_type,
                        success=True,
                        stage="load",
                        plugin_id=plugin_info.plugin_id
                    ))
                else:
                    raise PluginLoadError(plugin_config.name, "Plugin load returned None")
                
            except Exception as e:
                result = PluginStartupResult(
                    name=plugin_config.name,
                    plugin_type=plugin_type,
                    success=False,
                    error_message=str(e),
                    stage="load"
                )
                self._startup_results.append(result)
                
                strategy = plugin_config.failure_strategy or global_strategy
                if strategy == PluginFailureStrategy.FAIL_FAST or \
                   plugin_config.importance == PluginImportance.CRITICAL:
                    raise PluginLoadError(plugin_config.name, str(e))
                
                logger.warning(
                    f"Plugin {plugin_config.name} failed to load, but continuing startup per strategy: {e}"
                )
    
    async def start_plugins_with_strategy(
        self,
        plugin_type: PluginType,
        global_strategy: PluginFailureStrategy
    ) -> None:
        """根据策略启动插件
        
        Args:
            plugin_type: 插件类型
            global_strategy: 全局失败策略
            
        Raises:
            PluginStartError: 如果关键插件启动失败且策略为FAIL_FAST
        """
        plugins = self.plugin_loader.get_plugins_by_type(plugin_type)
        
        for plugin_info in plugins:
            try:
                success = await self.plugin_loader.start_plugin(
                    plugin_info.plugin_id
                )
                
                if success:
                    self._started_plugin_ids.add(plugin_info.plugin_id)
                    self._startup_results.append(PluginStartupResult(
                        name=plugin_info.name,
                        plugin_type=plugin_type.value,
                        success=True,
                        stage="start",
                        plugin_id=plugin_info.plugin_id
                    ))
                else:
                    config = self._get_plugin_config(plugin_info.name)
                    strategy = config.failure_strategy if config else global_strategy
                    
                    result = PluginStartupResult(
                        name=plugin_info.name,
                        plugin_type=plugin_type.value,
                        success=False,
                        error_message="Start returned failure",
                        stage="start",
                        plugin_id=plugin_info.plugin_id
                    )
                    self._startup_results.append(result)
                    
                    if strategy == PluginFailureStrategy.FAIL_FAST or \
                       (config and config.importance == PluginImportance.CRITICAL):
                        raise PluginStartError(plugin_info.name, "Start returned failure")
                
            except Exception as e:
                result = PluginStartupResult(
                    name=plugin_info.name,
                    plugin_type=plugin_type.value,
                    success=False,
                    error_message=str(e),
                    stage="start",
                    plugin_id=plugin_info.plugin_id
                )
                self._startup_results.append(result)
                
                config = self._get_plugin_config(plugin_info.name)
                strategy = config.failure_strategy if config else global_strategy
                
                if strategy == PluginFailureStrategy.FAIL_FAST or \
                   (config and config.importance == PluginImportance.CRITICAL):
                    raise
    
    async def _check_dependencies(
        self,
        plugin_config: PluginInstanceConfig
    ) -> bool:
        """检查插件依赖是否满足
        
        Args:
            plugin_config: 插件配置
            
        Returns:
            如果依赖满足返回True
        """
        for dep_name in plugin_config.depends_on:
            dep_result = next(
                (r for r in self._startup_results 
                 if r.name == dep_name and r.success),
                None
            )
            if not dep_result:
                return False
        return True
    
    def _get_plugin_config(
        self,
        plugin_name: str
    ) -> Optional[PluginInstanceConfig]:
        """获取插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件配置，如果不存在返回None
        """
        config = self.config_manager.config.plugins
        for plugin_list in [config.south, config.north, config.filter]:
            for plugin_config in plugin_list:
                if plugin_config.name == plugin_name:
                    return plugin_config
        return None
    
    def get_startup_results(self) -> List[PluginStartupResult]:
        """获取启动结果列表
        
        Returns:
            启动结果列表
        """
        return self._startup_results.copy()
    
    def get_started_plugin_ids(self) -> Set[str]:
        """获取已启动的插件ID集合
        
        Returns:
            已启动的插件ID集合
        """
        return self._started_plugin_ids.copy()
    
    def report_startup_status(self) -> None:
        """生成启动状态报告"""
        # 统计插件实例数量（使用plugin_id去重）
        plugin_ids = set(r.plugin_id for r in self._startup_results if r.plugin_id)
        total_plugins = len(plugin_ids)
        
        # 如果没有plugin_id，则使用name统计（向后兼容）
        if total_plugins == 0:
            plugin_names = set(r.name for r in self._startup_results)
            total_plugins = len(plugin_names)
        
        # 统计各阶段结果
        load_results = [r for r in self._startup_results if r.stage == "load"]
        start_results = [r for r in self._startup_results if r.stage == "start"]
        
        load_success = sum(1 for r in load_results if r.success)
        start_success = sum(1 for r in start_results if r.success)
        
        logger.info("=" * 60)
        logger.info("Plugin Startup Status Report")
        logger.info("=" * 60)
        logger.info(f"Total Plugins: {total_plugins}")
        logger.info(f"Load Stage: Success {load_success}/{len(load_results)}")
        logger.info(f"Start Stage: Success {start_success}/{len(start_results)}")
        
        # 显示失败的插件
        failed_results = [r for r in self._startup_results if not r.success]
        if failed_results:
            logger.warning("Failed operations:")
            for result in failed_results:
                logger.warning(
                    f"  - {result.name} ({result.plugin_type}/{result.stage}): "
                    f"{result.error_message}"
                )
        
        logger.info("=" * 60)
    
    async def rollback_startup(self) -> None:
        """回滚已启动的插件"""
        logger.info("Starting rollback of started plugins...")
        
        for plugin_id in self._started_plugin_ids:
            try:
                await self.plugin_loader.stop_plugin(plugin_id)
                logger.info(f"Plugin stopped: {plugin_id}")
            except Exception as e:
                logger.error(f"Failed to stop plugin {plugin_id}: {e}")
        
        self._started_plugin_ids.clear()
        logger.info("Rollback completed")
    
    def clear_results(self) -> None:
        """清空启动结果"""
        self._startup_results.clear()
        self._started_plugin_ids.clear()
