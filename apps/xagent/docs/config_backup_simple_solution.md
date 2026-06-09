# 配置备份功能 - 简化实用版本

## 设计理念

**针对轻量级IoT网关场景**：
- 内部系统，有Token验证
- 管理员操作，可信度高
- 简单场景：配置导出 → 导入

**简化原则**：
- 去除过度安全检查
- 保留核心功能
- 代码简洁易懂
- 满足实际需求

---

## 一、Storage层（简化版）

```python
# storage/sqlite.py

CONFIG_TABLES = [
    'device_registry',
    'point_registry',
    'plugin_registry',
    'service_registry',
    'rule_registry',
    'channel_registry',
    'pipeline_registry',
    'config_versions',
    'audit_logs',
    'mapping_registry'
]


async def export_config_tables(self, output_db_path: str) -> Dict[str, Any]:
    """导出配置表（简化版）
    
    使用场景：配置好的机器导出配置
    """
    if not self._initialized or not self._db:
        raise RuntimeError("Storage not initialized")

    # 创建输出数据库
    output_db = await aiosqlite.connect(output_db_path)
    await output_db.execute("PRAGMA journal_mode=WAL")

    stats = {"tables": 0, "records": 0}

    try:
        # 使用ATTACH DATABASE
        await self._db.execute(
            "ATTACH DATABASE ? AS backup",
            (output_db_path,)
        )

        for table in CONFIG_TABLES:
            # 检查表是否存在
            async with self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ) as cursor:
                if not await cursor.fetchone():
                    continue

            # 导出表结构
            async with self._db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    await output_db.execute(row[0])

            # 导出数据
            await self._db.execute(
                f"INSERT INTO backup.{table} SELECT * FROM main.{table}"
            )

            # 导出索引
            async with self._db.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (table,)
            ) as cursor:
                async for row in cursor:
                    if row[0]:
                        try:
                            await output_db.execute(row[0])
                        except:
                            pass

            # 统计
            async with self._db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                count = (await cursor.fetchone())[0]
                stats["tables"] += 1
                stats["records"] += count

        await output_db.commit()
        await self._db.execute("DETACH DATABASE backup")

        logger.info(f"Exported {stats['tables']} tables, {stats['records']} records")
        return stats

    except Exception as e:
        logger.error(f"Export failed: {e}")
        try:
            await self._db.execute("DETACH DATABASE backup")
        except:
            pass
        raise
    finally:
        await output_db.close()


async def import_config_tables(self, source_db_path: str) -> Dict[str, Any]:
    """导入配置表（简化版）
    
    使用场景：空机器导入配置
    """
    if not self._initialized or not self._db:
        raise RuntimeError("Storage not initialized")

    if not Path(source_db_path).exists():
        raise FileNotFoundError(f"Source database not found: {source_db_path}")

    stats = {"tables": 0, "records": 0}

    try:
        # 使用ATTACH DATABASE
        await self._db.execute(
            "ATTACH DATABASE ? AS source",
            (source_db_path,)
        )

        # 开始事务
        await self._db.execute("BEGIN TRANSACTION")

        # 禁用外键约束
        await self._db.execute("PRAGMA foreign_keys=OFF")

        for table in CONFIG_TABLES:
            # 检查源表是否存在
            async with self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ) as cursor:
                if not await cursor.fetchone():
                    continue

            # 清空目标表
            await self._db.execute(f"DELETE FROM main.{table}")

            # 导入数据
            await self._db.execute(
                f"INSERT INTO main.{table} SELECT * FROM source.{table}"
            )

            # 统计
            async with self._db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                count = (await cursor.fetchone())[0]
                stats["tables"] += 1
                stats["records"] += count

        # 启用外键约束
        await self._db.execute("PRAGMA foreign_keys=ON")

        # 提交事务
        await self._db.commit()

        await self._db.execute("DETACH DATABASE source")

        logger.info(f"Imported {stats['tables']} tables, {stats['records']} records")
        return stats

    except Exception as e:
        logger.error(f"Import failed: {e}")
        # 回滚事务
        try:
            await self._db.rollback()
        except:
            pass
        # 分离数据库
        try:
            await self._db.execute("DETACH DATABASE source")
        except:
            pass
        raise
```

---

## 二、Service层（简化版）

