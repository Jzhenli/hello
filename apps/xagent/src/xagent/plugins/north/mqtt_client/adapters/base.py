"""MQTT适配器基类

适配器 = 客户协议，数据格式与Topic结构作为整体。
差异由适配器内部消化，Plugin和Handler保持无感知。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from ..types import CommandContext, CommandData, CommandResult, PublishPacket, ResponsePacket
from ..exceptions import DataConversionError, TopicError, CommandParseError, MQTTAdapterError

logger = logging.getLogger(__name__)


class BaseAdapter:
    """客户协议基类

    适配器 = 客户的完整MQTT协议
    数据格式 + Topic结构 + 消息流程 作为一个整体

    子类覆盖点（protected方法）：
    - _infer_upload_type: 推断上行类型
    - _build_upload_payload: 构建上行payload
    - _get_publish_topic: 获取发布topic
    - parse_command: 解析下行命令
    - format_result: 格式化命令结果
    - _build_response_payload: 构建响应payload
    - _get_reply_topic: 获取回复topic
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    # ===== 上行：一步到位 =====

    def adapt_upload(
        self,
        readings: List[Reading],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[PublishPacket]:
        """转换上行数据 → 返回发布包列表

        适配器内部通过 _infer_upload_type 推断每条 reading 的上行类型，
        按类型分组后生成对应的 PublishPacket。

        调用方只需遍历列表：for packet in packets: client.publish(...)
        不需要知道 upload_type，不需要关心 topic。

        Args:
            readings: 数据列表
            context: 上下文信息（可选，包含 timestamp、device_status_map 等）

        Returns:
            List[PublishPacket]: 发布包列表，每个包的 topic+payload 已绑定

        Raises:
            DataConversionError: 数据转换失败
        """
        if not readings:
            raise DataConversionError("readings cannot be empty")

        try:
            # 按 upload_type 分组
            groups: Dict[str, List[Reading]] = {}
            for reading in readings:
                upload_type = self._infer_upload_type(reading)
                groups.setdefault(upload_type, []).append(reading)

            # 每组生成一个 PublishPacket
            packets = []
            for upload_type, group_readings in groups.items():
                payload = self._build_upload_payload(group_readings, upload_type)
                topic = self._get_publish_topic(upload_type, readings=group_readings)
                packets.append(PublishPacket(topic=topic, payload=payload))

            return packets
        except MQTTAdapterError:
            raise
        except Exception as e:
            logger.error(f"adapt_upload error: {e}")
            raise DataConversionError(f"Failed to adapt upload data: {e}") from e

    def _infer_upload_type(self, reading: Reading) -> str:
        """推断单条reading的上行类型 - 子类可覆盖

        默认实现：始终返回 "property"
        客户A覆盖：根据 reading.device_status 推断 connect/disconnect

        注意：参数是单条 Reading，不是 List，因为每条 reading 可能属于不同类型
        """
        return "property"

    def _build_upload_payload(self, readings: List[Reading], upload_type: str) -> Dict[str, Any]:
        """构建上行payload - 子类必须覆盖"""
        # 默认实现：简单格式
        params = {}
        for reading in readings:
            for key, value in reading.data.items():
                params[key] = value

        return {
            "asset": readings[0].asset,
            "timestamp": readings[0].timestamp,
            "data": params,
        }

    def _get_publish_topic(
        self,
        upload_type: str,
        readings: Optional[List[Reading]] = None,
    ) -> str:
        """获取发布topic - 配置驱动，子类可覆盖

        Args:
            upload_type: 上行类型（property, connect, disconnect 等）
            readings: 当前要发送的数据（用于提取运行时变量）

        Returns:
            格式化后的 topic 字符串
        """
        templates = self._config.get("topic_templates", {})
        template_key = self._upload_type_to_template_key(upload_type)

        if template_key not in templates:
            raise TopicError(f"No topic template for upload_type '{upload_type}' (key: '{template_key}')")

        try:
            return templates[template_key].format(**self._topic_context(upload_type, readings))
        except KeyError as e:
            raise TopicError(f"Topic template '{template_key}' has missing placeholder: {e}") from e

    def _upload_type_to_template_key(self, upload_type: str) -> str:
        """upload_type → 模板key的映射，支持配置驱动

        优先从 upload_type_map 配置读取映射，
        未配置时默认：property → property_up, connect → connect_up
        """
        mapping = self._config.get("upload_type_map", {})
        return mapping.get(upload_type, f"{upload_type}_up")

    def _topic_context(
        self,
        upload_type: str,
        readings: Optional[List[Reading]] = None,
    ) -> Dict[str, str]:
        """生成topic模板的填充上下文

        Args:
            upload_type: 上行类型
            readings: 当前要发送的数据（子类可从中提取运行时变量）

        Returns:
            包含配置值的上下文字典

        注意：
            基类只返回配置中的静态值。
            子类应覆盖此方法添加协议特有的运行时变量。

        Example:
            # 客户A子类覆盖:
            def _topic_context(self, upload_type, readings):
                context = super()._topic_context(upload_type, readings)
                if readings:
                    context["deviceSN"] = readings[0].asset
                return context
        """
        return {
            k: str(v) for k, v in self._config.items()
            if isinstance(v, (str, int, float))
        }

    # ===== 下行：解析 + 响应 =====

    def parse_command(self, raw: Dict[str, Any], context: CommandContext) -> CommandData:
        """解析下行命令 - 子类可覆盖

        Args:
            raw: 原始命令数据
            context: 命令上下文（含topic_type等信息）

        Returns:
            CommandData: 解析后的命令，含 requires_reply 标志

        Raises:
            CommandParseError: 命令解析失败
        """
        asset = raw.get("asset")
        if asset is None:
            logger.warning("Command missing 'asset' field, using empty string")
            asset = ""

        return CommandData(
            asset=asset,
            data=raw.get("data", {}),
        )

    def format_result(self, result: CommandResult, context: CommandContext) -> ResponsePacket:
        """格式化命令结果 → 返回完整的响应包

        调用方只需要：client.publish(packet.topic, packet.payload)
        不需要再问"响应该发到哪个topic"

        Args:
            result: 命令执行结果
            context: 命令上下文

        Returns:
            ResponsePacket: 自包含的响应单元
        """
        payload = self._build_response_payload(result, context)
        topic = self._get_reply_topic(context.topic)
        return ResponsePacket(topic=topic, payload=payload)

    def _build_response_payload(self, result: CommandResult, context: CommandContext) -> Dict[str, Any]:
        """构建响应payload - 子类可覆盖"""
        response = {"timestamp": context.raw_command.get("timestamp", 0)}

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

    def _get_reply_topic(self, command_topic: str) -> str:
        """获取回复topic - 配置驱动，子类可覆盖"""
        rule = self._config.get("reply_topic_rule", "suffix_result")
        if rule == "suffix_reply":
            return command_topic + "_reply"
        elif rule == "replace_down_with_reply":
            return command_topic.replace("/down", "/reply")
        return f"{command_topic}/result"

    # ===== Topic管理 =====

    def get_subscribe_topics(self) -> List[str]:
        """获取需要订阅的Topic列表 - 配置驱动

        注意：订阅 topic 通常使用通配符，子类应在 _topic_context 中处理。
        """
        templates = self._config.get("topic_templates", {})
        subscribe_types = self._config.get("subscribe_types", [])

        topics = []
        for topic_type in subscribe_types:
            if topic_type in templates:
                try:
                    topic = templates[topic_type].format(**self._topic_context(topic_type, readings=None))
                    topics.append(topic)
                except KeyError as e:
                    logger.warning(f"Topic template '{topic_type}' has missing placeholders: {e}")
            else:
                logger.warning(f"Subscribe type '{topic_type}' not found in topic_templates")

        return topics

    def parse_topic_type(self, topic: str) -> str:
        """解析topic类型 - 配置驱动"""
        rules = self._config.get("topic_type_rules", {})
        for pattern, topic_type in rules.items():
            if pattern in topic:
                return topic_type

        # 默认规则
        if "/sys/property/down" in topic:
            return "property_down"
        elif "/sys/subdevice/connect_reply" in topic:
            return "connect_reply"
        elif "/sys/subdevice/disconnect_reply" in topic:
            return "disconnect_reply"
        elif "/command" in topic:
            return "command"
        elif "/cmd" in topic:
            return "cmd"

        return "unknown"

    # ===== 工具方法 =====

    def to_json(self, payload: Any) -> str:
        """序列化payload为JSON字符串"""
        return json.dumps(payload, ensure_ascii=False)
