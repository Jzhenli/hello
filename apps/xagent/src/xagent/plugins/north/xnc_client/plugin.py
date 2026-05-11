"""XNC Client Plugin - UDP-based bidirectional north plugin with Protobuf support"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from xagent.xcore.core.event_bus import EventBus, Event, EventType
from xagent.xcore.plugins.north import NorthPluginBase
from xagent.xcore.storage.interface import Reading
from .adapter import XNCJsonAdapter, XNCProtobufAdapter
from .protocol import UDPProtocolCodec
from .codec import ProtobufCodec
from .generated import MessageType, apiMsg
from .constants import (
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_PORT,
    DEFAULT_LOCAL_PORT,
    DEFAULT_BATCH_SIZE,
    DEFAULT_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL,
    PROTOCOL_MODE_PROTOBUF,
)

logger = logging.getLogger(__name__)


class UDPCommandProtocol(asyncio.DatagramProtocol):
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
    def __init__(self):
        self.transport = None
    
    def connection_made(self, transport):
        self.transport = transport
    
    def error_received(self, exc):
        logger.error(f"UDP send error: {exc}")


class XNCClientPlugin(NorthPluginBase):
    """
    XNC 北向插件
    
    支持：
    - UDP 协议数据上传
    - JSON 和 Protobuf 格式
    - 下行命令接收
    """
    
    __plugin_name__ = "xnc_client"
    
    def _create_data_adapter(self) -> Any:
        """创建数据适配器"""
        adapter_config = self.config.get("adapter_config", {})
        adapter_name = self.config.get("adapter", "xnc_protobuf" if self._protocol_mode == PROTOCOL_MODE_PROTOBUF else "xnc_json")
        
        if adapter_name == "xnc_protobuf":
            adapter_config["mapping_config"] = self.config.get("mapping_config", {})
            return XNCProtobufAdapter(adapter_config)
        else:
            return XNCJsonAdapter(adapter_config)
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        logger.info(f"Initializing XNC Client plugin with config: {config}")
        
        self._protocol_mode = config.get("protocol", PROTOCOL_MODE_PROTOBUF)
        
        super().__init__(config, storage, event_bus)
        
        self._remote_host = config.get("remote_host", DEFAULT_REMOTE_HOST)
        self._remote_port = config.get("remote_port", DEFAULT_REMOTE_PORT)
        self._local_port = config.get("local_port", DEFAULT_LOCAL_PORT)
        self._batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
        self._interval = config.get("interval", DEFAULT_INTERVAL)
        self._reconnect_interval = config.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL)
        
        self._send_transport = None
        self._command_transport = None
        self._upload_task: Optional[asyncio.Task] = None
        
        self._protocol_codec = UDPProtocolCodec()
        
        logger.info(
            f"XNC Client plugin initialized: "
            f"remote={self._remote_host}:{self._remote_port}, "
            f"local_port={self._local_port}, "
            f"protocol={self._protocol_mode}"
        )
    
    async def connect(self) -> bool:
        try:
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
            
            self._connected = True
            logger.info(
                f"XNC Client connected: "
                f"remote={self._remote_host}:{self._remote_port}, "
                f"listening on port {self._local_port}"
            )
            return True
            
        except Exception as e:
            logger.error(f"XNC Client connection failed: {e}")
            await self._cleanup_connection()
            return False
    
    async def disconnect(self) -> None:
        if self._upload_task:
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass
            self._upload_task = None
        
        await self._cleanup_connection()
        self._running = False
        logger.info("XNC Client disconnected")
    
    async def _cleanup_connection(self) -> None:
        self._connected = False
        
        if self._command_transport:
            try:
                self._command_transport.close()
            except Exception as e:
                logger.debug(f"Error closing command transport: {e}")
            finally:
                self._command_transport = None
        
        if self._send_transport:
            try:
                self._send_transport.close()
            except Exception as e:
                logger.debug(f"Error closing send transport: {e}")
            finally:
                self._send_transport = None
    
    async def start(self) -> None:
        if self._running:
            logger.info("XNC Client plugin already running")
            return
        
        logger.info(f"Starting XNC Client plugin")
        success = await self.connect()
        if success:
            self._running = True
            self._upload_task = asyncio.create_task(self._upload_loop())
            logger.info(f"North plugin started: {self._service_name}")
        else:
            raise RuntimeError(f"Failed to connect north plugin: {self._service_name}")
    
    async def stop(self) -> None:
        if not self._running:
            return
        
        await self.disconnect()
        logger.info(f"North plugin stopped: {self._service_name}")
    
    async def send(self, readings: List[Reading]) -> int:
        if not self._connected or not self._send_transport:
            logger.warning("XNC Client not connected, cannot send")
            return 0
        
        if not readings:
            logger.debug("No readings to send")
            return 0
        
        logger.info(f"Starting to send {len(readings)} readings via UDP ({self._protocol_mode})")
        sent = 0
        
        if self._protocol_mode == PROTOCOL_MODE_PROTOBUF:
            sent = await self._send_protobuf(readings)
        else:
            sent = await self._send_json(readings)
        
        if sent > 0:
            logger.info(f"Sent {sent} readings to {self._remote_host}:{self._remote_port}")
        
        return sent
    
    async def _send_protobuf(self, readings: List[Reading]) -> int:
        sent = 0
        context = {"timestamp": time.time()}
        
        for i, reading in enumerate(readings):
            try:
                logger.debug(f"_send_protobuf: processing reading {i+1}/{len(readings)}")
                
                msgs = self.adapt_readings([reading], context)
                if msgs is None:
                    logger.warning(f"Adapter returned None for reading {reading.asset}")
                    continue
                
                if not isinstance(msgs, list):
                    msgs = [msgs]
                
                logger.info(f"Adapted {len(msgs)} messages for reading {reading.asset}")
                
                for msg in msgs:
                    logger.debug(f"Sending message: uuid={msg.uuid}, cmdID={msg.cmdID}, "
                                f"vdID={msg.vdID}, objects_count={len(msg.opv)}")
                    
                    payload_bytes = ProtobufCodec.encode_message(msg)
                    logger.debug(f"Encoded payload: {len(payload_bytes)} bytes")
                    
                    packet = self._protocol_codec.encode(payload_bytes)
                    logger.debug(f"Encoded packet: {len(packet)} bytes")
                    
                    self._send_transport.sendto(packet)
                    sent += 1
                
                logger.debug(f"Sent reading {i+1}/{len(readings)}: {reading.asset}")
                
            except Exception as e:
                logger.error(f"Error sending reading: {e}", exc_info=True)
        
        return sent
    
    async def _send_json(self, readings: List[Reading]) -> int:
        sent = 0
        context = {"timestamp": time.time()}
        
        for i, reading in enumerate(readings):
            try:
                adapted_payload = self.adapt_readings([reading], context)
                payload_json = self._data_adapter.to_json(adapted_payload)
                payload_bytes = payload_json.encode("utf-8")
                
                self._send_transport.sendto(payload_bytes)
                sent += 1
                logger.debug(f"Sent reading {i+1}/{len(readings)}: {reading.asset}")
                
            except Exception as e:
                logger.error(f"Error sending reading: {e}")
        
        return sent
    
    async def _upload_loop(self) -> None:
        logger.info(f"XNC Client upload loop started, interval={self._interval}s")
        while self._running:
            try:
                if not self._connected:
                    logger.warning("Not connected, waiting...")
                    await asyncio.sleep(self._reconnect_interval)
                    continue
                
                logger.debug(f"Upload loop: fetching data (batch_size={self._batch_size})")
                await self.fetch_and_send(self._batch_size)
                logger.debug(f"Upload loop: waiting {self._interval}s")
                await asyncio.sleep(self._interval)
                
            except asyncio.CancelledError:
                logger.info("Upload loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in upload loop: {e}")
                await asyncio.sleep(self._interval)
    
    async def _handle_command_data(self, data: bytes, addr: tuple) -> None:
        try:
            if self._protocol_mode == PROTOCOL_MODE_PROTOBUF:
                await self._handle_protobuf_command(data, addr)
            else:
                await self._handle_json_command(data, addr)
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
    
    async def _handle_protobuf_command(self, data: bytes, addr: tuple) -> None:
        try:
            sequence, payload = self._protocol_codec.decode(data)
            logger.info(f"Received protobuf command from {addr}, seq={sequence}")
            
            msg = ProtobufCodec.decode_message(payload)
            msg_dict = ProtobufCodec.message_to_dict(msg)
            logger.debug(f"Decoded message: {msg_dict}")
            
            if msg.cmdID == MessageType.READ_PROPERTY:
                await self._handle_read_property(msg, addr, sequence)
            elif msg.cmdID == MessageType.WRITE_PROPERTY:
                await self._handle_write_property(msg, addr, sequence)
            else:
                logger.warning(f"Unknown command type: {msg.cmdID}")
                await self._send_protobuf_response(addr, sequence, msg, error="Unknown command type")
                
        except ValueError as e:
            logger.error(f"Protocol decode error: {e}")
        except Exception as e:
            logger.error(f"Error handling protobuf command: {e}", exc_info=True)
    
    async def _handle_read_property(self, msg: apiMsg, addr: tuple, sequence: int) -> None:
        context = {"timestamp": time.time()}
        parsed = self.parse_response(msg, context)
        device_id = parsed.get("device_id")
        
        logger.info(f"READ_PROPERTY request for device {device_id}")
        
        event = Event(
            event_type=EventType.COMMAND_RECEIVED,
            data={
                "asset": device_id,
                "command": "read_property",
                "points": list(parsed.get("data", {}).keys())
            }
        )
        await self.event_bus.publish(event)
        
        await self._send_protobuf_response(addr, sequence, msg)
    
    async def _handle_write_property(self, msg: apiMsg, addr: tuple, sequence: int) -> None:
        context = {"timestamp": time.time()}
        parsed = self.parse_response(msg, context)
        device_id = parsed.get("device_id")
        data = parsed.get("data", {})
        
        logger.info(f"WRITE_PROPERTY request for device {device_id}: {data}")
        
        event = Event(
            event_type=EventType.COMMAND_RECEIVED,
            data={
                "asset": device_id,
                "command": "write_property",
                "data": data
            }
        )
        await self.event_bus.publish(event)
        logger.info(f"Published COMMAND_RECEIVED event for device {device_id}")
        
        await self._send_protobuf_response(addr, sequence, msg)
    
    async def _send_protobuf_response(
        self,
        addr: tuple,
        sequence: int,
        request_msg: apiMsg,
        error: Optional[str] = None
    ) -> None:
        if not self._command_transport:
            logger.warning("Cannot send response: transport not available")
            return
        
        try:
            response_msg = apiMsg()
            response_msg.uuid = request_msg.uuid
            response_msg.cmdID = request_msg.cmdID
            response_msg.vdID = request_msg.vdID
            
            if error:
                from .generated import errorCode
                response_msg.status = errorCode.OPERATIONAL_PROBLEM
            else:
                from .generated import errorCode
                response_msg.status = errorCode.NO_ERROR
            
            for obj in request_msg.opv:
                response_msg.opv.append(obj)
            
            payload_bytes = ProtobufCodec.encode_message(response_msg)
            packet = self._protocol_codec.encode(payload_bytes, sequence)
            
            self._command_transport.sendto(packet, addr)
            logger.debug(f"Sent protobuf response to {addr}, seq={sequence}")
            
        except Exception as e:
            logger.error(f"Error sending protobuf response: {e}")
    
    async def _handle_json_command(self, data: bytes, addr: tuple) -> None:
        try:
            payload = data.decode("utf-8")
            logger.info(f"Received JSON command from {addr}: {payload}")
            
            command = json.loads(payload)
            
            asset = command.get("asset")
            cmd_data = command.get("data")
            
            if not asset or not cmd_data:
                logger.warning("Invalid command: missing asset or data")
                await self._send_json_response(addr, {
                    "status": "error",
                    "error": "Invalid command: missing asset or data"
                })
                return
            
            logger.info(f"Executing command for asset {asset}: {cmd_data}")
            
            event = Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={
                    "asset": asset,
                    "data": cmd_data
                }
            )
            await self.event_bus.publish(event)
            logger.info(f"Published COMMAND_RECEIVED event for asset {asset}")
            
            await self._send_json_response(addr, {
                "status": "success",
                "asset": asset,
                "data": cmd_data
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON command: {e}")
            await self._send_json_response(addr, {
                "status": "error",
                "error": f"Invalid JSON: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Error handling JSON command: {e}", exc_info=True)
            await self._send_json_response(addr, {
                "status": "error",
                "error": str(e)
            })
    
    async def _send_json_response(self, addr: tuple, response: Dict[str, Any]) -> None:
        if not self._command_transport:
            logger.warning("Cannot send response: transport not available")
            return
        
        try:
            response_json = json.dumps(response, ensure_ascii=False)
            response_bytes = response_json.encode("utf-8")
            self._command_transport.sendto(response_bytes, addr)
            logger.debug(f"Sent JSON response to {addr}: {response_json}")
        except Exception as e:
            logger.error(f"Error sending JSON response: {e}")
    
    async def fetch_and_send(self, batch_size: int = 100) -> int:
        if not self.storage:
            logger.warning("Storage not available")
            return 0
        
        try:
            logger.debug(f"Querying storage for readings (limit={batch_size * 2})")
            readings = await self.storage.query(limit=batch_size * 2)
            logger.info(f"Queried {len(readings)} readings from storage")
            
            if not readings:
                logger.debug("No readings to send")
                return 0
            
            latest_readings_by_asset = {}
            for reading in readings:
                asset = reading.asset
                if asset not in latest_readings_by_asset or \
                   reading.timestamp > latest_readings_by_asset[asset].timestamp:
                    latest_readings_by_asset[asset] = reading
            
            latest_readings = list(latest_readings_by_asset.values())[:batch_size]
            logger.info(f"Filtered to {len(latest_readings)} latest readings")
            
            sent = await self.send(latest_readings)
            logger.info(f"Sent {sent} readings via XNC Client")
            return sent
            
        except Exception as e:
            logger.error(f"Error fetching and sending readings: {e}", exc_info=True)
            return 0
