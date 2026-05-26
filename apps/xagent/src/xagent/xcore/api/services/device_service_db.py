"""设备管理服务（数据库为中心版本）

此服务使用数据库作为唯一数据源，YAML文件仅用于导入导出。
"""

import logging
import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
from datetime import datetime

from ..models.device import (
    DeviceConfig,
    PointConfig,
    DeviceStatus,
    StandardDataType
)
from ...core.metadata import MetadataManager
from ...config.config_repository import ConfigRepository as DbConfigRepository
from ...services.config_service import ConfigService
from ...services.audit_service import AuditService

logger = logging.getLogger(__name__)


class DeviceService:
    """设备管理服务（数据库为中心）"""
    
    def __init__(
        self,
        metadata_manager: MetadataManager,
        plugin_loader: Any
    ):
        self.metadata_manager = metadata_manager
        self.plugin_loader = plugin_loader
        self._lock: Optional[asyncio.Lock] = None
        
        self._config_repo = DbConfigRepository(metadata_manager.db)
        self._audit_service = AuditService(metadata_manager.db)
        self._config_service: Optional[ConfigService] = None
    
    def _get_config_service(self) -> ConfigService:
        """获取配置服务（延迟初始化）"""
        if self._config_service is None:
            self._config_service = ConfigService(
                self._config_repo,
                self._audit_service,
                self.plugin_loader
            )
        return self._config_service
    
    async def _get_lock(self) -> asyncio.Lock:
        """获取异步锁（延迟初始化）"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def create_device(self, device: DeviceConfig) -> DeviceConfig:
        """创建设备
        
        Args:
            device: 设备配置
            
        Returns:
            创建的设备配置
            
        Raises:
            ValueError: 如果设备已存在或插件不可用
        """
        config_service = self._get_config_service()
        
        db_device = self._convert_api_device_to_db_device(device)
        
        plugin_name = device.plugin.name if device.plugin else ""
        if plugin_name:
            db_device.plugin_config = await self.merge_plugin_config(
                plugin_name, db_device.plugin_config
            )
        
        await config_service.create_device(db_device, user="api")
        
        logger.info(f"Device {device.asset} created successfully")
        return await self.get_device(device.asset)
    
    async def get_device(self, asset: str) -> Optional[DeviceConfig]:
        """获取设备配置
        
        Args:
            asset: 设备资产标识
            
        Returns:
            设备配置，如果不存在返回None
        """
        db_device = await self._config_repo.get_device(asset)
        
        if not db_device:
            return None
        
        return self._convert_db_device_to_api_device(db_device)
    
    async def list_devices(
        self,
        status: Optional[DeviceStatus] = None,
        plugin_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled: Optional[bool] = None
    ) -> List[DeviceConfig]:
        """列出设备
        
        Args:
            status: 按状态过滤
            plugin_name: 按插件名称过滤
            tags: 按标签过滤
            enabled: 按启用状态过滤
            
        Returns:
            设备列表
        """
        db_devices = await self._config_repo.list_devices(
            status=status.value if status else None,
            enabled=enabled,
            plugin_name=plugin_name
        )
        
        devices = []
        for db_device in db_devices:
            device = self._convert_db_device_to_api_device(db_device)
            
            if tags and not any(tag in device.tags for tag in tags):
                continue
            
            devices.append(device)
        
        return devices
    
    async def update_device(
        self,
        asset: str,
        updates: Dict[str, Any]
    ) -> DeviceConfig:
        """更新设备
        
        Args:
            asset: 设备资产标识
            updates: 更新内容
            
        Returns:
            更新后的设备配置
        """
        config_service = self._get_config_service()
        
        db_updates = self._convert_api_updates_to_db_updates(updates)
        await config_service.update_device(asset, db_updates, user="api")
        
        logger.info(f"Device {asset} updated successfully")
        return await self.get_device(asset)
    
    async def delete_device(self, asset: str) -> None:
        """删除设备
        
        Args:
            asset: 设备资产标识
        """
        config_service = self._get_config_service()
        
        await config_service.delete_device(asset, user="api")
        
        logger.info(f"Device {asset} deleted successfully")
    
    async def add_point(
        self,
        asset: str,
        point: PointConfig
    ) -> DeviceConfig:
        """添加点位
        
        Args:
            asset: 设备资产标识
            point: 点位配置
            
        Returns:
            更新后的设备配置
        """
        config_service = self._get_config_service()
        
        point_dict = point.model_dump()
        await config_service.add_point(asset, point_dict, user="api")
        
        return await self.get_device(asset)
    
    async def update_point(
        self,
        asset: str,
        point_name: str,
        updates: Dict[str, Any]
    ) -> DeviceConfig:
        """更新点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            updates: 更新内容
            
        Returns:
            更新后的设备配置
        """
        config_service = self._get_config_service()
        
        await config_service.update_point(asset, point_name, updates, user="api")
        
        return await self.get_device(asset)
    
    async def delete_point(
        self,
        asset: str,
        point_name: str
    ) -> DeviceConfig:
        """删除点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            
        Returns:
            更新后的设备配置
        """
        config_service = self._get_config_service()
        
        await config_service.delete_point(asset, point_name, user="api")
        
        return await self.get_device(asset)
    
    async def reload_device(self, asset: str) -> None:
        """重载设备
        
        Args:
            asset: 设备资产标识
        """
        config_service = self._get_config_service()
        
        await config_service.reload_device(asset, user="api")
        
        logger.info(f"Device {asset} reloaded successfully")
    
    async def export_devices(
        self,
        assets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """导出设备配置
        
        Args:
            assets: 要导出的设备列表，None表示导出所有
            
        Returns:
            导出的设备配置
        """
        config_service = self._get_config_service()
        
        return await config_service.export_devices(assets, user="api")
    
    async def import_devices(
        self,
        data: Dict[str, Any],
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """导入设备配置
        
        Args:
            data: 导入的设备配置
            overwrite: 是否覆盖已存在的设备
            
        Returns:
            导入结果
        """
        config_service = self._get_config_service()
        
        return await config_service.import_devices(data, user="api", overwrite=overwrite)

    async def batch_create_devices(
        self,
        devices: List[DeviceConfig]
    ) -> Dict[str, Any]:
        """批量创建设备

        Args:
            devices: 设备配置列表

        Returns:
            批量操作结果
        """
        results = {
            'total': len(devices),
            'succeeded': 0,
            'failed': 0,
            'details': []
        }

        for device in devices:
            try:
                await self.create_device(device)
                results['succeeded'] += 1
                results['details'].append({
                    'asset': device.asset,
                    'action': 'created',
                    'success': True
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'asset': device.asset,
                    'action': 'failed',
                    'success': False,
                    'message': str(e)
                })

        return results

    async def reload_devices(
        self,
        assets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """重载设备插件

        Args:
            assets: 要重载的设备列表，None表示重载所有启用的设备

        Returns:
            重载结果
        """
        if assets is None:
            devices = await self._config_repo.list_devices(enabled=True)
            assets = [d.asset for d in devices]

        results = {
            'total': len(assets),
            'succeeded': 0,
            'failed': 0,
            'details': []
        }

        for asset in assets:
            try:
                await self.reload_device(asset)
                results['succeeded'] += 1
                results['details'].append({
                    'asset': asset,
                    'action': 'reloaded',
                    'success': True
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'asset': asset,
                    'action': 'failed',
                    'success': False,
                    'message': str(e)
                })

        return results

    def _convert_api_device_to_db_device(self, api_device: DeviceConfig):
        """将API设备模型转换为数据库设备配置
        
        Args:
            api_device: API设备配置
            
        Returns:
            数据库设备配置
        """
        from ...config.config_repository import DeviceConfig as DbDeviceConfig
        
        points = []
        for point in api_device.points:
            points.append(point.model_dump())
        
        plugin_config = api_device.plugin.config if api_device.plugin else {}
        
        return DbDeviceConfig(
            asset=api_device.asset,
            name=api_device.name,
            description=api_device.description,
            plugin_name=api_device.plugin.name if api_device.plugin else "",
            plugin_config=plugin_config,
            enabled=api_device.enabled,
            status=api_device.status.value if api_device.status else "active",
            metadata=api_device.metadata or {},
            tags=api_device.tags or [],
            points=points
        )

    async def merge_plugin_config(
        self,
        plugin_name: str,
        device_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """合并插件默认配置与设备配置

        从 plugin_registry 数据库表读取插件默认参数，
        与设备特定配置合并（设备配置优先级更高）。

        Args:
            plugin_name: 插件名称
            device_config: 设备插件配置

        Returns:
            合并后的配置
        """
        plugin_defaults = await self._config_repo.get_plugin_defaults(plugin_name)
        if plugin_defaults:
            merged = {**plugin_defaults, **device_config}
            return merged
        return device_config
    
    def _convert_api_updates_to_db_updates(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """将API更新字段转换为数据库更新字段
        
        Args:
            updates: API格式的更新内容
            
        Returns:
            数据库格式的更新内容
        """
        db_updates = {}
        for key, value in updates.items():
            if key == 'plugin':
                db_updates['plugin_name'] = value.get('name', '') if isinstance(value, dict) else ''
                db_updates['plugin_config'] = value.get('config', {}) if isinstance(value, dict) else {}
            elif key == 'status':
                db_updates['status'] = value.value if hasattr(value, 'value') else str(value)
            else:
                db_updates[key] = value
        return db_updates

    def _convert_db_device_to_api_device(self, db_device) -> DeviceConfig:
        """将数据库设备转换为API设备模型
        
        Args:
            db_device: 数据库设备配置
            
        Returns:
            API设备配置
        """
        from ..models.device import PluginReference
        
        points = []
        for point in db_device.points:
            points.append(PointConfig(
                name=point.get('name'),
                description=point.get('description'),
                data_type=point.get('data_type'),
                standard_data_type=point.get('standard_data_type'),
                unit=point.get('unit'),
                config=point.get('config', {}),
                metadata=point.get('metadata', {}),
                tags=point.get('tags', []),
                enabled=point.get('enabled', True)
            ))
        
        return DeviceConfig(
            asset=db_device.asset,
            name=db_device.name,
            description=db_device.description,
            plugin=PluginReference(
                name=db_device.plugin_name,
                config=db_device.plugin_config
            ),
            enabled=db_device.enabled,
            status=DeviceStatus(db_device.status),
            metadata=db_device.metadata,
            tags=db_device.tags,
            points=points,
            created_at=datetime.fromtimestamp(db_device.created_at) if db_device.created_at else None,
            updated_at=datetime.fromtimestamp(db_device.updated_at) if db_device.updated_at else None
        )
    
    def get_devices_connection_status(self) -> Dict[str, str]:
        """获取所有设备的运行时连接状态
        
        从插件注册表中获取所有南向插件实例，调用其 get_device_status() 方法。
        
        Returns:
            设备资产标识到连接状态的映射 {"asset": "online"|"offline"}
        """
        from ...core.plugin import PluginType
        
        connection_status: Dict[str, str] = {}
        
        if not self.plugin_loader or not hasattr(self.plugin_loader, 'registry'):
            return connection_status
        
        south_plugins = self.plugin_loader.registry.get_plugins_by_type(PluginType.SOUTH)
        
        for plugin_info in south_plugins:
            asset = plugin_info.config.get('asset_name', plugin_info.name)
            
            if plugin_info.instance and hasattr(plugin_info.instance, 'get_device_status'):
                try:
                    status = plugin_info.instance.get_device_status()
                    connection_status[asset] = status
                except Exception as e:
                    logger.warning(f"Failed to get device status for {asset}: {e}")
                    connection_status[asset] = "offline"
            else:
                connection_status[asset] = "offline"
        
        return connection_status
