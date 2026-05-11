"""Webhook Delivery Plugin

通过 HTTP Webhook 发送通知。
"""

import asyncio
import logging
from typing import Any, Dict

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False

from xagent.xcore.rule_engine import (
    DeliveryPlugin,
    PluginMetadata,
    Notification,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)


class WebhookDeliveryPlugin(DeliveryPlugin):
    """Webhook 交付插件
    
    通过 HTTP POST 请求发送通知。
    """
    
    __plugin_name__ = "webhook"
    __plugin_type__ = "rule_engine.delivery"
    
    def __init__(self):
        super().__init__()
        self._url: str = ""
        self._method: str = "POST"
        self._headers: Dict[str, str] = {}
        self._timeout: int = 30
        self._retry_count: int = 3
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="webhook",
            version="1.0.0",
            description="通过 HTTP Webhook 发送通知",
            author="XAgent Team",
            plugin_type="rule_engine.delivery",
            icon="🔗",
            color="#10b981",
            category="notification",
            display_name="Webhook 通知",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "title": "Webhook URL",
                    "description": "接收通知的 URL"
                },
                "method": {
                    "type": "string",
                    "title": "HTTP 方法",
                    "enum": ["POST", "PUT", "GET"],
                    "default": "POST"
                },
                "headers": {
                    "type": "object",
                    "title": "HTTP 头",
                    "description": "自定义 HTTP 头"
                },
                "timeout": {
                    "type": "integer",
                    "title": "超时时间(秒)",
                    "default": 30
                },
                "retry_count": {
                    "type": "integer",
                    "title": "重试次数",
                    "default": 3
                }
            },
            "required": ["url"]
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._url = config.get("url", "")
        self._method = config.get("method", "POST")
        self._headers = config.get("headers", {})
        self._timeout = config.get("timeout", 30)
        self._retry_count = config.get("retry_count", 3)
        
        if not self._url:
            raise ValueError("Webhook URL is required")
        
        if "Content-Type" not in self._headers:
            self._headers["Content-Type"] = "application/json"
        
        logger.info(f"Webhook delivery initialized: {self._url}")
    
    async def deliver(self, notification: Notification) -> DeliveryResult:
        payload = self._build_payload(notification)
        
        for attempt in range(self._retry_count):
            try:
                result = await self._send_request(payload)
                
                if result.success:
                    logger.info(f"Webhook sent: {notification.notification_id}")
                    return result
                
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    
            except Exception as e:
                logger.error(f"Webhook delivery attempt {attempt + 1} failed: {e}")
                
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            success=False,
            error=f"Failed after {self._retry_count} attempts"
        )
    
    async def test_connection(self) -> bool:
        if not _HAS_AIOHTTP:
            logger.error("aiohttp is not installed, cannot test webhook connection")
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method="GET",
                    url=self._url,
                    headers=self._headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    return response.status < 500
        except Exception as e:
            logger.error(f"Webhook connection test failed: {e}")
            return False
    
    def _build_payload(self, notification: Notification) -> Dict[str, Any]:
        """构建请求负载"""
        return {
            "notification_id": notification.notification_id,
            "rule_id": notification.rule_id,
            "rule_name": notification.rule_name,
            "title": notification.title,
            "message": notification.message,
            "level": notification.level,
            "asset": notification.asset,
            "point_name": notification.point_name,
            "current_value": notification.current_value,
            "threshold": notification.threshold,
            "triggered_at": notification.triggered_at,
            "metadata": notification.metadata
        }
    
    async def _send_request(self, payload: Dict[str, Any]) -> DeliveryResult:
        """发送 HTTP 请求"""
        if not _HAS_AIOHTTP:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error="aiohttp is not installed"
            )
        async with aiohttp.ClientSession() as session:
            kwargs = {
                "method": self._method,
                "url": self._url,
                "headers": self._headers,
                "timeout": aiohttp.ClientTimeout(total=self._timeout)
            }
            
            if self._method in ["POST", "PUT"]:
                kwargs["json"] = payload
            
            async with session.request(**kwargs) as response:
                if response.status >= 200 and response.status < 300:
                    return DeliveryResult(
                        status=DeliveryStatus.SUCCESS,
                        success=True,
                        message=f"HTTP {response.status}"
                    )
                else:
                    return DeliveryResult(
                        status=DeliveryStatus.FAILED,
                        success=False,
                        error=f"HTTP {response.status}"
                    )
    
    async def shutdown(self) -> None:
        """关闭插件"""
        logger.info("Webhook delivery plugin shutdown")
