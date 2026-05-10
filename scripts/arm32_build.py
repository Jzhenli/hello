#!/usr/bin/env python3
"""
ARM32 构建脚本 — 在 QEMU ARM32 环境中运行

负责:
  1. 下载 PBS Python 并准备 shared-python 环境
  2. 构建/编译/打包各应用
  3. 调用 nuitka_compile.py 进行编译

用法:
    python3 arm32_build.py \
        --build-type full \
        --python-version 3.11 \
        --pbs-release 20260508 \
        --enable-nuitka true \
        --strip-stdlib true
"""

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  常量
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PBS_PYTHON_VERSIONS = {
    "3.10": "3.10.16",
    "3.11": "3.11.15",
    "3.12": "3.12.13",
}

STRIPPED_STDLIB_MODULES = [
    "tkinter", "idlelib", "lib2to3", "unittest",
    "pydoc_data", "curses", "tty", "webbrowser",
]

PBS_URL_TEMPLATE = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    "{pbs_release}/cpython-{pbs_python}+{pbs_release}"
    "-armv7-unknown-linux-gnueabihf-install_only_stripped.tar.gz"
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_cmd(cmd, **kwargs):
    """运行命令，失败时抛异常"""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def parse_bool(value: str) -> bool:
    """将字符串转为布尔值"""
    return value.lower() in ("true", "1", "yes")


