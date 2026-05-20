"""数据库迁移脚本 - 扩展表结构以支持数据库为中心的配置管理

此脚本添加以下功能：
1. 扩展 device_registry 表，添加版本控制和审计字段
2. 扩展 point_registry 表，添加版本控制和审计字段
3. 创建 config_versions 表，用于配置版本管理
4. 创建 audit_logs 表，用于审计日志
"""

import logging
import aiosqlite
from typing import Optional

logger = logging.getLogger(__name__)


async def migrate_v1_to_v2(db: aiosqlite.Connection) -> None:
    """从v1迁移到v2：添加配置版本控制和审计功能"""
    
    logger.info("Starting database migration v1 -> v2...")
    
    await _migrate_device_registry(db)
    
    await _migrate_point_registry(db)
    
    await _create_config_versions_table(db)
    
    await _create_audit_logs_table(db)
    
    await db.commit()
    
    logger.info("Database migration v1 -> v2 completed successfully")


async def _migrate_device_registry(db: aiosqlite.Connection) -> None:
    """扩展 device_registry 表"""
    
    async with db.execute("PRAGMA table_info(device_registry)") as cursor:
        columns = {row[1]: row[2] for row in await cursor.fetchall()}
    
    new_columns = {
        'version': 'INTEGER DEFAULT 1',
        'created_by': 'TEXT',
        'updated_by': 'TEXT',
        'last_reload_at': 'REAL',
        'reload_count': 'INTEGER DEFAULT 0'
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            try:
                await db.execute(f"ALTER TABLE device_registry ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column '{col_name}' to device_registry")
            except Exception as e:
                logger.warning(f"Failed to add column '{col_name}': {e}")


async def _migrate_point_registry(db: aiosqlite.Connection) -> None:
    """扩展 point_registry 表"""
    
    async with db.execute("PRAGMA table_info(point_registry)") as cursor:
        columns = {row[1]: row[2] for row in await cursor.fetchall()}
    
    new_columns = {
        'standard_data_type': 'TEXT',
        'version': 'INTEGER DEFAULT 1',
        'created_by': 'TEXT',
        'updated_by': 'TEXT'
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            try:
                await db.execute(f"ALTER TABLE point_registry ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column '{col_name}' to point_registry")
            except Exception as e:
                logger.warning(f"Failed to add column '{col_name}': {e}")


async def _create_config_versions_table(db: aiosqlite.Connection) -> None:
    """创建配置版本表"""
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS config_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            config TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            change_type TEXT NOT NULL,
            changed_by TEXT,
            changed_at REAL NOT NULL,
            change_reason TEXT,
            previous_version INTEGER,
            
            UNIQUE(entity_type, entity_id, version)
        )
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_config_versions_entity 
        ON config_versions(entity_type, entity_id)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_config_versions_time 
        ON config_versions(changed_at)
    """)
    
    logger.info("Created config_versions table")


async def _create_audit_logs_table(db: aiosqlite.Connection) -> None:
    """创建审计日志表"""
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            user TEXT,
            ip_address TEXT,
            details TEXT,
            old_value TEXT,
            new_value TEXT,
            timestamp REAL NOT NULL,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action 
        ON audit_logs(action)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_entity 
        ON audit_logs(entity_type, entity_id)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_time 
        ON audit_logs(timestamp)
    """)
    
    logger.info("Created audit_logs table")


async def check_migration_needed(db: aiosqlite.Connection) -> bool:
    """检查是否需要执行迁移"""
    
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='config_versions'"
    ) as cursor:
        result = await cursor.fetchone()
        if result:
            logger.info("Migration already applied (config_versions table exists)")
            return False
    
    logger.info("Migration needed (config_versions table not found)")
    return True


async def run_migration(db: aiosqlite.Connection) -> None:
    """执行数据库迁移"""
    
    if await check_migration_needed(db):
        await migrate_v1_to_v2(db)
    else:
        logger.info("Database is already up to date")
