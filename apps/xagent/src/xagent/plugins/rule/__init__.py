"""Rule Plugins Package"""

__all__ = [
    "ExpressionRulePlugin",
    "ThresholdRulePlugin",
]


def __getattr__(name):
    if name == "ExpressionRulePlugin":
        from .expression.plugin import ExpressionRulePlugin
        return ExpressionRulePlugin
    if name == "ThresholdRulePlugin":
        from .threshold.plugin import ThresholdRulePlugin
        return ThresholdRulePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
