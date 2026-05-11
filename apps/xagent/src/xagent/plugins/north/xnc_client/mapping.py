"""Device and Point Mapping - Maps device IDs and points to Protobuf IDs"""

import logging
import os
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class DeviceMapper:
    """Device and point mapping manager
    
    Maps:
    - point_name (点位名称) -> oid (Protobuf object ID)
    - point_name (点位名称) -> pid (Protobuf property ID)
    - device_id (设备ID) -> vdID (Protobuf virtual device ID)
    
    Supports namespace for point mapping:
    - Format 1: "device_id.point_name" (recommended, supports duplicate point names across devices)
    - Format 2: "point_name" (backward compatible, for unique point names)
    
    Config format:
        pid:
            point_value: 85       # 点位正常值上报的 pid
            point_error: 103      # 点位采集失败时的 pid
        
        vdid_mapping:
            "knx_device": 1       # 设备ID到vdID的映射
        
        oid_mapping:
            # Simple format (backward compatible)
            "living_room_light": 2001
            # Namespace format (recommended)
            "modbus_device_1.temperature": 1001
            "modbus_device_2.temperature": 1002
    """
    
    PID_POINT_VALUE = 85
    PID_POINT_ERROR = 103
    
    DEVICE_STATUS_ONLINE = 2
    DEVICE_STATUS_OFFLINE = 3
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        pid_config = self.config.get("pid", {})
        self._pid_point_value = pid_config.get("point_value", self.PID_POINT_VALUE)
        self._pid_point_error = pid_config.get("point_error", self.PID_POINT_ERROR)
        
        self._point_to_oid: Dict[str, int] = {}
        self._point_to_pid: Dict[str, int] = {}
        self._point_to_device: Dict[str, str] = {}
        
        self._device_to_vdid: Dict[str, int] = {}
        
        self._reverse_oid_mapping: Dict[int, str] = {}
        self._reverse_pid_mapping: Dict[int, str] = {}
        self._reverse_vdid_mapping: Dict[int, str] = {}
        self._oid_to_device: Dict[int, str] = {}
        
        self._next_oid = 1
        self._next_pid = 1
        self._next_vdid = 1
        
        self._load_mapping_config()
    
    def _load_mapping_config(self) -> None:
        mapping_file = self.config.get("device_mapping_file")
        if mapping_file and os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = yaml.safe_load(f) or {}
                
                if "points" in mapping_data:
                    for point_name, point_info in mapping_data["points"].items():
                        if isinstance(point_info, dict):
                            oid = point_info.get("oid")
                            pid = point_info.get("pid")
                            if oid is not None:
                                self._point_to_oid[point_name] = oid
                                self._reverse_oid_mapping[oid] = point_name
                                if oid >= self._next_oid:
                                    self._next_oid = oid + 1
                            if pid is not None:
                                self._point_to_pid[point_name] = pid
                                self._reverse_pid_mapping[pid] = point_name
                                if pid >= self._next_pid:
                                    self._next_pid = pid + 1
                
                logger.info(f"Loaded mapping config from {mapping_file}")
                
            except Exception as e:
                logger.error(f"Failed to load mapping config: {e}")
        
        vdid_mapping = self.config.get("vdid_mapping", {})
        for device_id, vdid in vdid_mapping.items():
            self._device_to_vdid[device_id] = vdid
            self._reverse_vdid_mapping[vdid] = device_id
            if vdid >= self._next_vdid:
                self._next_vdid = vdid + 1
        
        oid_mapping = self.config.get("oid_mapping", {})
        
        if oid_mapping:
            if "point" in oid_mapping and isinstance(oid_mapping["point"], dict):
                point_oid_config = oid_mapping["point"]
                for point_name, oid in point_oid_config.items():
                    if point_name not in self._point_to_oid:
                        self._point_to_oid[point_name] = oid
                        self._reverse_oid_mapping[oid] = point_name
                        if oid >= self._next_oid:
                            self._next_oid = oid + 1
                logger.info(f"Loaded {len(point_oid_config)} point OID mappings (legacy format)")
            else:
                for key, oid in oid_mapping.items():
                    if not isinstance(oid, int):
                        continue
                    
                    if key not in self._point_to_oid:
                        self._point_to_oid[key] = oid
                        self._reverse_oid_mapping[oid] = key
                        if oid >= self._next_oid:
                            self._next_oid = oid + 1
                        
                        if "." in key:
                            parts = key.split(".", 1)
                            if len(parts) == 2:
                                device_id, point_name = parts
                                self._point_to_device[key] = device_id
                
                logger.info(f"Loaded {len(oid_mapping)} point OID mappings (namespace format)")
    
    def get_vd_id(self, device_id: str) -> int:
        """获取设备ID对应的vdID，如果不存在则自动分配"""
        if device_id not in self._device_to_vdid:
            vdid = self._next_vdid
            self._device_to_vdid[device_id] = vdid
            self._reverse_vdid_mapping[vdid] = device_id
            self._next_vdid += 1
            logger.debug(f"Assigned new vdID {vdid} for device {device_id}")
        return self._device_to_vdid[device_id]
    
    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        """根据vdID获取设备ID"""
        return self._reverse_vdid_mapping.get(vdid)
    
    def get_oid(self, point_name: str, device_id: Optional[str] = None) -> int:
        """获取点位对应的oid，支持命名空间
        
        Args:
            point_name: 点位名称
            device_id: 设备ID（可选），用于支持命名空间
        
        Returns:
            对应的oid值
            
        查找优先级：
        1. 如果提供了device_id，优先查找 "device_id.point_name"
        2. 查找 "point_name" (向后兼容)
        3. 自动分配新的oid（使用命名空间格式）
        """
        namespaced_key = f"{device_id}.{point_name}" if device_id else None
        
        if namespaced_key and namespaced_key in self._point_to_oid:
            return self._point_to_oid[namespaced_key]
        
        if point_name in self._point_to_oid:
            return self._point_to_oid[point_name]
        
        oid = self._next_oid
        final_key = namespaced_key if device_id else point_name
        
        self._point_to_oid[final_key] = oid
        self._reverse_oid_mapping[oid] = final_key
        self._next_oid += 1
        
        if device_id:
            self._point_to_device[final_key] = device_id
        
        logger.debug(f"Assigned new oid {oid} for point {final_key}")
        return oid
    
    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        """根据oid获取点位名称（纯点位名称，不带命名空间）
        
        Args:
            oid: 对象ID
            
        Returns:
            纯点位名称（不带设备前缀），如果找不到返回None
        """
        full_name = self._reverse_oid_mapping.get(oid)
        if not full_name:
            return None
        
        if "." in full_name:
            parts = full_name.split(".", 1)
            if len(parts) == 2:
                return parts[1]
        
        return full_name
    
    def get_point_full_name_by_oid(self, oid: int) -> Optional[str]:
        """根据oid获取完整点位名称（带命名空间）
        
        Args:
            oid: 对象ID
            
        Returns:
            完整点位名称（可能是 "device_id.point_name" 或 "point_name"）
        """
        return self._reverse_oid_mapping.get(oid)
    
    def get_point_info_by_oid(self, oid: int) -> Dict[str, Optional[str]]:
        """根据oid获取点位完整信息
        
        Args:
            oid: 对象ID
            
        Returns:
            包含 point_name 和 device_id 的字典
        """
        full_name = self._reverse_oid_mapping.get(oid)
        if not full_name:
            return {"point_name": None, "device_id": None}
        
        if "." in full_name:
            parts = full_name.split(".", 1)
            if len(parts) == 2:
                return {
                    "point_name": parts[1],
                    "device_id": parts[0]
                }
        
        device_id = self._point_to_device.get(full_name)
        return {
            "point_name": full_name,
            "device_id": device_id
        }
    
    def get_pid(self, point_name: str) -> int:
        if point_name not in self._point_to_pid:
            self._point_to_pid[point_name] = self._pid_point_value
            if self._pid_point_value not in self._reverse_pid_mapping:
                self._reverse_pid_mapping[self._pid_point_value] = point_name
            logger.debug(f"Using default pid {self._pid_point_value} for point {point_name}")
        
        return self._point_to_pid[point_name]
    
    def get_pid_by_type(self, pid_type: str) -> int:
        """根据类型获取PID
        
        Args:
            pid_type: "point_value" 或 "point_error"
        
        Returns:
            对应的PID值
        """
        if pid_type == "point_error":
            return self._pid_point_error
        return self._pid_point_value
    
    def get_point_name_by_pid(self, pid: int) -> Optional[str]:
        return self._reverse_pid_mapping.get(pid)
    
    def get_point_mapping(self, point_name: str) -> Dict[str, int]:
        return {
            "oid": self.get_oid(point_name),
            "pid": self.get_pid(point_name)
        }
    
    def register_device(self, device_id: str) -> int:
        """注册设备并返回vdID"""
        return self.get_vd_id(device_id)
    
    def register_point_device(self, point_name: str, device_id: str) -> None:
        self._point_to_device[point_name] = device_id
    
    def get_device_by_oid(self, oid: int) -> Optional[str]:
        point_name = self._reverse_oid_mapping.get(oid)
        if point_name:
            return self._point_to_device.get(point_name)
        return self._oid_to_device.get(oid)
    
    def register_point(
        self,
        point_name: str,
        oid: Optional[int] = None,
        pid: Optional[int] = None
    ) -> Dict[str, int]:
        result = {}
        
        if oid is not None:
            if oid in self._reverse_oid_mapping:
                existing_point = self._reverse_oid_mapping[oid]
                if existing_point != point_name:
                    logger.warning(
                        f"oid {oid} already mapped to point {existing_point}, "
                        f"remapping to {point_name}"
                    )
            self._point_to_oid[point_name] = oid
            self._reverse_oid_mapping[oid] = point_name
            if oid >= self._next_oid:
                self._next_oid = oid + 1
            result["oid"] = oid
        else:
            result["oid"] = self.get_oid(point_name)
        
        if pid is not None:
            if pid in self._reverse_pid_mapping:
                existing_point = self._reverse_pid_mapping[pid]
                if existing_point != point_name:
                    logger.warning(
                        f"pid {pid} already mapped to point {existing_point}, "
                        f"remapping to {point_name}"
                    )
            self._point_to_pid[point_name] = pid
            self._reverse_pid_mapping[pid] = point_name
            if pid >= self._next_pid:
                self._next_pid = pid + 1
            result["pid"] = pid
        else:
            result["pid"] = self.get_pid(point_name)
        
        return result
    
    def export_mapping(self) -> Dict[str, Any]:
        return {
            "vdid_mapping": dict(self._device_to_vdid),
            "points": {
                point_name: {
                    "oid": self._point_to_oid.get(point_name),
                    "pid": self._point_to_pid.get(point_name)
                }
                for point_name in set(self._point_to_oid.keys()) | set(self._point_to_pid.keys())
            }
        }
    
    def save_mapping(self, file_path: str) -> None:
        mapping_data = self.export_mapping()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(mapping_data, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"Saved mapping config to {file_path}")
    
    def clear_mapping(self) -> None:
        self._point_to_oid.clear()
        self._point_to_pid.clear()
        self._device_to_vdid.clear()
        self._point_to_device.clear()
        self._reverse_oid_mapping.clear()
        self._reverse_pid_mapping.clear()
        self._reverse_vdid_mapping.clear()
        self._oid_to_device.clear()
        self._next_oid = 1
        self._next_pid = 1
        self._next_vdid = 1
        logger.info("Cleared all mappings")
