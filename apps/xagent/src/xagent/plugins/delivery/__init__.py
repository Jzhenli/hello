"""Delivery Plugins Package"""

__all__ = [
    "EmailDeliveryPlugin",
    "SystemDeliveryPlugin",
]


def __getattr__(name):
    if name == "EmailDeliveryPlugin":
        from .email.plugin import EmailDeliveryPlugin
        return EmailDeliveryPlugin
    if name == "SystemDeliveryPlugin":
        from .system.plugin import SystemDeliveryPlugin
        return SystemDeliveryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
