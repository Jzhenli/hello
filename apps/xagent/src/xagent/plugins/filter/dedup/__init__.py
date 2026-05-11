"""Dedup Filter Plugin"""

__all__ = ["DedupFilterPlugin"]


def __getattr__(name):
    if name == "DedupFilterPlugin":
        from .plugin import DedupFilterPlugin
        return DedupFilterPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
