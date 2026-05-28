# XNC通道配置字段映射文档

## 字段名称修正总结

### 后端XNC插件实际配置字段
根据 `apps/xagent/src/xagent/plugins/north/xnc_client/plugin.py` 的实现，XNC插件使用的配置字段：

```python
{
    "protocol": "protobuf",           # 协议模式 (protobuf/json)
    "remote_host": "127.0.0.1",       # 远程主机地址
    "remote_port": 9000,              # 远程端口
    "local_port": 8888,               # 本地监听端口
    "batch_size": 100,                # 批量大小
    "interval": 5,                    # 上传间隔
    "reconnect_interval": 5,          # 重连间隔
    "adapter": "xnc_protobuf",        # 适配器名称
    "adapter_config": {},             # 适配器配置
    "mapping_config": {}              # 映射配置（用于protobuf适配器）
}
```

### 已修正的字段

#### 1. 协议模式字段
- ❌ 错误：`protocol_mode`
- ✅ 正确：`protocol`

#### 2. 新增字段
- ✅ `reconnect_interval`: 重连间隔（秒）
- ✅ `mapping_config`: 设备映射配置（用于Protobuf适配器）

#### 3. 适配器字段
- ❌ 错误：`adapter_type`
- ✅ 正确：`adapter`

### 完整的XNC配置结构

#### 后端数据模型 (`north_channel.py`)
```python
class XNCConnectionConfig(BaseModel):
    local_port: int = Field(default=8888, description="本地监听端口")
    protocol: str = Field(default="protobuf", description="协议模式: protobuf/json")
    remote_host: Optional[str] = Field(default="127.0.0.1", description="远程主机地址")
    remote_port: Optional[int] = Field(default=9000, description="远程端口")
    reconnect_interval: int = Field(default=5, description="重连间隔(秒)")
    mapping_config: Optional[Dict[str, Any]] = Field(None, description="设备映射配置")
```

#### 前端类型定义 (`types.ts`)
```typescript
export interface XNCConnectionConfig {
  local_port: number
  protocol: 'protobuf' | 'json'
  remote_host?: string
  remote_port?: number
  reconnect_interval?: number
  mapping_config?: Record<string, unknown>
}
```

#### UI表单字段 (`NorthChannels.vue`)
```typescript
{
  local_port: 8888,
  protocol: 'protobuf' as 'protobuf' | 'json',
  remote_host: '127.0.0.1',
  remote_port: 9000,
  reconnect_interval: 5,
  mapping_config: '{}',
  adapter: 'xnc_protobuf',
  adapter_config: '{}'
}
```

### 默认值对照表

| 字段 | 后端默认值 | 前端默认值 | 说明 |
|------|-----------|-----------|------|
| `local_port` | 8888 | 8888 | UDP监听端口 |
| `protocol` | protobuf | protobuf | 协议模式 |
| `remote_host` | 127.0.0.1 | 127.0.0.1 | 远程主机地址 |
| `remote_port` | 9000 | 9000 | 远程端口 |
| `reconnect_interval` | 5 | 5 | 重连间隔（秒） |
| `adapter` | xnc_protobuf | xnc_protobuf | 适配器类型 |

### UI表单字段说明

#### 必填字段
1. **本地端口** (`local_port`)
   - 类型：数字
   - 范围：1024-65535
   - 说明：UDP监听端口，用于接收下行命令

2. **协议模式** (`protocol`)
   - 类型：单选
   - 选项：protobuf / json
   - 说明：Protobuf格式更高效，JSON格式更易调试

3. **远程主机** (`remote_host`)
   - 类型：文本
   - 说明：XNC服务器地址

4. **远程端口** (`remote_port`)
   - 类型：数字
   - 范围：1-65535
   - 说明：XNC服务器端口

#### 可选字段
5. **重连间隔** (`reconnect_interval`)
   - 类型：数字
   - 范围：1-300秒
   - 默认：5秒
   - 说明：连接失败后的重连间隔

6. **适配器** (`adapter`)
   - 类型：下拉选择
   - 选项：xnc_protobuf / xnc_json
   - 默认：xnc_protobuf

7. **映射配置** (`mapping_config`)
   - 类型：JSON文本
   - 条件：仅当适配器为xnc_protobuf时显示
   - 说明：用于Protobuf格式的设备ID和点位映射

### 配置示例

#### Protobuf模式配置
```json
{
  "id": "xnc_protobuf_channel",
  "name": "XNC Protobuf通道",
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
      "mapping_config": {
        "device_mapping": {
          "device_001": 1,
          "device_002": 2
        }
      }
    }
  },
  "adapter": {
    "type": "xnc_protobuf",
    "config": {}
  }
}
```

#### JSON模式配置
```json
{
  "id": "xnc_json_channel",
  "name": "XNC JSON通道",
  "protocol": "xnc",
  "connection": {
    "host": "127.0.0.1",
    "port": 9000,
    "xnc": {
      "local_port": 8889,
      "protocol": "json",
      "remote_host": "127.0.0.1",
      "remote_port": 9000,
      "reconnect_interval": 5
    }
  },
  "adapter": {
    "type": "xnc_json",
    "config": {}
  }
}
```

### 更新的文件列表

#### 后端文件
1. `apps/xagent/src/xagent/xcore/api/models/north_channel.py`
   - 更新 `XNCConnectionConfig` 类
   - 添加 `reconnect_interval` 字段
   - 添加 `mapping_config` 字段
   - 修正 `protocol_mode` 为 `protocol`

#### 前端文件
1. `apps/xagent-visual/src/api/types.ts`
   - 更新 `XNCConnectionConfig` 接口
   - 添加缺失的字段

2. `apps/xagent-visual/src/views/NorthChannels.vue`
   - 更新表单字段名
   - 添加缺失的表单字段
   - 更新详情显示字段
   - 更新配置构建逻辑

#### 配置文件
1. `apps/xagent/config/north_channels.json`
   - 更新示例配置字段名

### 验证清单

- [x] 后端数据模型字段与XNC插件匹配
- [x] 前端类型定义与后端模型匹配
- [x] UI表单字段与后端配置匹配
- [x] 详情显示字段正确
- [x] 配置构建逻辑正确
- [x] 示例配置文件正确
- [x] 默认值一致
- [x] 字段说明完整

### 注意事项

1. **协议模式字段名**
   - 必须使用 `protocol` 而不是 `protocol_mode`
   - 这是XNC插件的实际实现要求

2. **映射配置**
   - 仅在Protobuf模式下需要
   - 用于设备ID和点位的映射关系
   - 格式为JSON对象

3. **适配器选择**
   - `xnc_protobuf`: 使用Protobuf格式，高效但需要映射配置
   - `xnc_json`: 使用JSON格式，易调试但效率较低

4. **端口配置**
   - `local_port`: 本地UDP监听端口，用于接收命令
   - `remote_port`: 远程XNC服务器端口，用于发送数据
   - 两者可以不同
