"""MQTT Downlink Handler - Handles incoming commands and publishes results

Downlink: External system → XAgent (commands, write requests)
Uplink: XAgent → External system (data upload, status updates)
"""

import json
import logging
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus, Event, EventType
from .adapter import DownlinkResult  # 从 adapter.py 导入

if TYPE_CHECKING:
    import aiomqtt

logger = logging.getLogger(__name__)


class DownlinkHandler:
    """
    MQTT Downlink Handler
    
    Responsibilities:
    - Parse incoming MQTT messages
    - Dispatch messages based on topic type
    - Publish commands to EventBus
    - Send response/result back to MQTT
    
    Does NOT handle:
    - MQTT connection management
    - Topic subscription
    - Lifecycle management
    
    Usage:
        handler = DownlinkHandler(event_bus, adapter, plugin)
        
        # Handle incoming message
        result = await handler.handle_message(message, publish_callback)
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        adapter: Any,
        plugin: Any = None,
        command_timeout: float = 30.0
    ):
        self._event_bus = event_bus
        self._adapter = adapter
        self._plugin = plugin
        self._command_timeout = command_timeout
    
    async def handle_message(
        self,
        message: "aiomqtt.Message",
        publish_callback: Optional[Callable[[str, str], None]] = None,
        result_topic: Optional[str] = None
    ) -> DownlinkResult:
        """Handle incoming MQTT message

        Args:
            message: MQTT message
            publish_callback: Async callback for publishing result
            result_topic: Topic for publishing result

        Returns:
            DownlinkResult with execution status
        """
        try:
            payload = message.payload.decode("utf-8")
            topic = str(message.topic)
            logger.info(f"Received command on topic {topic}: {payload}")

            command = json.loads(payload)

            # 根据topic类型分发消息
            if self._plugin:
                topic_type = self._plugin.parse_topic_type(topic)
                result = await self._dispatch_by_topic_type(topic_type, command, topic)
            else:
                # 向后兼容：没有plugin时，直接解析命令
                result = await self._handle_property_down(command, topic)

            if publish_callback and result_topic:
                await self._publish_result(
                    publish_callback,
                    result_topic,
                    result
                )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON command: {e}")
            result = DownlinkResult(success=False, error=f"Invalid JSON: {str(e)}")

            if publish_callback and result_topic:
                await self._publish_result(publish_callback, result_topic, result)

            return result

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            result = DownlinkResult(success=False, error=str(e))

            if publish_callback and result_topic:
                await self._publish_result(publish_callback, result_topic, result)

            return result
    
    async def _dispatch_by_topic_type(
        self,
        topic_type: str,
        command: Dict[str, Any],
        topic: str
    ) -> DownlinkResult:
        """
        根据topic类型分发消息
        
        Args:
            topic_type: Topic类型
            command: 命令数据
            topic: 原始topic
        
        Returns:
            DownlinkResult
        """
        if topic_type == "property_down":
            # 设置设备属性
            return await self._handle_property_down(command, topic)
        elif topic_type == "connect_reply":
            # 设备上线回复
            return await self._handle_connect_reply(command, topic)
        elif topic_type == "disconnect_reply":
            # 设备下线回复
            return await self._handle_disconnect_reply(command, topic)
        else:
            # 未知类型，尝试作为普通命令处理
            logger.warning(f"Unknown topic type: {topic_type}, treating as property_down")
            return await self._handle_property_down(command, topic)
    
    async def _handle_property_down(
        self,
        command: Dict[str, Any],
        topic: str
    ) -> DownlinkResult:
        """
        处理设置设备属性命令
        
        Args:
            command: 命令数据
            topic: Topic
        
        Returns:
            DownlinkResult
        """
        # 委托适配器解析命令
        parsed = self._adapter.parse_command(command)
        asset = parsed.get("asset")
        data = parsed.get("data")

        if not asset or not data:
            logger.warning("Invalid command: missing asset or data after parsing")
            return DownlinkResult(
                success=False,
                error="Invalid command: missing asset or data",
                raw_command=command,
            )

        # 发布到EventBus
        await self._event_bus.publish(Event(
            event_type=EventType.COMMAND_RECEIVED,
            data={"asset": asset, "data": data}
        ))

        logger.info(f"Property down command executed successfully for asset {asset}")
        return DownlinkResult(
            success=True,
            asset=asset,
            data=data,
            raw_command=command,
        )
    
    async def _handle_connect_reply(
        self,
        command: Dict[str, Any],
        topic: str
    ) -> DownlinkResult:
        """
        处理设备上线回复
        
        Args:
            command: 回复数据
            topic: Topic
        
        Returns:
            DownlinkResult
        """
        # 委托适配器解析回复
        parsed = self._adapter.parse_response(command, {})
        
        code = command.get("code", -1)
        message = command.get("message", "")
        
        if code == 0:
            logger.info(f"Device connect success: {message}")
            return DownlinkResult(
                success=True,
                asset=parsed.get("asset", ""),
                data=parsed.get("data", {}),
                raw_command=command,
            )
        else:
            logger.warning(f"Device connect failed: {message}")
            return DownlinkResult(
                success=False,
                error=message,
                raw_command=command,
            )
    
    async def _handle_disconnect_reply(
        self,
        command: Dict[str, Any],
        topic: str
    ) -> DownlinkResult:
        """
        处理设备下线回复
        
        Args:
            command: 回复数据
            topic: Topic
        
        Returns:
            DownlinkResult
        """
        # 委托适配器解析回复
        parsed = self._adapter.parse_response(command, {})
        
        code = command.get("code", -1)
        message = command.get("message", "")
        
        if code == 0:
            logger.info(f"Device disconnect success: {message}")
            return DownlinkResult(
                success=True,
                asset=parsed.get("asset", ""),
                data=parsed.get("data", {}),
                raw_command=command,
            )
        else:
            logger.warning(f"Device disconnect failed: {message}")
            return DownlinkResult(
                success=False,
                error=message,
                raw_command=command,
            )
    
    async def _publish_result(
        self,
        publish_callback: Callable[[str, str], None],
        result_topic: str,
        result: DownlinkResult
    ) -> None:
        """Publish command execution result"""
        try:
            # 委托适配器格式化结果
            response = self._adapter.format_result(result)
            payload = json.dumps(response, ensure_ascii=False)
            await publish_callback(result_topic, payload)

            logger.debug(f"Published result to {result_topic}")

        except Exception as e:
            logger.error(f"Failed to publish command result: {e}")
