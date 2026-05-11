"""Expression Rule Plugin"""

__all__ = ["ExpressionRulePlugin"]


def __getattr__(name):
    if name == "ExpressionRulePlugin":
        from .plugin import ExpressionRulePlugin
        return ExpressionRulePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
