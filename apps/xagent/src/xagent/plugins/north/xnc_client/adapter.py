"""XNC Adapters - JSON and Protobuf format adapters"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from xagent.xcore.storage.interface import Reading

from .generated import MessageType, errorCode, apiMsg
from .codec import ProtobufCodec
from .mapping import DeviceMapper

logger = logging.getLogger(__name__)


class XNCJsonAdapter:
    """
    XNC JSON 数据适配器 - 符合 DataAdapter 协议
    
    将 Reading 数据适配为 XNC JSON 格式。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
    
    def adapt_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any]
    ) -> Any:
        """
        适配上传数据
        
        Args:
            readings: Reading 对象列表
            context: 上下文信息
        
        Returns:
            适配后的数据
        """
        if not readings:
            return None
        
        if len(readings) == 1:
            return self._adapt_single_reading(readings[0])
        else:
            return self._adapt_batch_readings(readings)
    
    def adapt_command(
        self,
        command_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        适配下行命令
        
        Args:
            command_data: 命令数据
            context: 上下文信息
        
        Returns:
            适配后的命令数据
        """
        return {
            "asset": command_data.get("asset"),
            "data": command_data.get("data", {}),
            "timestamp": context.get("timestamp"),
        }
    
    def parse_response(
        self,
        response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析响应数据
        
        Args:
            response: 原始响应
            context: 上下文信息
        
        Returns:
            解析后的数据字典
        """
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
        """适配单个 Reading"""
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
        """适配批量 Reading"""
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
        """提取点位数据"""
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
        """推断数据类型"""
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
        """格式化时间戳"""
        if self._timestamp_format == "iso":
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).isoformat()
        return timestamp
    
    def to_json(self, payload: Any) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(payload, ensure_ascii=False)


