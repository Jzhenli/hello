# 数据库为中心的配置管理 - 使用指南

## 概述

XAgent现在使用数据库为中心的配置管理方式，数据库是唯一数据源，YAML文件仅用于导入导出和备份。

## 启动流程

### 自动迁移

当系统启动时，如果数据库中没有设备，会自动检查YAML配置文件并迁移到数据库：

```
[xagent] Starting app...
Loading devices from database...
No enabled devices found in database
Found 1 YAML device files, migrating to database...
Successfully migrated 1 devices from YAML to database
Found 1 enabled devices in database
Loading 1 south devices and 0 north devices
```

### 正常启动

如果数据库中已有设备，则直接从数据库加载：

```
[xagent] Starting app...
Loading devices from database...
Found 5 enabled devices in database
Loading 3 south devices and 2 north devices
```

## 配置管理方式

### 1. 通过API管理（推荐）

所有配置变更都通过REST API进行：

```bash
# 创建设备
curl -X POST http://localhost:8080/api/devices/ \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "modbus_device_1",
    "name": "Modbus Device 1",
    "plugin_name": "modbus_tcp",
    "plugin_config": {
      "host": "192.168.1.100",
      "port": 502
    },
    "enabled": true,
    "points": [
      {
        "name": "temperature",
        "data_type": "float32",
        "unit": "°C",
        "config": {"address": 0}
      }
    ]
  }'

# 更新设备
curl -X PUT http://localhost:8080/api/devices/modbus_device_1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Device Name",
    "plugin_config": {
      "host": "192.168.1.101",
      "port": 502
    }
  }'

# 添加点位
curl -X POST http://localhost:8080/api/devices/modbus_device_1/points \
  -H "Content-Type: application/json" \
  -d '{
    "name": "pressure",
    "data_type": "float32",
    "unit": "kPa",
    "config": {"address": 10}
  }'

# 重载设备（热重载，无需重启）
curl -X POST http://localhost:8080/api/devices/modbus_device_1/reload
```

### 2. 通过Web UI管理

访问 http://localhost:8080/ 使用Web界面进行配置管理：

- 设备管理：创建、查看、编辑、删除设备
- 点位配置：添加、修改、删除点位
- 配置导入导出：支持JSON和YAML格式
- 热重载：配置变更后立即生效

### 3. 通过CLI工具管理

使用迁移工具进行批量操作：

```bash
# 导出配置到YAML文件
python -m xagent.tools.migrate_config export \
  --database ./data/xagent.db \
  --output-dir ./backup

# 从YAML文件导入配置
python -m xagent.tools.migrate_config import \
  --devices-dir ./config/devices \
  --database ./data/xagent.db

# 验证YAML文件
python -m xagent.tools.migrate_config validate \
  --devices-dir ./config/devices
```

## 配置变更生效

### 热重载机制

所有配置变更都会自动触发热重载，无需重启应用：

1. **添加点位**：立即生效，新点位开始采集数据
2. **删除点位**：立即生效，点位停止采集
3. **修改点位配置**：立即生效，使用新配置采集
4. **更新设备配置**：立即生效，插件重新加载

### 手动重载

如果需要手动重载设备：

```bash
# 重载单个设备
curl -X POST http://localhost:8080/api/devices/modbus_device_1/reload

# 批量重载
curl -X POST http://localhost:8080/api/devices/reload \
  -H "Content-Type: application/json" \
  -d '{
    "assets": ["device_1", "device_2"]
  }'
```

## 配置备份和恢复

### 自动备份

系统会在每次配置变更时自动保存版本历史，可以随时回滚：

```bash
# 查看配置历史
curl http://localhost:8080/api/devices/modbus_device_1/history

# 回滚到指定版本
curl -X POST http://localhost:8080/api/devices/modbus_device_1/rollback \
  -H "Content-Type: application/json" \
  -d '{"version": 2}'
```

### 手动备份

定期导出配置到YAML文件：

```bash
# 导出所有设备
curl -X POST http://localhost:8080/api/devices/export > backup_$(date +%Y%m%d).json

# 或使用CLI工具
python -m xagent.tools.migrate_config export \
  --database ./data/xagent.db \
  --output-dir ./backups/$(date +%Y%m%d)
```

## 审计日志

所有配置变更都会记录审计日志：

```bash
# 查询审计日志
curl http://localhost:8080/api/audit/logs?limit=100

# 查询特定设备的变更历史
curl http://localhost:8080/api/audit/logs?entity_type=device&entity_id=modbus_device_1

# 获取审计统计
curl http://localhost:8080/api/audit/stats
```

## 配置模板

使用模板批量创建相似设备：

