"""配置模板管理

支持从模板创建设备配置，提高配置效率和一致性。
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import aiosqlite
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


@dataclass
class DeviceTemplate:
    """设备模板"""
    name: str
    description: Optional[str] = None
    plugin_name: str = ""
    plugin_config_template: Dict[str, Any] = field(default_factory=dict)
    point_templates: List[Dict[str, Any]] = field(default_factory=list)
    metadata_template: Dict[str, Any] = field(default_factory=dict)
    tags_template: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "plugin_name": self.plugin_name,
            "plugin_config_template": self.plugin_config_template,
            "point_templates": self.point_templates,
            "metadata_template": self.metadata_template,
            "tags_template": self.tags_template,
            "variables": self.variables,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceTemplate':
        return cls(**data)


class TemplateManager:
    """模板管理器"""
    
    def __init__(self, db: aiosqlite.Connection):
        self._db = db
        self._ensure_table()
    
    async def _ensure_table(self) -> None:
        """确保模板表存在"""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS device_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                plugin_name TEXT NOT NULL,
                plugin_config_template TEXT,
                point_templates TEXT,
                metadata_template TEXT,
                tags_template TEXT,
                variables TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        await self._db.commit()
    
    async def create_template(
        self,
        template: DeviceTemplate,
        user: Optional[str] = None
    ) -> DeviceTemplate:
        """创建模板
        
        Args:
            template: 模板配置
            user: 操作用户
            
        Returns:
            创建的模板
        """
        now = time.time()
        
        try:
            await self._db.execute(
                """
                INSERT INTO device_templates (
                    name, description, plugin_name, plugin_config_template,
                    point_templates, metadata_template, tags_template,
                    variables, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.name, template.description, template.plugin_name,
                    json.dumps(template.plugin_config_template),
                    json.dumps(template.point_templates),
                    json.dumps(template.metadata_template),
                    json.dumps(template.tags_template),
                    json.dumps(template.variables),
                    now, now
                )
            )
            await self._db.commit()
            
            template.created_at = now
            template.updated_at = now
            
            logger.info(f"Template created: {template.name} by {user}")
            return template
        
        except aiosqlite.IntegrityError:
            raise ValueError(f"Template '{template.name}' already exists")
    
    async def get_template(self, name: str) -> Optional[DeviceTemplate]:
        """获取模板
        
        Args:
            name: 模板名称
            
        Returns:
            模板配置，如果不存在返回None
        """
        async with self._db.execute(
            """
            SELECT name, description, plugin_name, plugin_config_template,
                   point_templates, metadata_template, tags_template,
                   variables, created_at, updated_at
            FROM device_templates
            WHERE name = ?
            """,
            (name,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            return DeviceTemplate(
                name=row[0],
                description=row[1],
                plugin_name=row[2],
                plugin_config_template=json.loads(row[3]) if row[3] else {},
                point_templates=json.loads(row[4]) if row[4] else [],
                metadata_template=json.loads(row[5]) if row[5] else {},
                tags_template=json.loads(row[6]) if row[6] else [],
                variables=json.loads(row[7]) if row[7] else {},
                created_at=row[8],
                updated_at=row[9]
            )
    
    async def list_templates(
        self,
        plugin_name: Optional[str] = None
    ) -> List[DeviceTemplate]:
        """列出模板
        
        Args:
            plugin_name: 按插件名称过滤
            
        Returns:
            模板列表
        """
        if plugin_name:
            query = """
                SELECT name, description, plugin_name, plugin_config_template,
                       point_templates, metadata_template, tags_template,
                       variables, created_at, updated_at
                FROM device_templates
                WHERE plugin_name = ?
                ORDER BY name
            """
            params = (plugin_name,)
        else:
            query = """
                SELECT name, description, plugin_name, plugin_config_template,
                       point_templates, metadata_template, tags_template,
                       variables, created_at, updated_at
                FROM device_templates
                ORDER BY name
            """
            params = ()
        
        templates = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                templates.append(DeviceTemplate(
                    name=row[0],
                    description=row[1],
                    plugin_name=row[2],
                    plugin_config_template=json.loads(row[3]) if row[3] else {},
                    point_templates=json.loads(row[4]) if row[4] else [],
                    metadata_template=json.loads(row[5]) if row[5] else {},
                    tags_template=json.loads(row[6]) if row[6] else [],
                    variables=json.loads(row[7]) if row[7] else {},
                    created_at=row[8],
                    updated_at=row[9]
                ))
        
        return templates
    
    async def update_template(
        self,
        name: str,
        updates: Dict[str, Any],
        user: Optional[str] = None
    ) -> DeviceTemplate:
        """更新模板
        
        Args:
            name: 模板名称
            updates: 更新内容
            user: 操作用户
            
        Returns:
            更新后的模板
        """
        template = await self.get_template(name)
        if not template:
            raise ValueError(f"Template '{name}' not found")
        
        now = time.time()
        
        for key, value in updates.items():
            if key == 'name':
                continue
            if hasattr(template, key):
                setattr(template, key, value)
        
        template.updated_at = now
        
        await self._db.execute(
            """
            UPDATE device_templates SET
                description = ?, plugin_config_template = ?,
                point_templates = ?, metadata_template = ?,
                tags_template = ?, variables = ?, updated_at = ?
            WHERE name = ?
            """,
            (
                template.description,
                json.dumps(template.plugin_config_template),
                json.dumps(template.point_templates),
                json.dumps(template.metadata_template),
                json.dumps(template.tags_template),
                json.dumps(template.variables),
                now, name
            )
        )
        await self._db.commit()
        
        logger.info(f"Template updated: {name} by {user}")
        return template
    
    async def delete_template(
        self,
        name: str,
        user: Optional[str] = None
    ) -> None:
        """删除模板
        
        Args:
            name: 模板名称
            user: 操作用户
        """
        template = await self.get_template(name)
        if not template:
            raise ValueError(f"Template '{name}' not found")
        
        await self._db.execute(
            "DELETE FROM device_templates WHERE name = ?",
            (name,)
        )
        await self._db.commit()
        
        logger.info(f"Template deleted: {name} by {user}")
    
    async def instantiate_template(
        self,
        template_name: str,
        variables: Dict[str, Any],
        asset: str
    ) -> Dict[str, Any]:
        """从模板实例化设备配置
        
        Args:
            template_name: 模板名称
            variables: 变量值
            asset: 设备资产标识
            
        Returns:
            设备配置
        """
        template = await self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        merged_vars = {**template.variables, **variables}
        
        plugin_config = self._substitute_variables(
            template.plugin_config_template,
            merged_vars
        )
        
        points = []
        for point_template in template.point_templates:
            point = self._substitute_variables(point_template, merged_vars)
            points.append(point)
        
        metadata = self._substitute_variables(
            template.metadata_template,
            merged_vars
        )
        
        tags = template.tags_template.copy()
        
        return {
            "asset": asset,
            "name": merged_vars.get("device_name", asset),
            "description": merged_vars.get("device_description", f"Created from template {template_name}"),
            "plugin_name": template.plugin_name,
            "plugin_config": plugin_config,
            "enabled": True,
            "status": "active",
            "metadata": metadata,
            "tags": tags,
            "points": points
        }
    
    def _substitute_variables(
        self,
        obj: Any,
        variables: Dict[str, Any]
    ) -> Any:
        """递归替换变量
        
        Args:
            obj: 对象
            variables: 变量字典
            
        Returns:
            替换后的对象
        """
        if isinstance(obj, str):
            for var_name, var_value in variables.items():
                placeholder = f"${{{var_name}}}"
                if placeholder in obj:
                    obj = obj.replace(placeholder, str(var_value))
            return obj
        elif isinstance(obj, dict):
            return {
                key: self._substitute_variables(value, variables)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [
                self._substitute_variables(item, variables)
                for item in obj
            ]
        else:
            return obj
    
    async def export_template(
        self,
        name: str,
        output_file: Path
    ) -> None:
        """导出模板到YAML文件
        
        Args:
            name: 模板名称
            output_file: 输出文件路径
        """
        template = await self.get_template(name)
        if not template:
            raise ValueError(f"Template '{name}' not found")
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                template.to_dict(),
                f,
                default_flow_style=False,
                allow_unicode=True
            )
        
        logger.info(f"Template exported: {name} to {output_file}")
    
    async def import_template(
        self,
        input_file: Path,
        user: Optional[str] = None
    ) -> DeviceTemplate:
        """从YAML文件导入模板
        
        Args:
            input_file: 输入文件路径
            user: 操作用户
            
        Returns:
            导入的模板
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            template_data = yaml.safe_load(f)
        
        template = DeviceTemplate.from_dict(template_data)
        
        return await self.create_template(template, user)
