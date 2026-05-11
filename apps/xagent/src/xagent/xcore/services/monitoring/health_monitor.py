"""健康监控服务

负责监控系统健康状态和性能指标。
"""

import logging
from typing import Any, Dict, Optional

from ...core.plugin_loader import PluginLoader
from ...core.interfaces import ILifecycle

logger = logging.getLogger(__name__)


class HealthMonitor(ILifecycle):
    """健康监控服务
    
    监控系统健康状态，提供健康检查和状态报告功能。
    实现ILifecycle接口，支持统一的启动和停止。
    """
    
    def __init__(self, plugin_loader: PluginLoader):
        """初始化健康监控服务
        
        Args:
            plugin_loader: 插件加载器
        """
        self.plugin_loader = plugin_loader
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    async def start(self) -> None:
        """启动健康监控服务"""
        if self._running:
            return
        
        self._running = True
        logger.info("Health Monitor started")
    
    async def stop(self) -> None:
        """停止健康监控服务"""
        if not self._running:
            return
        
        self._running = False
        logger.info("Health Monitor stopped")
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态
        
        Returns:
            系统健康状态字典
        """
        if not self.plugin_loader:
            return {"status": "not_initialized"}
        
        health = self.plugin_loader.get_health_status()
        
        if health.failed_plugins > 0:
            overall_status = "degraded"
        elif health.running_plugins == health.total_plugins:
            overall_status = "healthy"
        else:
            overall_status = "partial"
        
        return {
            "overall_status": overall_status,
            "total_plugins": health.total_plugins,
            "running_plugins": health.running_plugins,
            "failed_plugins": health.failed_plugins,
            "stopped_plugins": health.stopped_plugins,
            "plugins": health.plugin_details
        }
    
    def get_plugin_health(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取单个插件的健康状态
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件健康状态字典，如果插件不存在返回None
        """
        plugin_info = self.plugin_loader.get_plugin(plugin_id)
        
        if not plugin_info:
            return None
        
        return {
            "plugin_id": plugin_info.plugin_id,
            "name": plugin_info.name,
            "type": plugin_info.plugin_type.value,
            "status": plugin_info.status.value,
            "error_message": plugin_info.error_message,
            "loaded_at": plugin_info.loaded_at.isoformat()
        }
    
    def is_healthy(self) -> bool:
        """检查系统是否健康
        
        Returns:
            如果系统健康返回True
        """
        health = self.get_system_health()
        return health.get("overall_status") in ["healthy", "partial"]
    
    def get_health_summary(self) -> str:
        """获取健康状态摘要
        
        Returns:
            健康状态摘要字符串
        """
        health = self.get_system_health()
        
        status_emoji = {
            "healthy": "✓",
            "partial": "⚠",
            "degraded": "✗",
            "not_initialized": "?"
        }
        
        emoji = status_emoji.get(health["overall_status"], "?")
        
        return (
            f"{emoji} System Status: {health['overall_status'].upper()} | "
            f"Plugins: {health['running_plugins']}/{health['total_plugins']} running, "
            f"{health['failed_plugins']} failed"
        )
