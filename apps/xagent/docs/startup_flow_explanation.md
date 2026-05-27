# 启动流程和配置管理说明

## 启动日志解读

### 你看到的日志

```
2026-05-20 14:48:46 - xagent.xcore.core.paths - INFO - Copied 9 default config templates (5 plugins, 4 devices)
2026-05-20 14:48:47 - xagent.xcore.core.config - INFO - Configuration loaded from C:\Users\77127\AppData\Local\adveco\XAgent\config\config.yaml
2026-05-20 14:48:47 - xagent.xcore.gateway - INFO - Initializing XAgent Gateway...
```

### 日志含义

#### 1. 拷贝默认配置模板
```
Copied 9 default config templates (5 plugins, 4 devices)
```

**作用**：初始化应用目录，提供默认配置模板

**内容**：
- 5个插件配置模板（modbus_tcp.yaml, mqtt_client.yaml等）
- 4个设备配置模板（example_modbus_device.yaml等）

**位置**：
- 插件配置：`C:\Users\77127\AppData\Local\adveco\XAgent\config\plugins\`
- 设备配置：`C:\Users\77127\AppData\Local\adveco\XAgent\config\devices\`

**注意**：这些是**模板文件**，供参考使用，不影响运行时

#### 2. 加载主配置文件
```
Configuration loaded from config.yaml
```

**作用**：加载系统配置

**内容**：
- 服务器配置（host: 0.0.0.0, port: 8080）
- 存储配置（数据库路径、保留天数）
- 插件配置（失败策略、启动顺序）
- 调度器配置

**不包含**：
- ❌ 设备配置
- ❌ 点位配置

#### 3. 初始化网关
```
Initializing XAgent Gateway...
```

**作用**：启动核心服务

**流程**：
1. 初始化存储（SQLite数据库）
2. 初始化插件加载器
3. 初始化元数据管理器
4. **加载设备（从数据库）** ← 关键步骤

## 设备加载流程（数据库驱动）

### 完整流程

```python
# 1. 启动时调用
async def load_all_devices(self):
    logger.info("Loading devices from database...")
    
    # 2. 从数据库查询设备
    devices = await self.config_repo.list_devices(enabled=True)
    
    # 3. 如果数据库为空，尝试迁移
    if not devices:
        logger.info("No enabled devices found in database")
        
        # 4. 检查YAML文件
        migrated = await self._try_migrate_from_yaml()
        
        if migrated:
            # 5. 重新从数据库加载
            devices = await self.config_repo.list_devices(enabled=True)
    
    # 6. 加载设备插件
    for device in devices:
        await self._load_device(device)
```

### 迁移流程

```python
async def _try_migrate_from_yaml(self):
    # 1. 检查YAML文件目录
    devices_dir = self.config_manager.paths.config_dir / 'devices'
    yaml_files = list(devices_dir.glob("*.yaml"))
    
    # 2. 如果有YAML文件，迁移到数据库
    if yaml_files:
        logger.info(f"Found {len(yaml_files)} YAML device files, migrating to database...")
        
        migrator = ConfigMigrator(self.config_repo)
        result = await migrator.migrate_from_yaml(devices_dir)
        
        # 3. 返回迁移结果
        return result['succeeded'] > 0
    
    return False
```

## 配置文件的作用

### 主配置文件（config.yaml）

**作用**：系统配置

**内容**：
```yaml
server:
  host: 0.0.0.0
  port: 8080

storage:
  type: sqlite
  database: ${data_dir}/xagent.db
  retention_days: 30

plugins:
  failure_strategy: continue
  allow_partial_startup: true
```

**加载时机**：启动时加载一次

**修改方式**：手动编辑文件

### 设备配置文件（devices/*.yaml）

**作用**：设备配置模板和备份

**内容**：
```yaml
asset: example_modbus_device
plugin_name: modbus_tcp
plugin_config:
  host: 192.168.1.100
  port: 502
points:
  - name: temperature
    data_type: float32
