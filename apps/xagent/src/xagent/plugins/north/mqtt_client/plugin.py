"""MQTT North Plugin - Bidirectional MQTT client for data upload and command reception"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus
from xagent.xcore.plugins.north import NorthPluginBase
from xagent.xcore.storage.interface import Reading
from xagent.xcore.core.plugin_loader import PluginType

from .constants import (
    DEFAULT_BROKER,
    DEFAULT_PORT,
    DEFAULT_TOPIC,
    DEFAULT_COMMAND_TOPIC,
    DEFAULT_CLIENT_ID,
    DEFAULT_QOS,
    DEFAULT_KEEPALIVE,
    DEFAULT_PUBLISH_MODE,
    DEFAULT_BATCH_SIZE as MQTT_DEFAULT_BATCH_SIZE,
    DEFAULT_INTERVAL as MQTT_DEFAULT_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL as MQTT_DEFAULT_RECONNECT_INTERVAL,
    DEFAULT_RECONNECT_MAX_DELAY as MQTT_DEFAULT_RECONNECT_MAX_DELAY,
    DEFAULT_RETRY_COUNT as MQTT_DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY as MQTT_DEFAULT_RETRY_DELAY,
    PUBLISH_MODE_SINGLE,
    PUBLISH_MODE_BATCH,
)

if TYPE_CHECKING:
    import aiomqtt

logger = logging.getLogger(__name__)

MQTT_AVAILABLE = None
_aiomqtt = None
_DownlinkHandler = None

_SENSITIVE_KEYS = {"password", "secret", "token", "api_key"}


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive fields in config"""
    sanitized = {}
    for key, value in config.items():
        if key in _SENSITIVE_KEYS:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_config(value)
        else:
            sanitized[key] = value
    return sanitized


def _check_mqtt_available():
    """Check if aiomqtt is available"""
    global MQTT_AVAILABLE, _aiomqtt, _DownlinkHandler

    if MQTT_AVAILABLE is not None:
        return MQTT_AVAILABLE

    try:
        import aiomqtt
        from .downlink import DownlinkHandler

        _aiomqtt = aiomqtt
        _DownlinkHandler = DownlinkHandler
        MQTT_AVAILABLE = True
    except ImportError:
        MQTT_AVAILABLE = False
        logger.warning(
            "aiomqtt not installed, MQTT plugin will not work. "
            "Install with: pip install aiomqtt"
        )
    return MQTT_AVAILABLE


