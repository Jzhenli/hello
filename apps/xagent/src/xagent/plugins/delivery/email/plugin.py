"""Email Delivery Plugin

通过 SMTP 发送邮件通知。
"""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List

from xagent.xcore.rule_engine import (
    DeliveryPlugin,
    PluginMetadata,
    Notification,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)


class EmailDeliveryPlugin(DeliveryPlugin):
    """邮件交付插件
    
    通过 SMTP 发送邮件通知。
    """
    
    __plugin_name__ = "email"
    __plugin_type__ = "rule_engine.delivery"
    
    def __init__(self):
        super().__init__()
        self._smtp_host: str = ""
        self._smtp_port: int = 587
        self._smtp_user: str = ""
        self._smtp_password: str = ""
        self._from_address: str = ""
        self._use_tls: bool = True
    
    @classmethod
    def plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name="email",
            version="1.0.0",
            description="通过邮件发送通知",
            author="XAgent Team",
            plugin_type="rule_engine.delivery",
            icon="📧",
            color="#3b82f6",
            category="notification",
            display_name="邮件通知",
        )
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "smtp_host": {
                    "type": "string",
                    "title": "SMTP 服务器",
                    "description": "SMTP 服务器地址"
                },
                "smtp_port": {
                    "type": "integer",
                    "title": "SMTP 端口",
                    "default": 587
                },
                "smtp_user": {
                    "type": "string",
                    "title": "SMTP 用户名"
                },
                "smtp_password": {
                    "type": "string",
                    "title": "SMTP 密码",
                    "format": "password"
                },
                "from_address": {
                    "type": "string",
                    "title": "发件人地址"
                },
                "use_tls": {
                    "type": "boolean",
                    "title": "使用 TLS",
                    "default": True
                }
            },
            "required": ["smtp_host", "smtp_user", "smtp_password", "from_address"]
        }
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._smtp_host = config.get("smtp_host", "")
        self._smtp_port = config.get("smtp_port", 587)
        self._smtp_user = config.get("smtp_user", "")
        self._smtp_password = config.get("smtp_password", "")
        self._from_address = config.get("from_address", "")
        self._use_tls = config.get("use_tls", True)
        
        if not all([self._smtp_host, self._smtp_user, self._smtp_password]):
            raise ValueError("SMTP configuration is incomplete")
        
        logger.info(f"Email delivery initialized: {self._smtp_host}:{self._smtp_port}")
    
    async def deliver(self, notification: Notification) -> DeliveryResult:
        try:
            msg = self._build_message(notification)
            
            recipients = notification.recipients or []
            if not recipients:
                return DeliveryResult(
                    status=DeliveryStatus.FAILED,
                    success=False,
                    error="No recipients specified"
                )
            
            await asyncio.to_thread(
                self._send_email, 
                msg, 
                recipients
            )
            
            logger.info(f"Email sent: {notification.notification_id}")
            
            return DeliveryResult(
                status=DeliveryStatus.SUCCESS,
                success=True,
                message=f"Email sent to {len(recipients)} recipients"
            )
            
        except Exception as e:
            logger.error(f"Email delivery failed: {e}")
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error=str(e)
            )
    
    async def test_connection(self) -> bool:
        try:
            await asyncio.to_thread(self._test_smtp_connection)
            logger.info("SMTP connection test passed")
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
    
    def _build_message(self, notification: Notification) -> MIMEMultipart:
        """构建邮件消息"""
        msg = MIMEMultipart("alternative")
        msg["From"] = self._from_address
        msg["To"] = ", ".join(notification.recipients or [])
        msg["Subject"] = f"[{notification.level.upper()}] {notification.title}"
        
        text_content = self._build_text_content(notification)
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        
        html_content = self._build_html_content(notification)
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        
        return msg
    
    def _build_text_content(self, notification: Notification) -> str:
        """构建纯文本内容"""
        lines = [
            "告警通知",
            "=" * 40,
            "",
            f"规则: {notification.rule_name}",
            f"级别: {notification.level}",
            f"设备: {notification.asset}",
            f"点位: {notification.point_name}",
            f"当前值: {notification.current_value}",
            f"阈值: {notification.threshold}",
            "",
            f"消息: {notification.message}",
            "",
            f"触发时间: {notification.triggered_at}",
        ]
        return "\n".join(lines)
    
    def _build_html_content(self, notification: Notification) -> str:
        """构建 HTML 内容"""
        level_colors = {
            "critical": "#dc2626",
            "warning": "#f59e0b",
            "info": "#3b82f6",
            "debug": "#6b7280"
        }
        color = level_colors.get(notification.level, "#6b7280")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2 style="color: {color};">
                    [{notification.level.upper()}] {notification.title}
                </h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>规则</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{notification.rule_name}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>设备</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{notification.asset}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>点位</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{notification.point_name}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>当前值</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{notification.current_value}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>阈值</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{notification.threshold}</td></tr>
                </table>
                <p style="margin-top: 16px;">{notification.message}</p>
            </div>
        </body>
        </html>
        """
    
    def _send_email(self, msg: MIMEMultipart, recipients: List[str]) -> None:
        """发送邮件"""
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            if self._use_tls:
                server.starttls()
            server.login(self._smtp_user, self._smtp_password)
            server.sendmail(self._from_address, recipients, msg.as_string())
    
    def _test_smtp_connection(self) -> None:
        """测试 SMTP 连接"""
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            if self._use_tls:
                server.starttls()
            server.login(self._smtp_user, self._smtp_password)
    
    async def shutdown(self) -> None:
        """关闭插件"""
        logger.info("Email delivery plugin shutdown")
