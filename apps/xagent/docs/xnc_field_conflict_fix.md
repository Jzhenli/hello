# XNC通道配置字段命名冲突修复

## 问题描述
UI上选择XNC协议后，显示的是"protobuf"，这是因为字段命名冲突导致的。

## 根本原因
存在两个同名的`protocol`字段：
1. **通道级别**：`protocol: 'xnc'` - 表示通道的协议类型（mqtt/xnc/http）
2. **XNC配置内部**：`protocol: 'protobuf'` - 表示XNC的协议模式（protobuf/json）

这两个字段在表单中冲突，导致UI显示错误。

## 解决方案
将XNC配置内部的协议模式字段重命名为`xnc_protocol`，避免与通道级别的`protocol`字段冲突。

## 修改的字段映射

### 前端表单字段
```typescript
// 通道级别字段
protocol: 'xnc'  // 通道协议类型

// XNC配置字段
xnc_protocol: 'protobuf'  // XNC协议模式
local_port: 8888
remote_host: '127.0.0.1'
remote_port: 9000
reconnect_interval: 5
mapping_config: '{}'
adapter: 'xnc_protobuf'
```

### 后端数据模型
```python
# 通道配置
class NorthChannelConfig:
    protocol: NorthChannelProtocol  # 通道协议类型

# XNC连接配置
class XNCConnectionConfig:
    protocol: str  # XNC协议模式 (protobuf/json)
    local_port: int
    remote_host: str
    remote_port: int
    reconnect_interval: int
    mapping_config: Optional[Dict]
```

### 数据转换
前端发送到后端时，`xnc_protocol`字段会被转换为`connection.xnc.protocol`：

```typescript
// 前端表单
{
  protocol: 'xnc',  // 通道级别
  xnc_protocol: 'protobuf',  // 表单字段
  // ...
}

// 转换为后端格式
{
  protocol: 'xnc',  // 通道级别
  connection: {
    xnc: {
      protocol: 'protobuf',  // XNC配置内部
      // ...
    }
  }
}
```

## 修改的文件

### 前端文件
1. **NorthChannels.vue**
   - 表单字段定义：`protocol` → `xnc_protocol`
   - 表单绑定：`v-model="channelForm.protocol"` → `v-model="channelForm.xnc_protocol"`
   - 数据转换：`protocol: channelForm.value.xnc_protocol`
   - 默认值设置：所有初始化函数中的字段名

### 后端文件
无需修改，后端模型保持`protocol`字段名不变。

## 验证步骤

1. **打开UI**，选择"新增通道"
2. **选择协议**：XNC
3. **验证显示**：
   - 协议类型显示：XNC ✅
   - 协议模式显示：Protobuf/JSON单选按钮 ✅
4. **填写配置**：
   - 本地端口：8888
   - 协议模式：选择Protobuf或JSON
   - 远程主机：127.0.0.1
   - 远程端口：9000
5. **保存配置**，验证数据结构正确

## 字段对照表

| 字段用途 | 前端表单字段 | 后端字段路径 | 说明 |
|---------|------------|------------|------|
| 通道协议类型 | `protocol` | `protocol` | mqtt/xnc/http |
| XNC协议模式 | `xnc_protocol` | `connection.xnc.protocol` | protobuf/json |
| 本地端口 | `local_port` | `connection.xnc.local_port` | UDP监听端口 |
| 远程主机 | `remote_host` | `connection.xnc.remote_host` | XNC服务器地址 |
| 远程端口 | `remote_port` | `connection.xnc.remote_port` | XNC服务器端口 |
| 重连间隔 | `reconnect_interval` | `connection.xnc.reconnect_interval` | 重连间隔 |
| 映射配置 | `mapping_config` | `connection.xnc.mapping_config` | 设备映射 |
| 适配器 | `adapter` | `adapter.type` | xnc_protobuf/xnc_json |

## 配置示例

### 完整的XNC通道配置
```json
{
  "id": "xnc_channel_001",
  "name": "XNC数据上传通道",
  "protocol": "xnc",
  "connection": {
    "host": "127.0.0.1",
    "port": 9000,
    "xnc": {
      "local_port": 8888,
      "protocol": "protobuf",
      "remote_host": "127.0.0.1",
      "remote_port": 9000,
      "reconnect_interval": 5,
      "mapping_config": {}
    }
  },
  "adapter": {
    "type": "xnc_protobuf",
    "config": {}
  }
}
```

## 注意事项

1. **字段命名规范**：
   - 通道级别的字段直接使用字段名（如`protocol`）
   - 协议特定的配置字段添加前缀（如`xnc_protocol`、`mqtt_client_id`）

2. **数据转换**：
   - 前端表单使用扁平化字段名
   - 提交时转换为嵌套的JSON结构
   - 确保字段名不冲突

3. **向后兼容**：
   - 后端API保持原有字段名
   - 前端负责字段映射和转换
