"""客户A私有云适配器
完整需求文档：
1. 设备属性上报
   Topic: $v1/{productKey}/{deviceSN}/sys/property/up
   方向：上行
   网关上报数据格式:
   {
       "msgid": "123456",
       "params": {
           "Temperature": {
               "value": "37.0",
               "ts": 1524448722000
           },
           "Battery": {
               "value": 23.6,
               "ts": 1524448722000
           }
       }
   }
   说明：
   - msgid: String类型的数字，取值范围0~4294967295，用于消息跟踪
   - params: 点位数据对象，每个属性是一个点位
   - value: 点位值（可以是字符串或数字）
   - ts: 毫秒时间戳

2. 设置设备属性
   Topic: $v1/{productKey}/{deviceSN}/sys/property/down
   方向：下行
   云平台下发数据格式:
   {
       "msgid": "123456",
       "params": {
           "Temperature": "37.0"
       }
   }

   Topic: $v1/{productKey}/{deviceSN}/sys/property/down_reply
   方向：上行
   网关回复上报数据格式:
   {
       "msgid": "123456",
       "code": 0,
       "data": {}
   }
   说明：
   - msgid: 消息ID（与请求保持一致）
   - params: 要写入的属性
   - code: 0表示成功，其他表示失败
   - data: 固定为空对象

3. 南向设备上线
   Topic: $v1/{productKey}/{deviceSN}/sys/subdevice/connect
   方向：上行
   网关上报数据格式:
   {
       "msgid": "123456",
       "params": {
           "productKey": "al12345****",
           "deviceSN": "device1234"
       }
   }

   Topic: $v1/{productKey}/{deviceSN}/sys/subdevice/connect_reply
   方向：下行
   云平台回复格式:
   {
       "msgid": "123456",
       "code": 0,
       "message": "success",
       "data": {
           "productKey": "al12345****",
           "deviceSN": "device1234"
       }
   }
   说明：
   - params包含productKey和deviceSN
   - 云平台回复包含message字段
   - data中返回productKey和deviceSN

4. 南向设备下线
   Topic: $v1/{productKey}/{deviceSN}/sys/subdevice/disconnect
   方向：上行
   网关上报数据格式:
   {
       "msgid": "123456",
       "params": {
           "productKey": "al12345****",
           "deviceSN": "device1234"
       }
   }

   Topic: $v1/{productKey}/{deviceSN}/sys/subdevice/disconnect_reply
   方向：下行
   云平台回复格式:
   {
       "msgid": "123456",
       "code": 0,
       "message": "success",
       "data": {
           "productKey": "al12345****",
           "deviceSN": "device1234"
       }
   }
   说明：
   - params包含productKey和deviceSN
   - 云平台回复包含message字段
   - data中返回productKey和deviceSN

完整协议：数据格式 + Topic结构 + 消息流程 作为一个整体
"""

import logging
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from ..types import CommandContext, CommandData, CommandResult, ResponsePacket
from ..exceptions import CommandParseError
from .base import BaseAdapter
from .registry import register

logger = logging.getLogger(__name__)


@register("customer_a", customer_code="C001")
class CustomerAAdapter(BaseAdapter):
    """客户A协议 - 数据格式与Topic结构作为整体"""

    MSGID_MAX = 4294967295

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._msgid_counter = 0
        # 设备状态缓存：{asset: last_status}
        self._device_status_cache: Dict[str, str] = {}

    # ===== Topic 上下文（协议特有变量） =====

    def _topic_context(
        self,
        upload_type: str,
        readings: Optional[List[Reading]] = None,
    ) -> Dict[str, str]:
        """客户A协议：添加 deviceSN 运行时变量

        发布时：deviceSN = readings[0].asset
        订阅时：deviceSN = "+" (MQTT 通配符)
        """
        context = super()._topic_context(upload_type, readings)
        if readings:
            # 发布：使用实际设备序列号
            context["deviceSN"] = readings[0].asset
        else:
            # 订阅：使用 MQTT 通配符匹配所有设备
            context["deviceSN"] = "+"
        return context

    # ===== upload_type推断 =====

    def _infer_upload_type(self, reading: Reading) -> str:
        """客户A：根据 device_status 变化推断上行类型

        状态变化：
        - 无状态 → online: connect（首次上线）
        - offline → online: connect（重新上线）
        - online → offline: disconnect（下线）
        - 状态未变化: property（属性数据）

        注意：设备上线/下线消息只在状态变化时发送一次，
        其他时候发送属性数据。
        """
        asset = reading.asset
        current_status = reading.device_status or "unknown"
        last_status = self._device_status_cache.get(asset)

        # 更新状态缓存
        self._device_status_cache[asset] = current_status

        # 状态变化检测
        if current_status == "online" and last_status != "online":
            # 首次上线或重新上线
            return "connect"
        elif current_status == "offline" and last_status == "online":
            # 从在线变为离线
            return "disconnect"
        else:
            # 状态未变化，发送属性数据
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
        """解析下行命令 - 根据topic_type分派

        注意：客户A协议中，property_down 类型的命令体不包含 asset 字段，
        asset 信息从 topic 路径中提取。
        """
        try:
            if context.topic_type == "property_down":
                # 客户A协议：property_down 命令的 asset 从 topic 中提取
                # topic 格式: /sys/{productKey}/{deviceSN}/thing/service/property/set
                device_sn = self._extract_device_sn_from_topic(context.topic)
                return CommandData(
                    asset=device_sn,
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

    def _extract_device_sn_from_topic(self, topic: str) -> str:
        """从 topic 中提取 deviceSN

        客户A topic 格式: $v1/{productKey}/{deviceSN}/sys/...
        例如: $v1/xnc/m_001/sys/property/down
        """
        parts = topic.split("/")

        # 格式: $v1/{productKey}/{deviceSN}/sys/...
        # parts: ['$v1', 'xnc', 'm_001', 'sys', 'property', 'down']
        if len(parts) >= 4 and parts[0].startswith("$v"):
            return parts[2]  # deviceSN 是第 3 个部分（索引 2）

        # 兼容旧格式: /sys/{productKey}/{deviceSN}/...
        if len(parts) >= 4 and parts[1] == "sys":
            return parts[3]

        return ""

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
