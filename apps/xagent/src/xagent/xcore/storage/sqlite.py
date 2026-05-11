"""SQLite Storage Implementation with async support"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from .interface import StorageInterface, Reading

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
            
            CREATE INDEX IF NOT EXISTS idx_device_asset ON device_registry(asset);
            CREATE INDEX IF NOT EXISTS idx_device_status ON device_registry(status);
            CREATE INDEX IF NOT EXISTS idx_device_enabled ON device_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_device_plugin ON device_registry(plugin_name);
            CREATE INDEX IF NOT EXISTS idx_point_asset ON point_registry(asset);
            CREATE INDEX IF NOT EXISTS idx_point_status ON point_registry(status);
            CREATE INDEX IF NOT EXISTS idx_point_enabled ON point_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_plugin_name ON plugin_registry(name);
            CREATE INDEX IF NOT EXISTS idx_plugin_type ON plugin_registry(type);
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
                SELECT asset, timestamp, service_name, data, tags, standard_points, device_status
                FROM readings
                WHERE {where_clause}
                ORDER BY timestamp DESC
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
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
