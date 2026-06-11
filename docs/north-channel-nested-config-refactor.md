# 北向通道配置嵌套结构重构方案

## 1. 背景与问题

### 1.1 当前架构

前端提交的配置是**嵌套结构**，API 模型也是嵌套的，但传递给插件时被 `_load_channel_plugin()` 展平为扁平字典：

```
前端 (嵌套)              API 模型 (嵌套)              插件 (扁平)
connection.broker   →   NorthChannelConnection.broker → config.get("broker")
adapter.config      →   NorthChannelAdapter.config    → config.get("adapter_config")
upload_strategy     →   NorthChannelUploadStrategy    → config.get("batch_size")
```

### 1.2 核心问题

| 问题 | 说明 |
|------|------|
| **展平逻辑脆弱** | `_load_channel_plugin()` 硬编码展平 `adapter.config`，如果 config 内有 `type` key 会覆盖外层 `type` |
| **字段丢失** | `command_topic`、`publish_mode`、`command_timeout` 在 plugin config_schema 中定义，但 API 模型 `NorthChannelConnection` 中缺失，展平后自然丢失 |
| **两套定义不同步** | plugin `config_schema()` 和 API `NorthChannelConnection` 各维护一份字段定义，容易不一致 |
| **前端绕圈** | 前端组装嵌套结构 → 后端展平 → 插件当扁平用，等于白绕一圈 |
| **XNC 兼容代码** | XNC 插件的 `_resolve_mapping_config()` 做了多级兼容查找，正是展平导致的补救措施 |

### 1.3 重构目标

- 插件直接消费嵌套结构，与 API 模型对齐
- 删除展平逻辑，消除字段丢失和覆盖风险
- 补全缺失字段（command_topic、publish_mode、command_timeout）
- 数据库存储格式不变，只在 `_load_channel_plugin()` 传给插件时构建嵌套结构

---

## 2. 重构后数据流

**核心原则：数据库存储保持扁平，只在传给插件时构建嵌套结构。**

```
前端提交 (嵌套)              API 模型 (嵌套)              数据库 (扁平JSON)             插件消费 (嵌套)
{                            NorthChannelConfig            connection_config:            config["connection"]
  connection: {              .connection                   {"broker":"...",              .get("broker")
    broker: "...",                                          "port":1883,                 .get("command_topic")
    port: 1883,                                              "command_topic":"...",
    command_topic: "...",                                    "publish_mode":"single",
    publish_mode: "single",                                  "command_timeout":30}
    command_timeout: 30
  },                                                        adapter_config:               config["adapter"]
  adapter: {                  .adapter                     {"type":"mqtt",               .get("type")
    type: "mqtt",                                           "adapter":"standard",        .get("adapter")
    adapter: "standard",                                     "config":{...}}             .get("config")
    config: {...}
  },                                                        upload_config:                config["upload_strategy"]
  upload_strategy: {          .upload_strategy              {"immediate_upload":true,     .get("batch_size")
    batch_size: 100,                                        "batch_size":100,
    interval: 5                                              "interval":5}
  }
}
```

**关键设计决策：为什么数据库保持扁平？**

1. 数据库列名 `connection_config` 本身已表达"这是连接配置"的语义，再包一层 `{"connection": {...}}` 是冗余的
2. 避免修改 `_channel_to_service()` 和 `_service_to_channel()`，减少改动范围
3. 不需要新旧格式兼容逻辑
4. `config_schema()` 保持扁平不影响 `_extract_defaults_from_schema()` 的递归提取

---

## 3. 流程推演验证

### 3.1 MQTT 通道推演

#### Step 1: 前端提交

```json
POST /api/channels/
{
  "id": "mqtt_prod_01",
  "name": "生产MQTT",
  "enabled": true,
  "protocol": "mqtt",
  "connection": {
    "broker": "broker.example.com",
    "port": 1883,
    "username": "admin",
    "password": "secret",
    "client_id": "xagent_001",
    "topic": "xagent/data",
    "command_topic": "xagent/command",
    "publish_mode": "batch",
    "command_timeout": 30.0,
    "qos": 1,
    "keepalive": 60,
    "clean_session": true
  },
  "adapter": {
    "type": "mqtt",
    "adapter": "C001",
    "config": {"productKey": "al12345"}
  },
  "upload_strategy": {
    "immediate_upload": true,
    "batch_size": 100,
    "interval": 5,
    "retry_times": 3,
    "retry_interval": 5
  }
}
```

