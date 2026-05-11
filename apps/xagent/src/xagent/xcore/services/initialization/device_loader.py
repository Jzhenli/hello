"""设备加载服务

负责在启动时从设备文件加载设备并启动插件实例。
"""

import logging
import time
from typing import List, Optional, Set, TYPE_CHECKING

from ...api.services.device_service import DeviceService
from ...core.plugin_loader import PluginType
from ...domain.models import PluginStartupResult
from ...core.exceptions import PluginLoadError

if TYPE_CHECKING:
    from ...core.config import ConfigManager
    from ...core.metadata import MetadataManager
    from ...core.plugin_loader import PluginLoader
    from ...services.orchestration.plugin_orchestrator import PluginOrchestrator
    from ...api.models.device import DeviceConfig

logger = logging.getLogger(__name__)


class DeviceLoader:
    """设备加载服务
    
    在系统启动时从设备文件加载设备并启动插件实例。
    确保设备文件、数据库和插件实例之间的数据一致性。
    
    数据同步策略：
    1. 设备文件是唯一数据源
    2. 数据库作为索引和状态追踪
    3. 启动时清理孤立记录，同步文件到数据库
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
        self.device_service: Optional[DeviceService] = None
    
    async def load_all_devices(self) -> None:
        """加载所有设备
        
        扫描设备目录，加载设备配置并启动插件实例。
        执行数据同步检查，确保文件、数据库和插件实例一致。
        """
        self.device_service = DeviceService(
            config_dir=self.config_manager.paths.config_dir,
            metadata_manager=self.metadata_manager,
            plugin_loader=self.plugin_loader
        )
        
        logger.info("Loading devices from config/devices/")
        
        devices = await self.device_service.list_devices(enabled=True)
        
        if not devices:
            logger.info("No devices found in config/devices/")
            await self._cleanup_orphaned_records(set())
            return
        
        logger.info(f"Found {len(devices)} enabled devices")
        
        file_assets = {d.asset for d in devices}
        
        await self._cleanup_orphaned_records(file_assets)
        
        await self._sync_devices_to_metadata(devices)
        
        south_devices = [
            d for d in devices 
            if self._get_plugin_type(d.plugin.name) == PluginType.SOUTH
        ]
        north_devices = [
            d for d in devices 
            if self._get_plugin_type(d.plugin.name) == PluginType.NORTH
        ]
        
        logger.info(f"Loading {len(south_devices)} south devices and {len(north_devices)} north devices")
        
        for device in south_devices:
            await self._load_device(device, PluginType.SOUTH)
        
        for device in north_devices:
            await self._load_device(device, PluginType.NORTH)
    
    async def _cleanup_orphaned_records(self, file_assets: Set[str]) -> None:
        """清理数据库中的孤立记录
        
        删除数据库中存在但文件中不存在的设备记录。
        
        Args:
            file_assets: 文件中存在的设备资产标识集合
        """
        try:
            db_devices = await self.metadata_manager.get_all_active_devices()
            db_assets = {d.asset for d in db_devices}
            
            orphaned_assets = db_assets - file_assets
            
            if orphaned_assets:
                logger.warning(f"Found {len(orphaned_assets)} orphaned devices in database: {orphaned_assets}")
                
                for asset in orphaned_assets:
                    try:
                        await self.metadata_manager._soft_delete_device(asset, time.time())
                        logger.info(f"Cleaned up orphaned device: {asset}")
                    except Exception as e:
                        logger.error(f"Failed to cleanup orphaned device {asset}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during orphaned records cleanup: {e}")
    
    async def _sync_devices_to_metadata(self, devices: List['DeviceConfig']) -> None:
        """同步设备到元数据库
        
        确保数据库中的设备记录与文件一致。
        
        Args:
            devices: 设备配置列表
        """
        logger.debug("Syncing devices to metadata database...")
        
        for device in devices:
            try:
                await self.device_service._sync_device_to_db(device)
                logger.debug(f"Device '{device.asset}' synced to database")
            except Exception as e:
                logger.error(f"Failed to sync device '{device.asset}' to database: {e}")
    
    async def _load_device(
        self, 
        device: 'DeviceConfig', 
        plugin_type: PluginType
    ) -> None:
        """加载单个设备
        
        加载设备配置并创建插件实例。
        
        Args:
            device: 设备配置
            plugin_type: 插件类型
        """
        try:
            plugin_config = await self.device_service._merge_plugin_config(device)
            
            plugin_info = await self.plugin_loader.load_plugin(
                plugin_type,
                device.plugin.name,
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
                logger.info(f"Device '{device.asset}' loaded (plugin: {device.plugin.name}, id: {plugin_info.plugin_id})")
            else:
                raise PluginLoadError(device.asset, "Plugin load returned None")
                
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
        
        用于设备文件修改后重新加载。
        
        Args:
            asset: 设备资产标识
            
        Returns:
            是否成功
        """
        if not self.device_service:
            self.device_service = DeviceService(
                config_dir=self.config_manager.paths.config_dir,
                metadata_manager=self.metadata_manager,
                plugin_loader=self.plugin_loader
            )
        
        try:
            device = await self.device_service.get_device(asset)
            
            if not device:
                logger.warning(f"Device '{asset}' not found, cannot reload")
                return False
            
            await self.device_service._sync_device_to_db(device)
            
            await self.device_service._reload_device_plugin(device)
            
            logger.info(f"Device '{asset}' reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload device '{asset}': {e}")
            return False
    
    async def unload_device(self, asset: str) -> bool:
        """卸载设备
        
        用于设备文件删除后卸载插件实例。
        
        Args:
            asset: 设备资产标识
            
        Returns:
            是否成功
        """
        if not self.device_service:
            self.device_service = DeviceService(
                config_dir=self.config_manager.paths.config_dir,
                metadata_manager=self.metadata_manager,
                plugin_loader=self.plugin_loader
            )
        
        try:
            await self.device_service._unload_device_plugin(asset)
            
            await self.metadata_manager._soft_delete_device(asset, time.time())
            
            logger.info(f"Device '{asset}' unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload device '{asset}': {e}")
            return False
