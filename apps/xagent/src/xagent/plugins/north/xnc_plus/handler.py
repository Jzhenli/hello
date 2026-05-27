import logging
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from .generated import MessageType, errorCode, apiMsg
from .mapping import DBMappingRegistry
from .models import CommandMessage, Direction
from .protobuf_codec import ProtobufCodec
from .protocol_codec import UDPProtocolCodec

logger = logging.getLogger(__name__)


class ProtobufHandler:

    def __init__(self, uuid: int = 0, batch_size: int = 50):
        self._uuid = uuid
        self._batch_size = batch_size
        self._protocol_codec = UDPProtocolCodec()

    def adapt_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any],
        registry: Optional[DBMappingRegistry] = None,
    ) -> List[apiMsg]:
        if not readings:
            return []

        messages: List[apiMsg] = []
        for reading in readings:
            msgs = self._adapt_reading(reading, registry)
            messages.extend(msgs)
        return messages

    def parse_response(
        self,
        response: Any,
        context: Dict[str, Any],
        registry: Optional[DBMappingRegistry] = None,
    ) -> Dict[str, Any]:
        if not isinstance(response, apiMsg):
            return {"raw": str(response)}

        msg = response
        device_id = registry.get_device_id_by_vdid(msg.vdID) if registry else None

        result: Dict[str, Any] = {
            "uuid": msg.uuid,
            "cmdID": msg.cmdID,
            "vdID": msg.vdID,
            "status": msg.status,
            "device_id": device_id,
            "data": {},
        }

        for obj in msg.opv:
            point_name = registry.get_point_name_by_oid(obj.oid) if registry else None
            for prop in obj.pv:
                value = ProtobufCodec.extract_data_value(prop.v)
                key = point_name if point_name else f"oid_{obj.oid}"
                result["data"][key] = value

        return result

    def encode_upload(
        self,
        readings: List[Reading],
        context: Dict[str, Any],
        registry: Optional[DBMappingRegistry] = None,
    ) -> List[bytes]:
        messages = self.adapt_upload(readings, context, registry)
        packets: List[bytes] = []
        for msg in messages:
            payload = ProtobufCodec.encode_message(msg)
            packet = self._protocol_codec.encode(payload)
            packets.append(packet)
        return packets

    def decode_command(
        self,
        data: bytes,
        addr: tuple,
        registry: Optional[DBMappingRegistry] = None,
    ) -> Optional[CommandMessage]:
        try:
            sequence, payload = self._protocol_codec.decode(data)
            msg = ProtobufCodec.decode_message(payload)
            return self._build_command_message(msg, addr, sequence, registry)
        except ValueError as e:
            logger.error(f"Protocol decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error decoding command: {e}", exc_info=True)
            return None

    def encode_response(
        self,
        cmd: CommandMessage,
        registry: Optional[DBMappingRegistry] = None,
        error: Optional[str] = None,
    ) -> Optional[bytes]:
        try:
            response_msg = apiMsg()
            response_msg.uuid = int(cmd.request_id) if cmd.request_id else 0

            if registry:
                vdid = registry.get_vd_id(cmd.device_id)
                response_msg.vdID = vdid if vdid is not None else 0
            else:
                response_msg.vdID = 0

            if cmd.command_type == "read_property":
                response_msg.cmdID = MessageType.READ_PROPERTY
            elif cmd.command_type == "write_property":
                response_msg.cmdID = MessageType.WRITE_PROPERTY
            else:
                response_msg.cmdID = MessageType.UPDATE_PROPERTY

            response_msg.status = (
                errorCode.OPERATIONAL_PROBLEM if error else errorCode.NO_ERROR
            )

            payload = ProtobufCodec.encode_message(response_msg)
            return self._protocol_codec.encode(payload, sequence=cmd.sequence)
        except Exception as e:
            logger.error(f"Error encoding response: {e}")
            return None

    def _adapt_reading(
        self,
        reading: Reading,
        registry: Optional[DBMappingRegistry] = None,
    ) -> List[apiMsg]:
        device_offline = reading.device_status and reading.device_status != "online"

        all_points = self._extract_points(reading)
        messages: List[apiMsg] = []

        for i in range(0, len(all_points), self._batch_size):
            batch = all_points[i : i + self._batch_size]
            objects = [
                self._create_point_object(p, reading.asset, device_offline, registry)
                for p in batch
            ]

            status = errorCode.NO_ERROR
            if i == 0 and reading.device_status:
                status = (
                    errorCode.NO_ERROR
                    if reading.device_status == "online"
                    else errorCode.COMM_NETWORK_DOWN
                )

            vdid = 0
            if registry:
                v = registry.get_vd_id(reading.asset)
                if v is not None:
                    vdid = v

            msg = ProtobufCodec.create_message(
                uuid=self._uuid,
                cmd_id=MessageType.UPDATE_PROPERTY,
                vd_id=vdid,
                objects=objects,
                status=status,
            )
            messages.append(msg)

        return messages

    def _extract_points(self, reading: Reading) -> List[Dict[str, Any]]:
        if reading.standard_points:
            return list(reading.standard_points)

        points: List[Dict[str, Any]] = []
        for key, value in reading.data.items():
            points.append({
                "point_name": key,
                "value": value,
                "quality": "good",
                "metadata": {},
            })
        return points

    def _create_point_object(
        self,
        point: Dict[str, Any],
        device_id: str,
        device_offline: bool,
        registry: Optional[DBMappingRegistry] = None,
    ) -> Any:
        point_name = point.get("point_name", "")
        value = point.get("value")
        quality = point.get("quality", "good")
        metadata = point.get("metadata", {})
        error_code = metadata.get("error_code", 10)

        oid = 0
        pid_value = 85
        pid_error = 103

        if registry:
            o = registry.get_oid(point_name, device_id)
            if o is not None:
                oid = o
            pid_value = registry.get_pid_by_type("point_value")
            pid_error = registry.get_pid_by_type("point_error")

            mapping = registry.lookup_forward(point_name, device_id)
            if mapping and mapping.value_transform:
                value = mapping.value_transform.forward(value)

        if device_offline or quality != "good":
            prop = ProtobufCodec.create_property(pid_error, error_code)
        else:
            prop = ProtobufCodec.create_property(pid_value, value)

        return ProtobufCodec.create_object(oid, [prop])

    def _build_command_message(
        self,
        msg: apiMsg,
        addr: tuple,
        sequence: int,
        registry: Optional[DBMappingRegistry] = None,
    ) -> CommandMessage:
        device_id = str(msg.vdID)
        if registry:
            d = registry.get_device_id_by_vdid(msg.vdID)
            if d is not None:
                device_id = d

        if msg.cmdID == MessageType.READ_PROPERTY:
            command_type = "read_property"
            points = []
            if registry:
                points = [
                    registry.get_point_name_by_oid(obj.oid) or f"oid_{obj.oid}"
                    for obj in msg.opv
                ]
            else:
                points = [f"oid_{obj.oid}" for obj in msg.opv]
            data: Dict[str, Any] = {}
        elif msg.cmdID == MessageType.WRITE_PROPERTY:
            command_type = "write_property"
            points = []
            data = {}
            for obj in msg.opv:
                point_name = f"oid_{obj.oid}"
                if registry:
                    pn = registry.get_point_name_by_oid(obj.oid)
                    if pn is not None:
                        point_name = pn
                for prop in obj.pv:
                    raw_value = ProtobufCodec.extract_data_value(prop.v)
                    if registry:
                        data[point_name] = registry.transform_value(
                            point_name, device_id, raw_value, Direction.COMMAND
                        )
                    else:
                        data[point_name] = raw_value
        else:
            command_type = "unknown"
            points = []
            data = {}

        return CommandMessage(
            device_id=device_id,
            command_type=command_type,
            points=points,
            data=data,
            request_id=str(msg.uuid),
            reply_addr=addr,
            sequence=sequence,
        )