FastAPI 反序列化为 `NorthChannelConfig`。 **OK**

#### Step 2: `_channel_to_service()` — 写入数据库（不改）

```python
connection_config = channel.connection.model_dump(exclude_none=True)
# → {"broker": "broker.example.com", "port": 1883, "username": "admin",
#    "password": "secret", "client_id": "xagent_001", "topic": "xagent/data",
#    "command_topic": "xagent/command", "publish_mode": "batch",
#    "command_timeout": 30.0, "qos": 1, "keepalive": 60, "clean_session": true}
# 存入数据库 connection_config 列 → 扁平，OK

adapter_config = {"type": "mqtt", "adapter": "C001", "config": {"productKey": "al12345"}}
# 存入数据库 adapter_config 列 → OK

upload_config = {"immediate_upload": true, "batch_size": 100, "interval": 5, ...}
# 存入数据库 upload_config 列 → 扁平，OK
```

**数据库存储格式不变。**

#### Step 3: `_service_to_channel()` — 从数据库读回（不改）

```python
conn_config = service.connection_config
# {"broker": "broker.example.com", "port": 1883, ..., "command_topic": "xagent/command", ...}
connection = NorthChannelConnection(**conn_config)  # 直接解包 → OK，新增字段自动填充

adapter_config = service.adapter_config
# {"type": "mqtt", "adapter": "C001", "config": {"productKey": "al12345"}}
adapter = NorthChannelAdapter(
    type=adapter_config.get("type", "default"),     # "mqtt"
    adapter=adapter_config.get("adapter"),           # "C001"
    mapping_config=adapter_config.get("mapping_config"),  # None
    headers=adapter_config.get("headers"),            # None
    config=adapter_config.get("config")               # {"productKey": "al12345"}
)
# → OK
```

**不需要兼容逻辑。**

#### Step 4: `_load_channel_plugin()` — 传给插件（核心改动）

改动后：

```python
plugin_config = {
    "channel_id": channel.id,
    "connection": channel.connection.model_dump(exclude_none=True),
    "adapter": channel.adapter.model_dump(exclude_none=True),
    "upload_strategy": channel.upload_strategy.model_dump(exclude_none=True),
}
```

结果：

```python
{
    "channel_id": "mqtt_prod_01",
    "connection": {
        "broker": "broker.example.com",
        "port": 1883,
        "username": "admin",
        "password": "secret",
        "client_id": "xagent_001",
        "topic": "xagent/data",
        "command_topic": "xagent/command",
        "publish_mode": "batch",
        "command_timeout": 30.0,
        "qos": 1,
        "keepalive": 60,
        "clean_session": true
    },
    "adapter": {
        "type": "mqtt",
        "adapter": "C001",
        "config": {"productKey": "al12345"}
    },
    "upload_strategy": {
        "immediate_upload": true,
        "batch_size": 100,
        "interval": 5,
        "retry_times": 3,
        "retry_interval": 5
    }
}
```

#### Step 5: MQTT 插件消费

```python
conn = config.get("connection", {})
self._broker = conn.get("broker", DEFAULT_BROKER)           # "broker.example.com" ✓
self._port = conn.get("port", DEFAULT_PORT)                  # 1883 ✓
self._command_topic = conn.get("command_topic", DEFAULT_COMMAND_TOPIC)  # "xagent/command" ✓
self._publish_mode = conn.get("publish_mode", DEFAULT_PUBLISH_MODE)     # "batch" ✓
self._command_timeout = conn.get("command_timeout", 30.0)               # 30.0 ✓

adapter_cfg = config.get("adapter", {})
adapter_name = adapter_cfg.get("adapter") or adapter_cfg.get("type", "standard")  # "C001" ✓
adapter_config = adapter_cfg.get("config", {})               # {"productKey": "al12345"} ✓
```

**所有字段正确传递，包括之前丢失的 command_topic、publish_mode、command_timeout。**

#### Step 6: 基类消费

```python
upload = config.get("upload_strategy", {})
self._immediate_upload = upload.get("immediate_upload", ...)  # true ✓
self._batch_size = upload.get("batch_size", ...)              # 100 ✓
self._interval = upload.get("interval", ...)                  # 5 ✓
```

**OK**

#### Step 7: 插件查找与卸载

```python
# _unload_channel_plugin / device_loader_db
plugin.config.get("channel_id") == channel_id  # "mqtt_prod_01" ✓
```

`channel_id` 仍在 plugin_config 顶层。**OK**