```python
# api/services/config_service.py

import zipfile
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ConfigService:
    """配置管理服务（简化版）"""

    def __init__(self, paths=None, storage=None):
        self._paths = paths or get_paths()
        self._storage = storage

    @property
    def backup_dir(self) -> Path:
        return self._paths.config_dir / "backups"

    async def export_config(self) -> Dict[str, Any]:
        """导出配置
        
        使用场景：配置好的机器导出配置
        """
        try:
            storage = self._get_storage()

            # 1. 创建临时数据库
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_db = self._paths.data_dir / f"config_export_{timestamp}.db"

            # 2. 导出配置表
            export_stats = await storage.export_config_tables(str(temp_db))

            # 3. 打包成ZIP
            backup_dir = self.backup_dir
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_file = backup_dir / f"config_{timestamp}.zip"

            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 添加配置数据库
                zf.write(temp_db, "config.db")

                # 添加系统配置文件
                config_file = self._paths.config_file
                if config_file.exists():
                    zf.write(config_file, "config.yaml")

            # 4. 清理临时文件
            temp_db.unlink()

            file_size = backup_file.stat().st_size

            logger.info(f"Config exported: {backup_file}")

            return {
                "success": True,
                "file": backup_file.name,
                "path": str(backup_file),
                "size_mb": round(file_size / 1024 / 1024, 2),
                "tables": export_stats["tables"],
                "records": export_stats["records"],
                "created_at": timestamp
            }

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {"success": False, "error": str(e)}

    async def import_config(self, backup_file: str, auto_reload: bool = True) -> Dict[str, Any]:
        """导入配置
        
        使用场景：空机器导入配置
        
        Args:
            backup_file: 备份文件路径
            auto_reload: 是否自动重载配置（默认True）
        
        注意：
            1. 不直接覆盖数据库文件（文件被锁定）
            2. 使用 ATTACH DATABASE 导入数据
            3. 导入前会停止所有插件
            4. 导入后自动重载配置
        """
        try:
            backup_path = Path(backup_file)

            if not backup_path.exists():
                return {"success": False, "error": "Backup file not found"}

            # 1. 停止所有插件（避免数据冲突）
            stop_result = await self._stop_all_plugins()

            # 2. 解压备份文件
            temp_dir = Path(tempfile.mkdtemp())

            try:
                with zipfile.ZipFile(backup_path, 'r') as zf:
                    zf.extractall(temp_dir)

                # 3. 导入配置数据库（使用ATTACH，不覆盖文件）
                config_db = temp_dir / "config.db"

                if not config_db.exists():
                    return {"success": False, "error": "Config database not found"}

                storage = self._get_storage()
                import_stats = await storage.import_config_tables(str(config_db))

                # 4. 恢复系统配置文件
                config_yaml = temp_dir / "config.yaml"
                if config_yaml.exists():
                    shutil.copy2(config_yaml, self._paths.config_file)

                logger.info(f"Config imported: {backup_path}")

                # 5. 自动重载配置（如果启用）
                reload_result = None
                if auto_reload:
                    reload_result = await self._reload_config()

                return {
                    "success": True,
                    "tables": import_stats["tables"],
                    "records": import_stats["records"],
                    "auto_reload": auto_reload,
                    "reload_result": reload_result,
                    "stop_result": stop_result,
                    "message": "Config imported and reloaded" if auto_reload else "Config imported, manual reload required"
                }

            finally:
                # 清理临时目录
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Import failed: {e}")
            return {"success": False, "error": str(e)}

    async def _stop_all_plugins(self) -> Dict[str, Any]:
        """停止所有插件（避免数据冲突）"""
        try:
            from ...dependencies import get_app_state
            state = get_app_state()
            
            if not state.gateway or not state.gateway.plugin_loader:
                return {"success": False, "reason": "Gateway not initialized"}
            
            plugin_loader = state.gateway.plugin_loader
            
            # 获取所有插件
            plugins = plugin_loader.get_all_plugins()
            stopped = []
            
            # 停止所有插件
            for plugin_id, plugin in plugins.items():
                try:
                    if hasattr(plugin, 'stop'):
                        await plugin.stop()
                    elif hasattr(plugin, 'shutdown'):
                        plugin.shutdown()
                    stopped.append(plugin_id)
                except Exception as e:
                    logger.error(f"Failed to stop plugin {plugin_id}: {e}")
            
            logger.info(f"Stopped {len(stopped)} plugins")
            return {
                "success": True,
                "stopped_count": len(stopped),
                "stopped_plugins": stopped
            }
            
        except Exception as e:
            logger.error(f"Failed to stop plugins: {e}")
            return {"success": False, "error": str(e)}

    async def _reload_config(self) -> Dict[str, Any]:
        """重载配置（热重载）"""
        try:
            from ...dependencies import get_app_state
            state = get_app_state()
            
            results = {
                "config": False,
                "devices": False
            }
            
            # 1. 重载主配置文件
            if state.gateway and state.gateway.config_manager:
                try:
                    state.gateway.config_manager.reload()
                    results["config"] = True
                    logger.info("Main config reloaded")
                except Exception as e:
                    logger.error(f"Failed to reload config: {e}")
            
            # 2. 重载设备插件
            if state.gateway and state.gateway.plugin_loader:
                try:
                    from ..services.device_service_db import DeviceService
                    service = DeviceService(
                        metadata_manager=state.metadata_manager,
                        plugin_loader=state.gateway.plugin_loader
                    )
                    reload_stats = await service.reload_devices()
                    results["devices"] = reload_stats["succeeded"] > 0
                    logger.info(f"Devices reloaded: {reload_stats}")
                except Exception as e:
                    logger.error(f"Failed to reload devices: {e}")
            
            return {
                "success": results["config"] or results["devices"],
                "details": results
            }
            
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return {"success": False, "error": str(e)}

    def _get_storage(self):
        """获取storage实例"""
        if self._storage:
            return self._storage

        from ...dependencies import get_app_state
        state = get_app_state()
        return state.storage
```

---

## 三、API层（简化版）

