# Python Android 应用源码保护与打包方案
**—— Nuitka + Briefcase 三阶段架构规范**
---
## 1. 概述
### 1.1 背景
在使用 Python 开发 Android 应用时，通常使用 Briefcase 将项目打包为 APK。然而，Briefcase 默认将 Python 源码（`.py` 文件）以明文形式打包进 APK 中，极易被反编译和窃取，无法满足商业应用的源码保护需求。
### 1.2 目标
通过 Nuitka 将核心 Python 代码编译为 C 语言并进一步编译为二进制动态链接库（`.so` 文件），替换原有的明文 `.py` 文件，最终由 Briefcase 打包为 APK，实现**源码级保护 + 标准化打包**。
### 1.3 核心挑战
- **环境矛盾**：Nuitka 编译 Android 可加载的 `.so` 必须依赖 **Bionic libc**（Android 底层 C 库）；而 Briefcase 打包 APK 依赖 **Android SDK + JDK + Gradle**，这些工具链仅能在标准 Linux（glibc）环境下稳定运行。
- **单一环境无法兼顾**：在标准 Linux 下交叉编译 Bionic `.so` 兼容性差、配置极为复杂；在 Termux 环境下安装完整 Android SDK 打包 APK 几乎不可行。
---
## 2. 架构设计
本方案采用**三阶段流水线**架构，通过 GitHub Actions 的 Artifact 机制解耦传递产物，实现"专境专用"。
```text
                        三阶段流水线架构
  ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
  │    阶段 0: 准备    │       │    阶段 1: 编译    │       │    阶段 2: 打包    │
  │                   │       │                   │       │                   │
  │  运行环境: Ubuntu │       │  运行环境: ARM     │       │  运行环境: Ubuntu  │
  │  核心能力: 配置解析│       │  核心能力: Bionic  │       │  核心能力: SDK     │
  │                   │       │                   │       │                   │
  │  输入: 标签/参数   │       │  输入: .py 源码    │       │  输入: .so 二进制  │
  │  处理: 验证配置    │──────▶│  处理: Nuitka     │──────▶│  处理: Briefcase  │
  │  产出: 构建参数    │       │  修补: patchelf   │ .so   │  产出: .apk       │
  └───────────────────┘       └───────────────────┘       └───────────────────┘
```
### 2.1 架构六大原则
| 原则 | 说明 |
|:---|:---|
| **环境专一** | Termux 专心编译 `.so`，Ubuntu 专心打包 APK，绝不混用 |
| **接口简洁** | 阶段间仅通过 `.so` 文件交互，不传递环境、配置或编译工具 |
| **原生编译** | ARM `.so` 必须在 ARM 机器上配合 Termux 原生编译，杜绝 NDK 交叉编译 |
| **最小替换** | 仅编译需保护的核心包，保留 `__init__.py`、`__main__.py` 和资源文件 |
| **补丁收敛** | 所有 ELF 修补（patchelf/cleaner）在阶段 1 末尾一次性完成，阶段 2 即插即用 |
| **灵活开关** | 通过 `enable_nuitka` 参数控制是否启用源码保护，便于调试 |
---
## 3. 技术原理
### 3.1 为什么必须用 Termux Docker？（Bionic vs glibc）
Android 系统使用 Bionic libc，而非标准 Linux 的 glibc。编译出的 `.so` 内部通过 `DT_NEEDED` 字段记录了依赖的动态库，Android 的 Linker 严格校验这些字段：
```text
✅ Bionic 环境 编译:
  NEEDED: libc.so           (Android 系统自带)
  NEEDED: libm.so           (Android 系统自带)
  NEEDED: libpython3.10.so  (Briefcase 打包提供)
  Linker: /system/bin/linker64
❌ 标准 Linux 环境 编译:
  NEEDED: libc.so.6         (Android 上不存在)
  NEEDED: libm.so.6         (Android 上不存在)
  NEEDED: libpthread.so.0   (Android 上不存在)
  Linker: ld-linux-aarch64.so.1 (Android 上不存在)
```
**结论**：在 glibc 环境下编译的 `.so` 在 Android 上 `dlopen` 加载时会直接报错 `not found`。Termux 提供了完整的 Bionic 用户空间，是唯一可靠的 CI 编译环境。
### 3.2 Python Import 机制与替换原理
将包目录（如 `hello/`）编译为单文件 `hello.so` 后，Python 的导入机制依然有效：
```python
# 代码中写的是：
from hello.core import something
# Python 解释器查找顺序：
# 1. 查找 hello/core.py -> 不存在（源码已被删除）
# 2. 查找 hello.so      -> 存在！
# 3. 从 hello.so 中导出 core 子模块 -> 成功加载
```
实际脚本会自动生成入口桩文件：
- `__init__.py`：动态加载 `.so` 模块，设置 `__path__` 和 `__package__`
- `__main__.py`：支持 `python -m hello` 运行，调用 `main()` 函数
### 3.3 ELF 修补原理
Termux 编译出的 `.so` 不能直接丢进 Briefcase，必须经过两步修补：
1. **`termux-elf-cleaner`**：剔除 Android 不支持的 ELF 段（如 `GNU_RELRO`），避免在低版本 Android 上加载崩溃。
2. **`patchelf`**：
   - `--set-rpath ''`：清除硬编码的库搜索路径，让系统默认路径生效。
   - `--replace-needed libpython${PY_VER}.so.1.0 libpython${PY_VER}.so`：**关键**。Termux 链接的是带版本号的精确库，而 Briefcase (Chaquopy) 提供的 Python 运行时库是不带版本号的模糊名，必须替换否则找不到 libpython。
