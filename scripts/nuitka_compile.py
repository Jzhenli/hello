#!/usr/bin/env python3
"""
Nuitka 编译脚本 (跨平台: Windows / Linux / macOS)

将 Python 模块编译为 .pyd (Windows) 或 .so (Linux/macOS)，
并生成入口桩文件，使编译后的模块可通过 `python -m module_name` 运行。

用法:
    python nuitka_compile.py <src_dir> [--python /path/to/python] [--extension .so] [-j N]

示例:
    # Windows (自动检测 .pyd)
    python nuitka_compile.py build/weather/windows/app/src/app

    # Linux ARM32 (自动检测 .so)
    shared-python/bin/python3 nuitka_compile.py build/weather/usr/app

    # 并行编译 (2 个工作线程)
    python nuitka_compile.py build/app/src -j 2

    # 强制指定扩展名 (跨编译场景)
    python nuitka_compile.py build/app/src --extension .so
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


COMPILED_EXTENSIONS = {
    "Windows": ".pyd",
    "Linux": ".so",
    "Darwin": ".so",
}

NUITKA_NOFOLLOW = [
    "--nofollow-import-to=tkinter",
    "--nofollow-import-to=unittest",
    "--nofollow-import-to=test",
    "--nofollow-import-to=tests",
    "--nofollow-import-to=*.test",
    "--nofollow-import-to=*.tests",
]


def detect_compiled_extension() -> str:
    system = platform.system()
    ext = COMPILED_EXTENSIONS.get(system)
    if ext is None:
        raise RuntimeError(
            f"不支持的平台: {system}\n"
            f"支持: {', '.join(COMPILED_EXTENSIONS)}\n"
            f"可使用 --extension 手动指定"
        )
    return ext


def check_nuitka(python_exe: str) -> str:
    try:
        result = subprocess.run(
            [python_exe, "-m", "nuitka", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ 错误: Nuitka 检查超时或找不到 Python: {e}")
        sys.exit(1)

    print("❌ 错误: Nuitka 未安装或不可用")
    print(f"  Python: {python_exe}")
    print(f"  返回码: {result.returncode}")
    if result.stderr:
        print(f"  stderr:\n{result.stderr}")
    print(f"  请运行: {python_exe} -m pip install nuitka ordered-set zstandard")
    sys.exit(1)


def scan_compilable_modules(src_dir: Path) -> list[str]:
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
    print(f"\n── 编译模块: {module_name} ──")

    compiled_dir = src_dir / f"compiled_{module_name}"
    if compiled_dir.exists():
        shutil.rmtree(compiled_dir)
    compiled_dir.mkdir()

    cmd = [
        python_exe, "-m", "nuitka",
        "--module", module_name,
        f"--output-dir={compiled_dir}",
        "--remove-output",
        "--assume-yes-for-downloads",
        "--nofollow-imports",
        f"--follow-import-to={module_name}",
        "--no-progressbar",
        "--lto=no",
        "--clang",
        "--python-flag=-OO",
    ] + NUITKA_NOFOLLOW

    result = subprocess.run(cmd, cwd=str(src_dir))

    if result.returncode != 0:
        raise RuntimeError(
            f"Nuitka 编译失败: {module_name} (exit code: {result.returncode})"
        )

    compiled_file = find_compiled_product(compiled_dir, module_name, extension)
    compiled_basename = compiled_file.name

    dest = src_dir / compiled_basename
    shutil.copy2(str(compiled_file), str(dest))

    shutil.rmtree(compiled_dir, ignore_errors=True)

    print(f"  ✅ 产物: {compiled_basename}")
    return compiled_basename


def compile_module_worker(args: tuple) -> tuple[str, bool, str]:
    module_name, src_dir, python_exe, extension = args
    try:
        compiled_basename = compile_module(module_name, src_dir, python_exe, extension)
        return (module_name, True, compiled_basename)
    except Exception as e:
        print(f"  ❌ 编译失败: {module_name} -> {e}")
        return (module_name, False, "")


def inject_stub(module_name: str, compiled_basename: str, src_dir: Path) -> None:
    module_dir = src_dir / module_name

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

    if module_dir.exists():
        shutil.rmtree(module_dir)
    module_dir.mkdir()

    for rel_path, data in saved_resources:
        dest = module_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    init_content = f"""\
