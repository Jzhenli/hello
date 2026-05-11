"""BACnet South Plugin Package"""

__all__ = ["BACnetPlugin"]


def __getattr__(name):
    if name == "BACnetPlugin":
        from .plugin import BACnetPlugin
        return BACnetPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
