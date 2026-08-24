#!/usr/bin/env python3
"""
DV360 知识库初始化脚本（简化版）
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


def init_dv360_knowledge():
    """初始化 DV360 知识库"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== Campaign 层级 ====================
    campaign_entry = KnowledgeEntry(
        entry_id="dv360_campaign_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="dv360",
        content={
            "level": "campaign",
            "description": "DV360 广告系列层级",
            "parameters": {
                "buyer_id": {
                    "name": "buyer_id",
                    "type": "integer",
                    "required": True,
                    "description": "买家ID（SSP侧）",
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
                    "constraints": [{"condition": {"max_length": 100}, "effect": {"error": "名称长度不能超过100个字符"}}],
                    "depends_on": {}
                },
                "start_date": {
                    "name": "start_date",
                    "type": "date",
                    "required": True,
                    "description": "开始日期",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "end_date": {
                    "name": "end_date",
                    "type": "date",
                    "required": False,
                    "description": "结束日期",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                }
            }
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="https://developers.google.com/display-video",
        created_at=datetime.now().isoformat(),
        tags=["dv360", "campaign", "hierarchy"],
        metadata={"verified": False}
    )
    kb.platform_kbs['dv360']['hierarchy'].add(campaign_entry)
    
    print("✅ DV360 知识库初始化完成（简化版）")


if __name__ == '__main__':
    init_dv360_knowledge()
