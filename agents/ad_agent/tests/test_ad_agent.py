"""
tests/test_ad_agent.py - ad-agent 生产级测试套件

运行：
    python -m pytest agents/ad_agent/tests/ -v
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ad_agent.persistence.store import AdAgentStore, CampaignRecord, ToolCallRecord
from agents.ad_agent.persistence.session_manager import SessionManager
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.capabilities.meta_capability import MetaCapability, MetaCreateCampaignMockHandler
from agents.ad_agent.capabilities.platform_capabilities import (
    GoogleCapability, TikTokCapability, DV360Capability,
    GoogleCreateCampaignHandler, TikTokCreateCampaignHandler,
)
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.core.interfaces import ToolContext, ToolResult, RiskLevel


# ═══════════════════════════════════════════════════════════════
# 1. 持久化层测试
# ═══════════════════════════════════════════════════════════════

class TestAdAgentStore:
    """测试 SQLite 持久化存储"""
    
    def setup_method(self):
        self.store = AdAgentStore(":memory:")
    
    def test_create_and_get_session(self):
        self.store.create_session("sess_001", "user_001", "ad_001")
        session = self.store.get_session("sess_001")
        assert session is not None
        assert session["session_id"] == "sess_001"
        assert session["user_id"] == "user_001"
    
    def test_update_session(self):
        self.store.create_session("sess_002", "user_001")
        self.store.update_session("sess_002", {"key": "value"})
        session = self.store.get_session("sess_002")
        assert json.loads(session["metadata"])["key"] == "value"
    
    def test_list_sessions(self):
        self.store.create_session("sess_a", "user_001")
        self.store.create_session("sess_b", "user_001")
        self.store.create_session("sess_c", "user_002")
        
        sessions = self.store.list_sessions("user_001")
        assert len(sessions) == 2
        
        all_sessions = self.store.list_sessions()
        assert len(all_sessions) == 3
    
    def test_record_tool_call(self):
        # First create the session (required by foreign key)
        self.store.create_session("sess_001", "user_001")
        
        record = ToolCallRecord(
            id="tc_001",
            session_id="sess_001",
            turn_id="turn_001",
            tool_name="meta_create_campaign",
            platform="meta",
            input_data={"name": "Test Campaign"},
            output_data={"campaign_id": "camp_123"},
            started_at="2025-01-01T00:00:00",
        )
        self.store.record_tool_call(record)
        
        calls = self.store.list_tool_calls("sess_001")
        assert len(calls) == 1
        assert calls[0].tool_name == "meta_create_campaign"
        assert calls[0].output_data["campaign_id"] == "camp_123"
    
    def test_save_and_get_campaign(self):
        record = CampaignRecord(
            id="meta_camp_001",
            platform="meta",
            campaign_id="camp_001",
            name="Test Campaign",
            status="ACTIVE",
            objective="OUTCOME_SALES",
            budget_daily=100.0,
        )
        self.store.save_campaign(record)
        
        fetched = self.store.get_campaign("meta", "camp_001")
        assert fetched is not None
        assert fetched.name == "Test Campaign"
        assert fetched.status == "ACTIVE"
    
    def test_list_campaigns_filter(self):
        for i in range(3):
            self.store.save_campaign(CampaignRecord(
                id=f"meta_camp_{i}", platform="meta", campaign_id=f"camp_{i}",
                name=f"Campaign {i}", status="ACTIVE"
            ))
        
        active = self.store.list_campaigns(platform="meta", status="ACTIVE")
        assert len(active) == 3
        
        all_meta = self.store.list_campaigns(platform="meta")
        assert len(all_meta) == 3
    
    def test_update_campaign_status(self):
        self.store.save_campaign(CampaignRecord(
            id="meta_camp_002", platform="meta", campaign_id="camp_002",
            name="C2", status="DRAFT"
        ))
        
        updated = self.store.update_campaign_status("meta", "camp_002", "ACTIVE")
        assert updated is True
        
        fetched = self.store.get_campaign("meta", "camp_002")
        assert fetched.status == "ACTIVE"
    
    def test_delete_campaign(self):
        self.store.save_campaign(CampaignRecord(
            id="meta_camp_003", platform="meta", campaign_id="camp_003",
            name="C3", status="DRAFT"
        ))
        
        deleted = self.store.delete_campaign("meta", "camp_003")
        assert deleted is True
        
        assert self.store.get_campaign("meta", "camp_003") is None


# ═══════════════════════════════════════════════════════════════
# 2. 会话管理器测试
# ═══════════════════════════════════════════════════════════════

class TestSessionManager:
    def setup_method(self):
        self.store = AdAgentStore(":memory:")
        self.sm = SessionManager(self.store)
    
    def test_create_session(self):
        session = self.sm.create_session("sess_001", "user_001", "ad_001")
        assert session is not None
        assert session["session_id"] == "sess_001"
    
    def test_record_and_retrieve_tool_call(self):
        # Create session first (required by foreign key)
        self.sm.create_session("sess_001", "user_001")
        
        record = ToolCallRecord(
            id="tc_1", session_id="sess_001", turn_id="turn_1",
            tool_name="meta_create_campaign", platform="meta",
            input_data={}, started_at="2025-01-01",
        )
        self.sm.record_tool_call("sess_001", "turn_1", record)
        
        history = self.sm.get_session_history("sess_001")
        assert len(history) == 1
        assert history[0].tool_name == "meta_create_campaign"
    
    def test_save_and_get_campaign(self):
        rec = self.sm.save_campaign("meta", "camp_001", "My Campaign", status="ACTIVE", budget_daily=200.0)
        assert rec.campaign_id == "camp_001"
        assert rec.budget_daily == 200.0
        
        fetched = self.sm.get_campaign("meta", "camp_001")
        assert fetched is not None
        assert fetched.status == "ACTIVE"
    
    def test_update_campaign_status(self):
        self.sm.save_campaign("meta", "camp_002", "C2", status="DRAFT")
        self.sm.update_campaign("meta", "camp_002", {"status": "ACTIVE"})
        # Verify by re-fetching
        fetched = self.sm.get_campaign("meta", "camp_002")
        assert fetched is not None
        assert fetched.status == "ACTIVE"


# ═══════════════════════════════════════════════════════════════
# 3. API 客户端测试（不验证真实网络，只验证导入和初始化）
# ═══════════════════════════════════════════════════════════════

class TestAPIClientImport:
    """验证所有 API 客户端可导入（无需真实凭证）"""
    
    def test_meta_client_init(self):
        client = MetaAPIClient({"meta": {"access_token": "test_token"}})
        assert client.platform == "meta"
    
    def test_tiktok_client_init(self):
        client = TikTokAPIClient({"tiktok": {"access_token": "test_token"}})
        assert client.platform == "tiktok"
    
    def test_dv360_client_init(self):
        client = DV360APIClient({
            "dv360": {
                "service_account_email": "test@project.iam.gserviceaccount.com",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            }
        })
        assert client.platform == "dv360"
    
    def test_google_client_init(self):
        client = GoogleAdsAPIClient({"google": {}})
        assert client.platform == "google"


# ═══════════════════════════════════════════════════════════════
# 4. Capability / Handler 测试
# ═══════════════════════════════════════════════════════════════

class TestCapabilityHandlers:
    def test_meta_create_campaign_mock(self):
        handler = MetaCreateCampaignMockHandler()
        ctx = ToolContext(
            session_id="sess_001",
            user_id="user_001",
            account_id="ad_001",
            protected_state={},
        )
        result = handler.execute(ctx, {
            "campaign_name": "Test Campaign",
            "objective": "OUTCOME_SALES",
            "budget": 100,
        })
        assert result.success
        assert "campaign_id" in result.data
    
    def test_meta_capability_registers_tools(self):
        cap = MetaCapability()
        tools = cap.register_tools()
        assert len(tools) > 0
        
        names = [t[0].name for t in tools]
        assert "meta_create_campaign" in names
        assert "meta_create_ad_set" in names
        assert "meta_get_campaign_report" in names
    
    def test_google_capability_registers_tools(self):
        cap = GoogleCapability()
        tools = cap.register_tools()
        assert len(tools) == 4
        names = [t[0].name for t in tools]
        assert "google_create_campaign" in names
        assert "google_get_campaign_report" in names
    
    def test_tiktok_capability_registers_tools(self):
        cap = TikTokCapability()
        tools = cap.register_tools()
        names = [t[0].name for t in tools]
        assert "tiktok_create_campaign" in names
        assert "tiktok_spark_ads_create" in names
    
    def test_dv360_capability_registers_tools(self):
        cap = DV360Capability()
        tools = cap.register_tools()
        names = [t[0].name for t in tools]
        assert "dv360_create_campaign" in names
        assert "dv360_create_io" in names
    
    def test_risk_levels(self):
        """验证写操作标注为 MEDIUM，读操作标注为 LOW"""
        cap = MetaCapability()
        tools = cap.register_tools()
        for defn, handler in tools:
            if "create" in defn.name or "boost" in defn.name:
                assert defn.risk_level == RiskLevel.MEDIUM, f"{defn.name} should be MEDIUM"
            elif "get" in defn.name or "list" in defn.name:
                assert defn.risk_level == RiskLevel.LOW, f"{defn.name} should be LOW"


# ═══════════════════════════════════════════════════════════════
# 5. Runtime 集成测试
# ═══════════════════════════════════════════════════════════════

class TestAgentRuntime:
    def test_multi_platform_campaign(self):
        runtime = AgentRuntime()
        runtime.register_capability(MetaCapability())
        runtime.register_capability(GoogleCapability())
        
        result = runtime.run(
            user_input="帮我投放Meta和Google广告，预算100元/天",
            user_id="test_user",
        )
        assert result["intent"]["intent_type"] == "create_campaign"
        assert "meta" in result["intent"]["platforms"]
        assert "google" in result["intent"]["platforms"]
        assert len(result["results"]) == 6  # 3 Meta + 3 Google
    
    def test_single_platform(self):
        runtime = AgentRuntime()
        runtime.register_capability(TikTokCapability())
        
        result = runtime.run(
            user_input="在TikTok上投放产品销售广告",
            user_id="test_user",
        )
        assert result["intent"]["platforms"] == ["tiktok"]
    
    def test_report_query(self):
        runtime = AgentRuntime()
        runtime.register_capability(MetaCapability())
        runtime.register_capability(GoogleCapability())
        
        result = runtime.run(
            user_input="查询Meta和Google过去7天的报表",
            user_id="test_user",
        )
        assert result["intent"]["intent_type"] == "download_report"
        assert len(result["results"]) == 2
    
    def test_with_persistence(self):
        store = AdAgentStore(":memory:")
        runtime = AgentRuntime(persistence_store=store)
        runtime.register_capability(MetaCapability())
        
        result = runtime.run(
            user_input="投放Meta广告",
            user_id="persist_test",
        )
        assert result["intent"]["intent_type"] == "create_campaign"
        
        # 验证持久化
        sessions = store.list_sessions(user_id="persist_test")
        assert len(sessions) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
