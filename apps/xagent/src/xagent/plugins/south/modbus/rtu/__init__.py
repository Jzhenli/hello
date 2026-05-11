"""Modbus RTU South Plugin Package"""

__all__ = ["ModbusRtuPlugin"]


def __getattr__(name):
    if name == "ModbusRtuPlugin":
        from .plugin import ModbusRtuPlugin
        return ModbusRtuPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
