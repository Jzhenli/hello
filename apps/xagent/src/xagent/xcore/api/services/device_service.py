import logging
import asyncio
import time
import hashlib
import json
import shutil
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
from ...core.metadata import MetadataManager, DeviceRecord, PointRecord, RegistryStatus

logger = logging.getLogger(__name__)


class DeviceService:
    """设备管理服务"""
    
    def __init__(
        self,
        config_dir: Path,
        metadata_manager: MetadataManager,
        plugin_loader: Any
    ):
        self.config_dir = Path(config_dir)
        self.devices_dir = self.config_dir / 'devices'
        self.plugins_dir = self.config_dir / 'plugins'
        self.metadata_manager = metadata_manager
        self.plugin_loader = plugin_loader
        self._lock: Optional[asyncio.Lock] = None
        
        self.devices_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
    
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
        async with await self._get_lock():
            logger.info(f"Creating device: {device.asset}")
            
            if not await self._validate_plugin(device.plugin.name):
                raise ValueError(f"Plugin '{device.plugin.name}' not available")
            
            if await self._device_exists(device.asset):
                raise ValueError(f"Device '{device.asset}' already exists")
            
            device_copy = device.model_copy(deep=True)
            now = datetime.now()
            device_copy.created_at = now
            device_copy.updated_at = now
            
            backup_file = None
            db_synced = False
            plugin_loaded = False
            
            try:
                backup_file = await self._save_device_config_with_backup(device_copy)
                
                await self._sync_device_to_db(device_copy)
                db_synced = True
                
                await self._load_device_plugin(device_copy)
                plugin_loaded = True
                
                logger.info(f"Device {device_copy.asset} created successfully")
                return device_copy
                
            except Exception as e:
                logger.error(f"Failed to create device {device.asset}, rolling back: {e}")
                
                if plugin_loaded:
                    try:
                        await self._unload_device_plugin(device_copy.asset)
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback plugin: {rollback_error}")
                
                if db_synced:
                    try:
                        await self.metadata_manager._soft_delete_device(
                            device_copy.asset,
                            time.time()
                        )
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback database: {rollback_error}")
                
                if backup_file and backup_file.exists():
                    try:
                        backup_file.unlink()
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback config file: {rollback_error}")
                
                raise
    
    async def get_device(self, asset: str) -> Optional[DeviceConfig]:
        """获取设备配置
        
        Args:
            asset: 设备资产标识
            
        Returns:
            设备配置，如果不存在返回 None
            
        Raises:
            ValueError: 如果配置文件格式错误
        """
        device_file = self.devices_dir / f"{asset}.yaml"
        
        if not device_file.exists():
            return None
        
        try:
            with open(device_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                logger.error(f"Empty device config file: {device_file}")
                raise ValueError(f"Empty device configuration for {asset}")
            
            return DeviceConfig(**data)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in device config {asset}: {e}")
            raise ValueError(f"Invalid YAML in device configuration for {asset}")
        except Exception as e:
            logger.error(f"Error loading device {asset}: {e}")
            raise
    
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
        devices = []
        
        for device_file in self.devices_dir.glob("*.yaml"):
            try:
                device = await self.get_device(device_file.stem)
                if device:
                    if status and device.status != status:
                        continue
                    if plugin_name and device.plugin.name != plugin_name:
                        continue
                    if tags and not any(tag in device.tags for tag in tags):
                        continue
                    if enabled is not None and device.enabled != enabled:
                        continue
                    
                    devices.append(device)
            except Exception as e:
                logger.error(f"Error loading device {device_file}: {e}")
        
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
        async with await self._get_lock():
            device = await self.get_device(asset)
            if not device:
                raise ValueError(f"Device '{asset}' not found")
            
            logger.info(f"Updating device: {asset}")
            
            device_copy = device.model_copy(deep=True)
            for key, value in updates.items():
                if key == 'asset':
                    continue
                if hasattr(device_copy, key):
                    setattr(device_copy, key, value)
            
            device_copy.updated_at = datetime.now()
            
            backup_file = None
            db_synced = False
            plugin_reloaded = False
            
            try:
                backup_file = await self._save_device_config_with_backup(device_copy)
                
                await self._sync_device_to_db(device_copy)
                db_synced = True
                
                await self._reload_device_plugin(device_copy)
                plugin_reloaded = True
                
                logger.info(f"Device {asset} updated successfully")
                return device_copy
                
            except Exception as e:
                logger.error(f"Failed to update device {asset}, rolling back: {e}")
                
                if backup_file and backup_file.exists():
                    try:
                        if db_synced:
                            device_file = self.devices_dir / f"{asset}.yaml"
                            shutil.copy2(backup_file, device_file)
                            logger.info(f"Config file restored from backup")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback config file: {rollback_error}")
                
                raise
    
    async def delete_device(self, asset: str) -> None:
        """删除设备
        
        Args:
            asset: 设备资产标识
        """
        async with await self._get_lock():
            device = await self.get_device(asset)
            if not device:
                raise ValueError(f"Device '{asset}' not found")
            
            logger.info(f"Deleting device: {asset}")
            
            await self._unload_device_plugin(asset)
            
            device_file = self.devices_dir / f"{asset}.yaml"
            if device_file.exists():
                device_file.unlink()
            
            await self.metadata_manager._soft_delete_device(
                asset, 
                time.time()
            )
            
            logger.info(f"Device {asset} deleted successfully")
    
    async def add_point(
        self,
        asset: str,
        point: PointConfig
    ) -> DeviceConfig:
        """向设备添加点位
        
        Args:
            asset: 设备资产标识
            point: 点位配置
            
        Returns:
            更新后的设备配置
        """
        async with await self._get_lock():
            device = await self.get_device(asset)
            if not device:
                raise ValueError(f"Device '{asset}' not found")
            
            if any(p.name == point.name for p in device.points):
                raise ValueError(
                    f"Point '{point.name}' already exists in device '{asset}'"
                )
            
            logger.info(f"Adding point {point.name} to device {asset}")
            
            device.points.append(point)
            device.updated_at = datetime.now()
            
            await self._save_device_config(device)
            
            await self._sync_point_to_db(asset, point)
            
            await self._reload_device_plugin(device)
            
            return device
    
    async def remove_point(
        self,
        asset: str,
        point_name: str
    ) -> DeviceConfig:
        """从设备移除点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            
        Returns:
            更新后的设备配置
        """
        async with await self._get_lock():
            device = await self.get_device(asset)
            if not device:
                raise ValueError(f"Device '{asset}' not found")
            
            original_count = len(device.points)
            device.points = [p for p in device.points if p.name != point_name]
            
            if len(device.points) == original_count:
                raise ValueError(
                    f"Point '{point_name}' not found in device '{asset}'"
                )
            
            logger.info(f"Removing point {point_name} from device {asset}")
            
            device.updated_at = datetime.now()
            
            await self._save_device_config(device)
            
            await self.metadata_manager._soft_delete_point(
                asset,
                point_name,
                time.time()
            )
            
            return device
    
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
        async with await self._get_lock():
            device = await self.get_device(asset)
            if not device:
                raise ValueError(f"Device '{asset}' not found")
            
            point_index = None
            for i, p in enumerate(device.points):
                if p.name == point_name:
                    point_index = i
                    break
            
            if point_index is None:
                raise ValueError(
                    f"Point '{point_name}' not found in device '{asset}'"
                )
            
            logger.info(f"Updating point {point_name} in device {asset}")
            
            for key, value in updates.items():
                if key == 'name':
                    continue
                if hasattr(device.points[point_index], key):
                    setattr(device.points[point_index], key, value)
            
            device.updated_at = datetime.now()
            
            await self._save_device_config(device)
            
            await self._sync_point_to_db(asset, device.points[point_index])
            
            await self._reload_device_plugin(device)
            
            return device
    
    async def _save_device_config(self, device: DeviceConfig) -> None:
        """保存设备配置到文件"""
        device_file = self.devices_dir / f"{device.asset}.yaml"
        
        with open(device_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                device.model_dump(mode='json', exclude_none=True),
                f,
                default_flow_style=False,
                allow_unicode=True
            )
        
        logger.debug(f"Device config saved to {device_file}")
    
    async def _save_device_config_with_backup(
        self, 
        device: DeviceConfig
    ) -> Optional[Path]:
        """保存设备配置并返回备份文件路径
        
        Args:
            device: 设备配置
            
        Returns:
            备份文件路径（如果文件已存在），否则返回 None
        """
        device_file = self.devices_dir / f"{device.asset}.yaml"
        backup_file = None
        
        if device_file.exists():
            import shutil
            backup_dir = self.devices_dir / '.backups'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"{device.asset}_{timestamp}.yaml"
            
            shutil.copy2(device_file, backup_file)
            logger.debug(f"Backup created: {backup_file}")
        
        await self._save_device_config(device)
        
        return backup_file
    
    async def _sync_device_to_db(self, device: DeviceConfig) -> None:
        """同步设备到数据库"""
        record = DeviceRecord(
            asset=device.asset,
            service_name=device.plugin.name,
            config_hash=self._compute_hash(device.model_dump(mode='json')),
            status=RegistryStatus.ACTIVE,
            created_at=device.created_at.timestamp() if device.created_at else time.time(),
            updated_at=device.updated_at.timestamp() if device.updated_at else time.time()
        )
        
        existing = await self.metadata_manager.get_device(device.asset)
        
        if existing is None:
            await self.metadata_manager._add_device(record)
        else:
            await self.metadata_manager._update_device(
                device.asset,
                record.config_hash,
                record.updated_at
            )
        
        for point in device.points:
            await self._sync_point_to_db(device.asset, point)
    
    async def _sync_point_to_db(
        self,
        asset: str,
        point: PointConfig
    ) -> None:
        """同步点位到数据库"""
        data_type = None
        if point.data_type:
            data_type = str(point.data_type)
        
        standard_data_type = None
        if point.standard_data_type:
            standard_data_type = point.standard_data_type.value if isinstance(point.standard_data_type, StandardDataType) else str(point.standard_data_type)
        
        record = PointRecord(
            asset=asset,
            point_name=point.name,
            data_type=data_type,
            unit=point.unit,
            config_hash=self._compute_hash(point.model_dump(mode='json')),
            status=RegistryStatus.ACTIVE
        )
        
        existing = await self.metadata_manager.get_point(asset, point.name)
        
        if existing is None:
            await self.metadata_manager._add_point(record)
        else:
            await self.metadata_manager._update_point(
                asset,
                point.name,
                record.config_hash,
                time.time()
            )
    
    async def _load_device_plugin(self, device: DeviceConfig) -> None:
        """加载设备插件实例"""
        try:
            plugin_config = await self._merge_plugin_config(device)
            
            plugin_info = await self.plugin_loader.load_plugin(
                plugin_type=device.plugin.name,
                name=device.plugin.name,
                config=plugin_config
            )
            
            await self.plugin_loader.start_plugin(plugin_info.plugin_id)
            
            logger.info(f"Plugin loaded for device {device.asset}")
        except Exception as e:
            logger.error(f"Failed to load plugin for device {device.asset}: {e}")
            raise
    
    async def _unload_device_plugin(self, asset: str) -> None:
        """卸载设备插件实例"""
        plugins = self.plugin_loader.get_all_plugins()
        
        for plugin in plugins:
            if plugin.config.get('asset_name') == asset:
                await self.plugin_loader.stop_plugin(plugin.plugin_id)
                await self.plugin_loader.unload_plugin(plugin.plugin_id)
                logger.info(f"Plugin unloaded for device {asset}")
                break
    
    async def _reload_device_plugin(self, device: DeviceConfig) -> None:
        """重新加载设备插件"""
        await self._unload_device_plugin(device.asset)
        await self._load_device_plugin(device)
    
    async def reload_device(self, asset: str) -> None:
        """Reload device plugin (public method)
        
        This method reloads a device's plugin without restarting the application.
        Use this when device point configuration has changed.
        
        Args:
            asset: Device asset name
            
        Raises:
            ValueError: If device not found
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        await self._reload_device_plugin(device)
        logger.info(f"Device {asset} reloaded successfully")
    
    async def reload_devices(self, assets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Reload multiple device plugins
        
        Args:
            assets: List of device asset names. If None, reloads all enabled devices.
            
        Returns:
            Dict containing reload results for each device
        """
        if assets is None:
            devices = await self.list_devices(enabled=True)
            assets = [d.asset for d in devices]
        
        if not assets:
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "results": {}
            }
        
        assets = list(set(assets))
        
        results = {}
        for asset in assets:
            try:
                await self.reload_device(asset)
                results[asset] = "reloaded"
            except ValueError as e:
                results[asset] = "not_found"
                logger.warning(f"Device {asset} not found during batch reload")
            except Exception as e:
                results[asset] = f"error: {str(e)}"
                logger.error(f"Failed to reload device {asset}: {e}")
        
        success_count = len([r for r in results.values() if r == "reloaded"])
        
        logger.info(f"Batch device reload completed: {success_count}/{len(assets)} succeeded")
        
        return {
            "total": len(assets),
            "succeeded": success_count,
            "failed": len(assets) - success_count,
            "results": results
        }
    
    async def _merge_plugin_config(
        self,
        device: DeviceConfig
    ) -> Dict[str, Any]:
        """合并插件配置"""
        plugin_defaults = await self._get_plugin_defaults(device.plugin.name)
        
        merged_config = {
            **plugin_defaults,
            **device.plugin.config,
            'asset_name': device.asset,
            'points': [p.model_dump(mode='json') for p in device.points]
        }
        
        return merged_config
    
    async def _get_plugin_defaults(
        self,
        plugin_name: str
    ) -> Dict[str, Any]:
        """获取插件默认配置"""
        plugin_file = self.plugins_dir / f"{plugin_name}.yaml"
        
        if plugin_file.exists():
            with open(plugin_file, 'r', encoding='utf-8') as f:
                plugin_config = yaml.safe_load(f)
                return plugin_config.get('defaults', {})
        
        return {}
    
    async def _validate_plugin(self, plugin_name: str) -> bool:
        """验证插件是否可用"""
        plugin_classes = self.plugin_loader.discover_plugins()
        return plugin_name in plugin_classes
    
    async def _device_exists(self, asset: str) -> bool:
        """检查设备是否已存在"""
        device_file = self.devices_dir / f"{asset}.yaml"
        return device_file.exists()
    
    def _compute_hash(self, config: Dict[str, Any]) -> str:
        """计算配置哈希"""
        content = json.dumps(config, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
    
    async def batch_create_devices(
        self,
        devices: List[DeviceConfig]
    ) -> Dict[str, Any]:
        """批量创建设备
        
        Args:
            devices: 设备列表
            
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
                    'success': True,
                    'message': f"Device '{device.asset}' created successfully"
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'asset': device.asset,
                    'success': False,
                    'message': str(e)
                })
        
        return results
    
    async def export_devices(
        self,
        assets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """导出设备配置
        
        Args:
            assets: 要导出的设备列表，None 表示导出所有
            
        Returns:
            导出的设备配置
        """
        if assets:
            devices = []
            for asset in assets:
                device = await self.get_device(asset)
                if device:
                    devices.append(device)
        else:
            devices = await self.list_devices()
        
        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'count': len(devices),
            'devices': [device.model_dump(mode='json') for device in devices]
        }
    
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
        devices_data = data.get('devices', [])
        results = {
            'total': len(devices_data),
            'succeeded': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        for device_data in devices_data:
            try:
                device = DeviceConfig(**device_data)
                
                if await self._device_exists(device.asset):
                    if overwrite:
                        await self.delete_device(device.asset)
                        await self.create_device(device)
                        results['succeeded'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'success': True,
                            'message': f"Device '{device.asset}' overwritten"
                        })
                    else:
                        results['skipped'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'success': False,
                            'message': f"Device '{device.asset}' already exists"
                        })
                else:
                    await self.create_device(device)
                    results['succeeded'] += 1
                    results['details'].append({
                        'asset': device.asset,
                        'success': True,
                        'message': f"Device '{device.asset}' imported"
                    })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'asset': device_data.get('asset', 'unknown'),
                    'success': False,
                    'message': str(e)
                })
        
        return results
