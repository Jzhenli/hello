"""MQTT Adapter Tests - 测试适配器重构的正确性"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import Mock, AsyncMock

from xagent.xcore.storage.interface import Reading
from xagent.plugins.north.mqtt_client.adapter import (
    MQTTAdapterBase,
    MQTTAdapterProtocol,
    DownlinkResult,
    _handle_adapter_errors,
)
from xagent.plugins.north.mqtt_client.adapters import (
    register,
    get_adapter,
    list_adapters,
)
from xagent.plugins.north.mqtt_client.adapters.standard import MQTTClientAdapter
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
        assert isinstance(adapter, MQTTClientAdapter)
        assert adapter.config == {}

    def test_get_standard_adapter_with_config(self):
        """测试获取标准适配器（带配置）"""
        config = {
            "timestamp_format": "iso8601",
            "property_mapping": {"temperature": "temp"},
        }
        adapter = get_adapter("standard", config)
        assert isinstance(adapter, MQTTClientAdapter)
        assert adapter._timestamp_format == "iso8601"
        assert adapter._property_mapping == {"temperature": "temp"}

    def test_get_customer_a_adapter(self):
        """测试获取客户A适配器"""
        adapter = get_adapter("customer_a")
        assert isinstance(adapter, CustomerAAdapter)

    def test_get_customer_a_adapter_with_config(self):
        """测试获取客户A适配器（带配置）"""
        config = {"sn_prefix": "SN-"}
        adapter = get_adapter("customer_a", config)
        assert isinstance(adapter, CustomerAAdapter)
        assert adapter._sn_prefix == "SN-"

    def test_get_nonexistent_adapter(self):
        """测试获取不存在的适配器"""
        with pytest.raises(ValueError) as exc_info:
            get_adapter("nonexistent")
        assert "Adapter 'nonexistent' not found" in str(exc_info.value)

    def test_register_decorator(self):
        """测试注册装饰器"""
        @register("test_adapter")
        class TestAdapter(MQTTAdapterBase):
            pass

        adapters = list_adapters()
        assert "test_adapter" in adapters

        adapter = get_adapter("test_adapter")
        assert isinstance(adapter, TestAdapter)


# ===== 测试标准适配器 =====

class TestStandardAdapter:
    """测试标准适配器"""

    def test_adapt_upload_single(self, sample_reading):
        """测试单条数据上传"""
        adapter = get_adapter("standard")
        context = {"timestamp": 1704067200.0}

        result = adapter.adapt_upload([sample_reading], context)

        assert result is not None
        assert result["asset"] == "device_01"
        assert result["timestamp"] == 1704067200.0
        assert result["service_name"] == "temperature_service"
        assert result["data"] == {"temperature": 25.5, "humidity": 60.0}
        assert result["device_status"] == "online"
        assert result["tags"] == {"location": "factory"}
        assert "standard_points" in result

    def test_adapt_upload_batch(self, sample_readings):
        """测试批量数据上传"""
        adapter = get_adapter("standard")
        context = {"timestamp": 1704067200.0}

        result = adapter.adapt_upload(sample_readings, context)

        assert result is not None
        assert result["count"] == 2
        assert len(result["readings"]) == 2
        assert result["readings"][0]["asset"] == "device_01"
        assert result["readings"][1]["asset"] == "device_02"

    def test_adapt_upload_empty(self):
        """测试空数据上传"""
        adapter = get_adapter("standard")
        result = adapter.adapt_upload([], {})
        assert result is None

    def test_timestamp_format_iso8601(self, sample_reading):
        """测试ISO8601时间戳格式"""
        config = {"timestamp_format": "iso8601"}
        adapter = get_adapter("standard", config)
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        expected_ts = datetime.fromtimestamp(1704067200.0, tz=timezone.utc).isoformat()
        assert result["timestamp"] == expected_ts

    def test_timestamp_format_milliseconds(self, sample_reading):
        """测试毫秒时间戳格式"""
        config = {"timestamp_format": "milliseconds"}
        adapter = get_adapter("standard", config)
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        assert result["timestamp"] == 1704067200000

    def test_property_mapping(self, sample_reading):
        """测试属性映射"""
        config = {
            "property_mapping": {
                "temperature": "temp",
                "humidity": "humi",
            }
        }
        adapter = get_adapter("standard", config)
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        assert result["data"] == {"temp": 25.5, "humi": 60.0}

    def test_device_name_mapping(self, sample_reading):
        """测试设备名映射"""
        config = {
            "device_name_mapping": {
                "device_01": "SENSOR-001",
            }
        }
        adapter = get_adapter("standard", config)
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        assert result["asset"] == "SENSOR-001"

    def test_parse_command(self):
        """测试命令解析"""
        adapter = get_adapter("standard")

        raw = {"asset": "device_01", "data": {"temperature": 30}}
        result = adapter.parse_command(raw)

        assert result["asset"] == "device_01"
        assert result["data"] == {"temperature": 30}

    def test_format_result_success(self):
        """测试成功结果格式化"""
        adapter = get_adapter("standard")

        result = DownlinkResult(
            success=True,
            asset="device_01",
            data={"temperature": 30},
            raw_command={"asset": "device_01", "data": {"temperature": 30}},
        )
        response = adapter.format_result(result)

        assert response["status"] == "success"
        assert response["asset"] == "device_01"
        assert response["data"] == {"temperature": 30}
        assert "timestamp" in response

    def test_format_result_error(self):
        """测试错误结果格式化"""
        adapter = get_adapter("standard")

        result = DownlinkResult(
            success=False,
            error="Command failed",
            raw_command={},
        )
        response = adapter.format_result(result)

        assert response["status"] == "error"
        assert response["error"] == "Command failed"

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

    def test_adapt_upload_single(self, sample_reading):
        """测试单条数据上报 - 普通数据"""
        adapter = get_adapter("customer_a")
        context = {}

        # 修改device_status为normal，表示普通数据上报
        reading = Reading(
            asset=sample_reading.asset,
            timestamp=sample_reading.timestamp,
            service_name=sample_reading.service_name,
            data=sample_reading.data,
            device_status="normal",  # 不是online/offline
            tags=sample_reading.tags,
            standard_points=sample_reading.standard_points,
        )

        result = adapter.adapt_upload([reading], context)

        # 验证普通数据格式
        assert result is not None
        assert "msgid" in result
        assert "params" in result

        # 验证msgid是字符串类型的数字
        assert isinstance(result["msgid"], str)
        msgid_int = int(result["msgid"])
        assert 0 <= msgid_int <= 4294967295

        # 验证params格式
        params = result["params"]
        assert "temperature" in params
        assert "humidity" in params

        # 验证点位数据格式
        temp_data = params["temperature"]
        assert "value" in temp_data
        assert "ts" in temp_data
        assert temp_data["value"] == 25.5
        assert temp_data["ts"] == 1704067200000  # 毫秒时间戳

    def test_adapt_upload_device_online(self):
        """测试设备上线上报"""
        adapter = get_adapter("customer_a")
        context = {"productKey": "al12345****"}

        # 创建设备上线的Reading
        reading = Reading(
            asset="device1234",
            timestamp=1524448722.0,
            service_name="device_service",
            data={},
            device_status="online",  # 设备上线
        )

        result = adapter.adapt_upload([reading], context)

        # 验证设备上线格式
        assert result is not None
        assert "msgid" in result
        assert "params" in result

        # 验证params包含productKey和deviceSN
        params = result["params"]
        assert "productKey" in params
        assert "deviceSN" in params
        assert params["productKey"] == "al12345****"
        assert params["deviceSN"] == "device1234"

    def test_adapt_upload_device_offline(self):
        """测试设备下线上报"""
        adapter = get_adapter("customer_a")
        context = {"productKey": "al12345****"}

        # 创建设备下线的Reading
        reading = Reading(
            asset="device1234",
            timestamp=1524448722.0,
            service_name="device_service",
            data={},
            device_status="offline",  # 设备下线
        )

        result = adapter.adapt_upload([reading], context)

        # 验证设备下线格式
        assert result is not None
        assert "msgid" in result
        assert "params" in result

        # 验证params包含productKey和deviceSN
        params = result["params"]
        assert "productKey" in params
        assert "deviceSN" in params
        assert params["productKey"] == "al12345****"
        assert params["deviceSN"] == "device1234"

    def test_adapt_upload_batch(self, sample_readings):
        """测试批量数据上传 - 合并到同一个params"""
        adapter = get_adapter("customer_a")
        context = {}

        # 修改device_status为normal，表示普通数据上报
        readings = [
            Reading(
                asset=r.asset,
                timestamp=r.timestamp,
                service_name=r.service_name,
                data=r.data,
                device_status="normal",  # 不是online/offline
                tags=r.tags,
                standard_points=r.standard_points,
            )
            for r in sample_readings
        ]

        result = adapter.adapt_upload(readings, context)

        # 验证返回单个对象（不是数组）
        assert isinstance(result, dict)
        assert "msgid" in result
        assert "params" in result

        # 验证所有点位都被合并
        params = result["params"]
        assert "temperature" in params
        assert "humidity" in params

    def test_msgid_increment(self, sample_reading):
        """测试msgid递增"""
        adapter = get_adapter("customer_a")
        context = {}

        result1 = adapter.adapt_upload([sample_reading], context)
        result2 = adapter.adapt_upload([sample_reading], context)

        msgid1 = int(result1["msgid"])
        msgid2 = int(result2["msgid"])

        # 验证msgid递增
        assert msgid2 == msgid1 + 1

    def test_msgid_range(self, sample_reading):
        """测试msgid范围限制"""
        adapter = get_adapter("customer_a")
        adapter._msgid_counter = 4294967295  # 设置为最大值
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        # 验证msgid回到0（循环）
        assert result["msgid"] == "0"

    def test_parse_command(self):
        """测试命令解析 - 写属性"""
        adapter = get_adapter("customer_a")

        raw = {"msgid": "123456", "params": {"Temperature": "37.0"}}
        result = adapter.parse_command(raw)

        # 验证解析结果
        assert result["asset"] == ""
        assert result["data"] == {"Temperature": "37.0"}

    def test_format_result_success(self):
        """测试成功结果格式化 - 写属性"""
        adapter = get_adapter("customer_a")

        result = DownlinkResult(
            success=True,
            asset="",
            data={"Temperature": "37.0"},
            raw_command={"msgid": "123456", "params": {"Temperature": "37.0"}},
        )
        response = adapter.format_result(result)

        # 验证回复格式
        assert response["msgid"] == "123456"
        assert response["code"] == 0
        assert response["data"] == {}

    def test_format_result_error(self):
        """测试错误结果格式化 - 写属性"""
        adapter = get_adapter("customer_a")

        result = DownlinkResult(
            success=False,
            asset="",
            error="Write failed",
            raw_command={"msgid": "123456", "params": {"Temperature": "37.0"}},
        )
        response = adapter.format_result(result)

        # 验证回复格式
        assert response["msgid"] == "123456"
        assert response["code"] == -1
        assert response["data"] == {}

    def test_parse_response_device_status(self):
        """测试解析云平台回复 - 设备上线/下线"""
        adapter = get_adapter("customer_a")

        response = {
            "msgid": "123456",
            "code": 0,
            "message": "success",
            "data": {
                "productKey": "al12345****",
                "deviceSN": "device1234"
            }
        }
        parsed = adapter.parse_response(response, {})

        # 验证解析结果
        assert parsed["msgid"] == "123456"
        assert parsed["code"] == 0
        assert parsed["message"] == "success"
        assert parsed["data"]["productKey"] == "al12345****"
        assert parsed["data"]["deviceSN"] == "device1234"

    def test_parse_response_write_property(self):
        """测试解析云平台回复 - 写属性"""
        adapter = get_adapter("customer_a")

        response = {
            "msgid": "123456",
            "code": 0,
            "data": {}
        }
        parsed = adapter.parse_response(response, {})

        # 验证解析结果
        assert parsed["msgid"] == "123456"
        assert parsed["code"] == 0
        assert parsed["data"] == {}


# ===== 测试基类 =====

class TestMQTTAdapterBase:
    """测试适配器基类"""

    def test_adapt_upload_single(self, sample_reading):
        """测试单条数据上传"""
        adapter = MQTTAdapterBase()
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        assert result is not None
        assert result["asset"] == "device_01"
        assert result["timestamp"] == 1704067200.0
        assert result["service_name"] == "temperature_service"
        assert result["data"] == {"temperature": 25.5, "humidity": 60.0}

    def test_adapt_upload_batch(self, sample_readings):
        """测试批量数据上传"""
        adapter = MQTTAdapterBase()
        context = {}

        result = adapter.adapt_upload(sample_readings, context)

        assert result is not None
        assert result["count"] == 2
        assert len(result["readings"]) == 2

    def test_adapt_upload_empty(self):
        """测试空数据上传"""
        adapter = MQTTAdapterBase()
        result = adapter.adapt_upload([], {})
        assert result is None

    def test_parse_command(self):
        """测试命令解析"""
        adapter = MQTTAdapterBase()

        raw = {"asset": "device_01", "data": {"temperature": 30}}
        result = adapter.parse_command(raw)

        assert result["asset"] == "device_01"
        assert result["data"] == {"temperature": 30}

    def test_format_result(self):
        """测试结果格式化"""
        adapter = MQTTAdapterBase()

        result = DownlinkResult(
            success=True,
            asset="device_01",
            data={"temperature": 30},
        )
        response = adapter.format_result(result)

        assert response["status"] == "success"
        assert response["asset"] == "device_01"
        assert "timestamp" in response

    def test_to_json(self):
        """测试JSON序列化"""
        adapter = MQTTAdapterBase()

        data = {"asset": "device_01", "temperature": 25.5}
        json_str = adapter.to_json(data)

        assert '"asset": "device_01"' in json_str

    def test_parse_response_dict(self):
        """测试解析字典响应"""
        adapter = MQTTAdapterBase()

        response = {"status": "success", "data": {"temperature": 30}}
        result = adapter.parse_response(response, {})

        assert result == response

    def test_parse_response_bytes(self):
        """测试解析字节响应"""
        adapter = MQTTAdapterBase()

        response = b'{"status": "success"}'
        result = adapter.parse_response(response, {})

        assert result["status"] == "success"

    def test_parse_response_string(self):
        """测试解析字符串响应"""
        adapter = MQTTAdapterBase()

        response = '{"status": "success"}'
        result = adapter.parse_response(response, {})

        assert result["status"] == "success"


# ===== 测试异常处理装饰器 =====

class TestHandleAdapterErrors:
    """测试异常处理装饰器"""

    def test_success(self):
        """测试正常执行"""
        class TestAdapter(MQTTAdapterBase):
            @_handle_adapter_errors
            def test_method(self, value):
                return value * 2

        adapter = TestAdapter()
        result = adapter.test_method(5)

        assert result == 10

    def test_exception(self):
        """测试异常处理"""
        class TestAdapter(MQTTAdapterBase):
            @_handle_adapter_errors
            def test_method(self, value):
                raise ValueError("Test error")

        adapter = TestAdapter()
        result = adapter.test_method(5)

        assert result is None


# ===== 测试类型协议 =====

class TestMQTTAdapterProtocol:
    """测试类型协议"""

    def test_protocol_check(self):
        """测试协议检查"""
        adapter = get_adapter("standard")

        # 运行时检查
        assert isinstance(adapter, MQTTAdapterProtocol)

    def test_customer_a_protocol_check(self):
        """测试客户A适配器协议检查"""
        adapter = get_adapter("customer_a")

        # 运行时检查
        assert isinstance(adapter, MQTTAdapterProtocol)


# ===== 测试向后兼容性 =====

class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_standard_adapter_default_behavior(self, sample_reading):
        """测试标准适配器默认行为与重构前一致"""
        adapter = get_adapter("standard")
        context = {}

        result = adapter.adapt_upload([sample_reading], context)

        # 验证默认行为
        assert result["asset"] == sample_reading.asset
        assert result["timestamp"] == sample_reading.timestamp
        assert result["service_name"] == sample_reading.service_name
        assert result["data"] == sample_reading.data
        assert result["device_status"] == sample_reading.device_status

    def test_downlink_result_structure(self):
        """测试DownlinkResult结构"""
        result = DownlinkResult(
            success=True,
            asset="device_01",
            data={"temperature": 30},
            error=None,
            raw_command={"asset": "device_01"},
        )

        assert result.success is True
        assert result.asset == "device_01"
        assert result.data == {"temperature": 30}
        assert result.error is None
        assert result.raw_command == {"asset": "device_01"}
