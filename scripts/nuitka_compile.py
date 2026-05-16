#!/usr/bin/env python3
"""
Nuitka 编译脚本 (跨平台: Windows / Linux / macOS)

将 Python 模块编译为 .pyd (Windows) 或 .so (Linux/macOS)，
并生成入口桩文件，使编译后的模块可通过 `python -m module_name` 运行。

用法:
    python nuitka_compile.py <src_dir> [--python /path/to/python] [--extension .so]

示例:
    # Windows (自动检测 .pyd)
    python nuitka_compile.py build/weather/windows/app/src/app

    # Linux ARM32 (自动检测 .so)
    shared-python/bin/python3 nuitka_compile.py build/weather/usr/app

    # 强制指定扩展名 (跨编译场景)
    python nuitka_compile.py build/app/src --extension .so
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  平台检测
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMPILED_EXTENSIONS = {
    "Windows": ".pyd",
    "Linux": ".so",
    "Darwin": ".so",
}


def detect_compiled_extension() -> str:
    """根据当前平台自动检测编译产物扩展名"""
    system = platform.system()
    ext = COMPILED_EXTENSIONS.get(system)
    if ext is None:
        raise RuntimeError(
            f"不支持的平台: {system}\n"
            f"支持: {', '.join(COMPILED_EXTENSIONS)}\n"
            f"可使用 --extension 手动指定"
        )
    return ext


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  前置检查
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_nuitka(python_exe: str) -> str:
    """检查 Nuitka 是否可用，返回版本号"""
    try:
        result = subprocess.run(
            [python_exe, "-m", "nuitka", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().split("\n")[0]
            return version_line
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print("❌ 错误: Nuitka 检查超时或找不到 Python")
        print(f"  异常: {e}")
        sys.exit(1)

    print("❌ 错误: Nuitka 未安装或不可用")
    print(f"  Python: {python_exe}")
    print(f"  返回码: {result.returncode}")
    if result.stdout:
        print(f"  stdout:\n{result.stdout}")
    if result.stderr:
        print(f"  stderr:\n{result.stderr}")
    print(f"  请运行: {python_exe} -m pip install nuitka ordered-set zstandard")
    sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  核心逻辑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def scan_compilable_modules(src_dir: Path) -> list[str]:
    """
    扫描源码目录，返回所有可编译的模块名。
    可编译 = 包含 __init__.py 的子目录
    """
    skip_dirs = {"__pycache__", "compiled"}
    modules = []

    for item in sorted(src_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name in skip_dirs:
            continue
        if (item / "__init__.py").exists():
            modules.append(item.name)

    return modules


def find_compiled_product(compiled_dir: Path, module_name: str, extension: str) -> Path:
    """
    在编译目录中查找编译产物。
    动态匹配，不硬编码 Python 版本/平台后缀。
    """
    pattern = f"{module_name}*{extension}"
    matches = list(compiled_dir.glob(pattern))

    if not matches:
        dir_contents = (
            [f.name for f in sorted(compiled_dir.iterdir())]
            if compiled_dir.exists() else ["(目录不存在)"]
        )
        raise FileNotFoundError(
            f"编译产物未找到: {compiled_dir / pattern}\n"
            f"目录内容: {dir_contents}"
        )

    if len(matches) > 1:
        print(f"  ⚠ 发现多个匹配，使用: {matches[0].name}")

    return matches[0]


def compile_module(
    module_name: str,
    src_dir: Path,
    python_exe: str,
    extension: str,
) -> str:
    """
    使用 Nuitka 编译单个 Python 模块，返回产物文件名。
    """
    print(f"\n── 编译模块: {module_name} ──")

    compiled_dir = src_dir / "compiled"
    if compiled_dir.exists():
        shutil.rmtree(compiled_dir)
    compiled_dir.mkdir()

    cmd = [
        python_exe, "-m", "nuitka",
        "--module", module_name,
        f"--output-dir={compiled_dir}",
        "--remove-output",
        "--assume-yes-for-downloads",
        f"--include-package={module_name}",
        "--no-progressbar",
    ]

    result = subprocess.run(cmd, cwd=str(src_dir))

    if result.returncode != 0:
        raise RuntimeError(
            f"Nuitka 编译失败: {module_name} (exit code: {result.returncode})"
        )

    # 动态查找编译产物（不硬编码 Python 版本/平台后缀）
    compiled_file = find_compiled_product(compiled_dir, module_name, extension)
    compiled_basename = compiled_file.name

    # 复制到源码根目录
    dest = src_dir / compiled_basename
    shutil.copy2(str(compiled_file), str(dest))
    print(f"  ✅ 产物: {compiled_basename}")

    return compiled_basename


def inject_stub(module_name: str, compiled_basename: str, src_dir: Path) -> None:
    """
    删除原始源码目录，生成 __init__.py 和 __main__.py 入口桩文件。
    保留非 .py 资源文件（配置、数据、模板等）。

    __init__.py : 通过 importlib 动态加载编译产物，注册到 sys.modules
    __main__.py : 直接 import 模块并调用 main()（复用 __init__.py 的加载结果）
    """
    module_dir = src_dir / module_name

    # ─── 保存非 .py 资源文件 ───
    saved_resources: list[tuple[Path, bytes]] = []
    if module_dir.exists():
        for f in module_dir.rglob("*"):
            if f.is_file() and not f.name.endswith(".py"):
                rel_path = f.relative_to(module_dir)
                try:
                    saved_resources.append((rel_path, f.read_bytes()))
                except (OSError, PermissionError):
                    print(f"  ⚠ 跳过无法读取的资源: {rel_path}")

    if saved_resources:
        print(f"  保留 {len(saved_resources)} 个非 .py 资源文件")

    # ─── 清理原始源码 ───
    if module_dir.exists():
        shutil.rmtree(module_dir)
    module_dir.mkdir()

    # ─── 恢复非 .py 资源文件 ───
    for rel_path, data in saved_resources:
        dest = module_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    # ─── 生成 __init__.py ───
    init_content = """\