```

**加载时机**：
- 首次启动时，如果数据库为空，自动迁移
- 之后不再加载，仅用于备份

**修改方式**：
- ✅ 通过API修改（推荐）
- ✅ 通过Web UI修改（推荐）
- ❌ 手动编辑文件（不推荐，会被覆盖）

### 数据库文件（xagent.db）

**作用**：唯一数据源

**内容**：
- 设备配置（device_registry表）
- 点位配置（point_registry表）
- 配置版本（config_versions表）
- 审计日志（audit_logs表）

**加载时机**：每次启动都从数据库加载

**修改方式**：
- ✅ 通过API修改
- ✅ 通过Web UI修改
- ✅ 通过CLI工具导入

## 如何验证使用的是数据库驱动

### 方法1：查看启动日志

**数据库驱动的日志**：
```
Loading devices from database...
Found X enabled devices in database
```

**YAML驱动的日志**：
```
Loading devices from config/devices/
Found X enabled devices
```

### 方法2：运行检查脚本

```bash
python tools/check_config_loader.py
```

**预期输出**：
```
✅ 使用数据库为中心的配置管理
  - 数据库是唯一数据源
  - YAML文件仅用于备份和迁移
```

### 方法3：检查设备配置位置

```bash
# 查看数据库中的设备
curl http://localhost:8080/api/devices/

# 查看YAML文件（仅作为备份）
ls C:\Users\77127\AppData\Local\adveco\XAgent\config\devices\
```

## 配置管理最佳实践

### 1. 日常配置管理

**推荐方式**：
```bash
# 通过API创建设备
curl -X POST http://localhost:8080/api/devices/ -d '{...}'

# 通过Web UI管理
访问 http://localhost:8080/
```

**不推荐方式**：
```bash
# ❌ 手动编辑YAML文件
vim config/devices/device.yaml
```

### 2. 配置备份

**推荐方式**：
```bash
# 定期导出配置
curl -X POST http://localhost:8080/api/devices/export > backup.json

# 或使用CLI工具
python -m xagent.tools.migrate_config export --database data/xagent.db --output-dir backups/
```

### 3. 配置迁移

**场景**：从开发环境迁移到生产环境

```bash
# 1. 开发环境导出
curl -X POST http://localhost:8080/api/devices/export > dev_config.json

# 2. 生产环境导入
curl -X POST http://localhost:8080/api/devices/import -d @dev_config.json
```

## 常见问题

### Q1: 为什么还会拷贝YAML文件？

**A**: 这是初始化应用目录的正常流程，提供默认配置模板供参考。这些模板文件不影响运行时的配置加载。

### Q2: 修改YAML文件会生效吗？

**A**: 不会。系统启动后，所有配置变更都通过API进行。YAML文件仅用于：
- 首次启动时的自动迁移
- 配置备份和恢复
- 手动导入配置

### Q3: 如何确认使用的是数据库驱动？

**A**: 查看启动日志中是否有：
```
Loading devices from database...
```

### Q4: 数据库损坏怎么办？

**A**: 从备份恢复：
```bash
# 从YAML备份恢复
python -m xagent.tools.migrate_config migrate --devices-dir config/devices --database data/xagent.db --overwrite

# 或从JSON备份恢复
curl -X POST http://localhost:8080/api/devices/import -d @backup.json
```

## 总结

### 配置管理方式

| 项目 | 之前（YAML驱动） | 现在（数据库驱动） |
|------|-----------------|-------------------|
| 数据源 | YAML文件 | 数据库 |
| 配置修改 | 编辑YAML文件 | API/Web UI |
| 生效方式 | 重启应用 | 热重载 |
| 版本控制 | Git管理文件 | 数据库版本表 |
| 审计日志 | 无 | 完整审计日志 |
| 备份方式 | 复制文件 | 导出JSON/YAML |

### 启动流程

```
初始化应用目录 → 加载系统配置 → 初始化数据库 → 从数据库加载设备
```

**关键点**：
- ✅ 数据库是唯一数据源
- ✅ YAML文件仅用于备份和迁移
- ✅ 所有配置变更通过API进行
- ✅ 支持热重载，无需重启

现在你的系统已经完全使用数据库为中心的配置管理方式了！
