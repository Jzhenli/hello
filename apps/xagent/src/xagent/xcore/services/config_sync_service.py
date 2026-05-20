"""配置同步服务

支持多实例之间的配置同步，确保配置一致性。
"""

import logging
import time
import json
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import asyncio
import aiohttp
import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class SyncInstance:
    """同步实例"""
    name: str
    url: str
    api_token: Optional[str] = None
    last_sync: Optional[float] = None
    status: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "api_token": self.api_token,
            "last_sync": self.last_sync,
            "status": self.status
        }


@dataclass
class SyncResult:
    """同步结果"""
    instance_name: str
    success: bool
    synced_devices: int = 0
    synced_points: int = 0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_name": self.instance_name,
            "success": self.success,
            "synced_devices": self.synced_devices,
            "synced_points": self.synced_points,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "timestamp": self.timestamp
        }


class ConfigSyncService:
    """配置同步服务"""
    
    def __init__(
        self,
        db: aiosqlite.Connection,
        config_repo: Any,
        local_instance_name: str = "local"
    ):
        self._db = db
        self.config_repo = config_repo
        self.local_instance_name = local_instance_name
        self._instances: Dict[str, SyncInstance] = {}
        self._sync_lock = asyncio.Lock()
        self._ensure_table()
    
    async def _ensure_table(self) -> None:
        """确保同步表存在"""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS sync_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                api_token TEXT,
                last_sync REAL,
                status TEXT DEFAULT 'unknown'
            )
        """)
        
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_name TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                synced_devices INTEGER DEFAULT 0,
                synced_points INTEGER DEFAULT 0,
                conflicts TEXT,
                errors TEXT,
                timestamp REAL NOT NULL
            )
        """)
        
        await self._db.commit()
    
    async def register_instance(
        self,
        instance: SyncInstance
    ) -> None:
        """注册同步实例
        
        Args:
            instance: 同步实例配置
        """
        await self._db.execute(
            """
            INSERT OR REPLACE INTO sync_instances (name, url, api_token, last_sync, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                instance.name, instance.url, instance.api_token,
                instance.last_sync, instance.status
            )
        )
        await self._db.commit()
        
        self._instances[instance.name] = instance
        logger.info(f"Registered sync instance: {instance.name}")
    
    async def unregister_instance(
        self,
        instance_name: str
    ) -> None:
        """注销同步实例
        
        Args:
            instance_name: 实例名称
        """
        await self._db.execute(
            "DELETE FROM sync_instances WHERE name = ?",
            (instance_name,)
        )
        await self._db.commit()
        
        if instance_name in self._instances:
            del self._instances[instance_name]
        
        logger.info(f"Unregistered sync instance: {instance_name}")
    
    async def list_instances(self) -> List[SyncInstance]:
        """列出所有同步实例
        
        Returns:
            实例列表
        """
        async with self._db.execute(
            """
            SELECT name, url, api_token, last_sync, status
            FROM sync_instances
            ORDER BY name
            """
        ) as cursor:
            instances = []
            async for row in cursor:
                instances.append(SyncInstance(
                    name=row[0],
                    url=row[1],
                    api_token=row[2],
                    last_sync=row[3],
                    status=row[4]
                ))
            return instances
    
    async def sync_to_instance(
        self,
        instance_name: str,
        assets: Optional[List[str]] = None,
        force: bool = False
    ) -> SyncResult:
        """同步配置到指定实例
        
        Args:
            instance_name: 实例名称
            assets: 要同步的设备列表，None表示同步所有
            force: 是否强制同步（忽略冲突）
            
        Returns:
            同步结果
        """
        async with self._sync_lock:
            instance = await self._get_instance(instance_name)
            if not instance:
                return SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=["Instance not found"]
                )
            
            try:
                local_devices = await self._get_local_devices(assets)
                
                remote_devices = await self._fetch_remote_devices(instance)
                
                conflicts = self._detect_conflicts(local_devices, remote_devices)
                
                if conflicts and not force:
                    return SyncResult(
                        instance_name=instance_name,
                        success=False,
                        conflicts=conflicts,
                        errors=["Conflicts detected, use force=True to override"]
                    )
                
                sync_result = await self._push_devices(instance, local_devices)
                
                await self._update_instance_status(instance_name, "success", time.time())
                
                await self._save_sync_history(sync_result)
                
                logger.info(f"Sync completed to {instance_name}: {sync_result.synced_devices} devices")
                return sync_result
            
            except Exception as e:
                error_result = SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=[str(e)]
                )
                
                await self._update_instance_status(instance_name, "error", time.time())
                await self._save_sync_history(error_result)
                
                logger.error(f"Sync failed to {instance_name}: {e}")
                return error_result
    
    async def sync_from_instance(
        self,
        instance_name: str,
        assets: Optional[List[str]] = None,
        force: bool = False
    ) -> SyncResult:
        """从指定实例同步配置
        
        Args:
            instance_name: 实例名称
            assets: 要同步的设备列表
            force: 是否强制同步
            
        Returns:
            同步结果
        """
        async with self._sync_lock:
            instance = await self._get_instance(instance_name)
            if not instance:
                return SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=["Instance not found"]
                )
            
            try:
                remote_devices = await self._fetch_remote_devices(instance, assets)
                
                local_devices = await self._get_local_devices(assets)
                
                conflicts = self._detect_conflicts(remote_devices, local_devices)
                
                if conflicts and not force:
                    return SyncResult(
                        instance_name=instance_name,
                        success=False,
                        conflicts=conflicts,
                        errors=["Conflicts detected, use force=True to override"]
                    )
                
                sync_result = await self._import_devices(remote_devices)
                
                await self._update_instance_status(instance_name, "success", time.time())
                
                await self._save_sync_history(sync_result)
                
                logger.info(f"Sync completed from {instance_name}: {sync_result.synced_devices} devices")
                return sync_result
            
            except Exception as e:
                error_result = SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=[str(e)]
                )
                
                await self._update_instance_status(instance_name, "error", time.time())
                await self._save_sync_history(error_result)
                
                logger.error(f"Sync failed from {instance_name}: {e}")
                return error_result
    
    async def bidirectional_sync(
        self,
        instance_name: str,
        strategy: str = "latest"
    ) -> SyncResult:
        """双向同步
        
        Args:
            instance_name: 实例名称
            strategy: 冲突解决策略 ('latest', 'local', 'remote')
            
        Returns:
            同步结果
        """
        async with self._sync_lock:
            instance = await self._get_instance(instance_name)
            if not instance:
                return SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=["Instance not found"]
                )
            
            try:
                local_devices = await self._get_local_devices()
                remote_devices = await self._fetch_remote_devices(instance)
                
                merged_devices = self._merge_devices(
                    local_devices,
                    remote_devices,
                    strategy
                )
                
                push_result = await self._push_devices(instance, merged_devices)
                
                import_result = await self._import_devices(merged_devices)
                
                sync_result = SyncResult(
                    instance_name=instance_name,
                    success=True,
                    synced_devices=push_result.synced_devices,
                    synced_points=push_result.synced_points
                )
                
                await self._update_instance_status(instance_name, "success", time.time())
                await self._save_sync_history(sync_result)
                
                logger.info(f"Bidirectional sync completed with {instance_name}")
                return sync_result
            
            except Exception as e:
                error_result = SyncResult(
                    instance_name=instance_name,
                    success=False,
                    errors=[str(e)]
                )
                
                await self._update_instance_status(instance_name, "error", time.time())
                await self._save_sync_history(error_result)
                
                logger.error(f"Bidirectional sync failed with {instance_name}: {e}")
                return error_result
    
    async def get_sync_history(
        self,
        instance_name: Optional[str] = None,
        limit: int = 100
    ) -> List[SyncResult]:
        """获取同步历史
        
        Args:
            instance_name: 实例名称，None表示所有实例
            limit: 返回数量限制
            
        Returns:
            同步历史列表
        """
        if instance_name:
            query = """
                SELECT instance_name, success, synced_devices, synced_points,
                       conflicts, errors, timestamp
                FROM sync_history
                WHERE instance_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (instance_name, limit)
        else:
            query = """
                SELECT instance_name, success, synced_devices, synced_points,
                       conflicts, errors, timestamp
                FROM sync_history
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (limit,)
        
        async with self._db.execute(query, params) as cursor:
            results = []
            async for row in cursor:
                results.append(SyncResult(
                    instance_name=row[0],
                    success=bool(row[1]),
                    synced_devices=row[2],
                    synced_points=row[3],
                    conflicts=json.loads(row[4]) if row[4] else [],
                    errors=json.loads(row[5]) if row[5] else [],
                    timestamp=row[6]
                ))
            return results
    
    async def _get_instance(self, instance_name: str) -> Optional[SyncInstance]:
        """获取实例配置"""
        async with self._db.execute(
            """
            SELECT name, url, api_token, last_sync, status
            FROM sync_instances
            WHERE name = ?
            """,
            (instance_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return SyncInstance(
                    name=row[0],
                    url=row[1],
                    api_token=row[2],
                    last_sync=row[3],
                    status=row[4]
                )
            return None
    
    async def _get_local_devices(
        self,
        assets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """获取本地设备配置"""
        if assets:
            devices = []
            for asset in assets:
                device = await self.config_repo.get_device(asset)
                if device:
                    devices.append(device.to_dict())
            return devices
        else:
            devices = await self.config_repo.list_devices()
            return [device.to_dict() for device in devices]
    
    async def _fetch_remote_devices(
        self,
        instance: SyncInstance,
        assets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """从远程实例获取设备配置"""
        headers = {}
        if instance.api_token:
            headers['Authorization'] = f'Bearer {instance.api_token}'
        
        url = f"{instance.url}/api/devices/export"
        if assets:
            url += f"?assets={','.join(assets)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('devices', [])
                else:
                    raise Exception(f"Failed to fetch devices: {response.status}")
    
    def _detect_conflicts(
        self,
        local_devices: List[Dict[str, Any]],
        remote_devices: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测配置冲突"""
        conflicts = []
        
        local_map = {d['asset']: d for d in local_devices}
        remote_map = {d['asset']: d for d in remote_devices}
        
        for asset in set(local_map.keys()) & set(remote_map.keys()):
            local_hash = self._compute_hash(local_map[asset])
            remote_hash = self._compute_hash(remote_map[asset])
            
            if local_hash != remote_hash:
                conflicts.append({
                    'asset': asset,
                    'local_updated': local_map[asset].get('updated_at'),
                    'remote_updated': remote_map[asset].get('updated_at'),
                    'type': 'config_mismatch'
                })
        
        return conflicts
    
    def _merge_devices(
        self,
        local_devices: List[Dict[str, Any]],
        remote_devices: List[Dict[str, Any]],
        strategy: str
    ) -> List[Dict[str, Any]]:
        """合并设备配置"""
        local_map = {d['asset']: d for d in local_devices}
        remote_map = {d['asset']: d for d in remote_devices}
        
        merged = {}
        
        for asset, device in local_map.items():
            merged[asset] = device
        
        for asset, device in remote_map.items():
            if asset not in merged:
                merged[asset] = device
            else:
                if strategy == 'latest':
                    local_time = local_map[asset].get('updated_at', 0)
                    remote_time = device.get('updated_at', 0)
                    if remote_time > local_time:
                        merged[asset] = device
                elif strategy == 'remote':
                    merged[asset] = device
        
        return list(merged.values())
    
    async def _push_devices(
        self,
        instance: SyncInstance,
        devices: List[Dict[str, Any]]
    ) -> SyncResult:
        """推送设备配置到远程实例"""
        headers = {'Content-Type': 'application/json'}
        if instance.api_token:
            headers['Authorization'] = f'Bearer {instance.api_token}'
        
        data = {
            'version': '1.0',
            'devices': devices
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{instance.url}/api/devices/import",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return SyncResult(
                        instance_name=instance.name,
                        success=True,
                        synced_devices=result.get('succeeded', 0),
                        synced_points=sum(len(d.get('points', [])) for d in devices)
                    )
                else:
                    raise Exception(f"Failed to push devices: {response.status}")
    
    async def _import_devices(
        self,
        devices: List[Dict[str, Any]]
    ) -> SyncResult:
        """导入设备配置"""
        synced_devices = 0
        synced_points = 0
        
        for device_data in devices:
            try:
                from ..config.config_repository import DeviceConfig
                device = DeviceConfig.from_dict(device_data)
                
                existing = await self.config_repo.get_device(device.asset)
                if existing:
                    await self.config_repo.update_device(
                        device.asset,
                        device.to_dict(),
                        user="sync"
                    )
                else:
                    await self.config_repo.create_device(device, user="sync")
                
                synced_devices += 1
                synced_points += len(device.points)
            
            except Exception as e:
                logger.error(f"Failed to import device {device_data.get('asset')}: {e}")
        
        return SyncResult(
            instance_name=self.local_instance_name,
            success=True,
            synced_devices=synced_devices,
            synced_points=synced_points
        )
    
    async def _update_instance_status(
        self,
        instance_name: str,
        status: str,
        last_sync: float
    ) -> None:
        """更新实例状态"""
        await self._db.execute(
            """
            UPDATE sync_instances
            SET status = ?, last_sync = ?
            WHERE name = ?
            """,
            (status, last_sync, instance_name)
        )
        await self._db.commit()
    
    async def _save_sync_history(
        self,
        result: SyncResult
    ) -> None:
        """保存同步历史"""
        await self._db.execute(
            """
            INSERT INTO sync_history (
                instance_name, success, synced_devices, synced_points,
                conflicts, errors, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.instance_name, result.success, result.synced_devices,
                result.synced_points, json.dumps(result.conflicts),
                json.dumps(result.errors), result.timestamp
            )
        )
        await self._db.commit()
    
    def _compute_hash(self, config: Dict[str, Any]) -> str:
        """计算配置哈希"""
        content = json.dumps(config, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
