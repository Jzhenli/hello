"""Protobuf Codec - Encodes and decodes apiMsg messages"""

import sys
import os

_src_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if os.path.exists(_src_path):
    sys.path.insert(0, _src_path)

try:
    from xagent.plugins.north.xnc_client.generated import (
        MessageType,
        ApplicationDataType,
        errorCode,
        apiDataValue,
        apiProperty,
        apiObject,
        apiMsg,
    )
except ImportError:
    from generated import (
        MessageType,
        ApplicationDataType,
        errorCode,
        apiDataValue,
        apiProperty,
        apiObject,
        apiMsg,
    )

from typing import Any, Dict, List, Optional, Union


class ProtobufCodec:
    """Protobuf message codec for XNC UDP protocol"""
    
    @staticmethod
    def infer_data_type(value: Any) -> ApplicationDataType:
        if value is None:
            return ApplicationDataType.APP_TAG_NULL
        if isinstance(value, bool):
            return ApplicationDataType.APP_TAG_BOOLEAN
        if isinstance(value, int):
            if value >= 0:
                return ApplicationDataType.APP_TAG_UNSIGNED_INT
            return ApplicationDataType.APP_TAG_SIGNED_INT
        if isinstance(value, float):
            return ApplicationDataType.APP_TAG_DOUBLE
        if isinstance(value, str):
            return ApplicationDataType.APP_TAG_CHARACTER_STRING
        if isinstance(value, bytes):
            return ApplicationDataType.APP_TAG_OCTET_STRING
        return ApplicationDataType.APP_TAG_NULL
    
    @staticmethod
    def create_data_value(value: Any) -> apiDataValue:
        data_value = apiDataValue()
        data_value.type = ProtobufCodec.infer_data_type(value)
        
        if value is None:
            pass
        elif isinstance(value, bool):
            data_value.uv = 1 if value else 0
        elif isinstance(value, int):
            if value >= 0:
                data_value.uv = value
            else:
                data_value.iv = value
        elif isinstance(value, float):
            data_value.rv = value
        elif isinstance(value, str):
            data_value.pv = value
        elif isinstance(value, bytes):
            data_value.pv = value.decode('utf-8', errors='replace')
        
        return data_value
    
    @staticmethod
    def extract_data_value(data_value: apiDataValue) -> Any:
        data_type = data_value.type
        
        if data_type == ApplicationDataType.APP_TAG_NULL:
            return None
        elif data_type == ApplicationDataType.APP_TAG_BOOLEAN:
            return bool(data_value.uv)
        elif data_type == ApplicationDataType.APP_TAG_UNSIGNED_INT:
            return data_value.uv
        elif data_type == ApplicationDataType.APP_TAG_SIGNED_INT:
            return data_value.iv
        elif data_type == ApplicationDataType.APP_TAG_REAL:
            return float(data_value.rv)
        elif data_type == ApplicationDataType.APP_TAG_DOUBLE:
            return float(data_value.rv)
        elif data_type == ApplicationDataType.APP_TAG_CHARACTER_STRING:
            return data_value.pv
        elif data_type == ApplicationDataType.APP_TAG_OCTET_STRING:
            return data_value.pv.encode('utf-8')
        elif data_type == ApplicationDataType.APP_TAG_ENUMERATED:
            return data_value.uv
        
        return None
    
    @staticmethod
    def create_property(
        pid: int,
        value: Any,
        index: int = -1,
        priority: int = 16,
        status: errorCode = errorCode.NO_ERROR
    ) -> apiProperty:
        prop = apiProperty()
        prop.pid = pid
        prop.index = index
        prop.priority = priority
        prop.v.CopyFrom(ProtobufCodec.create_data_value(value))
        prop.status = status
        return prop
    
    @staticmethod
    def create_object(oid: int, properties: List[apiProperty]) -> apiObject:
        obj = apiObject()
        obj.oid = oid
        for prop in properties:
            obj.pv.append(prop)
        return obj
    
    @staticmethod
    def create_message(
        uuid: int,
        cmd_id: MessageType,
        vd_id: int,
        objects: List[apiObject],
        status: errorCode = errorCode.NO_ERROR
    ) -> apiMsg:
        msg = apiMsg()
        msg.uuid = uuid
        msg.cmdID = cmd_id
        msg.vdID = vd_id
        for obj in objects:
            msg.opv.append(obj)
        msg.status = status
        return msg
    
    @staticmethod
    def encode_message(msg: apiMsg) -> bytes:
        return msg.SerializeToString()
    
    @staticmethod
    def decode_message(data: bytes) -> apiMsg:
        msg = apiMsg()
        msg.ParseFromString(data)
        return msg
    
    @staticmethod
    def message_to_dict(msg: apiMsg) -> Dict[str, Any]:
        result = {
            "uuid": msg.uuid,
            "cmdID": msg.cmdID,
            "cmdID_name": ProtobufCodec.get_message_type_name(msg.cmdID),
            "vdID": msg.vdID,
            "status": msg.status,
            "status_name": ProtobufCodec.get_error_code_name(msg.status),
            "objects": []
        }
        
        for obj in msg.opv:
            obj_dict = {
                "oid": obj.oid,
                "properties": []
            }
            for prop in obj.pv:
                prop_dict = {
                    "pid": prop.pid,
                    "index": prop.index,
                    "priority": prop.priority,
                    "value": ProtobufCodec.extract_data_value(prop.v),
                    "value_type": ProtobufCodec.get_data_type_name(prop.v.type),
                    "status": prop.status
                }
                obj_dict["properties"].append(prop_dict)
            result["objects"].append(obj_dict)
        
        return result
    
    @staticmethod
    def get_message_type_name(cmd_id: int) -> str:
        names = {
            10: "CREATE_OBJECT",
            11: "DELETE_OBJECT",
            12: "READ_PROPERTY",
            15: "WRITE_PROPERTY",
            20: "REINITIALIZE_DEVICE",
            21: "VT_OPEN",
            22: "VT_CLOSE",
            310: "PUB",
            1042: "UPDATE_PROPERTY",
            1298: "WARM_REBOOT",
        }
        return names.get(cmd_id, f"UNKNOWN({cmd_id})")
    
    @staticmethod
    def get_data_type_name(data_type: int) -> str:
        names = {
            0: "NULL",
            1: "BOOLEAN",
            2: "UNSIGNED_INT",
            3: "SIGNED_INT",
            4: "REAL",
            5: "DOUBLE",
            6: "OCTET_STRING",
            7: "CHARACTER_STRING",
            8: "BIT_STRING",
            9: "ENUMERATED",
            10: "DATE",
            11: "TIME",
            12: "OBJECT_IDENTIFIER",
        }
        return names.get(data_type, f"UNKNOWN({data_type})")
    
    @staticmethod
    def get_error_code_name(error_code: int) -> str:
        names = {
            0: "NO_ERROR",
            1: "DEVICE_NOT_FOUND",
            2: "PROPERTY_NOT_FOUND",
            3: "INSUFFICIENT_SPACE",
            4: "OPERATIONAL_PROBLEM",
            5: "READ_ONLY",
            6: "INVALID_VALUE",
            7: "ACCESS_DENIED",
            8: "TIMEOUT",
            9: "COMM_NETWORK_DOWN",
        }
        return names.get(error_code, f"UNKNOWN({error_code})")
    
    @staticmethod
    def create_read_property_message(
        uuid: int,
        vd_id: int,
        oid: int,
        pid: int
    ) -> apiMsg:
        prop = ProtobufCodec.create_property(pid, None)
        obj = ProtobufCodec.create_object(oid, [prop])
        return ProtobufCodec.create_message(
            uuid=uuid,
            cmd_id=MessageType.READ_PROPERTY,
            vd_id=vd_id,
            objects=[obj]
        )
    
    @staticmethod
    def create_write_property_message(
        uuid: int,
        vd_id: int,
        oid: int,
        pid: int,
        value: Any
    ) -> apiMsg:
        prop = ProtobufCodec.create_property(pid, value)
        obj = ProtobufCodec.create_object(oid, [prop])
        return ProtobufCodec.create_message(
            uuid=uuid,
            cmd_id=MessageType.WRITE_PROPERTY,
            vd_id=vd_id,
            objects=[obj]
        )
