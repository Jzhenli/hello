"""Rename Filter Plugin"""

__all__ = ["RenameFilterPlugin"]


def __getattr__(name):
    if name == "RenameFilterPlugin":
        from .plugin import RenameFilterPlugin
        return RenameFilterPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
