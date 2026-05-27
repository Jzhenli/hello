import logging
from typing import Any, Dict, List, Optional

from .generated import (
    MessageType,
    ApplicationDataType,
    errorCode,
    apiDataValue,
    apiProperty,
    apiObject,
    apiMsg,
)

logger = logging.getLogger(__name__)


class ProtobufCodec:

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
        dv = apiDataValue()
        dv.type = ProtobufCodec.infer_data_type(value)

        if value is None:
            pass
        elif isinstance(value, bool):
            dv.uv = 1 if value else 0
        elif isinstance(value, int):
            if value >= 0:
                dv.uv = value
            else:
                dv.iv = value
        elif isinstance(value, float):
            dv.rv = value
        elif isinstance(value, str):
            dv.pv = value
        elif isinstance(value, bytes):
            dv.pv = value.decode("utf-8", errors="replace")

        return dv

    @staticmethod
    def extract_data_value(dv: apiDataValue) -> Any:
        dt = dv.type
        if dt == ApplicationDataType.APP_TAG_NULL:
            return None
        if dt == ApplicationDataType.APP_TAG_BOOLEAN:
            return bool(dv.uv)
        if dt == ApplicationDataType.APP_TAG_UNSIGNED_INT:
            return dv.uv
        if dt == ApplicationDataType.APP_TAG_SIGNED_INT:
            return dv.iv
        if dt in (ApplicationDataType.APP_TAG_REAL, ApplicationDataType.APP_TAG_DOUBLE):
            return float(dv.rv)
        if dt == ApplicationDataType.APP_TAG_CHARACTER_STRING:
            return dv.pv
        if dt == ApplicationDataType.APP_TAG_OCTET_STRING:
            return dv.pv.encode("utf-8")
        if dt == ApplicationDataType.APP_TAG_ENUMERATED:
            return dv.uv
        return None

    @staticmethod
    def create_property(
        pid: int,
        value: Any,
        index: int = -1,
        priority: int = 16,
        status: errorCode = errorCode.NO_ERROR,
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
        status: errorCode = errorCode.NO_ERROR,
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
        result: Dict[str, Any] = {
            "uuid": msg.uuid,
            "cmdID": msg.cmdID,
            "vdID": msg.vdID,
            "status": msg.status,
            "objects": [],
        }
        for obj in msg.opv:
            obj_dict: Dict[str, Any] = {"oid": obj.oid, "properties": []}
            for prop in obj.pv:
                prop_dict: Dict[str, Any] = {
                    "pid": prop.pid,
                    "index": prop.index,
                    "priority": prop.priority,
                    "value": ProtobufCodec.extract_data_value(prop.v),
                    "status": prop.status,
                }
                obj_dict["properties"].append(prop_dict)
            result["objects"].append(obj_dict)
        return result
