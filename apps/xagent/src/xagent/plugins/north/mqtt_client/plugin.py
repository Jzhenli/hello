"""MQTT North Plugin - Bidirectional MQTT client for data upload and command reception"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus, Event, EventType
from xagent.xcore.plugins.north import NorthPluginBase
from xagent.xcore.storage.interface import Reading
from xagent.xcore.core.plugin_loader import PluginType

if TYPE_CHECKING:
    import aiomqtt

logger = logging.getLogger(__name__)

MQTT_AVAILABLE = None
_aiomqtt = None
_MQTTClientAdapter = None

_SENSITIVE_KEYS = {"password", "secret", "token", "api_key"}


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    脱敏配置字典中的敏感字段

    Args:
        config: 原始配置字典

    Returns:
        脱敏后的配置字典
    """
    sanitized = {}
    for key, value in config.items():
        if key in _SENSITIVE_KEYS:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_config(value)
        else:
            sanitized[key] = value
    return sanitized


def _check_mqtt_available():
    """
    检查 aiomqtt 是否可用

    Returns:
        是否可用
    """
    global MQTT_AVAILABLE, _aiomqtt, _MQTTClientAdapter

    if MQTT_AVAILABLE is not None:
        return MQTT_AVAILABLE

    try:
        import aiomqtt
        from .adapter import MQTTClientAdapter

        _aiomqtt = aiomqtt
        _MQTTClientAdapter = MQTTClientAdapter
        MQTT_AVAILABLE = True
    except ImportError:
        MQTT_AVAILABLE = False
        logger.warning(
            "aiomqtt not installed, MQTT plugin will not work. "
            "Install with: pip install aiomqtt"
        )
    return MQTT_AVAILABLE


def _is_connection_error(exc: Exception) -> bool:
    """
    判断异常是否为连接错误

    Args:
        exc: 异常对象

    Returns:
        是否为连接错误
    """
    if isinstance(exc, ConnectionError):
        return True
    if _aiomqtt is not None and hasattr(_aiomqtt, "ConnectionClosedError"):
        try:
            if isinstance(exc, _aiomqtt.ConnectionClosedError):
                return True
        except TypeError:
            pass
    err_str = str(exc)
    if "not currently connected" in err_str or "Disconnected" in err_str:
        return True
    if hasattr(exc, "code") and getattr(exc, "code", None) in (4, 128):
        return True
    return False


