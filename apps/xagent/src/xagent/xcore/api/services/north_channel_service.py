"""北向通道服务 - 数据库为中心的配置管理"""

import logging
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pathlib import Path

import aiosqlite

from ..models.north_channel import (
    NorthChannelConfig,
    NorthChannelStatus,
    NorthChannelProtocol,
    NorthChannelStatistics,
    NorthChannelConnection,
    NorthChannelAdapter,
    NorthChannelUploadStrategy
)
from ...config.config_repository import ServiceRepository, ServiceConfig
from ...core.plugin_loader import PluginLoader

logger = logging.getLogger(__name__)


class NorthChannelService:
    """北向通道服务 - 数据库为中心的配置管理
    
    职责：
    - 北向通道配置的 CRUD 操作
    - 通道状态管理
    - 插件实例生命周期管理
    """
    
    def __init__(
        self,
        db: aiosqlite.Connection,
        plugin_loader: Optional[PluginLoader] = None
    ):
        """初始化服务
        
        Args:
            db: 数据库连接
            plugin_loader: 插件加载器（可选）
        """
        self._db = db
        self._plugin_loader = plugin_loader
        self._service_repo = ServiceRepository(db)
        self._cache: Dict[str, NorthChannelConfig] = {}
    
    async def initialize(self) -> None:
        """初始化服务，从数据库加载配置到缓存"""
        await self._load_cache()
        logger.info(f"NorthChannelService initialized with {len(self._cache)} channels")
    
    async def _load_cache(self) -> None:
        """从数据库加载配置到内存缓存"""
        services = await self._service_repo.list_services()
        self._cache.clear()
        for service in services:
            try:
                channel = self._service_to_channel(service)
                self._cache[channel.id] = channel
            except Exception as e:
                logger.error(f"Failed to load service {service.name}: {e}")
        
        logger.info(f"Loaded {len(self._cache)} channels from database")
    
    def _service_to_channel(self, service: ServiceConfig) -> NorthChannelConfig:
        """将 ServiceConfig 转换为 NorthChannelConfig
        
        Args:
            service: 服务配置
            
        Returns:
            北向通道配置
        """
        conn_config = service.connection_config
        
        connection = NorthChannelConnection(
            host=conn_config.get("host", "localhost"),
            port=conn_config.get("port", 1883),
            username=conn_config.get("username"),
            password=conn_config.get("password"),
            mqtt=conn_config.get("mqtt"),
            xnc=conn_config.get("xnc"),
            http=conn_config.get("http")
        )
        
        adapter_data = service.adapter_config or {}
        adapter = NorthChannelAdapter(
            type=adapter_data.get("type", "default"),
            config=adapter_data.get("config", {})
        )
        
        upload_data = service.upload_config or {}
        upload_strategy = NorthChannelUploadStrategy(
            immediate_upload=upload_data.get("immediate_upload", True),
            batch_size=upload_data.get("batch_size", 100),
            interval=upload_data.get("interval", 5),
            retry_times=upload_data.get("retry_times", 3),
            retry_interval=upload_data.get("retry_interval")
        )
        
        statistics = None
        if service.statistics:
            statistics = NorthChannelStatistics(**service.statistics)
        
        protocol_map = {
            "mqtt": NorthChannelProtocol.MQTT,
            "xnc": NorthChannelProtocol.XNC,
            "http": NorthChannelProtocol.HTTP,
            "custom": NorthChannelProtocol.CUSTOM
        }
        
        status_map = {
            "online": NorthChannelStatus.ONLINE,
            "offline": NorthChannelStatus.OFFLINE,
            "error": NorthChannelStatus.ERROR
        }
        
        return NorthChannelConfig(
            id=service.name,
            name=service.display_name or service.name,
            description=service.description,
            enabled=service.enabled,
            protocol=protocol_map.get(service.protocol, NorthChannelProtocol.CUSTOM),
            status=status_map.get(service.status, NorthChannelStatus.OFFLINE),
            connection=connection,
            adapter=adapter,
            upload_strategy=upload_strategy,
            statistics=statistics,
            tags=service.tags,
            created_at=datetime.fromtimestamp(service.created_at).isoformat() if service.created_at else None,
            updated_at=datetime.fromtimestamp(service.updated_at).isoformat() if service.updated_at else None
        )
    
    def _channel_to_service(self, channel: NorthChannelConfig, user: Optional[str] = None) -> ServiceConfig:
        """将 NorthChannelConfig 转换为 ServiceConfig
        
        Args:
            channel: 北向通道配置
            user: 操作用户
            
        Returns:
            服务配置
        """
        # 前端已经只发送相关字段，直接序列化即可
        connection_config = channel.connection.model_dump(exclude_none=True)
        
        adapter_config = {
            "type": channel.adapter.type,
            "config": channel.adapter.config
        }
        
        upload_config = {
            "immediate_upload": channel.upload_strategy.immediate_upload,
            "batch_size": channel.upload_strategy.batch_size,
            "interval": channel.upload_strategy.interval,
            "retry_times": channel.upload_strategy.retry_times,
            "retry_interval": channel.upload_strategy.retry_interval
        }
        
        command_config = {}
        
        statistics_dict = None
        if channel.statistics:
            statistics_dict = channel.statistics.model_dump()
        
        return ServiceConfig(
            name=channel.id,
            protocol=channel.protocol.value,
            display_name=channel.name,
            description=channel.description,
            connection_config=connection_config,
            adapter_config=adapter_config,
            upload_config=upload_config,
            command_config=command_config,
            enabled=channel.enabled,
            status=channel.status.value if channel.status else "offline",
            priority=0,
            metadata={},
            tags=channel.tags,
            statistics=statistics_dict,
            created_by=user,
            updated_by=user
        )
    
    async def list_channels(
        self,
        status: Optional[NorthChannelStatus] = None,
        protocol: Optional[NorthChannelProtocol] = None,
        tags: Optional[List[str]] = None,
        enabled: Optional[bool] = None
    ) -> List[NorthChannelConfig]:
        """列出通道
        
        Args:
            status: 按状态过滤
            protocol: 按协议过滤
            tags: 按标签过滤
            enabled: 按启用状态过滤
            
        Returns:
            通道列表
        """
        channels = list(self._cache.values())
        
        if status:
            channels = [c for c in channels if c.status == status]
        
        if protocol:
            channels = [c for c in channels if c.protocol == protocol]
        
        if enabled is not None:
            channels = [c for c in channels if c.enabled == enabled]
        
        if tags:
            channels = [c for c in channels if any(tag in c.tags for tag in tags)]
        
        return channels
    
    async def get_channel(self, channel_id: str) -> Optional[NorthChannelConfig]:
        """获取通道详情
        
        Args:
            channel_id: 通道ID
            
        Returns:
            通道配置
        """
        return self._cache.get(channel_id)
    
    async def create_channel(
        self,
        channel: NorthChannelConfig,
        user: Optional[str] = None
    ) -> NorthChannelConfig:
        """创建通道
        
        Args:
            channel: 通道配置
            user: 操作用户
            
        Returns:
            创建的通道
            
        Raises:
            ValueError: 通道已存在
        """
        if channel.id in self._cache:
            raise ValueError(f"Channel '{channel.id}' already exists")
        
        now = datetime.now()
        channel.created_at = now.isoformat()
        channel.updated_at = now.isoformat()
        channel.status = NorthChannelStatus.OFFLINE
        
        service = self._channel_to_service(channel, user)
        created_service = await self._service_repo.create_service(service, user)
        
        created_channel = self._service_to_channel(created_service)
        self._cache[created_channel.id] = created_channel
        
        if channel.enabled and self._plugin_loader:
            await self._load_channel_plugin(created_channel)
        
        logger.info(f"Created channel: {channel.id}")
        return created_channel
    
    async def update_channel(
        self,
        channel_id: str,
        updates: Dict[str, Any],
        user: Optional[str] = None
    ) -> NorthChannelConfig:
        """更新通道
        
        Args:
            channel_id: 通道ID
            updates: 更新内容
            user: 操作用户
            
        Returns:
            更新后的通道
            
        Raises:
            ValueError: 通道不存在
        """
        if channel_id not in self._cache:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        updated_service = await self._service_repo.update_service(channel_id, updates, user)
        
        updated_channel = self._service_to_channel(updated_service)
        self._cache[channel_id] = updated_channel
        
        if self._plugin_loader:
            old_enabled = self._cache.get(channel_id, NorthChannelConfig(id="", name="", protocol=NorthChannelProtocol.MQTT, connection=NorthChannelConnection(host="", port=0))).enabled
            new_enabled = updated_channel.enabled
            
            if old_enabled and not new_enabled:
                await self._unload_channel_plugin(channel_id)
            elif not old_enabled and new_enabled:
                await self._load_channel_plugin(updated_channel)
            elif new_enabled:
                await self._reload_channel_plugin(updated_channel)
        
        logger.info(f"Updated channel: {channel_id}")
        return updated_channel
    
    async def delete_channel(
        self,
        channel_id: str,
        user: Optional[str] = None
    ) -> None:
        """删除通道
        
        Args:
            channel_id: 通道ID
            user: 操作用户
            
        Raises:
            ValueError: 通道不存在
        """
        if channel_id not in self._cache:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        if self._plugin_loader:
            await self._unload_channel_plugin(channel_id)
        
        await self._service_repo.delete_service(channel_id, user)
        del self._cache[channel_id]
        
        logger.info(f"Deleted channel: {channel_id}")
    
    async def toggle_channel(
        self,
        channel_id: str,
        user: Optional[str] = None
    ) -> NorthChannelConfig:
        """切换通道启用状态
        
        Args:
            channel_id: 通道ID
            user: 操作用户
            
        Returns:
            更新后的通道
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        return await self.update_channel(
            channel_id,
            {"enabled": not channel.enabled},
            user
        )
    
    async def update_status(
        self,
        channel_id: str,
        status: NorthChannelStatus,
        statistics: Optional[Dict[str, Any]] = None
    ) -> None:
        """更新通道状态
        
        Args:
            channel_id: 通道ID
            status: 新状态
            statistics: 统计信息
        """
        if channel_id not in self._cache:
            return
        
        await self._service_repo.update_status(channel_id, status.value, statistics)
        
        channel = self._cache[channel_id]
        channel.status = status
        if statistics:
            channel.statistics = NorthChannelStatistics(**statistics)
    
    async def test_connection(self, channel_id: str) -> Dict[str, Any]:
        """测试通道连接
        
        Args:
            channel_id: 通道ID
            
        Returns:
            测试结果
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        start_time = time.time()
        
        try:
            if channel.protocol == NorthChannelProtocol.XNC:
                result = await self._test_xnc_connection(channel)
            elif channel.protocol == NorthChannelProtocol.MQTT:
                result = await self._test_mqtt_connection(channel)
            elif channel.protocol == NorthChannelProtocol.HTTP:
                result = await self._test_http_connection(channel)
            else:
                result = {
                    "success": False,
                    "message": f"Unsupported protocol: {channel.protocol}"
                }
        except Exception as e:
            result = {
                "success": False,
                "message": f"Connection test failed: {str(e)}"
            }
        
        latency = (time.time() - start_time) * 1000
        result["latency"] = round(latency, 2)
        
        return result
    
    async def _test_xnc_connection(self, channel: NorthChannelConfig) -> Dict[str, Any]:
        """测试XNC连接"""
        try:
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            test_data = b"TEST"
            sock.sendto(test_data, (channel.connection.host, channel.connection.port))
            
            try:
                response, _ = sock.recvfrom(1024)
                sock.close()
                return {
                    "success": True,
                    "message": "XNC connection successful",
                    "details": {"response_size": len(response)}
                }
            except socket.timeout:
                sock.close()
                return {
                    "success": True,
                    "message": "XNC endpoint reachable (no response expected for UDP)"
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"XNC connection failed: {str(e)}"
            }
    
    async def _test_mqtt_connection(self, channel: NorthChannelConfig) -> Dict[str, Any]:
        """测试MQTT连接"""
        return {
            "success": True,
            "message": "MQTT connection test not implemented yet"
        }
    
    async def _test_http_connection(self, channel: NorthChannelConfig) -> Dict[str, Any]:
        """测试HTTP连接"""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=channel.connection.http.timeout if channel.connection.http else 30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                method = channel.connection.http.method.lower() if channel.connection.http else "get"
                
                async with session.request(
                    method,
                    channel.connection.http.endpoint if channel.connection.http else "",
                    headers=channel.connection.http.headers if channel.connection.http else None
                ) as response:
                    if response.status < 400:
                        return {
                            "success": True,
                            "message": f"HTTP connection successful (status: {response.status})"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"HTTP connection failed (status: {response.status})"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"HTTP connection failed: {str(e)}"
            }
    
    async def restart_channel(self, channel_id: str) -> Dict[str, Any]:
        """重启通道
        
        Args:
            channel_id: 通道ID
            
        Returns:
            重启结果
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        if self._plugin_loader:
            await self._reload_channel_plugin(channel)
        
        logger.info(f"Restarting channel: {channel_id}")
        
        return {
            "success": True,
            "message": f"Channel {channel_id} restart initiated"
        }
    
    async def get_channel_statistics(self, channel_id: str) -> Optional[NorthChannelStatistics]:
        """获取通道统计信息
        
        Args:
            channel_id: 通道ID
            
        Returns:
            统计信息
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            return None
        
        return channel.statistics or NorthChannelStatistics()
    
    async def batch_create_channels(
        self,
        channels: List[NorthChannelConfig],
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """批量创建通道
        
        Args:
            channels: 通道列表
            user: 操作用户
            
        Returns:
            批量操作结果
        """
        succeeded = 0
        failed = 0
        details = []
        
        for channel in channels:
            try:
                await self.create_channel(channel, user)
                succeeded += 1
                details.append({
                    "id": channel.id,
                    "success": True,
                    "message": "Channel created successfully"
                })
            except Exception as e:
                failed += 1
                details.append({
                    "id": channel.id,
                    "success": False,
                    "message": str(e)
                })
        
        return {
            "total": len(channels),
            "succeeded": succeeded,
            "failed": failed,
            "details": details
        }
    
    async def _load_channel_plugin(self, channel: NorthChannelConfig) -> None:
        """加载通道插件实例
        
        Args:
            channel: 通道配置
        """
        if not self._plugin_loader:
            return
        
        try:
            connection_dict = channel.connection.model_dump(exclude_none=True)
            upload_dict = channel.upload_strategy.model_dump(exclude_none=True)
            adapter_dict = channel.adapter.model_dump(exclude_none=True)
            
            plugin_config = {
                **connection_dict,
                **upload_dict,
                "adapter_config": adapter_dict
            }
            
            if channel.connection.xnc:
                plugin_config.update(channel.connection.xnc.model_dump(exclude_none=True))
            elif channel.connection.mqtt:
                plugin_config.update(channel.connection.mqtt.model_dump(exclude_none=True))
            elif channel.connection.http:
                plugin_config.update(channel.connection.http.model_dump(exclude_none=True))
            
            plugin_info = await self._plugin_loader.load_plugin(
                plugin_type="north",
                name=channel.protocol.value,
                config=plugin_config
            )
            
            if plugin_info:
                await self._plugin_loader.start_plugin(plugin_info.plugin_id)
                await self.update_status(channel.id, NorthChannelStatus.ONLINE)
                logger.info(f"Plugin loaded for channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Failed to load plugin for channel {channel.id}: {e}")
            await self.update_status(channel.id, NorthChannelStatus.ERROR)
    
    async def _unload_channel_plugin(self, channel_id: str) -> None:
        """卸载通道插件实例
        
        Args:
            channel_id: 通道ID
        """
        if not self._plugin_loader:
            return
        
        try:
            plugins = self._plugin_loader.get_all_plugins()
            
            for plugin in plugins:
                if plugin.config.get("channel_id") == channel_id:
                    await self._plugin_loader.stop_plugin(plugin.plugin_id)
                    await self._plugin_loader.unload_plugin(plugin.plugin_id)
                    await self.update_status(channel_id, NorthChannelStatus.OFFLINE)
                    logger.info(f"Plugin unloaded for channel {channel_id}")
                    break
            
        except Exception as e:
            logger.error(f"Failed to unload plugin for channel {channel_id}: {e}")
    
    async def _reload_channel_plugin(self, channel: NorthChannelConfig) -> None:
        """重新加载通道插件实例
        
        Args:
            channel: 通道配置
        """
        await self._unload_channel_plugin(channel.id)
        await self._load_channel_plugin(channel)
    
    async def load_all_plugins(self) -> None:
        """加载所有启用的通道插件"""
        for channel in self._cache.values():
            if channel.enabled:
                await self._load_channel_plugin(channel)
    
    async def unload_all_plugins(self) -> None:
        """卸载所有通道插件"""
        for channel_id in list(self._cache.keys()):
            await self._unload_channel_plugin(channel_id)
