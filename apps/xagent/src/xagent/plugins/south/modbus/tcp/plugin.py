"""Modbus TCP South Plugin - TCP transport implementation"""

import logging
from typing import Any, Dict, List

from ..base import ModbusBasePlugin

logger = logging.getLogger(__name__)

DEFAULT_PORT = 502

_AsyncModbusTcpClient = None
_MODBUS_TCP_AVAILABLE = None


def _check_modbus_tcp_available():
    global _MODBUS_TCP_AVAILABLE, _AsyncModbusTcpClient

    if _MODBUS_TCP_AVAILABLE is not None:
        return _MODBUS_TCP_AVAILABLE

    try:
        from pymodbus.client import AsyncModbusTcpClient
        _AsyncModbusTcpClient = AsyncModbusTcpClient
        _MODBUS_TCP_AVAILABLE = True
    except ImportError:
        _MODBUS_TCP_AVAILABLE = False
        logger.warning("pymodbus not installed, Modbus TCP plugin will not work")
    return _MODBUS_TCP_AVAILABLE


class ModbusTcpPlugin(ModbusBasePlugin):
    """
    Modbus TCP 南向插件

    仅实现 TCP 传输层专有逻辑，所有协议逻辑由 ModbusBasePlugin 提供。
    """

    __plugin_name__ = "modbus_tcp"

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "host": {"type": "string", "default": "127.0.0.1", "title": "主机地址"},
                "port": {"type": "integer", "default": 502, "title": "端口号"},
                "slave_id": {"type": "integer", "default": 1, "title": "从站ID"},
                "timeout": {"type": "number", "default": 3, "title": "超时时间(秒)"},
                "reconnect_interval": {"type": "number", "default": 5, "title": "重连间隔(秒)"},
                "heartbeat_address": {"type": ["integer", "null"], "default": None, "title": "心跳地址"},
                "heartbeat_timeout": {"type": "number", "default": 1.5, "title": "心跳超时(秒)"},
                "max_gap": {"type": "integer", "default": 5, "title": "最大间隔"},
            },
        }

    @classmethod
    def capabilities(cls) -> List[str]:
        return [
            "read_coils",
            "read_discrete_inputs",
            "read_holding_registers",
            "read_input_registers",
            "write_single_coil",
            "write_single_register",
        ]

    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: Any):
        self._host = config.get("host", "127.0.0.1")
        self._port = config.get("port", DEFAULT_PORT)
        super().__init__(config, storage, event_bus)

    @classmethod
    def _check_modbus_available(cls) -> bool:
        return _check_modbus_tcp_available()

    def _create_client(self) -> Any:
        return _AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=self._timeout,
            retries=2,
            reconnect_delay=1,
            reconnect_delay_max=10,
        )

    async def _connect_client(self, client: Any) -> None:
        await client.connect()

    async def _disconnect_client(self, client: Any) -> None:
        client.close()

    def _is_client_connected(self, client: Any) -> bool:
        return client.connected

    def _get_connection_info(self) -> Dict[str, Any]:
        return {
            "host": self._host,
            "port": self._port,
        }