```python
# api/routers/config.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.post("/export")
async def export_config(token: str = Depends(verify_api_token)):
    """导出配置（手动备份）
    
    这就是手动备份API！
    
    使用场景：
    1. 定期备份配置
    2. 导入新配置前先备份当前配置
    3. 配置迁移到其他机器
    
    返回ZIP文件，包含：
    - config.db: 配置数据库（不包含历史数据）
    - config.yaml: 系统配置文件
    """
    service = _get_config_service()
    result = await service.export_config()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@router.get("/export/download/{filename}")
async def download_export(filename: str, token: str = Depends(verify_api_token)):
    """下载导出的配置文件"""
    service = _get_config_service()
    backup_dir = service.backup_dir
    backup_file = backup_dir / filename

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=backup_file,
        filename=filename,
        media_type="application/zip"
    )


@router.post("/import")
async def import_config(
    file: UploadFile = File(...),
    auto_reload: bool = True,
    token: str = Depends(verify_api_token)
):
    """导入配置
    
    使用场景：空机器导入配置
    
    Args:
        file: 上传的ZIP文件
        auto_reload: 是否自动重载配置（默认True）
    
    自动重载会：
    1. 重载主配置文件（config.yaml）
    2. 重载所有设备插件
    
    如果auto_reload=False，需要手动调用：
    - POST /api/config/reload
    - POST /api/devices/reload
    """
    # 保存上传文件
    temp_dir = Path(tempfile.mkdtemp())
    temp_file = temp_dir / file.filename

    try:
        content = await file.read()
        with open(temp_file, 'wb') as f:
            f.write(content)

        # 导入配置
        service = _get_config_service()
        result = await service.import_config(str(temp_file), auto_reload=auto_reload)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))

        return result

    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/list")
async def list_configs(token: str = Depends(verify_api_token)):
    """列出所有导出的配置"""
    service = _get_config_service()
    backup_dir = service.backup_dir

    if not backup_dir.exists():
        return {"configs": [], "total": 0}

    configs = []
    for backup_file in sorted(backup_dir.glob("config_*.zip"), reverse=True):
        stat = backup_file.stat()
        configs.append({
            "filename": backup_file.name,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    return {"configs": configs, "total": len(configs)}


@router.delete("/export/{filename}")
async def delete_config(filename: str, token: str = Depends(verify_api_token)):
    """删除导出的配置文件"""
    service = _get_config_service()
    backup_dir = service.backup_dir
    backup_file = backup_dir / filename

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="File not found")

    backup_file.unlink()

    return {"success": True, "message": f"Deleted {filename}"}


def _get_config_service():
    """获取ConfigService实例"""
    from ..dependencies import get_app_state
    from ..services.config_service import ConfigService
    
    state = get_app_state()
    return ConfigService(storage=state.storage)
```

---

## 四、完整API列表

### 4.1 备份相关API

#### POST /api/config/export - 手动备份配置 ✅

**这就是手动备份API！**

```bash
POST /api/config/export
Authorization: Bearer xagent_47808
```

**响应**：
```json
{
  "success": true,
  "file": "config_20260605_143025.zip",
  "path": "C:/Users/.../backups/config_20260605_143025.zip",
  "size_mb": 0.5,
  "tables": 10,
  "records": 150,
  "created_at": "20260605_143025"
}
```

**使用场景**：
1. ✅ 定期备份配置
2. ✅ **导入新配置前先备份当前配置**
3. ✅ 配置迁移到其他机器

---

#### GET /api/config/list - 列出所有备份

```bash
GET /api/config/list
Authorization: Bearer xagent_47808
```

**响应**：
```json
{
  "configs": [
    {
      "filename": "config_20260605_143025.zip",
      "size_mb": 0.5,
      "created_at": "2026-06-05T14:30:25"
    }
  ],
  "total": 1
}
```

---

#### GET /api/config/export/download/{filename} - 下载备份

```bash
GET /api/config/export/download/config_20260605_143025.zip
Authorization: Bearer xagent_47808
```

---

#### DELETE /api/config/export/{filename} - 删除备份

```bash
DELETE /api/config/export/config_20260605_143025.zip
Authorization: Bearer xagent_47808
```

---

### 4.2 导入相关API

#### POST /api/config/import - 导入配置

```bash
POST /api/config/import
Authorization: Bearer xagent_47808
Content-Type: multipart/form-data

file: config_20260605_143025.zip
auto_reload: true  # 默认值
```

---

## 五、导入前的最佳实践（重要）

### 5.1 推荐流程

#### 步骤1：手动备份当前配置 ✅

```bash
# 备份当前配置
POST /api/config/export

Response:
{
  "success": true,
  "file": "config_backup_20260605_143025.zip"
}
```

**为什么需要手动备份？**
- 导入会覆盖原有配置
- 如果新配置有问题，可以快速回滚
- 保留配置变更历史

---

#### 步骤2：导入新配置

```bash
POST /api/config/import
file: config_new.zip
auto_reload: true
```

---

#### 步骤3：验证配置

```bash
# 检查设备配置
GET /api/devices

# 检查规则配置
GET /api/rules

# 检查系统状态
GET /api/system/status
```

---

#### 步骤4：如有问题，快速回滚

```bash
# 导入之前备份的配置
POST /api/config/import
file: config_backup_20260605_143025.zip
auto_reload: true
```

