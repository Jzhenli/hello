"""用户权限服务 - RBAC权限矩阵管理

提供用户、角色、权限的CRUD操作和权限矩阵管理功能。
"""

import json
import logging
import time
import hashlib
import secrets
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

PERMISSION_RESOURCES = [
    "dashboard",
    "devices",
    "rules",
    "alerts",
    "scada",
    "settings",
    "users",
    "logs",
    "backup",
    "control",
]

PERMISSION_ACTIONS = ["view", "create", "update", "delete"]

DEFAULT_ROLES = {
    "admin": {
        "display_name": "管理员",
        "description": "系统管理员，拥有所有权限",
        "permissions": {r: {a: True for a in PERMISSION_ACTIONS} for r in PERMISSION_RESOURCES},
    },
    "operator": {
        "display_name": "操作员",
        "description": "操作员，可查看和操作设备与规则",
        "permissions": {
            "dashboard": {"view": True, "create": False, "update": False, "delete": False},
            "devices": {"view": True, "create": True, "update": True, "delete": False},
            "rules": {"view": True, "create": True, "update": True, "delete": False},
            "alerts": {"view": True, "create": True, "update": True, "delete": False},
            "scada": {"view": True, "create": True, "update": True, "delete": False},
            "settings": {"view": True, "create": False, "update": False, "delete": False},
            "users": {"view": False, "create": False, "update": False, "delete": False},
            "logs": {"view": True, "create": False, "update": False, "delete": False},
            "backup": {"view": True, "create": False, "update": False, "delete": False},
            "control": {"view": True, "create": True, "update": True, "delete": False},
        },
    },
    "viewer": {
        "display_name": "只读用户",
        "description": "只读用户，仅可查看各模块数据",
        "permissions": {
            r: {"view": True, "create": False, "update": False, "delete": False}
            for r in PERMISSION_RESOURCES
        },
    },
}


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


