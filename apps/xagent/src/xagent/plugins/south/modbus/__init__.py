"""Modbus South Plugin Package - Unified Modbus TCP/RTU support

Exports:
    ModbusTcpPlugin: Modbus TCP 传输层插件
    ModbusRtuPlugin: Modbus RTU 串口传输层插件
"""

__all__ = ["ModbusTcpPlugin", "ModbusRtuPlugin"]


def __getattr__(name):
    if name == "ModbusTcpPlugin":
        from .tcp.plugin import ModbusTcpPlugin
        return ModbusTcpPlugin
    elif name == "ModbusRtuPlugin":
        from .rtu.plugin import ModbusRtuPlugin
        return ModbusRtuPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