---

### 3.2 XNC 通道推演

#### Step 1: 前端提交

```json
POST /api/channels/
{
  "id": "xnc_prod_01",
  "name": "生产XNC",
  "enabled": true,
  "protocol": "xnc",
  "connection": {
    "local_port": 8888,
    "remote_host": "192.168.1.100",
    "remote_port": 9000,
    "reconnect_interval": 10
  },
  "adapter": {
    "type": "xnc_protobuf",
    "mapping_config": {
      "device001": {"asset": "sensor_01", "points": {"temp": "temperature"}}
    }
  },
  "upload_strategy": {
    "immediate_upload": false,
    "batch_size": 50,
    "interval": 10,
    "retry_times": 5,
    "retry_interval": 3
  }
}
```

#### Step 2: `_channel_to_service()` — 写入数据库（不改）

```python
connection_config = {"local_port": 8888, "remote_host": "192.168.1.100",
                     "remote_port": 9000, "reconnect_interval": 10}
# 扁平，OK

adapter_config = {"type": "xnc_protobuf",
                  "mapping_config": {"device001": {"asset": "sensor_01", ...}}}
# OK

upload_config = {"immediate_upload": false, "batch_size": 50, "interval": 10, ...}
# 扁平，OK
```

#### Step 3: `_service_to_channel()` — 从数据库读回（不改）

```python
connection = NorthChannelConnection(**conn_config)
# local_port=8888, remote_host="192.168.1.100", remote_port=9000, reconnect_interval=10 ✓

adapter = NorthChannelAdapter(type="xnc_protobuf",
                              mapping_config={"device001": {...}})
# ✓
```

#### Step 4: `_load_channel_plugin()` — 传给插件

```python
plugin_config = {
    "channel_id": "xnc_prod_01",
    "connection": {"local_port": 8888, "remote_host": "192.168.1.100",
                   "remote_port": 9000, "reconnect_interval": 10},
    "adapter": {"type": "xnc_protobuf",
                "mapping_config": {"device001": {"asset": "sensor_01", ...}}},
    "upload_strategy": {"immediate_upload": false, "batch_size": 50,
                        "interval": 10, "retry_times": 5, "retry_interval": 3}
}
```

#### Step 5: XNC 插件消费

```python
conn = config.get("connection", {})
self._remote_host = conn.get("remote_host", DEFAULT_REMOTE_HOST)  # "192.168.1.100" ✓
self._remote_port = conn.get("remote_port", DEFAULT_REMOTE_PORT)  # 9000 ✓
self._local_port = conn.get("local_port", DEFAULT_LOCAL_PORT)     # 8888 ✓

# _resolve_mapping_config — 简化后
adapter_cfg = config.get("adapter", {})
mapping_config = adapter_cfg.get("mapping_config")  # {"device001": {...}} ✓ 直接取到！

# _create_data_adapter
adapter_cfg = config.get("adapter", {})
XNCProtobufAdapter(mapper=self._mapper, config=adapter_cfg.get("config", {}))  # {} ✓
```

**XNC 推演通过。`_resolve_mapping_config` 不再需要多级兼容查找。**

#### Step 6: 基类消费

```python
upload = config.get("upload_strategy", {})
self._batch_size = upload.get("batch_size", ...)  # 50 ✓
self._interval = upload.get("interval", ...)       # 10 ✓
```

**OK**

#### Step 7: 前端编辑回填

```typescript
local_port: fullChannel.connection.local_port || 8888,           // 8888 ✓
remote_host: fullChannel.connection.remote_host || '127.0.0.1',  // "192.168.1.100" ✓
remote_port: fullChannel.connection.remote_port || 9000,         // 9000 ✓
mapping_config: JSON.stringify(fullChannel.adapter.mapping_config || {}, null, 2)
// "{"device001": ...}" ✓
```

前端取值路径 `fullChannel.connection.xxx` 和 `fullChannel.adapter.xxx` 不变。**OK**

---

## 4. 后端改动

### 4.1 API 模型 — `north_channel.py`

**文件**: `apps/xagent/src/xagent/xcore/api/models/north_channel.py`

#### 4.1.1 `NorthChannelConnection` 补字段

