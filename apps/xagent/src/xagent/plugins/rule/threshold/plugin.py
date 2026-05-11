"""Threshold Rule Plugin

基于阈值评估规则。
"""

import logging
from typing import Any, Dict, Optional

from xagent.xcore.rule_engine import (
    RulePlugin,
    PluginMetadata,
    RuleContext,
    RuleEvaluationResult,
    RuleResult,
)

logger = logging.getLogger(__name__)


class ThresholdRulePlugin(RulePlugin):
    """阈值规则插件
    
    基于阈值比较评估规则是否触发。
    支持 >, <, >=, <=, ==, != 等比较操作。
    """
    
    __plugin_name__ = "threshold_rule"
    __plugin_type__ = "rule_engine.rule"
    
    def __init__(self):
        super().__init__()
        self._threshold: Optional[float] = None
        self._operator: str = ">"
        self._duration: int = 0
        self._trigger_start_time: float = 0
        self._last_result: bool = False
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="threshold_rule",
            version="1.0.0",
            description="基于阈值比较评估规则",
            author="XAgent Team",
            plugin_type="rule_engine.rule",
            icon="📊",
            color="#ef4444",
            category="condition",
            display_name="阈值条件",
            node_type="threshold-condition",
            input_types=["trigger", "logic"],
            output_types=["action", "logic"],
            preview_template="{{operator}} {{threshold}}",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "threshold": {
                    "type": "number",
                    "title": "阈值",
                    "description": "比较阈值"
                },
                "operator": {
                    "type": "string",
                    "title": "比较操作符",
                    "enum": [">", "<", ">=", "<=", "==", "!="],
                    "default": ">"
                },
                "duration": {
                    "type": "number",
                    "title": "持续时间(秒)",
                    "default": 0,
                    "minimum": 0
                }
            },
            "required": ["threshold"]
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._threshold = config.get("threshold")
        self._operator = config.get("operator", ">")
        self._duration = config.get("duration", 0)
        
        if self._threshold is None:
            raise ValueError("Threshold is required")
        
        logger.info(
            f"Threshold rule initialized: "
            f"operator={self._operator}, threshold={self._threshold}"
        )
    
    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        try:
            value = context.current_value
            
            if value is None:
                return RuleEvaluationResult(
                    result=RuleResult.NOT_TRIGGERED,
                    triggered=False,
                    reason="No current value"
                )
            
            if not isinstance(value, (int, float)):
                return RuleEvaluationResult(
                    result=RuleResult.ERROR,
                    triggered=False,
                    error=f"Value must be numeric, got {type(value).__name__}"
                )
            
            result = self._compare(value, self._threshold, self._operator)
            
            if self._duration > 0:
                return self._handle_duration(result, context.timestamp, value)
            
            if result:
                return RuleEvaluationResult(
                    result=RuleResult.TRIGGERED,
                    triggered=True,
                    reason=f"Value {value} {self._operator} {self._threshold}",
                    details={
                        "value": value,
                        "threshold": self._threshold,
                        "operator": self._operator
                    }
                )
            else:
                return RuleEvaluationResult(
                    result=RuleResult.NOT_TRIGGERED,
                    triggered=False,
                    reason=f"Value {value} not {self._operator} {self._threshold}"
                )
                
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return RuleEvaluationResult(
                result=RuleResult.ERROR,
                triggered=False,
                error=str(e)
            )
    
    def _compare(self, value: float, threshold: float, operator: str) -> bool:
        """比较值与阈值"""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def _handle_duration(
        self, 
        result: bool, 
        timestamp: float,
        value: float
    ) -> RuleEvaluationResult:
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
                    reason=f"Value {value} {self._operator} {self._threshold} for {elapsed:.1f}s"
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
        threshold = config.get("threshold", "?")
        operator = config.get("operator", ">")
        duration = config.get("duration", 0)
        
        text = f"{operator} {threshold}"
        if duration > 0:
            text += f"\n持续: {duration}s"
        return text
