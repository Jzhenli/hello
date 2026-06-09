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
"""

import logging
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from ..adapter import MQTTAdapterBase, DownlinkResult
from . import register

logger = logging.getLogger(__name__)


@register("customer_a")
class CustomerAAdapter(MQTTAdapterBase):
    """
    客户A适配器 - 只需覆盖与默认格式不同的方法

    设计要点：
    - 继承 MQTTAdapterBase，自动获得默认实现
    - 只覆盖需要定制的方法：adapt_upload、parse_command、format_result
    - 其他方法（adapt_command、parse_response、to_json）使用基类默认实现
    """

    # msgid取值范围
    MSGID_MAX = 4294967295  # 2^32 - 1

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # 客户A专属配置
        self._product_key = self.config.get("productKey", "")
        self._device_sn = self.config.get("deviceSN", "")
        self._sn_prefix = self.config.get("sn_prefix", "")
        # 用于生成递增的msgid（可选，也可以用随机数）
        self._msgid_counter = 0

    # ===== Topic管理 =====

    def get_subscribe_topics(self, context: Dict[str, Any]) -> List[str]:
        """
        获取客户A需要订阅的topic列表

        需要订阅的topic：
        1. $v1/{productKey}/{deviceSN}/sys/property/down - 设置设备属性
        2. $v1/{productKey}/{deviceSN}/sys/subdevice/connect_reply - 设备上线回复
        3. $v1/{productKey}/{deviceSN}/sys/subdevice/disconnect_reply - 设备下线回复

        Args:
            context: 上下文信息

        Returns:
            需要订阅的topic列表
        """
        product_key = context.get("productKey", self._product_key)
        device_sn = context.get("deviceSN", self._device_sn)

        if not product_key or not device_sn:
            logger.warning("productKey or deviceSN not provided, cannot generate subscribe topics")
            return []

        base_topic = f"$v1/{product_key}/{device_sn}/sys"

        return [
            f"{base_topic}/property/down",                    # 设置设备属性
            f"{base_topic}/subdevice/connect_reply",          # 设备上线回复
            f"{base_topic}/subdevice/disconnect_reply",       # 设备下线回复
        ]

    def get_publish_topic(self, context: Dict[str, Any]) -> str:
        """
        获取上报数据的topic

        根据上报类型返回不同的topic：
        - 设备上线：$v1/.../sys/subdevice/connect
        - 设备下线：$v1/.../sys/subdevice/disconnect
        - 普通数据：$v1/.../sys/property/up

        Args:
            context: 上下文信息

        Returns:
            上报topic
        """
        product_key = context.get("productKey", self._product_key)
        device_sn = context.get("deviceSN", self._device_sn)
        publish_type = context.get("publish_type", "property")  # property, connect, disconnect

        if not product_key or not device_sn:
            return context.get("topic", "")

        base_topic = f"$v1/{product_key}/{device_sn}/sys"

        if publish_type == "connect":
            return f"{base_topic}/subdevice/connect"
        elif publish_type == "disconnect":
            return f"{base_topic}/subdevice/disconnect"
        else:
            return f"{base_topic}/property/up"

    def get_reply_topic(self, command_topic: str, context: Dict[str, Any]) -> str:
        """
        根据命令topic生成回复topic

        例如：
        - $v1/.../sys/property/down → $v1/.../sys/property/down_reply

        Args:
            command_topic: 命令topic
            context: 上下文信息

        Returns:
            回复topic
        """
        # 客户A的回复topic规则：在命令topic后加"_reply"
        if command_topic.endswith("/down"):
            return command_topic + "_reply"
        else:
            # 默认规则
            return command_topic + "_reply"

    def _generate_msgid(self) -> str:
        """
        生成消息ID

        Returns:
            String类型的数字，范围0~4294967295
        """
        # 方式1：递增计数器（推荐，便于跟踪）
        self._msgid_counter = (self._msgid_counter + 1) % (self.MSGID_MAX + 1)
        return str(self._msgid_counter)

        # 方式2：随机数（备选）
        # return str(random.randint(0, self.MSGID_MAX))

    # ===== 上行：覆盖 =====

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """
        客户A上行格式：{msgid, params}

        支持两种场景：
        1. 设备上线/下线：Reading.device_status为"online"或"offline"
        2. 普通数据上报：其他情况

        注意：自行实现完整逻辑，包含异常处理
        """
        try:
            if not readings:
                return None

            # 检查是否为设备上线/下线事件
            reading = readings[0]
            device_status = reading.device_status

            if device_status in ("online", "offline"):
                # 设备上线/下线上报
                return self._adapt_device_status(reading, context)
            else:
                # 普通数据上报
                return self._adapt_normal_data(readings, context)

        except Exception as e:
            logger.error(f"adapt_upload error: {e}")
            return None

    def _adapt_device_status(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        适配设备上线/下线数据

        Args:
            reading: Reading对象，device_status为"online"或"offline"
            context: 上下文信息

        Returns:
            客户A设备上线/下线格式
        """
        # 从context或reading.data中获取productKey和deviceSN
        product_key = context.get("productKey", reading.data.get("productKey", ""))
        device_sn = reading.asset  # 使用asset作为deviceSN

        return {
            "msgid": self._generate_msgid(),
            "params": {
                "productKey": product_key,
                "deviceSN": device_sn,
            }
        }

    def _adapt_normal_data(self, readings: List[Reading], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        适配普通数据上报

        Args:
            readings: Reading对象列表
            context: 上下文信息

        Returns:
            客户A普通数据上报格式
        """
        # 合并所有readings的数据到一个params对象
        params = {}

        for reading in readings:
            # 遍历reading.data中的每个点位
            for point_name, point_value in reading.data.items():
                # 构造点位数据
                params[point_name] = {
                    "value": point_value,
                    "ts": int(reading.timestamp * 1000),  # 转换为毫秒时间戳
                }

        # 构造最终格式
        result = {
            "msgid": self._generate_msgid(),
            "params": params,
        }

        return result

    # ===== 下行：覆盖 =====

    def parse_command(self, raw: Dict[str, Any], topic: Optional[str] = None) -> Dict[str, Any]:
        """
        客户A下行命令解析：根据topic区分不同类型的命令

        支持的topic：
        - $v1/{productKey}/{deviceSN}/sys/property/down - 设置设备属性
        - $v1/{productKey}/{deviceSN}/sys/subdevice/connect_reply - 设备上线回复
        - $v1/{productKey}/{deviceSN}/sys/subdevice/disconnect_reply - 设备下线回复

        Args:
            raw: 客户A的命令格式
            topic: MQTT topic

        Returns:
            统一内部格式 {"asset": str, "data": Dict[str, Any]}
        """
        # 根据topic判断命令类型
        if topic:
            if "/sys/property/down" in topic:
                # 设置设备属性命令
                return self._parse_property_down(raw, topic)
            elif "/sys/subdevice/connect_reply" in topic:
                # 设备上线回复
                return self._parse_connect_reply(raw, topic)
            elif "/sys/subdevice/disconnect_reply" in topic:
                # 设备下线回复
                return self._parse_disconnect_reply(raw, topic)

        # 默认：设置设备属性（向后兼容）
        return self._parse_property_down(raw, topic)

    def _parse_property_down(self, raw: Dict[str, Any], topic: Optional[str]) -> Dict[str, Any]:
        """
        解析设置设备属性命令

        Args:
            raw: {"msgid": "123456", "params": {"Temperature": "37.0"}}
            topic: $v1/{productKey}/{deviceSN}/sys/property/down

        Returns:
            {"asset": "", "data": {"Temperature": "37.0"}, "command_type": "property_down"}
        """
        return {
            "asset": "",
            "data": raw.get("params", {}),
            "command_type": "property_down",
        }

    def _parse_connect_reply(self, raw: Dict[str, Any], topic: Optional[str]) -> Dict[str, Any]:
        """
        解析设备上线回复

        Args:
            raw: {"msgid": "123456", "code": 0, "message": "success", "data": {...}}
            topic: $v1/{productKey}/{deviceSN}/sys/subdevice/connect_reply

        Returns:
            {"asset": "device1234", "data": {...}, "command_type": "connect_reply"}
        """
        data = raw.get("data", {})
        return {
            "asset": data.get("deviceSN", ""),
            "data": data,
            "command_type": "connect_reply",
            "code": raw.get("code", 0),
            "message": raw.get("message", ""),
        }

    def _parse_disconnect_reply(self, raw: Dict[str, Any], topic: Optional[str]) -> Dict[str, Any]:
        """
        解析设备下线回复

        Args:
            raw: {"msgid": "123456", "code": 0, "message": "success", "data": {...}}
            topic: $v1/{productKey}/{deviceSN}/sys/subdevice/disconnect_reply

        Returns:
            {"asset": "device1234", "data": {...}, "command_type": "disconnect_reply"}
        """
        data = raw.get("data", {})
        return {
            "asset": data.get("deviceSN", ""),
            "data": data,
            "command_type": "disconnect_reply",
            "code": raw.get("code", 0),
            "message": raw.get("message", ""),
        }

    def format_result(self, result: DownlinkResult) -> Dict[str, Any]:
        """
        客户A回复格式：{msgid, code, data}

        Args:
            result: DownlinkResult 对象

        Returns:
            客户A要求的响应格式
        """
        raw = result.raw_command or {}
        msgid = raw.get("msgid", "0")

        if result.success:
            return {
                "msgid": msgid,
                "code": 0,
                "data": {},
            }
        else:
            return {
                "msgid": msgid,
                "code": -1,
                "data": {},
            }

    # ===== 解析云平台回复 =====

    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析云平台回复

        设备上线/下线回复：
        {
            "msgid": "123456",
            "code": 0,
            "message": "success",
            "data": {"productKey": "...", "deviceSN": "..."}
        }

        写属性回复：
        {
            "msgid": "123456",
            "code": 0,
            "data": {}
        }

        Args:
            response: 云平台回复
            context: 上下文信息

        Returns:
            解析后的字典
        """
        # 先调用基类方法解析
        parsed = super().parse_response(response, context)

        # 添加额外的处理逻辑（如果需要）
        # 例如：检查code字段，记录日志等

        return parsed

    # ===== adapt_command / parse_response / to_json 使用基类默认实现 =====
