"""Rule Engine Persistence Manager

负责规则引擎配置的持久化存储和恢复。
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class RuleRecord:
    """规则记录"""
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    plugin_config: Dict[str, Any] = field(default_factory=dict)
    data_subscriptions: Optional[List[Dict[str, Any]]] = None
    notification_config: Optional[Dict[str, Any]] = None
    pipeline_id: Optional[str] = None
    channel_ids: List[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class ChannelRecord:
    """渠道记录"""
    id: str
    plugin_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class PipelineRecord:
    """管道记录"""
    id: str
    filters: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


class RulePersistenceManager:
    """规则持久化管理器
    
    负责规则、渠道、管道的持久化存储和恢复。
    """
    
    def __init__(self, db_path: str = "./data/xagent.db"):
        """初始化持久化管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化数据库表"""
        if self._initialized:
            return
        
        self._db = await aiosqlite.connect(self._db_path)
        
        await self._db.execute("PRAGMA journal_mode=WAL")
        
        await self._create_tables()
        
        self._initialized = True
        logger.info(f"RulePersistenceManager initialized: {self._db_path}")
    
    async def _create_tables(self) -> None:
        """创建数据库表"""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS rule_registry (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                plugin_config TEXT NOT NULL,
                data_subscriptions TEXT,
                notification_config TEXT,
                pipeline_id TEXT,
                channel_ids TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS channel_registry (
                id TEXT PRIMARY KEY,
                plugin_name TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS pipeline_registry (
                id TEXT PRIMARY KEY,
                filters TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_rule_enabled ON rule_registry(enabled);
            CREATE INDEX IF NOT EXISTS idx_rule_pipeline ON rule_registry(pipeline_id);
        """)
        
        await self._db.commit()
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False
    
    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        return time.time()
    
    # ==================== Rule Operations ====================
    
    async def save_rule(self, rule: RuleRecord) -> bool:
        """保存规则
        
        Args:
            rule: 规则记录
            
        Returns:
            是否保存成功
        """
        if not self._db:
            return False
        
        try:
            now = self._get_timestamp()
            rule.created_at = rule.created_at or now
            rule.updated_at = now
            
            await self._db.execute("""
                INSERT OR REPLACE INTO rule_registry 
                (id, name, description, enabled, plugin_config, data_subscriptions, 
                 notification_config, pipeline_id, channel_ids, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.id,
                rule.name,
                rule.description,
                1 if rule.enabled else 0,
                json.dumps(rule.plugin_config),
                json.dumps(rule.data_subscriptions) if rule.data_subscriptions else None,
                json.dumps(rule.notification_config) if rule.notification_config else None,
                rule.pipeline_id,
                json.dumps(rule.channel_ids),
                rule.created_at,
                rule.updated_at,
            ))
            
            await self._db.commit()
            logger.debug(f"Rule saved: {rule.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save rule {rule.id}: {e}")
            return False
    
    async def load_rule(self, rule_id: str) -> Optional[RuleRecord]:
        """加载规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            规则记录，不存在返回 None
        """
        if not self._db:
            return None
        
        try:
            cursor = await self._db.execute(
                "SELECT * FROM rule_registry WHERE id = ?", (rule_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return RuleRecord(
                id=row[0],
                name=row[1],
                description=row[2],
                enabled=bool(row[3]),
                plugin_config=json.loads(row[4]),
                data_subscriptions=json.loads(row[5]) if row[5] else None,
                notification_config=json.loads(row[6]) if row[6] else None,
                pipeline_id=row[7],
                channel_ids=json.loads(row[8]) if row[8] else [],
                created_at=row[9],
                updated_at=row[10],
            )
            
        except Exception as e:
            logger.error(f"Failed to load rule {rule_id}: {e}")
            return None
    
    async def load_all_rules(self) -> Dict[str, RuleRecord]:
        """加载所有规则
        
        Returns:
            规则字典 {rule_id: RuleRecord}
        """
        if not self._db:
            return {}
        
        rules = {}
        try:
            cursor = await self._db.execute(
                "SELECT * FROM rule_registry WHERE enabled = 1"
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                rule = RuleRecord(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    enabled=bool(row[3]),
                    plugin_config=json.loads(row[4]),
                    data_subscriptions=json.loads(row[5]) if row[5] else None,
                    notification_config=json.loads(row[6]) if row[6] else None,
                    pipeline_id=row[7],
                    channel_ids=json.loads(row[8]) if row[8] else [],
                    created_at=row[9],
                    updated_at=row[10],
                )
                rules[rule.id] = rule
            
            logger.info(f"Loaded {len(rules)} rules from database")
            return rules
            
        except Exception as e:
            logger.error(f"Failed to load all rules: {e}")
            return {}
    
    async def delete_rule(self, rule_id: str) -> bool:
        """删除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否删除成功
        """
        if not self._db:
            return False
        
        try:
            await self._db.execute(
                "DELETE FROM rule_registry WHERE id = ?", (rule_id,)
            )
            await self._db.commit()
            logger.debug(f"Rule deleted: {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete rule {rule_id}: {e}")
            return False
    
    # ==================== Channel Operations ====================
    
    async def save_channel(self, channel: ChannelRecord) -> bool:
        """保存渠道
        
        Args:
            channel: 渠道记录
            
        Returns:
            是否保存成功
        """
        if not self._db:
            return False
        
        try:
            now = self._get_timestamp()
            channel.created_at = channel.created_at or now
            channel.updated_at = now
            
            await self._db.execute("""
                INSERT OR REPLACE INTO channel_registry 
                (id, plugin_name, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                channel.id,
                channel.plugin_name,
                json.dumps(channel.config),
                channel.created_at,
                channel.updated_at,
            ))
            
            await self._db.commit()
            logger.debug(f"Channel saved: {channel.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save channel {channel.id}: {e}")
            return False
    
    async def load_all_channels(self) -> Dict[str, ChannelRecord]:
        """加载所有渠道
        
        Returns:
            渠道字典 {channel_id: ChannelRecord}
        """
        if not self._db:
            return {}
        
        channels = {}
        try:
            cursor = await self._db.execute("SELECT * FROM channel_registry")
            rows = await cursor.fetchall()
            
            for row in rows:
                channel = ChannelRecord(
                    id=row[0],
                    plugin_name=row[1],
                    config=json.loads(row[2]),
                    created_at=row[3],
                    updated_at=row[4],
                )
                channels[channel.id] = channel
            
            logger.info(f"Loaded {len(channels)} channels from database")
            return channels
            
        except Exception as e:
            logger.error(f"Failed to load all channels: {e}")
            return {}
    
    async def delete_channel(self, channel_id: str) -> bool:
        """删除渠道
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            是否删除成功
        """
        if not self._db:
            return False
        
        try:
            await self._db.execute(
                "DELETE FROM channel_registry WHERE id = ?", (channel_id,)
            )
            await self._db.commit()
            logger.debug(f"Channel deleted: {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete channel {channel_id}: {e}")
            return False
    
    # ==================== Pipeline Operations ====================
    
    async def save_pipeline(self, pipeline: PipelineRecord) -> bool:
        """保存管道
        
        Args:
            pipeline: 管道记录
            
        Returns:
            是否保存成功
        """
        if not self._db:
            return False
        
        try:
            now = self._get_timestamp()
            pipeline.created_at = pipeline.created_at or now
            pipeline.updated_at = now
            
            await self._db.execute("""
                INSERT OR REPLACE INTO pipeline_registry 
                (id, filters, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pipeline.id,
                json.dumps(pipeline.filters),
                json.dumps(pipeline.config),
                pipeline.created_at,
                pipeline.updated_at,
            ))
            
            await self._db.commit()
            logger.debug(f"Pipeline saved: {pipeline.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save pipeline {pipeline.id}: {e}")
            return False
    
    async def load_all_pipelines(self) -> Dict[str, PipelineRecord]:
        """加载所有管道
        
        Returns:
            管道字典 {pipeline_id: PipelineRecord}
        """
        if not self._db:
            return {}
        
        pipelines = {}
        try:
            cursor = await self._db.execute("SELECT * FROM pipeline_registry")
            rows = await cursor.fetchall()
            
            for row in rows:
                pipeline = PipelineRecord(
                    id=row[0],
                    filters=json.loads(row[1]),
                    config=json.loads(row[2]),
                    created_at=row[3],
                    updated_at=row[4],
                )
                pipelines[pipeline.id] = pipeline
            
            logger.info(f"Loaded {len(pipelines)} pipelines from database")
            return pipelines
            
        except Exception as e:
            logger.error(f"Failed to load all pipelines: {e}")
            return {}
    
    async def delete_pipeline(self, pipeline_id: str) -> bool:
        """删除管道
        
        Args:
            pipeline_id: 管道ID
            
        Returns:
            是否删除成功
        """
        if not self._db:
            return False
        
        try:
            await self._db.execute(
                "DELETE FROM pipeline_registry WHERE id = ?", (pipeline_id,)
            )
            await self._db.commit()
            logger.debug(f"Pipeline deleted: {pipeline_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete pipeline {pipeline_id}: {e}")
            return False
