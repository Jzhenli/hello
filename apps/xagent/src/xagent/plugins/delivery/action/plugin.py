"""Action Delivery Plugin

规则触发后自动执行设备控制命令（如打开开关、写入设定值）。
通过 CommandExecutor 下发 write_setpoint / execute_operation 到南向插件。
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from xagent.xcore.rule_engine import (
    DeliveryPlugin,
    PluginMetadata,
    Notification,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)

_command_executor_ref: Optional[Any] = None


def set_command_executor(executor: Any) -> None:
    """设置 CommandExecutor 实例引用（由 Gateway 初始化时调用）"""
    global _command_executor_ref
    _command_executor_ref = executor


def _get_command_executor():
    return _command_executor_ref


class ActionDeliveryPlugin(DeliveryPlugin):
    """动作执行交付插件

    规则触发后自动执行设备控制命令。
    通过系统的 CommandExecutor 将控制命令下发到南向插件。

    配置项:
        target_service: 目标南向插件名称 (如 "modbus_tcp")
        target_asset: 目标设备资产名 (如 "light_001")
        operation: 操作类型 ("write_setpoint" | "execute_operation")
        point: 写入的点位名 (write_setpoint 时必填)
        value: 写入的值 (write_setpoint 时必填)
        parameters: 操作参数 (execute_operation 时使用)
        delay: 延迟执行秒数 (默认 0)
    """

    __plugin_name__ = "action"
    __plugin_type__ = "rule_engine.delivery"

    def __init__(self):
        super().__init__()
        self._target_service: str = ""
        self._target_asset: str = ""
        self._operation: str = "write_setpoint"
        self._point: str = ""
        self._value: Any = None
        self._parameters: Dict[str, Any] = {}
        self._delay: float = 0

    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="action",
            version="1.0.0",
            description="规则触发后自动执行设备控制命令",
            author="XAgent Team",
            plugin_type="rule_engine.delivery",
            icon="⚡",
            color="#27ae60",
            category="action",
            display_name="设备动作",
        )

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_service": {
                    "type": "string",
                    "title": "目标服务",
                    "description": "南向插件名称 (如 modbus_tcp, bacnet)"
                },
                "target_asset": {
                    "type": "string",
                    "title": "目标设备",
                    "description": "设备资产名 (如 light_001)"
                },
                "operation": {
                    "type": "string",
                    "title": "操作类型",
                    "enum": ["write_setpoint", "execute_operation"],
                    "default": "write_setpoint"
                },
                "point": {
                    "type": "string",
                    "title": "点位名",
                    "description": "写入的点位名 (write_setpoint 时必填)"
                },
                "value": {
                    "title": "写入值",
                    "description": "写入的值 (write_setpoint 时必填)"
                },
                "parameters": {
                    "type": "object",
                    "title": "操作参数",
                    "description": "execute_operation 时的参数"
                },
                "delay": {
                    "type": "number",
                    "title": "延迟执行(秒)",
                    "default": 0,
                    "minimum": 0
                }
            },
            "required": ["target_service", "target_asset"]
        }

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._target_service = config.get("target_service", "")
        self._target_asset = config.get("target_asset", "")
        self._operation = config.get("operation", "write_setpoint")
        self._point = config.get("point", "")
        self._value = config.get("value")
        self._parameters = config.get("parameters", {})
        self._delay = config.get("delay", 0)

        if not self._target_service:
            raise ValueError("target_service is required")
        if not self._target_asset:
            raise ValueError("target_asset is required")

        logger.info(
            f"Action delivery initialized: "
            f"{self._target_service}.{self._target_asset} "
            f"-> {self._operation}"
        )

    async def deliver(self, notification: Notification) -> DeliveryResult:
        import asyncio

        executor = _get_command_executor()
        if executor is None:
            logger.error("CommandExecutor not available")
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error="CommandExecutor not available"
            )

        if self._delay > 0:
            logger.info(f"Action delayed {self._delay}s before execution")
            await asyncio.sleep(self._delay)

        command_id = f"rule-{notification.rule_id}-{uuid.uuid4().hex[:8]}"

        target_asset = self._target_asset
        operation = self._operation
        parameters = dict(self._parameters)

        if notification.metadata and "rule_config" in notification.metadata:
            rule_config = notification.metadata["rule_config"]
            action_config = rule_config.get("action", {})
            if action_config:
                target_asset = action_config.get("target_asset", target_asset)
                operation = action_config.get("operation", operation)
                if "parameters" in action_config:
                    parameters.update(action_config["parameters"])

        if operation == "write_setpoint":
            point = self._point
            value = self._value
            if not point:
                return DeliveryResult(
                    status=DeliveryStatus.FAILED,
                    success=False,
                    error="Point name is required for write_setpoint"
                )
            parameters = {"point": point, "value": value}
        else:
            if not parameters:
                parameters = {"operation": operation}

        try:
            success = await executor.submit_command(
                command_id=command_id,
                target_service=self._target_service,
                target_asset=target_asset,
                operation=operation,
                parameters=parameters,
            )

            if success:
                logger.info(
                    f"Action command submitted: {command_id} -> "
                    f"{self._target_service}.{target_asset}.{operation}"
                )
                return DeliveryResult(
                    status=DeliveryStatus.SUCCESS,
                    success=True,
                    message=f"Command {command_id} submitted successfully",
                    delivered_at=time.time(),
                )
            else:
                return DeliveryResult(
                    status=DeliveryStatus.FAILED,
                    success=False,
                    error="Command submission failed"
                )

        except Exception as e:
            logger.error(f"Action delivery failed: {e}")
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error=str(e)
            )

    async def test_connection(self) -> bool:
        executor = _get_command_executor()
        return executor is not None

    async def shutdown(self) -> None:
        logger.info("Action delivery plugin shutdown")
