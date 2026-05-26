"""配置服务 - 业务逻辑层

此模块提供配置管理的业务逻辑，包括：
- 设备配置的CRUD操作
- 配置导入导出
- 配置版本管理
- 热重载支持
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml

from ..config.config_repository import ConfigRepository, DeviceConfig
from ..services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ConfigService:
    """配置服务 - 业务逻辑层"""
    
    def __init__(
        self,
        config_repo: ConfigRepository,
        audit_service: AuditService,
        plugin_loader: Any
    ):
        self.config_repo = config_repo
        self.audit_service = audit_service
        self.plugin_loader = plugin_loader
    
    async def create_device(
        self,
        device: DeviceConfig,
        user: Optional[str] = None,
        reload: bool = True
    ) -> DeviceConfig:
        """创建设备
        
        Args:
            device: 设备配置
            user: 操作用户
            reload: 是否立即加载插件
            
        Returns:
            创建的设备配置
            
        Raises:
            ValueError: 如果插件不可用或设备已存在
        """
        if not await self._validate_plugin(device.plugin_name):
            raise ValueError(f"Plugin '{device.plugin_name}' not available")
        
        created_device = await self.config_repo.create_device(device, user)
        
        if reload and device.enabled:
            try:
                await self._load_device_plugin(created_device)
            except Exception as e:
                logger.error(f"Failed to load plugin for device {device.asset}: {e}")
        
        await self.audit_service.log_action(
            action='create',
            entity_type='device',
            entity_id=device.asset,
            user=user,
            new_value=created_device.to_dict()
        )
        
        return created_device
    
    async def update_device(
        self,
        asset: str,
        updates: Dict[str, Any],
        user: Optional[str] = None,
        reload: bool = True
    ) -> DeviceConfig:
        """更新设备
        
        Args:
            asset: 设备资产标识
            updates: 更新内容
            user: 操作用户
            reload: 是否立即重载插件
            
        Returns:
            更新后的设备配置
            
        Raises:
            ValueError: 如果设备不存在
        """
        old_device = await self.config_repo.get_device(asset)
        if not old_device:
            raise ValueError(f"Device '{asset}' not found")
        
        updated_device = await self.config_repo.update_device(asset, updates, user)
        
        if reload:
            old_enabled = old_device.enabled
            new_enabled = updated_device.enabled
            
            if old_enabled and not new_enabled:
                await self._unload_device_plugin(asset)
                logger.info(f"Device '{asset}' disabled, plugin unloaded")
            elif not old_enabled and new_enabled:
                await self._load_device_plugin(updated_device)
                logger.info(f"Device '{asset}' enabled, plugin loaded")
            elif new_enabled:
                try:
                    await self._reload_device_plugin(updated_device)
                except Exception as e:
                    logger.error(f"Failed to reload plugin for device {asset}: {e}")
        
        await self.audit_service.log_action(
            action='update',
            entity_type='device',
            entity_id=asset,
            user=user,
            old_value=old_device.to_dict(),
            new_value=updated_device.to_dict()
        )
        
        return updated_device
    
    async def delete_device(
        self,
        asset: str,
        user: Optional[str] = None
    ) -> None:
        """删除设备
        
        Args:
            asset: 设备资产标识
            user: 操作用户
            
        Raises:
            ValueError: 如果设备不存在
        """
        device = await self.config_repo.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        try:
            await self._unload_device_plugin(asset)
        except Exception as e:
            logger.warning(f"Failed to unload plugin for device {asset}: {e}")
        
        await self.config_repo.delete_device(asset, user)
        
        await self.audit_service.log_action(
            action='delete',
            entity_type='device',
            entity_id=asset,
            user=user,
            old_value=device.to_dict()
        )
    
    async def reload_device(
        self,
        asset: str,
        user: Optional[str] = None
    ) -> None:
        """重载设备插件
        
        Args:
            asset: 设备资产标识
            user: 操作用户
            
        Raises:
            ValueError: 如果设备不存在
        """
        device = await self.config_repo.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        await self._reload_device_plugin(device)
        
        await self.audit_service.log_action(
            action='reload',
            entity_type='device',
            entity_id=asset,
            user=user
        )
        
        logger.info(f"Device reloaded: {asset} by {user}")
    
    async def add_point(
        self,
        asset: str,
        point: Dict[str, Any],
        user: Optional[str] = None,
        reload: bool = True
    ) -> None:
        """添加点位
        
        Args:
            asset: 设备资产标识
            point: 点位配置
            user: 操作用户
            reload: 是否立即重载插件
            
        Raises:
            ValueError: 如果设备不存在或点位已存在
        """
        await self.config_repo.add_point(asset, point, user)
        
        if reload:
            device = await self.config_repo.get_device(asset)
            if device and device.enabled:
                try:
                    await self._reload_device_plugin(device)
                except Exception as e:
                    logger.error(f"Failed to reload plugin after adding point: {e}")
        
        await self.audit_service.log_action(
            action='add_point',
            entity_type='point',
            entity_id=f"{asset}/{point.get('name')}",
            user=user,
            new_value=point
        )
    
    async def update_point(
        self,
        asset: str,
        point_name: str,
        updates: Dict[str, Any],
        user: Optional[str] = None,
        reload: bool = True
    ) -> None:
        """更新点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            updates: 更新内容
            user: 操作用户
            reload: 是否立即重载插件
            
        Raises:
            ValueError: 如果设备或点位不存在
        """
        device = await self.config_repo.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        old_point = None
        for p in device.points:
            if p.get('name') == point_name:
                old_point = p.copy()
                break
        
        await self.config_repo.update_point(asset, point_name, updates, user)
        
        if reload and device.enabled:
            try:
                updated_device = await self.config_repo.get_device(asset)
                if updated_device:
                    await self._reload_device_plugin(updated_device)
            except Exception as e:
                logger.error(f"Failed to reload plugin after updating point: {e}")
        
        await self.audit_service.log_action(
            action='update_point',
            entity_type='point',
            entity_id=f"{asset}/{point_name}",
            user=user,
            old_value=old_point,
            new_value=updates
        )
    
    async def delete_point(
        self,
        asset: str,
        point_name: str,
        user: Optional[str] = None,
        reload: bool = True
    ) -> None:
        """删除点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            user: 操作用户
            reload: 是否立即重载插件
            
        Raises:
            ValueError: 如果设备或点位不存在
        """
        device = await self.config_repo.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        old_point = None
        for p in device.points:
            if p.get('name') == point_name:
                old_point = p.copy()
                break
        
        await self.config_repo.delete_point(asset, point_name, user)
        
        if reload and device.enabled:
            try:
                updated_device = await self.config_repo.get_device(asset)
                if updated_device:
                    await self._reload_device_plugin(updated_device)
            except Exception as e:
                logger.error(f"Failed to reload plugin after deleting point: {e}")
        
        await self.audit_service.log_action(
            action='delete_point',
            entity_type='point',
            entity_id=f"{asset}/{point_name}",
            user=user,
            old_value=old_point
        )
    
    async def export_devices(
        self,
        assets: Optional[List[str]] = None,
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """导出设备配置
        
        Args:
            assets: 要导出的设备列表，None表示导出所有
            user: 操作用户
            
        Returns:
            导出的设备配置
        """
        if assets:
            devices = []
            for asset in assets:
                device = await self.config_repo.get_device(asset)
                if device:
                    devices.append(device)
        else:
            devices = await self.config_repo.list_devices()
        
        export_data = {
            'version': '1.0',
            'exported_at': time.time(),
            'exported_by': user,
            'count': len(devices),
            'devices': [device.to_dict() for device in devices]
        }
        
        await self.audit_service.log_action(
            action='export',
            entity_type='config',
            entity_id='devices',
            user=user,
            details={'count': len(devices), 'assets': assets}
        )
        
        logger.info(f"Exported {len(devices)} devices by {user}")
        return export_data
    
    async def import_devices(
        self,
        data: Dict[str, Any],
        user: Optional[str] = None,
        overwrite: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """导入设备配置
        
        Args:
            data: 导入的设备配置
            user: 操作用户
            overwrite: 是否覆盖已存在的设备
            dry_run: 是否只验证不执行
            
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
                device = DeviceConfig.from_dict(device_data)
                
                existing = await self.config_repo.get_device(device.asset)
                
                if existing:
                    if overwrite:
                        if not dry_run:
                            await self.update_device(
                                device.asset,
                                device.to_dict(),
                                user,
                                reload=False
                            )
                        results['succeeded'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'action': 'updated',
                            'success': True
                        })
                    else:
                        results['skipped'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'action': 'skipped',
                            'success': False,
                            'message': 'Device already exists'
                        })
                else:
                    if not dry_run:
                        await self.create_device(device, user, reload=False)
                    results['succeeded'] += 1
                    results['details'].append({
                        'asset': device.asset,
                        'action': 'created',
                        'success': True
                    })
            
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'asset': device_data.get('asset', 'unknown'),
                    'action': 'failed',
                    'success': False,
                    'message': str(e)
                })
        
        if not dry_run:
            await self.audit_service.log_action(
                action='import',
                entity_type='config',
                entity_id='devices',
                user=user,
                details=results
            )
        
        logger.info(f"Import completed: {results['succeeded']}/{results['total']} by {user}")
        return results
    
    async def export_to_yaml(
        self,
        output_dir: Path,
        assets: Optional[List[str]] = None,
        user: Optional[str] = None
    ) -> int:
        """导出设备配置到YAML文件
        
        Args:
            output_dir: 输出目录
            assets: 要导出的设备列表
            user: 操作用户
            
        Returns:
            导出的设备数量
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        export_data = await self.export_devices(assets, user)
        
        for device_data in export_data['devices']:
            device_file = output_dir / f"{device_data['asset']}.yaml"
            
            with open(device_file, 'w', encoding='utf-8') as f:
                yaml.dump(
                    device_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True
                )
        
        logger.info(f"Exported {len(export_data['devices'])} devices to {output_dir}")
        return len(export_data['devices'])
    
    async def import_from_yaml(
        self,
        input_dir: Path,
        user: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """从YAML文件导入设备配置
        
        Args:
            input_dir: 输入目录
            user: 操作用户
            overwrite: 是否覆盖已存在的设备
            
        Returns:
            导入结果
        """
        devices_data = []
        
        for yaml_file in input_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    device_data = yaml.safe_load(f)
                    if device_data:
                        devices_data.append(device_data)
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
        
        import_data = {
            'version': '1.0',
            'imported_from': str(input_dir),
            'devices': devices_data
        }
        
        return await self.import_devices(import_data, user, overwrite)
    
    async def get_config_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取配置历史
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            limit: 返回数量限制
            
        Returns:
            配置历史列表
        """
        return await self.config_repo.get_config_versions(entity_type, entity_id, limit)
    
    async def rollback_config(
        self,
        entity_type: str,
        entity_id: str,
        version: int,
        user: Optional[str] = None
    ) -> None:
        """回滚配置到指定版本
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            version: 目标版本号
            user: 操作用户
            
        Raises:
            ValueError: 如果版本不存在
        """
        old_config = await self.config_repo.get_config_version(entity_type, entity_id, version)
        if not old_config:
            raise ValueError(f"Version {version} not found for {entity_type}/{entity_id}")
        
        if entity_type == 'device':
            await self.update_device(entity_id, old_config['config'], user)
        
        await self.audit_service.log_action(
            action='rollback',
            entity_type=entity_type,
            entity_id=entity_id,
            user=user,
            details={'version': version}
        )
        
        logger.info(f"Config rolled back: {entity_type}/{entity_id} to v{version} by {user}")
    
    async def _validate_plugin(self, plugin_name: str) -> bool:
        """验证插件是否可用
        
        Args:
            plugin_name: 插件名称，如 'modbus_tcp' 或 'modbus'
            
        Returns:
            插件是否可用
        """
        try:
            plugin_classes = self.plugin_loader.discover_plugins()
            if plugin_name in plugin_classes:
                return True
            for key in plugin_classes:
                parts = key.split(':', 1)
                if len(parts) == 2 and parts[1] == plugin_name:
                    return True
            for key in plugin_classes:
                parts = key.split(':', 1)
                if len(parts) == 2 and plugin_name in parts[1]:
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to validate plugin {plugin_name}: {e}")
            return False
    
    def _resolve_plugin_key(self, plugin_name: str) -> Optional[str]:
        """解析插件名称到完整的注册key
        
        Args:
            plugin_name: 插件名称，如 'modbus_tcp', 'modbus', 'knx'
            
        Returns:
            完整的注册key，如 'south:modbus_tcp'，未找到返回None
        """
        plugin_classes = self.plugin_loader.discover_plugins()
        if plugin_name in plugin_classes:
            return plugin_name
        for key in plugin_classes:
            parts = key.split(':', 1)
            if len(parts) == 2 and parts[1] == plugin_name:
                return key
        for key in plugin_classes:
            parts = key.split(':', 1)
            if len(parts) == 2 and plugin_name in parts[1]:
                return key
        return None
    
    async def _load_device_plugin(self, device: DeviceConfig) -> None:
        """加载设备插件"""
        try:
            plugin_key = self._resolve_plugin_key(device.plugin_name)
            if not plugin_key:
                raise RuntimeError(f"Plugin '{device.plugin_name}' not found for device {device.asset}")
            
            parts = plugin_key.split(':', 1)
            plugin_type = parts[0] if len(parts) == 2 else device.plugin_name
            plugin_name = parts[1] if len(parts) == 2 else device.plugin_name
            
            plugin_config = {
                **device.plugin_config,
                'asset_name': device.asset,
                'points': device.points
            }
            
            plugin_info = await self.plugin_loader.load_plugin(
                plugin_type=plugin_type,
                name=plugin_name,
                config=plugin_config
            )
            
            if plugin_info:
                await self.plugin_loader.start_plugin(plugin_info.plugin_id)
                logger.info(f"Plugin loaded for device {device.asset}")
            else:
                raise RuntimeError(f"Plugin load returned None for device {device.asset}")
        
        except Exception as e:
            logger.error(f"Failed to load plugin for device {device.asset}: {e}")
            raise
    
    async def _unload_device_plugin(self, asset: str) -> None:
        """卸载设备插件"""
        try:
            plugins = self.plugin_loader.get_all_plugins()
            
            for plugin in plugins:
                if plugin.config.get('asset_name') == asset:
                    await self.plugin_loader.stop_plugin(plugin.plugin_id)
                    await self.plugin_loader.unload_plugin(plugin.plugin_id)
                    logger.info(f"Plugin unloaded for device {asset}")
                    break
        except Exception as e:
            logger.error(f"Failed to unload plugin for device {asset}: {e}")
            raise
    
    async def _reload_device_plugin(self, device: DeviceConfig) -> None:
        """重新加载设备插件"""
        await self._unload_device_plugin(device.asset)
        await self._load_device_plugin(device)
