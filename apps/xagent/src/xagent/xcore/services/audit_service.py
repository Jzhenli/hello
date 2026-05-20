"""审计服务 - 配置变更审计日志

此模块提供审计日志功能，包括：
- 记录所有配置变更操作
- 查询审计日志
- 审计统计分析
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
import aiosqlite

logger = logging.getLogger(__name__)


class AuditService:
    """审计服务 - 记录和查询配置变更"""
    
    def __init__(self, db: aiosqlite.Connection):
        self._db = db
    
    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """记录审计日志
        
        Args:
            action: 操作类型 ('create', 'update', 'delete', 'reload', 'import', 'export')
            entity_type: 实体类型 ('device', 'point', 'config')
            entity_id: 实体ID
            user: 操作用户
            ip_address: 操作IP地址
            details: 详细信息
            old_value: 旧值
            new_value: 新值
            success: 是否成功
            error_message: 错误信息
        """
        try:
            await self._db.execute(
                """
                INSERT INTO audit_logs (
                    action, entity_type, entity_id, user, ip_address,
                    details, old_value, new_value, timestamp, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action, entity_type, entity_id, user, ip_address,
                    json.dumps(details) if details else None,
                    json.dumps(old_value) if old_value else None,
                    json.dumps(new_value) if new_value else None,
                    time.time(), success, error_message
                )
            )
            await self._db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
    
    async def get_audit_logs(
        self,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """查询审计日志
        
        Args:
            action: 按操作类型过滤
            entity_type: 按实体类型过滤
            entity_id: 按实体ID过滤
            user: 按用户过滤
            start_time: 开始时间
            end_time: 结束时间
            success: 按成功状态过滤
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            审计日志列表
        """
        conditions = []
        params = []
        
        if action:
            conditions.append("action = ?")
            params.append(action)
        
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        
        if user:
            conditions.append("user = ?")
            params.append(user)
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if success is not None:
            conditions.append("success = ?")
            params.append(success)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])
        
        query = f"""
            SELECT id, action, entity_type, entity_id, user, ip_address,
                   details, old_value, new_value, timestamp, success, error_message
            FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        
        logs = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                logs.append({
                    'id': row[0],
                    'action': row[1],
                    'entity_type': row[2],
                    'entity_id': row[3],
                    'user': row[4],
                    'ip_address': row[5],
                    'details': json.loads(row[6]) if row[6] else None,
                    'old_value': json.loads(row[7]) if row[7] else None,
                    'new_value': json.loads(row[8]) if row[8] else None,
                    'timestamp': row[9],
                    'success': bool(row[10]),
                    'error_message': row[11]
                })
        
        return logs
    
    async def get_audit_stats(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """获取审计统计信息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            统计信息
        """
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        stats = {
            'total_actions': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'actions_by_type': {},
            'actions_by_entity_type': {},
            'actions_by_user': {}
        }
        
        async with self._db.execute(
            f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}",
            params
        ) as cursor:
            row = await cursor.fetchone()
            stats['total_actions'] = row[0] if row else 0
        
        async with self._db.execute(
            f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause} AND success = 1",
            params
        ) as cursor:
            row = await cursor.fetchone()
            stats['successful_actions'] = row[0] if row else 0
        
        async with self._db.execute(
            f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause} AND success = 0",
            params
        ) as cursor:
            row = await cursor.fetchone()
            stats['failed_actions'] = row[0] if row else 0
        
        async with self._db.execute(
            f"SELECT action, COUNT(*) FROM audit_logs WHERE {where_clause} GROUP BY action",
            params
        ) as cursor:
            async for row in cursor:
                stats['actions_by_type'][row[0]] = row[1]
        
        async with self._db.execute(
            f"SELECT entity_type, COUNT(*) FROM audit_logs WHERE {where_clause} GROUP BY entity_type",
            params
        ) as cursor:
            async for row in cursor:
                stats['actions_by_entity_type'][row[0]] = row[1]
        
        async with self._db.execute(
            f"SELECT user, COUNT(*) FROM audit_logs WHERE {where_clause} AND user IS NOT NULL GROUP BY user",
            params
        ) as cursor:
            async for row in cursor:
                stats['actions_by_user'][row[0]] = row[1]
        
        return stats
    
    async def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取实体的变更历史
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            limit: 返回数量限制
            
        Returns:
            变更历史列表
        """
        return await self.get_audit_logs(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit
        )
    
    async def cleanup_old_logs(
        self,
        before_timestamp: float,
        batch_size: int = 10000
    ) -> int:
        """清理旧的审计日志
        
        Args:
            before_timestamp: 清理此时间之前的日志
            batch_size: 批量删除大小
            
        Returns:
            删除的记录数
        """
        total_deleted = 0
        
        while True:
            async with self._db.cursor() as cursor:
                await cursor.execute(
                    """
                    DELETE FROM audit_logs 
                    WHERE id IN (
                        SELECT id FROM audit_logs 
                        WHERE timestamp < ? 
                        LIMIT ?
                    )
                    """,
                    (before_timestamp, batch_size)
                )
                deleted = cursor.rowcount
                await self._db.commit()
                total_deleted += deleted
                
                if deleted < batch_size:
                    break
                
                await asyncio.sleep(0.1)
        
        if total_deleted > 0:
            logger.info(f"Cleaned up {total_deleted} old audit logs")
        
        return total_deleted


import asyncio
