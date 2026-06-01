"""XNC Protobuf Adapter - Protobuf format adapter using unified mapping"""

import logging
from typing import Any, Dict, List, Optional, Union

from xagent.xcore.storage.interface import Reading

from .generated import MessageType, apiMsg
from .codec import ProtobufCodec
from .mapping import DeviceMapper

logger = logging.getLogger(__name__)


class XNCProtobufAdapter:
    """
    XNC Protobuf Data Adapter - Conforms to DataAdapter protocol
    
    Uses DeviceMapper for bidirectional mapping between:
    - Internal format: point_name, device_id
    - External format: oid, vdID
    
    Design principle:
    - DeviceMapper: responsible for mapping + encoding (encode_reading, decode_message)
    - XNCProtobufAdapter: responsible for data format conversion (adapt_upload, parse_response)
    
    Usage:
        # Upload direction
        messages = adapter.adapt_upload(readings, context)
        
        # Download direction
        parsed = adapter.parse_response(msg, context)
    """
    
    def __init__(
        self,
        mapper: Optional[DeviceMapper] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self._mapper = mapper or DeviceMapper(config=config)
        self.config = config or {}
        self._uuid = self.config.get("uuid", 0)
    
    @property
    def mapper(self) -> DeviceMapper:
        """Get the underlying mapper"""
        return self._mapper
    
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Union[apiMsg, List[apiMsg], None]:
        """Adapt upload data using DeviceMapper.encode_reading()
        
        This method delegates all mapping logic to DeviceMapper.encode_reading()
        and only handles the conversion to Protobuf messages.
        """
        if not readings:
            return None
        
        if len(readings) == 1:
            encoded = self._mapper.encode_reading(readings[0])
            return encoded.to_message(self._uuid)
        
        return self._adapt_batch_readings(readings)
    
    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> apiMsg:
        """Adapt command data"""
        device_id = command_data.get("asset")
        data = command_data.get("data", {})
        
        vdid = self._mapper.encode_device(device_id)
        
        objects = []
        for point_name, value in data.items():
            oid = self._mapper.encode_point(point_name, device_id)
            pid = self._mapper.get_pid_by_type("point_value")
            
            prop = ProtobufCodec.create_property(pid, value)
            obj = ProtobufCodec.create_object(oid, [prop])
            objects.append(obj)
        
        return ProtobufCodec.create_message(
            uuid=self._uuid,
            cmd_id=MessageType.WRITE_PROPERTY,
            vd_id=vdid,
            objects=objects
        )
    
    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response using DeviceMapper.decode_message()
        
        This method delegates all decoding logic to DeviceMapper.decode_message()
        and only handles the conversion to dictionary format.
        """
        if not isinstance(response, apiMsg):
            return {"raw": str(response)}
        
        decoded = self._mapper.decode_message(response)
        
        return {
            "uuid": decoded.uuid,
            "cmdID": decoded.command,
            "vdID": decoded.raw_msg.vdID if decoded.raw_msg else None,
            "status": decoded.raw_msg.status if decoded.raw_msg else None,
            "device_id": decoded.device_id,
            "data": decoded.data
        }
    
    def _adapt_batch_readings(self, readings: List[Reading]) -> List[apiMsg]:
        """Adapt batch Readings - reuses DeviceMapper.encode_reading()"""
        messages = []
        
        for reading in readings:
            encoded = self._mapper.encode_reading(reading)
            messages.append(encoded.to_message(self._uuid))
        
        return messages
    
    def adapt_read_request(self, device_id: str, point_names: List[str]) -> apiMsg:
        """Create read request message"""
        vdid = self._mapper.encode_device(device_id)
        
        objects = []
        for point_name in point_names:
            oid = self._mapper.encode_point(point_name, device_id)
            pid = self._mapper.get_pid_by_type("point_value")
            
            prop = ProtobufCodec.create_property(pid, None)
            obj = ProtobufCodec.create_object(oid, [prop])
            objects.append(obj)
        
        return ProtobufCodec.create_message(
            uuid=self._uuid,
            cmd_id=MessageType.READ_PROPERTY,
            vd_id=vdid,
            objects=objects
        )
    
    def to_bytes(self, msg: apiMsg) -> bytes:
        """Convert Protobuf message to bytes"""
        return ProtobufCodec.encode_message(msg)
    
    def from_bytes(self, data: bytes) -> apiMsg:
        """Parse bytes to Protobuf message"""
        return ProtobufCodec.decode_message(data)
