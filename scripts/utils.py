import hashlib
import re
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, **kwargs):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def parse_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


def extract_version_from_init(init_file: Path) -> str:
    if not init_file.exists():
        return "0.0.0"
    content = init_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def extract_version_from_pyproject(pyproject_file) -> str:
    pyproject_file = Path(pyproject_file)
    if not pyproject_file.exists():
        return "0.0.0"
    content = pyproject_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def set_version_in_pyproject(pyproject_file, version: str) -> None:
    pyproject_file = Path(pyproject_file)
    content = pyproject_file.read_text(encoding="utf-8")
    content = re.sub(r'^version\s*=\s*["\'][^"\']*["\']', f'version = "{version}"', content, count=1, flags=re.MULTILINE)
    pyproject_file.write_text(content, encoding="utf-8")


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
