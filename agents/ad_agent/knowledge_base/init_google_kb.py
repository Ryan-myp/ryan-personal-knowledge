#!/usr/bin/env python3.13
"""
Google Ads 知识库初始化脚本（简化版）
基于官方文档
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base import (
    LLMWikiKnowledgeBase, KnowledgeType, KnowledgeSource,
    KnowledgeEntry
)


def init_google_knowledge():
    """初始化 Google Ads 知识库"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== Campaign 层级 ====================
    campaign_entry = KnowledgeEntry(
        entry_id="google_campaign_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="google",
        content={
            "level": "campaign",
            "description": "Google Ads 广告系列层级",
            "parameters": {
                "customer_id": {
                    "name": "customer_id",
                    "type": "string",
                    "required": True,
                    "description": "Google Ads 客户ID",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "name": {
                    "name": "name",
                    "type": "string",
                    "required": True,
                    "description": "广告系列名称",
                    "valid_values": [],
                    "constraints": [{"condition": {"max_length": 60}, "effect": {"error": "名称长度不能超过60个字符"}}],
                    "depends_on": {}
                },
                "type": {
                    "name": "type",
                    "type": "string",
                    "required": True,
                    "description": "广告系列类型",
                    "valid_values": ["SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "APP", "MAXIMIZE"],
                    "constraints": [],
                    "depends_on": {}
                },
                "network_settings": {
                    "name": "network_settings",
                    "type": "json",
                    "required": False,
                    "description": "网络设置",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                }
            }
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="https://developers.google.com/adwords/api/docs/overview",
        created_at=datetime.now().isoformat(),
        tags=["google", "campaign", "hierarchy"],
        metadata={"verified": False}
    )
    kb.platform_kbs['google']['hierarchy'].add(campaign_entry)
    
    print("✅ Google Ads 知识库初始化完成（简化版）")


if __name__ == '__main__':
    init_google_knowledge()