```python
# 创建模板
template = {
    "name": "modbus_standard",
    "description": "标准Modbus设备模板",
    "plugin_name": "modbus_tcp",
    "plugin_config_template": {
        "host": "${device_ip}",
        "port": 502
    },
    "point_templates": [
        {
            "name": "temperature",
            "data_type": "float32",
            "config": {"address": "${temp_address}"}
        }
    ],
    "variables": {
        "device_ip": "192.168.1.100",
        "temp_address": 0
    }
}

# 从模板创建设备
curl -X POST http://localhost:8080/api/templates/modbus_standard/instantiate \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
        "device_ip": "192.168.1.200",
        "temp_address": 100
    },
    "asset": "modbus_device_2"
  }'
```

## 配置验证

在创建或更新设备前验证配置：

```bash
# 验证设备配置
curl -X POST http://localhost:8080/api/devices/validate \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "modbus_device_1",
    "plugin_name": "modbus_tcp",
    "plugin_config": {
      "host": "192.168.1.100",
      "port": 502
    }
  }'
```

## 配置同步

多实例之间同步配置：

```bash
# 注册远程实例
curl -X POST http://localhost:8080/api/sync/instances \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production",
    "url": "http://192.168.1.100:8080",
    "api_token": "your_token"
  }'

# 同步到远程实例
curl -X POST http://localhost:8080/api/sync/to/production

# 从远程实例同步
curl -X POST http://localhost:8080/api/sync/from/production

# 双向同步
curl -X POST http://localhost:8080/api/sync/bidirectional/production
```

## 最佳实践

### 1. 配置管理流程

1. **开发环境**：在开发环境创建和测试配置
2. **导出配置**：将配置导出为JSON或YAML文件
3. **版本控制**：将配置文件提交到Git仓库
4. **生产部署**：导入配置到生产环境
5. **监控审计**：查看审计日志，监控配置变更

### 2. 备份策略

- **每日备份**：自动导出配置到备份目录
- **版本控制**：将备份文件提交到Git仓库
- **多环境备份**：开发、测试、生产环境分别备份

### 3. 变更管理

- **审批流程**：重要配置变更需要审批
- **变更窗口**：在低峰期进行配置变更
- **回滚准备**：变更前确保可以快速回滚

### 4. 监控告警

- **配置变更告警**：配置变更时发送通知
- **验证失败告警**：配置验证失败时告警
- **同步失败告警**：配置同步失败时告警

## 故障排查

### 1. 配置未生效

**问题**：配置变更后未生效
**解决**：
```bash
# 手动重载设备
curl -X POST http://localhost:8080/api/devices/{asset}/reload

# 检查插件状态
curl http://localhost:8080/api/plugins/status
```

### 2. 迁移失败

**问题**：YAML文件迁移失败
**解决**：
```bash
# 验证YAML文件格式
python -m xagent.tools.migrate_config validate --devices-dir ./config/devices

# 查看详细错误
python -m xagent.tools.migrate_config migrate \
  --devices-dir ./config/devices \
  --database ./data/xagent.db \
  --verbose
```

### 3. 数据库损坏

**问题**：数据库文件损坏
**解决**：
```bash
# 从备份恢复
cp backup/xagent.db data/xagent.db

# 或从YAML文件重新导入
python -m xagent.tools.migrate_config migrate \
  --devices-dir ./config/devices \
  --database ./data/xagent.db \
  --overwrite
```

## 迁移指南

### 从YAML文件迁移

如果你的项目还在使用YAML文件管理配置：

1. **备份现有配置**：
   ```bash
   cp -r config/devices config/devices.backup
   ```

2. **启动应用**：
   系统会自动迁移YAML文件到数据库

3. **验证迁移结果**：
   ```bash
   curl http://localhost:8080/api/devices/
   ```

4. **更新工作流程**：
   - 停止手动编辑YAML文件
   - 使用API或Web UI进行配置管理
   - YAML文件仅用于备份和导入

### 配置文件位置

- **数据库文件**：`data/xagent.db`
- **YAML备份**：`config/devices/*.yaml`（仅用于备份）
- **配置模板**：`config/templates/*.yaml`

## 总结

数据库为中心的配置管理提供了：

- ✅ **数据一致性**：数据库为唯一数据源
- ✅ **版本控制**：完整的配置变更历史
- ✅ **审计追踪**：所有操作都有日志
- ✅ **热重载**：配置变更无需重启
- ✅ **向后兼容**：支持从YAML文件平滑迁移
- ✅ **多实例同步**：支持配置同步
- ✅ **Web UI**：友好的配置管理界面

开始使用新的配置管理方式，享受更可靠、更灵活的设备管理体验！