---
## 4. 实施规范
### 4.1 项目目录结构规范
```text
myproject/
├── .github/workflows/build-android.yml    # CI 配置
├── apps/
│   ├── hello/                   # APP_NAME (应用名)
│   │   ├── src/
│   │   │   └── hello/           # 与应用名同名的包
│   │   │       ├── __init__.py  # [保留] 包标识
│   │   │       ├── __main__.py  # [保留] 入口执行
│   │   │       ├── core.py      # [编译] 核心代码
│   │   │       └── resources/   # [保留] 资源文件
│   │   └── pyproject.toml       # Briefcase 配置
│   ├── weather/                 # 另一个应用
│   └── xagent/                  # 另一个应用
└── requirements.txt
```

**多应用架构说明**：
- 所有应用统一放在 `apps/` 目录下
- 每个应用独立配置 `pyproject.toml`
- CI 通过 `app_name` 参数选择构建目标应用
### 4.2 阶段 1：编译保护 (Termux Docker)
**执行环境**：`ubuntu-24.04-arm` (GitHub ARM Runner) + `termux/termux-docker`
**执行流程**：
1. **安装工具链**：
   ```bash
   pkg install -y tur-repo  # Python 3.10/3.11 需要
   pkg install -y python${PY_VER} clang ninja patchelf termux-elf-cleaner findutils
   pip install nuitka==${NUITKA_VERSION}
   ```
2. **Nuitka 编译**：
   ```bash
   python -m nuitka \
     --module ${APP_NAME} \
     --include-package=${APP_NAME} \
     --output-dir=/tmp/compiled \
     --remove-output \
     --assume-yes-for-downloads \
     --no-progressbar
   # 产出: ${APP_NAME}.cpython-311.so
   ```
3. **统一重命名**：
   ```bash
   mv ${APP_NAME}.*.so ${APP_NAME}.so  # 去掉版本后缀
   ```
4. **ELF 清理**：
   ```bash
   termux-elf-cleaner ${APP_NAME}.so
   ```
5. **修复链接**：
   ```bash
   patchelf --set-rpath '' ${APP_NAME}.so
   patchelf --replace-needed libpython${PY_VER}.so.1.0 libpython${PY_VER}.so ${APP_NAME}.so
   ```
6. **上传产物**：通过 `actions/upload-artifact` 将 `.so` 文件传递给阶段 2。

**多架构并行**：使用 Matrix Strategy 同时编译 `arm64` 和 `arm32`：
| 架构 | Runner | Termux Arch | Android ABI |
|:---|:---|:---|:---|
| arm64 | `ubuntu-24.04-arm` | `aarch64` | `arm64-v8a` |
| arm32 | `ubuntu-24.04-arm` | `arm` | `armeabi-v7a` |
### 4.3 阶段 2：应用打包
**执行环境**：`ubuntu-latest` (GitHub 标准 x64 Runner)
**执行流程**：
1. **下载产物**：通过 `actions/download-artifact` 获取阶段 1 编译的 `.so` 文件。
2. **源码替换与入口桩生成**：
   ```bash
   # 保留非 .py 资源文件
   find ${APP_NAME} -type f ! -name '*.py' -print0
   
   # 删除明文源码
   rm -rf ${APP_NAME}
   mkdir -p ${APP_NAME}
   
   # 放入二进制产物
   cp ${APP_NAME}.so .
   
   # 生成入口桩文件
   # __init__.py: 动态加载 .so 模块
   # __main__.py: 支持 python -m ${APP_NAME} 运行
   ```
3. **环境配置**：
   - 使用 `actions/setup-java@v4` 安装 JDK 17
   - Briefcase 自动管理 Android SDK，无需手动配置
4. **Briefcase 三步曲**：
   ```bash
   briefcase create android -C "build_gradle_extra_content = \"android.defaultConfig.ndk.abiFilters = ['${ANDROID_ABI}']\""
   briefcase build android
   briefcase package android -p apk
   ```
5. **产物重命名**：为 APK 追加架构后缀（如 `xagent-arm64-1.0.0.apk`）并上传。

