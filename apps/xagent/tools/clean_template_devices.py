#!/usr/bin/env python3
"""清理数据库中的模板设备"""

import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\77127\AppData\Local\adveco\XAgent\data\xagent.db")

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=== 清理模板设备 ===")

template_keywords = ['example', 'template', 'sample', 'demo']
cursor.execute("SELECT asset FROM device_registry WHERE status = 'active'")
all_assets = [row[0] for row in cursor.fetchall()]

template_devices = [asset for asset in all_assets if any(kw in asset.lower() for kw in template_keywords)]

if not template_devices:
    print("没有发现模板设备，无需清理")
    conn.close()
    exit(0)

print(f"发现 {len(template_devices)} 个模板设备:")
for asset in template_devices:
    print(f"  - {asset}")

confirm = input("\n确认删除这些模板设备吗？(yes/no): ")

if confirm.lower() == 'yes':
    placeholders = ','.join(['?' for _ in template_devices])
    
    cursor.execute(
        f"UPDATE device_registry SET status = 'deleted' WHERE asset IN ({placeholders})",
        template_devices
    )
    
    cursor.execute(
        f"UPDATE point_registry SET status = 'deleted' WHERE asset IN ({placeholders})",
        template_devices
    )
    
    conn.commit()
    
    print(f"\n✅ 已删除 {len(template_devices)} 个模板设备")
    print("重启应用后，这些设备将不会加载")
else:
    print("\n❌ 取消删除")

conn.close()
