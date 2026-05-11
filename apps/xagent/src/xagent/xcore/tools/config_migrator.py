import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """配置迁移工具
    
    将旧版配置格式迁移到新的模块化配置格式
    """
    
    def __init__(self, source_path: Path, target_path: Path):
        """
        Args:
            source_path: 源配置文件路径（旧格式）
            target_path: 目标配置目录路径（新格式）
        """
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
    
    async def migrate(self, backup: bool = True) -> Dict[str, Any]:
        """执行迁移
        
        Args:
            backup: 是否备份源配置文件
            
        Returns:
            迁移报告
        """
        logger.info(f"Starting migration from {self.source_path} to {self.target_path}")
        
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source config file not found: {self.source_path}")
        
        if backup:
            await self._backup_source()
        
        with open(self.source_path, 'r', encoding='utf-8') as f:
            legacy_config = yaml.safe_load(f)
        
        new_config = self._convert(legacy_config)
        
        await self._save_new_config(new_config)
        
        report = self._generate_report(legacy_config, new_config)
        
        logger.info(f"Migration completed: {json.dumps(report, indent=2)}")
        return report
    
    def _convert(self, legacy: Dict[str, Any]) -> Dict[str, Any]:
        """转换配置格式
        
        Args:
            legacy: 旧配置格式
            
        Returns:
            新配置格式
        """
        new_config = {
            'main': self._extract_main_config(legacy),
            'plugins': {},
            'devices': {}
        }
        
        for plugin_type in ['south', 'north', 'filter']:
            if plugin_type in legacy.get('plugins', {}):
                for plugin in legacy['plugins'][plugin_type]:
                    plugin_config = self._extract_plugin_config(plugin, plugin_type)
                    plugin_name = plugin_config['name']
                    new_config['plugins'][plugin_name] = plugin_config
        
        for plugin_type in ['south', 'north']:
            if plugin_type in legacy.get('plugins', {}):
                for plugin in legacy['plugins'][plugin_type]:
                    device_config = self._extract_device_config(plugin, plugin_type)
                    asset = device_config['asset']
                    new_config['devices'][asset] = device_config
        
        return new_config
    
    def _extract_main_config(self, legacy: Dict) -> Dict[str, Any]:
        """提取主配置
        
        Args:
            legacy: 旧配置
            
        Returns:
            主配置
        """
        return {
            'server': legacy.get('server', {}),
            'storage': legacy.get('storage', {}),
            'logging': legacy.get('logging', {}),
            'scheduler': legacy.get('scheduler', {}),
            'metrics': legacy.get('metrics', {}),
            'plugins': {
                'discovery_paths': ['config/plugins'],
                'auto_load': True
            },
            'devices': {
                'discovery_paths': ['config/devices'],
                'auto_load': True
            }
        }
    
    def _extract_plugin_config(
        self, 
        plugin: Dict[str, Any], 
        plugin_type: str
    ) -> Dict[str, Any]:
        """提取插件配置
        
        Args:
            plugin: 插件配置
            plugin_type: 插件类型
            
        Returns:
            插件配置
        """
        plugin_name = plugin['name']
        config = plugin.get('config', {})
        
        plugin_specific_fields = self._get_plugin_specific_fields(plugin_name)
        
        plugin_config = {
            'name': plugin_name,
            'type': plugin_type,
            'version': '1.0.0',
            'enabled': plugin.get('enabled', True),
            'defaults': {}
        }
        
        for field in plugin_specific_fields:
            if field in config and field not in ['asset_name', 'points']:
                plugin_config['defaults'][field] = config[field]
        
        return plugin_config
    
    def _extract_device_config(
        self, 
        plugin: Dict[str, Any], 
        plugin_type: str
    ) -> Dict[str, Any]:
        """提取设备配置
        
        Args:
            plugin: 插件配置
            plugin_type: 插件类型
            
        Returns:
            设备配置
        """
        config = plugin.get('config', {})
        asset = config.get('asset_name', plugin['name'])
        plugin_name = plugin['name']
        
        plugin_specific_fields = self._get_plugin_specific_fields(plugin_name)
        plugin_config = {}
        
        for field in plugin_specific_fields:
            if field in config:
                plugin_config[field] = config[field]
        
        points = config.get('points', [])
        
        return {
            'asset': asset,
            'name': asset,
            'enabled': plugin.get('enabled', True),
            'plugin': {
                'name': plugin_name,
                'config': plugin_config
            },
            'points': points,
            'metadata': {},
            'tags': []
        }
    
    def _get_plugin_specific_fields(self, plugin_name: str) -> List[str]:
        """获取插件特定字段
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件特定字段列表
        """
        fields_map = {
            'modbus_tcp': [
                'host', 'port', 'slave_id', 'timeout', 
                'reconnect_interval', 'heartbeat_address',
                'heartbeat_timeout', 'max_gap'
            ],
            'modbus_rtu': [
                'serial_port', 'baudrate', 'parity', 'stopbits',
                'bytesize', 'slave_id', 'timeout',
                'reconnect_interval', 'heartbeat_address',
                'heartbeat_timeout', 'max_gap'
            ],
            'bacnet': [
                'device_id', 'port', 'timeout',
                'heartbeat_mode', 'heartbeat_property'
            ],
            'knx': ['host', 'port'],
            'mqtt_client': [
                'host', 'port', 'username', 'password',
                'topic', 'qos', 'client_id'
            ]
        }
        return fields_map.get(plugin_name, [])
    
    async def _save_new_config(self, config: Dict[str, Any]) -> None:
        """保存新配置
        
        Args:
            config: 新配置
        """
        self.target_path.mkdir(parents=True, exist_ok=True)
        
        main_config_path = self.target_path / 'config.yaml'
        with open(main_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config['main'], f, default_flow_style=False, allow_unicode=True)
        
        plugins_dir = self.target_path / 'plugins'
        plugins_dir.mkdir(exist_ok=True)
        
        for plugin_name, plugin_config in config['plugins'].items():
            plugin_file = plugins_dir / f"{plugin_name}.yaml"
            with open(plugin_file, 'w', encoding='utf-8') as f:
                yaml.dump(plugin_config, f, default_flow_style=False, allow_unicode=True)
        
        devices_dir = self.target_path / 'devices'
        devices_dir.mkdir(exist_ok=True)
        
        for asset, device_config in config['devices'].items():
            device_file = devices_dir / f"{asset}.yaml"
            with open(device_file, 'w', encoding='utf-8') as f:
                yaml.dump(device_config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"New config saved to {self.target_path}")
    
    async def _backup_source(self) -> None:
        """备份源配置文件"""
        import shutil
        
        backup_dir = self.source_path.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"config_backup_{timestamp}.yaml"
        
        shutil.copy2(self.source_path, backup_path)
        logger.info(f"Source config backed up to {backup_path}")
    
    def _generate_report(
        self, 
        legacy: Dict, 
        new: Dict
    ) -> Dict[str, Any]:
        """生成迁移报告
        
        Args:
            legacy: 旧配置
            new: 新配置
            
        Returns:
            迁移报告
        """
        total_points = sum(
            len(d['points']) for d in new['devices'].values()
        )
        
        return {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'source': str(self.source_path),
            'target': str(self.target_path),
            'plugins_migrated': len(new['plugins']),
            'devices_migrated': len(new['devices']),
            'total_points': total_points,
            'details': {
                'plugins': list(new['plugins'].keys()),
                'devices': list(new['devices'].keys())
            }
        }
    
    async def validate_migration(self) -> Dict[str, Any]:
        """验证迁移结果
        
        Returns:
            验证结果
        """
        if not self.target_path.exists():
            return {
                'valid': False,
                'error': 'Target directory does not exist'
            }
        
        main_config = self.target_path / 'config.yaml'
        if not main_config.exists():
            return {
                'valid': False,
                'error': 'Main config file not found'
            }
        
        plugins_dir = self.target_path / 'plugins'
        devices_dir = self.target_path / 'devices'
        
        if not plugins_dir.exists() or not devices_dir.exists():
            return {
                'valid': False,
                'error': 'Required directories not found'
            }
        
        plugin_files = list(plugins_dir.glob('*.yaml'))
        device_files = list(devices_dir.glob('*.yaml'))
        
        return {
            'valid': True,
            'plugins_count': len(plugin_files),
            'devices_count': len(device_files),
            'details': {
                'plugins': [f.stem for f in plugin_files],
                'devices': [f.stem for f in device_files]
            }
        }
    
    @staticmethod
    async def rollback(
        backup_path: Path, 
        target_path: Path
    ) -> Dict[str, Any]:
        """回滚迁移
        
        Args:
            backup_path: 备份文件路径
            target_path: 目标目录路径
            
        Returns:
            回滚结果
        """
        import shutil
        
        if not backup_path.exists():
            return {
                'success': False,
                'error': 'Backup file not found'
            }
        
        try:
            if target_path.exists():
                shutil.rmtree(target_path)
            
            logger.info(f"Rollback completed: removed {target_path}")
            
            return {
                'success': True,
                'message': 'Rollback completed successfully'
            }
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


async def main():
    """命令行工具入口"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='XAgent Config Migration Tool')
    parser.add_argument(
        'source',
        type=str,
        help='Source config file path (legacy format)'
    )
    parser.add_argument(
        'target',
        type=str,
        help='Target config directory path (new format)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not backup source config'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate migration result'
    )
    parser.add_argument(
        '--rollback',
        type=str,
        help='Rollback migration using backup file'
    )
    
    args = parser.parse_args()
    
    migrator = ConfigMigrator(
        source_path=Path(args.source),
        target_path=Path(args.target)
    )
    
    try:
        if args.rollback:
            result = await ConfigMigrator.rollback(
                backup_path=Path(args.rollback),
                target_path=Path(args.target)
            )
        elif args.validate:
            result = await migrator.validate_migration()
        else:
            result = await migrator.migrate(backup=not args.no_backup)
        
        print(json.dumps(result, indent=2))
        
        if not result.get('success', result.get('valid', False)):
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': str(e)
        }, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
