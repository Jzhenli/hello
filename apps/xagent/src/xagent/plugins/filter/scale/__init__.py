"""Scale Filter Plugin"""

__all__ = ["ScaleFilterPlugin"]


def __getattr__(name):
    if name == "ScaleFilterPlugin":
        from .plugin import ScaleFilterPlugin
        return ScaleFilterPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
