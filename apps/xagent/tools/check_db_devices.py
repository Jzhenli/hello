#!/usr/bin/env python3
"""检查数据库中的设备"""

import sqlite3
import os
from pathlib import Path

db_path = Path(r"C:\Users\77127\AppData\Local\adveco\XAgent\data\xagent.db")

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=== 数据库中的设备 ===")
cursor.execute("SELECT asset, plugin_name, enabled, status FROM device_registry WHERE status = 'active'")
devices = cursor.fetchall()

if devices:
    print(f"找到 {len(devices)} 个活跃设备:")
    for asset, plugin_name, enabled, status in devices:
        print(f"  - {asset} (插件: {plugin_name}, 启用: {enabled}, 状态: {status})")
else:
    print("数据库中没有活跃设备")

print("\n=== 模板设备检查 ===")
template_keywords = ['example', 'template', 'sample', 'demo']
cursor.execute("SELECT asset FROM device_registry WHERE status = 'active'")
all_assets = [row[0] for row in cursor.fetchall()]

template_devices = [asset for asset in all_assets if any(kw in asset.lower() for kw in template_keywords)]

if template_devices:
    print(f"发现 {len(template_devices)} 个模板设备:")
    for asset in template_devices:
        print(f"  - {asset}")
    print("\n建议删除这些模板设备:")
    print("  python -c \"import sqlite3; conn = sqlite3.connect(r'C:\\Users\\77127\\AppData\\Local\\adveco\\XAgent\\data\\xagent.db'); conn.execute('UPDATE device_registry SET status=\\'deleted\\' WHERE asset IN (\\'' + '\\',\\''.join(template_devices) + '\\')'); conn.commit()\"")
else:
    print("没有发现模板设备")

conn.close()