```python
class NorthChannelConnection(BaseModel):
    """连接配置 - 扁平结构，根据protocol字段确定具体字段"""

    # MQTT字段
    broker: Optional[str] = Field(None, description="MQTT Broker地址")
    client_id: Optional[str] = Field(None, description="MQTT客户端ID")
    topic: Optional[str] = Field(None, description="发布主题")
    command_topic: Optional[str] = Field(None, description="命令订阅主题")          # 新增
    publish_mode: Optional[str] = Field(None, description="发布模式 single/batch")  # 新增
    command_timeout: Optional[float] = Field(None, description="命令超时时间(秒)")   # 新增
    qos: Optional[int] = Field(None, ge=0, le=2, description="QoS级别")
    keepalive: Optional[int] = Field(None, description="保活时间(秒)")
    clean_session: Optional[bool] = Field(None, description="清除会话")
    will_topic: Optional[str] = Field(None, description="遗嘱主题")
    will_message: Optional[str] = Field(None, description="遗嘱消息")
    will_qos: Optional[int] = Field(None, ge=0, le=2, description="遗嘱QoS")
    will_retain: Optional[bool] = Field(None, description="遗嘱保留")

    # XNC字段 (不变)
    local_port: Optional[int] = Field(None, description="本地监听端口")
    remote_host: Optional[str] = Field(None, description="远程主机地址")
    remote_port: Optional[int] = Field(None, description="远程端口")
    reconnect_interval: Optional[int] = Field(None, description="重连间隔(秒)")

    # HTTP字段 (不变)
    endpoint: Optional[str] = Field(None, description="HTTP端点URL")
    method: Optional[str] = Field(None, description="HTTP方法")
    headers: Optional[Dict[str, str]] = Field(None, description="请求头")
    timeout: Optional[int] = Field(None, description="超时时间(秒)")

    # 通用字段 (不变)
    port: Optional[int] = Field(None, description="端口号")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
```

#### 4.1.2 `NorthChannelAdapter` 补字段

```python
class NorthChannelAdapter(BaseModel):
    """适配器配置"""
    type: str = Field(default="default", description="适配器类型")
    adapter: Optional[str] = Field(None, description="适配器名称(如 standard/C001)")  # 新增

    # XNC适配器配置
    mapping_config: Optional[Dict[str, Any]] = Field(None, description="设备映射配置")

    # HTTP适配器配置
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP请求头")

    # 其他适配器配置
    config: Optional[Dict[str, Any]] = Field(None, description="其他适配器配置")
```

---

### 4.2 服务层 — `north_channel_service.py`

**文件**: `apps/xagent/src/xagent/xcore/api/services/north_channel_service.py`

#### 4.2.1 `_load_channel_plugin()` — 删除展平，构建嵌套传给插件

**改动前** (L604-628):

```python
upload_dict = channel.upload_strategy.model_dump(exclude_none=True)
adapter_dict = channel.adapter.model_dump(exclude_none=True)
connection_dict = channel.connection.model_dump(exclude_none=True)

# 展平 adapter.config
adapter_config = {}
for key, value in adapter_dict.items():
    if key == "config" and isinstance(value, dict):
        adapter_config.update(value)
    else:
        adapter_config[key] = value

plugin_config = {
    "channel_id": channel.id,
    **connection_dict,        # 扁平: broker, port, topic...
    **upload_dict,            # 扁平: batch_size, interval...
    "adapter_config": adapter_config  # 展平后的适配器配置
}
```

**改动后**:

```python
plugin_config = {
    "channel_id": channel.id,
    "connection": channel.connection.model_dump(exclude_none=True),
    "adapter": channel.adapter.model_dump(exclude_none=True),
    "upload_strategy": channel.upload_strategy.model_dump(exclude_none=True),
}
```

#### 4.2.2 `_channel_to_service()` — 不改

数据库存储保持扁平，`_channel_to_service()` 逻辑不变。只需在 `adapter_config` 构建中补上 `adapter` 字段：

```python
# 在现有代码 L159-173 中追加一行
adapter_config = {
    "type": channel.adapter.type
}
if channel.adapter.adapter:                              # 新增
    adapter_config["adapter"] = channel.adapter.adapter  # 新增
if channel.adapter.mapping_config:
    adapter_config["mapping_config"] = channel.adapter.mapping_config
if channel.adapter.headers:
    adapter_config["headers"] = channel.adapter.headers
if channel.adapter.config:
    adapter_config["config"] = channel.adapter.config
```

#### 4.2.3 `_service_to_channel()` — 不改

只需在 adapter 构建中补上 `adapter` 字段：

