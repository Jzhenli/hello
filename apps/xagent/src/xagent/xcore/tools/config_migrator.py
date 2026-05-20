"""配置迁移工具 - YAML到数据库迁移

此工具用于将现有的YAML配置文件迁移到数据库。
支持增量迁移和完整迁移。
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List
import aiosqlite

from ..config.config_repository import ConfigRepository, DeviceConfig

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """配置迁移工具"""
    
    def __init__(self, config_repo: ConfigRepository):
        self.config_repo = config_repo
    
    async def migrate_from_yaml(
        self,
        devices_dir: Path,
        user: str = "migration",
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """从YAML文件迁移配置到数据库
        
        Args:
            devices_dir: YAML设备配置目录
            user: 迁移操作用户
            skip_existing: 是否跳过已存在的设备
            
        Returns:
            迁移结果
        """
        logger.info(f"Starting migration from {devices_dir}")
        
        results = {
            'total': 0,
            'succeeded': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        if not devices_dir.exists():
            logger.warning(f"Devices directory not found: {devices_dir}")
            return results
        
        yaml_files = list(devices_dir.glob("*.yaml"))
        results['total'] = len(yaml_files)
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    device_data = yaml.safe_load(f)
                
                if not device_data:
                    results['skipped'] += 1
                    results['details'].append({
                        'file': str(yaml_file),
                        'status': 'skipped',
                        'reason': 'empty_file'
                    })
                    continue
                
                device = self._convert_yaml_to_device(device_data)
                
                existing = await self.config_repo.get_device(device.asset)
                if existing:
                    if skip_existing:
                        logger.info(f"Device {device.asset} already exists in database, skipping")
                        results['skipped'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'file': str(yaml_file),
                            'status': 'skipped',
                            'reason': 'already_exists'
                        })
                        continue
                    else:
                        logger.info(f"Device {device.asset} already exists, updating")
                        await self.config_repo.update_device(device.asset, device.to_dict(), user)
                        results['succeeded'] += 1
                        results['details'].append({
                            'asset': device.asset,
                            'file': str(yaml_file),
                            'status': 'updated'
                        })
                        continue
                
                await self.config_repo.create_device(device, user)
                
                results['succeeded'] += 1
                results['details'].append({
                    'asset': device.asset,
                    'file': str(yaml_file),
                    'status': 'success'
                })
                
                logger.info(f"Migrated device: {device.asset}")
            
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'file': str(yaml_file),
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Failed to migrate {yaml_file}: {e}")
        
        logger.info(f"Migration completed: {results['succeeded']}/{results['total']} succeeded")
        return results
    
    def _convert_yaml_to_device(self, yaml_data: Dict[str, Any]) -> DeviceConfig:
        """将YAML数据转换为DeviceConfig
        
        Args:
            yaml_data: YAML数据
            
        Returns:
            设备配置
        """
        plugin_data = yaml_data.get('plugin', {})
        plugin_config = plugin_data.get('config', {})
        
        points = []
        for point_data in yaml_data.get('points', []):
            points.append({
                'name': point_data.get('name'),
                'description': point_data.get('description'),
                'data_type': point_data.get('data_type'),
                'standard_data_type': point_data.get('standard_data_type'),
                'unit': point_data.get('unit'),
                'config': point_data.get('config', {}),
                'metadata': point_data.get('metadata', {}),
                'tags': point_data.get('tags', []),
                'enabled': point_data.get('enabled', True)
            })
        
        return DeviceConfig(
            asset=yaml_data.get('asset'),
            name=yaml_data.get('name'),
            description=yaml_data.get('description'),
            plugin_name=plugin_data.get('name', ''),
            plugin_config=plugin_config,
            enabled=yaml_data.get('enabled', True),
            status=yaml_data.get('status', 'active'),
            metadata=yaml_data.get('metadata', {}),
            tags=yaml_data.get('tags', []),
            points=points
        )
    
    async def validate_yaml_files(
        self,
        devices_dir: Path
    ) -> Dict[str, Any]:
        """验证YAML文件格式
        
        Args:
            devices_dir: YAML设备配置目录
            
        Returns:
            验证结果
        """
        results = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'details': []
        }
        
        if not devices_dir.exists():
            logger.warning(f"Devices directory not found: {devices_dir}")
            return results
        
        yaml_files = list(devices_dir.glob("*.yaml"))
        results['total'] = len(yaml_files)
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    device_data = yaml.safe_load(f)
                
                if not device_data:
                    results['invalid'] += 1
                    results['details'].append({
                        'file': str(yaml_file),
                        'valid': False,
                        'error': 'Empty file'
                    })
                    continue
                
                device = self._convert_yaml_to_device(device_data)
                
                if not device.asset:
                    results['invalid'] += 1
                    results['details'].append({
                        'file': str(yaml_file),
                        'valid': False,
                        'error': 'Missing asset name'
                    })
                    continue
                
                if not device.plugin_name:
                    results['invalid'] += 1
                    results['details'].append({
                        'file': str(yaml_file),
                        'valid': False,
                        'error': 'Missing plugin name'
                    })
                    continue
                
                results['valid'] += 1
                results['details'].append({
                    'file': str(yaml_file),
                    'valid': True,
                    'asset': device.asset
                })
            
            except Exception as e:
                results['invalid'] += 1
                results['details'].append({
                    'file': str(yaml_file),
                    'valid': False,
                    'error': str(e)
                })
        
        logger.info(f"Validation completed: {results['valid']}/{results['total']} valid")
        return results
    
    async def compare_yaml_with_db(
        self,
        devices_dir: Path
    ) -> Dict[str, Any]:
        """比较YAML文件和数据库配置
        
        Args:
            devices_dir: YAML设备配置目录
            
        Returns:
            比较结果
        """
        results = {
            'yaml_only': [],
            'db_only': [],
            'both': [],
            'differences': []
        }
        
        yaml_devices = set()
        if devices_dir.exists():
            for yaml_file in devices_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        device_data = yaml.safe_load(f)
                        if device_data and device_data.get('asset'):
                            yaml_devices.add(device_data['asset'])
                except Exception as e:
                    logger.error(f"Failed to read {yaml_file}: {e}")
        
        db_devices = await self.config_repo.list_devices()
        db_device_assets = {d.asset for d in db_devices}
        
        results['yaml_only'] = list(yaml_devices - db_device_assets)
        results['db_only'] = list(db_device_assets - yaml_devices)
        results['both'] = list(yaml_devices & db_device_assets)
        
        for asset in results['both']:
            yaml_device = None
            yaml_file = devices_dir / f"{asset}.yaml"
            if yaml_file.exists():
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        device_data = yaml.safe_load(f)
                        if device_data:
                            yaml_device = self._convert_yaml_to_device(device_data)
                except Exception as e:
                    logger.error(f"Failed to read {yaml_file}: {e}")
            
            db_device = await self.config_repo.get_device(asset)
            
            if yaml_device and db_device:
                yaml_hash = self.config_repo._compute_hash(
                    self.config_repo._compute_hash(str(yaml_device.to_dict()))
                )
                db_hash = self.config_repo._compute_hash(
                    self.config_repo._compute_hash(str(db_device.to_dict()))
                )
                
                if yaml_hash != db_hash:
                    results['differences'].append({
                        'asset': asset,
                        'yaml_updated': yaml_device.updated_at,
                        'db_updated': db_device.updated_at
                    })
        
        logger.info(f"Comparison completed: {len(results['yaml_only'])} YAML only, "
                   f"{len(results['db_only'])} DB only, {len(results['both'])} both, "
                   f"{len(results['differences'])} differences")
        
        return results
