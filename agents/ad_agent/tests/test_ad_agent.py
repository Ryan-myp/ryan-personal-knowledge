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
from agents.ad_agent.capabilities.meta import MetaCapability, MetaListCampaignsHandler
from agents.ad_agent.capabilities.google import GoogleCapability, GoogleListCampaignsHandler
from agents.ad_agent.capabilities.tiktok import TikTokCapability, TikTokListCampaignsHandler
from agents.ad_agent.capabilities.dv360 import DV360Capability
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.core.interfaces import ToolContext, ToolResult, RiskLevel