class MQTTClientPlugin(NorthPluginBase):
    """
    MQTT 北向插件

    支持：
    - 数据上传到 MQTT Broker（单条/批量模式）
    - 订阅命令主题接收下行命令
    - 自动重连（指数退避）
    """

    __plugin_name__ = "mqtt_client"
    __plugin_type__ = PluginType.NORTH.value

    def _create_data_adapter(self) -> Any:
        """
        创建数据适配器

        Returns:
            MQTTClientAdapter 实例
        """
        if not _check_mqtt_available():
            raise RuntimeError("MQTT dependencies not available")
        adapter_config = self.config.get("adapter_config", {})
        return _MQTTClientAdapter(adapter_config)

    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        super().__init__(config, storage, event_bus)

        self._broker = config.get("broker", "localhost")
        self._port = config.get("port", 1883)
        self._topic = config.get("topic", "xagent/data")
        self._command_topic = config.get("command_topic", "xagent/command")
        self._qos = config.get("qos", 1)
        self._username = config.get("username")
        self._password = config.get("password")
        self._client_id = config.get("client_id", "xagent_mqtt_uploader")
        self._keepalive = config.get("keepalive", 60)
        self._batch_size = config.get("batch_size", 100)
        self._interval = config.get("interval", 5)
        self._publish_mode = config.get("publish_mode", "single")

        self._client: Optional["aiomqtt.Client"] = None
        self._upload_task: Optional["asyncio.Task[None]"] = None
        self._command_task: Optional["asyncio.Task[None]"] = None
        self._reconnect_interval = config.get("reconnect_interval", 5)
        self._reconnect_max_delay = config.get("reconnect_max_delay", 60)
        self._reconnect_attempts = 0
        self._reconnect_lock = asyncio.Lock()

        logger.info(
            f"Initializing MQTT plugin with config: {_sanitize_config(config)}"
        )
        logger.info(
            f"MQTT plugin initialized: "
            f"broker={self._broker}, port={self._port}, topic={self._topic}"
        )

    async def connect(self) -> bool:
        """
        连接 MQTT Broker

        Returns:
            连接是否成功
        """
        if not _check_mqtt_available() or _aiomqtt is None:
            logger.error(
                "aiomqtt is not installed. Install with: pip install aiomqtt"
            )
            return False

        try:
            logger.info(f"Connecting to MQTT broker {self._broker}:{self._port}...")

            client_kwargs = {
                "hostname": self._broker,
                "port": self._port,
                "identifier": self._client_id,
                "keepalive": self._keepalive,
            }

            if self._username:
                client_kwargs["username"] = self._username
                client_kwargs["password"] = self._password

            client = _aiomqtt.Client(**client_kwargs)
            await client.__aenter__()
            self._client = client
            self._connected = True
            if self._running:
                self._command_task = asyncio.create_task(self._command_loop())
            logger.info(f"MQTT connected to {self._broker}:{self._port}")
            return True

        except Exception as e:
            self._connected = False
            await self._cleanup_connection()
            logger.warning(f"MQTT connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """断开 MQTT 连接"""
        if self._upload_task:
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass
            self._upload_task = None

        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                pass
            self._command_task = None

        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT broker: {e}")
            finally:
                self._client = None
                self._connected = False

        logger.info(f"MQTT client disconnected from {self._broker}:{self._port}")

    async def _cleanup_connection(self) -> None:
        """清理连接资源"""
        self._connected = False
        if self._client:
            client = self._client
            self._client = None
            try:
                await asyncio.wait_for(
                    client.__aexit__(None, None, None), timeout=2.0
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout while cleaning up MQTT connection")
            except Exception as e:
                logger.debug(f"Error during connection cleanup (ignored): {e}")

    async def _reconnect(self) -> bool:
        """
        尝试重连 MQTT Broker

        Returns:
            重连是否成功
        """
        if self._connected:
            return True

        async with self._reconnect_lock:
            if self._connected:
                return True

            self._reconnect_attempts += 1
            delay = min(
                self._reconnect_interval * (2 ** (self._reconnect_attempts - 1)),
                self._reconnect_max_delay
            )

            logger.warning(
                f"MQTT connection lost, reconnecting in {delay}s "
                f"(attempt {self._reconnect_attempts})..."
            )

            await asyncio.sleep(delay)

            await self._cleanup_connection()

            success = await self.connect()
            if success:
                self._reconnect_attempts = 0
                logger.info("MQTT reconnected successfully")
            else:
                logger.warning(
                    f"MQTT reconnect attempt {self._reconnect_attempts} "
                    f"failed, will retry..."
                )

            return success

    async def start(self) -> None:
        """启动插件"""
        if self._running:
            logger.info("MQTT plugin already running")
            return

        logger.info(
            f"Starting MQTT plugin, connecting to {self._broker}:{self._port}"
        )
        success = await self.connect()
        if success:
            self._running = True
            self._upload_task = asyncio.create_task(self._upload_loop())
            if not self._command_task:
                self._command_task = asyncio.create_task(self._command_loop())
            logger.info(f"North plugin started: {self._service_name}")
        else:
            logger.error("Failed to connect to MQTT broker, plugin will not start")
            raise RuntimeError(
                f"Failed to connect north plugin: {self._service_name}"
            )

    async def stop(self) -> None:
        """停止插件"""
        if not self._running:
            return

        await self.disconnect()
        self._running = False
        logger.info(f"North plugin stopped: {self._service_name}")

    async def send(self, readings: List[Reading]) -> int:
        """
        发送数据到 MQTT Broker

        Args:
            readings: Reading 对象列表

        Returns:
            成功发送的数量
        """
        if not self._connected or not self._client:
            if not await self._reconnect():
                return 0

        client = self._client
        if client is None:
            return 0

        if not readings:
            logger.debug("No readings to publish")
            return 0

        logger.info(f"Starting to publish {len(readings)} readings")

        device_status_map = {
            r.asset: r.device_status
            for r in readings
            if r.device_status
        }

        context = {
            "timestamp": time.time(),
            "device_status_map": device_status_map
        }

        retry_count = self.config.get("retry_count", 3)
        retry_delay = self.config.get("retry_delay", 1)

        if self._publish_mode == "batch":
            return await self._send_batch(
                client, readings, context, retry_count, retry_delay
            )
        else:
            return await self._send_single(
                client, readings, context, retry_count, retry_delay
            )

    async def _send_single(
        self,
        client: "aiomqtt.Client",
        readings: List[Reading],
        context: Dict[str, Any],
        retry_count: int,
        retry_delay: int,
    ) -> int:
        """
        逐条发送数据

        Args:
            client: MQTT 客户端
            readings: Reading 列表
            context: 上下文信息
            retry_count: 重试次数
            retry_delay: 重试延迟

        Returns:
            成功发送的数量
        """
        sent = 0
        connection_lost = False

        for i, reading in enumerate(readings):
            if connection_lost:
                break

            for attempt in range(retry_count):
                try:
                    adapted_payload = self.adapt_readings([reading], context)
                    if adapted_payload is None:
                        logger.warning(
                            f"Failed to adapt reading {i+1}/{len(readings)}"
                        )
                        break

                    payload = self._data_adapter.to_json(adapted_payload)
                    logger.debug(
                        f"Publishing reading {i+1}/{len(readings)}: "
                        f"{reading.asset} at {reading.timestamp}"
                    )

                    await client.publish(
                        topic=self._topic,
                        payload=payload,
                        qos=self._qos
                    )
                    sent += 1
                    logger.debug(
                        f"Successfully published reading {i+1}/{len(readings)}"
                    )
                    break

                except Exception as e:
                    if _is_connection_error(e):
                        logger.warning("MQTT connection lost during publish")
                        self._connected = False
                        connection_lost = True
                        break
                    elif attempt < retry_count - 1:
                        logger.warning(
                            f"Error publishing reading "
                            f"(attempt {attempt + 1}): {e}, retrying..."
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(
                            f"Error publishing reading after "
                            f"{retry_count} attempts: {e}"
                        )

        if sent > 0:
            logger.info(f"Published {sent} readings to {self._topic}")
        else:
            logger.warning("Failed to publish any readings")

        return sent

    async def _send_batch(
        self,
        client: "aiomqtt.Client",
        readings: List[Reading],
        context: Dict[str, Any],
        retry_count: int,
        retry_delay: int,
    ) -> int:
        """
        批量发送数据

        Args:
            client: MQTT 客户端
            readings: Reading 列表
            context: 上下文信息
            retry_count: 重试次数
            retry_delay: 重试延迟

        Returns:
            成功发送的数量
        """
        for attempt in range(retry_count):
            try:
                adapted_payload = self.adapt_readings(readings, context)
                if adapted_payload is None:
                    logger.warning("Failed to adapt readings for batch publish")
                    return 0

                payload = self._data_adapter.to_json(adapted_payload)
                await client.publish(
                    topic=self._topic,
                    payload=payload,
                    qos=self._qos
                )
                logger.info(
                    f"Published {len(readings)} readings (batch) "
                    f"to {self._topic}"
                )
                return len(readings)

            except Exception as e:
                if _is_connection_error(e):
                    logger.warning("MQTT connection lost during batch publish")
                    self._connected = False
                    return 0
                elif attempt < retry_count - 1:
                    logger.warning(
                        f"Error batch publishing "
                        f"(attempt {attempt + 1}): {e}, retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Error batch publishing after "
                        f"{retry_count} attempts: {e}"
                    )

        return 0

    async def _upload_loop(self) -> None:
        """上传数据循环"""
        logger.info(f"MQTT upload loop started, interval={self._interval}s")
        while self._running:
            try:
                if not self._connected:
                    if not await self._reconnect():
                        await asyncio.sleep(self._reconnect_interval)
                        continue

                logger.debug(
                    f"MQTT upload loop: fetching data "
                    f"(batch_size={self._batch_size})"
                )
                await self.fetch_and_send(self._batch_size)
                logger.debug(f"MQTT upload loop: waiting {self._interval}s")
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                logger.info("MQTT upload loop cancelled")
                break
            except Exception as e:
                if _is_connection_error(e):
                    self._connected = False
                else:
                    logger.error(f"Error in upload loop: {e}")
                await asyncio.sleep(self._reconnect_interval)

    async def _command_loop(self) -> None:
        """命令接收循环"""
        logger.info(
            f"MQTT command loop started, subscribing to {self._command_topic}"
        )
        while self._running:
            try:
                if not self._connected or not self._client:
                    if not await self._reconnect():
                        await asyncio.sleep(self._reconnect_interval)
                        continue

                client = self._client
                if client is None:
                    await asyncio.sleep(self._reconnect_interval)
                    continue

                await client.subscribe(self._command_topic, qos=self._qos)
                async for message in client.messages:
                    if not self._running:
                        break
                    try:
                        await asyncio.wait_for(
                            self._handle_command(message),
                            timeout=30.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Command handling timed out")
                    except Exception as e:
                        logger.error(f"Error handling command: {e}")
            except asyncio.CancelledError:
                logger.info("MQTT command loop cancelled")
                break
            except Exception as e:
                if _is_connection_error(e):
                    self._connected = False
                else:
                    logger.warning(f"MQTT command loop error: {e}")
                await asyncio.sleep(self._reconnect_interval)

    async def _publish_result(self, result: Dict[str, Any]) -> None:
        """
        发布命令执行结果

        Args:
            result: 结果数据
        """
        client = self._client
        if client is None:
            logger.warning("Cannot publish result: client not connected")
            return

        try:
            result_topic = f"{self._command_topic}/result"
            await client.publish(
                topic=result_topic,
                payload=json.dumps(result, ensure_ascii=False),
                qos=self._qos
            )
        except Exception as e:
            logger.error(f"Failed to publish command result: {e}")

    async def _handle_command(self, message: "aiomqtt.Message") -> None:
        """
        处理收到的命令消息

        Args:
            message: MQTT 消息
        """
        try:
            payload = message.payload.decode("utf-8")
            logger.info(f"Received command: {payload}")

            command = json.loads(payload)
            asset = command.get("asset")
            data = command.get("data")

            if not asset or not data:
                logger.warning("Invalid command: missing asset or data")
                return

            logger.info(f"Executing write command for asset {asset}: {data}")

            adapted = self.adapt_command(command, {"timestamp": time.time()})

            event = Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={
                    "asset": adapted.get("asset", asset),
                    "data": adapted.get("data", data)
                }
            )
            await self.event_bus.publish(event)
            logger.info(f"Published COMMAND_RECEIVED event for asset {asset}")

            await self._publish_result({
                "asset": asset,
                "data": data,
                "status": "success",
                "timestamp": time.time()
            })
            logger.info(f"Command executed successfully for asset {asset}")

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            await self._publish_result({
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            })

    @staticmethod
    def _dedup_latest_readings(readings: List[Reading], limit: int) -> List[Reading]:
        """
        按 asset 去重，保留每个 asset 时间戳最新的 Reading

        Args:
            readings: Reading 列表
            limit: 最大返回数量

        Returns:
            去重后的 Reading 列表
        """
        latest_by_asset: Dict[str, Reading] = {}
        for reading in readings:
            asset = reading.asset
            if asset not in latest_by_asset or reading.timestamp > latest_by_asset[asset].timestamp:
                latest_by_asset[asset] = reading
        return list(latest_by_asset.values())[:limit]

    async def fetch_and_send(self, batch_size: int = 100) -> int:
        """
        从存储获取数据并发送

        Args:
            batch_size: 批量大小

        Returns:
            发送数量
        """
        if not self.storage:
            logger.warning("Storage not available")
            return 0

        try:
            logger.debug(
                f"Querying storage for readings (limit={batch_size * 2})"
            )
            readings = await self.storage.query(limit=batch_size * 2)
            logger.info(f"Queried {len(readings)} readings from storage")

            if not readings:
                logger.debug("No readings to send")
                return 0

            latest_readings = self._dedup_latest_readings(readings, batch_size)
            logger.info(
                f"Filtered to {len(latest_readings)} latest readings "
                f"(one per asset)"
            )

            sent = await self.send(latest_readings)
            logger.info(f"Sent {sent} readings to MQTT broker")
            return sent
        except Exception as e:
            logger.error(
                f"Error fetching and sending readings: {e}", exc_info=True
            )
            return 0

    async def handle_command(self, command_data: Dict[str, Any]) -> bool:
        """
        处理下行命令

        Args:
            command_data: 命令数据

        Returns:
            处理是否成功
        """
        try:
            adapted = self.adapt_command(command_data, {"timestamp": time.time()})

            event = Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={
                    "asset": adapted.get("asset", command_data.get("asset")),
                    "data": adapted.get("data", command_data.get("data", {}))
                }
            )
            await self.event_bus.publish(event)

            logger.info(f"Command processed for {command_data.get('asset')}")
            return True

        except Exception as e:
            logger.error(f"Command handling error: {e}")
            return False
