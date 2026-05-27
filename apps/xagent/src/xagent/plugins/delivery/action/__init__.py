"""Action Delivery Plugin"""

__all__ = ["ActionDeliveryPlugin"]


def __getattr__(name):
    if name == "ActionDeliveryPlugin":
        from .plugin import ActionDeliveryPlugin
        return ActionDeliveryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
