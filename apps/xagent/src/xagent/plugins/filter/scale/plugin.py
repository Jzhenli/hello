"""Scale Filter Plugin

对数据值应用缩放因子和偏移量。
"""

import logging
from typing import Any, Dict

from xagent.xcore.rule_engine import (
    RuleFilterPlugin,
    PluginMetadata,
    ReadingSet,
)

logger = logging.getLogger(__name__)


class ScaleFilterPlugin(RuleFilterPlugin):
    """缩放过滤器插件
    
    对数据值应用缩放因子和偏移量。
    公式: output = input * factor + offset
    """
    
    __plugin_name__ = "scale"
    __plugin_type__ = "rule_engine.filter"
    
    def __init__(self):
        super().__init__()
        self._factor: float = 1.0
        self._offset: float = 0.0
        self._points: Dict[str, Dict[str, float]] = {}
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="scale",
            version="1.0.0",
            description="对数据值应用缩放和偏移",
            author="XAgent Team",
            plugin_type="rule_engine.filter",
            icon="📏",
            color="#10b981",
            category="transform",
            display_name="缩放转换",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "factor": {
                    "type": "number",
                    "title": "缩放因子",
                    "default": 1.0,
                    "description": "乘法因子"
                },
                "offset": {
                    "type": "number",
                    "title": "偏移量",
                    "default": 0.0,
                    "description": "加法偏移"
                },
                "points": {
                    "type": "object",
                    "title": "点位配置",
                    "description": "按点位配置不同的缩放参数",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "factor": {"type": "number"},
                            "offset": {"type": "number"}
                        }
                    }
                }
            }
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._factor = config.get("factor", 1.0)
        self._offset = config.get("offset", 0.0)
        self._points = config.get("points", {})
        
        logger.info(
            f"Scale filter initialized: "
            f"factor={self._factor}, offset={self._offset}"
        )
    
    def filter(self, data: ReadingSet) -> ReadingSet:
        filtered_points = {}
        
        for point_name, value in data.points.items():
            if value is None:
                filtered_points[point_name] = None
                continue
            
            point_config = self._points.get(point_name, {})
            factor = point_config.get("factor", self._factor)
            offset = point_config.get("offset", self._offset)
            
            try:
                if isinstance(value, (int, float)):
                    filtered_points[point_name] = value * factor + offset
                else:
                    filtered_points[point_name] = value
            except Exception as e:
                logger.warning(f"Scale failed for {point_name}: {e}")
                filtered_points[point_name] = value
        
        return ReadingSet(
            asset=data.asset,
            timestamp=data.timestamp,
            points=filtered_points,
            quality=data.quality,
            metadata=data.metadata
        )
