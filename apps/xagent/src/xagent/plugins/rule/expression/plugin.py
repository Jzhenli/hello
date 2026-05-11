"""Expression Rule Plugin

基于表达式评估规则。
"""

import ast
import logging
import operator
from typing import Any, Dict

from xagent.xcore.rule_engine import (
    RulePlugin,
    PluginMetadata,
    RuleContext,
    RuleEvaluationResult,
    RuleResult,
)

logger = logging.getLogger(__name__)

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
}

_SAFE_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}


class _ASTEvaluator:
    """基于 AST 的安全表达式评估器

    仅允许数学运算、比较运算和逻辑运算，
    禁止函数调用、属性访问等危险操作。
    """

    def __init__(self, variables: Dict[str, Any]):
        self._variables = variables

    def evaluate(self, expression: str) -> Any:
        tree = ast.parse(expression, mode='eval')
        return self._visit(tree.body)

    def _visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self._variables:
                return self._variables[node.id]
            raise NameError(f"Undefined variable: {node.id}")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
            left = self._visit(node.left)
            right = self._visit(node.right)
            return _SAFE_OPERATORS[op_type](left, right)

        if isinstance(node, ast.Compare):
            left = self._visit(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in _SAFE_OPERATORS:
                    raise ValueError(
                        f"Unsupported comparison operator: {op_type.__name__}"
                    )
                right = self._visit(comparator)
                if not _SAFE_OPERATORS[op_type](left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.BoolOp):
            op_type = type(node.op)
            if op_type == ast.And:
                result = self._visit(node.values[0])
                for value in node.values[1:]:
                    result = result and self._visit(value)
                return result
            elif op_type == ast.Or:
                result = self._visit(node.values[0])
                for value in node.values[1:]:
                    result = result or self._visit(value)
                return result
            raise ValueError(f"Unsupported boolean operator: {op_type.__name__}")

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_UNARY_OPERATORS:
                raise ValueError(
                    f"Unsupported unary operator: {op_type.__name__}"
                )
            operand = self._visit(node.operand)
            return _SAFE_UNARY_OPERATORS[op_type](operand)

        if isinstance(node, ast.IfExp):
            test = self._visit(node.test)
            if test:
                return self._visit(node.body)
            return self._visit(node.orelse)

        raise ValueError(f"Unsupported AST node: {type(node).__name__}")


class ExpressionRulePlugin(RulePlugin):
    """表达式规则插件

    基于用户定义的表达式评估规则是否触发。
    支持数学运算、逻辑运算、比较运算。
    """

    __plugin_name__ = "expression_rule"
    __plugin_type__ = "rule_engine.rule"

    def __init__(self):
        super().__init__()
        self._expression: str = ""
        self._duration: int = 0
        self._trigger_start_time: float = 0
        self._last_result: bool = False

    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="expression_rule",
            version="1.0.0",
            description="基于表达式评估规则",
            author="XAgent Team",
            plugin_type="rule_engine.rule",
            icon="⚙️",
            color="#8b5cf6",
            category="condition",
            display_name="表达式条件",
            node_type="expression-condition",
            input_types=["trigger", "logic"],
            output_types=["action", "logic"],
            preview_template="{{expression}}",
        )

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "title": "表达式",
                    "description": "要评估的布尔表达式"
                },
                "duration": {
                    "type": "number",
                    "title": "持续时间(秒)",
                    "default": 0,
                    "minimum": 0
                }
            },
            "required": ["expression"]
        }

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._expression = config.get("expression", "")
        self._duration = config.get("duration", 0)

        if not self._expression:
            raise ValueError("Expression is required")

        logger.info(f"Expression rule initialized: {self._expression}")

    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        try:
            eval_context = self._build_eval_context(context)

            result = self._safe_eval(self._expression, eval_context)

            if self._duration > 0:
                return self._handle_duration(result, context.timestamp)

            if result:
                return RuleEvaluationResult(
                    result=RuleResult.TRIGGERED,
                    triggered=True,
                    reason=f"Expression '{self._expression}' is true",
                    details={
                        "expression": self._expression,
                        "value": context.current_value
                    }
                )
            else:
                return RuleEvaluationResult(
                    result=RuleResult.NOT_TRIGGERED,
                    triggered=False
                )

        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return RuleEvaluationResult(
                result=RuleResult.ERROR,
                triggered=False,
                error=str(e)
            )

    def _build_eval_context(self, context: RuleContext) -> Dict[str, Any]:
        """构建评估上下文"""
        eval_context = {
            "value": context.current_value,
            "asset": context.asset,
            "point": context.point_name,
            "timestamp": context.timestamp,
            "device_status": context.device_status,
        }

        if context.window_avg is not None:
            eval_context["avg"] = context.window_avg
        if context.window_min is not None:
            eval_context["min"] = context.window_min
        if context.window_max is not None:
            eval_context["max"] = context.window_max

        if context.metadata:
            eval_context.update(context.metadata)

        return eval_context

    def _safe_eval(self, expression: str, context: Dict[str, Any]) -> bool:
        """安全评估表达式

        优先使用 simpleeval 库，备用 AST 评估器。
        两者均不使用 eval()，避免安全风险。
        """
        try:
            from simpleeval import EvalWithCompoundTypes

            evaluator = EvalWithCompoundTypes(names=context)
            result = evaluator.eval(expression)

            return bool(result)

        except ImportError:
            logger.debug(
                "simpleeval not installed, using AST evaluator. "
                "Install with: pip install simpleeval"
            )
            return self._ast_eval(expression, context)

        except Exception as e:
            logger.error(f"Expression evaluation failed: {e}")
            return False

    def _ast_eval(self, expression: str, context: Dict[str, Any]) -> bool:
        """基于 AST 的安全表达式评估

        解析表达式为 AST 节点树，仅允许安全的运算操作，
        完全避免使用 eval()。
        """
        try:
            evaluator = _ASTEvaluator(variables=context)
            result = evaluator.evaluate(expression)
            return bool(result)
        except Exception as e:
            logger.error(f"AST evaluation failed: {e}")
            return False

    def _handle_duration(self, result: bool, timestamp: float) -> RuleEvaluationResult:
        """处理持续时间逻辑"""
        if result and not self._last_result:
            self._trigger_start_time = timestamp
            self._last_result = True
            return RuleEvaluationResult(
                result=RuleResult.NOT_TRIGGERED,
                triggered=False,
                reason="Condition started, waiting for duration"
            )

        elif result and self._last_result:
            elapsed = timestamp - self._trigger_start_time
            if elapsed >= self._duration:
                return RuleEvaluationResult(
                    result=RuleResult.TRIGGERED,
                    triggered=True,
                    reason=f"Condition satisfied for {elapsed:.1f}s (required: {self._duration}s)"
                )
            else:
                return RuleEvaluationResult(
                    result=RuleResult.NOT_TRIGGERED,
                    triggered=False,
                    reason=f"Condition duration: {elapsed:.1f}s/{self._duration}s"
                )

        else:
            self._last_result = False
            self._trigger_start_time = 0
            return RuleEvaluationResult(
                result=RuleResult.NOT_TRIGGERED,
                triggered=False
            )

    def get_preview_text(self, config: Dict[str, Any]) -> str:
        expr = config.get("expression", "")
        duration = config.get("duration", 0)

        if duration > 0:
            return f"{expr}\n持续: {duration}s"
        return expr
