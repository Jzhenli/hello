# 模板设备清理指南

## 问题描述

新部署的系统启动后，数据库中会有模板设备（example_*），这些设备不应该被自动迁移到数据库。

## 原因分析

### 1. 之前的迁移

如果你之前运行过系统，模板设备可能已经被迁移到数据库中。即使现在修改了迁移逻辑，数据库中的设备仍然存在。

### 2. 启动流程

```
启动 → 初始化数据库 → 检查数据库中的设备
  ↓
如果数据库已有设备 → 直接加载（不会再次迁移）
```

## 解决方案

### 方案1：清理数据库中的模板设备（推荐）

#### 步骤1：检查数据库中的设备

```bash
python tools/check_db_devices.py
```

**预期输出**：
```
=== 数据库中的设备 ===
找到 4 个活跃设备:
  - example_knx_device (插件: knx, 启用: True, 状态: active)
  - example_modbus_device (插件: modbus_tcp, 启用: True, 状态: active)
  - example_modbus_rtu_device (插件: modbus_rtu, 启用: True, 状态: active)
  - example_mqtt_north (插件: mqtt_client, 启用: True, 状态: active)

=== 模板设备检查 ===
发现 4 个模板设备:
  - example_knx_device
  - example_modbus_device
  - example_modbus_rtu_device
  - example_mqtt_north
```

#### 步骤2：清理模板设备

```bash
python tools/clean_template_devices.py
```

**预期输出**：
```
=== 清理模板设备 ===
发现 4 个模板设备:
  - example_knx_device
  - example_modbus_device
  - example_modbus_rtu_device
  - example_mqtt_north

确认删除这些模板设备吗？(yes/no): yes

✅ 已删除 4 个模板设备
重启应用后，这些设备将不会加载
```

#### 步骤3：重启应用

重启应用后，系统会从数据库加载设备，模板设备不会被加载。

### 方案2：删除数据库重新初始化

如果你想完全重新开始：

```bash
# 停止应用
# 删除数据库
rm "C:\Users\77127\AppData\Local\adveco\XAgent\data\xagent.db"

# 重启应用
# 系统会创建新的空数据库
```

**注意**：这会删除所有设备配置，包括你自己创建的设备。

### 方案3：通过API删除模板设备

```bash
# 删除单个设备
curl -X DELETE http://localhost:8080/api/devices/example_modbus_device

# 批量删除
for device in example_knx_device example_modbus_device example_modbus_rtu_device example_mqtt_north; do
  curl -X DELETE http://localhost:8080/api/devices/$device
done
```

## 验证清理结果

### 1. 检查数据库

```bash
python tools/check_db_devices.py
```

**预期输出**：
```
=== 数据库中的设备 ===
数据库中没有活跃设备

=== 模板设备检查 ===
没有发现模板设备
```

### 2. 检查启动日志

重启应用后，应该看到：

```
Loading devices from database...
No enabled devices found in database
Only template files found, skipping auto-migration
```

## 防止模板设备被迁移

### 已实施的改进

系统现在会自动跳过以下类型的文件：
- `example_*` - 示例文件
- `template_*` - 模板文件
- `sample_*` - 样本文件
- `demo_*` - 演示文件

### 文件命名建议

#### ✅ 实际设备配置（会被迁移）
- `modbus_device_1.yaml`
- `production_plc.yaml`
- `workshop_temperature.yaml`

#### ❌ 模板文件（会被跳过）
- `example_modbus_device.yaml`
- `template_bacnet.yaml`
- `sample_opcua.yaml`
- `demo_sensor.yaml`

## 手动迁移设备

如果你确实需要迁移设备配置：

### 1. 创建设备配置文件

```yaml
# config/devices/my_device.yaml
asset: my_device
plugin_name: modbus_tcp
plugin_config:
  host: 192.168.1.100
  port: 502
points:
  - name: temperature
    data_type: float32
    config:
      address: 0
```

### 2. 手动迁移

```bash
python -m xagent.tools.migrate_config migrate \
  --devices-dir "C:\Users\77127\AppData\Local\adveco\XAgent\config\devices" \
  --database "C:\Users\77127\AppData\Local\adveco\XAgent\data\xagent.db"
```

### 3. 验证迁移结果

```bash
curl http://localhost:8080/api/devices/
```

## 总结

### 问题
- ❌ 模板设备被自动迁移到数据库
- ❌ 启动时会加载这些模板设备

### 解决方案
- ✅ 清理数据库中的模板设备
- ✅ 修改迁移逻辑，跳过模板文件
- ✅ 提供工具脚本进行清理

### 预防措施
- ✅ 文件命名规范（避免使用example/template等关键词）
- ✅ 自动跳过模板文件
- ✅ 提供清理工具

现在你的系统不会再自动迁移模板设备了！
