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
        self._sn_prefix = self.config.get("sn_prefix", "")
        # 用于生成递增的msgid（可选，也可以用随机数）
        self._msgid_counter = 0

    # ===== Topic管理（覆盖基类以提供客户A特定的topic） =====

    def get_subscribe_topic_types(self) -> List[str]:
        """
        客户A需要订阅的Topic类型

        Returns:
            ["property_down", "connect_reply", "disconnect_reply"]
        """
        # 优先从配置中读取
        if "subscribe_topic_types" in self.config:
            return self.config["subscribe_topic_types"]
        
        # 客户A默认订阅三种类型
        return ["property_down", "connect_reply", "disconnect_reply"]

    def get_reply_topic(self, command_topic: str) -> str:
        """
        客户A的回复Topic规则：在命令topic后加"_reply"

        Args:
            command_topic: 命令Topic

        Returns:
            回复Topic
        """
        # 优先从配置中读取规则
        if "reply_topic_rule" in self.config:
            rule = self.config["reply_topic_rule"]
            if rule == "suffix_reply":
                return command_topic + "_reply"
            elif rule == "suffix_result":
                return f"{command_topic}/result"
            elif rule == "replace_down_with_reply":
                return command_topic.replace("/down", "/reply")
        
        # 客户A默认规则：/down → /down_reply
        if command_topic.endswith("/down"):
            return command_topic + "_reply"
        else:
            return f"{command_topic}/result"

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

    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        客户A下行命令解析：{msgid, params} → {asset, data}

        Args:
            raw: 客户A的写属性格式 {"msgid": "123456", "params": {"Temperature": "37.0"}}

        Returns:
            统一内部格式 {"asset": "", "data": {"Temperature": "37.0"}}
        """
        return {
            "asset": "",
            "data": raw.get("params", {}),
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
