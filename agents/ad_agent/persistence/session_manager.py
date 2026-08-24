"""
persistence/session_manager.py - 会话管理器

管理会话生命周期，与 AgentRuntime 的 SessionContext 配合。
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime

from .store import AdAgentStore, ToolCallRecord, CampaignRecord

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器 - 持久化层入口。
    
    职责：
    1. 管理 Session 的创建/读取/更新
    2. 持久化工具调用记录
    3. 维护 Campaign 状态（跨会话共享）
    4. 提供会话恢复能力
    """
    
    def __init__(self, store: AdAgentStore):
        self.store = store
    
    # ─── Session 管理 ──────────────────────────────────────────
    
    def create_session(self, session_id: str, user_id: str, 
                       account_id: str = None, metadata: dict = None) -> dict:
        """创建新会话"""
        self.store.create_session(session_id, user_id, account_id, metadata)
        return self.get_session(session_id)
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话信息"""
        return self.store.get_session(session_id)
    
    def list_sessions(self, user_id: str = None, limit: int = 50) -> list:
        """列出会话"""
        return self.store.list_sessions(user_id, limit)
    
    def restore_session(self, session_id: str) -> dict:
        """
        恢复会话上下文。
        
        返回包含：
        - session: 会话元信息
        - recent_tools: 最近工具调用记录（用于上下文重建）
        - campaigns: 该会话相关的 Campaign 状态
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        recent_tools = self.store.list_tool_calls(session_id, limit=20)
        campaigns = self._get_session_campaigns(session_id)
        
        return {
            'session': session,
            'recent_tools': recent_tools,
            'campaigns': campaigns,
        }
    
    # ─── Tool Call 持久化 ──────────────────────────────────────
    
    def record_tool_call(self, session_id: str, turn_id: str, record: ToolCallRecord) -> None:
        """持久化工具调用记录"""
        record.session_id = session_id
        record.turn_id = turn_id
        self.store.record_tool_call(record)
        logger.debug(f"Tool call recorded: {record.tool_name} on session={session_id}")
    
    def get_session_history(self, session_id: str, limit: int = 50) -> list:
        """获取会话历史（工具调用 + 结果）"""
        return self.store.list_tool_calls(session_id, limit=limit)
    
    # ─── Campaign 状态管理 ─────────────────────────────────────
    
    def save_campaign(self, platform: str, campaign_id: str, name: str, 
                      status: str = "DRAFT", objective: str = None,
                      budget_daily: float = None, metadata: dict = None) -> CampaignRecord:
        """保存 Campaign 状态"""
        now = datetime.now().isoformat()
        record = CampaignRecord(
            id=f"{platform}_{campaign_id}",
            platform=platform,
            campaign_id=campaign_id,
            name=name,
            status=status,
            objective=objective,
            budget_daily=budget_daily,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self.store.save_campaign(record)
        return record
    
    def update_campaign(self, platform: str, campaign_id: str, updates: dict) -> Optional[CampaignRecord]:
        """更新 Campaign 状态"""
        existing = self.store.get_campaign(platform, campaign_id)
        if not existing:
            return None
        
        for key, value in updates.items():
            if hasattr(existing, key) and key not in ('id', 'platform', 'campaign_id', 'created_at'):
                setattr(existing, key, value)
        existing.updated_at = datetime.now().isoformat()
        
        self.store.save_campaign(existing)
        return existing
    
    def get_campaign(self, platform: str, campaign_id: str) -> Optional[CampaignRecord]:
        """获取 Campaign 状态"""
        return self.store.get_campaign(platform, campaign_id)
    
    def list_campaigns(self, platform: str = None, status: str = None, limit: int = 100) -> list:
        """列出 Campaign"""
        return self.store.list_campaigns(platform, status, limit)
    
    def delete_campaign(self, platform: str, campaign_id: str) -> bool:
        """删除 Campaign 记录"""
        return self.store.delete_campaign(platform, campaign_id)
    
    # ─── 辅助方法 ──────────────────────────────────────────────
    
    def _get_session_campaigns(self, session_id: str) -> list:
        """获取与该会话相关的 Campaign 列表"""
        # 从工具调用记录中提取 campaign_id，然后查询状态
        tool_calls = self.store.list_tool_calls(session_id, limit=50)
        campaign_ids = set()
        for tc in tool_calls:
            if tc.output_data and isinstance(tc.output_data, dict):
                for key in ['campaign_id', 'ad_group_id', 'ad_id', 'creative_id']:
                    if key in tc.output_data:
                        campaign_ids.add(tc.output_data[key])
        
        # 简化：返回所有 Campaign，实际应该按 platform + campaign_id 过滤
        campaigns = []
        for cid in campaign_ids:
            # 尝试从各平台查找
            for platform in ['meta', 'google', 'tiktok', 'dv360']:
                rec = self.store.get_campaign(platform, cid)
                if rec:
                    campaigns.append(rec)
        
        return campaigns