class MQTTClientPlugin(NorthPluginBase):
    """
    MQTT North Plugin - Bidirectional MQTT client
    
    Features:
    - Data upload to MQTT Broker (single/batch mode)
    - Subscribe to command topic for downlink commands
    - Automatic reconnection (exponential backoff)
    
    Architecture:
    - plugin.py: Lifecycle management + MQTT protocol handling
    - downlink.py: Downlink command processing + result publishing
    - adapter.py: Data format conversion
    - constants.py: Default configuration values
    """
    
    __plugin_name__ = "mqtt"
    __plugin_type__ = PluginType.NORTH.value
    
    DEFAULT_BATCH_SIZE = MQTT_DEFAULT_BATCH_SIZE
    DEFAULT_INTERVAL = MQTT_DEFAULT_INTERVAL
    DEFAULT_RECONNECT_INTERVAL = MQTT_DEFAULT_RECONNECT_INTERVAL
    DEFAULT_RECONNECT_MAX_DELAY = MQTT_DEFAULT_RECONNECT_MAX_DELAY
    DEFAULT_RETRY_COUNT = MQTT_DEFAULT_RETRY_COUNT
    DEFAULT_RETRY_DELAY = MQTT_DEFAULT_RETRY_DELAY
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "broker": {"type": "string", "default": DEFAULT_BROKER, "title": "Broker Address"},
                "port": {"type": "integer", "default": DEFAULT_PORT, "title": "Broker Port"},
                "username": {"type": ["string", "null"], "default": None, "title": "Username"},
                "password": {"type": ["string", "null"], "default": None, "title": "Password"},
                "client_id": {"type": "string", "default": DEFAULT_CLIENT_ID, "title": "Client ID"},
                "topic": {"type": "string", "default": DEFAULT_TOPIC, "title": "Data Topic"},
                "command_topic": {"type": "string", "default": DEFAULT_COMMAND_TOPIC, "title": "Command Topic"},
                "qos": {"type": "integer", "default": DEFAULT_QOS, "enum": [0, 1, 2], "title": "QoS Level"},
                "keepalive": {"type": "integer", "default": DEFAULT_KEEPALIVE, "title": "Keepalive (seconds)"},
                "publish_mode": {"type": "string", "default": DEFAULT_PUBLISH_MODE, "enum": ["single", "batch"], "title": "Publish Mode"},
                # 新增字段
                "adapter": {
                    "type": "string",
                    "default": "standard",
                    "title": "Adapter Name",
                    "description": "数据适配器名称，对应 adapters/ 目录下的客户适配器"
                },
                "adapter_config": {
                    "type": "object",
                    "default": {},
                    "title": "Adapter Config",
                    "description": "适配器专属配置，不同适配器支持不同参数。例如客户A需要productKey和deviceSN"
                },
            },
        }
    
    @classmethod
    def capabilities(cls) -> List[str]:
        return ["publish", "subscribe"]
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        if not _check_mqtt_available():
            raise RuntimeError("MQTT dependencies not available. Install with: pip install aiomqtt")
        
        self._broker = config.get("broker", DEFAULT_BROKER)
        self._port = config.get("port", DEFAULT_PORT)
        self._topic = config.get("topic", DEFAULT_TOPIC)
        self._command_topic = config.get("command_topic", DEFAULT_COMMAND_TOPIC)
        self._qos = config.get("qos", DEFAULT_QOS)
        self._username = config.get("username")
        self._password = config.get("password")
        self._client_id = config.get("client_id", DEFAULT_CLIENT_ID)
        self._keepalive = config.get("keepalive", DEFAULT_KEEPALIVE)
        self._publish_mode = config.get("publish_mode", DEFAULT_PUBLISH_MODE)
        
        self._client: Optional["aiomqtt.Client"] = None
        
        super().__init__(config, storage, event_bus)
        
        self._downlink_handler = _DownlinkHandler(
            event_bus=event_bus,
            adapter=self._data_adapter,
            plugin=self  # 传递plugin引用，用于topic解析
        )
        
        logger.info(f"MQTT plugin initialized: broker={self._broker}:{self._port}, topic={self._topic}")
        logger.debug(f"MQTT plugin config: {_sanitize_config(config)}")
    
    # ===== Implement hook methods =====
    
    def _create_data_adapter(self) -> Any:
        """创建数据适配器 - 使用注册表"""
        from .adapters import get_adapter

        adapter_name = self.config.get("adapter", "standard")
        adapter_config = self.config.get("adapter_config", {})

        try:
            return get_adapter(adapter_name, adapter_config)
        except ValueError as e:
            logger.warning(f"{e}. Falling back to standard adapter")
            return get_adapter("standard", adapter_config)
    
    # ===== Topic管理（Plugin层：委托给适配器） =====

    def get_subscribe_topics(self) -> List[str]:
        """
        获取需要订阅的Topic列表（委托给适配器）

        Returns:
            需要订阅的Topic列表
        """
        # 从适配器获取订阅topic列表（适配器自己使用config构建context）
        topics = self._data_adapter.get_subscribe_topics()
        
        # 如果适配器没有返回topic，使用默认的command_topic
        return topics if topics else [self._command_topic]
    
    def get_publish_topic(self, publish_type: str = "property") -> str:
        """
        获取发布Topic（委托给适配器）

        Args:
            publish_type: 发布类型（property, connect, disconnect）
        
        Returns:
            发布Topic
        """
        # 从适配器获取发布topic（适配器自己使用config构建context）
        topic = self._data_adapter.get_publish_topic(publish_type)
        
        # 如果适配器没有返回topic，使用默认的topic
        return topic if topic else self._topic
    
    def get_reply_topic(self, command_topic: str) -> str:
        """
        根据命令Topic生成回复Topic（委托给适配器）

        Args:
            command_topic: 命令Topic
        
        Returns:
            回复Topic
        """
        return self._data_adapter.get_reply_topic(command_topic)
    
    def parse_topic_type(self, topic: str) -> str:
        """
        解析Topic类型（委托给适配器）

        Args:
            topic: MQTT Topic
        
        Returns:
            Topic类型
        """
        return self._data_adapter.parse_topic_type(topic)
    
    async def _do_connect(self) -> bool:
        client_kwargs = {
            "hostname": self._broker,
            "port": self._port,
            "identifier": self._client_id,
            "keepalive": self._keepalive,
        }
        
        if self._username:
            client_kwargs["username"] = self._username
            client_kwargs["password"] = self._password
        
        self._client = _aiomqtt.Client(**client_kwargs)
        await self._client.__aenter__()
        return True
    
    async def _do_disconnect(self) -> None:
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error during MQTT disconnect: {e}")
            finally:
                self._client = None
    
    async def _do_send(self, payload: Any) -> bool:
        if not self._client:
            return False
        
        payload_str = self._data_adapter.to_json(payload)
        await self._client.publish(self._topic, payload_str, qos=self._qos)
        logger.debug(f"Published {len(payload_str)} bytes to {self._topic}")
        return True
    
    async def _do_subscribe(self) -> None:
        """Subscribe to command topic and listen for messages"""
        if not self._client:
            return
        
        logger.info(f"Subscribing to command topic: {self._command_topic}")
        await self._client.subscribe(self._command_topic, qos=self._qos)
        
        async for message in self._client.messages:
            if not self._running:
                break
            
            try:
                await asyncio.wait_for(
                    self._handle_mqtt_message(message),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("Command handling timed out")
            except Exception as e:
                logger.error(f"Error handling MQTT message: {e}")
    
    def _is_connection_error(self, exc: Exception) -> bool:
        """Check if exception is a MQTT connection error"""
        if isinstance(exc, ConnectionError):
            return True
        
        if _aiomqtt is not None and hasattr(_aiomqtt, "ConnectionClosedError"):
            try:
                if isinstance(exc, _aiomqtt.ConnectionClosedError):
                    return True
            except TypeError:
                pass
        
        err_str = str(exc)
        if "not currently connected" in err_str or "Disconnected" in err_str:
            return True
        
        if hasattr(exc, "code") and getattr(exc, "code", None) in (4, 128):
            return True
        
        return False
    
    # ===== MQTT-specific methods =====
    
    async def _handle_mqtt_message(self, message: "aiomqtt.Message") -> None:
        """Handle MQTT message - delegates to DownlinkHandler"""
        result_topic = f"{self._command_topic}/result"
        
        await self._downlink_handler.handle_message(
            message=message,
            publish_callback=self._publish_to_topic,
            result_topic=result_topic
        )
    
    async def _publish_to_topic(self, topic: str, payload: str) -> None:
        """Publish payload to specified topic"""
        if not self._client:
            logger.warning("Cannot publish: client not connected")
            return
        
        try:
            await self._client.publish(topic=topic, payload=payload, qos=self._qos)
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
    
    # ===== Override send method for single/batch mode =====
    
    async def send(self, readings: List[Reading]) -> int:
        """Send data to MQTT Broker (supports single/batch mode)"""
        if not self._connected:
            if not await self._reconnect():
                return 0
        
        if not readings:
            return 0
        
        if self._publish_mode == PUBLISH_MODE_BATCH:
            sent = await self._send_batch(readings)
        else:
            sent = await self._send_single(readings)
        
        success = sent > 0
        sent_count = sent if success else 0
        
        if self._stats_manager:
            await self._stats_manager.record_channel_stats(
                self._service_name,
                sent_count,
                success=success
            )
        
        return sent
    
    async def _send_single(self, readings: List[Reading]) -> int:
        """Send readings one by one"""
        sent = 0
        
        for reading in readings:
            try:
                context = {
                    "timestamp": time.time(),
                    "device_status_map": {r.asset: r.device_status for r in [reading] if r.device_status}
                }
                
                payload = self.adapt_readings([reading], context)
                if payload is None:
                    continue
                
                success = await self._send_with_retry(payload)
                if success:
                    sent += 1
                    
            except Exception as e:
                if self._is_connection_error(e):
                    self._connected = False
                    break
                logger.error(f"Error sending reading: {e}")
        
        if sent > 0:
            logger.info(f"Published {sent} readings to {self._topic}")
        
        return sent
    
    async def _send_batch(self, readings: List[Reading]) -> int:
        """Send readings in batch"""
        try:
            context = {
                "timestamp": time.time(),
                "device_status_map": {r.asset: r.device_status for r in readings if r.device_status}
            }
            
            payload = self.adapt_readings(readings, context)
            if payload is None:
                return 0
            
            success = await self._send_with_retry(payload)
            if success:
                logger.info(f"Published {len(readings)} readings (batch) to {self._topic}")
                return len(readings)
            
        except Exception as e:
            if self._is_connection_error(e):
                self._connected = False
            logger.error(f"Error batch publishing: {e}")
        
        return 0
