"""XNC Client Plugin - UDP-based bidirectional north plugin with Protobuf support"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from xagent.xcore.core.event_bus import EventBus
from xagent.xcore.plugins.north import NorthPluginBase
from xagent.xcore.storage.interface import Reading
from .adapter import XNCProtobufAdapter
from .mapping import DeviceMapper
from .protocol import UDPProtocolCodec
from .codec import ProtobufCodec
from .downlink import DownlinkHandler
from .generated import apiMsg
from .constants import (
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_PORT,
    DEFAULT_LOCAL_PORT,
    DEFAULT_BATCH_SIZE as XNC_DEFAULT_BATCH_SIZE,
    DEFAULT_INTERVAL as XNC_DEFAULT_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL as XNC_DEFAULT_RECONNECT_INTERVAL,
)

logger = logging.getLogger(__name__)


class UDPCommandProtocol(asyncio.DatagramProtocol):
    """UDP command listener protocol"""
    
    def __init__(self, plugin: "XNCClientPlugin"):
        self.plugin = plugin
        self.transport = None
    
    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"UDP command listener started on port {self.plugin._local_port}")
    
    def datagram_received(self, data: bytes, addr: tuple):
        asyncio.create_task(self.plugin._handle_command_data(data, addr))
    
    def error_received(self, exc):
        logger.error(f"UDP command listener error: {exc}")
    
    def connection_lost(self, exc):
        logger.info("UDP command listener connection closed")


class UDPSendProtocol(asyncio.DatagramProtocol):
    """UDP send protocol"""
    
    def __init__(self):
        self.transport = None
    
    def connection_made(self, transport):
        self.transport = transport
    
    def error_received(self, exc):
        logger.error(f"UDP send error: {exc}")


class XNCClientPlugin(NorthPluginBase):
    """
    XNC Client Plugin - UDP-based bidirectional north plugin
    
    Features:
    - UDP protocol data upload
    - Protobuf format support
    - Downlink command reception
    - Automatic device/point mapping
    
    Architecture:
    - plugin.py: Lifecycle management + UDP protocol handling
    - downlink.py: Downlink command processing + response sending
    - mapping.py: Device/point bidirectional mapping
    - adapter.py: Data format conversion
    - codec.py: Protobuf encoding/decoding
    - protocol.py: UDP packet encoding/decoding
    """
    
    __plugin_name__ = "xnc"
    
    DEFAULT_BATCH_SIZE = XNC_DEFAULT_BATCH_SIZE
    DEFAULT_INTERVAL = XNC_DEFAULT_INTERVAL
    DEFAULT_RECONNECT_INTERVAL = XNC_DEFAULT_RECONNECT_INTERVAL
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        conn = config.get("connection", {})
        self._remote_host = conn.get("remote_host", DEFAULT_REMOTE_HOST)
        self._remote_port = conn.get("remote_port", DEFAULT_REMOTE_PORT)
        self._local_port = conn.get("local_port", DEFAULT_LOCAL_PORT)
        
        self._send_transport = None
        self._command_transport = None
        self._protocol_codec = UDPProtocolCodec()
        
        super().__init__(config, storage, event_bus)
        
        self._command_handler = DownlinkHandler(
            mapper=self._mapper,
            event_bus=event_bus,
            protocol_codec=self._protocol_codec
        )
        
        logger.info(
            f"XNC Client plugin initialized: "
            f"remote={self._remote_host}:{self._remote_port}, "
            f"local_port={self._local_port}"
        )
    
    # ===== Override properties to use XNC-specific mapper =====
    
    def _resolve_mapping_config(self) -> Dict[str, Any]:
        """Resolve mapping_config from adapter config."""
        adapter_cfg = self.config.get("adapter", {})
        mapping_config = adapter_cfg.get("mapping_config")
        if isinstance(mapping_config, dict) and mapping_config:
            return mapping_config
        return {}

    @property
    def _mapper(self) -> DeviceMapper:
        """Get or create DeviceMapper"""
        if not hasattr(self, '_xnc_mapper'):
            mapping_config = self._resolve_mapping_config()
            self._xnc_mapper = DeviceMapper(mapping_config=mapping_config)
        return self._xnc_mapper

    # ===== Implement hook methods =====
    
    def _create_data_adapter(self) -> Any:
        adapter_cfg = self.config.get("adapter", {})
        return XNCProtobufAdapter(mapper=self._mapper, config=adapter_cfg.get("config", {}))
    
    async def _do_connect(self) -> bool:
        loop = asyncio.get_event_loop()
        
        self._send_transport, _ = await loop.create_datagram_endpoint(
            UDPSendProtocol,
            remote_addr=(self._remote_host, self._remote_port)
        )
        
        local_addr = ("0.0.0.0", self._local_port)
        self._command_transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPCommandProtocol(self),
            local_addr=local_addr
        )
        
        return True
    
    async def _do_disconnect(self) -> None:
        for transport in [self._command_transport, self._send_transport]:
            if transport:
                try:
                    transport.close()
                except Exception as e:
                    logger.debug(f"Error closing transport: {e}")
        
        self._command_transport = None
        self._send_transport = None
    
    async def _do_send(self, payload: Any) -> bool:
        if not self._send_transport:
            return False
        
        return await self._send_protobuf_payload(payload)
    
    async def _do_subscribe(self) -> None:
        """UDP doesn't need active subscription, commands received via UDPCommandProtocol"""
        while self._running:
            await asyncio.sleep(1)
    
    # ===== XNC-specific methods =====
    
    async def _send_protobuf_payload(self, payload: Any) -> bool:
        """Send Protobuf format data"""
        try:
            messages = payload if isinstance(payload, list) else [payload]
            
            for msg in messages:
                if not isinstance(msg, apiMsg):
                    continue
                
                payload_bytes = ProtobufCodec.encode_message(msg)
                packet = self._protocol_codec.encode(payload_bytes)
                self._send_transport.sendto(packet)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending protobuf: {e}")
            return False
    
    async def _handle_command_data(self, data: bytes, addr: tuple) -> None:
        """Handle received command data - delegates to CommandHandler"""
        try:
            await self._command_handler.handle_protobuf(
                data, addr, self._command_transport
            )
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
    
    # ===== Override send method for Protobuf batch support =====
    
    async def send(self, readings: List[Reading]) -> int:
        """Send data (supports Protobuf batch sending)"""
        if not self._connected:
            if not await self._reconnect():
                return 0
        
        if not readings:
            return 0
        
        logger.info(f"Sending {len(readings)} readings via UDP")
        
        context = {"timestamp": time.time()}
        payload = self.adapt_readings(readings, context)
        
        if payload is None:
            return 0
        
        messages = payload if isinstance(payload, list) else [payload]
        sent = 0
        
        for msg in messages:
            if await self._send_protobuf_payload(msg):
                sent += 1
        
        if sent > 0:
            logger.info(f"Sent {sent} protobuf messages to {self._remote_host}:{self._remote_port}")
        
        success = sent > 0
        sent_count = len(readings) if success else 0
        
        if self._stats_manager:
            await self._stats_manager.record_channel_stats(
                self._service_name,
                sent_count,
                success=success
            )
        
        return sent
