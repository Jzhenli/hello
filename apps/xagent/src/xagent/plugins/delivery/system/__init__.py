"""System Notification Delivery Plugin"""

__all__ = ["SystemDeliveryPlugin"]


def __getattr__(name):
    if name == "SystemDeliveryPlugin":
        from .plugin import SystemDeliveryPlugin
        return SystemDeliveryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