import os
import sys
import importlib.util

_compiled_path = os.path.join(os.path.dirname(__file__), "..", "{compiled_basename}")
_spec = importlib.util.spec_from_file_location("{module_name}", _compiled_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["{module_name}"] = _module
_spec.loader.exec_module(_module)
"""
    (module_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    main_content = f"""\
import sys
import {module_name}

if hasattr({module_name}, "main"):
    {module_name}.main()
else:
    print("Error: No main() function found in {module_name}")
    sys.exit(1)
"""
    (module_dir / "__main__.py").write_text(main_content, encoding="utf-8")

    print(f"  ✅ 入口: {module_name}/__init__.py, __main__.py")


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

  # 并行编译 (2 个工作线程)
  python nuitka_compile.py build/app/src -j 2

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
    parser.add_argument(
        "-j", "--parallel",
        type=int,
        default=1,
        metavar="N",
        help="并行编译线程数 (默认: 1 顺序编译, 0=自动检测CPU核数)",
    )

    args = parser.parse_args()

    src_dir = Path(args.src_dir).resolve()
    python_exe = args.python or sys.executable
    extension = args.extension or detect_compiled_extension()
    parallel = args.parallel
    if parallel == 0:
        parallel = os.cpu_count() or 1

    print("=" * 55)
    print("  Nuitka 编译 (跨平台)")
    print(f"  平台    : {platform.system()} ({platform.machine()})")
    print(f"  产物类型: {extension}")
    print(f"  Python  : {python_exe}")
    print(f"  SRC_DIR : {src_dir}")
    if parallel > 1:
        print(f"  并行    : {parallel} 线程")
    print("=" * 55)

    if not src_dir.is_dir():
        print(f"\n❌ 错误: 找不到源码目录 {src_dir}")
        sys.exit(1)

    nuitka_version = check_nuitka(python_exe)
    print(f"  Nuitka  : {nuitka_version}")

    modules = scan_compilable_modules(src_dir)

    if not modules:
        print("\n⚠ 未发现可编译的模块 (需含 __init__.py 的子目录)")
        sys.exit(0)

    print(f"\n发现 {len(modules)} 个可编译模块: {', '.join(modules)}")

    start_time = time.time()

    compiled_results: dict[str, tuple[bool, str]] = {}

    if parallel > 1 and len(modules) > 1:
        print(f"\n🚀 并行编译 ({parallel} 线程)")
        worker_args = [
            (m, src_dir, python_exe, extension)
            for m in modules
        ]
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(compile_module_worker, arg): arg[0]
                for arg in worker_args
            }
            for future in as_completed(futures):
                module_name, success, compiled_basename = future.result()
                compiled_results[module_name] = (success, compiled_basename)
    else:
        for module_name in modules:
            try:
                compiled_basename = compile_module(
                    module_name, src_dir, python_exe, extension
                )
                compiled_results[module_name] = (True, compiled_basename)
            except Exception as e:
                print(f"  ❌ 编译失败: {module_name} -> {e}")
                compiled_results[module_name] = (False, "")

    compiled_count = 0
    failed_modules = []

    for module_name in modules:
        success, compiled_basename = compiled_results.get(module_name, (False, ""))
        if success:
            inject_stub(module_name, compiled_basename, src_dir)
            compiled_count += 1
        else:
            failed_modules.append(module_name)

    elapsed = time.time() - start_time
    if elapsed < 60:
        time_str = f"{elapsed:.1f}s"
    else:
        time_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    print()
    print("=" * 55)
    print("  编译完成")
    print(f"  成功: {compiled_count} 个模块")
    print(f"  耗时: {time_str}")

    if failed_modules:
        print(f"  失败: {len(failed_modules)} 个模块")
        for m in failed_modules:
            print(f"    - {m}")
        print("=" * 55)
        sys.exit(1)

    print("=" * 55)

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
