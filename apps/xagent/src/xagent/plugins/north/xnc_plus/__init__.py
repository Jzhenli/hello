"""XNC Plus Plugin Package - UDP-based bidirectional north plugin with Protobuf support"""

__all__ = ["XNCPlusPlugin"]


def __getattr__(name):
    if name == "XNCPlusPlugin":
        from .plugin import XNCPlusPlugin
        return XNCPlusPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
