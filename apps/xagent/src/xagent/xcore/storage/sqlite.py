"""SQLite Storage Implementation with async support"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from .interface import StorageInterface, Reading
from ..utils.constants import DataConstants

logger = logging.getLogger(__name__)


class SQLiteStorage(StorageInterface):
    def __init__(self):
        self._db: Optional[aiosqlite.Connection] = None
        self._database_path: str = ""
        self._wal_mode: bool = True
        self._initialized: bool = False

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._database_path = config.get("database", "./data/xagent.db")
        self._wal_mode = config.get("wal_mode", True)
        
        db_path = Path(self._database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._db = await aiosqlite.connect(self._database_path)
        
        if self._wal_mode:
            await self._db.execute("PRAGMA journal_mode=WAL")
        
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                timestamp REAL NOT NULL,
                service_name TEXT NOT NULL,
                data TEXT NOT NULL,
                tags TEXT,
                standard_points TEXT,
                device_status TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        await self._migrate_add_columns()
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_asset 
            ON readings(asset)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_timestamp 
            ON readings(timestamp)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_service 
            ON readings(service_name)
        """)
        
        await self._create_metadata_tables()
        
        await self._run_migrations()
        
        await self._db.commit()
        self._initialized = True
        logger.info(f"SQLite storage initialized: {self._database_path}")

    async def _create_metadata_tables(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS device_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL UNIQUE,
                name TEXT,
                description TEXT,
                service_name TEXT NOT NULL,
                plugin_name TEXT,
                plugin_config TEXT,
                config_hash TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'active',
                metadata TEXT,
                tags TEXT,
                config_path TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                deleted_at REAL
            );
            
            CREATE TABLE IF NOT EXISTS point_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                point_name TEXT NOT NULL,
                description TEXT,
                data_type TEXT,
                unit TEXT,
                config TEXT,
                metadata TEXT,
                tags TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                config_hash TEXT,
                status TEXT DEFAULT 'active',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                deleted_at REAL,
                UNIQUE(asset, point_name)
            );
            
            CREATE TABLE IF NOT EXISTS plugin_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                version TEXT,
                description TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                defaults TEXT,
                capabilities TEXT,
                config_path TEXT,
                status TEXT DEFAULT 'registered',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS service_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT,
                description TEXT,
                protocol TEXT NOT NULL,
                connection_config TEXT NOT NULL,
                adapter_config TEXT,
                upload_config TEXT,
                command_config TEXT,
                enabled INTEGER DEFAULT 1,
                status TEXT DEFAULT 'offline',
                priority INTEGER DEFAULT 0,
                metadata TEXT,
                tags TEXT,
                statistics TEXT,
                config_hash TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                created_by TEXT,
                updated_by TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_device_asset ON device_registry(asset);
            CREATE INDEX IF NOT EXISTS idx_device_status ON device_registry(status);
            CREATE INDEX IF NOT EXISTS idx_device_enabled ON device_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_device_plugin ON device_registry(plugin_name);
            CREATE INDEX IF NOT EXISTS idx_point_asset ON point_registry(asset);
            CREATE INDEX IF NOT EXISTS idx_point_status ON point_registry(status);
            CREATE INDEX IF NOT EXISTS idx_point_enabled ON point_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_plugin_name ON plugin_registry(name);
            CREATE INDEX IF NOT EXISTS idx_plugin_type ON plugin_registry(type);
            CREATE INDEX IF NOT EXISTS idx_service_name ON service_registry(name);
            CREATE INDEX IF NOT EXISTS idx_service_protocol ON service_registry(protocol);
            CREATE INDEX IF NOT EXISTS idx_service_enabled ON service_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_service_status ON service_registry(status);
            
            CREATE TABLE IF NOT EXISTS mapping_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                mapping_type TEXT NOT NULL,
                internal_name TEXT NOT NULL,
                external_id TEXT,
                device_id TEXT,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                created_at REAL,
                updated_at REAL,
                UNIQUE(service_name, mapping_type, internal_name)
            );
            
            CREATE INDEX IF NOT EXISTS idx_mapping_service ON mapping_registry(service_name);
            CREATE INDEX IF NOT EXISTS idx_mapping_type ON mapping_registry(mapping_type);
            CREATE INDEX IF NOT EXISTS idx_mapping_internal ON mapping_registry(internal_name);
            CREATE INDEX IF NOT EXISTS idx_mapping_external ON mapping_registry(external_id);
            
            CREATE TABLE IF NOT EXISTS config_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                config TEXT,
                config_hash TEXT,
                change_type TEXT,
                changed_by TEXT,
                changed_at REAL,
                previous_version INTEGER,
                created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
                UNIQUE(entity_type, entity_id, version)
            );
            
            CREATE INDEX IF NOT EXISTS idx_config_versions_entity ON config_versions(entity_type, entity_id);
        """)
        logger.info("Metadata tables created/verified")

    async def _migrate_add_columns(self) -> None:
        """Add new columns to existing table if they don't exist."""
        if not self._db:
            return
        try:
            async with self._db.execute("PRAGMA table_info(readings)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            
            if "standard_points" not in columns:
                await self._db.execute("ALTER TABLE readings ADD COLUMN standard_points TEXT")
                logger.info("Added standard_points column to readings table")
            
            if "device_status" not in columns:
                await self._db.execute("ALTER TABLE readings ADD COLUMN device_status TEXT")
                logger.info("Added device_status column to readings table")
            
            async with self._db.execute("PRAGMA table_info(device_registry)") as cursor:
                device_columns = [row[1] for row in await cursor.fetchall()]
            
            device_new_columns = {
                'name': 'TEXT',
                'description': 'TEXT',
                'plugin_name': 'TEXT',
                'plugin_config': 'TEXT',
                'enabled': 'BOOLEAN DEFAULT TRUE',
                'metadata': 'TEXT',
                'tags': 'TEXT',
                'config_path': 'TEXT'
            }
            
            for col_name, col_type in device_new_columns.items():
                if col_name not in device_columns:
                    await self._db.execute(f"ALTER TABLE device_registry ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Added {col_name} column to device_registry table")
            
            async with self._db.execute("PRAGMA table_info(point_registry)") as cursor:
                point_columns = [row[1] for row in await cursor.fetchall()]
            
            point_new_columns = {
                'description': 'TEXT',
                'config': 'TEXT',
                'metadata': 'TEXT',
                'tags': 'TEXT',
                'enabled': 'BOOLEAN DEFAULT TRUE'
            }
            
            for col_name, col_type in point_new_columns.items():
                if col_name not in point_columns:
                    await self._db.execute(f"ALTER TABLE point_registry ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Added {col_name} column to point_registry table")
                
        except Exception as e:
            logger.warning(f"Migration check failed (this is normal for new databases): {e}")

    async def save_batch(self, readings: List[Reading]) -> int:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        if not readings:
            return 0
        
        values = []
        skipped = 0
        for reading in readings:
            try:
                values.append((
                    reading.asset,
                    reading.timestamp,
                    reading.service_name,
                    json.dumps(reading.data),
                    json.dumps(reading.tags),
                    json.dumps(reading.standard_points) if reading.standard_points else None,
                    reading.device_status
                ))
            except Exception as e:
                skipped += 1
                logger.warning(f"Error serializing reading (asset={reading.asset}): {e}")
        
        if skipped > 0:
            logger.warning(f"Skipped {skipped}/{len(readings)} readings due to serialization errors")
        
        if not values:
            raise RuntimeError(f"All {len(readings)} readings failed to serialize")
        
        try:
            await self._db.executemany(
                """
                INSERT INTO readings (asset, timestamp, service_name, data, tags, standard_points, device_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values
            )
            await self._db.commit()
        except Exception as e:
            logger.error(f"Error saving batch: {e}")
            raise
        
        logger.debug(f"Saved {len(values)} readings to SQLite")
        return len(values)

    async def query(
        self,
        asset: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        active_only: bool = False
    ) -> List[Reading]:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        conditions = []
        params = []
        
        if asset:
            conditions.append("r.asset = ?")
            params.append(asset)
        
        if start_time is not None:
            conditions.append("r.timestamp >= ?")
            params.append(start_time)
        
        if end_time is not None:
            conditions.append("r.timestamp <= ?")
            params.append(end_time)
        
        if active_only:
            conditions.append("d.status = 'active'")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        if active_only:
            query = f"""
                SELECT r.asset, r.timestamp, r.service_name, r.data, r.tags, r.standard_points, r.device_status
                FROM readings r
                INNER JOIN device_registry d ON r.asset = d.asset
                WHERE {where_clause}
                ORDER BY r.timestamp DESC
                LIMIT ?
            """
        else:
            query = f"""
                SELECT r.asset, r.timestamp, r.service_name, r.data, r.tags, r.standard_points, r.device_status
                FROM readings r
                WHERE {where_clause}
                ORDER BY r.timestamp DESC
                LIMIT ?
            """
        
        readings = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                readings.append(Reading(
                    asset=row[0],
                    timestamp=row[1],
                    service_name=row[2],
                    data=json.loads(row[3]),
                    tags=json.loads(row[4]) if row[4] else [],
                    standard_points=json.loads(row[5]) if row[5] else [],
                    device_status=row[6]
                ))
        
        return readings

    async def delete_old_readings(self, before_timestamp: float) -> int:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        async with self._db.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM readings WHERE timestamp < ?",
                (before_timestamp,)
            )
            deleted = cursor.rowcount
            await self._db.commit()
        
        logger.info(f"Deleted {deleted} readings before {before_timestamp}")
        return deleted

    async def delete_old_readings_batch(
        self,
        before_timestamp: float,
        batch_size: int = 10000
    ) -> int:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        total_deleted = 0
        
        while True:
            async with self._db.cursor() as cursor:
                await cursor.execute(
                    """
                    DELETE FROM readings 
                    WHERE id IN (
                        SELECT id FROM readings 
                        WHERE timestamp < ? 
                        LIMIT ?
                    )
                    """,
                    (before_timestamp, batch_size)
                )
                deleted = cursor.rowcount
                await self._db.commit()
                total_deleted += deleted
                
                if deleted < batch_size:
                    break
                
                await asyncio.sleep(0.1)
        
        if total_deleted > 0:
            logger.info(f"Batch deleted {total_deleted} readings before {before_timestamp}")
        return total_deleted

    async def get_storage_size(self) -> Dict[str, Any]:
        if not self._initialized or not self._db:
            return {"status": "not_initialized"}
        
        db_path = Path(self._database_path)
        db_size = db_path.stat().st_size if db_path.exists() else 0
        
        wal_path = Path(str(db_path) + "-wal")
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0
        
        shm_path = Path(str(db_path) + "-shm")
        shm_size = shm_path.stat().st_size if shm_path.exists() else 0
        
        async with self._db.execute("SELECT COUNT(*) FROM readings") as cursor:
            row = await cursor.fetchone()
            total_count = row[0] if row else 0
        
        return {
            "status": "ok",
            "database_file": self._database_path,
            "database_size_bytes": db_size,
            "database_size_mb": round(db_size / (1024 * 1024), 2),
            "wal_size_bytes": wal_size,
            "shm_size_bytes": shm_size,
            "total_size_bytes": db_size + wal_size + shm_size,
            "total_size_mb": round((db_size + wal_size + shm_size) / (1024 * 1024), 2),
            "total_readings": total_count
        }

    async def vacuum(self) -> None:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        logger.info("Starting VACUUM operation...")
        await self._db.execute("VACUUM")
        await self._db.commit()
        logger.info("VACUUM completed")

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False
            logger.info("SQLite storage closed")

    async def get_stats(self, include_device_status: bool = False) -> Dict[str, Any]:
        if not self._initialized or not self._db:
            return {"status": "not_initialized"}
        
        async with self._db.execute("SELECT COUNT(*) FROM readings") as cursor:
            row = await cursor.fetchone()
            total_count = row[0] if row else 0
        
        async with self._db.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM readings"
        ) as cursor:
            row = await cursor.fetchone()
            min_ts, max_ts = row if row else (None, None)
        
        async with self._db.execute(
            "SELECT COUNT(DISTINCT asset) FROM readings"
        ) as cursor:
            row = await cursor.fetchone()
            asset_count = row[0] if row else 0
        
        result = {
            "status": "ok",
            "total_readings": total_count,
            "unique_assets": asset_count,
            "time_range": {
                "start": min_ts,
                "end": max_ts
            }
        }
        
        if include_device_status:
            async with self._db.execute(
                "SELECT COUNT(*) FROM device_registry WHERE status = 'active'"
            ) as cursor:
                row = await cursor.fetchone()
                active_devices = row[0] if row else 0
            
            async with self._db.execute(
                "SELECT COUNT(*) FROM device_registry WHERE status = 'deleted'"
            ) as cursor:
                row = await cursor.fetchone()
                deleted_devices = row[0] if row else 0
            
            result["devices"] = {
                "active": active_devices,
                "deleted": deleted_devices,
                "total": active_devices + deleted_devices
            }
        
        return result

    async def get_latest_readings_by_device(self, active_only: bool = False) -> List[Reading]:
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        if active_only:
            query = """
                SELECT r.asset, r.timestamp, r.service_name, r.data, r.tags, r.standard_points, r.device_status
                FROM readings r
                INNER JOIN (
                    SELECT asset, MAX(timestamp) as max_ts
                    FROM readings
                    GROUP BY asset
                ) latest ON r.asset = latest.asset AND r.timestamp = latest.max_ts
                LEFT JOIN device_registry d ON r.asset = d.asset
                WHERE d.asset IS NULL OR d.status = 'active'
                ORDER BY r.asset
            """
        else:
            query = """
                SELECT r.asset, r.timestamp, r.service_name, r.data, r.tags, r.standard_points, r.device_status
                FROM readings r
                INNER JOIN (
                    SELECT asset, MAX(timestamp) as max_ts
                    FROM readings
                    GROUP BY asset
                ) latest ON r.asset = latest.asset AND r.timestamp = latest.max_ts
                ORDER BY r.asset
            """
        
        readings = []
        async with self._db.execute(query) as cursor:
            async for row in cursor:
                readings.append(Reading(
                    asset=row[0],
                    timestamp=row[1],
                    service_name=row[2],
                    data=json.loads(row[3]),
                    tags=json.loads(row[4]) if row[4] else [],
                    standard_points=json.loads(row[5]) if row[5] else [],
                    device_status=row[6]
                ))
        
        return readings
    
    async def get_quality_stats(self) -> Dict[str, Any]:
        """获取数据质量统计

        Returns:
            数据质量统计字典，包含：
            - good: 良好数据点数
            - bad: 不良数据点数
            - uncertain: 不确定数据点数
            - total: 总数据点数
        """
        if not self._initialized or not self._db:
            return {"good": 0, "bad": 0, "uncertain": 0, "total": 0}

        try:
            # 先获取总记录数，决定使用哪种策略
            async with self._db.execute("SELECT COUNT(*) FROM readings") as cursor:
                row = await cursor.fetchone()
                total_records = row[0] if row else 0

            # 轻量级网关场景：数据量通常不大，使用智能策略
            if total_records < DataConstants.QUALITY_STATS_THRESHOLD:
                # 数据量小：完整扫描
                return await self._get_quality_stats_full_scan()
            else:
                # 数据量大：采样统计（最近N条）
                return await self._get_quality_stats_sample()

        except Exception as e:
            logger.error(f"Failed to get quality stats: {e}")
            return {"good": 0, "bad": 0, "uncertain": 0, "total": 0}

    def _process_quality_rows(self, rows: list) -> Dict[str, int]:
        """处理质量统计行数据的公共方法

        Args:
            rows: 数据库查询结果行

        Returns:
            质量统计字典
        """
        stats = {"good": 0, "bad": 0, "uncertain": 0, "total": 0}

        # 遍历每条记录的standard_points
        for row in rows:
            if row[0]:
                try:
                    # 解析JSON数据
                    points = json.loads(row[0])

                    # 统计每个数据点的质量
                    for point in points:
                        quality = point.get("quality", "good").lower()
                        stats["total"] += 1

                        if quality == "good":
                            stats["good"] += 1
                        elif quality == "bad":
                            stats["bad"] += 1
                        elif quality == "uncertain":
                            stats["uncertain"] += 1
                        else:
                            # 未知质量标记为uncertain
                            stats["uncertain"] += 1
                except (json.JSONDecodeError, TypeError) as e:
                    # JSON解析失败，跳过该记录
                    logger.warning(f"Failed to parse standard_points: {e}")
                    continue

        return stats

    async def _get_quality_stats_full_scan(self) -> Dict[str, int]:
        """完整扫描统计（适用于小数据量）

        Returns:
            数据质量统计字典
        """
        async with self._db.execute(
            "SELECT standard_points FROM readings WHERE standard_points IS NOT NULL"
        ) as cursor:
            rows = await cursor.fetchall()

        stats = self._process_quality_rows(rows)
        logger.debug(f"Quality stats (full scan): {stats}")
        return stats

    async def _get_quality_stats_sample(self) -> Dict[str, int]:
        """采样统计（适用于大数据量）

        Returns:
            数据质量统计字典
        """
        # 只统计最近N条记录
        async with self._db.execute(
            f"""SELECT standard_points FROM readings
               WHERE standard_points IS NOT NULL
               ORDER BY timestamp DESC
               LIMIT {DataConstants.QUALITY_STATS_SAMPLE_LIMIT}"""
        ) as cursor:
            rows = await cursor.fetchall()

        stats = self._process_quality_rows(rows)
        logger.debug(f"Quality stats (sample): {stats}")
        return stats
    
    async def count_readings_since(self, timestamp: float) -> int:
        """统计指定时间后的采集量
        
        Args:
            timestamp: Unix时间戳
            
        Returns:
            采集量
        """
        if not self._initialized or not self._db:
            return 0
        
        try:
            async with self._db.execute(
                "SELECT COUNT(*) FROM readings WHERE timestamp >= ?",
                (timestamp,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to count readings since {timestamp}: {e}")
            return 0
    
    async def count_readings_in_range(
        self,
        start_time: float,
        end_time: float
    ) -> int:
        """统计时间范围内的采集量
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            采集量
        """
        if not self._initialized or not self._db:
            return 0
        
        try:
            async with self._db.execute(
                "SELECT COUNT(*) FROM readings WHERE timestamp >= ? AND timestamp < ?",
                (start_time, end_time)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to count readings in range: {e}")
            return 0
    
    def get_connection(self) -> Optional[aiosqlite.Connection]:
        """Get the internal database connection.
        
        [DEPRECATED] This method exposes internal implementation details
        and breaks the StorageInterface abstraction. Use StorageInterface
        methods instead.
        """
        import warnings
        warnings.warn(
            "get_connection() is deprecated. Use StorageInterface methods instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._db
    
    async def _run_migrations(self) -> None:
        """运行数据库迁移"""
        try:
            from .migrations.v2_config_versioning import run_migration
            await run_migration(self._db)
        except Exception as e:
            logger.warning(f"Migration check failed (this is normal for new databases): {e}")
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    async def export_config_tables(self, output_db_path: str) -> Dict[str, Any]:
        """导出配置表到新数据库（不包含历史数据）
        
        使用逐表复制的方式，避免长时间锁定数据库
        
        Args:
            output_db_path: 输出数据库路径
            
        Returns:
            导出结果，包含表数量、记录数等信息
        """
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        # 配置表列表（不包含历史数据表）
        config_tables = [
            'device_registry',
            'point_registry',
            'plugin_registry',
            'service_registry',
            'rule_registry',
            'channel_registry',
            'pipeline_registry',
            'config_versions',
            'audit_logs',
            'mapping_registry'
        ]
        
        output_db = None
        stats = {"tables": 0, "records": 0, "table_details": {}}
        
        try:
            # 创建输出数据库
            output_db = await aiosqlite.connect(output_db_path)
            await output_db.execute("PRAGMA journal_mode=WAL")
            
            # 导出每个表
            for table in config_tables:
                try:
                    # 检查表是否存在
                    async with self._db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    ) as cursor:
                        if not await cursor.fetchone():
                            continue
                    
                    # 获取表结构
                    async with self._db.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if not row or not row[0]:
                            continue
                        
                        # 创建表
                        await output_db.execute(row[0])
                    
                    # 读取数据并写入（分批处理，避免长时间锁定）
                    batch_size = 1000
                    total_count = 0

                    # 获取列名
                    async with self._db.execute(f"PRAGMA table_info({table})") as cursor:
                        columns_info = await cursor.fetchall()
                        columns = [row[1] for row in columns_info]

                    # 检查是否有id列（用于基于主键的分页）
                    has_id_column = any(col[1] == 'id' for col in columns_info)

                    if has_id_column:
                        # 使用基于主键的分页（性能更好）
                        last_id = 0
                        while True:
                            async with self._db.execute(
                                f"SELECT * FROM {table} WHERE id > ? ORDER BY id LIMIT ?",
                                (last_id, batch_size)
                            ) as cursor:
                                rows = await cursor.fetchall()

                                if not rows:
                                    break

                                # 构建INSERT语句
                                placeholders = ','.join(['?' for _ in columns])
                                await output_db.executemany(
                                    f"INSERT INTO {table} VALUES ({placeholders})",
                                    rows
                                )

                                total_count += len(rows)
                                last_id = rows[-1][0]  # 更新last_id为最后一条记录的id
                    else:
                        # 回退到LIMIT OFFSET方式（兼容没有id列的表）
                        offset = 0
                        async with self._db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                            total_records = (await cursor.fetchone())[0]

                        while offset < total_records:
                            async with self._db.execute(
                                f"SELECT * FROM {table} LIMIT ? OFFSET ?",
                                (batch_size, offset)
                            ) as cursor:
                                rows = await cursor.fetchall()

                                if not rows:
                                    break

                                # 构建INSERT语句
                                placeholders = ','.join(['?' for _ in columns])
                                await output_db.executemany(
                                    f"INSERT INTO {table} VALUES ({placeholders})",
                                    rows
                                )

                                total_count += len(rows)
                                offset += batch_size
                    
                    # 导出索引
                    async with self._db.execute(
                        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                        (table,)
                    ) as cursor:
                        async for row in cursor:
                            if row[0]:
                                try:
                                    await output_db.execute(row[0])
                                except:
                                    pass
                    
                    stats["tables"] += 1
                    stats["records"] += total_count
                    stats["table_details"][table] = total_count
                    
                    logger.debug(f"Exported table {table}: {total_count} records")
                        
                except Exception as e:
                    logger.error(f"Failed to export table {table}: {e}")
                    continue
            
            await output_db.commit()
            
            logger.info(f"Config tables exported: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to export config tables: {e}")
            raise
        finally:
            # 关闭输出数据库
            if output_db:
                try:
                    await output_db.close()
                except Exception as e:
                    logger.warning(f"Failed to close output database: {e}")
    
    async def import_config_tables(self, source_db_path: str) -> Dict[str, Any]:
        """从外部数据库导入配置表
        
        使用逐表复制的方式，避免长时间锁定数据库
        
        Args:
            source_db_path: 源数据库路径
            
        Returns:
            导入结果，包含表数量、记录数等信息
        """
        if not self._initialized or not self._db:
            raise RuntimeError("Storage not initialized")
        
        if not Path(source_db_path).exists():
            raise FileNotFoundError(f"Source database not found: {source_db_path}")
        
        # 配置表列表
        config_tables = [
            'device_registry',
            'point_registry',
            'plugin_registry',
            'service_registry',
            'rule_registry',
            'channel_registry',
            'pipeline_registry',
            'config_versions',
            'audit_logs',
            'mapping_registry'
        ]
        
        source_db = None
        stats = {"tables": 0, "records": 0, "table_details": {}}
        
        try:
            # 打开源数据库
            source_db = await aiosqlite.connect(source_db_path)
            
            # 开始事务
            await self._db.execute("BEGIN TRANSACTION")
            
            # 禁用外键约束
            await self._db.execute("PRAGMA foreign_keys=OFF")
            
            # 导入每个表
            for table in config_tables:
                try:
                    # 检查源表是否存在
                    async with source_db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    ) as cursor:
                        if not await cursor.fetchone():
                            continue
                    
                    # 清空目标表
                    await self._db.execute(f"DELETE FROM main.{table}")

                    # 分批读取并写入
                    batch_size = 1000
                    total_count = 0

                    # 获取列名
                    async with source_db.execute(f"PRAGMA table_info({table})") as cursor:
                        columns_info = await cursor.fetchall()
                        columns = [row[1] for row in columns_info]

                    # 检查是否有id列（用于基于主键的分页）
                    has_id_column = any(col[1] == 'id' for col in columns_info)

                    if has_id_column:
                        # 使用基于主键的分页（性能更好）
                        last_id = 0
                        while True:
                            async with source_db.execute(
                                f"SELECT * FROM {table} WHERE id > ? ORDER BY id LIMIT ?",
                                (last_id, batch_size)
                            ) as cursor:
                                rows = await cursor.fetchall()

                                if not rows:
                                    break

                                # 构建INSERT语句
                                placeholders = ','.join(['?' for _ in columns])
                                await self._db.executemany(
                                    f"INSERT INTO main.{table} VALUES ({placeholders})",
                                    rows
                                )

                                total_count += len(rows)
                                last_id = rows[-1][0]  # 更新last_id为最后一条记录的id
                    else:
                        # 回退到LIMIT OFFSET方式（兼容没有id列的表）
                        offset = 0
                        async with source_db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                            total_records = (await cursor.fetchone())[0]

                        while offset < total_records:
                            async with source_db.execute(
                                f"SELECT * FROM {table} LIMIT ? OFFSET ?",
                                (batch_size, offset)
                            ) as cursor:
                                rows = await cursor.fetchall()

                                if not rows:
                                    break

                                # 构建INSERT语句
                                placeholders = ','.join(['?' for _ in columns])
                                await self._db.executemany(
                                    f"INSERT INTO main.{table} VALUES ({placeholders})",
                                    rows
                                )

                                total_count += len(rows)
                                offset += batch_size
                    
                    stats["tables"] += 1
                    stats["records"] += total_count
                    stats["table_details"][table] = total_count
                    
                    logger.debug(f"Imported table {table}: {total_count} records")
                        
                except Exception as e:
                    logger.error(f"Failed to import table {table}: {e}")
                    continue
            
            # 启用外键约束
            await self._db.execute("PRAGMA foreign_keys=ON")
            
            # 提交事务
            await self._db.commit()
            
            logger.info(f"Config tables imported: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to import config tables: {e}")
            # 回滚事务
            try:
                await self._db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Failed to rollback: {rollback_error}")
            raise
        finally:
            # 关闭源数据库
            if source_db:
                try:
                    await source_db.close()
                except Exception as e:
                    logger.warning(f"Failed to close source database: {e}")
