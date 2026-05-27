"""Schedule Rule Plugin"""

__all__ = ["ScheduleRulePlugin"]


def __getattr__(name):
    if name == "ScheduleRulePlugin":
        from .plugin import ScheduleRulePlugin
        return ScheduleRulePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