**Nuitka 开关**：通过 `enable_nuitka` 参数控制是否启用源码保护：
- `true`：编译为 `.so` 二进制，保护源码
- `false`：使用明文 `.py` 源码，便于调试
---
## 5. CI/CD 通用配置模板
为方便不同项目复用，所有差异化配置均提取到 `env` 和 `workflow_dispatch` 中。
### 5.1 触发方式
```yaml
on:
  push:
    tags:
      - 'android-*/v*'    # 标签触发: android-xagent/v1.0.0
  workflow_dispatch:
    inputs:
      app_name:
        description: 'App to build (hello / weather / xagent)'
        type: choice
        options: [hello, weather, xagent]
        default: 'xagent'
      python_version:
        description: 'Python version'
        type: choice
        options: ['3.10', '3.11', '3.12']
        default: '3.11'
      architectures:
        description: 'Target architectures (comma-separated)'
        type: choice
        options: ['arm64', 'arm32', 'arm64,arm32']
        default: 'arm64'
      enable_nuitka:
        description: 'Enable Nuitka compilation for source protection'
        type: boolean
        default: true
```
### 5.2 参数化变量
| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `app_name` | `xagent` | 应用名称（对应 `apps/` 下的目录名） |
| `python_version` | `3.11` | Python 版本（支持 3.10/3.11/3.12） |
| `architectures` | `arm64` | 目标架构（可选 arm64、arm32 或两者） |
| `enable_nuitka` | `true` | 是否启用 Nuitka 源码保护 |
| `NUITKA_VERSION` | `2.7.12` | Nuitka 编译器版本 |
| `BRIEFCASE_VERSION` | `0.4.2` | Briefcase 打包工具版本 |
### 5.3 派生变量自动推算
只需修改 `python_version`，CI 自动推算所有相关路径与包名，消除硬编码：
```text
PYTHON_VERSION = "3.11"
     │
     ├─▶ PY_LIB_FULL  = "libpython3.11.so.1.0"  → patchelf 源库名
     └─▶ PY_LIB_SHORT = "libpython3.11.so"      → patchelf 目标库名
```
### 5.4 作业流程
```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   prepare   │────▶│   compile   │────▶│    build    │
│  解析配置    │     │  Nuitka编译  │     │  APK打包    │
│  验证项目    │     │  (并行多架构) │     │  (并行多架构) │
└─────────────┘     └─────────────┘     └─────────────┘
```
**prepare**：解析标签或输入参数，验证应用配置
**compile**：Termux Docker 编译 `.so`（可跳过）
**build**：Briefcase 打包 APK
---
## 6. 常见问题与避坑指南
### Q1: 可以把 Briefcase 也放进 Termux Docker 里以节约时间吗？
**A**: 不建议。Termux Docker 缺乏 JDK 和完整的 Android SDK 生态，强行安装配置极度复杂且极易出错。两阶段架构虽然多了一次 Artifact 传递，但稳定性和可维护性远胜于混合环境。
### Q2: 可以用 `uraimo/run-on-arch-action` 替代 Termux Docker 吗？
**A**: 绝对不行。`uraimo` 跑的是标准 Debian/Ubuntu（glibc），编译出的 `.so` 依赖 `libc.so.6`，在 Android (Bionic) 上无法加载，会直接 Crash。
### Q3: `__init__.py` 和 `__main__.py` 需要编译进 `.so` 吗？
**A**: 
- `__init__.py`：**绝对不要**。它是 Python 识别包的唯一标识，缺失会导致 `ImportError`。实际脚本会自动生成入口桩 `__init__.py`，动态加载 `.so` 模块。
- `__main__.py`：**不要**。它是支持 `python -m ${APP_NAME}` 运行的入口，必须保留为明文 `.py`。实际脚本会自动生成此文件。
### Q4: 如果项目依赖了 C 扩展库（如 numpy/opencv）怎么办？
**A**: 
- **纯 Python 依赖**：写进 `requirements.txt`，由 Briefcase (Chaquopy) 在打包阶段自动 pip 安装。
- **含 C 扩展的依赖**：必须在阶段 1 的 Termux 环境中使用 `pip install` 编译安装，并在 Nuitka 编译时通过 `--include-package` 将其一起编入 `.so`，否则运行时缺失 `.so` 会报错。
### Q5: 私有仓库使用该方案的费用如何？
**A**: GitHub ARM Runner 在私有仓库中按 **2x 倍率** 消耗免费分钟数。一次完整构建（2 ARM 编译 + 2 x64 打包）约消耗 80-100 分钟。Free 计划每月 2000 分钟，约可构建 20 次。如构建频繁，建议使用自托管 ARM Runner。
### Q6: 如何在调试时跳过 Nuitka 编译？
**A**: 在 GitHub Actions 手动触发时，将 `enable_nuitka` 设为 `false`。此时 CI 会跳过编译阶段，直接使用明文 `.py` 源码打包 APK，便于快速调试。
---
## 7. 扩展与替代方案
| 方案 | 优势 | 劣势 | 适用场景 |
|:---|:---|:---|:---|
| **Cython (替代 Nuitka)** | 交叉编译资料较多，编译速度极快 | 需手写 `.pyx` 或手动处理类型，无法做到纯零侵入 | 对编译速度要求极高、代码量小的项目 |
| **自托管 ARM Runner** | 无分钟数限制，无 Docker Hub 拉取限制 | 需自备 ARM 物理机/云服务器并维护 | 商业项目、高频构建的私有仓库 |
| **GitHub NDK 交叉编译** | 无需 ARM 机器 | NDK 下载大(1.5G+)，Nuitka autoconf 极易失败，维护成本灾难级 | 极端情况下的备选，不推荐 |
