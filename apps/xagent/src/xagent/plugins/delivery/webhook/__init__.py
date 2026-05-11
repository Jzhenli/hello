"""Webhook Delivery Plugin"""

__all__ = ["WebhookDeliveryPlugin"]


def __getattr__(name):
    if name == "WebhookDeliveryPlugin":
        from .plugin import WebhookDeliveryPlugin
        return WebhookDeliveryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
