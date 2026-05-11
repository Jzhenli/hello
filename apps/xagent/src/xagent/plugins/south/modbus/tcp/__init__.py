"""Modbus TCP South Plugin Package"""

__all__ = ["ModbusTcpPlugin"]


def __getattr__(name):
    if name == "ModbusTcpPlugin":
        from .plugin import ModbusTcpPlugin
        return ModbusTcpPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
