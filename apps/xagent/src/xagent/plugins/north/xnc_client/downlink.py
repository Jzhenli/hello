"""XNC Downlink Handler - Handles incoming commands and sends responses

Downlink: External system → XAgent (commands, read/write requests)
Uplink: XAgent → External system (data upload, property updates)
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus, Event, EventType

from .generated import MessageType, errorCode, apiMsg
from .codec import ProtobufCodec
from .mapping import DeviceMapper
from .protocol import UDPProtocolCodec

if TYPE_CHECKING:
    import asyncio

logger = logging.getLogger(__name__)


@dataclass
class DownlinkResult:
    """Downlink command execution result"""
    success: bool
    device_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DownlinkHandler:
    """
    XNC Downlink Handler
    
    Responsibilities:
    - Handle Protobuf format commands (READ_PROPERTY, WRITE_PROPERTY)
    - Handle JSON format commands
    - Send responses back to client
    
    Does NOT handle:
    - Connection management
    - UDP protocol details
    - Lifecycle management
    
    Usage:
        handler = DownlinkHandler(mapper, event_bus)
        
        # Handle Protobuf command
        result = await handler.handle_protobuf(data, addr, transport)
        
        # Handle JSON command
        result = await handler.handle_json(data, addr, transport)
    """
    
    def __init__(
        self,
        mapper: DeviceMapper,
        event_bus: EventBus,
        protocol_codec: Optional[UDPProtocolCodec] = None
    ):
        self._mapper = mapper
        self._event_bus = event_bus
        self._protocol_codec = protocol_codec or UDPProtocolCodec()
    
    async def handle_protobuf(
        self,
        data: bytes,
        addr: tuple,
        transport: Optional["asyncio.DatagramTransport"] = None
    ) -> DownlinkResult:
        """Handle Protobuf format command
        
        Args:
            data: Raw UDP packet data
            addr: Client address (host, port)
            transport: UDP transport for sending response
            
        Returns:
            DownlinkResult with execution status
        """
        try:
            sequence, payload = self._protocol_codec.decode(data)
            msg = ProtobufCodec.decode_message(payload)
            
            logger.info(f"Received protobuf command from {addr}, seq={sequence}, cmd={msg.cmdID}")
            
            if msg.cmdID == MessageType.READ_PROPERTY:
                result = await self._handle_read_property(msg)
            elif msg.cmdID == MessageType.WRITE_PROPERTY:
                result = await self._handle_write_property(msg)
            else:
                logger.warning(f"Unknown command type: {msg.cmdID}")
                result = DownlinkResult(success=False, error=f"Unknown command type: {msg.cmdID}")
            
            if transport:
                await self._send_protobuf_response(addr, transport, sequence, msg, result)
            
            return result
            
        except ValueError as e:
            logger.error(f"Protocol decode error: {e}")
            return DownlinkResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"Error handling protobuf command: {e}", exc_info=True)
            return DownlinkResult(success=False, error=str(e))
    
    async def handle_json(
        self,
        data: bytes,
        addr: tuple,
        transport: Optional["asyncio.DatagramTransport"] = None
    ) -> DownlinkResult:
        """Handle JSON format command
        
        Args:
            data: Raw JSON data
            addr: Client address (host, port)
            transport: UDP transport for sending response
            
        Returns:
            DownlinkResult with execution status
        """
        try:
            payload = data.decode("utf-8")
            logger.info(f"Received JSON command from {addr}: {payload}")
            
            command = json.loads(payload)
            asset = command.get("asset")
            cmd_data = command.get("data")
            
            if not asset or not cmd_data:
                logger.warning("Invalid command: missing asset or data")
                result = DownlinkResult(success=False, error="Invalid command: missing asset or data")
            else:
                await self._event_bus.publish(Event(
                    event_type=EventType.COMMAND_RECEIVED,
                    data={"asset": asset, "data": cmd_data}
                ))
                result = DownlinkResult(success=True, device_id=asset, data=cmd_data)
            
            if transport:
                await self._send_json_response(addr, transport, result)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON command: {e}")
            result = DownlinkResult(success=False, error=f"Invalid JSON: {str(e)}")
            if transport:
                await self._send_json_response(addr, transport, result)
            return result
        except Exception as e:
            logger.error(f"Error handling JSON command: {e}", exc_info=True)
            result = DownlinkResult(success=False, error=str(e))
            if transport:
                await self._send_json_response(addr, transport, result)
            return result
    
    async def _handle_read_property(self, msg: apiMsg) -> DownlinkResult:
        """Handle READ_PROPERTY command"""
        decoded = self._mapper.decode_message(msg)
        device_id = decoded.device_id
        
        logger.info(f"READ_PROPERTY request for device {device_id}")
        
        await self._event_bus.publish(Event(
            event_type=EventType.COMMAND_RECEIVED,
            data={
                "asset": device_id,
                "command": "read_property",
                "points": list(decoded.data.keys())
            }
        ))
        
        return DownlinkResult(
            success=True,
            device_id=device_id,
            data=decoded.data
        )
    
    async def _handle_write_property(self, msg: apiMsg) -> DownlinkResult:
        """Handle WRITE_PROPERTY command"""
        decoded = self._mapper.decode_message(msg)
        device_id = decoded.device_id
        data = decoded.data
        
        logger.info(f"WRITE_PROPERTY request for device {device_id}: {data}")
        
        await self._event_bus.publish(Event(
            event_type=EventType.COMMAND_RECEIVED,
            data={
                "asset": device_id,
                "command": "write_property",
                "data": data
            }
        ))
        
        return DownlinkResult(
            success=True,
            device_id=device_id,
            data=data
        )
    
    async def _send_protobuf_response(
        self,
        addr: tuple,
        transport: "asyncio.DatagramTransport",
        sequence: int,
        request_msg: apiMsg,
        result: DownlinkResult
    ) -> None:
        """Send Protobuf response"""
        try:
            response_msg = apiMsg()
            response_msg.uuid = request_msg.uuid
            response_msg.cmdID = request_msg.cmdID
            response_msg.vdID = request_msg.vdID
            response_msg.status = errorCode.NO_ERROR if result.success else errorCode.OPERATIONAL_PROBLEM
            
            for obj in request_msg.opv:
                response_msg.opv.append(obj)
            
            payload_bytes = ProtobufCodec.encode_message(response_msg)
            packet = self._protocol_codec.encode(payload_bytes, sequence)
            
            transport.sendto(packet, addr)
            logger.debug(f"Sent protobuf response to {addr}, seq={sequence}")
            
        except Exception as e:
            logger.error(f"Error sending protobuf response: {e}")
    
    async def _send_json_response(
        self,
        addr: tuple,
        transport: "asyncio.DatagramTransport",
        result: DownlinkResult
    ) -> None:
        """Send JSON response"""
        try:
            response = {
                "status": "success" if result.success else "error",
                "timestamp": time.time()
            }
            
            if result.success:
                if result.device_id:
                    response["asset"] = result.device_id
                if result.data:
                    response["data"] = result.data
            else:
                response["error"] = result.error
            
            response_json = json.dumps(response, ensure_ascii=False)
            response_bytes = response_json.encode("utf-8")
            transport.sendto(response_bytes, addr)
            logger.debug(f"Sent JSON response to {addr}")
            
        except Exception as e:
            logger.error(f"Error sending JSON response: {e}")


# Backward compatibility alias
CommandHandler = DownlinkHandler
CommandResult = DownlinkResult
