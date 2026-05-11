"""Rename Filter Plugin

重命名点位或资产。
"""

import logging
from typing import Any, Dict

from xagent.xcore.rule_engine import (
    RuleFilterPlugin,
    PluginMetadata,
    ReadingSet,
)

logger = logging.getLogger(__name__)


class RenameFilterPlugin(RuleFilterPlugin):
    """重命名过滤器插件
    
    重命名点位或资产。
    """
    
    __plugin_name__ = "rename"
    __plugin_type__ = "rule_engine.filter"
    
    def __init__(self):
        super().__init__()
        self._point_mapping: Dict[str, str] = {}
        self._asset_mapping: Dict[str, str] = {}
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="rename",
            version="1.0.0",
            description="重命名点位或资产",
            author="XAgent Team",
            plugin_type="rule_engine.filter",
            icon="✏️",
            color="#f59e0b",
            category="transform",
            display_name="重命名",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "point_mapping": {
                    "type": "object",
                    "title": "点位名称映射",
                    "description": "点位名称映射 {old_name: new_name}"
                },
                "asset_mapping": {
                    "type": "object",
                    "title": "资产名称映射",
                    "description": "资产名称映射 {old_name: new_name}"
                }
            }
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._point_mapping = config.get("point_mapping", {})
        self._asset_mapping = config.get("asset_mapping", {})
        
        logger.info(
            f"Rename filter initialized: "
            f"points={len(self._point_mapping)}, assets={len(self._asset_mapping)}"
        )
    
    def filter(self, data: ReadingSet) -> ReadingSet:
        new_points = {}
        
        for name, value in data.points.items():
            new_name = self._point_mapping.get(name, name)
            new_points[new_name] = value
        
        new_asset = self._asset_mapping.get(data.asset, data.asset)
        
        new_quality = None
        if data.quality:
            new_quality = {}
            for name, quality in data.quality.items():
                new_name = self._point_mapping.get(name, name)
                new_quality[new_name] = quality
        
        return ReadingSet(
            asset=new_asset,
            timestamp=data.timestamp,
            points=new_points,
            quality=new_quality,
            metadata=data.metadata
        )
