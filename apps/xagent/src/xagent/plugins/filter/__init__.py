"""Filter plugins package"""

__all__ = [
    "ScaleFilterPlugin",
    "RenameFilterPlugin",
    "DedupFilterPlugin",
]


def __getattr__(name):
    if name == "ScaleFilterPlugin":
        from .scale.plugin import ScaleFilterPlugin
        return ScaleFilterPlugin
    if name == "RenameFilterPlugin":
        from .rename.plugin import RenameFilterPlugin
        return RenameFilterPlugin
    if name == "DedupFilterPlugin":
        from .dedup.plugin import DedupFilterPlugin
        return DedupFilterPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