```python
adapter = NorthChannelAdapter(
    type=adapter_config.get("type", "default"),
    adapter=adapter_config.get("adapter"),       # 新增
    mapping_config=adapter_config.get("mapping_config"),
    headers=adapter_config.get("headers"),
    config=adapter_config.get("config"),
)
```

---

### 4.3 MQTT 插件 — `mqtt_client/plugin.py`

**文件**: `apps/xagent/src/xagent/plugins/north/mqtt_client/plugin.py`

#### 4.3.1 `__init__` — 改为嵌套取值

**改动前** (L151-165):

```python
def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
    self._broker = config.get("broker", DEFAULT_BROKER)
    self._port = config.get("port", DEFAULT_PORT)
    self._topic = config.get("topic", DEFAULT_TOPIC)
    self._command_topic = config.get("command_topic", DEFAULT_COMMAND_TOPIC)
    self._qos = config.get("qos", DEFAULT_QOS)
    self._username = config.get("username")
    self._password = config.get("password")
    self._client_id = config.get("client_id", DEFAULT_CLIENT_ID)
    self._keepalive = config.get("keepalive", DEFAULT_KEEPALIVE)
    self._publish_mode = config.get("publish_mode", DEFAULT_PUBLISH_MODE)
    self._command_timeout = config.get("command_timeout", 30.0)
```

**改动后**:

```python
def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
    if not _check_mqtt_available():
        raise RuntimeError("MQTT dependencies not available. Install with: pip install aiomqtt")

    conn = config.get("connection", {})
    self._broker = conn.get("broker", DEFAULT_BROKER)
    self._port = conn.get("port", DEFAULT_PORT)
    self._topic = conn.get("topic", DEFAULT_TOPIC)
    self._command_topic = conn.get("command_topic", DEFAULT_COMMAND_TOPIC)
    self._qos = conn.get("qos", DEFAULT_QOS)
    self._username = conn.get("username")
    self._password = conn.get("password")
    self._client_id = conn.get("client_id", DEFAULT_CLIENT_ID)
    self._keepalive = conn.get("keepalive", DEFAULT_KEEPALIVE)
    self._publish_mode = conn.get("publish_mode", DEFAULT_PUBLISH_MODE)
    self._command_timeout = conn.get("command_timeout", 30.0)

    self._client: Optional["aiomqtt.Client"] = None

    super().__init__(config, storage, event_bus)

    self._downlink_handler = _DownlinkHandler(
        event_bus=event_bus,
        adapter=self._data_adapter,
        command_timeout=self._command_timeout,
    )

    logger.info(f"MQTT plugin initialized: broker={self._broker}:{self._port}, topic={self._topic}")
    logger.debug(f"MQTT plugin config: {_sanitize_config(config)}")
```

#### 4.3.2 `_create_data_adapter` — 从 adapter 子对象取值

**改动前** (L182-205):

```python
def _create_data_adapter(self) -> Any:
    adapter_name = self.config.get("adapter", "standard")
    adapter_config = self.config.get("adapter_config", {})
```

**改动后**:

```python
def _create_data_adapter(self) -> Any:
    from .adapters import get_adapter

    adapter_cfg = self.config.get("adapter", {})
    adapter_name = adapter_cfg.get("adapter") or adapter_cfg.get("type", "standard")
    adapter_config = adapter_cfg.get("config", {})

    logger.info(f"Creating MQTT adapter: name={adapter_name}, config_keys={list(adapter_config.keys())}")

    try:
        adapter = get_adapter(adapter_name, adapter_config)
        logger.info(f"MQTT adapter created: {type(adapter).__name__}")
        subscribe_topics = adapter.get_subscribe_topics()
        logger.info(f"MQTT subscribe topics: {subscribe_topics}")
        return adapter
    except ValueError as e:
        logger.warning(f"{e}. Falling back to standard adapter")
        return get_adapter("standard", adapter_config)
    except Exception as e:
        logger.error(f"Failed to create adapter: {e}")
        raise
```

#### 4.3.3 `config_schema` — 不改

保持扁平结构，原因：
1. `_extract_defaults_from_schema()` 只做一层遍历，嵌套 schema 会导致默认值提取失败
2. `config_schema()` 的主要消费方是 `sync_plugin_registry()`，它将默认值写入 `plugin_registry` 表
3. 数据库存储也是扁平的，`config_schema` 保持扁平与存储格式一致

---

### 4.4 XNC 插件 — `xnc_client/plugin.py`

**文件**: `apps/xagent/src/xagent/plugins/north/xnc_client/plugin.py`

#### 4.4.1 `__init__` — 改为嵌套取值

