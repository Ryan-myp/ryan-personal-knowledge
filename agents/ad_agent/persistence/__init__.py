"""
persistence/__init__.py - 持久化层

使用 SQLite 持久化：
- Sessions（对话会话）
- Tool Calls（工具调用记录）
- Campaign State（Campaign 资源状态，跨会话恢复）
"""

from .interfaces import PersistenceBackend
from .store import AdAgentStore, CampaignRecord, ToolCallRecord
from .session_manager import SessionManager

__all__ = [
    "AdAgentStore", "CampaignRecord", "ToolCallRecord", "PersistenceBackend",
    "SessionManager",
]
