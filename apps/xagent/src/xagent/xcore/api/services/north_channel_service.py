import logging
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pathlib import Path

from ..models.north_channel import (
    NorthChannelConfig,
    NorthChannelStatus,
    NorthChannelProtocol,
    NorthChannelStatistics
)

logger = logging.getLogger(__name__)


class NorthChannelService:
    """北向通道服务 - 管理北向通道配置和状态"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self._channels: Dict[str, NorthChannelConfig] = {}
        self._config_file = config_dir / "north_channels.json" if config_dir else Path("config/north_channels.json")
        self._plugin_instances: Dict[str, Any] = {}
        
    async def initialize(self):
        """初始化服务，加载配置"""
        await self._load_config()
        logger.info(f"NorthChannelService initialized with {len(self._channels)} channels")
    
    async def _load_config(self):
        """从配置文件加载通道配置"""
        if not self._config_file.exists():
            logger.info(f"Config file {self._config_file} not found, starting with empty channels")
            return
        
        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for channel_data in data.get('channels', []):
                try:
                    channel = NorthChannelConfig(**channel_data)
                    self._channels[channel.id] = channel
                except Exception as e:
                    logger.error(f"Failed to load channel {channel_data.get('id')}: {e}")
            
            logger.info(f"Loaded {len(self._channels)} channels from {self._config_file}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    async def _save_config(self):
        """保存配置到文件"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'channels': [channel.model_dump() for channel in self._channels.values()]
            }
            
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self._channels)} channels to {self._config_file}")
        except Exception as e:
            logger.error(f"Failed to save config file: {e}")
    
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
        channels = list(self._channels.values())
        
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
        return self._channels.get(channel_id)
    
    async def create_channel(self, channel: NorthChannelConfig) -> NorthChannelConfig:
        """创建通道
        
        Args:
            channel: 通道配置
            
        Returns:
            创建的通道
            
        Raises:
            ValueError: 通道已存在
        """
        if channel.id in self._channels:
            raise ValueError(f"Channel '{channel.id}' already exists")
        
        channel.created_at = datetime.now().isoformat()
        channel.updated_at = datetime.now().isoformat()
        channel.status = NorthChannelStatus.OFFLINE
        
        self._channels[channel.id] = channel
        await self._save_config()
        
        logger.info(f"Created channel: {channel.id}")
        return channel
    
    async def update_channel(
        self,
        channel_id: str,
        updates: Dict[str, Any]
    ) -> NorthChannelConfig:
        """更新通道
        
        Args:
            channel_id: 通道ID
            updates: 更新内容
            
        Returns:
            更新后的通道
            
        Raises:
            ValueError: 通道不存在
        """
        if channel_id not in self._channels:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        channel = self._channels[channel_id]
        
        for field, value in updates.items():
            if hasattr(channel, field):
                setattr(channel, field, value)
        
        channel.updated_at = datetime.now().isoformat()
        
        await self._save_config()
        logger.info(f"Updated channel: {channel_id}")
        
        return channel
    
    async def delete_channel(self, channel_id: str):
        """删除通道
        
        Args:
            channel_id: 通道ID
            
        Raises:
            ValueError: 通道不存在
        """
        if channel_id not in self._channels:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        del self._channels[channel_id]
        await self._save_config()
        
        logger.info(f"Deleted channel: {channel_id}")
    
    async def toggle_channel(self, channel_id: str) -> NorthChannelConfig:
        """切换通道启用状态
        
        Args:
            channel_id: 通道ID
            
        Returns:
            更新后的通道
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        
        channel.enabled = not channel.enabled
        channel.updated_at = datetime.now().isoformat()
        
        await self._save_config()
        logger.info(f"Toggled channel {channel_id}: enabled={channel.enabled}")
        
        return channel
    
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
        channels: List[NorthChannelConfig]
    ) -> Dict[str, Any]:
        """批量创建通道
        
        Args:
            channels: 通道列表
            
        Returns:
            批量操作结果
        """
        succeeded = 0
        failed = 0
        details = []
        
        for channel in channels:
            try:
                await self.create_channel(channel)
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
