import logging
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from .generated import MessageType, errorCode, apiMsg
from .protobuf_codec import ProtobufCodec
from .protocol_codec import UDPProtocolCodec
from .mapping import IDMapper
from .models import CommandMessage

logger = logging.getLogger(__name__)


class ProtobufHandler:

    def __init__(self, mapper: IDMapper, uuid: int = 0, batch_size: int = 50):
        self._mapper = mapper
        self._uuid = uuid
        self._batch_size = batch_size
        self._protocol_codec = UDPProtocolCodec()

    def adapt_upload(
        self, readings: List[Reading], context: Dict[str, Any]
    ) -> List[apiMsg]:
        if not readings:
            return []

        messages: List[apiMsg] = []
        for reading in readings:
            msgs = self._adapt_reading(reading)
            messages.extend(msgs)
        return messages

    def parse_response(
        self, response: Any, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(response, apiMsg):
            return {"raw": str(response)}

        msg = response
        device_id = self._mapper.get_device_id_by_vdid(msg.vdID)

        result: Dict[str, Any] = {
            "uuid": msg.uuid,
            "cmdID": msg.cmdID,
            "vdID": msg.vdID,
            "status": msg.status,
            "device_id": device_id,
            "data": {},
        }

        for obj in msg.opv:
            point_name = self._mapper.get_point_name_by_oid(obj.oid)
            for prop in obj.pv:
                value = ProtobufCodec.extract_data_value(prop.v)
                key = point_name if point_name else f"oid_{obj.oid}"
                result["data"][key] = value

        return result

    def encode_upload(
        self, readings: List[Reading], context: Dict[str, Any]
    ) -> List[bytes]:
        messages = self.adapt_upload(readings, context)
        packets: List[bytes] = []
        for msg in messages:
            payload = ProtobufCodec.encode_message(msg)
            packet = self._protocol_codec.encode(payload)
            packets.append(packet)
        return packets

    def decode_command(self, data: bytes, addr: tuple) -> Optional[CommandMessage]:
        try:
            sequence, payload = self._protocol_codec.decode(data)
            msg = ProtobufCodec.decode_message(payload)
            return self._build_command_message(msg, addr, sequence)
        except ValueError as e:
            logger.error(f"Protocol decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error decoding command: {e}", exc_info=True)
            return None

    def encode_response(
        self, cmd: CommandMessage, error: Optional[str] = None
    ) -> Optional[bytes]:
        try:
            response_msg = apiMsg()
            response_msg.uuid = int(cmd.request_id) if cmd.request_id else 0
            response_msg.vdID = self._mapper.get_vd_id(cmd.device_id)

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

    def _adapt_reading(self, reading: Reading) -> List[apiMsg]:
        device_offline = reading.device_status and reading.device_status != "online"

        all_points = self._extract_points(reading)
        messages: List[apiMsg] = []

        for i in range(0, len(all_points), self._batch_size):
            batch = all_points[i : i + self._batch_size]
            objects = [self._create_point_object(p, reading.asset, device_offline) for p in batch]

            status = errorCode.NO_ERROR
            if i == 0 and reading.device_status:
                status = (
                    errorCode.NO_ERROR
                    if reading.device_status == "online"
                    else errorCode.COMM_NETWORK_DOWN
                )

            vdid = self._mapper.get_vd_id(reading.asset)
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
        self, point: Dict[str, Any], device_id: str, device_offline: bool
    ) -> Any:
        point_name = point.get("point_name", "")
        value = point.get("value")
        quality = point.get("quality", "good")
        metadata = point.get("metadata", {})
        error_code = metadata.get("error_code", 10)

        oid = self._mapper.get_oid(point_name, device_id)

        if device_offline or quality != "good":
            pid = self._mapper.get_pid_by_type("point_error")
            prop = ProtobufCodec.create_property(pid, error_code)
        else:
            pid = self._mapper.get_pid_by_type("point_value")
            prop = ProtobufCodec.create_property(pid, value)

        return ProtobufCodec.create_object(oid, [prop])

    def _build_command_message(
        self, msg: apiMsg, addr: tuple, sequence: int
    ) -> CommandMessage:
        device_id = self._mapper.get_device_id_by_vdid(msg.vdID) or str(msg.vdID)

        if msg.cmdID == MessageType.READ_PROPERTY:
            command_type = "read_property"
            points = [
                self._mapper.get_point_name_by_oid(obj.oid) or f"oid_{obj.oid}"
                for obj in msg.opv
            ]
            data: Dict[str, Any] = {}
        elif msg.cmdID == MessageType.WRITE_PROPERTY:
            command_type = "write_property"
            points = []
            data = {}
            for obj in msg.opv:
                point_name = self._mapper.get_point_name_by_oid(obj.oid) or f"oid_{obj.oid}"
                for prop in obj.pv:
                    data[point_name] = ProtobufCodec.extract_data_value(prop.v)
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
