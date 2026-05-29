"""Device and Point Mapping - Bidirectional mapping with symmetric API"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    import aiosqlite

from .generated import MessageType, errorCode, apiMsg
from .codec import ProtobufCodec

logger = logging.getLogger(__name__)


@dataclass
class EncodedReading:
    """Encoded reading for Protobuf transmission"""
    vdid: int
    points: List[Dict[str, Any]]
    device_status: str = "online"
    
    def to_message(self, uuid: int = 0) -> apiMsg:
        """Convert to Protobuf message"""
        objects = []
        for pt in self.points:
            prop = ProtobufCodec.create_property(pt["pid"], pt["value"])
            obj = ProtobufCodec.create_object(pt["oid"], [prop])
            objects.append(obj)
        
        status = errorCode.NO_ERROR if self.device_status == "online" else errorCode.COMM_NETWORK_DOWN
        
        return ProtobufCodec.create_message(
            uuid=uuid,
            cmd_id=MessageType.UPDATE_PROPERTY,
            vd_id=self.vdid,
            objects=objects,
            status=status
        )


@dataclass
class DecodedMessage:
    """Decoded Protobuf message"""
    device_id: Optional[str]
    command: int
    data: Dict[str, Any]
    uuid: int = 0
    raw_msg: Optional[apiMsg] = None


class DeviceMapper:
    """
    Device and point mapper - Bidirectional mapping with symmetric API
    
    Design principles:
    - Symmetric naming: encode_xxx / decode_xxx
    - Stateless mapping: method parameters contain all necessary info
    - Auto persistence: new mappings auto-save to database
    
    Usage:
        mapper = DeviceMapper(db, service_name="xnc_channel")
        
        # Point mapping
        oid = mapper.encode_point("temperature", "device_1")
        point_info = mapper.decode_point(oid)  # {"point_name": "temperature", "device_id": "device_1"}
        
        # Device mapping
        vdid = mapper.encode_device("device_1")
        device_id = mapper.decode_device(vdid)
        
        # Batch mapping (efficient)
        encoded = mapper.encode_reading(reading)
        decoded = mapper.decode_message(msg)
    """
    
    PID_POINT_VALUE = 85
    PID_POINT_ERROR = 103
    
    def __init__(
        self,
        mapping_config: Optional[Dict[str, Any]] = None,
        db: Optional["aiosqlite.Connection"] = None,
        service_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize device mapper
        
        Args:
            mapping_config: Mapping configuration (recommended, dependency injection)
            db: Database connection for persistence
            service_name: Service name for database queries
            config: Legacy config dict (backward compatibility, will be deprecated)
        """
        self._db = db
        self._service_name = service_name
        
        self._point_to_oid: Dict[str, int] = {}
        self._oid_to_point: Dict[int, str] = {}
        self._point_to_device: Dict[str, str] = {}
        
        self._device_to_vdid: Dict[str, int] = {}
        self._vdid_to_device: Dict[int, str] = {}
        
        self._next_oid = 1
        self._next_vdid = 1
        
        self._pid_point_value = self.PID_POINT_VALUE
        self._pid_point_error = self.PID_POINT_ERROR
        
        if mapping_config:
            self._apply_mapping_config(mapping_config)
        elif config:
            logger.warning(
                "Using legacy config parameter is deprecated, "
                "please pass mapping_config directly"
            )
            self._load_from_legacy_config(config)
        
        if db and service_name:
            asyncio.create_task(self._load_from_db())
    
    # ===== Point Mapping (Symmetric API) =====
    
    def encode_point(self, point_name: str, device_id: Optional[str] = None) -> int:
        """Encode point name to OID (upload direction)
        
        Args:
            point_name: Internal point name
            device_id: Device ID for namespaced mapping
            
        Returns:
            OID (Object ID)
        """
        key = f"{device_id}.{point_name}" if device_id else point_name
        
        if key not in self._point_to_oid:
            oid = self._next_oid
            self._point_to_oid[key] = oid
            self._oid_to_point[oid] = key
            self._next_oid += 1
            
            if device_id:
                self._point_to_device[key] = device_id
            
            self._persist_mapping("point", key, oid, device_id)
            logger.debug(f"Assigned new OID {oid} for point {key}")
        
        return self._point_to_oid[key]
    
    def decode_point(self, oid: int) -> Dict[str, Optional[str]]:
        """Decode OID to point info (download direction)
        
        Args:
            oid: Object ID
            
        Returns:
            {"point_name": str, "device_id": str or None}
        """
        full_name = self._oid_to_point.get(oid)
        if not full_name:
            return {"point_name": None, "device_id": None}
        
        if "." in full_name:
            device_id, point_name = full_name.split(".", 1)
            return {"point_name": point_name, "device_id": device_id}
        
        return {"point_name": full_name, "device_id": None}
    
    # ===== Device Mapping (Symmetric API) =====
    
    def encode_device(self, device_id: str) -> int:
        """Encode device ID to vdID (upload direction)
        
        Args:
            device_id: Internal device ID
            
        Returns:
            vdID (Virtual Device ID)
        """
        if device_id not in self._device_to_vdid:
            vdid = self._next_vdid
            self._device_to_vdid[device_id] = vdid
            self._vdid_to_device[vdid] = device_id
            self._next_vdid += 1
            
            self._persist_mapping("device", device_id, vdid)
            logger.debug(f"Assigned new vdID {vdid} for device {device_id}")
        
        return self._device_to_vdid[device_id]
    
    def decode_device(self, vdid: int) -> Optional[str]:
        """Decode vdID to device ID (download direction)
        
        Args:
            vdid: Virtual Device ID
            
        Returns:
            Device ID or None
        """
        return self._vdid_to_device.get(vdid)
    
    # ===== Batch Mapping (Efficient) =====
    
    def encode_reading(self, reading) -> EncodedReading:
        """Encode entire Reading object (single call for all mappings)
        
        Args:
            reading: Reading object with standard_points
            
        Returns:
            EncodedReading ready for Protobuf serialization
        """
        device_id = reading.asset
        vdid = self.encode_device(device_id)
        device_offline = reading.device_status and reading.device_status != "online"
        
        points = []
        
        if hasattr(reading, 'standard_points') and reading.standard_points:
            for sp in reading.standard_points:
                point_name = sp.get("point_name", "")
                value = sp.get("value")
                quality = sp.get("quality", "good")
                metadata = sp.get("metadata", {})
                error_code = metadata.get("error_code", 10)
                
                oid = self.encode_point(point_name, device_id)
                
                if device_offline or quality != "good":
                    pid = self._pid_point_error
                    pid_value = error_code
                else:
                    pid = self._pid_point_value
                    pid_value = value
                
                points.append({
                    "oid": oid,
                    "pid": pid,
                    "value": pid_value
                })
        else:
            for key, value in reading.data.items():
                oid = self.encode_point(key, device_id)
                pid = self._pid_point_error if device_offline else self._pid_point_value
                points.append({
                    "oid": oid,
                    "pid": pid,
                    "value": 10 if device_offline else value
                })
        
        return EncodedReading(
            vdid=vdid,
            points=points,
            device_status=reading.device_status or "online"
        )
    
    def decode_message(self, msg: apiMsg) -> DecodedMessage:
        """Decode entire Protobuf message
        
        Args:
            msg: apiMsg Protobuf message
            
        Returns:
            DecodedMessage with device_id and data
        """
        device_id = self.decode_device(msg.vdID)
        data = {}
        
        for obj in msg.opv:
            point_info = self.decode_point(obj.oid)
            point_name = point_info.get("point_name")
            
            for prop in obj.pv:
                value = ProtobufCodec.extract_data_value(prop.v)
                if point_name:
                    data[point_name] = value
                else:
                    data[f"oid_{obj.oid}"] = value
        
        return DecodedMessage(
            device_id=device_id,
            command=msg.cmdID,
            data=data,
            uuid=msg.uuid,
            raw_msg=msg
        )
    
    # ===== PID Mapping =====
    
    def get_pid_by_type(self, pid_type: str) -> int:
        """Get PID by type
        
        Args:
            pid_type: "point_value" or "point_error"
            
        Returns:
            PID value
        """
        if pid_type == "point_error":
            return self._pid_point_error
        return self._pid_point_value
    
    # ===== Persistence =====
    
    def _persist_mapping(
        self,
        mapping_type: str,
        internal_name: str,
        external_id: int,
        device_id: Optional[str] = None
    ) -> None:
        """Persist mapping to database"""
        if not self._db or not self._service_name:
            return
        
        async def _save():
            try:
                await self._db.execute(
                    """
                    INSERT OR REPLACE INTO mapping_registry
                    (service_name, mapping_type, internal_name, external_id, device_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (self._service_name, mapping_type, internal_name, str(external_id), device_id, time.time())
                )
                await self._db.commit()
            except Exception as e:
                logger.debug(f"Failed to persist mapping: {e}")
        
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(_save())
    
    async def _load_from_db(self) -> None:
        """Load mappings from database"""
        if not self._db or not self._service_name:
            return
        
        try:
            async with self._db.execute(
                """
                SELECT mapping_type, internal_name, external_id, device_id
                FROM mapping_registry
                WHERE service_name = ?
                """,
                (self._service_name,)
            ) as cursor:
                async for row in cursor:
                    mapping_type = row[0]
                    internal_name = row[1]
                    external_id = int(row[2]) if row[2] else None
                    device_id = row[3]
                    
                    if mapping_type == "point" and external_id:
                        self._point_to_oid[internal_name] = external_id
                        self._oid_to_point[external_id] = internal_name
                        if external_id >= self._next_oid:
                            self._next_oid = external_id + 1
                        if device_id:
                            self._point_to_device[internal_name] = device_id
                    
                    elif mapping_type == "device" and external_id:
                        self._device_to_vdid[internal_name] = external_id
                        self._vdid_to_device[external_id] = internal_name
                        if external_id >= self._next_vdid:
                            self._next_vdid = external_id + 1
            
            logger.info(
                f"Loaded {len(self._point_to_oid)} point mappings, "
                f"{len(self._device_to_vdid)} device mappings from database"
            )
            
        except Exception as e:
            logger.warning(f"Failed to load mappings from database: {e}")
    
    def _apply_mapping_config(self, mapping_config: Dict[str, Any]) -> None:
        """
        Apply mapping configuration
        
        Args:
            mapping_config: Mapping configuration dict with vdid_mapping, oid_mapping, etc.
        """
        if not mapping_config:
            logger.info("Empty mapping config provided, auto-mapping will be used")
            return
        
        pid_config = mapping_config.get("pid", {})
        if pid_config:
            self._pid_point_value = pid_config.get("point_value", self.PID_POINT_VALUE)
            self._pid_point_error = pid_config.get("point_error", self.PID_POINT_ERROR)
        
        # Support both vdid_mapping and device_mapping (backward compatibility)
        vdid_mapping = mapping_config.get("vdid_mapping") or mapping_config.get("device_mapping", {})
        for device_id, vdid in vdid_mapping.items():
            if not isinstance(vdid, int):
                logger.warning(f"Invalid VDID type for {device_id}: {type(vdid)}, expected int")
                continue
            
            self._device_to_vdid[device_id] = vdid
            self._vdid_to_device[vdid] = device_id
            if vdid >= self._next_vdid:
                self._next_vdid = vdid + 1
        
        oid_mapping = mapping_config.get("oid_mapping", {})
        for key, oid in oid_mapping.items():
            if not isinstance(oid, int):
                logger.warning(f"Invalid OID type for {key}: {type(oid)}, expected int")
                continue
            
            if key not in self._point_to_oid:
                self._point_to_oid[key] = oid
                self._oid_to_point[oid] = key
                if oid >= self._next_oid:
                    self._next_oid = oid + 1
                
                if "." in key:
                    parts = key.split(".", 1)
                    if len(parts) == 2:
                        self._point_to_device[key] = parts[0]
        
        logger.info(
            f"Applied mapping config: {len(self._device_to_vdid)} devices, "
            f"{len(self._point_to_oid)} points"
        )
    
    def _load_from_legacy_config(self, config: Dict[str, Any]) -> None:
        """
        Load mapping config from legacy config structure
        
        This method provides backward compatibility for old config format.
        It extracts mapping_config from multiple possible locations.
        
        Args:
            config: Legacy config dict
        """
        mapping_config = config.get("mapping_config", {}) or {}
        
        if not mapping_config and isinstance(config.get("xnc"), dict):
            mapping_config = config["xnc"].get("mapping_config", {}) or {}
        
        if not mapping_config and isinstance(config.get("adapter_config"), dict):
            mapping_config = config["adapter_config"].get("mapping_config", {}) or {}
        
        mapping_file = config.get("device_mapping_file") or mapping_config.get("device_mapping_file")
        if mapping_file and os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = yaml.safe_load(f) or {}
                
                if "points" in mapping_data:
                    for point_name, point_info in mapping_data["points"].items():
                        if isinstance(point_info, dict):
                            oid = point_info.get("oid")
                            if oid is not None:
                                self._point_to_oid[point_name] = oid
                                self._oid_to_point[oid] = point_name
                                if oid >= self._next_oid:
                                    self._next_oid = oid + 1
                
                logger.info(f"Loaded mapping config from {mapping_file}")
                
            except Exception as e:
                logger.error(f"Failed to load mapping config from file: {e}")
        
        vdid_mapping = config.get("vdid_mapping", {})
        if not vdid_mapping and isinstance(config.get("xnc"), dict):
            vdid_mapping = config["xnc"].get("vdid_mapping", {})
        if not vdid_mapping and isinstance(config.get("adapter_config"), dict):
            vdid_mapping = config["adapter_config"].get("mapping_config", {}).get("vdid_mapping", {})
        if not vdid_mapping:
            vdid_mapping = mapping_config.get("vdid_mapping", {}) or mapping_config.get("device_mapping", {})
        
        for device_id, vdid in vdid_mapping.items():
            if not isinstance(vdid, int):
                continue
            
            self._device_to_vdid[device_id] = vdid
            self._vdid_to_device[vdid] = device_id
            if vdid >= self._next_vdid:
                self._next_vdid = vdid + 1
        
        oid_mapping = config.get("oid_mapping", {})
        if not oid_mapping and isinstance(config.get("xnc"), dict):
            oid_mapping = config["xnc"].get("oid_mapping", {})
        if not oid_mapping and isinstance(config.get("adapter_config"), dict):
            oid_mapping = config["adapter_config"].get("mapping_config", {}).get("oid_mapping", {})
        if not oid_mapping:
            oid_mapping = mapping_config.get("oid_mapping", {})
        
        for key, oid in oid_mapping.items():
            if not isinstance(oid, int):
                continue
            
            if key not in self._point_to_oid:
                self._point_to_oid[key] = oid
                self._oid_to_point[oid] = key
                if oid >= self._next_oid:
                    self._next_oid = oid + 1
                
                if "." in key:
                    parts = key.split(".", 1)
                    if len(parts) == 2:
                        self._point_to_device[key] = parts[0]
        
        logger.info(
            f"Loaded from legacy config: {len(self._device_to_vdid)} devices, "
            f"{len(self._point_to_oid)} points"
        )
    
    # ===== Backward Compatibility (Legacy API) =====
    
    def get_vd_id(self, device_id: str) -> int:
        """[Legacy] Use encode_device() instead"""
        return self.encode_device(device_id)
    
    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        """[Legacy] Use decode_device() instead"""
        return self.decode_device(vdid)
    
    def get_oid(self, point_name: str, device_id: Optional[str] = None) -> int:
        """[Legacy] Use encode_point() instead"""
        return self.encode_point(point_name, device_id)
    
    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        """[Legacy] Use decode_point() instead"""
        result = self.decode_point(oid)
        return result.get("point_name")
    
    def get_point_info_by_oid(self, oid: int) -> Dict[str, Optional[str]]:
        """[Legacy] Use decode_point() instead"""
        return self.decode_point(oid)
    
    def register_point_device(self, point_name: str, device_id: str) -> None:
        """[Legacy] No longer needed with new API"""
        self._point_to_device[point_name] = device_id
    
    # ===== Utility Methods =====
    
    def export_mapping(self) -> Dict[str, Any]:
        """Export all mappings"""
        return {
            "vdid_mapping": dict(self._device_to_vdid),
            "oid_mapping": dict(self._point_to_oid),
            "points": {
                point_name: {"oid": oid}
                for point_name, oid in self._point_to_oid.items()
            }
        }
    
    def clear_mapping(self) -> None:
        """Clear all mappings"""
        self._point_to_oid.clear()
        self._oid_to_point.clear()
        self._device_to_vdid.clear()
        self._vdid_to_device.clear()
        self._point_to_device.clear()
        self._next_oid = 1
        self._next_vdid = 1
        logger.info("Cleared all mappings")