**改动前** (L88-91):

```python
def __init__(self, config, storage, event_bus):
    self._remote_host = config.get("remote_host", DEFAULT_REMOTE_HOST)
    self._remote_port = config.get("remote_port", DEFAULT_REMOTE_PORT)
    self._local_port = config.get("local_port", DEFAULT_LOCAL_PORT)
```

**改动后**:

```python
def __init__(self, config, storage, event_bus):
    conn = config.get("connection", {})
    self._remote_host = conn.get("remote_host", DEFAULT_REMOTE_HOST)
    self._remote_port = conn.get("remote_port", DEFAULT_REMOTE_PORT)
    self._local_port = conn.get("local_port", DEFAULT_LOCAL_PORT)
```

#### 4.4.2 `_resolve_mapping_config` — 简化

**改动前** (L113-126): 多级兼容查找

```python
def _resolve_mapping_config(self):
    mapping_config = self.config.get("mapping_config")
    if isinstance(mapping_config, dict) and mapping_config:
        return mapping_config
    for parent_key in ("xnc", "adapter_config"):
        parent = self.config.get(parent_key)
        if isinstance(parent, dict):
            parent_mapping = parent.get("mapping_config")
            if isinstance(parent_mapping, dict) and parent_mapping:
                return parent_mapping
    return {}
```

**改动后**:

```python
def _resolve_mapping_config(self):
    adapter_cfg = self.config.get("adapter", {})
    mapping_config = adapter_cfg.get("mapping_config")
    if isinstance(mapping_config, dict) and mapping_config:
        return mapping_config
    return {}
```

#### 4.4.3 `_create_data_adapter` — 从 adapter 子对象取值

**改动前** (L138-140):

```python
def _create_data_adapter(self):
    adapter_config = self.config.get("adapter_config", {})
    return XNCProtobufAdapter(mapper=self._mapper, config=adapter_config)
```

**改动后**:

```python
def _create_data_adapter(self):
    adapter_cfg = self.config.get("adapter", {})
    return XNCProtobufAdapter(mapper=self._mapper, config=adapter_cfg.get("config", {}))
```

---

### 4.5 基类 — `north.py`

**文件**: `apps/xagent/src/xagent/xcore/plugins/north.py`

#### 4.5.1 `__init__` — 从 upload_strategy 子对象取值

**改动前** (L57-83):

```python
def __init__(self, config, storage, event_bus):
    self.config = config
    self._service_name = config.get("channel_id") or ...
    self._data_adapter = self._create_data_adapter()
    self._immediate_upload = config.get("immediate_upload", self.DEFAULT_IMMEDIATE_UPLOAD)
    self._batch_size = config.get("batch_size", self.DEFAULT_BATCH_SIZE)
    self._interval = config.get("interval", self.DEFAULT_INTERVAL)
    self._retry_count = config.get("retry_count", self.DEFAULT_RETRY_COUNT)
    self._retry_delay = config.get("retry_delay", self.DEFAULT_RETRY_DELAY)
    self._reconnect_interval = config.get("reconnect_interval", self.DEFAULT_RECONNECT_INTERVAL)
    self._reconnect_max_delay = config.get("reconnect_max_delay", self.DEFAULT_RECONNECT_MAX_DELAY)
```

**改动后**:

```python
def __init__(self, config, storage, event_bus):
    self.config = config
    self.storage = storage
    self.event_bus = event_bus

    self._running = False
    self._connected = False

    self._service_name = config.get("channel_id") or self.__plugin_name__ or self.__class__.__name__

    self._data_adapter = self._create_data_adapter()

    upload = config.get("upload_strategy", {})
    self._immediate_upload = upload.get("immediate_upload", self.DEFAULT_IMMEDIATE_UPLOAD)
    self._batch_size = upload.get("batch_size", self.DEFAULT_BATCH_SIZE)
    self._interval = upload.get("interval", self.DEFAULT_INTERVAL)
    self._retry_count = upload.get("retry_count", self.DEFAULT_RETRY_COUNT)
    self._retry_delay = upload.get("retry_delay", self.DEFAULT_RETRY_DELAY)
    self._reconnect_interval = upload.get("reconnect_interval", self.DEFAULT_RECONNECT_INTERVAL)
    self._reconnect_max_delay = upload.get("reconnect_max_delay", self.DEFAULT_RECONNECT_MAX_DELAY)
    self._reconnect_attempts = 0
    self._reconnect_lock = asyncio.Lock()

    self._upload_task: Optional[asyncio.Task] = None
    self._command_task: Optional[asyncio.Task] = None

    self._stats_manager = None

    if self._immediate_upload and event_bus:
        event_bus.subscribe(EventType.WRITE_COMPLETED, self._handle_write_completed)
        logger.info(f"Immediate upload enabled for {self._service_name}")
```

