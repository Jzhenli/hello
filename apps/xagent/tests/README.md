# 后端 API 测试说明

## 测试概述

本测试套件为 Dashboard 所需的三个核心 API 提供完整的测试覆盖：

1. **系统统计 API** (`/api/system/stats`)
2. **数据质量 API** (`/api/data/quality`)
3. **数据采集统计 API** (`/api/data/stats`)

## 测试文件结构

```
apps/xagent/tests/
├── statistics/
│   ├── test_statistics_manager_extended.py  # StatisticsManager 扩展方法测试
│   └── test_statistics_manager.py           # 原有测试
├── storage/
│   └── test_storage_extended.py             # Storage 扩展方法测试
└── api/
    └── test_system_api.py                   # System API 测试
```

## 测试覆盖范围

### 1. StatisticsManager 扩展方法测试

**文件：** `test_statistics_manager_extended.py`

**测试内容：**
- ✅ 系统资源统计（CPU、内存、磁盘、运行时长等）
- ✅ 数据质量统计
- ✅ 数据采集趋势统计
- ✅ 错误处理和降级方案
- ✅ 无存储时的默认值处理

**测试用例数：** 20+

### 2. Storage 扩展方法测试

**文件：** `test_storage_extended.py`

**测试内容：**
- ✅ 数据质量统计查询
- ✅ 指定时间后的采集量统计
- ✅ 时间范围内的采集量统计
- ✅ 空存储处理
- ✅ 存储关闭后的处理
- ✅ 边界条件测试

**测试用例数：** 15+

### 3. System API 测试

**文件：** `test_system_api.py`

**测试内容：**
- ✅ API 端点正确性
- ✅ 返回数据格式验证
- ✅ 参数传递验证
- ✅ 错误处理和降级方案
- ✅ 响应时间测试
- ✅ 并发请求测试

**测试用例数：** 15+

## 运行测试

### 1. 安装测试依赖

```bash
pip install pytest pytest-asyncio pytest-cov
```

### 2. 运行所有测试

```bash
# 在项目根目录运行
cd apps/xagent
pytest tests/ -v
```

### 3. 运行特定测试文件

```bash
# 运行 StatisticsManager 测试
pytest tests/statistics/test_statistics_manager_extended.py -v

# 运行 Storage 测试
pytest tests/storage/test_storage_extended.py -v

# 运行 API 测试
pytest tests/api/test_system_api.py -v
```

### 4. 运行特定测试用例

```bash
# 运行单个测试类
pytest tests/statistics/test_statistics_manager_extended.py::TestStatisticsManagerExtended -v

# 运行单个测试方法
pytest tests/statistics/test_statistics_manager_extended.py::TestStatisticsManagerExtended::test_get_system_stats_basic -v
```

### 5. 生成测试覆盖率报告

```bash
# 生成覆盖率报告
pytest tests/ --cov=xagent.xcore.statistics --cov=xagent.xcore.storage --cov=xagent.xcore.api.routers.system --cov-report=html

# 查看报告
open htmlcov/index.html
```

## 测试结果示例

### 成功示例

```
=============================== test session starts ===============================
collected 50 items

tests/statistics/test_statistics_manager_extended.py::TestStatisticsManagerExtended::test_get_system_stats_basic PASSED
tests/statistics/test_statistics_manager_extended.py::TestStatisticsManagerExtended::test_get_system_stats_with_storage PASSED
tests/statistics/test_statistics_manager_extended.py::TestStatisticsManagerExtended::test_get_system_stats_no_storage PASSED
...
tests/storage/test_storage_extended.py::TestStorageExtended::test_get_quality_stats_empty_storage PASSED
tests/storage/test_storage_extended.py::TestStorageExtended::test_count_readings_since_with_data PASSED
...
tests/api/test_system_api.py::TestSystemAPI::test_get_system_stats_success PASSED
tests/api/test_system_api.py::TestSystemAPI::test_get_data_quality_success PASSED
tests/api/test_system_api.py::TestSystemAPI::test_get_collection_stats_success PASSED
...

=============================== 50 passed in 3.45s ===============================
```

## 测试要点

### 1. 异步测试

所有测试都使用 `@pytest.mark.asyncio` 装饰器支持异步测试：

```python
@pytest.mark.asyncio
async def test_get_system_stats_basic(self, stats_manager):
    stats = await stats_manager.get_system_stats()
    assert "cpu_usage" in stats
```

### 2. Mock 使用

使用 `unittest.mock` 进行依赖模拟：

```python
@pytest.fixture
def mock_storage(self):
    storage = AsyncMock()
    storage.get_stats = AsyncMock(return_value={"total_readings": 10000})
    return storage
```

### 3. 临时存储

使用 `tmp_path` fixture 创建临时数据库：

```python
@pytest.fixture
async def storage(self, tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(str(db_path))
    await storage.initialize()
    yield storage
    await storage.close()
```

### 4. 错误处理测试

每个测试都包含错误处理验证：

```python
@pytest.mark.asyncio
async def test_get_system_stats_error_handling(self, stats_manager, mock_storage):
    mock_storage.get_stats.side_effect = Exception("Storage error")
    stats_manager._storage = mock_storage

    stats = await stats_manager.get_system_stats()
    assert stats["total_readings"] == 0  # 返回默认值
```

## 持续集成

### GitHub Actions 配置示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-asyncio pytest-cov

    - name: Run tests
      run: pytest tests/ -v --cov=xagent --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## 测试最佳实践

1. **独立性**：每个测试都是独立的，不依赖其他测试
2. **可重复性**：测试结果可重复，使用 mock 和临时数据
3. **清晰性**：测试名称清晰描述测试内容
4. **完整性**：覆盖正常、异常、边界情况
5. **快速性**：测试执行快速，避免长时间等待

## 常见问题

### 1. 测试失败：找不到模块

**解决方案：** 确保在项目根目录运行测试，或设置 PYTHONPATH

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

### 2. 异步测试失败

**解决方案：** 确保安装了 pytest-asyncio

```bash
pip install pytest-asyncio
```

### 3. 数据库锁定错误

**解决方案：** 使用 `tmp_path` fixture 创建临时数据库，避免并发访问冲突

## 测试覆盖率目标

- **Statements**: > 90%
- **Branches**: > 85%
- **Functions**: > 95%
- **Lines**: > 90%

## 贡献指南

添加新功能时，请确保：

1. 为新功能添加测试用例
2. 所有测试通过
3. 测试覆盖率不降低
4. 遵循现有的测试风格

## 联系方式

如有问题，请联系开发团队或提交 Issue。