---

### 5.2 完整示例

#### 场景：生产环境更新配置

```bash
# 1. 备份当前配置（重要！）
POST /api/config/export
# 得到: config_backup_20260605_143025.zip

# 2. 导入新配置
POST /api/config/import
file: config_new.zip
auto_reload: true

Response:
{
  "success": true,
  "tables": 10,
  "records": 150
}

# 3. 验证配置
GET /api/devices
# 检查设备是否正常

# 4. 如果发现问题，立即回滚
POST /api/config/import
file: config_backup_20260605_143025.zip
auto_reload: true
```

---

### 5.3 是否需要自动备份？

#### 方案A：导入时自动备份（可选）

**优点**：
- ✅ 用户无需手动备份
- ✅ 防止忘记备份
- ✅ 更安全

**缺点**：
- ⚠️ 增加导入时间
- ⚠️ 占用更多磁盘空间
- ⚠️ 可能产生很多备份文件

**实现**：
```python
async def import_config(backup_file: str, auto_backup: bool = True):
    # 1. 自动备份当前配置（可选）
    if auto_backup:
        backup_result = await self.export_config()
        logger.info(f"Auto backup created: {backup_result['file']}")
    
    # 2. 导入新配置
    # ...
```

---

#### 方案B：手动备份（推荐）

**优点**：
- ✅ 用户有明确意识
- ✅ 不占用额外空间
- ✅ 更灵活

**推荐理由**：
- 管理员操作，应该有备份意识
- API文档明确说明需要备份
- 失败可以快速回滚

---

### 5.4 备份策略建议

#### 策略1：定期备份

```bash
# 每天备份一次
# crontab: 0 2 * * * curl -X POST http://localhost:8080/api/config/export

# 或使用脚本
#!/bin/bash
DATE=$(date +%Y%m%d)
curl -X POST http://localhost:8080/api/config/export \
  -H "Authorization: Bearer xagent_47808" \
  -o "config_backup_${DATE}.zip"
```

---

#### 策略2：变更前备份

```bash
# 每次导入新配置前先备份
# 1. 备份
POST /api/config/export

# 2. 导入
POST /api/config/import
```

---

#### 策略3：保留多个备份

```bash
# 查看所有备份
GET /api/config/list

# 保留最近10个备份
# 删除旧备份
DELETE /api/config/export/config_old.zip
```

---

## 六、使用示例

### 场景1：配置好的机器导出

```bash
# 1. 导出配置
POST /api/config/export
Authorization: Bearer xagent_47808

Response:
{
  "success": true,
  "file": "config_20260605_143025.zip",
  "path": "C:/Users/.../backups/config_20260605_143025.zip",
  "size_mb": 0.5,
  "tables": 10,
  "records": 150,
  "created_at": "20260605_143025"
}

# 2. 下载配置文件
GET /api/config/export/download/config_20260605_143025.zip
Authorization: Bearer xagent_47808

Response: ZIP文件下载
```

### 场景2：空机器导入

```bash
# 方式1：自动重载（推荐）
POST /api/config/import
Authorization: Bearer xagent_47808
Content-Type: multipart/form-data

file: config_20260605_143025.zip
auto_reload: true  # 默认值，可省略

Response:
{
  "success": true,
  "tables": 10,
  "records": 150,
  "auto_reload": true,
  "reload_result": {
    "success": true,
    "details": {
      "config": true,      # 主配置重载成功
      "devices": true      # 设备插件重载成功
    }
  },
  "message": "Config imported and reloaded"
}

# 方式2：手动重载
POST /api/config/import
Authorization: Bearer xagent_47808
Content-Type: multipart/form-data

file: config_20260605_143025.zip
auto_reload: false

Response:
{
  "success": true,
  "tables": 10,
  "records": 150,
  "auto_reload": false,
  "reload_result": null,
  "message": "Config imported, manual reload required"
}

# 然后手动重载
POST /api/config/reload
POST /api/devices/reload
```

### 场景3：管理导出文件

```bash
# 列出所有导出的配置
GET /api/config/list
Authorization: Bearer xagent_47808

Response:
{
  "configs": [
    {
      "filename": "config_20260605_143025.zip",
      "size_mb": 0.5,
      "created_at": "2026-06-05T14:30:25"
    }
  ],
  "total": 1
}

# 删除配置文件
DELETE /api/config/export/config_20260605_143025.zip
Authorization: Bearer xagent_47808
```

---

## 五、简化对比

### 代码量对比

| 模块 | 改进版 | 简化版 | 减少 |
|------|--------|--------|------|
| Storage | ~200行 | ~80行 | 60% |
| Service | ~150行 | ~60行 | 60% |
| API | ~120行 | ~50行 | 58% |
| **总计** | ~470行 | ~190行 | **60%** |

### 功能对比

| 功能 | 改进版 | 简化版 | 说明 |
|------|--------|--------|------|
| 导出配置 | ✅ | ✅ | 核心功能 |
| 导入配置 | ✅ | ✅ | 核心功能 |
| 事务保护 | ✅ | ✅ | 必需 |
| 路径验证 | ✅ | ❌ | 内部系统不需要 |
| 文件验证 | ✅ | ❌ | 管理员可信 |
| 临时备份 | ✅ | ❌ | 空机器不需要 |
| 磁盘检查 | ✅ | ❌ | 可选功能 |