---

## 5. 前端改动

### 5.1 类型定义 — `types.ts`

**文件**: `apps/xagent-visual/src/api/types.ts`

#### 5.1.1 `MQTTConnectionConfig` 补字段

```typescript
export interface MQTTConnectionConfig {
  broker: string
  port: number
  username?: string
  password?: string
  client_id: string
  topic: string
  command_topic?: string                      // 新增
  publish_mode?: 'single' | 'batch'           // 新增
  command_timeout?: number                    // 新增
  qos: 0 | 1 | 2
  keepalive: number
  clean_session?: boolean
  will_topic?: string
  will_message?: string
  will_qos?: 0 | 1 | 2
  will_retain?: boolean
}
```

#### 5.1.2 `NorthChannelConnection` 补字段

```typescript
export interface NorthChannelConnection {
  // MQTT字段
  broker?: string
  client_id?: string
  topic?: string
  command_topic?: string                      // 新增
  publish_mode?: 'single' | 'batch'           // 新增
  command_timeout?: number                    // 新增
  qos?: 0 | 1 | 2
  keepalive?: number
  clean_session?: boolean
  will_topic?: string
  will_message?: string
  will_qos?: 0 | 1 | 2
  will_retain?: boolean

  // XNC字段 (不变)
  local_port?: number
  protocol?: 'protobuf' | 'json'
  remote_host?: string
  remote_port?: number
  reconnect_interval?: number

  // HTTP字段 (不变)
  endpoint?: string
  method?: 'GET' | 'POST' | 'PUT'
  headers?: Record<string, string>
  timeout?: number

  // 通用字段 (不变)
  port?: number
  username?: string
  password?: string
}
```

#### 5.1.3 `NorthChannelAdapter` 补字段

```typescript
export interface NorthChannelAdapter {
  type: string
  adapter?: string                            // 已有，确认保留
  adapter_config?: Record<string, unknown>
  mapping_config?: Record<string, unknown>
  headers?: Record<string, string>
  config?: Record<string, unknown>
}
```

---

### 5.2 表单页面 — `NorthChannels.vue`

**文件**: `apps/xagent-visual/src/views/NorthChannels.vue`

#### 5.2.1 `channelForm` 新增字段

```typescript
const channelForm = ref({
  // ... 原有字段不变
  command_topic: '',                                          // 新增
  publish_mode: 'single' as 'single' | 'batch',              // 新增
  command_timeout: 30,                                        // 新增
})
```

#### 5.2.2 `protocolOptions` MQTT 默认配置补字段

```typescript
const protocolOptions = [
  {
    label: 'MQTT',
    value: 'mqtt',
    defaultPort: 1883,
    defaultConfig: {
      client_id: `xagent_${Date.now()}`,
      topic: 'data/upload',
      qos: 1,
      keepalive: 60,
      clean_session: true,
      command_topic: 'xagent/command',          // 新增
      publish_mode: 'single',                    // 新增
      command_timeout: 30,                       // 新增
    }
  },
  // XNC、HTTP 不变
]
```

#### 5.2.3 `buildChannelConfig()` MQTT 部分补字段

在 `if (channelForm.value.protocol === 'mqtt')` 分支中追加：

```typescript
connection.command_topic = channelForm.value.command_topic     // 新增
connection.publish_mode = channelForm.value.publish_mode       // 新增
connection.command_timeout = channelForm.value.command_timeout  // 新增
```

#### 5.2.4 `handleEditChannel()` 补回填

```typescript
command_topic: fullChannel.connection.command_topic || '',
publish_mode: fullChannel.connection.publish_mode || 'single',
command_timeout: fullChannel.connection.command_timeout || 30,
```

#### 5.2.5 模板新增表单项

在 MQTT 配置区块（`v-if="channelForm.protocol === 'mqtt'"`）内，"主题"字段之后添加：

