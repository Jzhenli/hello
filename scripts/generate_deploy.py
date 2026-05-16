#!/usr/bin/env python3
"""
部署包组装脚本

负责:
  1. 复制 install.sh 到 dist/
  2. 生成 checksums.txt (含 install.sh)
  3. 打印部署包摘要

用法:
    python3 scripts/generate_deploy.py dist/
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import sha256_file, format_size


def detect_package_type(dist_dir: Path) -> tuple[str, int]:
    has_python = (dist_dir / "shared-python-base-arm32.tar.gz").exists()
    app_tars = [
        t for t in dist_dir.glob("*-arm32.tar.gz")
        if t.name != "shared-python-base-arm32.tar.gz"
    ]
    app_count = len(app_tars)

    if has_python and app_count > 0:
        return "full", app_count
    elif has_python:
        return "python-only", 0
    elif app_count > 0:
        return "app-only", app_count
    else:
        return "empty", 0


PACKAGE_TYPE_LABELS = {
    "full": "全量包 (Python + {} 个应用)",
    "python-only": "Python 升级包",
    "app-only": "应用增量升级包 ({} 个应用)",
    "empty": "空包",
}


def main():
    if len(sys.argv) < 2:
        print("用法: python3 generate_deploy.py <dist_dir>")
        sys.exit(1)

    dist_dir = Path(sys.argv[1])
    if not dist_dir.is_dir():
        print(f"❌ 目录不存在: {dist_dir}")
        sys.exit(1)

    scripts_dir = Path(__file__).parent

    install_sh_src = scripts_dir / "install.sh"
    install_sh_dst = dist_dir / "install.sh"
    if install_sh_src.exists():
        shutil.copy2(str(install_sh_src), str(install_sh_dst))
        install_sh_dst.chmod(0o755)
        print(f"✅ 已复制: install.sh")
    else:
        print(f"⚠ 未找到: {install_sh_src}")

    checksum_files = sorted(dist_dir.glob("*.tar.gz"))
    install_sh = dist_dir / "install.sh"
    if install_sh.exists():
        checksum_files.append(install_sh)

    if checksum_files:
        checksums_file = dist_dir / "checksums.txt"
        with open(checksums_file, "w", encoding="utf-8") as f:
            for file_path in checksum_files:
                checksum = sha256_file(file_path)
                f.write(f"{checksum}  {file_path.name}\n")
        print(f"✅ 已生成: checksums.txt ({len(checksum_files)} 个文件)")
    else:
        print("⚠ 未找到需要校验的文件")

    pkg_type, app_count = detect_package_type(dist_dir)
    label_template = PACKAGE_TYPE_LABELS.get(pkg_type, "未知")
    label = label_template.format(app_count) if "{}" in label_template else label_template

    print()
    print("=== 部署包内容 ===")
    for f in sorted(dist_dir.iterdir()):
        if f.is_file():
            print(f"  {f.name}: {format_size(f.stat().st_size)}")

    print()
    print(f"📦 包类型: {label}")


if __name__ == "__main__":
    main()
