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
    - Publish commands to EventBus
    - Send response/result back to MQTT
    
    Does NOT handle:
    - MQTT connection management
    - Topic subscription
    - Lifecycle management
    
    Usage:
        handler = DownlinkHandler(event_bus, adapter)
        
        # Handle incoming message
        result = await handler.handle_message(message, publish_callback)
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        adapter: Any,
        command_timeout: float = 30.0
    ):
        self._event_bus = event_bus
        self._adapter = adapter
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
            topic = str(message.topic)  # 获取topic
            logger.info(f"Received command on topic {topic}: {payload}")

            command = json.loads(payload)

            # 委托适配器解析命令格式（传递topic）
            parsed = self._adapter.parse_command(command, topic)
            asset = parsed.get("asset")
            data = parsed.get("data")

            if not asset or not data:
                logger.warning("Invalid command: missing asset or data after parsing")
                result = DownlinkResult(
                    success=False,
                    error="Invalid command: missing asset or data",
                    raw_command=command,  # 保留原始命令
                )
            else:
                # 直接使用 parse_command 的结果发布到 EventBus
                await self._event_bus.publish(Event(
                    event_type=EventType.COMMAND_RECEIVED,
                    data={"asset": asset, "data": data}
                ))

                result = DownlinkResult(
                    success=True,
                    asset=asset,
                    data=data,
                    raw_command=command,  # 保留原始命令
                )
                logger.info(f"Command executed successfully for asset {asset}")

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
