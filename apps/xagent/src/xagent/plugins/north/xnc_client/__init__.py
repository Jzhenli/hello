"""XNC Client Plugin Package - UDP-based bidirectional north plugin with Protobuf support"""

__all__ = ["XNCClientPlugin"]


def __getattr__(name):
    if name == "XNCClientPlugin":
        from .plugin import XNCClientPlugin
        return XNCClientPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
