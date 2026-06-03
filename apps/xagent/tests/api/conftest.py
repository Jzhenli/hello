"""pytest configuration for API tests"""

import pytest
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))


def pytest_configure(config):
    """Configure pytest with asyncio mode"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
