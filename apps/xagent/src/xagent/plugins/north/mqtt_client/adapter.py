"""MQTT Adapter - 基类 + 标准实现 + 共享类型"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from xagent.xcore.storage.interface import Reading

logger = logging.getLogger(__name__)


# ===== 类型协议定义（可选，用于IDE类型检查） =====
@runtime_checkable
class MQTTAdapterProtocol(Protocol):
    """
    MQTT适配器协议 - 用于IDE类型提示和静态检查

    注意：这是可选的类型提示，不强制实现。
    鸭子类型保证运行时兼容性。
    """
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any: ...
    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]: ...
    def format_result(self, result: "DownlinkResult") -> Dict[str, Any]: ...
    def to_json(self, payload: Any) -> str: ...


# ===== 异常处理装饰器 =====
def _handle_adapter_errors(func):
    """
    适配器方法异常处理装饰器

    用法：
        @_handle_adapter_errors
        def adapt_upload(self, readings, context):
            # 无需try/except，装饰器会处理
            ...

    注意：adapt_upload基类已内置异常处理，子类覆盖时可选使用此装饰器
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__} error: {e}")
            return None
    return wrapper


# ===== 共享类型定义 =====
@dataclass
class DownlinkResult:
    """
    下行命令执行结果

    Attributes:
        success: 执行是否成功
        asset: 资产/设备ID
        data: 命令数据
        error: 错误信息
        raw_command: 原始命令（供format_result使用）
    """
    success: bool
    asset: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_command: Optional[Dict[str, Any]] = None


