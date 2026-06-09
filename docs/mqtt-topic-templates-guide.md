# MQTT适配器Topic模板配置指南

## 📋 概述

Topic模板支持**三种方式**定义：

1. **默认模板**：适配器提供默认的topic模板
2. **配置覆盖**：通过`adapter_config.topic_templates`覆盖默认模板
3. **代码覆盖**：适配器类覆盖`get_topic_templates()`方法

---

## 🎯 方式1：使用默认模板

**适用场景**：客户使用标准的topic格式（如客户A）

**配置示例**：
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: customer_a
  adapter_config:
    productKey: al12345****
    deviceSN: device1234
```

**说明**：
- 不需要定义`topic_templates`
- 使用适配器提供的默认模板

---

## 🎯 方式2：通过配置覆盖模板

**适用场景**：客户有自定义的topic格式，但不想修改代码

**配置示例**：
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard  # 使用标准适配器
  adapter_config:
    productKey: al12345****
    deviceSN: device1234
    # 自定义topic模板
    topic_templates:
      # 上行：网关→云平台
      property_up: "custom/{productKey}/{deviceSN}/data/upload"
      connect: "custom/{productKey}/{deviceSN}/device/online"
      disconnect: "custom/{productKey}/{deviceSN}/device/offline"
      property_down_reply: "custom/{productKey}/{deviceSN}/data/reply"
      
      # 下行：云平台→网关
      property_down: "custom/{productKey}/{deviceSN}/data/download"
      connect_reply: "custom/{productKey}/{deviceSN}/device/online_reply"
      disconnect_reply: "custom/{productKey}/{deviceSN}/device/offline_reply"
```

**说明**：
- 通过`adapter_config.topic_templates`定义自定义模板
- 支持占位符：`{productKey}`, `{deviceSN}`
- 优先级高于适配器默认模板

---

## 🎯 方式3：代码覆盖模板

**适用场景**：客户有固定的topic格式，需要硬编码

**代码示例**：
```python
# adapters/customer_b.py
from ..adapter import MQTTAdapterBase, register

@register("customer_b")
class CustomerBAdapter(MQTTAdapterBase):
    """客户B适配器 - 自定义topic格式"""
    
    def get_topic_templates(self):
        """覆盖：提供客户B特定的topic模板"""
        return {
            "property_up": "device/{deviceSN}/upload",
            "property_down": "device/{deviceSN}/download",
            "property_down_reply": "device/{deviceSN}/reply",
        }
    
    # 其他方法...
```

**配置示例**：
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: customer_b
  adapter_config:
    deviceSN: device1234
```

**说明**：
- 适配器类覆盖`get_topic_templates()`方法
- 硬编码客户特定的topic格式
- 配置中的`topic_templates`优先级更高

---

## 📊 优先级

```
配置中的topic_templates > 适配器代码覆盖 > 适配器默认模板
```

**示例**：
```yaml
adapter_config:
  topic_templates:
    property_up: "config/defined/topic"  # 最高优先级
```

即使适配器代码中覆盖了`get_topic_templates()`，配置中的模板仍然优先。

---

## 🔧 完整配置示例

### 客户A（使用默认模板）
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: customer_a
  adapter_config:
    productKey: al12345****
    deviceSN: device1234
    # 不需要定义topic_templates，使用默认
```

### 客户B（自定义模板）
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard
  adapter_config:
    productKey: custom_product
    deviceSN: custom_device
    topic_templates:
      property_up: "v2/{productKey}/{deviceSN}/upload"
      property_down: "v2/{productKey}/{deviceSN}/download"
      property_down_reply: "v2/{productKey}/{deviceSN}/reply"
```

### 客户C（极简格式）
```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard
  adapter_config:
    deviceSN: device1234
    topic_templates:
      property_up: "data/{deviceSN}"
      property_down: "cmd/{deviceSN}"
      property_down_reply: "result/{deviceSN}"
```

---

## 🎉 总结

| 方式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **默认模板** | 标准格式客户 | 简单，无需配置 | 不够灵活 |
| **配置覆盖** | 自定义格式客户 | 灵活，无需改代码 | 配置较复杂 |
| **代码覆盖** | 固定格式客户 | 硬编码，类型安全 | 需要修改代码 |

**推荐**：
- 优先使用**默认模板**
- 需要灵活调整时使用**配置覆盖**
- 固定格式时使用**代码覆盖**
