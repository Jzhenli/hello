"""XNC Adapters - JSON and Protobuf format adapters using unified mapping"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from xagent.xcore.storage.interface import Reading

from .generated import MessageType, apiMsg
from .codec import ProtobufCodec
from .mapping import DeviceMapper, EncodedReading, DecodedMessage

logger = logging.getLogger(__name__)


class XNCJsonAdapter:
    """
    XNC JSON Data Adapter - Conforms to DataAdapter protocol
    
    Adapts Reading data to XNC JSON format.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
    
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """Adapt upload data"""
        if not readings:
            return None
        
        if len(readings) == 1:
            return self._adapt_single_reading(readings[0])
        else:
            return self._adapt_batch_readings(readings)
    
    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt command data"""
        return {
            "asset": command_data.get("asset"),
            "data": command_data.get("data", {}),
            "timestamp": context.get("timestamp"),
        }
    
    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response data"""
        if isinstance(response, dict):
            return response
        
        if isinstance(response, bytes):
            try:
                return json.loads(response.decode())
            except json.JSONDecodeError:
                return {"raw": response.decode()}
        
        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"raw": response}
        
        return {"raw": str(response)}
    
    def _adapt_single_reading(self, reading: Reading) -> Dict[str, Any]:
        """Adapt single Reading"""
        points = self._extract_points(reading)
        
        payload = {
            "device_id": reading.asset,
            "timestamp": self._format_timestamp(reading.timestamp),
            "points": points
        }
        
        if self._include_metadata and reading.tags:
            payload["tags"] = reading.tags
        
        return payload
    
    def _adapt_batch_readings(self, readings: List[Reading]) -> Dict[str, Any]:
        """Adapt batch Readings"""
        grouped = {}
        for reading in readings:
            if reading.asset not in grouped:
                grouped[reading.asset] = {
                    "device_id": reading.asset,
                    "timestamp": self._format_timestamp(reading.timestamp),
                    "points": []
                }
            
            points = self._extract_points(reading)
            grouped[reading.asset]["points"].extend(points)
        
        return {
            "count": len(readings),
            "devices": list(grouped.values()),
            "timestamp": self._format_timestamp(readings[0].timestamp) if readings else None
        }
    
    def _extract_points(self, reading: Reading) -> List[Dict[str, Any]]:
        """Extract point data"""
        points = []
        
        if reading.standard_points:
            for sp in reading.standard_points:
                point = {
                    "point_name": sp.get("point_name", ""),
                    "value": sp.get("value"),
                    "data_type": sp.get("data_type", "unknown"),
                }
                if sp.get("unit"):
                    point["unit"] = sp["unit"]
                if self._include_quality:
                    point["quality"] = sp.get("quality", "good")
                points.append(point)
        else:
            for key, value in reading.data.items():
                point = {
                    "point_name": key,
                    "value": value,
                    "data_type": self._infer_data_type(value),
                }
                if self._include_quality:
                    point["quality"] = "good"
                points.append(point)
        
        return points
    
    def _infer_data_type(self, value: Any) -> str:
        """Infer data type"""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, bytes):
            return "bytes"
        elif isinstance(value, (dict, list)):
            return "json"
        else:
            return "unknown"
    
    def _format_timestamp(self, timestamp: float) -> Any:
        """Format timestamp"""
        if self._timestamp_format == "iso":
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).isoformat()
        return timestamp
    
    def to_json(self, payload: Any) -> str:
        """Convert to JSON string"""
        return json.dumps(payload, ensure_ascii=False)


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