class XNCProtobufAdapter:
    """
    XNC Protobuf 数据适配器 - 符合 DataAdapter 协议
    
    将 Reading 数据适配为 XNC Protobuf 格式。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._uuid = self.config.get("uuid", 0)
        self._batch_size = self.config.get("batch_size", 50)
        self._mapper = DeviceMapper(self.config.get("mapping_config", {}))
    
    def adapt_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any]
    ) -> Union[apiMsg, List[apiMsg], None]:
        """
        适配上传数据
        
        Args:
            readings: Reading 对象列表
            context: 上下文信息
        
        Returns:
            适配后的 Protobuf 消息
        """
        if not readings:
            return None
        
        if len(readings) == 1:
            return self._adapt_single_reading(readings[0])
        else:
            return self._adapt_batch_readings(readings)
    
    def adapt_command(
        self,
        command_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> apiMsg:
        """
        适配下行命令
        
        Args:
            command_data: 命令数据
            context: 上下文信息
        
        Returns:
            适配后的 Protobuf 消息
        """
        device_id = command_data.get("asset")
        data = command_data.get("data", {})
        
        vdid = self._mapper.get_vd_id(device_id)
        
        objects = []
        for point_name, value in data.items():
            oid = self._mapper.get_oid(point_name, device_id)
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
    
    def parse_response(
        self,
        response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析响应数据
        
        Args:
            response: 原始响应（apiMsg）
            context: 上下文信息
        
        Returns:
            解析后的数据字典
        """
        if not isinstance(response, apiMsg):
            return {"raw": str(response)}
        
        msg = response
        device_id = self._mapper.get_device_id_by_vdid(msg.vdID)
        
        result = {
            "uuid": msg.uuid,
            "cmdID": msg.cmdID,
            "vdID": msg.vdID,
            "status": msg.status,
            "device_id": device_id,
            "data": {}
        }
        
        for obj in msg.opv:
            point_name = self._mapper.get_point_name_by_oid(obj.oid)
            
            for prop in obj.pv:
                value = ProtobufCodec.extract_data_value(prop.v)
                if point_name:
                    result["data"][point_name] = value
                else:
                    result["data"][f"oid_{obj.oid}"] = value
        
        return result
    
    def _adapt_single_reading(self, reading: Reading) -> apiMsg:
        """适配单个 Reading"""
        logger.debug(f"_adapt_single_reading: asset={reading.asset}, device_status={reading.device_status}")
        
        device_offline = reading.device_status and reading.device_status != "online"
        
        objects = []
        
        if reading.standard_points:
            for sp in reading.standard_points:
                point_name = sp.get("point_name", "")
                value = sp.get("value")
                quality = sp.get("quality", "good")
                metadata = sp.get("metadata", {})
                error_code = metadata.get("error_code", 10)
                
                oid = self._mapper.get_oid(point_name, reading.asset)
                self._mapper.register_point_device(point_name, reading.asset)
                
                if device_offline or quality != "good":
                    pid = self._mapper.get_pid_by_type("point_error")
                    prop = ProtobufCodec.create_property(pid, error_code)
                else:
                    pid = self._mapper.get_pid_by_type("point_value")
                    prop = ProtobufCodec.create_property(pid, value)
                
                obj = ProtobufCodec.create_object(oid, [prop])
                objects.append(obj)
        else:
            for key, value in reading.data.items():
                oid = self._mapper.get_oid(key, reading.asset)
                self._mapper.register_point_device(key, reading.asset)
                
                if device_offline:
                    pid = self._mapper.get_pid_by_type("point_error")
                    prop = ProtobufCodec.create_property(pid, 10)
                else:
                    pid = self._mapper.get_pid_by_type("point_value")
                    prop = ProtobufCodec.create_property(pid, value)
                
                obj = ProtobufCodec.create_object(oid, [prop])
                objects.append(obj)
        
        device_status = errorCode.NO_ERROR
        if reading.device_status:
            if reading.device_status == "online":
                device_status = errorCode.NO_ERROR
            else:
                device_status = errorCode.COMM_NETWORK_DOWN
        
        vdid = self._mapper.get_vd_id(reading.asset)
        
        msg = ProtobufCodec.create_message(
            uuid=self._uuid,
            cmd_id=MessageType.UPDATE_PROPERTY,
            vd_id=vdid,
            objects=objects,
            status=device_status
        )
        
        return msg
    
    def _adapt_batch_readings(self, readings: List[Reading]) -> List[apiMsg]:
        """适配批量 Reading"""
        readings_by_device = {}
        for reading in readings:
            if reading.asset not in readings_by_device:
                readings_by_device[reading.asset] = []
            readings_by_device[reading.asset].append(reading)
        
        messages = []
        for device_id, device_readings in readings_by_device.items():
            device_messages = self._adapt_device_readings_with_batch(device_id, device_readings)
            messages.extend(device_messages)
        
        return messages
    
    def _adapt_device_readings_with_batch(self, device_id: str, readings: List[Reading]) -> List[apiMsg]:
        """处理单个设备的多个 reading，点位超过 batch_size 时分批"""
        all_points = []
        device_status = None
        
        for reading in readings:
            if reading.device_status:
                device_status = reading.device_status
            
            if reading.standard_points:
                all_points.extend(reading.standard_points)
            else:
                for key, value in reading.data.items():
                    all_points.append({
                        "point_name": key,
                        "value": value,
                        "quality": "good"
                    })
        
        device_offline = device_status and device_status != "online"
        
        messages = []
        for i in range(0, len(all_points), self._batch_size):
            batch_points = all_points[i:i + self._batch_size]
            
            objects = []
            for sp in batch_points:
                point_name = sp.get("point_name", "")
                value = sp.get("value")
                quality = sp.get("quality", "good")
                metadata = sp.get("metadata", {})
                error_code = metadata.get("error_code", 10)
                
                oid = self._mapper.get_oid(point_name, device_id)
                self._mapper.register_point_device(point_name, device_id)
                
                if device_offline or quality != "good":
                    pid = self._mapper.get_pid_by_type("point_error")
                    prop = ProtobufCodec.create_property(pid, error_code)
                else:
                    pid = self._mapper.get_pid_by_type("point_value")
                    prop = ProtobufCodec.create_property(pid, value)
                
                obj = ProtobufCodec.create_object(oid, [prop])
                objects.append(obj)
            
            status = errorCode.NO_ERROR
            if i == 0 and device_status:
                if device_status == "online":
                    status = errorCode.NO_ERROR
                else:
                    status = errorCode.COMM_NETWORK_DOWN
            
            vdid = self._mapper.get_vd_id(device_id)
            
            msg = ProtobufCodec.create_message(
                uuid=self._uuid,
                cmd_id=MessageType.UPDATE_PROPERTY,
                vd_id=vdid,
                objects=objects,
                status=status
            )
            messages.append(msg)
        
        return messages
    
    def adapt_read_request(self, device_id: str, point_names: List[str]) -> apiMsg:
        """创建读请求消息"""
        vdid = self._mapper.get_vd_id(device_id)
        
        objects = []
        for point_name in point_names:
            oid = self._mapper.get_oid(point_name, device_id)
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
    
    def get_mapper(self) -> DeviceMapper:
        """获取设备映射器"""
        return self._mapper
    
    def to_bytes(self, msg: apiMsg) -> bytes:
        """将 Protobuf 消息转换为字节"""
        return ProtobufCodec.encode_message(msg)
    
    def from_bytes(self, data: bytes) -> apiMsg:
        """从字节解析 Protobuf 消息"""
        return ProtobufCodec.decode_message(data)
