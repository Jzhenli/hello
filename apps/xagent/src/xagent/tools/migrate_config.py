#!/usr/bin/env python3
"""配置迁移CLI工具

用于将YAML配置迁移到数据库的命令行工具。
"""

import argparse
import asyncio
import logging
from pathlib import Path

from xagent.xcore.storage.sqlite import SQLiteStorage
from xagent.xcore.config.config_repository import ConfigRepository
from xagent.xcore.tools.config_migrator import ConfigMigrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_command(args):
    """执行迁移"""
    storage = SQLiteStorage()
    await storage.initialize({'database': args.database})
    
    config_repo = ConfigRepository(storage._db)
    migrator = ConfigMigrator(config_repo)
    
    devices_dir = Path(args.devices_dir)
    
    logger.info(f"Migrating from {devices_dir} to database {args.database}")
    
    results = await migrator.migrate_from_yaml(
        devices_dir,
        user=args.user,
        skip_existing=not args.overwrite
    )
    
    print("\n=== Migration Results ===")
    print(f"Total: {results['total']}")
    print(f"Succeeded: {results['succeeded']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped: {results['skipped']}")
    
    if results['failed'] > 0:
        print("\nFailed devices:")
        for detail in results['details']:
            if detail.get('status') == 'failed':
                print(f"  - {detail.get('file')}: {detail.get('error')}")
    
    await storage.close()


async def validate_command(args):
    """验证YAML文件"""
    migrator = ConfigMigrator(None)
    devices_dir = Path(args.devices_dir)
    
    logger.info(f"Validating YAML files in {devices_dir}")
    
    results = await migrator.validate_yaml_files(devices_dir)
    
    print("\n=== Validation Results ===")
    print(f"Total: {results['total']}")
    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")
    
    if results['invalid'] > 0:
        print("\nInvalid files:")
        for detail in results['details']:
            if not detail.get('valid'):
                print(f"  - {detail.get('file')}: {detail.get('error')}")


async def compare_command(args):
    """比较YAML和数据库配置"""
    storage = SQLiteStorage()
    await storage.initialize({'database': args.database})
    
    config_repo = ConfigRepository(storage._db)
    migrator = ConfigMigrator(config_repo)
    
    devices_dir = Path(args.devices_dir)
    
    logger.info(f"Comparing {devices_dir} with database {args.database}")
    
    results = await migrator.compare_yaml_with_db(devices_dir)
    
    print("\n=== Comparison Results ===")
    print(f"YAML only: {len(results['yaml_only'])}")
    print(f"Database only: {len(results['db_only'])}")
    print(f"Both: {len(results['both'])}")
    print(f"Differences: {len(results['differences'])}")
    
    if results['yaml_only']:
        print("\nDevices only in YAML:")
        for asset in results['yaml_only']:
            print(f"  - {asset}")
    
    if results['db_only']:
        print("\nDevices only in database:")
        for asset in results['db_only']:
            print(f"  - {asset}")
    
    if results['differences']:
        print("\nDevices with differences:")
        for diff in results['differences']:
            print(f"  - {diff['asset']}")
    
    await storage.close()


def main():
    parser = argparse.ArgumentParser(
        description='Configuration Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate YAML files
  python migrate_config.py validate --devices-dir ./config/devices
  
  # Compare YAML with database
  python migrate_config.py compare --devices-dir ./config/devices --database ./data/xagent.db
  
  # Migrate YAML to database
  python migrate_config.py migrate --devices-dir ./config/devices --database ./data/xagent.db
  
  # Migrate with overwrite
  python migrate_config.py migrate --devices-dir ./config/devices --database ./data/xagent.db --overwrite
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    migrate_parser = subparsers.add_parser('migrate', help='Migrate YAML to database')
    migrate_parser.add_argument('--devices-dir', required=True, help='Devices YAML directory')
    migrate_parser.add_argument('--database', required=True, help='Database file path')
    migrate_parser.add_argument('--user', default='migration', help='Migration user')
    migrate_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing devices')
    
    validate_parser = subparsers.add_parser('validate', help='Validate YAML files')
    validate_parser.add_argument('--devices-dir', required=True, help='Devices YAML directory')
    
    compare_parser = subparsers.add_parser('compare', help='Compare YAML with database')
    compare_parser.add_argument('--devices-dir', required=True, help='Devices YAML directory')
    compare_parser.add_argument('--database', required=True, help='Database file path')
    
    args = parser.parse_args()
    
    if args.command == 'migrate':
        asyncio.run(migrate_command(args))
    elif args.command == 'validate':
        asyncio.run(validate_command(args))
    elif args.command == 'compare':
        asyncio.run(compare_command(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