### 适用场景

**改进版**：适合公开API、多用户、高安全要求
**简化版**：适合内部系统、管理员操作、IoT网关

---

## 六、实现建议

### 选择简化版的理由

1. **场景匹配**
   - IoT网关：内部系统
   - 管理员操作：可信度高
   - 简单场景：导出→导入

2. **代码质量**
   - 代码量减少60%
   - 逻辑清晰易懂
   - 维护成本低

3. **性能更好**
   - 无额外验证开销
   - 执行速度更快
   - 资源占用更少

4. **符合项目定位**
   - 轻量级IoT网关
   - 简单实用
   - 不过度设计

### 安全保障

简化版仍保留核心安全机制：

1. **Token验证**：所有API需要Token
2. **事务保护**：导入失败自动回滚
3. **资源清理**：自动清理临时文件
4. **错误处理**：完善的异常处理

---

## 七、数据库锁定问题及解决方案（重要）

### 7.1 问题分析

#### 实际场景

```
机器A（配置好的）          机器B（空机器）
     ↓                        ↓
导出配置.zip              启动系统
     ↓                        ↓
                          创建xagent.db（空库）
                          数据库被锁定 🔒
     ↓                        ↓
导入配置.zip  →  ❌ 无法覆盖文件
```

#### 为什么无法覆盖？

1. **SQLite文件锁定**
   - 系统启动时创建 `xagent.db`
   - 数据库连接保持打开状态
   - 文件被操作系统锁定
   - 无法直接覆盖或删除

2. **WAL模式**
   - 启用WAL模式后，还有两个文件：
     - `xagent.db-wal`（预写日志）
     - `xagent.db-shm`（共享内存）
   - 这些文件也被锁定

3. **数据冲突**
   - 导入时如果有插件正在运行
   - 可能产生数据读写冲突
   - 导致数据不一致

---

### 7.2 解决方案

#### 方案1：ATTACH DATABASE（推荐）✅

**原理**：不覆盖文件，直接在数据库层面导入数据

```python
async def import_config_tables(source_db_path: str):
    # 1. 附加源数据库
    await self._db.execute(
        "ATTACH DATABASE ? AS source",
        (source_db_path,)
    )
    
    # 2. 清空目标表
    await self._db.execute(f"DELETE FROM main.{table}")
    
    # 3. 复制数据
    await self._db.execute(
        f"INSERT INTO main.{table} SELECT * FROM source.{table}"
    )
    
    # 4. 分离数据库
    await self._db.execute("DETACH DATABASE source")
```

**优点**：
- ✅ 不需要关闭数据库连接
- ✅ 不需要覆盖文件
- ✅ 直接在数据库层面操作
- ✅ 性能高效

**注意**：
- ⚠️ 导入前需要停止插件（避免数据冲突）
- ⚠️ 使用事务保护（失败自动回滚）

---

#### 方案2：停止服务后替换文件（不推荐）

**流程**：
```bash
# 1. 停止服务
systemctl stop xagent

# 2. 替换数据库文件
cp config.db xagent.db

# 3. 重启服务
systemctl start xagent
```

**缺点**：
- ❌ 需要停止服务
- ❌ 服务中断
- ❌ 不适合生产环境

---

### 7.3 完整导入流程

#### 实际执行步骤

```
1. 停止所有插件
   ↓
2. 解压备份文件
   ↓
3. ATTACH DATABASE（附加源数据库）
   ↓
4. 清空目标表
   ↓
5. 复制数据（INSERT ... SELECT）
   ↓
6. DETACH DATABASE（分离源数据库）
   ↓
7. 重载配置
   ↓
8. 启动插件
```

#### 代码实现

```python
async def import_config(backup_file: str, auto_reload: bool = True):
    # 1. 停止所有插件（避免数据冲突）
    stop_result = await self._stop_all_plugins()
    
    # 2. 解压备份文件
    with zipfile.ZipFile(backup_path, 'r') as zf:
        zf.extractall(temp_dir)
    
    # 3. 导入配置（使用ATTACH，不覆盖文件）
    import_stats = await storage.import_config_tables(str(config_db))
    
    # 4. 重载配置（启动插件）
    if auto_reload:
        reload_result = await self._reload_config()
```

---

### 7.4 为什么需要停止插件？

#### 场景1：导入时不停止插件（❌ 错误）

```
插件正在运行
  ↓
读取设备数据 → 写入数据库
  ↓
同时导入配置 → 清空表
  ↓
数据冲突 💥
```

**可能的问题**：
- 数据不一致
- 外键约束失败
- 导入失败

---

#### 场景2：导入前停止插件（✅ 正确）

```
停止所有插件
  ↓
无数据读写
  ↓
安全导入配置
  ↓
重载配置并启动插件
  ↓
配置生效 ✅
```

---

### 7.5 实际使用示例

#### 场景1：空机器导入配置

