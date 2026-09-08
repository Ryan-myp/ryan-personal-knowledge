"""
persistence/__init__.py - 持久化层

使用 SQLite 持久化：
- Sessions（对话会话）
- Tool Calls（工具调用记录）
- Campaign State（Campaign 资源状态，跨会话恢复）
"""

from .interfaces import PersistenceBackend
from .models import CampaignRecord, OutboxEvent, TaskRecord, ToolCallRecord
from .store import AdAgentStore
from .factory import create_persistence_store
from .mysql_store import MySQLStore
from .session_manager import SessionManager

__all__ = [
    "AdAgentStore", "MySQLStore", "create_persistence_store", "CampaignRecord", "OutboxEvent", "TaskRecord", "ToolCallRecord", "PersistenceBackend",
    "SessionManager",
]