class UserPermissionService:
    """用户权限服务"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        await self._seed_default_data()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def _create_tables(self) -> None:
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                permissions TEXT NOT NULL DEFAULT '{}',
                is_system BOOLEAN DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT,
                email TEXT,
                role_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                last_login REAL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (role_name) REFERENCES roles(name)
            )
            """
        )

        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role_name)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name)"
        )

        await self._db.commit()

    async def _seed_default_data(self) -> None:
        async with self._db.execute("SELECT COUNT(*) FROM roles") as cursor:
            row = await cursor.fetchone()
            if row and row[0] > 0:
                return

        now = time.time()
        for role_name, role_data in DEFAULT_ROLES.items():
            await self._db.execute(
                """
                INSERT INTO roles (name, display_name, description, permissions, is_system, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    role_name,
                    role_data["display_name"],
                    role_data["description"],
                    json.dumps(role_data["permissions"]),
                    now,
                    now,
                ),
            )

        hashed, salt = _hash_password("admin")
        await self._db.execute(
            """
            INSERT INTO users (username, password_hash, password_salt, display_name, role_name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            ("admin", hashed, salt, "系统管理员", "admin", now, now),
        )

        hashed_op, salt_op = _hash_password("operator")
        await self._db.execute(
            """
            INSERT INTO users (username, password_hash, password_salt, display_name, role_name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            ("operator", hashed_op, salt_op, "操作员", "operator", now, now),
        )

        await self._db.commit()
        logger.info("Default roles and users seeded")

    async def list_users(self) -> List[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT u.id, u.username, u.display_name, u.email, u.role_name,
                   r.display_name as role_display_name, u.status, u.last_login,
                   u.created_at, u.updated_at
            FROM users u LEFT JOIN roles r ON u.role_name = r.name
            ORDER BY u.id
            """
        ) as cursor:
            users = []
            async for row in cursor:
                users.append(
                    {
                        "id": row[0],
                        "username": row[1],
                        "display_name": row[2],
                        "email": row[3],
                        "role_name": row[4],
                        "role_display_name": row[5],
                        "status": row[6],
                        "last_login": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                    }
                )
            return users

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT u.id, u.username, u.display_name, u.email, u.role_name,
                   r.display_name as role_display_name, u.status, u.last_login,
                   u.created_at, u.updated_at
            FROM users u LEFT JOIN roles r ON u.role_name = r.name
            WHERE u.id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "display_name": row[2],
                "email": row[3],
                "role_name": row[4],
                "role_display_name": row[5],
                "status": row[6],
                "last_login": row[7],
                "created_at": row[8],
                "updated_at": row[9],
            }

    async def create_user(
        self,
        username: str,
        password: str,
        role_name: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with self._db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ) as cursor:
            if await cursor.fetchone():
                raise ValueError(f"用户名 '{username}' 已存在")

        async with self._db.execute(
            "SELECT name FROM roles WHERE name = ?", (role_name,)
        ) as cursor:
            if not await cursor.fetchone():
                raise ValueError(f"角色 '{role_name}' 不存在")

        hashed, salt = _hash_password(password)
        now = time.time()

        cursor = await self._db.execute(
            """
            INSERT INTO users (username, password_hash, password_salt, display_name, email, role_name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (username, hashed, salt, display_name or username, email, role_name, now, now),
        )
        await self._db.commit()

        return await self.get_user(cursor.lastrowid)

    async def update_user(
        self,
        user_id: int,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        role_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        user = await self.get_user(user_id)
        if user is None:
            return None

        if role_name is not None:
            async with self._db.execute(
                "SELECT name FROM roles WHERE name = ?", (role_name,)
            ) as cursor:
                if not await cursor.fetchone():
                    raise ValueError(f"角色 '{role_name}' 不存在")

        now = time.time()
        updates = []
        params = []

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if role_name is not None:
            updates.append("role_name = ?")
            params.append(role_name)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return user

        updates.append("updated_at = ?")
        params.append(now)
        params.append(user_id)

        await self._db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
        )
        await self._db.commit()

        return await self.get_user(user_id)

    async def delete_user(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if user is None:
            return False

        if user["username"] == "admin":
            raise ValueError("无法删除系统管理员账户")

        await self._db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await self._db.commit()
        return True

    async def change_password(self, user_id: int, new_password: str) -> bool:
        hashed, salt = _hash_password(new_password)
        now = time.time()
        await self._db.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, updated_at = ? WHERE id = ?",
            (hashed, salt, now, user_id),
        )
        await self._db.commit()
        return True

    async def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        async with self._db.execute(
            "SELECT id, password_hash, password_salt FROM users WHERE username = ? AND status = 'active'",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None

            user_id, stored_hash, salt = row[0], row[1], row[2]
            computed_hash, _ = _hash_password(password, salt)

            if computed_hash != stored_hash:
                return None

            now = time.time()
            await self._db.execute(
                "UPDATE users SET last_login = ? WHERE id = ?", (now, user_id)
            )
            await self._db.commit()

            return await self.get_user(user_id)

    async def list_roles(self) -> List[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT id, name, display_name, description, permissions, is_system, created_at, updated_at
            FROM roles ORDER BY id
            """
        ) as cursor:
            roles = []
            async for row in cursor:
                roles.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "display_name": row[2],
                        "description": row[3],
                        "permissions": json.loads(row[4]) if row[4] else {},
                        "is_system": bool(row[5]),
                        "created_at": row[6],
                        "updated_at": row[7],
                    }
                )
            return roles

    async def get_role(self, role_name: str) -> Optional[Dict[str, Any]]:
        async with self._db.execute(
            """
            SELECT id, name, display_name, description, permissions, is_system, created_at, updated_at
            FROM roles WHERE name = ?
            """,
            (role_name,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "display_name": row[2],
                "description": row[3],
                "permissions": json.loads(row[4]) if row[4] else {},
                "is_system": bool(row[5]),
                "created_at": row[6],
                "updated_at": row[7],
            }

    async def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permissions: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> Dict[str, Any]:
        async with self._db.execute(
            "SELECT name FROM roles WHERE name = ?", (name,)
        ) as cursor:
            if await cursor.fetchone():
                raise ValueError(f"角色 '{name}' 已存在")

        now = time.time()
        perms = permissions or {r: {a: False for a in PERMISSION_ACTIONS} for r in PERMISSION_RESOURCES}

        await self._db.execute(
            """
            INSERT INTO roles (name, display_name, description, permissions, is_system, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (name, display_name, description, json.dumps(perms), now, now),
        )
        await self._db.commit()

        return await self.get_role(name)

    async def update_role(
        self,
        role_name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> Optional[Dict[str, Any]]:
        role = await self.get_role(role_name)
        if role is None:
            return None

        now = time.time()
        updates = []
        params = []

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if permissions is not None:
            updates.append("permissions = ?")
            params.append(json.dumps(permissions))

        if not updates:
            return role

        updates.append("updated_at = ?")
        params.append(now)
        params.append(role_name)

        await self._db.execute(
            f"UPDATE roles SET {', '.join(updates)} WHERE name = ?", params
        )
        await self._db.commit()

        return await self.get_role(role_name)

    async def delete_role(self, role_name: str) -> bool:
        role = await self.get_role(role_name)
        if role is None:
            return False

        if role.get("is_system"):
            raise ValueError("无法删除系统内置角色")

        async with self._db.execute(
            "SELECT COUNT(*) FROM users WHERE role_name = ?", (role_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] > 0:
                raise ValueError(f"角色 '{role_name}' 下仍有 {row[0]} 个用户，无法删除")

        await self._db.execute("DELETE FROM roles WHERE name = ?", (role_name,))
        await self._db.commit()
        return True

    async def get_permission_matrix(self) -> Dict[str, Any]:
        roles = await self.list_roles()
        return {
            "resources": PERMISSION_RESOURCES,
            "actions": PERMISSION_ACTIONS,
            "roles": [
                {
                    "name": r["name"],
                    "display_name": r["display_name"],
                    "is_system": r["is_system"],
                    "permissions": r["permissions"],
                }
                for r in roles
            ],
        }

    async def update_permission_matrix(
        self, role_name: str, permissions: Dict[str, Dict[str, bool]]
    ) -> Optional[Dict[str, Any]]:
        return await self.update_role(role_name, permissions=permissions)

    async def check_permission(
        self, username: str, resource: str, action: str
    ) -> bool:
        async with self._db.execute(
            """
            SELECT r.permissions FROM users u
            JOIN roles r ON u.role_name = r.name
            WHERE u.username = ? AND u.status = 'active'
            """,
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return False

            permissions = json.loads(row[0]) if row[0] else {}
            return permissions.get(resource, {}).get(action, False)

    async def get_user_permissions(self, username: str) -> Dict[str, Dict[str, bool]]:
        async with self._db.execute(
            """
            SELECT r.permissions FROM users u
            JOIN roles r ON u.role_name = r.name
            WHERE u.username = ? AND u.status = 'active'
            """,
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return {}
            return json.loads(row[0]) if row[0] else {}