```html
<el-form-item label="命令主题">
  <el-input
    v-model="channelForm.command_topic"
    placeholder="命令订阅主题，如 xagent/command"
  />
  <div style="font-size: 12px; color: #909399; margin-top: 4px;">
    留空则使用默认值 xagent/command
  </div>
</el-form-item>
<el-form-item label="发布模式">
  <el-radio-group v-model="channelForm.publish_mode">
    <el-radio value="single">单条发送</el-radio>
    <el-radio value="batch">批量发送</el-radio>
  </el-radio-group>
</el-form-item>
<el-form-item label="命令超时">
  <el-input-number v-model="channelForm.command_timeout" :min="5" :max="300" />
  <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
</el-form-item>
```

---

## 6. 数据库影响

### 6.1 表结构

**不需要改**。`service_registry` 表的 `connection_config`、`adapter_config`、`upload_config` 均为 TEXT 类型，存 JSON 字符串。

### 6.2 存储内容格式

**不变**。数据库存储保持扁平格式：

| 字段 | 格式 |
|------|------|
| `connection_config` | `{"broker":"localhost","port":1883,"topic":"xagent/data","command_topic":"xagent/command",...}` |
| `upload_config` | `{"immediate_upload":true,"batch_size":100,"interval":5,...}` |
| `adapter_config` | `{"type":"mqtt","adapter":"standard","config":{...}}` |

### 6.3 无需兼容逻辑

由于数据库存储格式不变，`_service_to_channel()` 和 `_channel_to_service()` 不需要新旧格式兼容代码。

---

## 7. 改动量与风险评估

### 7.1 改动量统计

| 文件 | 改动类型 | 改动量 |
|------|---------|-------|
| **后端** | | |
| `xcore/api/models/north_channel.py` | 加字段 | ~5 行 |
| `xcore/api/services/north_channel_service.py` | `_load_channel_plugin` 删展平 + 补字段 | ~15 行 |
| `plugins/north/mqtt_client/plugin.py` | 取值路径改嵌套 | ~15 行 |
| `plugins/north/xnc_client/plugin.py` | 取值路径改嵌套 + 简化 | ~10 行 |
| `xcore/plugins/north.py` | 取值路径改嵌套 | ~5 行 |
| **前端** | | |
| `api/types.ts` | 加字段 | ~6 行 |
| `views/NorthChannels.vue` | 表单 + 组装 + 回填 | ~30 行 |
| `stores/channels.ts` | 不变 | 0 行 |

### 7.2 风险评估

| 风险项 | 等级 | 应对措施 |
|--------|------|---------|
| 插件取值路径遗漏 | 低 | 每个 `config.get` 都有默认值，遗漏时走默认值不会崩溃 |
| `adapter.config` 展平删除后适配器行为变化 | 低 | 适配器本来就接收独立 config dict，展平删除后反而更清晰 |
| 前端表单新增字段默认值 | 低 | 留空时后端使用 plugin 默认值，不会出错 |
| `lifecycle.py` 中 `config.get('interval')` 取值 | 低 | 仅影响南向插件轮询，北向插件不走此分支，当前重构范围不含南向 |

### 7.3 不需要改动的部分

- 数据库表结构 — 无需 DDL
- 数据库存储格式 — 保持扁平不变
- `ServiceRepository` — 读写 JSON TEXT 逻辑不变
- `ServiceConfig` dataclass — 字段定义不变
- `_channel_to_service()` — 基本不变，仅补 `adapter` 字段
- `_service_to_channel()` — 基本不变，仅补 `adapter` 字段
- API 路由层 — 无变化
- `config_schema()` — 保持扁平不变，不影响 `_extract_defaults_from_schema()`
- 前端 Store (`channels.ts`) — 无变化
- 前端 API 层 (`channels.ts` / `index.ts`) — 无变化
- MQTT 适配器 (`adapters/`) — 接收的 config 结构不变

---

## 8. 重构收益

| 收益 | 说明 |
|------|------|
| 消除展平逻辑 | 不再有隐式 key 展平/覆盖风险 |
| 字段自动对齐 | API 模型加字段后插件自动能收到，不会丢失 |
| 数据库不变 | 存储格式不变，无需迁移，无需兼容逻辑 |
| config_schema 不变 | 不影响 `_extract_defaults_from_schema()` 的默认值提取 |
| 前端结构不变 | 前端本来就是嵌套提交的，只需补字段 |
| XNC 兼容代码简化 | `_resolve_mapping_config` 不再多级查找 |
| 改动范围最小 | 核心改动集中在 `_load_channel_plugin()` + 插件取值路径 |
| 未来扩展容易 | 新增协议只需在 API 模型加字段 + 插件从 `connection` 取值 |
