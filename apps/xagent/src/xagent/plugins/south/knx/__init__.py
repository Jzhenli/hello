"""KNX South Plugin Package"""

__all__ = ["KNXPlugin"]


def __getattr__(name):
    if name == "KNXPlugin":
        from .plugin import KNXPlugin
        return KNXPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
