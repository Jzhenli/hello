"""XNC UDP Server - Receives data from XAgent and sends commands"""

import asyncio
import json
import socket
import sys
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

_src_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if os.path.exists(_src_path):
    sys.path.insert(0, _src_path)

from protocol import UDPProtocolCodec
from codec import ProtobufCodec

try:
    from xagent.plugins.north.xnc_client.generated import MessageType, errorCode, apiMsg
except ImportError:
    from generated import MessageType, errorCode, apiMsg


@dataclass
class ReceivedMessage:
    """Received message from XAgent"""
    timestamp: float
    client_addr: Tuple[str, int]
    sequence: int
    raw_data: bytes
    parsed_data: Dict[str, Any]
    message_type: str = ""
    device_id: Optional[str] = None
    points: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceMapping:
    """Device and point mapping"""
    vdid_to_device: Dict[int, str] = field(default_factory=dict)
    device_to_vdid: Dict[str, int] = field(default_factory=dict)
    oid_to_point: Dict[int, Tuple[str, str]] = field(default_factory=dict)
    point_to_oid: Dict[Tuple[str, str], int] = field(default_factory=dict)
    
    next_vdid: int = 1
    next_oid: int = 1


class XNCUDPServer:
    """XNC UDP Server for receiving data and sending commands"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        on_message_received: Optional[Callable[[ReceivedMessage], None]] = None,
        on_client_connected: Optional[Callable[[Tuple[str, int]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.host = host
        self.port = port
        self.on_message_received = on_message_received
        self.on_client_connected = on_client_connected
        self.on_error = on_error
        
        self._protocol_codec = UDPProtocolCodec()
        self._mapping = DeviceMapping()
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._receive_thread: Optional[threading.Thread] = None
        self._clients: Dict[Tuple[str, int], float] = {}
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the UDP server"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.settimeout(1.0)
            
            self._running = True
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()
            
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to start server: {e}")
            return False
    
    def stop(self):
        """Stop the UDP server"""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
        if self._receive_thread:
            self._receive_thread.join(timeout=2.0)
    
    def _receive_loop(self):
        """Main receive loop"""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                self._handle_data(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running and self.on_error:
                    self.on_error(f"Receive error: {e}")
    
    def _handle_data(self, data: bytes, addr: Tuple[str, int]):
        """Handle received data"""
        try:
            with self._lock:
                self._clients[addr] = time.time()
            
            if self.on_client_connected:
                self.on_client_connected(addr)
            
            sequence, payload = self._protocol_codec.decode(data)
            msg = ProtobufCodec.decode_message(payload)
            
            parsed = ProtobufCodec.message_to_dict(msg)
            
            device_id = self._update_mapping(msg, parsed)
            
            points = self._extract_points(msg)
            
            received_msg = ReceivedMessage(
                timestamp=time.time(),
                client_addr=addr,
                sequence=sequence,
                raw_data=data,
                parsed_data=parsed,
                message_type=ProtobufCodec.get_message_type_name(msg.cmdID),
                device_id=device_id,
                points=points
            )
            
            if self.on_message_received:
                self.on_message_received(received_msg)
                
        except Exception as e:
            if self.on_error:
                self.on_error(f"Handle data error: {e}")
    
    def _update_mapping(self, msg: apiMsg, parsed: Dict[str, Any]) -> Optional[str]:
        """Update device/point mapping from received message"""
        with self._lock:
            vdid = msg.vdID
            device_id = self._mapping.vdid_to_device.get(vdid)
            
            if device_id is None:
                device_id = f"device_{vdid}"
                self._mapping.vdid_to_device[vdid] = device_id
                self._mapping.device_to_vdid[device_id] = vdid
            
            for obj in msg.opv:
                oid = obj.oid
                if oid not in self._mapping.oid_to_point:
                    point_name = f"point_{oid}"
                    self._mapping.oid_to_point[oid] = (device_id, point_name)
                    self._mapping.point_to_oid[(device_id, point_name)] = oid
            
            return device_id
    
    def _extract_points(self, msg: apiMsg) -> Dict[str, Any]:
        """Extract point values from message"""
        points = {}
        
        for obj in msg.opv:
            oid = obj.oid
            point_info = self._mapping.oid_to_point.get(oid, (None, f"oid_{oid}"))
            point_name = point_info[1] if point_info else f"oid_{oid}"
            
            for prop in obj.pv:
                value = ProtobufCodec.extract_data_value(prop.v)
                pid = prop.pid
                points[f"{point_name}(pid={pid})"] = value
        
        return points
    
    def send_read_command(
        self,
        client_addr: Tuple[str, int],
        device_id: str,
        point_name: str,
        pid: int = 85,
        uuid: int = 0
    ) -> bool:
        """Send READ_PROPERTY command to XAgent"""
        with self._lock:
            vdid = self._mapping.device_to_vdid.get(device_id)
            if vdid is None:
                vdid = self._mapping.next_vdid
                self._mapping.device_to_vdid[device_id] = vdid
                self._mapping.vdid_to_device[vdid] = device_id
                self._mapping.next_vdid += 1
            
            oid = self._mapping.point_to_oid.get((device_id, point_name))
            if oid is None:
                oid = self._mapping.next_oid
                self._mapping.point_to_oid[(device_id, point_name)] = oid
                self._mapping.oid_to_point[oid] = (device_id, point_name)
                self._mapping.next_oid += 1
        
        msg = ProtobufCodec.create_read_property_message(
            uuid=uuid,
            vd_id=vdid,
            oid=oid,
            pid=pid
        )
        
        return self._send_message(client_addr, msg)
    
    def send_write_command(
        self,
        client_addr: Tuple[str, int],
        device_id: str,
        point_name: str,
        value: Any,
        pid: int = 85,
        uuid: int = 0
    ) -> bool:
        """Send WRITE_PROPERTY command to XAgent"""
        with self._lock:
            vdid = self._mapping.device_to_vdid.get(device_id)
            if vdid is None:
                vdid = self._mapping.next_vdid
                self._mapping.device_to_vdid[device_id] = vdid
                self._mapping.vdid_to_device[vdid] = device_id
                self._mapping.next_vdid += 1
            
            oid = self._mapping.point_to_oid.get((device_id, point_name))
            if oid is None:
                oid = self._mapping.next_oid
                self._mapping.point_to_oid[(device_id, point_name)] = oid
                self._mapping.oid_to_point[oid] = (device_id, point_name)
                self._mapping.next_oid += 1
        
        msg = ProtobufCodec.create_write_property_message(
            uuid=uuid,
            vd_id=vdid,
            oid=oid,
            pid=pid,
            value=value
        )
        
        return self._send_message(client_addr, msg)
    
    def send_raw_protobuf(
        self,
        client_addr: Tuple[str, int],
        msg: apiMsg
    ) -> bool:
        """Send raw protobuf message"""
        return self._send_message(client_addr, msg)
    
    def _send_message(self, client_addr: Tuple[str, int], msg: apiMsg) -> bool:
        """Send protobuf message to client"""
        try:
            payload = ProtobufCodec.encode_message(msg)
            packet = self._protocol_codec.encode(payload)
            self._socket.sendto(packet, client_addr)
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Send error: {e}")
            return False
    
    def get_clients(self) -> List[Tuple[str, int]]:
        """Get list of connected clients"""
        with self._lock:
            current_time = time.time()
            return [
                addr for addr, last_seen in self._clients.items()
                if current_time - last_seen < 60
            ]
    
    def get_mapping(self) -> Dict[str, Any]:
        """Get current mapping state"""
        with self._lock:
            return {
                "vdid_mapping": dict(self._mapping.vdid_to_device),
                "oid_mapping": {
                    oid: f"{device}.{point}"
                    for oid, (device, point) in self._mapping.oid_to_point.items()
                }
            }
    
    def set_mapping(self, vdid_mapping: Dict[int, str], oid_mapping: Dict[int, Tuple[str, str]]):
        """Set mapping from external source"""
        with self._lock:
            for vdid, device_id in vdid_mapping.items():
                self._mapping.vdid_to_device[vdid] = device_id
                self._mapping.device_to_vdid[device_id] = vdid
                if vdid >= self._mapping.next_vdid:
                    self._mapping.next_vdid = vdid + 1
            
            for oid, (device_id, point_name) in oid_mapping.items():
                self._mapping.oid_to_point[oid] = (device_id, point_name)
                self._mapping.point_to_oid[(device_id, point_name)] = oid
                if oid >= self._mapping.next_oid:
                    self._mapping.next_oid = oid + 1