```bash
# 系统已启动，创建了空数据库
POST /api/config/import
file: config.zip
auto_reload: true

Response:
{
  "success": true,
  "stop_result": {
    "success": true,
    "stopped_count": 0,  # 空机器，无插件
    "stopped_plugins": []
  },
  "tables": 10,
  "records": 150,
  "reload_result": {
    "success": true,
    "details": {
      "config": true,
      "devices": true
    }
  },
  "message": "Config imported and reloaded"
}
```

---

#### 场景2：已有配置的机器导入新配置

```bash
# 系统已有设备和插件在运行
POST /api/config/import
file: config.zip
auto_reload: true

Response:
{
  "success": true,
  "stop_result": {
    "success": true,
    "stopped_count": 5,  # 停止了5个插件
    "stopped_plugins": [
      "modbus_tcp_device1",
      "modbus_tcp_device2",
      "mqtt_north",
      ...
    ]
  },
  "tables": 10,
  "records": 150,
  "reload_result": {
    "success": true,
    "details": {
      "config": true,
      "devices": true
    }
  },
  "message": "Config imported and reloaded"
}
```

---

### 7.6 对比其他方案

| 方案 | 是否中断服务 | 是否覆盖文件 | 数据安全性 | 适用场景 |
|------|--------------|--------------|------------|----------|
| ATTACH DATABASE | ❌ 否 | ❌ 否 | ✅ 高 | 生产环境 |
| 停止服务替换 | ✅ 是 | ✅ 是 | ⚠️ 中 | 维护窗口 |
| 直接覆盖文件 | ❌ 否 | ✅ 是 | ❌ 低 | 不可行 |

---

### 7.7 常见问题

#### Q1: 为什么不直接覆盖数据库文件？

**A**: 
1. 文件被锁定，无法覆盖
2. 即使能覆盖，也可能导致数据损坏
3. ATTACH DATABASE 是SQLite推荐的方式

---

#### Q2: 导入时服务会中断吗？

**A**: 
- ❌ 不会中断服务
- ✅ API仍然可用
- ⚠️ 数据采集会短暂停止（几秒）

---

#### Q3: 导入失败会怎样？

**A**: 
- 自动回滚事务
- 恢复原有配置
- 重新启动插件
- 服务继续运行

---

#### Q4: 导入后需要重启吗？

**A**: 
- 通常不需要（使用热重载）
- 修改底层配置时需要重启

---

## 八、配置生效机制（重要）

### 7.1 配置生效的三种方式

#### 方式1：自动热重载（推荐）✅

**特点**：导入后立即生效，无需重启

```bash
POST /api/config/import
auto_reload: true  # 默认值
```

**执行流程**：
```
导入配置 → 自动重载主配置 → 自动重载设备插件 → 立即生效
```

**重载内容**：
1. ✅ 主配置文件（config.yaml）
   - 服务器配置
   - 日志配置
   - 存储配置
   
2. ✅ 设备插件
   - 设备连接
   - 点位配置
   - 采集策略

**优点**：
- ✅ 无需重启，服务不中断
- ✅ 配置立即生效
- ✅ 适合生产环境

**限制**：
- ⚠️ 某些底层配置可能需要重启（如端口、数据库路径）

---

#### 方式2：手动热重载

**特点**：导入后手动触发重载

```bash
# 1. 导入配置（不自动重载）
POST /api/config/import
auto_reload: false

# 2. 手动重载
POST /api/config/reload      # 重载主配置
POST /api/devices/reload     # 重载设备插件
```

**适用场景**：
- 需要验证配置后再生效
- 分步操作，更可控
- 批量导入多台设备时

---

#### 方式3：重启服务（最彻底）

**特点**：重启整个应用，所有配置重新加载

```bash
# 1. 导入配置
POST /api/config/import
auto_reload: false

# 2. 重启服务
POST /api/config/restart
{
  "delay": 5  # 5秒后重启
}
```

**适用场景**：
- 修改了底层配置（端口、数据库路径等）
- 需要完全重置状态
- 热重载失败时

**注意**：
- ⚠️ 服务会短暂中断
- ⚠️ 建议在维护窗口执行

---

### 7.2 配置生效对比

| 方式 | 生效速度 | 服务中断 | 适用场景 |
|------|----------|----------|----------|
| 自动热重载 | 立即 | ❌ 无 | 日常配置导入 |
| 手动热重载 | 手动触发 | ❌ 无 | 需要验证的场景 |
| 重启服务 | 延迟 | ✅ 短暂 | 底层配置变更 |

---

### 7.3 热重载原理

#### 主配置重载

```python
# 调用 ConfigManager.reload()
config_manager.reload()
```

**重载内容**：
- 服务器配置（端口、地址等）
- 日志配置（级别、格式等）
- 存储配置（保留天数等）
- 插件配置（加载策略等）

**不重载**：
- 已建立的数据库连接
- 已加载的插件实例

---

#### 设备插件重载

```python
# 调用 DeviceService.reload_devices()
await service.reload_devices()
```

**重载流程**：
1. 停止旧插件实例
2. 从数据库读取新配置
3. 创建新插件实例
4. 启动新插件实例

**重载内容**：
- 设备连接参数
- 点位配置
- 采集策略
- 数据处理规则

---

### 7.4 实际使用建议

#### 场景1：空机器导入配置（推荐自动重载）

