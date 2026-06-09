"""客户A私有云适配器

完整协议：数据格式 + Topic结构 + 消息流程 作为一个整体
"""

import logging
from typing import Any, Dict, List

from xagent.xcore.storage.interface import Reading

from ..types import CommandContext, CommandData, CommandResult, ResponsePacket
from ..exceptions import CommandParseError
from .base import BaseAdapter
from . import register

logger = logging.getLogger(__name__)


@register("customer_a")
class CustomerAAdapter(BaseAdapter):
    """客户A协议 - 数据格式与Topic结构作为整体"""

    MSGID_MAX = 4294967295

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._msgid_counter = 0

    # ===== upload_type推断 =====

    def _infer_upload_type(self, reading: Reading) -> str:
        """客户A：根据 device_status 推断上行类型

        online → connect
        offline → disconnect
        其他 → property
        """
        if reading.device_status == "online":
            return "connect"
        elif reading.device_status == "offline":
            return "disconnect"
        return "property"

    # ===== 上行payload构建 =====

    def _build_upload_payload(self, readings: List[Reading], upload_type: str) -> Dict[str, Any]:
        """构建上行payload - 根据upload_type分派"""
        if upload_type == "connect":
            return self._build_connect_payload(readings[0])
        elif upload_type == "disconnect":
            return self._build_disconnect_payload(readings[0])
        else:
            return self._build_property_payload(readings)

    def _build_property_payload(self, readings: List[Reading]) -> Dict[str, Any]:
        """普通数据上报: {msgid, params: {point: {value, ts}}}"""
        params = {}
        for reading in readings:
            for point_name, point_value in reading.data.items():
                params[point_name] = {
                    "value": point_value,
                    "ts": int(reading.timestamp * 1000),
                }

        return {
            "msgid": self._generate_msgid(),
            "params": params,
        }

    def _build_connect_payload(self, reading: Reading) -> Dict[str, Any]:
        """设备上线: {msgid, params: {productKey, deviceSN}}"""
        product_key = self._config.get("productKey", "")
        return {
            "msgid": self._generate_msgid(),
            "params": {
                "productKey": product_key,
                "deviceSN": reading.asset,
            },
        }

    def _build_disconnect_payload(self, reading: Reading) -> Dict[str, Any]:
        """设备下线: {msgid, params: {productKey, deviceSN}}"""
        product_key = self._config.get("productKey", "")
        return {
            "msgid": self._generate_msgid(),
            "params": {
                "productKey": product_key,
                "deviceSN": reading.asset,
            },
        }

    def _generate_msgid(self) -> str:
        """生成消息ID"""
        self._msgid_counter = (self._msgid_counter + 1) % (self.MSGID_MAX + 1)
        return str(self._msgid_counter)

    # ===== 下行命令解析 =====

    def parse_command(self, raw: Dict[str, Any], context: CommandContext) -> CommandData:
        """解析下行命令 - 根据topic_type分派"""
        try:
            if context.topic_type == "property_down":
                return CommandData(
                    asset="",
                    data=raw.get("params", {}),
                    command_type="write_property",
                    requires_reply=True,
                )
            elif context.topic_type in ("connect_reply", "disconnect_reply"):
                return CommandData(
                    asset=raw.get("data", {}).get("deviceSN", ""),
                    data=raw.get("data", {}),
                    command_type="device_status",
                    requires_reply=False,
                )
            else:
                return CommandData(
                    asset=raw.get("asset", ""),
                    data=raw.get("data", {}),
                    requires_reply=True,
                )
        except Exception as e:
            raise CommandParseError(f"Failed to parse command: {e}") from e

    # ===== 下行响应格式化 =====

    def _build_response_payload(self, result: CommandResult, context: CommandContext) -> Dict[str, Any]:
        """构建响应payload"""
        msgid = context.raw_command.get("msgid", "0")

        if context.topic_type == "property_down":
            return {
                "msgid": msgid,
                "code": 0 if result.success else -1,
                "data": {},
            }

        return {
            "msgid": msgid,
            "code": 0 if result.success else -1,
            "message": "success" if result.success else (result.error or "error"),
        }

    def _get_reply_topic(self, command_topic: str) -> str:
        """客户A回复topic规则"""
        rule = self._config.get("reply_topic_rule", "")
        if rule == "suffix_reply":
            return command_topic + "_reply"
        elif rule == "replace_down_with_reply":
            return command_topic.replace("/down", "/reply")

        # 客户A默认规则：property_down → _reply, 其他 → /result
        if command_topic.endswith("/down"):
            return command_topic + "_reply"
        return f"{command_topic}/result"
