"""MQTT Adapter Tests - 测试适配器重构的正确性"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import Mock, AsyncMock

from xagent.xcore.storage.interface import Reading

from xagent.plugins.north.mqtt_client.types import (
    PublishPacket,
    CommandData,
    CommandResult,
    CommandContext,
    ResponsePacket,
)
from xagent.plugins.north.mqtt_client.exceptions import (
    MQTTAdapterError,
    DataConversionError,
    TopicError,
    CommandParseError,
)
from xagent.plugins.north.mqtt_client.adapters.base import BaseAdapter
from xagent.plugins.north.mqtt_client.adapters import (
    register,
    get_adapter,
    list_adapters,
    list_customer_codes,
)
from xagent.plugins.north.mqtt_client.adapters.standard import StandardAdapter
from xagent.plugins.north.mqtt_client.adapters.customer_a import CustomerAAdapter


# ===== 测试数据 =====

@pytest.fixture
def sample_reading():
    """创建示例Reading对象"""
    return Reading(
        asset="device_01",
        timestamp=1704067200.0,  # 2024-01-01 00:00:00 UTC
        service_name="temperature_service",
        data={"temperature": 25.5, "humidity": 60.0},
        device_status="online",
        tags={"location": "factory"},
        standard_points=[
            {"point_name": "temp", "value": 25.5, "quality": 192},
            {"point_name": "humi", "value": 60.0, "quality": 192},
        ],
    )


@pytest.fixture
def sample_readings(sample_reading):
    """创建多个Reading对象"""
    return [
        sample_reading,
        Reading(
            asset="device_02",
            timestamp=1704067260.0,
            service_name="temperature_service",
            data={"temperature": 26.0, "humidity": 58.0},
            device_status="online",
        ),
    ]


# ===== 测试适配器注册表 =====

class TestAdapterRegistry:
    """测试适配器注册表"""

    def test_list_adapters(self):
        """测试列出所有适配器"""
        adapters = list_adapters()
        assert "standard" in adapters
        assert "customer_a" in adapters

    def test_get_standard_adapter(self):
        """测试获取标准适配器"""
        adapter = get_adapter("standard")
        assert isinstance(adapter, StandardAdapter)

    def test_get_standard_adapter_with_config(self):
        """测试获取标准适配器（带配置）"""
        config = {
            "timestamp_format": "iso8601",
            "property_mapping": {"temperature": "temp"},
        }
        adapter = get_adapter("standard", config)
        assert isinstance(adapter, StandardAdapter)
        assert adapter._timestamp_format == "iso8601"
        assert adapter._property_mapping == {"temperature": "temp"}

    def test_get_customer_a_adapter(self):
        """测试获取客户A适配器"""
        adapter = get_adapter("customer_a")
        assert isinstance(adapter, CustomerAAdapter)

    def test_get_customer_a_adapter_with_config(self):
        """测试获取客户A适配器（带配置）"""
        config = {"productKey": "al12345****"}
        adapter = get_adapter("customer_a", config)
        assert isinstance(adapter, CustomerAAdapter)
        assert adapter._config.get("productKey") == "al12345****"

    def test_get_nonexistent_adapter(self):
        """测试获取不存在的适配器"""
        with pytest.raises(ValueError) as exc_info:
            get_adapter("nonexistent")
        assert "Adapter 'nonexistent' not found" in str(exc_info.value)

    def test_get_adapter_by_customer_code(self):
        """测试通过客户编号获取适配器"""
        adapter = get_adapter("C001")
        assert isinstance(adapter, CustomerAAdapter)

    def test_get_adapter_by_customer_code_with_config(self):
        """测试通过客户编号获取适配器（带配置）"""
        config = {"productKey": "al12345****"}
        adapter = get_adapter("C001", config)
        assert isinstance(adapter, CustomerAAdapter)
        assert adapter._config.get("productKey") == "al12345****"

    def test_list_customer_codes(self):
        """测试列出客户编号映射"""
        codes = list_customer_codes()
        assert "C001" in codes
        assert codes["C001"] == "customer_a"

    def test_register_with_customer_code(self):
        """测试注册带客户编号的适配器"""
        @register("test_with_code", customer_code="T999")
        class TestCodeAdapter(BaseAdapter):
            pass

        # 通过编号查找
        adapter = get_adapter("T999")
        assert isinstance(adapter, TestCodeAdapter)

        # 通过名称也能查找
        adapter = get_adapter("test_with_code")
        assert isinstance(adapter, TestCodeAdapter)

        # 编号映射正确
        codes = list_customer_codes()
        assert codes["T999"] == "test_with_code"

    def test_register_decorator(self):
        """测试注册装饰器"""
        @register("test_adapter_v2")
        class TestAdapter(BaseAdapter):
            pass

        adapters = list_adapters()
        assert "test_adapter_v2" in adapters

        adapter = get_adapter("test_adapter_v2")
        assert isinstance(adapter, TestAdapter)


# ===== 测试标准适配器 =====

class TestStandardAdapter:
    """测试标准适配器"""

    def test_adapt_upload_single(self, sample_reading):
        """测试单条数据上传"""
        config = {
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload([sample_reading])

        assert len(packets) == 1
        packet = packets[0]
        assert isinstance(packet, PublishPacket)
        assert packet.topic == "xagent/data"
        assert packet.payload["asset"] == "device_01"
        assert packet.payload["timestamp"] == 1704067200.0
        assert packet.payload["service_name"] == "temperature_service"
        assert packet.payload["data"] == {"temperature": 25.5, "humidity": 60.0}
        assert packet.payload["device_status"] == "online"
        assert packet.payload["tags"] == {"location": "factory"}
        assert "standard_points" in packet.payload

    def test_adapt_upload_batch(self, sample_readings):
        """测试批量数据上传"""
        config = {
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload(sample_readings)

        assert len(packets) == 1
        packet = packets[0]
        assert packet.payload["count"] == 2
        assert len(packet.payload["readings"]) == 2
        assert packet.payload["readings"][0]["asset"] == "device_01"
        assert packet.payload["readings"][1]["asset"] == "device_02"

    def test_adapt_upload_empty(self):
        """测试空数据上传"""
        adapter = get_adapter("standard")

        with pytest.raises(DataConversionError):
            adapter.adapt_upload([])

    def test_timestamp_format_iso8601(self, sample_reading):
        """测试ISO8601时间戳格式"""
        config = {
            "timestamp_format": "iso8601",
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload([sample_reading])

        expected_ts = datetime.fromtimestamp(1704067200.0, tz=timezone.utc).isoformat()
        assert packets[0].payload["timestamp"] == expected_ts

    def test_timestamp_format_milliseconds(self, sample_reading):
        """测试毫秒时间戳格式"""
        config = {
            "timestamp_format": "milliseconds",
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload([sample_reading])

        assert packets[0].payload["timestamp"] == 1704067200000

    def test_property_mapping(self, sample_reading):
        """测试属性映射"""
        config = {
            "property_mapping": {"temperature": "temp", "humidity": "humi"},
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload([sample_reading])

        assert packets[0].payload["data"] == {"temp": 25.5, "humi": 60.0}

    def test_device_name_mapping(self, sample_reading):
        """测试设备名映射"""
        config = {
            "device_name_mapping": {"device_01": "SENSOR-001"},
            "topic_templates": {"property_up": "xagent/data"},
        }
        adapter = get_adapter("standard", config)

        packets = adapter.adapt_upload([sample_reading])

        assert packets[0].payload["asset"] == "SENSOR-001"

    def test_parse_command(self):
        """测试命令解析"""
        adapter = get_adapter("standard")

        raw = {"asset": "device_01", "data": {"temperature": 30}}
        context = CommandContext(raw_command=raw, topic="xagent/command", topic_type="command")

        result = adapter.parse_command(raw, context)

        assert isinstance(result, CommandData)
        assert result.asset == "device_01"
        assert result.data == {"temperature": 30}
        assert result.requires_reply is True

    def test_format_result_success(self):
        """测试成功结果格式化"""
        adapter = get_adapter("standard")

        result = CommandResult(
            success=True,
            asset="device_01",
            data={"temperature": 30},
        )
        context = CommandContext(
            raw_command={"asset": "device_01", "data": {"temperature": 30}},
            topic="xagent/command",
            topic_type="command",
        )
        response = adapter.format_result(result, context)

        assert isinstance(response, ResponsePacket)
        assert response.payload["status"] == "success"
        assert response.payload["asset"] == "device_01"
        assert response.payload["data"] == {"temperature": 30}

    def test_format_result_error(self):
        """测试错误结果格式化"""
        adapter = get_adapter("standard")

        result = CommandResult(
            success=False,
            error="Command failed",
        )
        context = CommandContext(
            raw_command={},
            topic="xagent/command",
            topic_type="command",
        )
        response = adapter.format_result(result, context)

        assert response.payload["status"] == "error"
        assert response.payload["error"] == "Command failed"

    def test_to_json(self):
        """测试JSON序列化"""
        adapter = get_adapter("standard")

        data = {"asset": "device_01", "temperature": 25.5}
        json_str = adapter.to_json(data)

        assert '"asset": "device_01"' in json_str
        assert '"temperature": 25.5' in json_str


# ===== 测试客户A适配器 =====

class TestCustomerAAdapter:
    """测试客户A适配器"""

    def _make_customer_a_adapter(self, **extra_config):
        config = {
            "productKey": "al12345****",
            "deviceSN": "gateway01",
            "topic_templates": {
                "property_up": "$v1/{productKey}/{deviceSN}/sys/property/up",
                "connect": "$v1/{productKey}/{deviceSN}/sys/subdevice/connect",
                "disconnect": "$v1/{productKey}/{deviceSN}/sys/subdevice/disconnect",
            },
            "upload_type_map": {
                "property": "property_up",
                "connect": "connect",
                "disconnect": "disconnect",
            },
            **extra_config,
        }
        return get_adapter("customer_a", config)

    def test_adapt_upload_normal_data(self, sample_reading):
        """测试普通数据上报"""
        adapter = self._make_customer_a_adapter()

        # device_status不是online/offline → property
        reading = Reading(
            asset=sample_reading.asset,
            timestamp=sample_reading.timestamp,
            service_name=sample_reading.service_name,
            data=sample_reading.data,
            device_status="normal",
        )

        packets = adapter.adapt_upload([reading])

        assert len(packets) == 1
        packet = packets[0]
        assert isinstance(packet, PublishPacket)
        assert "$v1/al12345****/gateway01/sys/property/up" == packet.topic
        assert "msgid" in packet.payload
        assert "params" in packet.payload

        # 验证点位数据格式
        params = packet.payload["params"]
        assert "temperature" in params
        temp_data = params["temperature"]
        assert "value" in temp_data
        assert "ts" in temp_data
        assert temp_data["value"] == 25.5
        assert temp_data["ts"] == 1704067200000

    def test_adapt_upload_device_online(self):
        """测试设备上线上报"""
        adapter = self._make_customer_a_adapter()

        reading = Reading(
            asset="device1234",
            timestamp=1524448722.0,
            service_name="device_service",
            data={},
            device_status="online",
        )

        packets = adapter.adapt_upload([reading])

        assert len(packets) == 1
        packet = packets[0]
        assert "connect" in packet.topic
        assert packet.payload["params"]["productKey"] == "al12345****"
        assert packet.payload["params"]["deviceSN"] == "device1234"

    def test_adapt_upload_device_offline(self):
        """测试设备下线上报"""
        adapter = self._make_customer_a_adapter()

        reading = Reading(
            asset="device1234",
            timestamp=1524448722.0,
            service_name="device_service",
            data={},
            device_status="offline",
        )

        packets = adapter.adapt_upload([reading])

        assert len(packets) == 1
        packet = packets[0]
        assert "disconnect" in packet.topic
        assert packet.payload["params"]["productKey"] == "al12345****"
        assert packet.payload["params"]["deviceSN"] == "device1234"

    def test_adapt_upload_mixed_types(self):
        """测试批量混合类型上报"""
        adapter = self._make_customer_a_adapter()

        readings = [
            Reading(asset="sensor_01", timestamp=1704067200.0, service_name="s1", data={"Temp": 37.0}),
            Reading(asset="sub_dev_01", timestamp=1704067200.0, service_name="s1", data={}, device_status="online"),
            Reading(asset="sensor_02", timestamp=1704067200.0, service_name="s1", data={"Humidity": 65.0}),
        ]

        packets = adapter.adapt_upload(readings)

        # 应该有2个packet：property组 + connect组
        assert len(packets) == 2

        # 找到property和connect的packet
        topics = [p.topic for p in packets]
        assert any("property/up" in t for t in topics)
        assert any("connect" in t for t in topics)

    def test_msgid_increment(self, sample_reading):
        """测试msgid递增"""
        adapter = self._make_customer_a_adapter()

        reading = Reading(
            asset=sample_reading.asset,
            timestamp=sample_reading.timestamp,
            service_name=sample_reading.service_name,
            data=sample_reading.data,
        )

        packets1 = adapter.adapt_upload([reading])
        packets2 = adapter.adapt_upload([reading])

        msgid1 = int(packets1[0].payload["msgid"])
        msgid2 = int(packets2[0].payload["msgid"])

        assert msgid2 == msgid1 + 1

    def test_msgid_range(self, sample_reading):
        """测试msgid范围限制"""
        adapter = self._make_customer_a_adapter()
        adapter._msgid_counter = 4294967295

        reading = Reading(
            asset=sample_reading.asset,
            timestamp=sample_reading.timestamp,
            service_name=sample_reading.service_name,
            data=sample_reading.data,
        )

        packets = adapter.adapt_upload([reading])

        assert packets[0].payload["msgid"] == "0"

    def test_parse_command_property_down(self):
        """测试命令解析 - 写属性"""
        adapter = self._make_customer_a_adapter()

        raw = {"msgid": "123456", "params": {"Temperature": "37.0"}}
        context = CommandContext(raw_command=raw, topic=".../property/down", topic_type="property_down")

        result = adapter.parse_command(raw, context)

        assert isinstance(result, CommandData)
        assert result.asset == ""
        assert result.data == {"Temperature": "37.0"}
        assert result.requires_reply is True

    def test_parse_command_connect_reply(self):
        """测试命令解析 - 设备上线回复（不需要回复）"""
        adapter = self._make_customer_a_adapter()

        raw = {
            "msgid": "123456",
            "code": 0,
            "message": "success",
            "data": {"productKey": "al12345****", "deviceSN": "device1234"},
        }
        context = CommandContext(raw_command=raw, topic=".../connect_reply", topic_type="connect_reply")

        result = adapter.parse_command(raw, context)

        assert isinstance(result, CommandData)
        assert result.asset == "device1234"
        assert result.command_type == "device_status"
        assert result.requires_reply is False

    def test_format_result_success(self):
        """测试成功结果格式化 - 写属性"""
        adapter = self._make_customer_a_adapter()

        result = CommandResult(
            success=True,
            asset="",
            data={"Temperature": "37.0"},
        )
        context = CommandContext(
            raw_command={"msgid": "123456", "params": {"Temperature": "37.0"}},
            topic=".../property/down",
            topic_type="property_down",
        )
        response = adapter.format_result(result, context)

        assert isinstance(response, ResponsePacket)
        assert response.payload["msgid"] == "123456"
        assert response.payload["code"] == 0
        assert response.payload["data"] == {}

    def test_format_result_error(self):
        """测试错误结果格式化 - 写属性"""
        adapter = self._make_customer_a_adapter()

        result = CommandResult(
            success=False,
            error="Write failed",
        )
        context = CommandContext(
            raw_command={"msgid": "123456", "params": {"Temperature": "37.0"}},
            topic=".../property/down",
            topic_type="property_down",
        )
        response = adapter.format_result(result, context)

        assert response.payload["msgid"] == "123456"
        assert response.payload["code"] == -1


# ===== 测试基类 =====

class TestBaseAdapter:
    """测试适配器基类"""

    def test_adapt_upload_returns_list(self, sample_reading):
        """测试adapt_upload返回List[PublishPacket]"""
        config = {"topic_templates": {"property_up": "xagent/data"}}
        adapter = BaseAdapter(config)

        packets = adapter.adapt_upload([sample_reading])

        assert isinstance(packets, list)
        assert len(packets) == 1
        assert isinstance(packets[0], PublishPacket)

    def test_adapt_upload_empty_raises(self):
        """测试空数据上传抛出异常"""
        adapter = BaseAdapter({})

        with pytest.raises(DataConversionError):
            adapter.adapt_upload([])

    def test_parse_command_default(self):
        """测试默认命令解析"""
        adapter = BaseAdapter({})

        raw = {"asset": "device_01", "data": {"temperature": 30}}
        context = CommandContext(raw_command=raw, topic="test/topic", topic_type="command")

        result = adapter.parse_command(raw, context)

        assert isinstance(result, CommandData)
        assert result.asset == "device_01"
        assert result.data == {"temperature": 30}
        assert result.requires_reply is True

    def test_format_result_default(self):
        """测试默认结果格式化"""
        adapter = BaseAdapter({})

        result = CommandResult(success=True, asset="device_01", data={"temperature": 30})
        context = CommandContext(
            raw_command={"asset": "device_01"},
            topic="test/command",
            topic_type="command",
        )
        response = adapter.format_result(result, context)

        assert isinstance(response, ResponsePacket)
        assert response.payload["status"] == "success"
        assert response.payload["asset"] == "device_01"

    def test_to_json(self):
        """测试JSON序列化"""
        adapter = BaseAdapter({})

        data = {"asset": "device_01", "temperature": 25.5}
        json_str = adapter.to_json(data)

        assert '"asset": "device_01"' in json_str

    def test_get_subscribe_topics_config_driven(self):
        """测试配置驱动的订阅topic"""
        config = {
            "topic_templates": {
                "property_down": "$v1/{productKey}/{deviceSN}/sys/property/down",
            },
            "subscribe_types": ["property_down"],
            "productKey": "al12345",
            "deviceSN": "gw01",
        }
        adapter = BaseAdapter(config)

        topics = adapter.get_subscribe_topics()

        assert len(topics) == 1
        assert topics[0] == "$v1/al12345/gw01/sys/property/down"

    def test_parse_topic_type_config_driven(self):
        """测试配置驱动的topic类型解析"""
        config = {
            "topic_type_rules": {
                "/sys/property/down": "property_down",
                "/sys/subdevice/connect_reply": "connect_reply",
            }
        }
        adapter = BaseAdapter(config)

        assert adapter.parse_topic_type("$v1/pk/sn/sys/property/down") == "property_down"
        assert adapter.parse_topic_type("$v1/pk/sn/sys/subdevice/connect_reply") == "connect_reply"
        assert adapter.parse_topic_type("unknown/topic") == "unknown"

    def test_upload_type_map_config_driven(self):
        """测试配置驱动的upload_type映射"""
        config = {
            "upload_type_map": {"property": "data"},
            "topic_templates": {"data": "device/{deviceSN}/data"},
            "deviceSN": "sn123",
        }
        adapter = BaseAdapter(config)

        topic = adapter._get_publish_topic("property")
        assert topic == "device/sn123/data"

    def test_topic_context_filters_basic_types(self):
        """测试_topic_context只返回基本类型值"""
        config = {
            "productKey": "al12345",
            "deviceSN": "gw01",
            "topic_templates": {"some": "template"},
            "subscribe_types": ["property_down"],
        }
        adapter = BaseAdapter(config)

        ctx = adapter._topic_context("property")

        assert "productKey" in ctx
        assert "deviceSN" in ctx
        assert "topic_templates" not in ctx
        assert "subscribe_types" not in ctx


# ===== 测试异常层次 =====

class TestExceptions:
    """测试异常层次"""

    def test_exception_hierarchy(self):
        """测试异常继承关系"""
        assert issubclass(DataConversionError, MQTTAdapterError)
        assert issubclass(TopicError, MQTTAdapterError)
        assert issubclass(CommandParseError, MQTTAdapterError)

    def test_topic_error_on_missing_template(self):
        """测试缺少topic模板时抛出TopicError"""
        adapter = BaseAdapter({})

        with pytest.raises(TopicError):
            adapter._get_publish_topic("property")


# ===== 测试类型定义 =====

class TestTypes:
    """测试核心类型定义"""

    def test_publish_packet(self):
        """测试PublishPacket"""
        packet = PublishPacket(topic="test/topic", payload={"key": "value"})
        assert packet.topic == "test/topic"
        assert packet.payload == {"key": "value"}

    def test_command_data_defaults(self):
        """测试CommandData默认值"""
        cmd = CommandData(asset="device_01", data={"temp": 30})
        assert cmd.command_type == "write_property"
        assert cmd.requires_reply is True

    def test_command_data_no_reply(self):
        """测试CommandData不需要回复"""
        cmd = CommandData(asset="device_01", data={}, requires_reply=False)
        assert cmd.requires_reply is False

    def test_command_context(self):
        """测试CommandContext"""
        ctx = CommandContext(
            raw_command={"msgid": "123"},
            topic="test/topic",
            topic_type="property_down",
        )
        assert ctx.raw_command == {"msgid": "123"}
        assert ctx.topic == "test/topic"
        assert ctx.topic_type == "property_down"

    def test_command_result(self):
        """测试CommandResult"""
        result = CommandResult(success=True, asset="device_01", data={"temp": 30})
        assert result.success is True
        assert result.asset == "device_01"
        assert result.error is None

    def test_response_packet(self):
        """测试ResponsePacket"""
        packet = ResponsePacket(topic="test/reply", payload={"code": 0})
        assert packet.topic == "test/reply"
        assert packet.payload == {"code": 0}
