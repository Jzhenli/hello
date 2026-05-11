"""MQTT North Plugin Package"""

__all__ = ["MQTTClientPlugin"]


def __getattr__(name):
    if name == "MQTTClientPlugin":
        from .plugin import MQTTClientPlugin
        return MQTTClientPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
