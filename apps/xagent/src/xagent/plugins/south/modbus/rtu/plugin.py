"""Modbus RTU South Plugin - Serial/RTU transport implementation"""

import logging
from typing import Any, Dict

from ..base import ModbusBasePlugin

logger = logging.getLogger(__name__)

_AsyncModbusSerialClient = None
_MODBUS_RTU_AVAILABLE = None

DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8


def _check_modbus_rtu_available():
    global _MODBUS_RTU_AVAILABLE, _AsyncModbusSerialClient

    if _MODBUS_RTU_AVAILABLE is not None:
        return _MODBUS_RTU_AVAILABLE

    try:
        import serial
    except ImportError:
        _MODBUS_RTU_AVAILABLE = False
        logger.warning("pyserial not installed, Modbus RTU plugin will not work. Install with: pip install pyserial")
        return _MODBUS_RTU_AVAILABLE

    try:
        from pymodbus.client import AsyncModbusSerialClient
        _AsyncModbusSerialClient = AsyncModbusSerialClient
        _MODBUS_RTU_AVAILABLE = True
    except ImportError:
        _MODBUS_RTU_AVAILABLE = False
        logger.warning("pymodbus not installed, Modbus RTU plugin will not work")
    return _MODBUS_RTU_AVAILABLE


class ModbusRtuPlugin(ModbusBasePlugin):
    """
    Modbus RTU 南向插件

    仅实现 RTU 串口传输层专有逻辑，所有协议逻辑由 ModbusBasePlugin 提供。

    RTU 专有配置：
    - serial_port: 串口设备路径 (默认 /dev/ttyUSB0)
    - baudrate: 波特率 (默认 9600)
    - parity: 校验位 N/E/O (默认 N)
    - stopbits: 停止位 1/2 (默认 1)
    - bytesize: 数据位 7/8 (默认 8)
    """

    __plugin_name__ = "modbus_rtu"

    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: Any):
        self._serial_port = config.get("serial_port", DEFAULT_SERIAL_PORT)
        self._baudrate = config.get("baudrate", DEFAULT_BAUDRATE)
        self._parity = config.get("parity", DEFAULT_PARITY)
        self._stopbits = config.get("stopbits", DEFAULT_STOPBITS)
        self._bytesize = config.get("bytesize", DEFAULT_BYTESIZE)
        super().__init__(config, storage, event_bus)

    @classmethod
    def _check_modbus_available(cls) -> bool:
        return _check_modbus_rtu_available()

    def _create_client(self) -> Any:
        return _AsyncModbusSerialClient(
            port=self._serial_port,
            baudrate=self._baudrate,
            parity=self._parity,
            stopbits=self._stopbits,
            bytesize=self._bytesize,
            timeout=self._timeout,
            retries=2,
        )

    async def _connect_client(self, client: Any) -> None:
        await client.connect()

    async def _disconnect_client(self, client: Any) -> None:
        client.close()

    def _is_client_connected(self, client: Any) -> bool:
        return client.connected

    def _get_connection_info(self) -> Dict[str, Any]:
        return {
            "serial_port": self._serial_port,
            "baudrate": self._baudrate,
            "parity": self._parity,
            "stopbits": self._stopbits,
            "bytesize": self._bytesize,
        }
