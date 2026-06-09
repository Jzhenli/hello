"""MQTT Downlink Handler - Handles incoming commands and publishes results

Downlink: External system → XAgent (commands, write requests)
Uplink: XAgent → External system (data upload, status updates)
"""

import json
import logging
from typing import Any, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus, Event, EventType

from .types import CommandContext, CommandData, CommandResult, ResponsePacket
from .exceptions import CommandParseError, MQTTAdapterError

if TYPE_CHECKING:
    import aiomqtt

logger = logging.getLogger(__name__)


class DownlinkHandler:
    """
    MQTT Downlink Handler

    Responsibilities:
    - Parse incoming MQTT messages via adapter
    - Publish commands to EventBus
    - Format and return response packets

    Does NOT handle:
    - MQTT connection management
    - Topic subscription
    - Lifecycle management
    - Topic type dispatching (handled by adapter.parse_command)
    """

    def __init__(
        self,
        event_bus: EventBus,
        adapter: Any,
        command_timeout: float = 30.0,
    ):
        self._event_bus = event_bus
        self._adapter = adapter
        self._command_timeout = command_timeout

    async def handle_message(
        self,
        message: "aiomqtt.Message",
        topic: str,
        topic_type: str,
    ) -> Optional[ResponsePacket]:
        """Handle incoming MQTT message

        Args:
            message: MQTT message
            topic: Message topic (already parsed by Plugin)
            topic_type: Topic type (already parsed by Plugin via adapter)

        Returns:
            ResponsePacket if reply is needed, None otherwise
        """
        try:
            payload = message.payload.decode("utf-8")
            logger.info(f"Received command on topic {topic}: {payload}")

            raw = json.loads(payload)

            # 构建命令上下文
            context = CommandContext(
                raw_command=raw,
                topic=topic,
                topic_type=topic_type,
            )

            # 适配器解析命令（内部根据topic_type处理差异）
            command = self._adapter.parse_command(raw, context)

            # 发布事件
            await self._event_bus.publish(Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={"asset": command.asset, "data": command.data}
            ))

            logger.info(f"Command executed: type={command.command_type}, asset={command.asset}")

            # 只有需要回复的命令才生成响应
            if not command.requires_reply:
                return None

            # 等待命令执行结果
            result = await self._wait_for_result(command)

            # 适配器格式化响应（内部决定reply topic和payload格式）
            return self._adapter.format_result(result, context)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON command: {e}")
            return None

        except CommandParseError as e:
            logger.error(f"Command parse error: {e}")
            return None

        except MQTTAdapterError as e:
            logger.error(f"Adapter error: {e}")
            return None

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            return None

    async def _wait_for_result(self, command: CommandData) -> CommandResult:
        """等待命令执行结果

        当前简化实现：直接返回成功。
        未来应通过 EventBus 订阅 WRITE_COMPLETED 事件等待实际执行结果。
        """
        return CommandResult(
            success=True,
            asset=command.asset,
            data=command.data,
        )
