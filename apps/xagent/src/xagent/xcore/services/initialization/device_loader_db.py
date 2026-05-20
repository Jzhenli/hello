"""设备加载服务（数据库为中心）

负责在启动时从数据库加载设备并启动插件实例。
数据库是唯一数据源，YAML文件仅用于导入导出。
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from ...config.config_repository import ConfigRepository
from ...core.plugin_loader import PluginType
from ...domain.models import PluginStartupResult

if TYPE_CHECKING:
    from ...core.config import ConfigManager
    from ...core.metadata import MetadataManager
    from ...core.plugin_loader import PluginLoader
    from ...services.orchestration.plugin_orchestrator import PluginOrchestrator

logger = logging.getLogger(__name__)


class DeviceLoader:
    """设备加载服务（数据库为中心）
    
    在系统启动时从数据库加载设备并启动插件实例。
    数据库是唯一数据源，YAML文件仅用于导入导出。
    """
    
    SOUTH_PLUGINS = {
        'modbus_tcp', 'modbus_rtu', 'bacnet', 'knx', 'opcua', 
        'demo_sensor', 'simulator', 'virtual_device'
    }
    NORTH_PLUGINS = {
        'mqtt_client', 'influxdb', 'timescaledb', 
        'xnc_client', 'kafka', 'redis'
    }
    
    def __init__(
        self,
        config_manager: 'ConfigManager',
        metadata_manager: 'MetadataManager',
        plugin_loader: 'PluginLoader',
        orchestrator: 'PluginOrchestrator'
    ):
        """初始化设备加载服务
        
        Args:
            config_manager: 配置管理器
            metadata_manager: 元数据管理器
            plugin_loader: 插件加载器
            orchestrator: 插件编排服务
        """
        self.config_manager = config_manager
        self.metadata_manager = metadata_manager
        self.plugin_loader = plugin_loader
        self.orchestrator = orchestrator
        self.config_repo: Optional[ConfigRepository] = None
    
    async def load_all_devices(self) -> None:
        """加载所有设备
        
        从数据库加载所有启用的设备并启动插件实例。
        如果数据库中没有设备，尝试从YAML文件迁移。
        """
        logger.info("Loading devices from database...")
        
        self.config_repo = ConfigRepository(self.metadata_manager._db)
        
        devices = await self.config_repo.list_devices(enabled=True)
        
        if not devices:
            logger.info("No enabled devices found in database")
            
            migrated = await self._try_migrate_from_yaml()
            if not migrated:
                logger.info("No devices to load")
                return
            
            devices = await self.config_repo.list_devices(enabled=True)
            if not devices:
                return
        
        logger.info(f"Found {len(devices)} enabled devices in database")
        
        south_devices = [
            d for d in devices 
            if self._get_plugin_type(d.plugin_name) == PluginType.SOUTH
        ]
        north_devices = [
            d for d in devices 
            if self._get_plugin_type(d.plugin_name) == PluginType.NORTH
        ]
        
        logger.info(f"Loading {len(south_devices)} south devices and {len(north_devices)} north devices")
        
        for device in south_devices:
            await self._load_device(device, PluginType.SOUTH)
        
        for device in north_devices:
            await self._load_device(device, PluginType.NORTH)
    
    async def _try_migrate_from_yaml(self) -> bool:
        """尝试从YAML文件迁移设备到数据库
        
        注意：默认模板文件（包含example/template）不会被迁移
        
        Returns:
            是否成功迁移了设备
        """
        try:
            devices_dir = self.config_manager.paths.config_dir / 'devices'
            
            if not devices_dir.exists():
                logger.info("No devices directory found")
                return False
            
            yaml_files = list(devices_dir.glob("*.yaml"))
            if not yaml_files:
                logger.info("No YAML device files found")
                return False
            
            non_template_files = [
                f for f in yaml_files
                if not any(keyword in f.stem.lower() for keyword in ['example', 'template', 'sample', 'demo'])
            ]
            
            if not non_template_files:
                logger.info("Only template files found, skipping auto-migration")
                logger.info("Use CLI tool to manually migrate if needed:")
                logger.info("  python -m xagent.tools.migrate_config migrate --devices-dir <path> --database <path>")
                return False
            
            logger.info(f"Found {len(non_template_files)} non-template YAML device files, migrating to database...")
            
            from ...tools.config_migrator import ConfigMigrator
            migrator = ConfigMigrator(self.config_repo)
            
            result = await migrator.migrate_from_yaml(
                devices_dir,
                user="auto_migration",
                skip_existing=True
            )
            
            if result['succeeded'] > 0:
                logger.info(f"Successfully migrated {result['succeeded']} devices from YAML to database")
                return True
            else:
                logger.info("No devices were migrated")
                return False
        
        except Exception as e:
            logger.error(f"Failed to migrate devices from YAML: {e}")
            return False
    
    async def _load_device(
        self, 
        device, 
        plugin_type: PluginType
    ) -> None:
        """加载单个设备
        
        加载设备配置并创建插件实例。
        
        Args:
            device: 设备配置
            plugin_type: 插件类型
        """
        try:
            plugin_config = {
                **device.plugin_config,
                'asset_name': device.asset,
                'points': device.points
            }
            
            plugin_info = await self.plugin_loader.load_plugin(
                plugin_type,
                device.plugin_name,
                plugin_config
            )
            
            if plugin_info:
                self.orchestrator._startup_results.append(PluginStartupResult(
                    name=device.asset,
                    plugin_type=plugin_type.value,
                    success=True,
                    stage="load",
                    plugin_id=plugin_info.plugin_id
                ))
                logger.info(f"Device '{device.asset}' loaded (plugin: {device.plugin_name}, id: {plugin_info.plugin_id})")
            else:
                raise RuntimeError(f"Plugin load returned None for device {device.asset}")
                
        except Exception as e:
            logger.error(f"Failed to load device '{device.asset}': {e}")
            self.orchestrator._startup_results.append(PluginStartupResult(
                name=device.asset,
                plugin_type=plugin_type.value,
                success=False,
                error_message=str(e),
                stage="load"
            ))
    
    def _get_plugin_type(self, plugin_name: str) -> PluginType:
        """判断插件类型
        
        根据插件名称判断插件是南向还是北向。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件类型
        """
        if plugin_name in self.SOUTH_PLUGINS:
            return PluginType.SOUTH
        elif plugin_name in self.NORTH_PLUGINS:
            return PluginType.NORTH
        else:
            plugin_classes = self.plugin_loader.discover_plugins()
            if plugin_name in plugin_classes:
                plugin_class = plugin_classes[plugin_name]
                if hasattr(plugin_class, 'plugin_type'):
                    return plugin_class.plugin_type
            
            logger.warning(f"Unknown plugin type for '{plugin_name}', assuming SOUTH")
            return PluginType.SOUTH
    
    async def reload_device(self, asset: str) -> bool:
        """重新加载单个设备
        
        用于设备配置变更后重新加载。
        
        Args:
            asset: 设备资产标识
            
        Returns:
            是否成功
        """
        if not self.config_repo:
            self.config_repo = ConfigRepository(self.metadata_manager._db)
        
        try:
            device = await self.config_repo.get_device(asset)
            
            if not device:
                logger.warning(f"Device '{asset}' not found, cannot reload")
                return False
            
            await self._unload_device_plugin(asset)
            
            plugin_type = self._get_plugin_type(device.plugin_name)
            await self._load_device(device, plugin_type)
            
            logger.info(f"Device '{asset}' reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload device '{asset}': {e}")
            return False
    
    async def unload_device(self, asset: str) -> bool:
        """卸载设备
        
        用于设备删除后卸载插件实例。
        
        Args:
            asset: 设备资产标识
            
        Returns:
            是否成功
        """
        try:
            await self._unload_device_plugin(asset)
            
            logger.info(f"Device '{asset}' unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload device '{asset}': {e}")
            return False
    
    async def _unload_device_plugin(self, asset: str) -> None:
        """卸载设备插件实例"""
        plugins = self.plugin_loader.get_all_plugins()
        
        for plugin in plugins:
            if plugin.config.get('asset_name') == asset:
                await self.plugin_loader.stop_plugin(plugin.plugin_id)
                await self.plugin_loader.unload_plugin(plugin.plugin_id)
                logger.info(f"Plugin unloaded for device {asset}")
                break
