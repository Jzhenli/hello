"""配置仓库 - 数据库为中心的配置管理

此模块提供数据库为中心的配置管理功能，包括：
- 设备配置的CRUD操作
- 点位配置管理
- 配置版本控制
- 配置历史查询
"""

import json
import logging
import time
import hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """设备配置数据类"""
    asset: str
    name: Optional[str] = None
    description: Optional[str] = None
    plugin_name: str = ""
    plugin_config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    points: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "asset": self.asset,
            "name": self.name,
            "description": self.description,
            "plugin_name": self.plugin_name,
            "plugin_config": self.plugin_config,
            "enabled": self.enabled,
            "status": self.status,
            "metadata": self.metadata,
            "tags": self.tags,
            "points": self.points,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceConfig':
        """从字典创建实例"""
        return cls(**data)


class ConfigRepository:
    """配置仓库 - 数据库操作层"""
    
    def __init__(self, db: aiosqlite.Connection):
        self._db = db
    
    async def get_device(self, asset: str) -> Optional[DeviceConfig]:
        """获取设备配置
        
        Args:
            asset: 设备资产标识
            
        Returns:
            设备配置，如果不存在返回None
        """
        device_data = await self._get_device_record(asset)
        if not device_data:
            return None
        
        points = await self._get_device_points(asset)
        device_data['points'] = points
        
        return DeviceConfig.from_dict(device_data)
    
    async def list_devices(
        self,
        status: Optional[str] = None,
        enabled: Optional[bool] = None,
        plugin_name: Optional[str] = None
    ) -> List[DeviceConfig]:
        """列出设备
        
        Args:
            status: 按状态过滤
            enabled: 按启用状态过滤
            plugin_name: 按插件名称过滤
            
        Returns:
            设备列表
        """
        conditions = ["status != 'deleted'"]
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if enabled is not None:
            conditions.append("enabled = ?")
            params.append(enabled)
        
        if plugin_name:
            conditions.append("plugin_name = ?")
            params.append(plugin_name)
        
        query = f"""
            SELECT asset, name, description, plugin_name, plugin_config, 
                   enabled, status, metadata, tags,
                   created_at, updated_at
            FROM device_registry
            WHERE {' AND '.join(conditions)}
            ORDER BY asset
        """
        
        devices = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                device_data = {
                    'asset': row[0],
                    'name': row[1],
                    'description': row[2],
                    'plugin_name': row[3],
                    'plugin_config': json.loads(row[4]) if row[4] else {},
                    'enabled': bool(row[5]),
                    'status': row[6],
                    'metadata': json.loads(row[7]) if row[7] else {},
                    'tags': json.loads(row[8]) if row[8] else [],
                    'version': 1,
                    'created_at': row[9],
                    'updated_at': row[10],
                    'created_by': None,
                    'updated_by': None
                }
                
                points = await self._get_device_points(device_data['asset'])
                device_data['points'] = points
                
                devices.append(DeviceConfig.from_dict(device_data))
        
        return devices
    
    async def create_device(
        self,
        device: DeviceConfig,
        user: Optional[str] = None
    ) -> DeviceConfig:
        """创建设备
        
        Args:
            device: 设备配置
            user: 操作用户
            
        Returns:
            创建的设备配置
            
        Raises:
            ValueError: 如果设备已存在
        """
        now = time.time()
        config_json = json.dumps(device.to_dict(), sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        try:
            await self._db.execute(
                """
                INSERT INTO device_registry (
                    asset, name, description, service_name, plugin_name, plugin_config,
                    enabled, status, metadata, tags, config_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device.asset, device.name, device.description,
                    device.plugin_name, device.plugin_name, json.dumps(device.plugin_config),
                    device.enabled, device.status,
                    json.dumps(device.metadata), json.dumps(device.tags),
                    config_hash, now, now
                )
            )
        except aiosqlite.IntegrityError as e:
            if 'UNIQUE constraint' in str(e):
                raise ValueError(f"Device '{device.asset}' already exists")
            raise ValueError(f"Failed to create device '{device.asset}': {e}")
        
        for point in device.points:
            await self._create_point(device.asset, point, user)
        
        await self._save_config_version(
            'device', device.asset, device.to_dict(), 
            'create', user, now
        )
        
        await self._db.commit()
        
        device.version = 1
        device.created_at = now
        device.updated_at = now
        device.created_by = user
        device.updated_by = user
        
        logger.info(f"Device created: {device.asset} by {user}")
        return device
    
    async def update_device(
        self,
        asset: str,
        updates: Dict[str, Any],
        user: Optional[str] = None
    ) -> DeviceConfig:
        """更新设备
        
        Args:
            asset: 设备资产标识
            updates: 更新内容
            user: 操作用户
            
        Returns:
            更新后的设备配置
            
        Raises:
            ValueError: 如果设备不存在
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        old_config = device.to_dict()
        
        for key, value in updates.items():
            if key == 'asset':
                continue
            if hasattr(device, key):
                setattr(device, key, value)
        
        now = time.time()
        device.updated_at = now
        device.updated_by = user
        device.version += 1
        
        config_json = json.dumps(device.to_dict(), sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        await self._db.execute(
            """
            UPDATE device_registry SET
                name = ?, description = ?, service_name = ?, plugin_name = ?, plugin_config = ?,
                enabled = ?, status = ?, metadata = ?, tags = ?,
                config_hash = ?, updated_at = ?
            WHERE asset = ?
            """,
            (
                device.name, device.description,
                device.plugin_name, device.plugin_name, json.dumps(device.plugin_config),
                device.enabled, device.status,
                json.dumps(device.metadata), json.dumps(device.tags),
                config_hash, now, asset
            )
        )
        
        await self._save_config_version(
            'device', asset, device.to_dict(),
            'update', user, now, old_config
        )
        
        await self._db.commit()
        
        logger.info(f"Device updated: {asset} v{device.version} by {user}")
        return device
    
    async def delete_device(
        self,
        asset: str,
        user: Optional[str] = None
    ) -> None:
        """删除设备（软删除）
        
        Args:
            asset: 设备资产标识
            user: 操作用户
            
        Raises:
            ValueError: 如果设备不存在
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        now = time.time()
        
        await self._db.execute(
            """
            UPDATE device_registry 
            SET status = 'deleted', deleted_at = ?, updated_at = ?
            WHERE asset = ?
            """,
            (now, now, asset)
        )
        
        await self._db.execute(
            """
            UPDATE point_registry 
            SET status = 'deleted', deleted_at = ?
            WHERE asset = ? AND status = 'active'
            """,
            (now, asset)
        )
        
        await self._save_config_version(
            'device', asset, device.to_dict(),
            'delete', user, now
        )
        
        await self._db.commit()
        
        logger.info(f"Device deleted: {asset} by {user}")
    
    async def add_point(
        self,
        asset: str,
        point: Dict[str, Any],
        user: Optional[str] = None
    ) -> None:
        """添加点位
        
        Args:
            asset: 设备资产标识
            point: 点位配置
            user: 操作用户
            
        Raises:
            ValueError: 如果设备不存在或点位已存在
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        if any(p.get('name') == point.get('name') for p in device.points):
            raise ValueError(f"Point '{point.get('name')}' already exists in device '{asset}'")
        
        await self._create_point(asset, point, user)
        
        device.points.append(point)
        device.version += 1
        device.updated_at = time.time()
        device.updated_by = user
        
        await self._update_device_version(device)
        
        await self._db.commit()
        
        logger.info(f"Point added: {asset}/{point.get('name')} by {user}")
    
    async def update_point(
        self,
        asset: str,
        point_name: str,
        updates: Dict[str, Any],
        user: Optional[str] = None
    ) -> None:
        """更新点位
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            updates: 更新内容
            user: 操作用户
            
        Raises:
            ValueError: 如果设备或点位不存在
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        point_index = None
        for i, p in enumerate(device.points):
            if p.get('name') == point_name:
                point_index = i
                break
        
        if point_index is None:
            raise ValueError(f"Point '{point_name}' not found in device '{asset}'")
        
        for key, value in updates.items():
            if key == 'name':
                continue
            device.points[point_index][key] = value
        
        now = time.time()
        config_json = json.dumps(device.points[point_index], sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        await self._db.execute(
            """
            UPDATE point_registry SET
                description = ?, data_type = ?,
                unit = ?, config = ?, metadata = ?, tags = ?, enabled = ?,
                config_hash = ?, updated_at = ?
            WHERE asset = ? AND point_name = ?
            """,
            (
                device.points[point_index].get('description'),
                device.points[point_index].get('data_type'),
                device.points[point_index].get('unit'),
                json.dumps(device.points[point_index].get('config', {})),
                json.dumps(device.points[point_index].get('metadata', {})),
                json.dumps(device.points[point_index].get('tags', [])),
                device.points[point_index].get('enabled', True),
                config_hash, now, asset, point_name
            )
        )
        
        device.version += 1
        device.updated_at = now
        device.updated_by = user
        
        await self._update_device_version(device)
        
        await self._db.commit()
        
        logger.info(f"Point updated: {asset}/{point_name} by {user}")
    
    async def delete_point(
        self,
        asset: str,
        point_name: str,
        user: Optional[str] = None
    ) -> None:
        """删除点位（软删除）
        
        Args:
            asset: 设备资产标识
            point_name: 点位名称
            user: 操作用户
            
        Raises:
            ValueError: 如果设备或点位不存在
        """
        device = await self.get_device(asset)
        if not device:
            raise ValueError(f"Device '{asset}' not found")
        
        point_exists = any(p.get('name') == point_name for p in device.points)
        if not point_exists:
            raise ValueError(f"Point '{point_name}' not found in device '{asset}'")
        
        now = time.time()
        
        await self._db.execute(
            """
            UPDATE point_registry 
            SET status = 'deleted', deleted_at = ?
            WHERE asset = ? AND point_name = ?
            """,
            (now, asset, point_name)
        )
        
        device.points = [p for p in device.points if p.get('name') != point_name]
        device.version += 1
        device.updated_at = now
        device.updated_by = user
        
        await self._update_device_version(device)
        
        await self._db.commit()
        
        logger.info(f"Point deleted: {asset}/{point_name} by {user}")
    
    async def get_config_versions(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取配置版本历史
        
        Args:
            entity_type: 实体类型 ('device' 或 'point')
            entity_id: 实体ID
            limit: 返回数量限制
            
        Returns:
            版本历史列表
        """
        async with self._db.execute(
            """
            SELECT version, config, config_hash, change_type, changed_by,
                   changed_at, previous_version
            FROM config_versions
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (entity_type, entity_id, limit)
        ) as cursor:
            versions = []
            async for row in cursor:
                versions.append({
                    'version': row[0],
                    'config': json.loads(row[1]),
                    'config_hash': row[2],
                    'change_type': row[3],
                    'changed_by': row[4],
                    'changed_at': row[5],
                    'previous_version': row[6]
                })
            return versions
    
    async def get_config_version(
        self,
        entity_type: str,
        entity_id: str,
        version: int
    ) -> Optional[Dict[str, Any]]:
        """获取特定版本的配置
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            version: 版本号
            
        Returns:
            配置信息，如果不存在返回None
        """
        async with self._db.execute(
            """
            SELECT version, config, config_hash, change_type, changed_by,
                   changed_at, previous_version
            FROM config_versions
            WHERE entity_type = ? AND entity_id = ? AND version = ?
            """,
            (entity_type, entity_id, version)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'version': row[0],
                    'config': json.loads(row[1]),
                    'config_hash': row[2],
                    'change_type': row[3],
                    'changed_by': row[4],
                    'changed_at': row[5],
                    'previous_version': row[6]
                }
            return None
    
    async def _get_device_record(self, asset: str) -> Optional[Dict[str, Any]]:
        """获取设备记录（内部方法）"""
        async with self._db.execute(
            """
            SELECT asset, name, description, plugin_name, plugin_config,
                   enabled, status, metadata, tags,
                   created_at, updated_at
            FROM device_registry
            WHERE asset = ? AND status != 'deleted'
            """,
            (asset,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                'asset': row[0],
                'name': row[1],
                'description': row[2],
                'plugin_name': row[3],
                'plugin_config': json.loads(row[4]) if row[4] else {},
                'enabled': bool(row[5]),
                'status': row[6],
                'metadata': json.loads(row[7]) if row[7] else {},
                'tags': json.loads(row[8]) if row[8] else [],
                'version': 1,
                'created_at': row[9],
                'updated_at': row[10],
                'created_by': None,
                'updated_by': None
            }
    
    async def _get_device_points(self, asset: str) -> List[Dict[str, Any]]:
        """获取设备的所有点位（内部方法）"""
        async with self._db.execute(
            """
            SELECT point_name, description, data_type,
                   unit, config, metadata, tags, enabled
            FROM point_registry
            WHERE asset = ? AND status = 'active'
            ORDER BY point_name
            """,
            (asset,)
        ) as cursor:
            points = []
            async for row in cursor:
                points.append({
                    'name': row[0],
                    'description': row[1],
                    'data_type': row[2],
                    'unit': row[3],
                    'config': json.loads(row[4]) if row[4] else {},
                    'metadata': json.loads(row[5]) if row[5] else {},
                    'tags': json.loads(row[6]) if row[6] else [],
                    'enabled': bool(row[7])
                })
            return points
    
    async def _create_point(
        self,
        asset: str,
        point: Dict[str, Any],
        user: Optional[str] = None
    ) -> None:
        """创建点位（内部方法）"""
        now = time.time()
        config_json = json.dumps(point, sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        try:
            await self._db.execute(
                """
                INSERT INTO point_registry (
                    asset, point_name, description, data_type,
                    unit, config, metadata, tags, enabled, config_hash,
                    created_at, updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    asset, point['name'], point.get('description'),
                    point.get('data_type'),
                    point.get('unit'), json.dumps(point.get('config', {})),
                    json.dumps(point.get('metadata', {})),
                    json.dumps(point.get('tags', [])),
                    point.get('enabled', True), config_hash,
                    now, now
                )
            )
        except aiosqlite.IntegrityError as e:
            if 'UNIQUE constraint' in str(e):
                raise ValueError(f"Point '{point['name']}' already exists in device '{asset}'")
            raise ValueError(f"Failed to create point '{point['name']}': {e}")
    
    async def _update_device_version(self, device: DeviceConfig) -> None:
        """更新设备版本（内部方法）"""
        config_json = json.dumps(device.to_dict(), sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        await self._db.execute(
            """
            UPDATE device_registry SET
                config_hash = ?, updated_at = ?
            WHERE asset = ?
            """,
            (config_hash, device.updated_at, device.asset)
        )
        
        await self._save_config_version(
            'device', device.asset, device.to_dict(),
            'update', device.updated_by, device.updated_at
        )
    
    async def _save_config_version(
        self,
        entity_type: str,
        entity_id: str,
        config: Dict[str, Any],
        change_type: str,
        changed_by: Optional[str],
        changed_at: float,
        old_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """保存配置版本（内部方法）"""
        config_json = json.dumps(config, sort_keys=True)
        config_hash = self._compute_hash(config_json)
        
        async with self._db.execute(
            """
            SELECT MAX(version) FROM config_versions
            WHERE entity_type = ? AND entity_id = ?
            """,
            (entity_type, entity_id)
        ) as cursor:
            row = await cursor.fetchone()
            max_version = row[0] if row and row[0] else 0
        
        version = max_version + 1
        previous_version = max_version if max_version > 0 else None
        
        await self._db.execute(
            """
            INSERT INTO config_versions (
                entity_type, entity_id, version, config, config_hash,
                change_type, changed_by, changed_at, previous_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type, entity_id, version, config_json, config_hash,
                change_type, changed_by, changed_at, previous_version
            )
        )
    
    async def commit(self) -> None:
        """提交当前事务"""
        await self._db.commit()

    def _compute_hash(self, content: str) -> str:
        """计算配置哈希值"""
        return hashlib.md5(content.encode()).hexdigest()

    async def upsert_plugin_meta(
        self,
        name: str,
        plugin_type: str,
        version: str = "1.0.0",
        description: Optional[str] = None,
        defaults: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
    ) -> None:
        """写入或更新插件元信息到 plugin_registry 表

        Args:
            name: 插件名称
            plugin_type: 插件类型 (south/north/filter 等)
            version: 插件版本
            description: 插件描述
            defaults: 默认配置参数
            capabilities: 插件能力列表
        """
        now = time.time()
        await self._db.execute(
            """
            INSERT INTO plugin_registry (
                name, type, version, description, defaults, capabilities,
                enabled, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'registered', ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                type = excluded.type,
                version = excluded.version,
                description = excluded.description,
                defaults = excluded.defaults,
                capabilities = excluded.capabilities,
                updated_at = excluded.updated_at
            """,
            (
                name,
                plugin_type,
                version,
                description,
                json.dumps(defaults) if defaults else None,
                json.dumps(capabilities) if capabilities else None,
                now,
                now,
            ),
        )

    async def get_plugin_defaults(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件默认配置

        Args:
            plugin_name: 插件名称

        Returns:
            默认配置字典，不存在则返回空字典
        """
        async with self._db.execute(
            "SELECT defaults FROM plugin_registry WHERE name = ?",
            (plugin_name,),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return {}

    async def list_plugins_by_type(
        self, plugin_type: str
    ) -> List[Dict[str, Any]]:
        """按类型列出已注册插件

        Args:
            plugin_type: 插件类型

        Returns:
            插件信息列表
        """
        async with self._db.execute(
            """
            SELECT name, type, version, description, defaults, capabilities, status
            FROM plugin_registry WHERE type = ?
            ORDER BY name
            """,
            (plugin_type,),
        ) as cursor:
            plugins = []
            async for row in cursor:
                plugins.append(
                    {
                        "name": row[0],
                        "type": row[1],
                        "version": row[2],
                        "description": row[3],
                        "defaults": json.loads(row[4]) if row[4] else {},
                        "capabilities": json.loads(row[5]) if row[5] else [],
                        "status": row[6],
                    }
                )
            return plugins

    async def get_affected_device_assets(
        self, plugin_names: List[str]
    ) -> List[str]:
        """查询使用指定插件的设备资产标识列表

        Args:
            plugin_names: 插件名称列表

        Returns:
            受影响的设备 asset 列表
        """
        if not plugin_names:
            return []
        placeholders = ",".join("?" for _ in plugin_names)
        async with self._db.execute(
            f"""
            SELECT asset FROM device_registry
            WHERE plugin_name IN ({placeholders}) AND status != 'deleted'
            ORDER BY asset
            """,
            plugin_names,
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # ── North Channel CRUD ──────────────────────────────────────

    async def get_north_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT id, name, plugin_name, remote_host, remote_port,
                   local_port, config, enabled, status, created_at, updated_at
            FROM north_channel_registry
            WHERE id = ? AND status != 'deleted'
            """,
            (channel_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "plugin_name": row[2],
                "remote_host": row[3],
                "remote_port": row[4],
                "local_port": row[5],
                "config": json.loads(row[6]) if row[6] else {},
                "enabled": bool(row[7]),
                "status": row[8],
                "created_at": row[9],
                "updated_at": row[10],
            }

    async def list_north_channels(
        self,
        status: Optional[str] = None,
        enabled: Optional[bool] = None,
        plugin_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conditions = ["status != 'deleted'"]
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if enabled is not None:
            conditions.append("enabled = ?")
            params.append(enabled)
        if plugin_name:
            conditions.append("plugin_name = ?")
            params.append(plugin_name)
        query = f"""
            SELECT id, name, plugin_name, remote_host, remote_port,
                   local_port, config, enabled, status, created_at, updated_at
            FROM north_channel_registry
            WHERE {' AND '.join(conditions)}
            ORDER BY id
        """
        channels = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                channels.append({
                    "id": row[0],
                    "name": row[1],
                    "plugin_name": row[2],
                    "remote_host": row[3],
                    "remote_port": row[4],
                    "local_port": row[5],
                    "config": json.loads(row[6]) if row[6] else {},
                    "enabled": bool(row[7]),
                    "status": row[8],
                    "created_at": row[9],
                    "updated_at": row[10],
                })
        return channels

    async def create_north_channel(
        self, data: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        now = time.time()
        try:
            await self._db.execute(
                """
                INSERT INTO north_channel_registry
                    (name, plugin_name, remote_host, remote_port,
                     local_port, config, enabled, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    data["name"],
                    data.get("plugin_name", "xnc_plus"),
                    data.get("remote_host"),
                    data.get("remote_port"),
                    data.get("local_port"),
                    json.dumps(data.get("config", {})),
                    data.get("enabled", True),
                    now,
                    now,
                ),
            )
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                raise ValueError(f"Channel '{data['name']}' already exists")
            raise ValueError(f"Failed to create channel: {e}")
        await self._db.commit()
        async with self._db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            channel_id = row[0] if row else None
        channel = await self.get_north_channel(channel_id)
        await self._save_config_version(
            "north_channel", str(channel_id), channel, "create", user, now
        )
        await self._db.commit()
        return channel

    async def update_north_channel(
        self, channel_id: int, updates: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        channel = await self.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        old_config = dict(channel)
        allowed = {
            "name", "plugin_name", "remote_host", "remote_port",
            "local_port", "config", "enabled",
        }
        set_parts = []
        params: list = []
        for key in allowed:
            if key in updates:
                set_parts.append(f"{key} = ?")
                val = updates[key]
                if key == "config":
                    val = json.dumps(val)
                elif key == "enabled":
                    val = bool(val)
                params.append(val)
        if not set_parts:
            return channel
        now = time.time()
        set_parts.append("updated_at = ?")
        params.append(now)
        params.append(channel_id)
        await self._db.execute(
            f"UPDATE north_channel_registry SET {', '.join(set_parts)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        updated = await self.get_north_channel(channel_id)
        await self._save_config_version(
            "north_channel", str(channel_id), updated, "update", user, now, old_config
        )
        await self._db.commit()
        return updated

    async def delete_north_channel(
        self, channel_id: int, user: Optional[str] = None
    ) -> None:
        channel = await self.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        now = time.time()
        await self._db.execute(
            "UPDATE north_channel_registry SET status = 'deleted', deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, channel_id),
        )
        await self._db.execute(
            "UPDATE north_point_mapping SET status = 'deleted', deleted_at = ? WHERE channel_id = ? AND status = 'active'",
            (now, channel_id),
        )
        await self._save_config_version(
            "north_channel", str(channel_id), channel, "delete", user, now
        )
        await self._db.commit()

    # ── North Point Mapping CRUD ────────────────────────────────

    async def get_north_mapping(self, mapping_id: int) -> Optional[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT id, channel_id, asset, point_name, protocol_oid, protocol_vdid,
                   pid_value, pid_error, value_transform, protocol_config, enabled,
                   status, created_at, updated_at
            FROM north_point_mapping
            WHERE id = ? AND status != 'deleted'
            """,
            (mapping_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "channel_id": row[1],
                "asset": row[2],
                "point_name": row[3],
                "protocol_oid": row[4],
                "protocol_vdid": row[5],
                "pid_value": row[6],
                "pid_error": row[7],
                "value_transform": json.loads(row[8]) if row[8] else None,
                "protocol_config": json.loads(row[9]) if row[9] else None,
                "enabled": bool(row[10]),
                "status": row[11],
                "created_at": row[12],
                "updated_at": row[13],
            }

    async def list_north_mappings(
        self,
        channel_id: Optional[int] = None,
        asset: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        conditions = ["m.status != 'deleted'"]
        params: list = []
        if channel_id is not None:
            conditions.append("m.channel_id = ?")
            params.append(channel_id)
        if asset is not None:
            conditions.append("m.asset = ?")
            params.append(asset)
        if enabled is not None:
            conditions.append("m.enabled = ?")
            params.append(enabled)
        query = f"""
            SELECT m.id, m.channel_id, m.asset, m.point_name, m.protocol_oid,
                   m.protocol_vdid, m.pid_value, m.pid_error, m.value_transform,
                   m.protocol_config, m.enabled, m.status, m.created_at, m.updated_at
            FROM north_point_mapping m
            WHERE {' AND '.join(conditions)}
            ORDER BY m.channel_id, m.asset, m.point_name
        """
        mappings = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                mappings.append({
                    "id": row[0],
                    "channel_id": row[1],
                    "asset": row[2],
                    "point_name": row[3],
                    "protocol_oid": row[4],
                    "protocol_vdid": row[5],
                    "pid_value": row[6],
                    "pid_error": row[7],
                    "value_transform": json.loads(row[8]) if row[8] else None,
                    "protocol_config": json.loads(row[9]) if row[9] else None,
                    "enabled": bool(row[10]),
                    "status": row[11],
                    "created_at": row[12],
                    "updated_at": row[13],
                })
        return mappings

    async def create_north_mapping(
        self, data: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        now = time.time()
        vt = data.get("value_transform")
        vt_json = json.dumps(vt) if vt else None
        pc = data.get("protocol_config")
        pc_json = json.dumps(pc) if pc else None
        try:
            await self._db.execute(
                """
                INSERT INTO north_point_mapping
                    (channel_id, asset, point_name, protocol_oid, protocol_vdid,
                     pid_value, pid_error, value_transform, protocol_config, enabled,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    data["channel_id"],
                    data["asset"],
                    data["point_name"],
                    data.get("protocol_oid"),
                    data.get("protocol_vdid"),
                    data.get("pid_value", 85),
                    data.get("pid_error", 103),
                    vt_json,
                    pc_json,
                    data.get("enabled", True),
                    now,
                    now,
                ),
            )
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                raise ValueError(
                    f"Mapping for channel={data['channel_id']}, "
                    f"asset={data['asset']}, point={data['point_name']} already exists"
                )
            raise ValueError(f"Failed to create mapping: {e}")
        await self._db.commit()
        async with self._db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            mapping_id = row[0] if row else None
        mapping = await self.get_north_mapping(mapping_id)
        await self._save_config_version(
            "north_mapping", str(mapping_id), mapping, "create", user, now
        )
        await self._db.commit()
        return mapping

    async def update_north_mapping(
        self, mapping_id: int, updates: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        mapping = await self.get_north_mapping(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping '{mapping_id}' not found")
        old_config = dict(mapping)
        allowed = {
            "asset", "point_name", "protocol_oid", "protocol_vdid",
            "pid_value", "pid_error", "value_transform", "protocol_config", "enabled",
        }
        set_parts = []
        params: list = []
        for key in allowed:
            if key in updates:
                set_parts.append(f"{key} = ?")
                val = updates[key]
                if key == "value_transform":
                    val = json.dumps(val) if val else None
                elif key == "protocol_config":
                    val = json.dumps(val) if val else None
                elif key == "enabled":
                    val = bool(val)
                params.append(val)
        if not set_parts:
            return mapping
        now = time.time()
        set_parts.append("updated_at = ?")
        params.append(now)
        params.append(mapping_id)
        await self._db.execute(
            f"UPDATE north_point_mapping SET {', '.join(set_parts)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        updated = await self.get_north_mapping(mapping_id)
        await self._save_config_version(
            "north_mapping", str(mapping_id), updated, "update", user, now, old_config
        )
        await self._db.commit()
        return updated

    async def delete_north_mapping(
        self, mapping_id: int, user: Optional[str] = None
    ) -> None:
        mapping = await self.get_north_mapping(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping '{mapping_id}' not found")
        now = time.time()
        await self._db.execute(
            "UPDATE north_point_mapping SET status = 'deleted', deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, mapping_id),
        )
        await self._save_config_version(
            "north_mapping", str(mapping_id), mapping, "delete", user, now
        )
        await self._db.commit()

    async def batch_create_north_mappings(
        self, mappings: List[Dict[str, Any]], user: Optional[str] = None
    ) -> Dict[str, Any]:
        succeeded = 0
        failed = 0
        details = []
        for m in mappings:
            try:
                await self.create_north_mapping(m, user)
                succeeded += 1
                details.append({
                    "asset": m.get("asset"),
                    "point_name": m.get("point_name"),
                    "success": True,
                })
            except Exception as e:
                failed += 1
                details.append({
                    "asset": m.get("asset"),
                    "point_name": m.get("point_name"),
                    "success": False,
                    "message": str(e),
                })
        return {"total": len(mappings), "succeeded": succeeded, "failed": failed, "details": details}

    async def delete_north_mappings_by_channel(
        self, channel_id: int, user: Optional[str] = None
    ) -> int:
        now = time.time()
        cursor = await self._db.execute(
            "UPDATE north_point_mapping SET status = 'deleted', deleted_at = ?, updated_at = ? WHERE channel_id = ? AND status = 'active'",
            (now, now, channel_id),
        )
        count = cursor.rowcount
        await self._db.commit()
        return count
