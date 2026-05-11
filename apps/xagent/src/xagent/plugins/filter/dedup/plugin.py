"""Dedup Filter Plugin

去重过滤器，只转发变化的值。
"""

import logging
from typing import Any, Dict

from xagent.xcore.rule_engine import (
    RuleFilterPlugin,
    PluginMetadata,
    ReadingSet,
)

logger = logging.getLogger(__name__)


class DedupFilterPlugin(RuleFilterPlugin):
    """去重过滤器插件
    
    只转发变化的值。
    """
    
    __plugin_name__ = "dedup"
    __plugin_type__ = "rule_engine.filter"
    
    def __init__(self):
        super().__init__()
        self._last_values: Dict[str, Any] = {}
        self._tolerance: float = 0.0
        self._include_first: bool = True
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="dedup",
            version="1.0.0",
            description="去重过滤器，只转发变化的值",
            author="XAgent Team",
            plugin_type="rule_engine.filter",
            icon="🔄",
            color="#6366f1",
            category="filter",
            display_name="去重过滤",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tolerance": {
                    "type": "number",
                    "default": 0.0,
                    "description": "变化容忍度（绝对值）"
                },
                "include_first": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否包含首次数据"
                }
            }
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._tolerance = config.get("tolerance", 0.0)
        self._include_first = config.get("include_first", True)
        
        logger.info(
            f"Dedup filter initialized: "
            f"tolerance={self._tolerance}, include_first={self._include_first}"
        )
    
    def filter(self, data: ReadingSet) -> ReadingSet:
        filtered_points = {}
        filtered_quality = {}
        
        for name, value in data.points.items():
            last_value = self._last_values.get(name)
            
            if last_value is None:
                if self._include_first:
                    filtered_points[name] = value
                    self._last_values[name] = value
                    if data.quality and name in data.quality:
                        filtered_quality[name] = data.quality[name]
                continue
            
            if self._has_changed(value, last_value):
                filtered_points[name] = value
                self._last_values[name] = value
                if data.quality and name in data.quality:
                    filtered_quality[name] = data.quality[name]
        
        return ReadingSet(
            asset=data.asset,
            timestamp=data.timestamp,
            points=filtered_points,
            quality=filtered_quality if filtered_quality else None,
            metadata=data.metadata
        )
    
    def _has_changed(self, value: Any, last_value: Any) -> bool:
        """检查值是否发生变化"""
        if isinstance(value, (int, float)) and isinstance(last_value, (int, float)):
            return abs(value - last_value) > self._tolerance
        else:
            return value != last_value
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._last_values.clear()
    
    def shutdown(self) -> None:
        """关闭插件"""
        self.clear_cache()
        logger.info("Dedup filter shutdown")
