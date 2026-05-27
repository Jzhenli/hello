"""System Notification Delivery Plugin

将告警通知存储到系统内部，供前端告警页面展示。
"""

import logging
import time
import uuid
from typing import Any, Dict, List

from xagent.xcore.rule_engine import (
    DeliveryPlugin,
    PluginMetadata,
    Notification,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)

_alerts_store: List[Dict[str, Any]] = []
_max_alerts = 1000


def get_system_alerts() -> List[Dict[str, Any]]:
    return list(_alerts_store)


def acknowledge_alert(alert_id: str) -> bool:
    for alert in _alerts_store:
        if alert["id"] == alert_id:
            alert["status"] = "acknowledged"
            return True
    return False


def resolve_alert(alert_id: str) -> bool:
    for alert in _alerts_store:
        if alert["id"] == alert_id:
            alert["status"] = "resolved"
            return True
    return False


def ignore_alert(alert_id: str) -> bool:
    for alert in _alerts_store:
        if alert["id"] == alert_id:
            alert["status"] = "ignored"
            return True
    return False


def clear_resolved_alerts() -> int:
    global _alerts_store
    before = len(_alerts_store)
    _alerts_store = [a for a in _alerts_store if a["status"] != "resolved"]
    return before - len(_alerts_store)


class SystemDeliveryPlugin(DeliveryPlugin):

    __plugin_name__ = "system"
    __plugin_type__ = "rule_engine.delivery"

    def __init__(self):
        super().__init__()
        self._retention_days: int = 30
        self._max_notifications: int = 1000

    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="system",
            version="1.0.0",
            description="系统内部通知，在告警页面展示",
            author="XAgent Team",
            plugin_type="rule_engine.delivery",
            icon="🔔",
            color="#f59e0b",
            category="notification",
            display_name="系统通知",
        )

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "retention_days": {
                    "type": "integer",
                    "title": "保留天数",
                    "default": 30
                },
                "max_notifications": {
                    "type": "integer",
                    "title": "最大通知数",
                    "default": 1000
                }
            }
        }

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._retention_days = config.get("retention_days", 30)
        self._max_notifications = config.get("max_notifications", 1000)
        global _max_alerts
        _max_alerts = self._max_notifications
        logger.info(f"System delivery initialized (retention={self._retention_days}d, max={self._max_notifications})")

    async def deliver(self, notification: Notification) -> DeliveryResult:
        try:
            alert_record = {
                "id": notification.notification_id or str(uuid.uuid4()),
                "rule_id": notification.rule_id,
                "rule_name": notification.rule_name or "",
                "title": notification.title or "",
                "message": notification.message or "",
                "level": notification.level or "info",
                "status": "new",
                "asset": notification.asset or "",
                "point_name": notification.point_name or "",
                "current_value": str(notification.current_value) if notification.current_value is not None else "",
                "threshold": str(notification.threshold) if notification.threshold is not None else "",
                "triggered_at": notification.triggered_at or time.time(),
                "triggered_at_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(notification.triggered_at or time.time())),
                "metadata": notification.metadata or {},
            }

            _alerts_store.insert(0, alert_record)

            while len(_alerts_store) > _max_alerts:
                _alerts_store.pop()

            logger.info(f"System notification stored: {alert_record['id']}")

            return DeliveryResult(
                status=DeliveryStatus.SUCCESS,
                success=True,
                message=f"System notification stored (total: {len(_alerts_store)})"
            )

        except Exception as e:
            logger.error(f"System notification delivery failed: {e}")
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error=str(e)
            )

    async def test_connection(self) -> bool:
        return True

    async def shutdown(self) -> None:
        logger.info("System delivery plugin shutdown")
