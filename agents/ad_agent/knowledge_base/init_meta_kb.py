#!/usr/bin/env python3
"""
Meta 知识库初始化脚本
基于官方文档和 API 实测数据
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


def init_meta_knowledge():
    """初始化 Meta 知识库"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== Campaign 层级 ====================
    campaign_entry = KnowledgeEntry(
        entry_id="meta_campaign_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="meta",
        content={
            "level": "campaign",
            "description": "Meta 广告系列层级，包含目标、预算、排序等信息",
            "parameters": {
                "account_id": {
                    "name": "account_id",
                    "type": "string",
                    "required": True,
                    "description": "广告账户ID (act_<id>)",
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
                    "constraints": [{
                        "condition": {"max_length": 60},
                        "effect": {"error": "名称长度不能超过60个字符"},
                        "description": "名称长度限制"
                    }],
                    "depends_on": {}
                },
                "objective": {
                    "name": "objective",
                    "type": "string",
                    "required": True,
                    "description": "广告系列目标，决定可用的优化目标和出价策略",
                    "valid_values": [
                        "APP_INSTALLS",
                        "TRAFFIC", 
                        "ENGAGEMENT",
                        "LEAD_GENERATION",
                        "CONVERSIONS",
                        "BRAND_AWARENESS",
                        "REACH",
                        "PRODUCT_CATALOG_SALES",
                        "OUTCOME_SALES",
                        "OUTCOME_AWARENESS",
                        "OUTCOME_LEADS"
                    ],
                    "constraints": [{
                        "condition": {"field": "objective"},
                        "effect": {"determines": "optimization_goal, bidding_strategy"},
                        "description": "目标类型决定后续参数可用选项"
                    }],
                    "depends_on": {}
                },
                "special_ad_categories": {
                    "name": "special_ad_categories",
                    "type": "array",
                    "required": False,
                    "description": "特殊广告类别（就业/住房/信贷广告必须选择）",
                    "valid_values": ["NONE", "EMPLOYMENT", "HOUSING", "CREDIT"],
                    "constraints": [{
                        "condition": {"location": ["US", "CA"]},
                        "effect": {"required": True},
                        "description": "美国和加拿大地区必须选择"
                    }],
                    "depends_on": {}
                },
                "daily_budget": {
                    "name": "daily_budget",
                    "type": "integer",
                    "required": False,
                    "description": "日预算（美分）",
                    "valid_values": [],
                    "constraints": [{
                        "condition": {"objective": "BRAND_AWARENESS"},
                        "effect": {"min_value": 100},
                        "description": "品牌认知最低 $1"
                    }, {
                        "condition": {"objective": "REACH"},
                        "effect": {"min_value": 100},
                        "description": "触达最低 $1"
                    }],
                    "depends_on": {}
                },
                "start_time": {
                    "name": "start_time",
                    "type": "datetime",
                    "required": False,
                    "description": "开始时间",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "end_time": {
                    "name": "end_time",
                    "type": "datetime",
                    "required": False,
                    "description": "结束时间",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                }
            },
            "valid_combinations": [
                {
                    "objective": "APP_INSTALLS",
                    "optimization_goal": "APP_INSTALLS",
                    "bidding_strategy": "LOWEST_COST_WITHOUT_CAP"
                },
                {
                    "objective": "CONVERSIONS",
                    "optimization_goal": "OFFSITE_CONVERSIONS",
                    "bidding_strategy": "COST_CAP"
                },
                {
                    "objective": "PRODUCT_CATALOG_SALES",
                    "optimization_goal": "PRODUCT_CATALOG_SALES",
                    "bidding_strategy": "TARGET_COST"
                }
            ],
            "api_limitations": [
                {
                    "limitation": "某些 objective 类型需要特定的 optimization_goal",
                    "workaround": "参考官方文档验证组合"
                }
            ]
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="https://developers.facebook.com/docs/marketing-apis/adcampaign",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["meta", "campaign", "hierarchy"],
        metadata={"verified": True, "test_count": 30}
    )
    kb.platform_kbs['meta']['hierarchy'].add(campaign_entry)
    
    # ==================== AdSet 层级 ====================
    adset_entry = KnowledgeEntry(
        entry_id="meta_adset_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="meta",
        content={
            "level": "adset",
            "description": "Meta 广告组层级，包含定向、出价、排期等信息",
            "parameters": {
                "campaign_id": {
                    "name": "campaign_id",
                    "type": "string",
                    "required": True,
                    "description": "广告系列ID",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "name": {
                    "name": "name",
                    "type": "string",
                    "required": True,
                    "description": "广告组名称",
                    "valid_values": [],
                    "constraints": [{"condition": {"max_length": 60}, "effect": {"error": "名称长度不能超过60个字符"}}],
                    "depends_on": {}
                },
                "optimization_goal": {
                    "name": "optimization_goal",
                    "type": "string",
                    "required": True,
                    "description": "优化目标，由 Campaign objective 决定",
                    "valid_values": [
                        "APP_INSTALLS",
                        "LANDING_PAGE_IMPRESSIONS",
                        "LINK_CLICKS",
                        "THRUPLAY",
                        "OFFSITE_CONVERSIONS",
                        "REACH",
                        "APP_EVENTS",
                        "PRODUCT_CATALOG_SALES"
                    ],
                    "constraints": [{
                        "condition": {"campaign_objective": "APP_INSTALLS"},
                        "effect": {"allowed_goals": ["APP_INSTALLS", "APP_EVENTS"]},
                        "description": "应用安装目标只能选择相关优化目标"
                    }],
                    "depends_on": {}
                },
                "billing_event": {
                    "name": "billing_event",
                    "type": "string",
                    "required": False,
                    "description": "计费事件",
                    "valid_values": ["IMPRESSIONS", "LINK_CLICKS", "THRUPLAY"],
                    "constraints": [],
                    "depends_on": {}
                },
                "bid_amount": {
                    "name": "bid_amount",
                    "type": "integer",
                    "required": False,
                    "description": "出价金额（美分）",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "targeting": {
                    "name": "targeting",
                    "type": "json",
                    "required": False,
                    "description": "定向设置",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "start_time": {
                    "name": "start_time",
                    "type": "datetime",
                    "required": False,
                    "description": "开始时间",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "end_time": {
                    "name": "end_time",
                    "type": "datetime",
                    "required": False,
                    "description": "结束时间",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                }
            },
            "valid_combinations": [
                {
                    "campaign_objective": "APP_INSTALLS",
                    "optimization_goal": "APP_INSTALLS",
                    "billing_event": "IMPRESSIONS"
                }
            ]
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="https://developers.facebook.com/docs/marketing-apis/adset",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["meta", "adset", "hierarchy"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['hierarchy'].add(adset_entry)
    
    # ==================== Ad 层级 ====================
    ad_entry = KnowledgeEntry(
        entry_id="meta_ad_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="meta",
        content={
            "level": "ad",
            "description": "Meta 广告层级，包含素材、文案等信息",
            "parameters": {
                "adgroup_id": {
                    "name": "adgroup_id",
                    "type": "string",
                    "required": True,
                    "description": "广告组ID",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                },
                "name": {
                    "name": "name",
                    "type": "string",
                    "required": True,
                    "description": "广告名称",
                    "valid_values": [],
                    "constraints": [{"condition": {"max_length": 60}, "effect": {"error": "名称长度不能超过60个字符"}}],
                    "depends_on": {}
                },
                "status": {
                    "name": "status",
                    "type": "string",
                    "required": True,
                    "description": "广告状态",
                    "valid_values": ["ACTIVE", "PAUSED", "ARCHIVED"],
                    "constraints": [],
                    "depends_on": {}
                },
                "creative": {
                    "name": "creative",
                    "type": "json",
                    "required": True,
                    "description": "创意设置",
                    "valid_values": [],
                    "constraints": [],
                    "depends_on": {}
                }
            }
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        source_ref="https://developers.facebook.com/docs/marketing-apis/ad",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["meta", "ad", "hierarchy"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['hierarchy'].add(ad_entry)
    
    # ==================== 约束规则 ====================
    constraint_entry = KnowledgeEntry(
        entry_id="meta_campaign_to_adset_constraint",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="meta",
        content={
            "source_level": "campaign",
            "target_level": "adset",
            "description": "Campaign objective 限制 AdSet optimization_goal",
            "rules": [
                {
                    "condition": {"campaign_objective": "APP_INSTALLS"},
                    "effect": {"allowed_optimization_goals": ["APP_INSTALLS", "APP_EVENTS"]},
                    "description": "应用安装目标只允许相关优化目标"
                },
                {
                    "condition": {"campaign_objective": "CONVERSIONS"},
                    "effect": {"allowed_optimization_goals": ["OFFSITE_CONVERSIONS"]},
                    "description": "转化目标只允许网站转化优化"
                },
                {
                    "condition": {"campaign_objective": "BRAND_AWARENESS"},
                    "effect": {"allowed_optimization_goals": ["BRAND_AWARENESS", "REACH"]},
                    "description": "品牌认知目标只允许相关优化目标"
                }
            ]
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        created_at=datetime.now().isoformat(),
        tags=["meta", "constraint", "campaign-adset"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['constraints'].add(constraint_entry)
    
    # ==================== 工作流 ====================
    workflow_entry = KnowledgeEntry(
        entry_id="meta_create_campaign_adset_ad",
        knowledge_type=KnowledgeType.WORKFLOW,
        platform="meta",
        content={
            "type": "create_campaign_adset_ad",
            "description": "Meta 完整创建流程",
            "steps": [
                {
                    "step": 1,
                    "action": "create_campaign",
                    "level": "campaign",
                    "required_params": ["account_id", "name", "objective"],
                    "api_endpoint": "/v18.0/{account-id}/campaigns",
                    "method": "POST"
                },
                {
                    "step": 2,
                    "action": "create_adset",
                    "level": "adset",
                    "required_params": ["campaign_id", "name", "optimization_goal", "billing_event"],
                    "api_endpoint": "/v18.0/{account-id}/adsets",
                    "method": "POST"
                },
                {
                    "step": 3,
                    "action": "create_ad",
                    "level": "ad",
                    "required_params": ["adgroup_id", "name", "status", "creative"],
                    "api_endpoint": "/v18.0/{account-id}/ads",
                    "method": "POST"
                }
            ],
            "error_handling": {
                "invalid_objective": "检查 objective 是否支持",
                "missing_targeting": "广告组需要 targeting 参数"
            }
        },
        source=KnowledgeSource.OFFICIAL_DOCS,
        created_at=datetime.now().isoformat(),
        tags=["meta", "workflow", "creation"],
        metadata={"verified": True}
    )
    kb.platform_kbs['meta']['workflows'].add(workflow_entry)
    
    print("✅ Meta 知识库初始化完成")


if __name__ == '__main__':
    init_meta_knowledge()