import os, sys, importlib.util as _u

_n = __name__
_d = os.path.dirname(os.path.abspath(__file__))
_p = os.path.dirname(_d)
_f = next((f for f in os.listdir(_p) if f.startswith(_n) and f.endswith((".pyd", ".so"))), None)
if not _f: raise ImportError(f"No {_n} compiled module in {_p}")
if hasattr(os, "add_dll_directory"): os.add_dll_directory(os.path.dirname(_p))

_s = _u.spec_from_file_location(_n, os.path.join(_p, _f))
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)
_m.__path__ = getattr(_m, "__path__", None) or [_d]
_m.__package__ = _n
if _m.__spec__: _m.__spec__.submodule_search_locations = list(_m.__path__)
_m._RESOURCE_DIR = _d

class _F:
    @staticmethod
    def find_spec(n, *_):
        if n == f"{_n}.__main__": return _u.spec_from_file_location(n, os.path.join(_d, "__main__.py"))

sys.meta_path.insert(0, _F)
sys.modules[_n] = _m
"""
    (module_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    # ─── 生成 __main__.py ───
    main_content = """\
import importlib, sys
_m = importlib.import_module(__package__)
_m.main() if hasattr(_m, "main") else sys.exit(f"No main() in {__package__}")
"""
    (module_dir / "__main__.py").write_text(main_content, encoding="utf-8")

    print(f"  ✅ 入口: {module_name}/__init__.py, __main__.py")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  主流程
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(
        description="Nuitka 编译脚本 (跨平台: Windows .pyd / Linux .so)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # Windows (自动检测 .pyd)
  python nuitka_compile.py build/weather/windows/app/src/app

  # Linux ARM32 (自动检测 .so)
  shared-python/bin/python3 nuitka_compile.py build/weather/usr/app

  # 强制指定扩展名 (跨编译场景)
  python nuitka_compile.py build/app/src --extension .so
""",
    )
    parser.add_argument(
        "src_dir",
        type=str,
        help="源码目录路径 (包含 Python 模块的目录)",
    )
    parser.add_argument(
        "--python",
        type=str,
        default=None,
        help="运行 Nuitka 的 Python 解释器 (默认: sys.executable)",
    )
    parser.add_argument(
        "--extension",
        type=str,
        default=None,
        choices=[".pyd", ".so"],
        help="编译产物扩展名 (默认: 自动检测 - Windows: .pyd, Linux/macOS: .so)",
    )

    args = parser.parse_args()

    src_dir = Path(args.src_dir).resolve()
    python_exe = args.python or sys.executable
    extension = args.extension or detect_compiled_extension()

    # ─── 打印配置 ───
    print("=" * 55)
    print("  Nuitka 编译 (跨平台)")
    print(f"  平台    : {platform.system()} ({platform.machine()})")
    print(f"  产物类型: {extension}")
    print(f"  Python  : {python_exe}")
    print(f"  SRC_DIR : {src_dir}")
    print("=" * 55)

    # ─── 目录校验 ───
    if not src_dir.is_dir():
        print(f"\n❌ 错误: 找不到源码目录 {src_dir}")
        print("当前目录结构:")
        cwd = Path(".").resolve()
        for p in sorted(cwd.rglob("*"))[:30]:
            if p.is_dir():
                print(f"  {p.relative_to(cwd)}/")
        sys.exit(1)

    # ─── 检查 Nuitka ───
    nuitka_version = check_nuitka(python_exe)
    print(f"  Nuitka  : {nuitka_version}")

    # ─── 扫描可编译模块 ───
    modules = scan_compilable_modules(src_dir)

    if not modules:
        print("\n⚠ 未发现可编译的模块 (需含 __init__.py 的子目录)")
        sys.exit(0)

    print(f"\n发现 {len(modules)} 个可编译模块: {', '.join(modules)}")

    # ─── 逐个编译 ───
    compiled_count = 0
    failed_modules = []

    for module_name in modules:
        try:
            compiled_basename = compile_module(
                module_name, src_dir, python_exe, extension
            )
            inject_stub(module_name, compiled_basename, src_dir)
            compiled_count += 1
        except Exception as e:
            print(f"  ❌ 编译失败: {module_name} -> {e}")
            failed_modules.append(module_name)
        finally:
            # 清理临时编译目录
            compiled_dir = src_dir / "compiled"
            if compiled_dir.exists():
                shutil.rmtree(compiled_dir, ignore_errors=True)

    # ─── 编译报告 ───
    print()
    print("=" * 55)
    print("  编译完成")
    print(f"  成功: {compiled_count} 个模块")

    if failed_modules:
        print(f"  失败: {len(failed_modules)} 个模块")
        for m in failed_modules:
            print(f"    - {m}")
        print("=" * 55)
        sys.exit(1)

    print("=" * 55)

    # 列出编译产物
    compiled_files = [f for f in src_dir.glob(f"*{extension}") if f.is_file()]
    if compiled_files:
        print(f"\n编译产物 ({extension}):")
        for f in sorted(compiled_files):
            size_kb = f.stat().st_size / 1024
            if size_kb >= 1024:
                print(f"  {f.name} ({size_kb / 1024:.1f} MB)")
            else:
                print(f"  {f.name} ({size_kb:.1f} KB)")
    else:
        print(f"\n⚠ 未找到编译产物 (*{extension})")


if __name__ == "__main__":
    main()
