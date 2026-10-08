#!/usr/bin/env python3.13
"""
扩展 Meta 知识库 - 添加约束规则和工作流
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


def extend_meta_knowledge():
    """扩展 Meta 知识库"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== AdSet → Ad 约束 ====================
    constraint1 = KnowledgeEntry(
        entry_id="meta_adset_to_ad_creative_constraint",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="meta",
        content={
            "source_level": "adset",
            "target_level": "ad",
            "description": "AdSet 设置限制 Ad 素材类型",
            "rules": [
                {
                    "condition": {"optimization_goal": "APP_INSTALLS"},
                    "effect": {"required_fields": ["page_id", "call_to_action_type"]},
                    "description": "应用安装需要 Page ID 和 CTA"
                },
                {
                    "condition": {"optimization_goal": "CONVERSIONS"},
                    "effect": {"required_fields": ["landing_url", "pixel_id"]},
                    "description": "转化需要落地页和 Pixel"
                },
                {
                    "condition": {"optimization_goal": "REACH"},
                    "effect": {"allowed_formats": ["IMAGE", "VIDEO"]},
                    "description": "触达目标支持图片和视频"
                }
            ]
        },
        source=KnowledgeSource.API_TEST,
        source_ref="Meta Marketing API v18.0",
        created_at=datetime.now().isoformat(),
        tags=["meta", "constraint", "adset-ad"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['constraints'].add(constraint1)
    
    # ==================== 特殊广告类别约束 ====================
    constraint2 = KnowledgeEntry(
        entry_id="meta_special_ad_categories_constraint",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="meta",
        content={
            "source_level": "campaign",
            "target_level": "adset",
            "description": "特殊广告类别限制",
            "rules": [
                {
                    "condition": {"special_ad_categories": ["EMPLOYMENT"]},
                    "effect": {"restricted_locations": ["US", "CA"], "no_age_gender_targeting": True},
                    "description": "就业广告不能定向年龄和性别"
                },
                {
                    "condition": {"special_ad_categories": ["HOUSING"]},
                    "effect": {"restricted_locations": ["US", "CA"], "no_age_gender_targeting": True},
                    "description": "住房广告不能定向年龄和性别"
                },
                {
                    "condition": {"special_ad_categories": ["CREDIT"]},
                    "effect": {"restricted_locations": ["US", "CA"], "no_age_gender_targeting": True},
                    "description": "信贷广告不能定向年龄和性别"
                }
            ]
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="Meta Advertising Policies",
        created_at=datetime.now().isoformat(),
        tags=["meta", "constraint", "special-ad-categories"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['constraints'].add(constraint2)
    
    # ==================== Ad 创建工作流 ====================
    workflow1 = KnowledgeEntry(
        entry_id="meta_create_ad_workflow",
        knowledge_type=KnowledgeType.WORKFLOW,
        platform="meta",
        content={
            "type": "create_ad",
            "description": "Meta Ad 创建工作流",
            "prerequisites": ["adgroup_id", "campaign_id", "page_id"],
            "steps": [
                {
                    "step": 1,
                    "action": "prepare_creative",
                    "description": "准备创意素材",
                    "required": ["profile_id", "name", "object_story_spec"]
                },
                {
                    "step": 2,
                    "action": "create_ad",
                    "description": "调用 API 创建广告",
                    "endpoint": "/v18.0/{adgroup-id}/ads",
                    "method": "POST"
                },
                {
                    "step": 3,
                    "action": "verify_creation",
                    "description": "验证广告创建结果",
                    "check": ["ad_id exists", "run_status=ACTIVE"]
                }
            ],
            "error_handling": {
                "INVALID_PAGE": "检查 Page ID 权限",
                "CREATIVE_REJECTED": "检查素材政策合规性"
            }
        },
        source=KnowledgeSource.API_TEST,
        created_at=datetime.now().isoformat(),
        tags=["meta", "workflow", "ad"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['workflows'].add(workflow1)
    
    print("✅ Meta 知识库扩展完成")


if __name__ == '__main__':
    extend_meta_knowledge()
