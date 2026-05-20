#!/usr/bin/env python3
"""检查配置加载方式"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from xagent.xcore.services.initialization import DeviceLoader

print("当前使用的DeviceLoader:")
print(f"  模块: {DeviceLoader.__module__}")
print(f"  文件: {DeviceLoader.__module__.__file__ if hasattr(DeviceLoader.__module__, '__file__') else 'N/A'}")
print()

if 'device_loader_db' in DeviceLoader.__module__:
    print("✅ 使用数据库为中心的配置管理")
    print("  - 数据库是唯一数据源")
    print("  - YAML文件仅用于备份和迁移")
else:
    print("❌ 使用YAML文件为中心的配置管理")
    print("  - YAML文件是数据源")
    print("  - 需要切换到新的加载方式")
