#!/usr/bin/env python3
"""
Nuitka 编译脚本 (跨平台: Windows / Linux / macOS / Android)

将 Python 模块编译为 .pyd (Windows) 或 .so (Linux/macOS)，
并生成入口桩文件，使编译后的模块可通过 `python -m module_name` 运行。

用法:
    # 完整编译 + 桩文件注入
    python nuitka_compile.py <src_dir> [--python /path/to/python] [--extension .so]

    # 仅注入桩文件（不编译，用于 Android 等预编译场景）
    python nuitka_compile.py <src_dir> --stub-only [--module weather]

示例:
    python nuitka_compile.py build/weather/windows/app/src/app
    python nuitka_compile.py .../python --stub-only --module weather
"""

import os
import sys
import shutil
import subprocess
import tempfile
import platform
import argparse
from pathlib import Path
from typing import List, Optional

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))


COMPILED_EXTENSIONS = {
    "Windows": ".pyd",
    "Linux": ".so",
    "Darwin": ".so",
}

INIT_PY_TEMPLATE = '''\
import sys, importlib.util as u, os
d = os.path.dirname(os.path.abspath(__file__))
m, s = sys.modules["{pkg_name}"], sys.modules["{pkg_name}"].__spec__
sp = u.spec_from_file_location("{pkg_name}", os.path.join(d, "{mod_file}"))
lib = u.module_from_spec(sp); sp.loader.exec_module(lib)
sys.meta_path.sort(key=lambda f: type(f).__name__ == "nuitka_module_loader")
m.__dict__.update({{k: v for k, v in vars(lib).items() if k[:2] != "__"}})
m.__spec__, m.__file__, m._RESOURCE_DIR = s, __file__, d
lib._RESOURCE_DIR = d
sys.modules["{pkg_name}"] = m
'''

MAIN_PY_TEMPLATE = '''\
import {pkg_name}
{pkg_name}.main()
'''


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
        raise RuntimeError(f"Nuitka 检查失败: {e}") from e

    raise RuntimeError(
        f"Nuitka 未安装或不可用\n"
        f"  请运行: {python_exe} -m pip install nuitka ordered-set zstandard"
    )


def scan_compilable_modules(src_dir: Path, module_filter: Optional[List[str]] = None) -> List[str]:
    skip_dirs = {"__pycache__", "compiled", "app_packages"}
    modules = []

    for item in sorted(src_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name in skip_dirs or item.name.startswith("."):
            continue
        if (item / "__init__.py").exists():
            if module_filter and item.name not in module_filter:
                continue
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


def detect_mod_file(module_dir: Path, module_name: str) -> str:
    for f in module_dir.iterdir():
        if f.is_file() and f.name.startswith(module_name) and f.suffix in (".pyd", ".so"):
            return f.name
    raise FileNotFoundError(f"No compiled module found in {module_dir}")


def compile_module(
    module_name: str,
    src_dir: Path,
    python_exe: str,
    extension: str,
) -> str:
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

    compiled_file = find_compiled_product(compiled_dir, module_name, extension)
    compiled_basename = compiled_file.name

    dest = src_dir / compiled_basename
    shutil.copy2(str(compiled_file), str(dest))
    print(f"  ✅ 产物: {compiled_basename}")

    return compiled_basename


def inject_stub(module_name: str, src_dir: Path, mod_file: Optional[str] = None) -> None:
    module_dir = src_dir / module_name

    _tmpdir = Path(tempfile.mkdtemp())
    try:
        if module_dir.exists():
            for f in module_dir.rglob("*"):
                if f.is_file() and not f.name.endswith(".py"):
                    rel_path = f.relative_to(module_dir)
                    dest = _tmpdir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(dest))

            res_count = sum(1 for _ in _tmpdir.rglob("*") if _.is_file())
            if res_count > 0:
                print(f"  保留 {res_count} 个非 .py 资源文件")

        if module_dir.exists():
            shutil.rmtree(module_dir)
        module_dir.mkdir()

        for f in _tmpdir.rglob("*"):
            if f.is_file():
                rel_path = f.relative_to(_tmpdir)
                dest = module_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))
    finally:
        shutil.rmtree(str(_tmpdir), ignore_errors=True)

    if mod_file:
        src_file = src_dir / mod_file
        if src_file.exists():
            shutil.move(str(src_file), str(module_dir / mod_file))
    else:
        mod_file = detect_mod_file(module_dir, module_name)

    (module_dir / "__init__.py").write_text(
        INIT_PY_TEMPLATE.format(pkg_name=module_name, mod_file=mod_file),
        encoding="utf-8",
    )
    (module_dir / "__main__.py").write_text(
        MAIN_PY_TEMPLATE.format(pkg_name=module_name),
        encoding="utf-8",
    )
    print(f"  ✅ 入口: {module_name}/__init__.py, __main__.py")


def main():
    parser = argparse.ArgumentParser(
        description="Nuitka 编译脚本 (跨平台)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # 完整编译 (Windows)
  python nuitka_compile.py build/weather/windows/app/src/app

  # 仅注入桩文件 (Android 预编译场景)
  python nuitka_compile.py .../python --stub-only --module weather
""",
    )
    parser.add_argument("src_dir", type=str, help="源码目录路径")
    parser.add_argument("--python", type=str, default=None, help="Python 解释器路径")
    parser.add_argument("--extension", type=str, default=None, choices=[".pyd", ".so"], help="编译产物扩展名")
    parser.add_argument("--stub-only", action="store_true", help="仅注入桩文件，不编译")
    parser.add_argument("--module", type=str, nargs="+", default=None, help="指定处理的模块名")

    args = parser.parse_args()
    src_dir = Path(args.src_dir).resolve()
    python_exe = args.python or sys.executable
    extension = args.extension or detect_compiled_extension()

    if not src_dir.is_dir():
        print(f"❌ 错误: 找不到源码目录 {src_dir}")
        sys.exit(1)

    modules = scan_compilable_modules(src_dir, args.module)
    if not modules:
        print("⚠ 未发现可处理的模块")
        sys.exit(0)

    print("=" * 50)
    print(f"  模式: {'桩文件注入' if args.stub_only else '编译 + 桩文件注入'}")
    print(f"  平台: {platform.system()} ({platform.machine()})")
    print(f"  模块: {', '.join(modules)}")
    print("=" * 50)

    if args.stub_only:
        for module_name in modules:
            print(f"\n── 注入桩文件: {module_name} ──")
            inject_stub(module_name, src_dir)
    else:
        nuitka_version = check_nuitka(python_exe)
        print(f"  Nuitka: {nuitka_version}")

        compiled_count = 0
        failed_modules = []

        for module_name in modules:
            try:
                mod_file = compile_module(module_name, src_dir, python_exe, extension)
                inject_stub(module_name, src_dir, mod_file)
                compiled_count += 1
            except Exception as e:
                print(f"  ❌ 编译失败: {module_name} -> {e}")
                failed_modules.append(module_name)
            finally:
                compiled_dir = src_dir / "compiled"
                if compiled_dir.exists():
                    shutil.rmtree(compiled_dir, ignore_errors=True)

        print()
        print("=" * 50)
        print(f"  成功: {compiled_count} 个模块")
        if failed_modules:
            print(f"  失败: {len(failed_modules)} 个模块")
            for m in failed_modules:
                print(f"    - {m}")
            sys.exit(1)
        print("=" * 50)


if __name__ == "__main__":
    main()
