"""
persistence/session_manager.py - 会话管理器

管理会话生命周期，与 AgentRuntime 的 SessionContext 配合。
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime

from .interfaces import PersistenceBackend
from .store import ToolCallRecord, CampaignRecord

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
    
    def __init__(self, store: PersistenceBackend):
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

    def update_session(self, session_id: str, metadata: dict = None) -> None:
        """更新会话元数据（不保存凭证）。"""
        self.store.update_session(session_id, metadata or {})
    
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
                      budget_daily: float = None, metadata: dict = None,
                      account_id: str = None) -> CampaignRecord:
        """保存 Campaign 状态"""
        now = datetime.now().isoformat()
        record = CampaignRecord(
            id=f"{platform}_{account_id or 'unknown'}_{campaign_id}",
            platform=platform,
            campaign_id=campaign_id,
            name=name,
            status=status,
            objective=objective,
            budget_daily=budget_daily,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            account_id=str(account_id) if account_id is not None else None,
        )
        self.store.save_campaign(record)
        return record
    
    def update_campaign(
        self, platform: str, campaign_id: str, updates: dict,
        account_id: str = None,
    ) -> Optional[CampaignRecord]:
        """更新 Campaign 状态"""
        existing = self.store.get_campaign(platform, campaign_id, account_id)
        if not existing:
            return None
        
        for key, value in updates.items():
            if hasattr(existing, key) and key not in ('id', 'platform', 'campaign_id', 'created_at'):
                setattr(existing, key, value)
        existing.updated_at = datetime.now().isoformat()
        
        self.store.save_campaign(existing)
        return existing
    
    def get_campaign(
        self, platform: str, campaign_id: str, account_id: str = None
    ) -> Optional[CampaignRecord]:
        """获取 Campaign 状态"""
        return self.store.get_campaign(platform, campaign_id, account_id)
    
    def list_campaigns(
        self, platform: str = None, status: str = None, limit: int = 100,
        account_id: str = None,
    ) -> list:
        """列出 Campaign"""
        return self.store.list_campaigns(platform, status, limit, account_id)
    
    def delete_campaign(
        self, platform: str, campaign_id: str, account_id: str = None,
    ) -> bool:
        """删除 Campaign 记录"""
        return self.store.delete_campaign(platform, campaign_id, account_id)
    
    # ─── 辅助方法 ──────────────────────────────────────────────
    
    def _get_session_campaigns(self, session_id: str) -> list:
        """获取与该会话相关的 Campaign 列表"""
        # 从工具调用记录中提取 campaign_id，然后查询状态
        tool_calls = self.store.list_tool_calls(session_id, limit=50)
        session = self.store.get_session(session_id) or {}
        session_account_id = session.get("account_id")
        campaign_keys = set()
        for tc in tool_calls:
            if tc.output_data and isinstance(tc.output_data, dict):
                for key in ['campaign_id', 'ad_group_id', 'ad_id', 'creative_id']:
                    if key in tc.output_data:
                        account_id = session_account_id
                        if isinstance(tc.input_data, dict):
                            for account_key in ('account_id', 'advertiser_id', 'customer_id'):
                                if tc.input_data.get(account_key):
                                    account_id = str(tc.input_data[account_key])
                                    break
                        campaign_keys.add((tc.platform, tc.output_data[key], account_id))
        
        # 简化：返回所有 Campaign，实际应该按 platform + campaign_id 过滤
        campaigns = []
        for platform, cid, account_id in campaign_keys:
            normalized_platform = 'google-ads' if platform == 'google' else platform
            rec = self.store.get_campaign(normalized_platform, cid, account_id)
            if rec:
                campaigns.append(rec)
        
        return campaigns

    # -- Workflow audit / compensation ---------------------------------

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned", metadata: dict = None,
    ) -> None:
        """Create a durable local workflow record; never stores credentials."""
        self.store.create_workflow(
            workflow_id, session_id, intent_type, execution_mode, status, metadata
        )

    def update_workflow(
        self, workflow_id: str, status: str, metadata: dict = None,
    ) -> bool:
        return self.store.update_workflow(workflow_id, status, metadata)

    def record_workflow_item(
        self, workflow_id: str, sequence: int, platform: str, tool_name: str,
        status: str, input_data: dict, output_data: dict = None,
        error: str = None, compensation_required: bool = False,
    ) -> None:
        self.store.upsert_workflow_item(
            item_id=f"{workflow_id}:{sequence}", workflow_id=workflow_id,
            sequence=sequence, platform=platform, tool_name=tool_name,
            status=status, input_data=input_data, output_data=output_data,
            error=error, compensation_required=compensation_required,
        )

    def get_workflow(self, workflow_id: str) -> Optional[dict]:
        return self.store.get_workflow(workflow_id)

    def mark_workflow_items_for_compensation(
        self, workflow_id: str, sequences: list[int]
    ) -> None:
        self.store.mark_workflow_items_for_compensation(workflow_id, sequences)

    def update_workflow_item(
        self, workflow_id: str, sequence: int, status: str,
        output_data: Optional[dict] = None, error: Optional[str] = None,
        compensation_required: Optional[bool] = None,
    ) -> bool:
        return self.store.update_workflow_item(
            workflow_id, sequence, status, output_data, error,
            compensation_required,
        )

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, limit: int = 50,
        include_stale_running: bool = False, stale_after_seconds: float = 300.0,
    ) -> list[dict]:
        return self.store.list_resumable_workflows(
            user_id, limit, include_stale_running, stale_after_seconds
        )
