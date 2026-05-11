"""Filter Plugin - Base class for data filtering plugins"""

import logging
import warnings
from abc import abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..storage.interface import Reading
from ..core.event_bus import EventBus
from ..core.plugin_loader import PluginType
from ..core.interfaces import IPlugin

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    passed: bool
    reading: Optional[Reading] = None
    error: Optional[str] = None


class FilterPluginBase(IPlugin):
    """
    核心过滤器插件基类
    
    所有核心过滤器插件必须继承此类，并实现必要的抽象方法。
    实现 IPlugin 接口，与规则引擎插件体系统一生命周期管理。
    注意：此类与规则引擎的 RuleFilterPlugin 是不同的体系，
    本类处理 Reading 对象，RuleFilterPlugin 处理 ReadingSet 对象。
    """
    
    __plugin_type__ = PluginType.FILTER.value
    __plugin_name__: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        self.config = config
        self.storage = storage
        self.event_bus = event_bus
        self._priority = config.get("priority", 100)
        self._service_name = self.__plugin_name__ or self.__class__.__name__
    
    @property
    def priority(self) -> int:
        return self._priority
    
    @property
    def plugin_type(self) -> str:
        return self.__plugin_type__
    
    @property
    def plugin_name(self) -> str:
        return self._service_name
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def shutdown(self) -> None:
        pass

    @abstractmethod
    async def process(self, reading: Reading) -> FilterResult:
        pass

    async def start(self) -> None:
        logger.info(f"Filter plugin started: {self._service_name}")

    async def stop(self) -> None:
        logger.info(f"Filter plugin stopped: {self._service_name}")


class FilterChain:
    def __init__(self):
        self._filters: List[FilterPluginBase] = []

    def add_filter(self, filter_plugin: FilterPluginBase) -> None:
        self._filters.append(filter_plugin)
        self._filters.sort(key=lambda f: f.priority)

    def remove_filter(self, filter_name: str) -> bool:
        for i, f in enumerate(self._filters):
            if f._service_name == filter_name:
                self._filters.pop(i)
                return True
        return False

    async def process(self, reading: Reading) -> FilterResult:
        current_reading = reading
        
        for filter_plugin in self._filters:
            try:
                result = await filter_plugin.process(current_reading)
                
                if not result.passed:
                    logger.debug(f"Reading filtered out by {filter_plugin._service_name}")
                    return FilterResult(passed=False, reading=current_reading)
                
                if result.reading:
                    current_reading = result.reading
                    
            except Exception as e:
                logger.error(f"Error in filter {filter_plugin._service_name}: {e}")
                error_policy = filter_plugin.config.get("error_policy", "pass")
                
                if error_policy == "drop":
                    return FilterResult(passed=False, error=str(e))
        
        return FilterResult(passed=True, reading=current_reading)

    async def process_batch(self, readings: List[Reading]) -> List[Reading]:
        results = []
        
        for reading in readings:
            result = await self.process(reading)
            if result.passed and result.reading:
                results.append(result.reading)
        
        return results

    def get_filters(self) -> List[FilterPluginBase]:
        return self._filters.copy()

    def clear(self) -> None:
        self._filters.clear()


class ScaleFilter(FilterPluginBase):
    """[DEPRECATED] Use plugins/filter/scale plugin instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ScaleFilter is deprecated. Use the standalone plugins/filter/scale plugin instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
    
    __plugin_name__ = "scale_filter"
    
    async def process(self, reading: Reading) -> FilterResult:
        scale = self.config.get("scale", 1.0)
        
        if not isinstance(reading.data, dict):
            return FilterResult(passed=True, reading=reading)
        
        scaled_data = {}
        for key, value in reading.data.items():
            if isinstance(value, (int, float)):
                scaled_data[key] = value * scale
            else:
                scaled_data[key] = value
        
        reading.data = scaled_data
        return FilterResult(passed=True, reading=reading)


class ThresholdFilter(FilterPluginBase):
    """[DEPRECATED] Use plugins/rule/threshold plugin instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ThresholdFilter is deprecated. Use the standalone plugins/rule/threshold plugin instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
    
    __plugin_name__ = "threshold_filter"
    
    async def process(self, reading: Reading) -> FilterResult:
        min_val = self.config.get("min", None)
        max_val = self.config.get("max", None)
        field = self.config.get("field", None)
        
        if not field or not isinstance(reading.data, dict):
            return FilterResult(passed=True, reading=reading)
        
        value = reading.data.get(field)
        if value is None:
            return FilterResult(passed=True, reading=reading)
        
        if min_val is not None and value < min_val:
            return FilterResult(passed=False, error=f"Value {value} below minimum {min_val}")
        
        if max_val is not None and value > max_val:
            return FilterResult(passed=False, error=f"Value {value} above maximum {max_val}")
        
        return FilterResult(passed=True, reading=reading)