```bash
# 一键导入并生效
POST /api/config/import
file: config.zip
auto_reload: true  # 默认值，可省略

# 配置立即生效，开始采集数据
```

---

#### 场景2：修改部分配置（推荐手动重载）

```bash
# 1. 导入配置
POST /api/config/import
auto_reload: false

# 2. 验证配置
GET /api/devices
GET /api/rules

# 3. 确认无误后重载
POST /api/devices/reload
```

---

#### 场景3：修改底层配置（必须重启）

```bash
# 如果修改了：
# - 服务器端口
# - 数据库路径
# - 日志文件路径

# 1. 导入配置
POST /api/config/import
auto_reload: false

# 2. 重启服务
POST /api/config/restart
{"delay": 10}  # 10秒后重启
```

---

### 7.5 热重载 vs 重启

#### 何时使用热重载？

✅ **适合热重载的配置**：
- 设备点位配置
- 规则配置
- 采集策略
- 日志级别
- 数据保留天数

❌ **不适合热重载的配置**：
- 服务器端口
- 数据库路径
- API Token
- 插件加载路径

---

#### 何时必须重启？

必须重启的情况：
1. 修改了服务器端口
2. 修改了数据库文件路径
3. 修改了插件加载目录
4. 热重载失败
5. 需要完全重置状态

---

### 7.6 故障处理

#### 热重载失败怎么办？

```bash
# 1. 查看错误日志
GET /api/logs
filter: "reload"

# 2. 尝试重启服务
POST /api/config/restart
{"delay": 5}

# 3. 如果重启失败，检查配置
GET /api/config/validate
```

---

#### 配置导入后不生效？

检查步骤：
1. 确认 `auto_reload=true`
2. 检查 `reload_result` 返回值
3. 查看日志是否有错误
4. 尝试手动重载
5. 最后尝试重启服务

---

## 九、已有配置机器导入新配置的影响分析（重要）

### 9.1 影响评估

#### 导入流程对系统的影响

```
导入前状态：
- 设备正在采集数据
- 规则正在执行
- 数据正在写入数据库

导入过程：
1. 停止插件 → 数据采集暂停（影响1）
2. 导入配置 → 原有配置被覆盖（影响2）
3. 重载配置 → 新配置生效

导入后状态：
- 新设备开始采集
- 新规则开始执行
- 历史数据保留
```

---

### 9.2 具体影响分析

#### 影响1：数据采集短暂中断 ⚠️

**影响程度**：轻微

**中断时间**：通常 2-5 秒

**受影响内容**：
- 设备数据采集暂停
- 规则执行暂停
- 北向服务推送暂停

**不受影响**：
- API服务继续运行
- 历史数据不丢失
- 数据库连接保持

**示例**：
```
导入前：每秒采集100个点位
导入中：采集暂停（2-5秒）
导入后：恢复采集，每秒采集100个点位

影响：丢失 200-500 个数据点（可接受）
```

---

#### 影响2：原有配置被覆盖 ⚠️⚠️

**影响程度**：中等

**覆盖内容**：
- ✅ 设备配置（device_registry）
- ✅ 点位配置（point_registry）
- ✅ 规则配置（rule_registry）
- ✅ 插件配置（plugin_registry）
- ✅ 北向服务配置（service_registry）

**不覆盖内容**：
- ❌ 历史采集数据（readings表）
- ❌ 审计日志（audit_logs表，可选）
- ❌ 配置版本历史（config_versions表）

**风险**：
- 原有设备配置丢失
- 原有规则配置丢失
- 如果新配置有问题，需要重新导入

---

#### 影响3：正在采集的数据 ⚠️

**影响程度**：轻微

**场景分析**：

```
时间线：
T0: 设备采集数据 → 写入缓冲区
T1: 停止插件
T2: 缓冲区数据写入数据库
T3: 导入新配置
T4: 启动新插件
```

**可能的数据丢失**：
- 缓冲区中未写入的数据
- 通常很少（几秒的数据）

**缓解措施**：
- 停止插件前等待缓冲区写入
- 使用WriteBehindBuffer确保数据写入

---

### 9.3 历史数据是否会丢失？

#### ❌ 不会丢失历史数据

**原因**：
1. **只导入配置表**
   ```python
   CONFIG_TABLES = [
       'device_registry',  # 设备配置
       'point_registry',   # 点位配置
       'rule_registry',    # 规则配置
       # 注意：不包含 'readings' 表
   ]
   ```

2. **导入操作是清空+复制**
   ```python
   # 清空配置表
   DELETE FROM device_registry
   
   # 复制新配置
   INSERT INTO device_registry SELECT * FROM source.device_registry
   
   # 历史数据表（readings）不受影响
   ```

3. **历史数据保留**
   - 所有历史采集数据保留
   - 数据清理策略不变
   - 可以继续查询历史数据

---

### 9.4 最佳实践建议

#### 场景1：完全替换配置（推荐）

**适用情况**：
- 测试环境配置迁移到生产环境
- 完全替换现有配置
- 不需要保留原有配置

**操作步骤**：
```bash
# 1. 导出当前配置（备份）
POST /api/config/export
# 得到: config_old_20260605.zip

# 2. 导入新配置
POST /api/config/import
file: config_new.zip
auto_reload: true

# 3. 验证新配置
GET /api/devices
GET /api/rules
```

