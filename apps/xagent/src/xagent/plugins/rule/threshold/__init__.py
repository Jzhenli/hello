"""Threshold Rule Plugin"""

__all__ = ["ThresholdRulePlugin"]


def __getattr__(name):
    if name == "ThresholdRulePlugin":
        from .plugin import ThresholdRulePlugin
        return ThresholdRulePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
