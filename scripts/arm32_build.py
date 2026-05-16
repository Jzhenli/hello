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
        --enable-nuitka true \
        --strip-stdlib true
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import PBS_PYTHON_VERSIONS, PBS_RELEASE, PIWHEELS_URL, STRIPPED_STDLIB_MODULES
from utils import run_cmd, parse_bool, format_size, extract_version_from_init


PBS_URL_TEMPLATE = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    "{pbs_release}/cpython-{pbs_python}+{pbs_release}"
    "-armv7-unknown-linux-gnueabihf-install_only_stripped.tar.gz"
)


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
        return pip3 if pip3.exists() else None

    def _pip_cmd_base(self) -> list[str]:
        if self.pbs_pip_exe:
            return [str(self.pbs_pip_exe), "install", f"--extra-index-url={PIWHEELS_URL}"]
        return [str(self.pbs_python_exe), "-m", "pip", "install", f"--extra-index-url={PIWHEELS_URL}"]

    def pip_install(self, *args, verify_nuitka=False):
        env = os.environ.copy()
        env["PIP_ROOT_USER_ACTION"] = "ignore"
        run_cmd(self._pip_cmd_base() + list(args), env=env)
        if verify_nuitka:
            self._verify_nuitka_install()

    def _verify_nuitka_install(self):
        result = subprocess.run(
            [str(self.pbs_python_exe), "-m", "nuitka", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✅ Nuitka 验证成功: {result.stdout.strip().split(chr(10))[0]}")
            return

        print("  ⚠ Nuitka 验证失败，调试信息:")
        print(f"  返回码: {result.returncode}")
        if result.stderr:
            print(f"  stderr:\n{result.stderr}")

        for pkg in ["ordered_set", "zstandard"]:
            r = subprocess.run(
                [str(self.pbs_python_exe), "-c", f"import {pkg}; print({pkg}.__file__)"],
                capture_output=True, text=True
            )
            status = "✅" if r.returncode == 0 else "❌"
            print(f"  {pkg}: {status} {r.stdout.strip() or r.stderr.strip()}")

        result2 = subprocess.run(
            [str(self.pbs_python_exe), "-c", "import site; print(chr(10).join(site.getsitepackages()))"],
            capture_output=True, text=True
        )
        print(f"  site-packages: {result2.stdout.strip()}")

        result3 = subprocess.run(
            [str(self.pbs_python_exe), "-c", "import nuitka; print(nuitka.__file__)"],
            capture_output=True, text=True
        )
        print(f"  nuitka location: {result3.stdout.strip() or result3.stderr.strip()}")

    def pip_install_target(self, target_dir: Path, requirements_file: Path):
        cmd = self._pip_cmd_base() + ["--target", str(target_dir), "-r", str(requirements_file)]
        try:
            result = run_cmd(cmd, capture_output=True, text=True)
            if result.stdout:
                lines = result.stdout.strip().split("\n")
                for line in lines[-5:]:
                    print(f"  {line}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ pip install 失败:")
            if e.stdout:
                print(e.stdout[-500:] if len(e.stdout) > 500 else e.stdout)
            if e.stderr:
                print(e.stderr[-500:] if len(e.stderr) > 500 else e.stderr)
            raise

    def run(self):
        self._print_header()

        self.dist_dir.mkdir(parents=True, exist_ok=True)

        if self.build_type == "app-only":
            for f in self.dist_dir.glob("*.tar.gz"):
                if f.name != f"{self.target_component}-arm32.tar.gz":
                    f.unlink()
            for f in self.dist_dir.glob("checksums.txt"):
                f.unlink()
        elif self.build_type == "python-only":
            for f in self.dist_dir.glob("*-arm32.tar.gz"):
                if f.name != "shared-python-base-arm32.tar.gz":
                    f.unlink()
            for f in self.dist_dir.glob("checksums.txt"):
                f.unlink()

        need_package_python = self.build_type in ("full", "python-only")

        pbs_dir = self._download_pbs_python()

        self._setup_shared_python(pbs_dir)
        self._write_version(need_package_python)

        if self.enable_nuitka:
            print("\n━━━ 安装 Nuitka ━━━")
            self.pip_install("cffi", "nuitka", "ordered-set", "zstandard", verify_nuitka=True)

        if self.build_type in ("full", "app-only"):
            self.build_apps()

        if need_package_python:
            self._package_clean_shared_python(pbs_dir)

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
        if self.build_type == "app-only":
            print(f"  目标组件  : '{self.target_component}'")
        print("=" * 55)

    def _download_pbs_python(self) -> Path:
        print("\n━━━ 下载 PBS Python ━━━")
        url = PBS_URL_TEMPLATE.format(
            pbs_release=self.pbs_release,
            pbs_python=self.pbs_python,
        )
        tar_path = Path("/tmp/pbs.tar.gz")

        print(f"  下载: {url}")
        run_cmd(["wget", "-q", url, "-O", str(tar_path)])
        run_cmd(["tar", "xzf", str(tar_path), "-C", "/tmp/"])

        pbs_dir = Path("/tmp/python")
        if not pbs_dir.is_dir():
            candidates = sorted(Path("/tmp").glob("cpython*"))
            pbs_dir = candidates[0] if candidates else None

        if not pbs_dir or not pbs_dir.is_dir():
            print("❌ 无法找到解压后的 Python 目录")
            sys.exit(1)

        print(f"  ✅ PBS Python 已下载: {pbs_dir}")
        return pbs_dir

    def _setup_shared_python(self, pbs_dir: Path):
        print("\n━━━ 设置 shared-python 环境 ━━━")
        if self.shared_python_dir.exists():
            shutil.rmtree(self.shared_python_dir)
        self.shared_python_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(["cp", "-a", f"{pbs_dir}/.", str(self.shared_python_dir)])

        if not self.pbs_python_exe.exists():
            print(f"❌ python3 不可执行: {self.pbs_python_exe}")
            sys.exit(1)

        print(f"  ✅ shared-python 已就绪: {self.pbs_python_exe}")

    def _strip_stdlib(self):
        print("  裁剪 stdlib...")
        pylib_dirs = list(self.shared_python_dir.glob("lib/python3.*"))
        if not pylib_dirs:
            print("  ⚠ 未找到 lib/python3.* 目录")
            return

        pylib = pylib_dirs[0]

        for mod in STRIPPED_STDLIB_MODULES:
            mod_path = pylib / mod
            if mod_path.exists():
                shutil.rmtree(mod_path, ignore_errors=True)

        for pattern in ["__pycache__", "test", "tests"]:
            for d in pylib.rglob(pattern):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

        include_dir = self.shared_python_dir / "include"
        if include_dir.exists():
            shutil.rmtree(include_dir)

        print("  ✅ stdlib 已裁剪")

    def _write_version(self, for_package: bool = False):
        if for_package and self.build_type == "python-only" and self.target_version:
            py_ver = self.target_version
        else:
            py_ver = f"{self.pbs_python}-{self.pbs_release}"

        (self.shared_python_dir / "VERSION").write_text(py_ver, encoding="utf-8")
        print(f"  版本: {py_ver}")

    def _package_clean_shared_python(self, pbs_dir: Path):
        print("\n━━━ 打包 shared-python ━━━")

        if self.shared_python_dir.exists():
            shutil.rmtree(self.shared_python_dir)

        self.shared_python_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(["cp", "-a", f"{pbs_dir}/.", str(self.shared_python_dir)])

        py_ver = f"{self.pbs_python}-{self.pbs_release}"
        if self.build_type == "python-only" and self.target_version:
            py_ver = self.target_version
        (self.shared_python_dir / "VERSION").write_text(py_ver, encoding="utf-8")

        if self.strip_stdlib:
            self._strip_stdlib()

        tar_name = "shared-python-base-arm32.tar.gz"
        tar_path = self.dist_dir / tar_name

        print(f"  打包: {tar_name}")
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(self.shared_python_dir), arcname="shared-python")

        print(f"  ✅ shared-python ({py_ver}) → dist/{tar_name}")

    def build_apps(self):
        if self.build_type == "full":
            apps_dir = self.repo_root / "apps"
            app_names = [
                d.name for d in sorted(apps_dir.iterdir())
                if d.is_dir()
            ]
        elif self.build_type == "app-only":
            if not self.target_component:
                print("❌ 错误: app-only 模式需要指定 --target-component")
                sys.exit(1)
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

        for app_name in app_names:
            self.build_app(app_name)

    def build_app(self, app_name: str):
        print(f"\n{'=' * 55}")
        print(f"  构建: {app_name}")
        print(f"{'=' * 55}")

        app_dir = self.repo_root / "apps" / app_name
        build_dir = self.repo_root / "build" / app_name

        if build_dir.exists():
            shutil.rmtree(build_dir)
        (build_dir / "usr" / "app").mkdir(parents=True)
        (build_dir / "usr" / "app_packages").mkdir(parents=True)

        app_src = app_dir / "src"
        if app_src.is_dir():
            self._copy_tree(app_src, build_dir / "usr" / "app")
        else:
            for py_file in app_dir.glob("*.py"):
                shutil.copy2(str(py_file), str(build_dir / "usr" / "app"))

        req_file = app_dir / "requirements.txt"
        if req_file.exists():
            print("  安装依赖...")
            self.pip_install_target(build_dir / "usr" / "app_packages", req_file)

        module_name = self._detect_module_name(build_dir, app_name)
        app_version = self._resolve_version(app_dir, module_name, app_name)

        (build_dir / "VERSION").write_text(app_version, encoding="utf-8")
        print(f"  模块: {module_name}, 版本: {app_version}")

        if self.enable_nuitka:
            self._run_nuitka(build_dir)

        self._generate_run_sh(build_dir, module_name, app_version)
        self._cleanup_build(build_dir)

        tar_path = self.dist_dir / f"{app_name}-arm32.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(build_dir), arcname=app_name)

        print(f"  ✅ {app_name} ({app_version}) → dist/{tar_path.name}")

    def _detect_module_name(self, build_dir: Path, app_name: str) -> str:
        app_dir = build_dir / "usr" / "app"

        if (app_dir / app_name / "__main__.py").exists():
            return app_name

        for main_file in sorted(app_dir.iterdir()):
            if main_file.is_dir() and (main_file / "__main__.py").exists():
                return main_file.name

        return app_name

    def _resolve_version(self, app_dir: Path, module_name: str, app_name: str) -> str:
        if self.build_type == "app-only" and self.target_version:
            return self.target_version

        init_file = app_dir / "src" / module_name / "__init__.py"
        version = extract_version_from_init(init_file)
        return version or "0.0.0"

    def _run_nuitka(self, build_dir: Path):
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
        run_sh = build_dir / "run.sh"
        content = f"""\
#!/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "${{BASH_SOURCE[0]}}")")"
PYTHON="/opt/shared-python/bin/python3"
if [ ! -x "$PYTHON" ]; then
  echo "错误: 未找到共享 Python" >&2; exit 1
fi
export PYTHONEXECUTABLE="$PYTHON"
export PYTHONHOME="/opt/shared-python"
export PYTHONPATH="${{SCRIPT_DIR}}/usr/app:${{SCRIPT_DIR}}/usr/app_packages"
export LD_LIBRARY_PATH="/opt/shared-python/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
export APP_VERSION="{app_version}"
exec -a "{module_name}" "$PYTHON" -s -m {module_name} "$@"
"""
        run_sh.write_text(content, encoding="utf-8")
        run_sh.chmod(0o755)
        print(f"  ✅ 启动脚本: run.sh")

    def _cleanup_build(self, build_dir: Path):
        app_packages = build_dir / "usr" / "app_packages"
        for pattern in ["*.dist-info", "*.egg-info", "tests", "test"]:
            for d in app_packages.rglob(pattern):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

        for d in build_dir.rglob("__pycache__"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
        for f in build_dir.rglob("*.pyc"):
            f.unlink(missing_ok=True)
        for f in build_dir.rglob("*.pyo"):
            f.unlink(missing_ok=True)

    def _copy_tree(self, src: Path, dst: Path):
        if not dst.exists():
            dst.mkdir(parents=True)
        for item in src.iterdir():
            dest_item = dst / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(dest_item), symlinks=True)
            else:
                shutil.copy2(str(item), str(dest_item))

    def _fix_dist_permissions(self):
        if not self.dist_dir.exists():
            return
        for f in self.dist_dir.rglob("*"):
            if f.is_dir():
                f.chmod(0o755)
            elif f.is_file():
                f.chmod(0o644)
        install_sh = self.dist_dir / "install.sh"
        if install_sh.exists():
            install_sh.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(
        description="ARM32 构建脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--build-type", required=True,
                        choices=["full", "python-only", "app-only"])
    parser.add_argument("--target-component", default="")
    parser.add_argument("--target-version", default="")
    parser.add_argument("--python-version", default="3.11")
    parser.add_argument("--pbs-release", default=PBS_RELEASE)
    parser.add_argument("--enable-nuitka", default="true")
    parser.add_argument("--strip-stdlib", default="true")
    parser.add_argument("--repo-root", default=".")

    args = parser.parse_args()
    builder = ARM32Builder(args)
    builder.run()


if __name__ == "__main__":
    main()
