"""设备和服务加载服务（数据库为中心）

负责在启动时从数据库加载设备和服务并启动插件实例。
数据库是唯一数据源。
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from ...config.config_repository import ConfigRepository, ServiceRepository, ServiceConfig
from ...core.plugin_loader import PluginType
from ...domain.models import PluginStartupResult

if TYPE_CHECKING:
    from ...core.config import ConfigManager
    from ...core.metadata import MetadataManager
    from ...core.plugin_loader import PluginLoader
    from ...services.orchestration.plugin_orchestrator import PluginOrchestrator

logger = logging.getLogger(__name__)


class DeviceLoader:
    """设备和服务加载服务（数据库为中心）
    
    在系统启动时从数据库加载设备和服务并启动插件实例。
    数据库是唯一数据源。
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
        self.service_repo: Optional[ServiceRepository] = None
    
    async def load_all_devices(self) -> None:
        """加载所有设备和服务
        
        从数据库加载所有启用的设备和服务并启动插件实例。
        """
        logger.info("Loading devices and services from database...")
        
        self.config_repo = ConfigRepository(self.metadata_manager.db)
        self.service_repo = ServiceRepository(self.metadata_manager.db)
        
        await self._load_south_devices()
        
        await self._load_north_services()
    
    async def _load_south_devices(self) -> None:
        """加载南向设备"""
        devices = await self.config_repo.list_devices(enabled=True)
        
        if not devices:
            logger.info("No enabled devices found in database")
            self._check_legacy_yaml_devices()
            return
        
        south_devices = [
            d for d in devices 
            if self._get_plugin_type(d.plugin_name) == PluginType.SOUTH
        ]
        
        logger.info(f"Found {len(south_devices)} enabled south devices in database")
        
        for device in south_devices:
            await self._load_device(device, PluginType.SOUTH)
    
    async def _load_north_services(self) -> None:
        """加载北向服务"""
        services = await self.service_repo.list_services(enabled=True)
        
        if not services:
            logger.info("No enabled north services found in database")
            return
        
        logger.info(f"Found {len(services)} enabled north services in database")
        
        for service in services:
            await self._load_service(service)
    
    def _check_legacy_yaml_devices(self) -> None:
        """检测用户配置目录下是否残留 YAML 设备文件
        
        如果发现残留的 YAML 设备文件，输出警告日志引导用户
        通过 API 或 import_from_yaml 方法导入设备配置。
        """
        try:
            devices_dir = self.config_manager.paths.config_dir / 'devices'
            if not devices_dir.exists():
                return
            
            yaml_files = [
                f for f in devices_dir.glob("*.yaml")
                if not any(kw in f.stem.lower() for kw in ['example', 'template', 'sample', 'demo'])
            ]
            if yaml_files:
                logger.warning(
                    f"Found {len(yaml_files)} legacy YAML device config(s) in {devices_dir}. "
                    "YAML device configs are no longer auto-migrated. "
                    "Use the API (POST /api/devices/import) or import_from_yaml() to import them."
                )
        except Exception:
            pass

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
    
    async def _load_service(self, service: ServiceConfig) -> None:
        """加载单个北向服务
        
        加载服务配置并创建插件实例。
        
        Args:
            service: 服务配置
        """
        try:
            # 构建嵌套结构传递给插件
            plugin_config = {
                'channel_id': service.name,
                'connection': service.connection_config,
                'adapter': service.adapter_config,
                'upload_strategy': service.upload_config,
            }
            
            logger.debug(f"Loading service '{service.name}' with nested config: {plugin_config}")
            
            plugin_info = await self.plugin_loader.load_plugin(
                PluginType.NORTH,
                service.protocol,
                plugin_config
            )
            
            if plugin_info:
                self.orchestrator._startup_results.append(PluginStartupResult(
                    name=service.name,
                    plugin_type=PluginType.NORTH.value,
                    success=True,
                    stage="load",
                    plugin_id=plugin_info.plugin_id
                ))
                
                await self.service_repo.update_status(service.name, "online")
                
                logger.info(f"Service '{service.name}' loaded (protocol: {service.protocol}, id: {plugin_info.plugin_id})")
            else:
                raise RuntimeError(f"Plugin load returned None for service {service.name}")
                
        except Exception as e:
            logger.error(f"Failed to load service '{service.name}': {e}")
            
            if self.service_repo:
                await self.service_repo.update_status(service.name, "error")
            
            self.orchestrator._startup_results.append(PluginStartupResult(
                name=service.name,
                plugin_type=PluginType.NORTH.value,
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
            self.config_repo = ConfigRepository(self.metadata_manager.db)
        
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
    
    async def reload_service(self, name: str) -> bool:
        """重新加载单个北向服务
        
        用于服务配置变更后重新加载。
        
        Args:
            name: 服务名称
            
        Returns:
            是否成功
        """
        if not self.service_repo:
            self.service_repo = ServiceRepository(self.metadata_manager.db)
        
        try:
            service = await self.service_repo.get_service(name)
            
            if not service:
                logger.warning(f"Service '{name}' not found, cannot reload")
                return False
            
            await self._unload_service_plugin(name)
            
            await self._load_service(service)
            
            logger.info(f"Service '{name}' reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload service '{name}': {e}")
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
    
    async def unload_service(self, name: str) -> bool:
        """卸载北向服务
        
        用于服务删除后卸载插件实例。
        
        Args:
            name: 服务名称
            
        Returns:
            是否成功
        """
        try:
            await self._unload_service_plugin(name)
            
            logger.info(f"Service '{name}' unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload service '{name}': {e}")
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
    
    async def _unload_service_plugin(self, name: str) -> None:
        """卸载服务插件实例"""
        plugins = self.plugin_loader.get_all_plugins()
        
        for plugin in plugins:
            if plugin.config.get('channel_id') == name:
                await self.plugin_loader.stop_plugin(plugin.plugin_id)
                await self.plugin_loader.unload_plugin(plugin.plugin_id)
                
                if self.service_repo:
                    await self.service_repo.update_status(name, "offline")
                
                logger.info(f"Plugin unloaded for service {name}")
                break
