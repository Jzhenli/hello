# 共享 AppDir 方案技术白皮书

> 适用场景：ARM32 Ubuntu 工控机，多 Python 应用部署与运维

***

## 目录

- [1. 方案概述](#1-方案概述)
- [2. 原理与架构](#2-原理与架构)
- [3. 开发规范](#3-开发规范)
- [4. 打包流程](#4-打包流程)
- [5. 部署方式](#5-部署方式)
- [6. 升级与回滚](#6-升级与回滚)
- [7. 依赖管理](#7-依赖管理)
- [8. 启动机制](#8-启动机制)
- [9. 方案对比](#9-方案对比)
- [10. ARM32 工控机可行性评估](#10-arm32-工控机可行性评估)
- [11. 风险与缓解](#11-风险与缓解)
- [12. 常见问题](#12-常见问题)
- [附录 A：完整 Workflow 文件](#附录-a完整-workflow-文件)
- [附录 B：项目模板](#附录-b项目模板)

***

## 1. 方案概述

### 1.1 是什么

共享 AppDir 方案是一种 Python 应用打包与部署模式：

- **一个共享 Python runtime**（解释器 + 标准库）安装在目标机器上，所有应用共用
- **每个应用只带自己的代码和 pip 依赖**，以独立目录形式存在
- **通过启动脚本**调用共享 Python 运行，而非自包含的 AppImage

### 1.2 核心思想

```
传统 AppImage：每个应用 = 完整 Python + 标准库 + 代码 + 依赖（50-60 MB/个）
共享 AppDir：  共享 Python + 各应用代码/依赖分离（30 MB + 3-5 MB/个）
```

### 1.3 适用场景

| 场景                           |      是否适用      |
| ---------------------------- | :------------: |
| ARM32 嵌入式/工控机，部署多个 Python 应用 |     ✅ 非常适合     |
| 磁盘空间有限（eMMC/SD 卡）            |  ✅ 节省 50%+ 空间  |
| 需要 FUSE（AppImage 依赖）的环境      |   ✅ 不依赖 FUSE   |
| 需要频繁升级/回滚                    |     ✅ 目录级替换    |
| Python 版本统一可控                |     ✅ 必须统一     |
| 面向桌面用户分发单个应用                 | ❌ AppImage 更友好 |
| 需要"单文件拿来即用"                  |    ❌ 需要安装脚本    |

***

## 2. 原理与架构

### 2.1 目录结构

```
/opt/
├── shared-python/                          ← 共享 Python Runtime
│   ├── bin/
│   │   ├── python3                         ← Python 解释器（所有应用共用）
│   │   └── python3.10 → python3
│   ├── lib/
│   │   ├── libpython3.10.so                ← Python 共享库
│   │   └── python3.10/                     ← 标准库
│   │       ├── json/
│   │       ├── os.py
│   │       ├── ssl/
│   │       ├── logging/
│   │       ├── lib-dynload/                ← C 扩展 .so
│   │       │   ├── _ssl.cpython-310-arm-linux-gnueabihf.so
│   │       │   └── ...
│   │       └── site-packages/              ← 保持为空！
│   └── (无 include/，已精简)
│
├── app1/                                   ← 应用1
│   ├── run.sh                              ← 启动脚本（入口）
│   └── usr/
│       ├── app/                            ← 应用代码
│       │   └── app1/
│       │       ├── __init__.py
│       │       └── __main__.py
│       ├── app_packages/                   ← pip 依赖（仅 app1 的）
│       │   ├── requests/
│       │   └── ...
│       └── lib/                            ← 额外 .so（如有）
│
├── app2/                                   ← 应用2
│   ├── run.sh
│   └── usr/
│       ├── app/
│       │   └── app2/
│       └── app_packages/
│
└── app3/                                   ← 应用3（无 pip 依赖）
    ├── run.sh
    └── usr/
        └── app/
            └── app3/
                └── __main__.py
/usr/local/bin/
├── app1 → /opt/app1/run.sh                 ← 符号链接
├── app2 → /opt/app2/run.sh
└── app3 → /opt/app3/run.sh
```

### 2.2 运行时搜索路径

当用户执行 `app1` 时，Python 的 `import` 搜索顺序：

```
import 某模块时的搜索顺序：
  ① /opt/app1/usr/app/                ← PYTHONPATH 第一项
     └── app1/                         ← 应用代码
  ② /opt/app1/usr/app_packages/       ← PYTHONPATH 第二项
     ├── requests/                     ← app1 的 pip 依赖
     └── ...
  ③ /opt/shared-python/lib/python3.10/ ← Python 自动搜索（解释器所在目录）
     ├── json/                         ← 标准库
     ├── os.py
     ├── ssl/
     └── lib-dynload/                  ← C 扩展 .so
         └── _ssl.cpython-310-*.so
  ④ (无，-s 禁用了用户 site-packages)
```

### 2.3 依赖隔离原理

```
app1 运行时:
  PYTHONPATH = /opt/app1/usr/app:/opt/app1/usr/app_packages
  → 只看到自己的代码和依赖
  → 看不到 app2 的任何东西
app2 运行时:
  PYTHONPATH = /opt/app2/usr/app:/opt/app2/usr/app_packages
  → 只看到自己的代码和依赖
  → 看不到 app1 的任何东西
共享标准库:
  /opt/shared-python/lib/python3.10/
  → 所有应用都能看到
  → 但标准库 API 在小版本间高度稳定，实际不会冲突
```

### 2.4 体积分析

```
3 个应用的体积对比：
独立 AppImage 方案:
  app1.AppImage   ≈ 50 MB  (含 Python + stdlib + 代码 + 依赖)
  app2.AppImage   ≈ 50 MB  (含 Python + stdlib + 代码 + 依赖)
  app3.AppImage   ≈ 50 MB  (含 Python + stdlib + 代码 + 依赖)
  ─────────────────────────
  总计            ≈ 150 MB
共享 AppDir 方案:
  shared-python/  ≈ 25-30 MB  (解释器 + 精简标准库，仅一份)
  app1/           ≈ 3-5 MB    (代码 + pip 依赖)
  app2/           ≈ 2-4 MB    (代码 + pip 依赖)
  app3/           ≈ 0.5 MB    (纯代码，无 pip 依赖)
  ─────────────────────────
  总计            ≈ 32-40 MB
节省: ≈ 110 MB (73%)
```

***

## 3. 开发规范

### 3.1 项目结构

推荐 monorepo 结构：

```
project/
├── .github/
│   └── workflows/
│       └── build-arm32.yml           ← CI/CD 工作流
├── apps/
│   ├── data-collector/               ← 应用1
│   │   ├── requirements.txt          ← pip 依赖声明
│   │   └── src/
│   │       └── data_collector/
│   │           ├── __init__.py
│   │           └── __main__.py
│   ├── device-monitor/               ← 应用2
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── device_monitor/
│   │           ├── __init__.py
│   │           └── __main__.py
│   └── alarm-service/                ← 应用3
│       ├── requirements.txt
│       └── src/
│           └── alarm_service/
│               ├── __init__.py
│               └── __main__.py
└── deploy/
    └── install.sh                    ← 部署脚本模板
```

### 3.2 应用代码规范

每个应用必须满足：

1. **有** **`__main__.py`**：支持 `python -m <module_name>` 启动

```python
# src/data_collector/__main__.py
import sys
from .core import main
if __name__ == "__main__":
    sys.exit(main())
```

1. **有** **`__init__.py`**：使其成为合法 Python 包

```python
# src/data_collector/__init__.py
"""数据采集服务"""
__version__ = "1.2.0"
```

1. **依赖声明在** **`requirements.txt`**：

```
# requirements.txt
pyserial>=3.5
paho-mqtt>=1.6
```

1. **避免硬编码路径**：使用相对于脚本或环境变量的路径

```python
# ❌ 不好
CONFIG = "/opt/app1/config.yaml"
# ✅ 好
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("APP1_CONFIG", os.path.join(SCRIPT_DIR, "config.yaml"))
```

### 3.3 模块名约定

模块名（即 `python -m <module_name>` 中的名字）按以下规则自动检测：

```
检测顺序:
  1. 在构建代码目录中找 __main__.py
  2. __main__.py 所在目录名即为模块名
  3. 如果找不到，fallback 到应用目录名
示例:
  apps/data-collector/src/data_collector/__main__.py
  → 模块名: data_collector
```

***

## 4. 打包流程

### 4.1 打包架构

```
┌──────────────────────────────────────────────────┐
│  GitHub Actions (x86_64 runner)                  │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  ARM32 容器 (QEMU 模拟)                   │   │
│  │                                           │   │
│  │  Phase 1: 环境准备                        │   │
│  │    → 启动 ARM32 容器                      │   │
│  │    → 安装编译工具链                        │   │
│  │                                           │   │
│  │  Phase 2: 构建共享 Python                 │   │
│  │    → 下载 python-build-standalone ARM32   │   │
│  │    → 精简标准库                           │   │
│  │    → 打包 shared-python-base-arm32.tar.gz │   │
│  │                                           │   │
│  │  Phase 3: 构建各应用                      │   │
│  │    → 复制代码                             │   │
│  │    → pip install --target 安装依赖        │   │
│  │    → 生成 run.sh                          │   │
│  │    → 打包 appX-arm32.tar.gz               │   │
│  │                                           │   │
│  │  Phase 4: 组装部署包                      │   │
│  │    → 生成 install.sh                      │   │
│  │    → 汇总到 dist/                         │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Phase 5: 上传 artifacts                        │
└──────────────────────────────────────────────────┘
```

### 4.2 关键步骤详解

#### Step 1：下载 python-build-standalone ARM32

```bash
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.10.16+20241016-armv7-unknown-linux-gnueabihf-install_only.tar.gz"
wget -q "$PBS_URL" -O /tmp/pbs.tar.gz
tar xzf /tmp/pbs.tar.gz -C /tmp/
```

> 版本号映射需根据 [PBS Releases](https://github.com/astral-sh/python-build-standalone/releases) 更新。

#### Step 2：精简标准库

```bash
PYLIB="/workspace/shared-python-base/lib/python3.10"
# 删除控制台应用不需要的模块
for mod in tkinter idlelib lib2to3 unittest pydoc_data curses tty webbrowser; do
  rm -rf "$PYLIB/$mod"
done
# 删除缓存和测试
find "$PYLIB" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$PYLIB" -type d -name test -exec rm -rf {} + 2>/dev/null || true
# 删除头文件（运行时不需要）
rm -rf /workspace/shared-python-base/include
```

#### Step 3：安装应用依赖

```bash
PIP="/workspace/shared-python-base/bin/pip3"
# 安装到应用专属目录
pip install \
  --target /workspace/build/app1/usr/app_packages \
  -r /workspace/apps/app1/requirements.txt
```

> `--target` 将包安装到指定目录，不影响共享 Python 的 site-packages。

#### Step 4：生成启动脚本

```bash
cat > "$BUILD_DIR/run.sh" <<'RUNEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/shared-python/bin/python3"
if [ ! -x "$PYTHON" ]; then
  echo "错误: 未找到共享 Python"
  exit 1
fi
export PYTHONPATH="${SCRIPT_DIR}/usr/app:${SCRIPT_DIR}/usr/app_packages"
export LD_LIBRARY_PATH="/opt/shared-python/lib:${SCRIPT_DIR}/usr/lib:${LD_LIBRARY_PATH}"
exec "$PYTHON" -s -m ${MODULE_NAME} "$@"
RUNEOF
chmod +x "$BUILD_DIR/run.sh"
```

### 4.3 构建产物

```
dist/
├── shared-python-base-arm32.tar.gz    ← 共享 Python（约 25-30 MB）
├── data-collector-arm32.tar.gz        ← 应用1（约 3-5 MB）
├── device-monitor-arm32.tar.gz        ← 应用2（约 2-4 MB）
├── alarm-service-arm32.tar.gz         ← 应用3（约 0.5 MB）
└── install.sh                         ← 部署脚本
```

### 4.4 完整 Workflow

见 [附录 A](#附录-a完整-workflow-文件)。

## 5. 部署方式

### 5.1 首次部署

```bash
# 1. 上传部署包到工控机
scp -r dist/ operator@192.168.1.100:/tmp/deploy/
# 2. SSH 登录工控机
ssh operator@192.168.1.100
# 3. 执行部署
cd /tmp/deploy
sudo bash install.sh
```

`install.sh` 执行的操作：

```
install.sh 执行流程:
  1. 检查 /opt/shared-python 是否存在
     ├── 不存在 → 解压 shared-python-base-arm32.tar.gz 到 /opt/
     └── 已存在 → 询问是否覆盖
  2. 遍历 *-arm32.tar.gz
     ├── 为每个应用创建 /opt/<app_name>/
     ├── 解压到对应目录（--strip-components=1）
     ├── chmod +x run.sh
     └── 创建符号链接 /usr/local/bin/<app_name> → run.sh
  3. 验证
     ├── /opt/shared-python/bin/python3 --version
     └── 逐个运行 <app_name> --version
```

### 5.2 离线部署

工控机通常无法联网，部署包需要自包含：

```bash
# 在有网机器上准备
git clone <repo> && cd <repo>
# 触发 GitHub Actions 构建
# 下载 artifacts
# 通过 U 盘 / SCP / 内网传输
scp -r dist/ operator@target:/tmp/deploy/
# 在工控机上离线安装
sudo bash /tmp/deploy/install.sh
```

### 5.3 批量部署

多台工控机场景：

```bash
#!/bin/bash
# batch_deploy.sh
TARGETS=("192.168.1.100" "192.168.1.101" "192.168.1.102")
USER="operator"
DEPLOY_DIR="/tmp/deploy"
for TARGET in "${TARGETS[@]}"; do
  echo "=== 部署到 $TARGET ==="
  scp -r "$DEPLOY_DIR" "${USER}@${TARGET}:/tmp/deploy/"
  ssh "${USER}@${TARGET}" "cd /tmp/deploy && sudo bash install.sh"
  echo "✅ $TARGET 部署完成"
done
```

### 5.4 验证部署

```bash
# 检查共享 Python
/opt/shared-python/bin/python3 --version
/opt/shared-python/bin/python3 -c "import ssl, sqlite3, json; print('OK')"
# 检查各应用
app1 --version
app2 --version
app3 --version
# 检查路径
which app1          # → /usr/local/bin/app1
readlink -f $(which app1)  # → /opt/app1/run.sh
```

***

## 6. 升级与回滚

### 6.1 升级分类

| 升级类型        | 影响范围 |  频率 |  风险 |
| ----------- | :--: | :-: | :-: |
| 只升级某个应用     | 单个应用 |  高  |  低  |
| 升级共享 Python | 所有应用 |  低  |  中  |
| 整体版本升级      |  全部  |  中  |  中  |

### 6.2 只升级某个应用

```bash
# 构建端：只重新打包变更的应用
# （GitHub Actions 可根据 git diff 自动判断）
# 目标机器：
sudo rm -rf /opt/app1
sudo tar xzf app1-arm32.tar.gz -C /opt/app1 --strip-components=1
sudo chmod +x /opt/app1/run.sh
sudo ln -sf /opt/app1/run.sh /usr/local/bin/app1
# 验证
app1 --version
```

**其他应用完全不受影响，无需重启。**

### 6.3 升级共享 Python

```bash
# 备份旧版
sudo cp -a /opt/shared-python /opt/shared-python.bak
# 替换
sudo rm -rf /opt/shared-python
sudo tar xzf shared-python-base-arm32.tar.gz -C /opt/
# 验证所有应用
app1 --version && app2 --version && app3 --version
```

> ⚠️ Python 大版本升级（3.10→3.11）可能导致 C 扩展不兼容，需重新构建所有应用。

### 6.4 整体版本升级

```bash
sudo systemctl stop app1 app2 app3 2>/dev/null || true
sudo rm -rf /opt/shared-python /opt/app1 /opt/app2 /opt/app3
sudo bash install.sh
```

### 6.5 回滚

```bash
# 单应用回滚
sudo rm -rf /opt/app1
sudo tar xzf app1-arm32-v1.0.0.tar.gz -C /opt/app1 --strip-components=1
# 共享 Python 回滚
sudo rm -rf /opt/shared-python
sudo mv /opt/shared-python.bak /opt/shared-python
# 或用备份的 tar
sudo tar xzf shared-python-base-arm32-v1.tar.gz -C /opt/
```

### 6.6 版本管理建议

```
/opt/
├── shared-python/           ← 当前版本
├── shared-python.bak/       ← 上一版本备份
├── app1/                    ← 当前版本
├── app1.bak/                ← 上一版本备份（可选）
...
```

或在 install.sh 中自动维护版本记录：

```bash
# /opt/versions 记录各组件版本
echo "shared-python:$(cat /opt/shared-python/VERSION)" >> /opt/versions
echo "app1:$(cat /opt/app1/VERSION)" >> /opt/versions
```

***

## 7. 依赖管理

### 7.1 依赖层次

```
┌─────────────────────────────────────────┐
│  Layer 0: 系统库 (glibc, libffi, etc.)  │ ← OS 提供
├─────────────────────────────────────────┤
│  Layer 1: 共享 Python Runtime           │ ← /opt/shared-python
│  ├── Python 解释器                       │
│  ├── 标准库                              │
│  └── site-packages (空！)               │
├─────────────────────────────────────────┤
│  Layer 2: 各应用 pip 依赖               │ ← /opt/appX/usr/app_packages/
│  ├── app1: requests, pyserial           │ ← 完全独立
│  ├── app2: numpy, opencv-python         │ ← 完全独立
│  └── app3: (无)                         │
├─────────────────────────────────────────┤
│  Layer 3: 各应用代码                    │ ← /opt/appX/usr/app/
│  ├── app1/                              │
│  ├── app2/                              │
│  └── app3/                              │
└─────────────────────────────────────────┘
```

### 7.2 依赖隔离保证

| 隔离项                       | 机制                     | 说明                                       |
| ------------------------- | ---------------------- | ---------------------------------------- |
| 应用间 pip 依赖                | PYTHONPATH 各自独立        | app1 的 requests 和 app2 的 requests 版本可以不同 |
| 应用代码                      | PYTHONPATH 优先级         | 各自 `usr/app/` 在最前面                       |
| C 扩展 .so                  | LD\_LIBRARY\_PATH 各自独立 | numpy 等的 .so 不会互相覆盖                      |
| 共享 Python 的 site-packages | 保持为空 + 删除 pip          | 防止有人往共享 Python 装包                        |

### 7.3 同一依赖不同版本的处理

```
场景: app1 需要 numpy==1.24, app2 需要 numpy==1.26
/opt/app1/usr/app_packages/numpy/  → 1.24（app1 专用）
/opt/app2/usr/app_packages/numpy/  → 1.26（app2 专用）
运行时:
  app1 → PYTHONPATH 含 /opt/app1/usr/app_packages → 只找到 numpy 1.24
  app2 → PYTHONPATH 含 /opt/app2/usr/app_packages → 只找到 numpy 1.26
✅ 完全不冲突
```

### 7.4 共享 Python 的 site-packages 防护

```bash
# 在 install.sh 中
# 1. 删除共享 Python 中的 pip，防止误装包
rm -f /opt/shared-python/bin/pip*
rm -f /opt/shared-python/bin/pip3*
# 2. 设置 site-packages 为只读
chmod -R a-w /opt/shared-python/lib/python3.10/site-packages/
# 3. 验证 site-packages 为空
CONTENTS=$(find /opt/shared-python/lib/python3.10/site-packages -mindepth 1 2>/dev/null | wc -l)
if [ "$CONTENTS" -gt 0 ]; then
  echo "⚠️ 共享 Python site-packages 不为空，可能导致冲突"
fi
```

***

## 8. 启动机制

### 8.1 启动链路

```
用户输入: app1 arg1 arg2
  /usr/local/bin/app1              ← 符号链接
       │
       ▼
  /opt/app1/run.sh arg1 arg2       ← 启动脚本
       │
       │  设置 PYTHONPATH + LD_LIBRARY_PATH
       │
       ▼
  /opt/shared-python/bin/python3 -s -m app1 arg1 arg2
       │
       ▼
  Python 解释器启动
    → 加载标准库（从 /opt/shared-python/lib/python3.10/）
    → 沿 PYTHONPATH 搜索 app1 包和依赖
    → 执行 app1/__main__.py
```

### 8.2 启动脚本模板

**标准控制台应用：**

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/shared-python/bin/python3"
if [ ! -x "$PYTHON" ]; then
  echo "错误: 未找到共享 Python (/opt/shared-python/bin/python3)" >&2
  echo "请先安装 shared-python-base" >&2
  exit 1
fi
export PYTHONPATH="${SCRIPT_DIR}/usr/app:${SCRIPT_DIR}/usr/app_packages"
export LD_LIBRARY_PATH="/opt/shared-python/lib:${SCRIPT_DIR}/usr/lib:${LD_LIBRARY_PATH}"
exec "$PYTHON" -s -m myapp "$@"
```

**后台服务应用（配合 systemd）：**

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/shared-python/bin/python3"
export PYTHONPATH="${SCRIPT_DIR}/usr/app:${SCRIPT_DIR}/usr/app_packages"
export LD_LIBRARY_PATH="/opt/shared-python/lib:${SCRIPT_DIR}/usr/lib:${LD_LIBRARY_PATH}"
exec "$PYTHON" -s -m myapp "$@" >> /var/log/myapp.log 2>&1
```

systemd unit：

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application Service
After=network.target
[Service]
Type=simple
ExecStart=/opt/myapp/run.sh
Restart=on-failure
RestartSec=5
User=myapp
Group=myapp
WorkingDirectory=/opt/myapp
[Install]
WantedBy=multi-user.target
```

### 8.3 启动速度

| 场景                   |    典型耗时    |
| -------------------- | :--------: |
| Hello World（冷启动）     |  30-80 ms  |
| 中等应用（import 10+ 模块）  | 100-200 ms |
| 重型应用（import numpy 等） | 200-500 ms |
| 热启动（磁盘缓存后）           | 上述的 50-70% |

> 启动速度瓶颈在 Python 解释器本身 + import，不在脚本或共享 AppDir 方案。
> 相比 AppImage 方案，省掉了 FUSE 挂载开销，通常更快。

### 8.4 启动脚本中各参数说明

| 参数/设置                                     | 作用                                    |
| ----------------------------------------- | ------------------------------------- |
| `SCRIPT_DIR=...`                          | 获取脚本绝对路径，用于拼接相对目录                     |
| `PYTHON="/opt/shared-python/bin/python3"` | 指向共享 Python                           |
| `PYTHONPATH=...`                          | Python 模块搜索路径，先应用代码，再 pip 依赖          |
| `LD_LIBRARY_PATH=...`                     | C 动态库搜索路径，含共享 Python 的 .so 和应用自身的 .so |
| `-s`                                      | 不添加用户 site-packages，防止污染              |
| `-m`                                      | 以模块方式运行，找 `<module>/__main__.py`      |
| `exec`                                    | 替换当前 bash 进程，不额外占用资源                  |
| `"$@"`                                    | 透传所有命令行参数                             |

***

## 9. 方案对比

### 9.1 与 AppImage 对比

| 维度             | AppImage          | 共享 AppDir                       |
| -------------- | ----------------- | ------------------------------- |
| **形态**         | 单个 `.AppImage` 文件 | 多个目录 + tar.gz                   |
| **Python 解释器** | 每个 AppImage 自带一份  | 所有应用共用一份                        |
| **标准库**        | 每个 AppImage 自带一份  | 所有应用共用一份                        |
| **FUSE 依赖**    | 需要                | 不需要                             |
| **单应用体积**      | \~50 MB           | 共享 Python \~30 MB + 应用 \~3-5 MB |
| **3 应用总占用**    | \~150 MB          | \~40 MB                         |
| **多应用磁盘效率**    | 低（重复）             | 高（共享）                           |
| **部署复杂度**      | 低（下载即用）           | 中（需安装脚本）                        |
| **升级粒度**       | 替换整个文件            | 可只替换单个应用目录                      |
| **启动速度**       | 略慢（FUSE 挂载）       | 更快（直接执行）                        |
| **依赖隔离**       | 完全隔离              | 应用间隔离，共享 Python 统一              |
| **适合场景**       | 桌面分发、单应用          | 嵌入式/工控、多应用                      |

### 9.2 与 deb/rpm 对比

| 维度            | deb/rpm          | 共享 AppDir                   |
| ------------- | ---------------- | --------------------------- |
| **Python 来源** | 系统包管理器提供的 Python | 自带的 python-build-standalone |
| **Python 版本** | 受 OS 发行版限制       | 自由选择                        |
| **依赖声明**      | deb 控制文件         | requirements.txt            |
| **安装**        | `dpkg -i`        | 解压 tar.gz                   |
| **卸载**        | `dpkg -r`        | `rm -rf /opt/appX`          |
| **多版本共存**     | 困难               | 天然支持                        |
| **离线部署**      | 需解决依赖链           | 自包含，无外部依赖                   |
| **跨发行版**      | 需分别打包            | 与发行版无关                      |

### 9.3 与 venv 对比

| 维度             | venv         | 共享 AppDir    |
| -------------- | ------------ | ------------ |
| **Python 解释器** | 链接到系统 Python | 自带独立 Python  |
| **标准库**        | 共享系统 Python  | 自带精简标准库      |
| **隔离性**        | 虚拟隔离         | 物理隔离         |
| **可移植性**       | 依赖系统 Python  | 不依赖系统 Python |
| **适合场景**       | 开发环境         | 生产部署         |

### 9.4 与 Docker 对比

| 维度       | Docker             | 共享 AppDir          |
| -------- | ------------------ | ------------------ |
| **开销**   | 需 Docker 运行时 + 镜像层 | 无额外运行时             |
| **资源占用** | 每容器 10-50 MB RAM   | 仅 Python 进程        |
| **磁盘占用** | 基础镜像 100+ MB       | \~40 MB            |
| **启动速度** | 100-500 ms         | 30-200 ms          |
| **适用性**  | 服务器                | 嵌入式/工控（可能无 Docker） |

***

## 10. ARM32 工控机可行性评估

### 10.1 硬件兼容性

| 检查项              |  评估 | 说明                                    |
| ---------------- | :-: | ------------------------------------- |
| ARM32 (armv7) 支持 |  ✅  | python-build-standalone 提供 armv7 构建产物 |
| eMMC/SD 卡存储      |  ✅  | 3 应用仅 \~40 MB，eMMC 4 GB 即够            |
| 内存 512 MB+       |  ✅  | Python 进程本身占用 20-50 MB                |
| 内存 256 MB        |  ⚠️ | 勉强可用，避免 import 重型库                    |
| 无 FUSE           |  ✅  | 共享 AppDir 不依赖 FUSE                    |
| 无 Docker         |  ✅  | 不需要 Docker                            |
| 无 snap/flatpak   |  ✅  | 不需要任何容器运行时                            |

### 10.2 系统依赖

共享 AppDir 方案对目标系统的**唯一要求**：

```
必需:
  ✅ Linux 内核（任何 ARM32 发行版）
  ✅ glibc（python-build-standalone 链接的版本）
不需要:
  ❌ FUSE
  ❌ Docker
  ❌ snapd / flatpak
  ❌ 系统安装的 Python
  ❌ 任何开发工具
```

glibc 兼容性检查：

```bash
# 在工控机上检查 glibc 版本
ldd --version
# python-build-standalone ARM32 通常链接 glibc 2.28+
# Debian 10+ / Ubuntu 18.04+ 的 glibc 满足要求
```

### 10.3 性能评估

| 指标          |      估计值      | 说明              |
| ----------- | :-----------: | --------------- |
| 冷启动时间（小应用）  |   50-150 ms   | Python + import |
| 冷启动时间（中型应用） |   100-300 ms  | 含 10+ 标准库模块     |
| 冷启动时间（重型应用） |   200-500 ms  | 含 numpy 等大包     |
| 热启动时间       |   上述 50-70%   | 磁盘缓存生效          |
| 运行时内存       |    20-80 MB   | 取决于应用           |
| 磁盘 I/O（启动时） |   5-20 MB 读   | 加载 .py/.pyc/.so |
| CPU 占用      | 与普通 Python 相同 | 无额外开销           |

### 10.4 可靠性评估

| 风险点          |  等级 | 缓解措施                      |
| ------------ | :-: | ------------------------- |
| 共享 Python 损坏 |  中  | 自动备份 + tar 回滚             |
| 单应用损坏        |  低  | 独立目录，只影响自己                |
| 磁盘写满         |  低  | 体积小（\~40 MB），eMMC 4 GB 足够 |
| 断电导致文件损坏     |  中  | tar.gz 是只读的，可重新解压         |
| glibc 不兼容    |  低  | 构建时选择对应版本                 |
| 进程崩溃         |  低  | 用 systemd 自动重启            |

### 10.5 运维便利性

| 操作      | 命令                                                                                          |
| ------- | ------------------------------------------------------------------------------------------- |
| 查看已安装应用 | `ls /opt/app*/`                                                                             |
| 查看应用版本  | `app1 --version`                                                                            |
| 升级某个应用  | `sudo rm -rf /opt/app1 && sudo tar xzf app1-arm32.tar.gz -C /opt/app1 --strip-components=1` |
| 回滚应用    | 用旧 tar.gz 重新解压                                                                              |
| 查看日志    | `journalctl -u app1`（配合 systemd）                                                            |
| 重启服务    | `sudo systemctl restart app1`                                                               |
| 卸载应用    | `sudo rm -rf /opt/app1 /usr/local/bin/app1`                                                 |
| 完全卸载    | `sudo rm -rf /opt/shared-python /opt/app* /usr/local/bin/app*`                              |

***

## 11. 风险与缓解

### 11.1 已识别风险

| #  | 风险                                    | 影响 |  概率 | 缓解措施                                        |
| -- | ------------------------------------- | -- | :-: | ------------------------------------------- |
| R1 | Python 大版本升级导致 C 扩展不兼容                | 高  |  低  | 大版本升级时重建所有应用                                |
| R2 | 有人往共享 Python 装包导致冲突                   | 中  |  中  | 删除 pip + site-packages 只读                   |
| R3 | python-build-standalone 停止提供 ARM32 构建 | 高  |  低  | 可用系统 Python 替代                              |
| R4 | 共享 Python 损坏影响所有应用                    | 高  |  低  | 升级前自动备份                                     |
| R5 | glibc 版本不兼容                           | 高  |  极低 | 选择与目标系统匹配的 PBS 版本                           |
| R6 | 断电导致解压不完整                             | 中  |  低  | 升级脚本中先备份再替换                                 |
| R7 | 磁盘空间不足                                | 低  |  极低 | 3 应用仅 \~40 MB                               |
| R8 | 模块名自动检测不准                             | 低  |  低  | 支持在 requirements.txt 旁放 MODULE\_NAME 文件显式指定 |

### 11.2 回退方案

如果共享 AppDir 方案不满足需求，可回退到：

1. **独立 AppImage**：每个应用自包含，最简单
2. **deb 包**：用系统包管理器，最规范
3. **Docker**：最隔离，但资源开销大

***

## 12. 常见问题

### Q1: 共享 AppDir 有官方标准吗？

没有。这是对 AppImage AppDir 结构的非标准用法。AppImage 官方推崇"one app = one file"。但在 HPC/集群环境中，"共享 Python + 各项目独立依赖"的模式非常成熟。Flatpak/Snap 的共享 runtime 也是同样的思路。

### Q2: 应用间依赖会冲突吗？

不会。每个应用的 `app_packages/` 完全独立，通过各自的 `PYTHONPATH` 隔离。同一个包（如 numpy）在不同应用中可以是不同版本。

### Q3: 启动速度怎么样？

瓶颈在 Python 解释器本身，不在脚本或共享 AppDir。典型冷启动 50-300ms，热启动 30-200ms。比 AppImage 略快（省掉 FUSE 挂载）。

### Q4: 能否在不装共享 Python 的机器上运行？

不能。共享 Python 是前提条件。但部署很简单，解压一个 tar.gz 即可。

### Q5: 如果工控机已有系统 Python 怎么办？

互不影响。共享 Python 安装在 `/opt/shared-python/`，不修改系统 Python。两者可以共存。

### Q6: 能否同时跑 Python 3.10 和 3.11 的应用？

默认不支持，因为只有一个共享 Python。变通方法：

```
/opt/shared-python-3.10/     ← Python 3.10 runtime
/opt/shared-python-3.11/     ← Python 3.11 runtime
/opt/app1/run.sh → /opt/shared-python-3.10/bin/python3
/opt/app2/run.sh → /opt/shared-python-3.11/bin/python3
```

### Q7: 如何处理应用自己的配置文件？

推荐做法：

```bash
# 配置文件放在应用目录外，避免升级时被覆盖
/opt/app1/
├── run.sh
└── usr/app/
/etc/app1/
├── config.yaml         ← 配置文件放这里
└── logging.conf
```

run.sh 中：

```bash
export APP1_CONFIG_DIR="${APP1_CONFIG_DIR:-/etc/app1}"
```

### Q8: 如何处理应用运行时数据？

```bash
/var/lib/app1/          ← 运行时数据
/var/log/app1/          ← 日志
/tmp/app1/              ← 临时文件
```

### Q9: 如何做健康检查？

```bash
# 简单版
app1 --health-check
# systemd 版
[Service]
ExecStart=/opt/app1/run.sh
ExecStartPost=/opt/app1/run.sh --health-check
Restart=on-failure
```

### Q10: 如何减少 pip 依赖体积？

```bash
# 1. 只安装运行时必需的依赖
#    requirements.txt 中不要放开发依赖
# 2. 删除 .dist-info 和 .egg-info（运行时不需要）
find /opt/app1/usr/app_packages -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find /opt/app1/usr/app_packages -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
# 3. 删除测试和文档
find /opt/app1/usr/app_packages -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find /opt/app1/usr/app_packages -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true
# 4. strip .so 文件
find /opt/app1/usr/app_packages -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true
```

***

## 附录 A：完整 Workflow 文件

```yaml
# .github/workflows/build-arm32-shared-appdir.yml
name: Build ARM32 Shared AppDir
on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      python_version:
        description: 'Python version (3.10 / 3.11 / 3.12)'
        required: false
        default: '3.11'
      strip_stdlib:
        description: 'Strip unused stdlib modules (saves ~3 MB for stripped builds)'
        required: false
        type: boolean
        default: true
env:
  PYTHON_VERSION: ${{ github.event.inputs.python_version || '3.11' }}
  PBS_RELEASE: '20260508'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      # ================================================================
      #  Phase 1: 环境准备
      # ================================================================
      - name: Checkout
        uses: actions/checkout@v4
      # ================================================================
      #  Phase 2: 构建共享 Python 基础包
      # ================================================================
      - name: Build shared Python base
        uses: uraimo/run-on-arch-action@v3
        with:
          arch: armv7
          distro: debian_bookworm
          githubToken: ${{ github.token }}
          install: |
            apt-get update -qq
            apt-get install -y -qq \
              build-essential libffi-dev libssl-dev \
              libbz2-dev libreadline-dev libsqlite3-dev zlib1g-dev \
              wget git file ca-certificates
            echo "✅ 系统依赖安装完成"
            mkdir -p /etc/pip
            cat > /etc/pip/pip.conf <<EOF
            [global]
            extra-index-url=https://www.piwheels.org/simple
            timeout=120
            retries=5
            EOF
          run: |
            set -e
            PYTHON_VERSION="${{ env.PYTHON_VERSION }}"
            PBS_RELEASE="${{ env.PBS_RELEASE }}"
            case "$PYTHON_VERSION" in
              3.10) PBS_PYTHON="3.10.20" ;;
              3.11) PBS_PYTHON="3.11.15" ;;
              3.12) PBS_PYTHON="3.12.13" ;;
              *)    PBS_PYTHON="$PYTHON_VERSION" ;;
            esac
            PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PBS_PYTHON}+${PBS_RELEASE}-armv7-unknown-linux-gnueabihf-install_only_stripped.tar.gz"
            echo "=== 下载 python-build-standalone ==="
            wget -q "$PBS_URL" -O /tmp/pbs.tar.gz || {
              echo "❌ 下载失败，请检查版本号"
              echo "   访问 https://github.com/astral-sh/python-build-standalone/releases 确认"
              exit 1
            }
            tar xzf /tmp/pbs.tar.gz -C /tmp/
            PBS_DIR="/tmp/python"
            [ ! -d "$PBS_DIR" ] && PBS_DIR=$(find /tmp -maxdepth 1 -type d -name "cpython*" | head -1)
            mkdir -p shared-python
            cp -a "$PBS_DIR/." shared-python/
            PYLIB=$(ls -d shared-python/lib/python3.* 2>/dev/null | head -1)
            if [ "${{ github.event.inputs.strip_stdlib }}" != "false" ]; then
              echo "=== 精简标准库 ==="
              echo "注意: install_only_stripped 版本已移除 test/__pycache__，此处仅删除 GUI/开发工具"
              for mod in tkinter idlelib lib2to3 unittest pydoc_data curses tty webbrowser; do
                rm -rf "$PYLIB/$mod" 2>/dev/null || true
              done
              find "$PYLIB" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
              find "$PYLIB" -type d -name test -exec rm -rf {} + 2>/dev/null || true
              find "$PYLIB" -type d -name tests -exec rm -rf {} + 2>/dev/null || true
              rm -rf shared-python/include
              echo "✅ 标准库已精简 (节省约 3 MB)"
            fi
            echo "${PBS_PYTHON}" > shared-python/VERSION
            shared-python/bin/python3 --version
            shared-python/bin/python3 -c "import json, ssl, sqlite3; print(\"✅ 核心模块正常\")"
            tar czf shared-python-base-arm32.tar.gz shared-python/
            echo "✅ 共享 Python: $(ls -lh shared-python-base-arm32.tar.gz | awk '{print $5}')"
      # ================================================================
      #  Phase 3: 构建各应用
      # ================================================================
      - name: Build apps
        uses: uraimo/run-on-arch-action@v3
        with:
          arch: armv7
          distro: debian_bookworm
          githubToken: ${{ github.token }}
          install: |
            apt-get update -qq
            apt-get install -y -qq tar gzip
          run: |
            set -e
            if [ ! -d "shared-python" ]; then
              echo "解压 shared-python-base-arm32.tar.gz..."
              tar xzf shared-python-base-arm32.tar.gz
            fi
            PYTHON="$(pwd)/shared-python/bin/python3"
            if [ -x "$(pwd)/shared-python/bin/pip3" ]; then
              PIP="$(pwd)/shared-python/bin/pip3"
            else
              PIP="$PYTHON -m pip"
            fi
            mkdir -p dist
            if [ ! -d "apps" ] || [ -z "$(ls -A apps 2>/dev/null)" ]; then
              echo "⚠️ apps 目录不存在或为空，跳过应用构建"
              exit 0
            fi
            for APP_DIR in apps/*/; do
              [ -d "$APP_DIR" ] || continue
              APP_NAME=$(basename "$APP_DIR")
              echo "=========================================="
              echo "  构建: $APP_NAME"
              echo "=========================================="
              BUILD_DIR="build/${APP_NAME}"
              rm -rf "$BUILD_DIR"
              mkdir -p "$BUILD_DIR/usr/app"
              mkdir -p "$BUILD_DIR/usr/app_packages"
              if [ -d "$APP_DIR/src" ]; then
                cp -a "$APP_DIR/src/." "$BUILD_DIR/usr/app/"
              elif [ -f "$APP_DIR/__main__.py" ]; then
                cp -a "$APP_DIR"/*.py "$BUILD_DIR/usr/app/" 2>/dev/null || true
              elif [ -f "$APP_DIR/__init__.py" ]; then
                mkdir -p "$BUILD_DIR/usr/app/$APP_NAME"
                cp -a "$APP_DIR"/*.py "$BUILD_DIR/usr/app/$APP_NAME/" 2>/dev/null || true
              else
                cp -a "$APP_DIR"/*.py "$BUILD_DIR/usr/app/" 2>/dev/null || true
              fi
              if [ -f "$APP_DIR/requirements.txt" ]; then
                echo "--- 安装依赖 ---"
                $PIP install \
                  --target "$BUILD_DIR/usr/app_packages" \
                  -r "$APP_DIR/requirements.txt" 2>&1 | tail -5
              fi
              if [ -f "$BUILD_DIR/usr/app/__main__.py" ]; then
                MODULE_NAME=$(basename "$(find "$BUILD_DIR/usr/app" -name "__main__.py" -type f | head -1 | xargs dirname)")
              elif [ -f "$BUILD_DIR/usr/app/$APP_NAME/__main__.py" ]; then
                MODULE_NAME="$APP_NAME"
              elif [ -f "$BUILD_DIR/usr/app/$APP_NAME/__init__.py" ]; then
                MODULE_NAME="$APP_NAME"
              else
                MODULE_NAME="$APP_NAME"
              fi
              echo "模块名: $MODULE_NAME"
              echo "$MODULE_NAME" > "$BUILD_DIR/MODULE_NAME"
              cat > "$BUILD_DIR/run.sh" <<RUNEOF
            #!/bin/bash
            SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
            PYTHON="/opt/shared-python/bin/python3"
            if [ ! -x "\$PYTHON" ]; then
              echo "错误: 未找到共享 Python (/opt/shared-python/bin/python3)" >&2
              echo "请先安装 shared-python-base" >&2
              exit 1
            fi
            export PYTHONPATH="\${SCRIPT_DIR}/usr/app:\${SCRIPT_DIR}/usr/app_packages"
            export LD_LIBRARY_PATH="/opt/shared-python/lib:\${LD_LIBRARY_PATH}"
            exec "\$PYTHON" -s -m ${MODULE_NAME} "\$@"
            RUNEOF
              chmod +x "$BUILD_DIR/run.sh"
              echo "--- 验证 ---"
              export PYTHONPATH="$(pwd)/$BUILD_DIR/usr/app:$(pwd)/$BUILD_DIR/usr/app_packages"
              export LD_LIBRARY_PATH="$(pwd)/shared-python/lib"
              if $PYTHON -s -c "import ${MODULE_NAME}; print('✅ import ${MODULE_NAME} 成功')" 2>&1; then
                echo "验证通过"
              else
                echo "⚠️ import 验证失败，请检查代码和依赖"
                echo "继续构建，但应用可能无法正常运行"
              fi
              echo "--- 清理 ---"
              find "$BUILD_DIR/usr/app_packages" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
              find "$BUILD_DIR/usr/app_packages" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
              find "$BUILD_DIR/usr/app_packages" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
              find "$BUILD_DIR/usr/app_packages" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
              find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
              find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
              find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
              tar czf "dist/${APP_NAME}-arm32.tar.gz" \
                -C build "$APP_NAME"
              SIZE=$(ls -lh "dist/${APP_NAME}-arm32.tar.gz" | awk '{print $5}')
              echo "✅ $APP_NAME 打包完成: $SIZE"
            done
      # ================================================================
      #  Phase 4: 组装部署包
      # ================================================================
      - name: Create deployment script
        run: |
          cat > dist/install.sh <<'INSTALL_EOF'
          #!/bin/bash
          # ================================================
          # ARM32 共享 Python 应用部署/升级脚本
          # ================================================
          set -e
          INSTALL_DIR="/opt"
          SHARED_PYTHON_DIR="${INSTALL_DIR}/shared-python"
          SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
          FORCE_MODE=false
          UPGRADE_MODE=
          UPGRADE_APP=
          show_help() {
            echo "Usage:"
            echo "  $0                           # 首次安装"
            echo "  $0 --force                   # 强制安装（跳过确认）"
            echo "  $0 --upgrade app1            # 只升级 app1"
            echo "  $0 --upgrade-shared-python   # 只升级共享 Python"
            echo "  $0 --upgrade-all             # 全量升级"
            echo "  $0 --list                    # 列出可安装的应用"
            echo "  $0 --clean-backup            # 清理所有备份"
            exit 0
          }
          check_root() {
            if [ "$(id -u)" -ne 0 ]; then
              echo "❌ 错误: 需要 root 权限"
              echo "   请使用: sudo $0 $@"
              exit 1
            fi
          }
          check_files() {
            if [ ! -f "shared-python-base-arm32.tar.gz" ]; then
              echo "❌ 错误: 未找到 shared-python-base-arm32.tar.gz"
              exit 1
            fi
            if [ -z "$(ls *-arm32.tar.gz 2>/dev/null | grep -v shared-python)" ]; then
              echo "⚠️ 警告: 未找到任何应用包"
            fi
          }
          list_apps() {
            echo "可安装的应用:"
            echo "  - shared-python (基础环境)"
            for app_tar in *-arm32.tar.gz; do
              [ "$app_tar" = "shared-python-base-arm32.tar.gz" ] && continue
              [ ! -f "$app_tar" ] && continue
              APP_NAME=$(echo "$app_tar" | sed "s/-arm32.tar.gz//")
              SIZE=$(du -sh "$app_tar" 2>/dev/null | cut -f1)
              echo "  - $APP_NAME ($SIZE)"
            done
            exit 0
          }
          clean_backup() {
            echo "清理备份文件..."
            find "$INSTALL_DIR" -name "*.bak" -type d -exec rm -rf {} + 2>/dev/null || true
            echo "✅ 备份清理完成"
            exit 0
          }
          backup_app() {
            local APP_DIR="$1"
            if [ -d "$APP_DIR" ]; then
              local BACKUP_DIR="${APP_DIR}.bak.$(date +%Y%m%d_%H%M%S)"
              echo "备份: $APP_DIR -> $BACKUP_DIR"
              cp -a "$APP_DIR" "$BACKUP_DIR"
              find "$INSTALL_DIR" -name "*.bak.*" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
            fi
          }
          install_shared_python() {
            echo "--- 安装共享 Python ---"
            if [ -d "$SHARED_PYTHON_DIR" ]; then
              if [ "$FORCE_MODE" = true ]; then
                backup_app "$SHARED_PYTHON_DIR"
                rm -rf "$SHARED_PYTHON_DIR"
              else
                echo "⚠️ 共享 Python 已存在: $SHARED_PYTHON_DIR"
                $SHARED_PYTHON_DIR/bin/python3 --version 2>/dev/null || true
                if [ -t 0 ]; then
                  read -p "是否覆盖? (y/N): " overwrite
                  if [ "$overwrite" = "y" ] || [ "$overwrite" = "Y" ]; then
                    backup_app "$SHARED_PYTHON_DIR"
                    rm -rf "$SHARED_PYTHON_DIR"
                  else
                    echo "跳过共享 Python 安装"
                    return 0
                  fi
                else
                  echo "❌ 共享 Python 已存在，使用 --force 强制覆盖"
                  exit 1
                fi
              fi
            fi
            tar xzf shared-python-base-arm32.tar.gz -C "$INSTALL_DIR/"
            rm -f "$SHARED_PYTHON_DIR/bin/pip"* 2>/dev/null || true
            $SHARED_PYTHON_DIR/bin/python3 --version
            echo "✅ 共享 Python 已安装"
          }
          install_app() {
            local APP_TAR="$1"
            local APP_NAME=$(echo "$APP_TAR" | sed "s/-arm32.tar.gz//")
            local APP_DIR="${INSTALL_DIR}/${APP_NAME}"
            echo "--- 安装应用: $APP_NAME ---"
            if [ -d "$APP_DIR" ]; then
              if [ "$FORCE_MODE" = true ]; then
                backup_app "$APP_DIR"
                rm -rf "$APP_DIR"
              else
                echo "⚠️ 应用已存在: $APP_DIR"
                if [ -t 0 ]; then
                  read -p "是否覆盖? (y/N): " overwrite
                  if [ "$overwrite" = "y" ] || [ "$overwrite" = "Y" ]; then
                    backup_app "$APP_DIR"
                    rm -rf "$APP_DIR"
                  else
                    echo "跳过 $APP_NAME 安装"
                    return 0
                  fi
                else
                  backup_app "$APP_DIR"
                  rm -rf "$APP_DIR"
                fi
              fi
            fi
            mkdir -p "$APP_DIR"
            tar xzf "$APP_TAR" -C "$APP_DIR/" --strip-components=1
            chmod +x "$APP_DIR/run.sh" 2>/dev/null || true
            rm -f "/usr/local/bin/$APP_NAME" 2>/dev/null || true
            ln -sf "$APP_DIR/run.sh" "/usr/local/bin/$APP_NAME"
            echo "✅ $APP_NAME 已安装 → 运行: $APP_NAME"
          }
          while [[ $# -gt 0 ]]; do
            case "$1" in
              --force)
                FORCE_MODE=true
                shift
                ;;
              --upgrade)
                UPGRADE_MODE=app
                if [ -z "$2" ] || [[ "$2" == -* ]]; then
                  echo "❌ 错误: --upgrade 需要指定应用名"
                  exit 1
                fi
                UPGRADE_APP="$2"
                shift 2
                ;;
              --upgrade-shared-python)
                UPGRADE_MODE=shared-python
                shift
                ;;
              --upgrade-all)
                UPGRADE_MODE=all
                shift
                ;;
              --list)
                list_apps
                ;;
              --clean-backup)
                clean_backup
                ;;
              --help|-h)
                show_help
                ;;
              *)
                echo "❌ 未知参数: $1"
                show_help
                ;;
            esac
          done
          check_root "$@"
          cd "$SCRIPT_DIR"
          check_files
          if [ -z "$UPGRADE_MODE" ]; then
            echo "========================================"
            echo "  ARM32 共享 Python 应用 - 首次安装"
            echo "========================================"
            install_shared_python
            for app_tar in *-arm32.tar.gz; do
              [ "$app_tar" = "shared-python-base-arm32.tar.gz" ] && continue
              [ ! -f "$app_tar" ] && continue
              install_app "$app_tar"
            done
            echo ""
            echo "========================================"
            echo "  首次安装完成！"
            echo "========================================"
            echo "已安装应用:"
            for app in /usr/local/bin/*; do
              [ -L "$app" ] && echo "  - $(basename $app)"
            done
            exit 0
          fi
          case "$UPGRADE_MODE" in
            app)
              APP_TAR="${UPGRADE_APP}-arm32.tar.gz"
              if [ ! -f "$APP_TAR" ]; then
                echo "❌ 未找到 $APP_TAR"
                echo "可用的应用:"
                ls *-arm32.tar.gz 2>/dev/null | sed 's/-arm32.tar.gz//' | sed 's/^/  - /'
                exit 1
              fi
              install_app "$APP_TAR"
              ;;
            shared-python)
              install_shared_python
              ;;
            all)
              echo "========================================"
              echo "  全量升级"
              echo "========================================"
              install_shared_python
              for app_tar in *-arm32.tar.gz; do
                [ "$app_tar" = "shared-python-base-arm32.tar.gz" ] && continue
                [ ! -f "$app_tar" ] && continue
                install_app "$app_tar"
              done
              echo ""
              echo "========================================"
              echo "  全量升级完成！"
              echo "========================================"
              ;;
          esac
          INSTALL_EOF
          chmod +x dist/install.sh
      - name: Assemble deployment package
        run: |
          cp shared-python-base-arm32.tar.gz dist/
          echo "=== 部署包内容 ==="
          for f in dist/*; do
            echo "  $(basename $f): $(du -sh $f | cut -f1)"
          done
      # ================================================================
      #  Phase 5: 上传
      # ================================================================
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: arm32-deployment
          path: dist/
      - name: Build summary
        if: always()
        run: |
          echo "============================================"
          echo "  构建完成摘要"
          echo "============================================"
          echo "Python 版本: ${{ env.PYTHON_VERSION }}"
          echo "目标架构: ARM32 (armv7)"
          echo ""
          echo "产物:"
          for f in dist/* shared-python-base-arm32.tar.gz; do
            [ -f "$f" ] && echo "  $(basename $f): $(du -sh $f | cut -f1)"
          done
          echo ""
          echo "部署: sudo bash install.sh"
          echo "升级: sudo bash install.sh --upgrade app1"
```

***

## 附录 B：项目模板

### B.1 最小应用模板

```
apps/hello/
├── requirements.txt
└── src/
    └── hello/
        ├── __init__.py
        └── __main__.py
```

`__init__.py`：

```python
"""Hello World 应用"""
__version__ = "1.0.0"
```

`__main__.py`：

```python
import sys
def main():
    print("Hello from ARM32!")
    return 0
if __name__ == "__main__":
    sys.exit(main())
```

`requirements.txt`：

```
# 无外部依赖
```

### B.2 带依赖的应用模板

```
apps/data-collector/
├── requirements.txt
└── src/
    └── data_collector/
        ├── __init__.py
        ├── __main__.py
        ├── core.py
        └── config.py
```

`requirements.txt`：

```
pyserial>=3.5
paho-mqtt>=1.6
pyyaml>=6.0
```

### B.3 后台服务应用模板

除标准文件外，额外提供 systemd unit：

```ini
# deploy/data-collector.service
[Unit]
Description=Data Collector Service
After=network.target
[Service]
Type=simple
ExecStart=/opt/data-collector/run.sh
Restart=on-failure
RestartSec=5
User=datacollector
Group=datacollector
WorkingDirectory=/opt/data-collector
[Install]
WantedBy=multi-user.target
```

在 install.sh 中自动安装：

```bash
if [ -f "$APP_DIR/data-collector.service" ]; then
  cp "$APP_DIR/data-collector.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable data-collector
  systemctl start data-collector
fi
```

***

## 评估结论

| 评估维度     |     结论     | 说明                                     |
| -------- | :--------: | -------------------------------------- |
| 技术可行性    |    ✅ 可行    | python-build-standalone 提供 ARM32 构建产物  |
| 硬件兼容性    |    ✅ 可行    | 不依赖 FUSE/Docker，glibc 兼容 Ubuntu 18.04+ |
| 磁盘占用     |    ✅ 优秀    | 3 应用 \~40 MB，比 3 个 AppImage 节省 73%     |
| 启动速度     |    ✅ 良好    | 50-300ms，优于 AppImage                   |
| 依赖隔离     |    ✅ 良好    | 应用间隔离，共享 Python 统一版本                   |
| 升级便利性    |    ✅ 优秀    | 目录级替换，支持单应用/共享 Python/全量升级             |
| 回滚便利性    |    ✅ 优秀    | tar.gz 解压即回滚，自动备份旧版                    |
| 运维复杂度    |     ✅ 低    | 常用操作均为 rm/tar/ln                       |
| 风险等级     |     ✅ 低    | 已识别风险均有缓解措施                            |
| **综合评估** | **✅ 推荐采用** | **适合 ARM32 Ubuntu 工控机多 Python 应用场景**   |

