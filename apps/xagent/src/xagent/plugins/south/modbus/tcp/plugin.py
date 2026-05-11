"""Modbus TCP South Plugin - TCP transport implementation"""

import logging
from typing import Any, Dict

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
