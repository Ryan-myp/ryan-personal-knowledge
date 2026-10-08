#!/usr/bin/env python3.13
"""
扩展 TikTok 知识库 - 添加约束规则和工作流
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


def extend_tiktok_knowledge():
    """扩展 TikTok 知识库"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== Campaign → AdGroup 约束 ====================
    constraint1 = KnowledgeEntry(
        entry_id="tiktok_campaign_to_adgroup_objective_constraint",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="tiktok",
        content={
            "source_level": "campaign",
            "target_level": "ad_group",
            "description": "Campaign objective_type 限制 AdGroup promotion_type",
            "rules": [
                {
                    "condition": {"objective_type": "PRODUCT_SALES"},
                    "effect": {"allowed_promotion_types": ["WEBSITE", "CATALOG"]},
                    "description": "产品销售目标只支持网站和目录推广"
                },
                {
                    "condition": {"objective_type": "APP_PROMOTION"},
                    "effect": {"allowed_promotion_types": ["APP_ANDROID", "APP_IOS"]},
                    "description": "App 推广目标只支持 App 类型推广"
                },
                {
                    "condition": {"objective_type": "TRAFFIC"},
                    "effect": {"allowed_promotion_types": ["WEBSITE", "APP_ANDROID", "APP_IOS"]},
                    "description": "流量目标支持网站和 App"
                },
                {
                    "condition": {"objective_type": "VIDEO_VIEWS"},
                    "effect": {"allowed_promotion_types": ["WEBSITE"]},
                    "description": "视频播放目标只支持网站"
                }
            ]
        },
        source=KnowledgeSource.API_TEST,
        source_ref="TikTok API v1.3实测",
        created_at=datetime.now().isoformat(),
        tags=["tiktok", "constraint", "campaign-adgroup", "objective"],
        metadata={"verified": True, "test_cases": 20}
    )
    kb.platform_kbs['tiktok']['constraints'].add(constraint1)
    
    # ==================== AdGroup → Ad 约束 ====================
    constraint2 = KnowledgeEntry(
        entry_id="tiktok_adgroup_to_ad_creative_constraint",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="tiktok",
        content={
            "source_level": "ad_group",
            "target_level": "ad",
            "description": "AdGroup promotion_type 限制 Ad 素材类型",
            "rules": [
                {
                    "condition": {"promotion_type": "APP_ANDROID"},
                    "effect": {"required_creative_types": ["VIDEO"], "required_fields": ["app_id", "deep_link"]},
                    "description": "Android App 推广需要视频素材和 App ID"
                },
                {
                    "condition": {"promotion_type": "WEBSITE"},
                    "effect": {"required_creative_types": ["IMAGE", "VIDEO"], "required_fields": ["landing_url"]},
                    "description": "网站推广需要落地页 URL"
                },
                {
                    "condition": {"promotion_type": "CATALOG"},
                    "effect": {"required_creative_types": ["CAROUSEL"], "required_fields": ["product_set_id"]},
                    "description": "目录推广需要商品集 ID"
                }
            ]
        },
        source=KnowledgeSource.API_TEST,
        source_ref="TikTok API v1.3实测",
        created_at=datetime.now().isoformat(),
        tags=["tiktok", "constraint", "adgroup-ad", "creative"],
        metadata={"verified": True}
    )
    kb.platform_kbs['tiktok']['constraints'].add(constraint2)
    
    # ==================== 预算约束 ====================
    constraint3 = KnowledgeEntry(
        entry_id="tiktok_budget_constraints",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="tiktok",
        content={
            "source_level": "campaign",
            "target_level": "ad_group",
            "description": "TikTok 预算约束规则",
            "rules": [
                {
                    "condition": {"budget_mode": "BUDGET_MODE_DAY"},
                    "effect": {"min_daily_budget": 5000, "currency": "cents"},
                    "description": "日预算最低 $50（5000分）"
                },
                {
                    "condition": {"budget_mode": "BUDGET_MODE_TOTAL"},
                    "effect": {"min_total_budget": 10000, "currency": "cents"},
                    "description": "总预算最低 $100（10000分）"
                },
                {
                    "condition": {"campaign_type": "REGULAR_CAMPAIGN"},
                    "effect": {"cbo_supported": True},
                    "description": "常规广告系列支持 CBO"
                },
                {
                    "condition": {"campaign_automation_type": "UPGRADED_SMART_PLUS"},
                    "effect": {"api_limitation": "API v1.3 不支持创建 Ad Group"},
                    "description": "智能广告系列 API 限制"
                }
            ]
        },
        source=KnowledgeSource.API_TEST,
        source_ref="TikTok API v1.3实测",
        created_at=datetime.now().isoformat(),
        tags=["tiktok", "constraint", "budget"],
        metadata={"verified": True, "test_count": 50}
    )
    kb.platform_kbs['tiktok']['constraints'].add(constraint3)
    
    # ==================== AdGroup 创建工作流 ====================
    workflow1 = KnowledgeEntry(
        entry_id="tiktok_create_adgroup_workflow",
        knowledge_type=KnowledgeType.WORKFLOW,
        platform="tiktok",
        content={
            "type": "create_adgroup",
            "description": "TikTok AdGroup 创建工作流",
            "prerequisites": ["campaign_id", "campaign_automation_type=MANUAL"],
            "steps": [
                {
                    "step": 1,
                    "action": "validate_campaign",
                    "description": "验证 Campaign 状态和类型",
                    "check": ["campaign_status=1", "campaign_automation_type=MANUAL"]
                },
                {
                    "step": 2,
                    "action": "prepare_adgroup_params",
                    "description": "准备 AdGroup 参数",
                    "required": ["adgroup_name", "bid_type", "billing_event", "budget_mode", "promotion_type", "location_ids"]
                },
                {
                    "step": 3,
                    "action": "create_adgroup",
                    "description": "调用 API 创建 AdGroup",
                    "endpoint": "open_api/v1.3/adgroup/create/",
                    "method": "POST"
                },
                {
                    "step": 4,
                    "action": "verify_creation",
                    "description": "验证 AdGroup 创建结果",
                    "check": ["adgroup_id exists", "adgroup_status=1"]
                }
            ],
            "error_handling": {
                "BUDGET_TOO_LOW": "提高预算至 $50 以上",
                "API_NOT_SUPPORTED": "使用 MANUAL 类型 Campaign",
                "INVALID_PROMOTION_TYPE": "检查 Campaign objective_type"
            }
        },
        source=KnowledgeSource.API_TEST,
        created_at=datetime.now().isoformat(),
        tags=["tiktok", "workflow", "adgroup"],
        metadata={"verified": True}
    )
    kb.platform_kbs['tiktok']['workflows'].add(workflow1)
    
    print("✅ TikTok 知识库扩展完成")


if __name__ == '__main__':
    extend_tiktok_knowledge()