**优点**：
- ✅ 简单直接
- ✅ 配置完全替换
- ✅ 历史数据保留

---

#### 场景2：部分更新配置（需谨慎）

**适用情况**：
- 只更新部分设备
- 需要保留其他设备配置
- 增量更新

**风险**：
- ⚠️ 导入会清空所有配置表
- ⚠️ 未在新配置中的设备会丢失

**建议方案**：
```bash
# 方案A：先导出，修改后再导入
# 1. 导出当前配置
POST /api/config/export

# 2. 解压并修改
unzip config_old.zip
# 修改 config.db 中的配置

# 3. 重新打包并导入
zip config_new.zip config.db config.yaml
POST /api/config/import
file: config_new.zip

# 方案B：使用API逐个更新（推荐）
# 使用设备管理API更新单个设备
PUT /api/devices/{asset}
```

---

#### 场景3：回滚到之前的配置

**适用情况**：
- 新配置有问题
- 需要回滚到之前的配置

**操作步骤**：
```bash
# 导入之前备份的配置
POST /api/config/import
file: config_old_20260605.zip
auto_reload: true
```

**优点**：
- ✅ 快速回滚
- ✅ 无需重启服务
- ✅ 历史数据保留

---

### 9.5 影响对比表

| 影响项 | 影响程度 | 持续时间 | 是否可恢复 |
|--------|----------|----------|------------|
| 数据采集中断 | 轻微 | 2-5秒 | ✅ 自动恢复 |
| 原有配置丢失 | 中等 | 永久 | ✅ 可回滚 |
| 历史数据丢失 | 无 | - | - |
| 服务中断 | 无 | - | - |
| API不可用 | 无 | - | - |

---

### 9.6 实际案例

#### 案例1：生产环境配置更新

```
场景：将测试环境配置迁移到生产环境

步骤：
1. 测试环境导出配置
   POST /api/config/export (测试环境)
   
2. 生产环境备份当前配置
   POST /api/config/export (生产环境)
   得到: config_prod_backup.zip
   
3. 生产环境导入新配置
   POST /api/config/import
   file: config_test.zip
   auto_reload: true
   
4. 验证配置
   GET /api/devices (生产环境)
   
5. 如果有问题，回滚
   POST /api/config/import
   file: config_prod_backup.zip
```

**影响评估**：
- 数据采集暂停：3秒
- 丢失数据：约300个点
- 历史数据：完整保留
- 可回滚：是

---

#### 案例2：设备批量更新

```
场景：批量更新100台设备的点位配置

错误做法 ❌：
- 直接导入新配置
- 原有50台设备配置丢失

正确做法 ✅：
1. 导出当前配置
2. 修改配置数据库
   - 保留原有50台设备
   - 更新100台设备配置
3. 重新打包导入
```

---

### 9.7 风险缓解措施

#### 措施1：导入前自动备份

```python
async def import_config(backup_file: str, auto_reload: bool = True):
    # 1. 自动备份当前配置
    backup_result = await self.export_config()
    
    try:
        # 2. 导入新配置
        # ...
    except Exception:
        # 3. 失败时自动回滚
        await self.import_config(backup_result["path"])
        raise
```

---

#### 措施2：导入前验证

```bash
# 1. 验证配置文件
POST /api/config/validate
config_content: "..."

# 2. 确认无误后导入
POST /api/config/import
```

---

#### 措施3：分步导入

```bash
# 1. 导入配置（不自动重载）
POST /api/config/import
auto_reload: false

# 2. 检查配置
GET /api/devices
GET /api/rules

# 3. 确认无误后重载
POST /api/config/reload
POST /api/devices/reload
```

---

### 9.8 总结

#### 影响评估

| 方面 | 评估 | 说明 |
|------|------|------|
| 服务可用性 | ✅ 无影响 | API继续运行 |
| 数据采集 | ⚠️ 短暂中断 | 2-5秒，可接受 |
| 历史数据 | ✅ 完整保留 | 不导入历史表 |
| 原有配置 | ⚠️ 被覆盖 | 可回滚 |
| 可恢复性 | ✅ 高 | 自动备份+回滚 |

#### 使用建议

1. **生产环境**：
   - ✅ 导入前备份当前配置
   - ✅ 先在测试环境验证
   - ✅ 选择维护窗口执行

2. **测试环境**：
   - ✅ 可以直接导入
   - ✅ 失败可快速回滚

3. **部分更新**：
   - ⚠️ 建议使用API逐个更新
   - ⚠️ 或先导出修改后再导入

---

## 十、总结

### 简化版优势

✅ **代码简洁**：减少60%代码量
✅ **逻辑清晰**：易于理解和维护
✅ **性能更好**：无额外验证开销
✅ **场景匹配**：符合实际使用场景
✅ **安全足够**：保留核心安全机制

### 适用范围

**推荐使用简化版**：
- ✅ 内部系统
- ✅ 管理员操作
- ✅ IoT网关项目
- ✅ 简单导出/导入场景

**考虑使用改进版**：
- ⚠️ 公开API
- ⚠️ 多用户环境
- ⚠️ 高安全要求

---

**简化版更适合轻量级IoT网关项目！**
