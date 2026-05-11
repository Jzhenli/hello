"""Metadata Manager - Device and Point registry management"""

import hashlib
import logging
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import aiosqlite

logger = logging.getLogger(__name__)


class RegistryStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


@dataclass
class DeviceRecord:
    asset: str
    service_name: str
    config_hash: str
    status: RegistryStatus = RegistryStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deleted_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "service_name": self.service_name,
            "config_hash": self.config_hash,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }


@dataclass
class PointRecord:
    asset: str
    point_name: str
    data_type: Optional[str] = None
    unit: Optional[str] = None
    config_hash: str = ""
    status: RegistryStatus = RegistryStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deleted_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "point_name": self.point_name,
            "data_type": self.data_type,
            "unit": self.unit,
            "config_hash": self.config_hash,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }


@dataclass
class ConfigDiff:
    added_devices: Set[str] = field(default_factory=set)
    removed_devices: Set[str] = field(default_factory=set)
    modified_devices: Set[str] = field(default_factory=set)
    added_points: Dict[str, Set[str]] = field(default_factory=dict)
    removed_points: Dict[str, Set[str]] = field(default_factory=dict)
    modified_points: Dict[str, Set[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "added_devices": list(self.added_devices),
            "removed_devices": list(self.removed_devices),
            "modified_devices": list(self.modified_devices),
            "added_points": {k: list(v) for k, v in self.added_points.items()},
            "removed_points": {k: list(v) for k, v in self.removed_points.items()},
            "modified_points": {k: list(v) for k, v in self.modified_points.items()}
        }
    
    def has_changes(self) -> bool:
        return bool(
            self.added_devices or 
            self.removed_devices or 
            self.modified_devices or
            self.added_points or 
            self.removed_points or 
            self.modified_points
        )


class MetadataManager:
    _instance: Optional['MetadataManager'] = None
    
    @classmethod
    def get_instance(cls, db_connection: Optional[aiosqlite.Connection] = None) -> 'MetadataManager':
        """获取全局单例实例
        
        [DEPRECATED] 优先通过 DI 容器管理实例。此方法作为向后兼容的过渡方案，
        后续应统一使用 Container.resolve() 获取实例。
        """
        warnings.warn(
            "MetadataManager.get_instance() is deprecated. Use DI container instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self, db_connection: Optional[aiosqlite.Connection] = None):
        self._db: Optional[aiosqlite.Connection] = None
        self._owns_connection = False
    
    @classmethod
    def reset_instance(cls):
        cls._instance = None
    
    async def initialize(self, db_connection: Optional[aiosqlite.Connection] = None, storage: Optional[Any] = None) -> None:
        if self._db is not None:
            return
        
        if db_connection:
            self._db = db_connection
            self._owns_connection = False
        elif storage is not None:
            self._db = storage._db
            self._owns_connection = False
        else:
            raise ValueError("Database connection or storage is required for initialization")
        
        logger.info("MetadataManager initialized with shared database connection")
    
    def _compute_hash(self, config: Dict[str, Any]) -> str:
        import json
        content = json.dumps(config, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
    
    async def sync_from_config(
        self,
        plugin_configs: Dict[str, List[Dict[str, Any]]]
    ) -> ConfigDiff:
        if self._db is None:
            raise RuntimeError("MetadataManager not initialized")
        
        diff = ConfigDiff()
        current_time = time.time()
        
        current_devices = await self._get_active_devices()
        new_devices: Set[str] = set()
        
        for plugin_type, plugins in plugin_configs.items():
            for plugin_config in plugins:
                if not plugin_config.get("enabled", True):
                    continue
                
                config = plugin_config.get("config", {})
                asset = config.get("asset_name") or plugin_config.get("name", "unknown")
                service_name = plugin_config.get("name", "unknown")
                config_hash = self._compute_hash(plugin_config)
                
                new_devices.add(asset)
                
                existing = await self._get_device(asset)
                
                if existing is None:
                    await self._add_device(DeviceRecord(
                        asset=asset,
                        service_name=service_name,
                        config_hash=config_hash,
                        created_at=current_time,
                        updated_at=current_time
                    ))
                    diff.added_devices.add(asset)
                    logger.info(f"Device added: {asset}")
                
                elif existing.status == RegistryStatus.DELETED:
                    await self._restore_device(asset, service_name, config_hash, current_time)
                    diff.added_devices.add(asset)
                    logger.info(f"Device restored: {asset}")
                
                elif existing.config_hash != config_hash:
                    await self._update_device(asset, config_hash, current_time)
                    diff.modified_devices.add(asset)
                    logger.info(f"Device modified: {asset}")
                
                await self._sync_points(asset, config, diff, current_time)
        
        removed_devices = current_devices - new_devices
        for asset in removed_devices:
            await self._soft_delete_device(asset, current_time)
            diff.removed_devices.add(asset)
            logger.info(f"Device removed (soft delete): {asset}")
        
        return diff
    
    async def _get_active_devices(self) -> Set[str]:
        async with self._db.execute(
            "SELECT asset FROM device_registry WHERE status = 'active'"
        ) as cursor:
            return {row[0] for row in await cursor.fetchall()}
    
    async def _get_device(self, asset: str) -> Optional[DeviceRecord]:
        async with self._db.execute(
            "SELECT asset, service_name, config_hash, status, created_at, updated_at, deleted_at "
            "FROM device_registry WHERE asset = ?",
            (asset,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return DeviceRecord(
                    asset=row[0],
                    service_name=row[1],
                    config_hash=row[2],
                    status=RegistryStatus(row[3]),
                    created_at=row[4],
                    updated_at=row[5],
                    deleted_at=row[6]
                )
            return None
    
    async def get_device(self, asset: str) -> Optional[DeviceRecord]:
        return await self._get_device(asset)
    
    async def _add_device(self, device: DeviceRecord) -> None:
        await self._db.execute(
            "INSERT INTO device_registry (asset, service_name, config_hash, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (device.asset, device.service_name, device.config_hash, 
             device.status.value, device.created_at, device.updated_at)
        )
        await self._db.commit()
    
    async def _update_device(self, asset: str, config_hash: str, updated_at: float) -> None:
        await self._db.execute(
            "UPDATE device_registry SET config_hash = ?, updated_at = ? WHERE asset = ?",
            (config_hash, updated_at, asset)
        )
        await self._db.commit()
    
    async def _restore_device(self, asset: str, service_name: str, config_hash: str, updated_at: float) -> None:
        await self._db.execute(
            "UPDATE device_registry SET status = 'active', service_name = ?, config_hash = ?, "
            "updated_at = ?, deleted_at = NULL WHERE asset = ?",
            (service_name, config_hash, updated_at, asset)
        )
        await self._db.commit()
    
    async def _soft_delete_device(self, asset: str, deleted_at: float) -> None:
        await self._db.execute(
            "UPDATE device_registry SET status = 'deleted', deleted_at = ? WHERE asset = ?",
            (deleted_at, asset)
        )
        await self._db.execute(
            "UPDATE point_registry SET status = 'deleted', deleted_at = ? WHERE asset = ? AND status = 'active'",
            (deleted_at, asset)
        )
        await self._db.commit()
    
    async def _sync_points(
        self,
        asset: str,
        config: Dict[str, Any],
        diff: ConfigDiff,
        current_time: float
    ) -> None:
        point_configs = config.get("points", [])
        current_points = await self._get_active_points(asset)
        new_points: Set[str] = set()
        
        for point_config in point_configs:
            point_name = point_config.get("name") or point_config.get("point_name")
            if not point_name:
                continue
            
            new_points.add(point_name)
            config_hash = self._compute_hash(point_config)
            
            existing = await self._get_point(asset, point_name)
            
            if existing is None:
                await self._add_point(PointRecord(
                    asset=asset,
                    point_name=point_name,
                    data_type=point_config.get("data_type"),
                    unit=point_config.get("unit"),
                    config_hash=config_hash,
                    created_at=current_time,
                    updated_at=current_time
                ))
                if asset not in diff.added_points:
                    diff.added_points[asset] = set()
                diff.added_points[asset].add(point_name)
            
            elif existing.status == RegistryStatus.DELETED:
                await self._restore_point(asset, point_name, config_hash, current_time)
                if asset not in diff.added_points:
                    diff.added_points[asset] = set()
                diff.added_points[asset].add(point_name)
            
            elif existing.config_hash != config_hash:
                await self._update_point(asset, point_name, config_hash, current_time)
                if asset not in diff.modified_points:
                    diff.modified_points[asset] = set()
                diff.modified_points[asset].add(point_name)
        
        removed_points = current_points - new_points
        for point_name in removed_points:
            await self._soft_delete_point(asset, point_name, current_time)
            if asset not in diff.removed_points:
                diff.removed_points[asset] = set()
            diff.removed_points[asset].add(point_name)
    
    async def _get_active_points(self, asset: str) -> Set[str]:
        async with self._db.execute(
            "SELECT point_name FROM point_registry WHERE asset = ? AND status = 'active'",
            (asset,)
        ) as cursor:
            return {row[0] for row in await cursor.fetchall()}
    
    async def _get_point(self, asset: str, point_name: str) -> Optional[PointRecord]:
        async with self._db.execute(
            "SELECT asset, point_name, data_type, unit, config_hash, status, created_at, updated_at, deleted_at "
            "FROM point_registry WHERE asset = ? AND point_name = ?",
            (asset, point_name)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return PointRecord(
                    asset=row[0],
                    point_name=row[1],
                    data_type=row[2],
                    unit=row[3],
                    config_hash=row[4],
                    status=RegistryStatus(row[5]),
                    created_at=row[6],
                    updated_at=row[7],
                    deleted_at=row[8]
                )
            return None
    
    async def get_point(self, asset: str, point_name: str) -> Optional[PointRecord]:
        return await self._get_point(asset, point_name)
    
    async def _add_point(self, point: PointRecord) -> None:
        await self._db.execute(
            "INSERT INTO point_registry (asset, point_name, data_type, unit, config_hash, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (point.asset, point.point_name, point.data_type, point.unit,
             point.config_hash, point.status.value, point.created_at, point.updated_at)
        )
        await self._db.commit()
    
    async def _update_point(self, asset: str, point_name: str, config_hash: str, updated_at: float) -> None:
        await self._db.execute(
            "UPDATE point_registry SET config_hash = ?, updated_at = ? WHERE asset = ? AND point_name = ?",
            (config_hash, updated_at, asset, point_name)
        )
        await self._db.commit()
    
    async def _restore_point(self, asset: str, point_name: str, config_hash: str, updated_at: float) -> None:
        await self._db.execute(
            "UPDATE point_registry SET status = 'active', config_hash = ?, "
            "updated_at = ?, deleted_at = NULL WHERE asset = ? AND point_name = ?",
            (config_hash, updated_at, asset, point_name)
        )
        await self._db.commit()
    
    async def _soft_delete_point(self, asset: str, point_name: str, deleted_at: float) -> None:
        await self._db.execute(
            "UPDATE point_registry SET status = 'deleted', deleted_at = ? WHERE asset = ? AND point_name = ?",
            (deleted_at, asset, point_name)
        )
        await self._db.commit()
    
    async def get_device_status(self, asset: str) -> Optional[str]:
        async with self._db.execute(
            "SELECT status FROM device_registry WHERE asset = ?",
            (asset,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_all_active_devices(self) -> List[DeviceRecord]:
        async with self._db.execute(
            "SELECT asset, service_name, config_hash, status, created_at, updated_at, deleted_at "
            "FROM device_registry WHERE status = 'active'"
        ) as cursor:
            rows = await cursor.fetchall()
            return [DeviceRecord(
                asset=row[0], service_name=row[1], config_hash=row[2],
                status=RegistryStatus(row[3]), created_at=row[4], 
                updated_at=row[5], deleted_at=row[6]
            ) for row in rows]
    
    async def get_all_devices(self, status: Optional[str] = None) -> List[DeviceRecord]:
        if status:
            query = "SELECT asset, service_name, config_hash, status, created_at, updated_at, deleted_at " \
                    "FROM device_registry WHERE status = ?"
            params = (status,)
        else:
            query = "SELECT asset, service_name, config_hash, status, created_at, updated_at, deleted_at " \
                    "FROM device_registry"
            params = ()
        
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [DeviceRecord(
                asset=row[0], service_name=row[1], config_hash=row[2],
                status=RegistryStatus(row[3]), created_at=row[4], 
                updated_at=row[5], deleted_at=row[6]
            ) for row in rows]
    
    async def get_device_points(self, asset: str, status: Optional[str] = None) -> List[PointRecord]:
        if status:
            query = "SELECT asset, point_name, data_type, unit, config_hash, status, created_at, updated_at, deleted_at " \
                    "FROM point_registry WHERE asset = ? AND status = ?"
            params = (asset, status)
        else:
            query = "SELECT asset, point_name, data_type, unit, config_hash, status, created_at, updated_at, deleted_at " \
                    "FROM point_registry WHERE asset = ?"
            params = (asset,)
        
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [PointRecord(
                asset=row[0], point_name=row[1], data_type=row[2],
                unit=row[3], config_hash=row[4], status=RegistryStatus(row[5]),
                created_at=row[6], updated_at=row[7], deleted_at=row[8]
            ) for row in rows]
    
    async def get_points_stats(self) -> Dict[str, int]:
        if self._db is None:
            raise RuntimeError("MetadataManager not initialized")
        
        result = {"total_points": 0, "active_points": 0}
        
        async with self._db.execute(
            "SELECT status, COUNT(*) FROM point_registry GROUP BY status"
        ) as cursor:
            rows = await cursor.fetchall()
            for status, count in rows:
                result["total_points"] += count
                if status == "active":
                    result["active_points"] += count
        
        return result
    
    async def close(self) -> None:
        if self._owns_connection and self._db:
            await self._db.close()
        self._db = None
        logger.info("MetadataManager closed")
    
    @property
    def is_initialized(self) -> bool:
        return self._db is not None
