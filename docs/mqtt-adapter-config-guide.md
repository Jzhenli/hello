# MQTT适配器完整配置指南

## 📋 概述

MQTT适配器支持**完全配置驱动**，无需修改代码即可适配不同客户。

---

## 🎯 配置优先级

```
adapter_config中的配置 > 适配器代码覆盖 > 适配器默认值
```

---

## 📝 完整配置示例

### 客户A（标准配置）

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: customer_a
  adapter_config:
    # 基础配置
    productKey: al12345****
    deviceSN: device1234
    sn_prefix: "SN-"
    
    # Topic模板（可选，使用默认）
    # topic_templates:
    #   property_up: "$v1/{productKey}/{deviceSN}/sys/property/up"
    #   ...
    
    # 订阅Topic类型（可选，使用默认）
    # subscribe_topic_types:
    #   - property_down
    #   - connect_reply
    #   - disconnect_reply
    
    # 回复Topic规则（可选，使用默认）
    # reply_topic_rule: suffix_reply
    
    # Topic类型解析规则（可选，使用默认）
    # topic_type_rules:
    #   "/sys/property/down": property_down
    #   "/sys/subdevice/connect_reply": connect_reply
    #   "/sys/subdevice/disconnect_reply": disconnect_reply
```

---

### 客户B（自定义Topic格式）

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard  # 使用标准适配器
  adapter_config:
    # 基础配置
    productKey: custom_product
    deviceSN: custom_device
    
    # 自定义Topic模板
    topic_templates:
      property_up: "v2/{productKey}/{deviceSN}/data/upload"
      property_down: "v2/{productKey}/{deviceSN}/data/download"
      property_down_reply: "v2/{productKey}/{deviceSN}/data/reply"
      connect: "v2/{productKey}/{deviceSN}/device/online"
      connect_reply: "v2/{productKey}/{deviceSN}/device/online_reply"
      disconnect: "v2/{productKey}/{deviceSN}/device/offline"
      disconnect_reply: "v2/{productKey}/{deviceSN}/device/offline_reply"
    
    # 订阅Topic类型
    subscribe_topic_types:
      - property_down
      - connect_reply
      - disconnect_reply
    
    # 回复Topic规则
    reply_topic_rule: suffix_result  # /down → /down/result
    
    # Topic类型解析规则
    topic_type_rules:
      "/data/download": property_down
      "/device/online_reply": connect_reply
      "/device/offline_reply": disconnect_reply
```

---

### 客户C（极简格式）

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard
  adapter_config:
    # 基础配置（只需要deviceSN）
    deviceSN: device1234
    
    # 极简Topic模板
    topic_templates:
      property_up: "data/{deviceSN}"
      property_down: "cmd/{deviceSN}"
      property_down_reply: "result/{deviceSN}"
    
    # 订阅Topic类型
    subscribe_topic_types:
      - property_down
    
    # 回复Topic规则
    reply_topic_rule: replace_down_with_reply  # /down → /reply
    
    # Topic类型解析规则
    topic_type_rules:
      "/cmd/": property_down
```

---

### 客户D（完全不同的格式）

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  adapter: standard
  adapter_config:
    # 基础配置
    siteId: factory-01
    deviceId: sensor-001
    
    # 自定义Topic模板（使用不同的占位符）
    topic_templates:
      property_up: "site/{siteId}/device/{deviceId}/telemetry"
      property_down: "site/{siteId}/device/{deviceId}/command"
      property_down_reply: "site/{siteId}/device/{deviceId}/response"
    
    # 订阅Topic类型
    subscribe_topic_types:
      - property_down
    
    # 回复Topic规则
    reply_topic_rule: suffix_result
    
    # Topic类型解析规则
    topic_type_rules:
      "/command": property_down
```

---

## 🔧 配置字段说明

### 1. topic_templates

**作用**：定义Topic模板，支持占位符

**格式**：
```yaml
topic_templates:
  property_up: "xxx/{productKey}/{deviceSN}/xxx"
  property_down: "xxx/{productKey}/{deviceSN}/xxx"
  ...
```

**支持的占位符**：
- `{productKey}` - 产品Key
- `{deviceSN}` - 设备序列号
- `{siteId}` - 站点ID
- `{deviceId}` - 设备ID
- 任何自定义字段

---

### 2. subscribe_topic_types

**作用**：定义需要订阅的Topic类型

**格式**：
```yaml
subscribe_topic_types:
  - property_down
  - connect_reply
  - disconnect_reply
```

**说明**：这些类型必须在`topic_templates`中定义。

---

### 3. reply_topic_rule

**作用**：定义回复Topic生成规则

**可选值**：
- `suffix_reply` - 在命令topic后加`_reply`（客户A）
- `suffix_result` - 在命令topic后加`/result`（默认）
- `replace_down_with_reply` - 替换`/down`为`/reply`

**示例**：
```yaml
reply_topic_rule: suffix_reply
```

---

### 4. topic_type_rules

**作用**：定义Topic类型解析规则

**格式**：
```yaml
topic_type_rules:
  "/sys/property/down": property_down
  "/sys/subdevice/connect_reply": connect_reply
  ...
```

**说明**：key是匹配模式（字符串包含匹配），value是Topic类型。

---

## 📊 配置对比

| 客户 | Topic格式 | 配置复杂度 | 是否需要修改代码 |
|------|----------|-----------|----------------|
| 客户A | 标准格式 | 简单 | 否 |
| 客户B | 自定义格式 | 中等 | 否 |
| 客户C | 极简格式 | 简单 | 否 |
| 客户D | 完全不同 | 复杂 | 否 |

---

## 🎉 总结

**核心优势**：

1. ✅ **完全配置驱动** - 无需修改代码
2. ✅ **灵活的优先级** - 配置 > 代码 > 默认
3. ✅ **支持任意格式** - 通过配置定义
4. ✅ **易于维护** - 配置文件管理

**推荐做法**：

- 优先使用**配置**定义客户特定逻辑
- 只在配置无法满足时才**覆盖代码**
- 保持配置文件的**可读性和可维护性**