# ===== 适配器基类 =====
class MQTTAdapterBase:
    """
    MQTT 适配器基类

    提供所有方法的默认实现（等同于当前 Standard 格式），
    客户适配器只需覆盖与默认格式不同的方法。

    设计要点：
    - 使用鸭子类型，不强制Protocol（轻量级项目足够）
    - 异常处理统一在基类中，子类只需关注业务逻辑
    - 保留DataAdapter Protocol兼容性（adapt_command、parse_response）
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器

        Args:
            config: 适配器配置字典
        """
        self.config = config or {}

    # ===== 上行：数据上传 =====

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """
        适配上传数据 - 默认实现：单条/批量格式

        Args:
            readings: Reading 对象列表
            context: 上下文信息（包含 device_status_map 等）

        Returns:
            适配后的数据，单条返回字典，多条返回批量格式
            失败返回 None
        """
        try:
            if not readings:
                return None

            if len(readings) == 1:
                return self._adapt_single_reading(readings[0], context)
            else:
                return {
                    "count": len(readings),
                    "readings": [self._adapt_single_reading(r, context) for r in readings],
                    "timestamp": self._format_timestamp(readings[0].timestamp),
                }
        except Exception as e:
            logger.error(f"adapt_upload error: {e}")
            return None

    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        单条数据适配 - 子类可覆盖

        Args:
            reading: Reading 对象
            context: 上下文信息

        Returns:
            适配后的字典
        """
        context = context or {}
        device_status_map = context.get("device_status_map", {})

        payload = {
            "asset": reading.asset,
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": reading.data,
        }

        # 添加设备状态
        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status

        return payload

    def _format_timestamp(self, timestamp: float) -> Any:
        """
        时间戳格式化 - 子类可覆盖以支持不同格式

        Args:
            timestamp: Unix 时间戳

        Returns:
            格式化后的时间戳（默认返回原始值）
        """
        return timestamp

    # ===== Topic管理（适配器提供客户特定的Topic信息） =====

    def get_topic_templates(self) -> Dict[str, str]:
        """
        获取Topic模板（适配器可覆盖以提供客户特定的topic）

        优先级：
        1. 从adapter_config中读取topic_templates（最高优先级）
        2. 使用默认的topic模板

        Returns:
            Topic模板字典，key为topic类型，value为topic模板
        """
        # 优先从配置中读取
        if "topic_templates" in self.config:
            return self.config["topic_templates"]
        
        # 默认实现：标准topic模板（客户A格式）
        return {
            # 上行：网关→云平台
            "property_up": "$v1/{productKey}/{deviceSN}/sys/property/up",
            "connect": "$v1/{productKey}/{deviceSN}/sys/subdevice/connect",
            "disconnect": "$v1/{productKey}/{deviceSN}/sys/subdevice/disconnect",
            "property_down_reply": "$v1/{productKey}/{deviceSN}/sys/property/down_reply",
            
            # 下行：云平台→网关
            "property_down": "$v1/{productKey}/{deviceSN}/sys/property/down",
            "connect_reply": "$v1/{productKey}/{deviceSN}/sys/subdevice/connect_reply",
            "disconnect_reply": "$v1/{productKey}/{deviceSN}/sys/subdevice/disconnect_reply",
        }
    
    def get_subscribe_topic_types(self) -> List[str]:
        """
        获取需要订阅的Topic类型列表

        优先级：
        1. 从adapter_config中读取subscribe_topic_types
        2. 使用默认值

        Returns:
            Topic类型列表
        """
        # 优先从配置中读取
        if "subscribe_topic_types" in self.config:
            return self.config["subscribe_topic_types"]
        
        # 默认实现：订阅property_down
        return ["property_down"]
    
    def get_subscribe_topics(self, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        获取需要订阅的Topic列表（适配器可覆盖以提供客户特定的生成逻辑）

        Args:
            context: 上下文信息（可选），如果不提供则使用self.config

        Returns:
            需要订阅的Topic列表
        """
        # 如果没有提供context，使用self.config作为context
        if context is None:
            context = self.config
        
        # 获取topic模板和订阅类型
        templates = self.get_topic_templates()
        subscribe_types = self.get_subscribe_topic_types()
        
        # 生成topic列表
        topics = []
        for topic_type in subscribe_types:
            if topic_type in templates:
                try:
                    topic = templates[topic_type].format(**context)
                    topics.append(topic)
                except KeyError:
                    # 模板中的占位符在context中不存在，跳过
                    logger.warning(f"Topic template '{topic_type}' has missing placeholders in context")
                    continue
        
        return topics
    
    def get_publish_topic(self, publish_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        获取发布Topic（适配器可覆盖以提供客户特定的生成逻辑）

        Args:
            publish_type: 发布类型（property, connect, disconnect）
            context: 上下文信息（可选），如果不提供则使用self.config

        Returns:
            发布Topic
        """
        # 如果没有提供context，使用self.config作为context
        if context is None:
            context = self.config
        
        # 获取topic模板
        templates = self.get_topic_templates()
        
        # 根据发布类型选择模板
        topic_type_map = {
            "property": "property_up",
            "connect": "connect",
            "disconnect": "disconnect",
        }
        
        topic_type = topic_type_map.get(publish_type, "property_up")
        
        if topic_type in templates:
            try:
                return templates[topic_type].format(**context)
            except KeyError as e:
                logger.warning(f"Topic template '{topic_type}' has missing placeholder: {e}")
                return ""
        
        return ""
    
    def get_reply_topic(self, command_topic: str) -> str:
        """
        根据命令Topic生成回复Topic（适配器可覆盖以提供客户特定的规则）

        优先级：
        1. 从adapter_config中读取reply_topic_rule
        2. 使用默认规则

        Args:
            command_topic: 命令Topic

        Returns:
            回复Topic
        """
        # 优先从配置中读取规则
        if "reply_topic_rule" in self.config:
            rule = self.config["reply_topic_rule"]
            if rule == "suffix_reply":
                # 客户A规则：/down → /down_reply
                return command_topic + "_reply"
            elif rule == "suffix_result":
                # 默认规则：/down → /down/result
                return f"{command_topic}/result"
            elif rule == "replace_down_with_reply":
                # 替换规则：/down → /reply
                return command_topic.replace("/down", "/reply")
        
        # 默认规则：在命令topic后加"/result"
        return f"{command_topic}/result"
    
    def parse_topic_type(self, topic: str) -> str:
        """
        解析Topic类型（适配器可覆盖以提供客户特定的解析逻辑）

        优先级：
        1. 从adapter_config中读取topic_type_rules
        2. 使用默认解析逻辑

        Args:
            topic: MQTT Topic

        Returns:
            Topic类型
        """
        # 优先从配置中读取规则
        if "topic_type_rules" in self.config:
            rules = self.config["topic_type_rules"]
            for pattern, topic_type in rules.items():
                if pattern in topic:
                    return topic_type
            return "unknown"
        
        # 默认实现：标准topic解析（客户A格式）
        if "/sys/property/down" in topic:
            return "property_down"
        elif "/sys/subdevice/connect_reply" in topic:
            return "connect_reply"
        elif "/sys/subdevice/disconnect_reply" in topic:
            return "disconnect_reply"
        else:
            return "unknown"

    # ===== 下行：命令解析与响应 =====

    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析下行命令 - 将客户特有的命令格式转换为统一内部格式

        Args:
            raw: 客户下发的原始命令字典

        Returns:
            统一格式: {"asset": str, "data": Dict[str, Any]}
        """
        return {
            "asset": raw.get("asset", ""),
            "data": raw.get("data", {}),
        }

    def format_result(self, result: DownlinkResult) -> Dict[str, Any]:
        """
        格式化命令执行结果 - 将内部结果转换为客户要求的响应格式

        Args:
            result: DownlinkResult 对象

        Returns:
            客户要求的响应字典
        """
        # 使用当前时间戳，确保响应始终包含有效的时间信息
        response = {"timestamp": self._format_timestamp(time.time())}

        if result.success:
            response["status"] = "success"
            if result.asset:
                response["asset"] = result.asset
            if result.data:
                response["data"] = result.data
        else:
            response["status"] = "error"
            if result.error:
                response["error"] = result.error

        return response

    # ===== 工具方法 =====

    def to_json(self, payload: Any) -> str:
        """
        序列化为 JSON 字符串

        Args:
            payload: 待序列化的数据

        Returns:
            JSON 字符串
        """
        return json.dumps(payload, ensure_ascii=False)

    # ===== DataAdapter Protocol 兼容方法 =====

    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        适配下行命令数据（保持 DataAdapter Protocol 兼容）

        注意：此方法用于上行方向的命令构造，不应用于下行解析场景

        Args:
            command_data: 命令数据
            context: 上下文信息

        Returns:
            适配后的命令数据
        """
        return {
            "asset": command_data.get("asset", ""),
            "data": command_data.get("data", {}),
            "timestamp": context.get("timestamp"),
        }

    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析响应数据（保持 DataAdapter Protocol 兼容）

        Args:
            response: 原始响应（dict、bytes、str 或其他类型）
            context: 上下文信息

        Returns:
            解析后的字典
        """
        if isinstance(response, dict):
            return response

        if isinstance(response, bytes):
            try:
                return json.loads(response.decode("utf-8"))
            except json.JSONDecodeError:
                return {"raw": response.decode("utf-8")}

        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"raw": response}

        return {"raw": str(response)}
