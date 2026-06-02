"""统计记录器 - 在编排层统一拦截并记录统计

设计原则：
1. 对业务代码零侵入
2. 统一处理同步/异步方法
3. 异常安全，统计失败不影响主流程
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import StatisticsManager

logger = logging.getLogger(__name__)


class StatsRecorder:
    """统计记录器
    
    在编排层统一拦截并记录统计，对业务代码零侵入。
    
    使用示例：
        recorder = StatsRecorder(stats_manager)
        
        # 异步操作
        result = await recorder.record_async(
            category="rule",
            name="threshold_rule",
            coro=plugin.evaluate(context),
            triggered=True,
        )
        
        # 同步操作
        result = recorder.record_sync(
            category="filter",
            name="dedup",
            func=lambda: plugin.filter(data),
            input_count=10,
        )
    """
    
    def __init__(self, stats_manager: Optional["StatisticsManager"]):
        """初始化统计记录器
        
        Args:
            stats_manager: 统计管理器实例，为 None 时不记录统计
        """
        self._stats_manager = stats_manager
    
    @property
    def stats_manager(self) -> Optional["StatisticsManager"]:
        """获取统计管理器"""
        return self._stats_manager
    
    def set_stats_manager(self, stats_manager: "StatisticsManager") -> None:
        """设置统计管理器"""
        self._stats_manager = stats_manager
    
    async def record_async(
        self,
        category: str,
        name: str,
        coro: Any,
        **extra
    ) -> Any:
        """执行异步操作并记录统计
        
        Args:
            category: 分类（如 rule, delivery, filter）
            name: 操作名称
            coro: 协程对象或异步函数
            **extra: 额外指标
            
        Returns:
            原始操作的返回值
        """
        start_time = time.time()
        success = True
        result = None
        
        try:
            if asyncio.iscoroutine(coro):
                result = await coro
            elif asyncio.iscoroutinefunction(coro):
                result = await coro()
            elif callable(coro):
                result = coro()
            else:
                result = coro
        except Exception as e:
            success = False
            raise
        finally:
            if self._stats_manager:
                try:
                    await self._stats_manager.record_operation(
                        category=category,
                        name=name,
                        success=success,
                        duration=time.time() - start_time,
                        **extra
                    )
                except Exception as stats_error:
                    logger.debug(f"Stats recording failed: {stats_error}")
        
        return result
    
    def record_sync(
        self,
        category: str,
        name: str,
        func: Callable,
        **extra
    ) -> Any:
        """执行同步操作并记录统计
        
        Args:
            category: 分类
            name: 操作名称
            func: 同步函数
            **extra: 额外指标
            
        Returns:
            原始操作的返回值
        """
        start_time = time.time()
        success = True
        result = None
        
        try:
            result = func()
        except Exception:
            success = False
            raise
        finally:
            if self._stats_manager:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self._stats_manager.record_operation(
                            category=category,
                            name=name,
                            success=success,
                            duration=time.time() - start_time,
                            **extra
                        )
                    )
                except RuntimeError:
                    pass
                except Exception as stats_error:
                    logger.debug(f"Stats recording failed: {stats_error}")
        
        return result
    
    async def record_async_with_result(
        self,
        category: str,
        name: str,
        coro: Any,
        result_extractor: Optional[Callable[[Any], dict]] = None,
        **extra
    ) -> Any:
        """执行异步操作并记录统计，支持从结果提取额外指标
        
        Args:
            category: 分类
            name: 操作名称
            coro: 协程对象
            result_extractor: 从结果提取额外指标的函数
            **extra: 基础额外指标
            
        Returns:
            原始操作的返回值
        """
        start_time = time.time()
        success = True
        result = None
        
        try:
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
        except Exception:
            success = False
            raise
        finally:
            if self._stats_manager:
                try:
                    final_extra = dict(extra)
                    
                    if result_extractor and result is not None:
                        try:
                            extracted = result_extractor(result)
                            if extracted:
                                final_extra.update(extracted)
                        except Exception as e:
                            logger.debug(f"Failed to extract result metrics: {e}")
                    
                    await self._stats_manager.record_operation(
                        category=category,
                        name=name,
                        success=success,
                        duration=time.time() - start_time,
                        **final_extra
                    )
                except Exception as stats_error:
                    logger.debug(f"Stats recording failed: {stats_error}")
        
        return result
