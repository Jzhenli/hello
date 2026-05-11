"""Delivery Plugins Package"""

__all__ = [
    "EmailDeliveryPlugin",
]


def __getattr__(name):
    if name == "EmailDeliveryPlugin":
        from .email.plugin import EmailDeliveryPlugin
        return EmailDeliveryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
