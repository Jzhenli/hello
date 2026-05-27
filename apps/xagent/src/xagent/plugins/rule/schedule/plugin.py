"""Schedule Rule Plugin

基于时间调度评估规则，支持 cron 表达式和周期性触发。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

from xagent.xcore.rule_engine import (
    RulePlugin,
    PluginMetadata,
    RuleContext,
    RuleEvaluationResult,
    RuleResult,
)

logger = logging.getLogger(__name__)


def _parse_cron_field(field: str, all_values: List[int]) -> List[int]:
    if field in ("*", "?"):
        return list(all_values)
    result = set()
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = min(all_values) if base == "*" else int(base)
            for v in range(start, max(all_values) + 1, step):
                if v in all_values:
                    result.add(v)
        elif "-" in part:
            start, end = part.split("-", 1)
            for v in range(int(start), int(end) + 1):
                if v in all_values:
                    result.add(v)
        else:
            v = int(part)
            if v in all_values:
                result.add(v)
    return sorted(result)


def _matches_cron(cron_expr: str, dt: datetime) -> bool:
    parts = cron_expr.strip().split()
    if len(parts) != 6:
        raise ValueError(f"Invalid cron expression (need 6 fields): {cron_expr}")

    minute_vals = _parse_cron_field(parts[1], list(range(60)))
    hour_vals = _parse_cron_field(parts[2], list(range(24)))
    day_vals = _parse_cron_field(parts[3], list(range(1, 32)))
    month_vals = _parse_cron_field(parts[4], list(range(1, 13)))
    weekday_vals = _parse_cron_field(parts[5], list(range(7)))

    return (
        dt.minute in minute_vals
        and dt.hour in hour_vals
        and dt.day in day_vals
        and dt.month in month_vals
        and dt.weekday() in weekday_vals
    )


class ScheduleRulePlugin(RulePlugin):
    """定时规则插件

    基于 cron 表达式或周期性间隔评估规则。
    当时间匹配时自动触发，无需依赖数据事件。

    配置项:
        trigger_type: "cron" | "interval"
        cron: 6字段 cron 表达式 (秒 分 时 日 月 周)
        interval: 周期间隔秒数
    """

    __plugin_name__ = "schedule_rule"
    __plugin_type__ = "rule_engine.rule"

    def __init__(self):
        super().__init__()
        self._trigger_type: str = "interval"
        self._cron: str = ""
        self._interval: int = 60
        self._last_trigger_time: float = 0
        self._last_cron_match: Optional[str] = None

    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="schedule_rule",
            version="1.0.0",
            description="基于时间调度的定时规则",
            author="XAgent Team",
            plugin_type="rule_engine.rule",
            icon="⏰",
            color="#06b6d4",
            category="trigger",
            display_name="定时触发",
            node_type="schedule-trigger",
            output_types=["condition", "action"],
            preview_template="{{trigger_type}}: {{cron_or_interval}}",
        )

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "trigger_type": {
                    "type": "string",
                    "title": "触发类型",
                    "enum": ["cron", "interval"],
                    "default": "interval",
                    "description": "cron: 使用 cron 表达式, interval: 使用固定间隔"
                },
                "cron": {
                    "type": "string",
                    "title": "Cron 表达式",
                    "description": "6字段格式: 秒 分 时 日 月 周 (例: 0 0 8 * * ? 每天8:00)"
                },
                "interval": {
                    "type": "integer",
                    "title": "间隔秒数",
                    "default": 60,
                    "minimum": 1,
                    "description": "周期性触发的间隔时间（秒）"
                }
            },
            "required": ["trigger_type"]
        }

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._trigger_type = config.get("trigger_type", "interval")
        self._cron = config.get("cron", "")
        self._interval = config.get("interval", 60)

        if self._trigger_type == "cron" and not self._cron:
            raise ValueError("Cron expression is required when trigger_type is 'cron'")

        if self._trigger_type == "cron":
            _matches_cron(self._cron, datetime.now())

        logger.info(
            f"Schedule rule initialized: type={self._trigger_type}, "
            f"cron={self._cron or 'N/A'}, interval={self._interval}s"
        )

    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        now = datetime.now()
        now_ts = context.timestamp or now.timestamp()

        if self._trigger_type == "cron":
            return self._evaluate_cron(now, now_ts)
        else:
            return self._evaluate_interval(now_ts)

    def _evaluate_cron(self, now: datetime, now_ts: float) -> RuleEvaluationResult:
        try:
            if _matches_cron(self._cron, now):
                minute_key = now.strftime("%Y-%m-%d %H:%M")
                if minute_key == self._last_cron_match:
                    return RuleEvaluationResult(
                        result=RuleResult.NOT_TRIGGERED,
                        triggered=False,
                        reason="Already triggered this minute"
                    )

                self._last_cron_match = minute_key
                self._last_trigger_time = now_ts

                return RuleEvaluationResult(
                    result=RuleResult.TRIGGERED,
                    triggered=True,
                    reason=f"Schedule triggered: cron '{self._cron}' at {now.isoformat()}",
                    details={
                        "trigger_type": "cron",
                        "cron": self._cron,
                        "triggered_at": now.isoformat(),
                    }
                )
            else:
                self._last_cron_match = None
                return RuleEvaluationResult(
                    result=RuleResult.NOT_TRIGGERED,
                    triggered=False,
                    reason=f"Schedule not matched: cron '{self._cron}'"
                )
        except Exception as e:
            return RuleEvaluationResult(
                result=RuleResult.ERROR,
                triggered=False,
                error=f"Cron evaluation error: {e}"
            )

    def _evaluate_interval(self, now_ts: float) -> RuleEvaluationResult:
        if self._last_trigger_time == 0:
            self._last_trigger_time = now_ts
            return RuleEvaluationResult(
                result=RuleResult.NOT_TRIGGERED,
                triggered=False,
                reason="Interval timer initialized"
            )

        elapsed = now_ts - self._last_trigger_time
        if elapsed >= self._interval:
            self._last_trigger_time = now_ts
            return RuleEvaluationResult(
                result=RuleResult.TRIGGERED,
                triggered=True,
                reason=f"Interval triggered: {self._interval}s elapsed",
                details={
                    "trigger_type": "interval",
                    "interval": self._interval,
                    "elapsed": elapsed,
                }
            )
        else:
            return RuleEvaluationResult(
                result=RuleResult.NOT_TRIGGERED,
                triggered=False,
                reason=f"Interval not reached: {elapsed:.0f}/{self._interval}s"
            )

    def get_preview_text(self, config: Dict[str, Any]) -> str:
        trigger_type = config.get("trigger_type", "interval")
        if trigger_type == "cron":
            return f"cron: {config.get('cron', '?')}"
        else:
            interval = config.get("interval", 60)
            if interval >= 86400:
                return f"每 {interval // 86400} 天"
            elif interval >= 3600:
                return f"每 {interval // 3600} 小时"
            else:
                return f"每 {interval} 秒"