def extract_version_from_init(init_file: Path) -> str:
    """从 __init__.py 提取 __version__"""
    if not init_file.exists():
        return "0.0.0"
    content = init_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  核心构建器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ARM32Builder:
    def __init__(self, args):
        self.build_type = args.build_type
        self.target_component = args.target_component
        self.target_version = args.target_version
        self.python_version = args.python_version
        self.pbs_release = args.pbs_release
        self.enable_nuitka = parse_bool(args.enable_nuitka)
        self.strip_stdlib = parse_bool(args.strip_stdlib)
        self.repo_root = Path(args.repo_root).resolve()
        self.dist_dir = self.repo_root / "dist"
        self.shared_python_dir = self.repo_root / "shared-python"

    @property
    def pbs_python(self) -> str:
        return PBS_PYTHON_VERSIONS.get(self.python_version, self.python_version)

    @property
    def pbs_python_exe(self) -> Path:
        return self.shared_python_dir / "bin" / "python3"

    @property
    def pbs_pip_exe(self) -> Path | None:
        pip3 = self.shared_python_dir / "bin" / "pip3"
        if pip3.exists():
            return pip3
        return None

    # ─── pip 封装 ───

    def pip_install(self, *args):
        """使用 PBS Python 的 pip 安装包"""
        if self.pbs_pip_exe:
            cmd = [str(self.pbs_pip_exe), "install"] + list(args)
        else:
            cmd = [str(self.pbs_python_exe), "-m", "pip", "install"] + list(args)
        run_cmd(cmd)

    def pip_install_target(self, target_dir: Path, requirements_file: Path):
        """安装依赖到指定目录"""
        if self.pbs_pip_exe:
            cmd = [
                str(self.pbs_pip_exe), "install",
                "--target", str(target_dir),
                "-r", str(requirements_file),
            ]
        else:
            cmd = [
                str(self.pbs_python_exe), "-m", "pip", "install",
                "--target", str(target_dir),
                "-r", str(requirements_file),
            ]
        try:
            result = run_cmd(cmd, capture_output=True, text=True)
            # 只显示最后几行，与原始 tail -5 行为一致
            if result.stdout:
                lines = result.stdout.strip().split("\n")
                for line in lines[-5:]:
                    print(f"  {line}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ pip install 失败:")
            if e.stdout:
                tail = e.stdout[-500:] if len(e.stdout) > 500 else e.stdout
                print(tail)
            if e.stderr:
                tail = e.stderr[-500:] if len(e.stderr) > 500 else e.stderr
                print(tail)
            raise

    # ─── 主入口 ───

    def run(self):
        self._print_header()

        self.dist_dir.mkdir(parents=True, exist_ok=True)

        need_package_python = self.build_type in ("full", "python-only")
        self.prepare_shared_python(need_package_python)

        if self.build_type in ("full", "app-only"):
            self.build_apps()

        self._fix_dist_permissions()

    def _print_header(self):
        type_labels = {
            "full": "🚀 全量构建模式",
            "python-only": "🐍 仅构建 Shared Python",
            "app-only": f"🎯 仅构建应用: {self.target_component}",
        }
        print("=" * 55)
        print("  ARM32 Build")
        print("=" * 55)
        print(f"  模式      : {type_labels.get(self.build_type, self.build_type)}")
        print(f"  Python    : {self.python_version} (PBS {self.pbs_python})")
        print(f"  Nuitka    : {'启用' if self.enable_nuitka else '禁用'}")
        print(f"  裁剪stdlib: {'启用' if self.strip_stdlib else '禁用'}")
        print("=" * 55)

    # ─── Shared Python ───

    def prepare_shared_python(self, need_package: bool):
        print("\n━━━ 准备 shared-python 环境 ━━━")

        self._download_pbs_python()
        self._strip_stdlib()
        self._write_version(need_package)

        if need_package:
            self._package_shared_python()

    def _download_pbs_python(self):
        url = PBS_URL_TEMPLATE.format(
            pbs_release=self.pbs_release,
            pbs_python=self.pbs_python,
        )
        tar_path = Path("/tmp/pbs.tar.gz")

        print(f"  下载: {url}")
        run_cmd(["wget", "-q", url, "-O", str(tar_path)])
        run_cmd(["tar", "xzf", str(tar_path), "-C", "/tmp/"])

        # 查找解压目录
        pbs_dir = Path("/tmp/python")
        if not pbs_dir.is_dir():
            candidates = sorted(Path("/tmp").glob("cpython*"))
            pbs_dir = candidates[0] if candidates else None

        if not pbs_dir or not pbs_dir.is_dir():
            print("❌ 无法找到解压后的 Python 目录")
            sys.exit(1)

        # 复制到 shared-python
        self.shared_python_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(["cp", "-a", f"{pbs_dir}/.", str(self.shared_python_dir)])

        # 验证
        if not self.pbs_python_exe.exists():
            print(f"❌ python3 不可执行: {self.pbs_python_exe}")
            sys.exit(1)

        print(f"  ✅ PBS Python 已就绪: {self.pbs_python_exe}")

    def _strip_stdlib(self):
        if not self.strip_stdlib:
            return

        print("  裁剪 stdlib...")
        pylib_dirs = list(self.shared_python_dir.glob("lib/python3.*"))
        if not pylib_dirs:
            print("  ⚠ 未找到 lib/python3.* 目录")
            return

        pylib = pylib_dirs[0]

        # 删除指定模块
        for mod in STRIPPED_STDLIB_MODULES:
            mod_path = pylib / mod
            if mod_path.exists():
                shutil.rmtree(mod_path, ignore_errors=True)

        # 删除 __pycache__, test, tests 目录
        for pattern in ["__pycache__", "test", "tests"]:
            for d in pylib.rglob(pattern):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

        # 删除 include
        include_dir = self.shared_python_dir / "include"
        if include_dir.exists():
            shutil.rmtree(include_dir)

        print("  ✅ stdlib 已裁剪")

    def _write_version(self, need_package: bool):
        if self.build_type == "python-only" and self.target_version:
            py_ver = self.target_version
        else:
            py_ver = f"{self.pbs_python}-{self.pbs_release}"

        (self.shared_python_dir / "VERSION").write_text(py_ver, encoding="utf-8")
        print(f"  版本: {py_ver}")

    def _package_shared_python(self):
        py_ver = (self.shared_python_dir / "VERSION").read_text().strip()
        tar_name = "shared-python-base-arm32.tar.gz"
        tar_path = self.dist_dir / tar_name

        print(f"  打包: {tar_name}")
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(self.shared_python_dir), arcname="shared-python")

        print(f"  ✅ shared-python ({py_ver}) → dist/{tar_name}")

    # ─── 应用构建 ───

    def build_apps(self):
        # 确定要构建的应用列表
        # [Fix #1] 不再过滤 src/ 目录，列出所有子目录
        if self.build_type == "full":
            apps_dir = self.repo_root / "apps"
            app_names = [
                d.name for d in sorted(apps_dir.iterdir())
                if d.is_dir()
            ]
        elif self.build_type == "app-only":
            app_dir = self.repo_root / "apps" / self.target_component
            if not app_dir.is_dir():
                print(f"❌ 错误: 目录 {app_dir} 不存在")
                sys.exit(1)
            app_names = [self.target_component]
        else:
            return

        if not app_names:
            print("⚠ 未发现可构建的应用")
            return

        # 安装 Nuitka
        if self.enable_nuitka:
            print("\n━━━ 安装 Nuitka ━━━")
            self.pip_install("nuitka", "ordered-set", "zstandard")

        # 逐个构建
        for app_name in app_names:
            self.build_app(app_name)

    def build_app(self, app_name: str):
        print(f"\n{'=' * 55}")
        print(f"  构建: {app_name}")
        print(f"{'=' * 55}")

        app_dir = self.repo_root / "apps" / app_name
        build_dir = self.repo_root / "build" / app_name

        # 清理 & 创建目录
        if build_dir.exists():
            shutil.rmtree(build_dir)
        (build_dir / "usr" / "app").mkdir(parents=True)
        (build_dir / "usr" / "app_packages").mkdir(parents=True)

        # 复制源码
        # [Fix #5] 使用纯 Python 复制，不再依赖 cp -a
        app_src = app_dir / "src"
        if app_src.is_dir():
            self._copy_tree(app_src, build_dir / "usr" / "app")
        else:
            for py_file in app_dir.glob("*.py"):
                shutil.copy2(str(py_file), str(build_dir / "usr" / "app"))

        # 安装依赖
        req_file = app_dir / "requirements.txt"
        if req_file.exists():
            print("  安装依赖...")
            self.pip_install_target(build_dir / "usr" / "app_packages", req_file)

        # 检测模块名 & 版本
        module_name = self._detect_module_name(build_dir, app_name)
        app_version = self._resolve_version(app_dir, module_name, app_name)

        (build_dir / "VERSION").write_text(app_version, encoding="utf-8")
        print(f"  模块: {module_name}, 版本: {app_version}")

        # Nuitka 编译
        if self.enable_nuitka:
            self._run_nuitka(build_dir)

        # 生成启动脚本
        self._generate_run_sh(build_dir, module_name, app_version)

        # 清理
        self._cleanup_build(build_dir)

        # 打包
        tar_path = self.dist_dir / f"{app_name}-arm32.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(build_dir), arcname=app_name)

        print(f"  ✅ {app_name} ({app_version}) → dist/{tar_path.name}")

    def _detect_module_name(self, build_dir: Path, app_name: str) -> str:
        """检测主模块名"""
        app_dir = build_dir / "usr" / "app"

        # 优先: 与应用同名的目录 + __main__.py
        if (app_dir / app_name / "__main__.py").exists():
            return app_name

        # 其次: 任何含 __main__.py 的子目录 (深度 1)
        for main_file in sorted(app_dir.rglob("__main__.py")):
            if main_file.parent.parent == app_dir:
                return main_file.parent.name

        # [Fix #9] 根级 __main__.py 存在时，查找任意含 __main__.py 的深层子目录
        if (app_dir / "__main__.py").exists():
            for main_file in sorted(app_dir.rglob("__main__.py")):
                if main_file.parent != app_dir:
                    return main_file.parent.name

        return app_name

    def _resolve_version(self, app_dir: Path, module_name: str, app_name: str) -> str:
        """解析应用版本号"""
        # app-only 模式优先使用 tag 版本
        if self.build_type == "app-only" and self.target_version:
            return self.target_version

        # 从 __init__.py 读取
        init_file = app_dir / "src" / module_name / "__init__.py"
        version = extract_version_from_init(init_file)
        return version or "0.0.0"

    def _run_nuitka(self, build_dir: Path):
        """调用跨平台 nuitka_compile.py 脚本"""
        print("  Nuitka 编译...")
        nuitka_script = self.repo_root / "scripts" / "nuitka_compile.py"
        app_src = build_dir / "usr" / "app"

        run_cmd([
            str(self.pbs_python_exe),
            str(nuitka_script),
            str(app_src),
            "--python", str(self.pbs_python_exe),
        ])

    def _generate_run_sh(self, build_dir: Path, module_name: str, app_version: str):
        """生成启动脚本 run.sh"""
        run_sh = build_dir / "run.sh"
        content = f"""\
#!/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "${{BASH_SOURCE[0]}}")")"
PYTHON="/opt/shared-python/bin/python3"
if [ ! -x "$PYTHON" ]; then
  echo "错误: 未找到共享 Python" >&2; exit 1
fi
export PYTHONPATH="${{SCRIPT_DIR}}/usr/app:${{SCRIPT_DIR}}/usr/app_packages"
export LD_LIBRARY_PATH="/opt/shared-python/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
export APP_VERSION="{app_version}"
exec -a "{module_name}" "$PYTHON" -s -m {module_name} "$@"
"""
        run_sh.write_text(content, encoding="utf-8")
        run_sh.chmod(0o755)
        print(f"  ✅ 启动脚本: run.sh")

    def _cleanup_build(self, build_dir: Path):
        """清理构建目录中的冗余文件"""
        app_packages = build_dir / "usr" / "app_packages"
        cleanup_patterns_dirs = ["*.dist-info", "*.egg-info", "tests", "test"]
        for pattern in cleanup_patterns_dirs:
            for d in app_packages.rglob(pattern):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

        # 全局清理
        for d in build_dir.rglob("__pycache__"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
        for f in build_dir.rglob("*.pyc"):
            f.unlink(missing_ok=True)
        for f in build_dir.rglob("*.pyo"):
            f.unlink(missing_ok=True)

    def _copy_tree(self, src: Path, dst: Path):
        """递归复制目录内容（纯 Python 实现）"""
        if not dst.exists():
            dst.mkdir(parents=True)
        for item in src.iterdir():
            dest_item = dst / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(dest_item), symlinks=True)
            else:
                shutil.copy2(str(item), str(dest_item))

    def _fix_dist_permissions(self):
        """修正 dist 目录权限"""
        if not self.dist_dir.exists():
            return
        for f in self.dist_dir.rglob("*"):
            if f.is_dir():
                f.chmod(0o755)
            elif f.is_file():
                f.chmod(0o644)
        # install.sh 需要可执行
        install_sh = self.dist_dir / "install.sh"
        if install_sh.exists():
            install_sh.chmod(0o755)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  入口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(
        description="ARM32 构建脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--build-type", required=True,
                        choices=["full", "python-only", "app-only"],
                        help="构建类型")
    parser.add_argument("--target-component", default="",
                        help="目标组件名 (app-only 模式)")
    parser.add_argument("--target-version", default="",
                        help="目标版本号")
    parser.add_argument("--python-version", default="3.11",
                        help="Python 主版本 (3.10/3.11/3.12)")
    parser.add_argument("--pbs-release", default="20260508",
                        help="python-build-standalone release 标签")
    parser.add_argument("--enable-nuitka", default="true",
                        help="启用 Nuitka 编译 (true/false)")
    parser.add_argument("--strip-stdlib", default="true",
                        help="裁剪 stdlib (true/false)")
    parser.add_argument("--repo-root", default=".",
                        help="仓库根目录")

    args = parser.parse_args()
    builder = ARM32Builder(args)
    builder.run()


if __name__ == "__main__":
    main()
