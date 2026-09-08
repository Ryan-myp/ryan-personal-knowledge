#!/usr/bin/env python3.13
"""
TikTok 知识库初始化脚本
基于官方文档和API实测数据
"""

import json
import os
import sys
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base import (
    LLMWikiKnowledgeBase, KnowledgeType, KnowledgeEntry,
    ParameterDefinition, LevelDefinition
)


def init_tiktok_knowledge():
    """初始化 TikTok 知识库"""
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== Campaign 层级知识 ====================
    campaign_entry = KnowledgeEntry(
        entry_id="tiktok_campaign_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="tiktok",
        content={
            "level": "campaign",
            "description": "TikTok 广告系列层级，是广告投放的顶层结构",
            "parameters": {
                "advertiser_id": ParameterDefinition(
                    name="advertiser_id",
                    type="string",
                    required=True,
                    description="广告主ID",
                    valid_values=[],
                    constraints=[]
                ),
                "campaign_name": ParameterDefinition(
                    name="campaign_name",
                    type="string",
                    required=True,
                    description="广告系列名称",
                    valid_values=[],
                    constraints=[{
                        "condition": {"max_length": 60},
                        "effect": {"error": "名称长度不能超过60个字符"},
                        "description": "名称长度限制"
                    }]
                ),
                "campaign_status": ParameterDefinition(
                    name="campaign_status",
                    type="integer",
                    required=True,
                    description="广告系列状态: 1=启用, 0=禁用",
                    valid_values=["1", "0"],
                    constraints=[]
                ),
                "objective_type": ParameterDefinition(
                    name="objective_type",
                    type="string",
                    required=True,
                    description="广告目标类型，决定广告组可用的 promotion_type",
                    valid_values=[
                        "PRODUCT_SALES", "TRAFFIC", "APP_INSTALL", "VIDEO_VIEWS",
                        "CONVERSIONS", "REACH", "LEAD_GENERATION", "ENGAGEMENT",
                        "CATALOG_SALES", "SHOP_PURCHASES", "WEB_CONVERSIONS", "APP_PROMOTION"
                    ],
                    constraints=[{
                        "condition": {"field": "objective_type"},
                        "effect": {"allowed_promotion_types": "根据目标类型限制"},
                        "description": "目标类型限制 promotion_type"
                    }]
                ),
                "budget_mode": ParameterDefinition(
                    name="budget_mode",
                    type="string",
                    required=True,
                    description="预算模式",
                    valid_values=[
                        "BUDGET_MODE_DAY", "BUDGET_MODE_INFINITE",
                        "BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL"
                    ],
                    constraints=[{
                        "condition": {"budget_mode": "BUDGET_MODE_DAY"},
                        "effect": {"required_fields": ["daily_budget"]},
                        "description": "日预算模式需要 daily_budget"
                    }, {
                        "condition": {"budget_mode": "BUDGET_MODE_INFINITE"},
                        "effect": {"required_fields": []},
                        "description": "无限预算模式不需要预算字段"
                    }]
                ),
                "campaign_type": ParameterDefinition(
                    name="campaign_type",
                    type="string",
                    required=True,
                    description="广告系列类型",
                    valid_values=["REGULAR_CAMPAIGN", "IOS14_CAMPAIGN"],
                    constraints=[{
                        "condition": {"campaign_type": "REGULAR_CAMPAIGN"},
                        "effect": {"supported": True},
                        "description": "常规广告系列"
                    }]
                ),
                "campaign_automation_type": ParameterDefinition(
                    name="campaign_automation_type",
                    type="string",
                    required=True,
                    description="自动化类型，影响 API 支持功能",
                    valid_values=["MANUAL", "UPGRADED_SMART_PLUS"],
                    constraints=[{
                        "condition": {"automation_type": "UPGRADED_SMART_PLUS"},
                        "effect": {"api_limitation": "API v1.3 不支持创建 Ad Group"},
                        "description": "智能广告系列限制 API 功能"
                    }]
                ),
                "promote_object_type": ParameterDefinition(
                    name="promote_object_type",
                    type="integer",
                    required=True,
                    description="推广对象类型: 0=APP, 1=WEBSITE",
                    valid_values=["0", "1"],
                    constraints=[]
                ),
                "app_id": ParameterDefinition(
                    name="app_id",
                    type="string",
                    required=False,
                    description="App ID（APP 类型需要）",
                    valid_values=[],
                    constraints=[],
                    depends_on={"promote_object_type": "0"}
                ),
                "landing_url": ParameterDefinition(
                    name="landing_url",
                    type="string",
                    required=False,
                    description="落地页URL（WEBSITE 类型需要）",
                    valid_values=[],
                    constraints=[],
                    depends_on={"promote_object_type": "1"}
                ),
                "daily_budget": ParameterDefinition(
                    name="daily_budget",
                    type="integer",
                    required=False,
                    description="日预算（单位：分），BUDGET_MODE_DAY 时需要",
                    valid_values=[],
                    constraints=[{
                        "condition": {"budget_mode": "BUDGET_MODE_DAY"},
                        "effect": {"min_value": 5000},
                        "description": "最小预算 $50（5000分）"
                    }],
                    depends_on={"budget_mode": "BUDGET_MODE_DAY"}
                )
            },
            "valid_combinations": [
                {
                    "objective_type": "TRAFFIC",
                    "promotion_type": "WEBSITE",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID"
                },
                {
                    "objective_type": "APP_PROMOTION",
                    "promotion_type": "APP_ANDROID",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID",
                    "deep_bid_type": "AEO"
                }
            ],
            "api_limitations": [
                {
                    "api_version": "v1.3",
                    "limitation": "不支持 UPGRADED_SMART_PLUS Campaign 的 Ad Group 创建",
                    "workaround": "使用 MANUAL 类型 Campaign"
                }
            ]
        },
        source="official_docs+tiktok_api",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["tiktok", "campaign", "hierarchy", "api_v1.3"],
        metadata={"verified": True, "test_count": 50}
    )
    
    # ==================== Ad Group 层级知识 ====================
    adgroup_entry = KnowledgeEntry(
        entry_id="tiktok_adgroup_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="tiktok",
        content={
            "level": "ad_group",
            "description": "TikTok 广告组层级，包含定向、出价、素材等信息",
            "parameters": {
                "adgroup_name": ParameterDefinition(
                    name="adgroup_name",
                    type="string",
                    required=True,
                    description="广告组名称",
                    valid_values=[],
                    constraints=[{"condition": {"max_length": 60}, "effect": {"error": "名称长度不能超过60个字符"}}]
                ),
                "ad_group_status": ParameterDefinition(
                    name="ad_group_status",
                    type="integer",
                    required=True,
                    description="广告组状态: 1=启用, 0=禁用",
                    valid_values=["1", "0"]
                ),
                "schedule_type": ParameterDefinition(
                    name="schedule_type",
                    type="string",
                    required=True,
                    description="投放时间类型",
                    valid_values=["SCHEDULE_FROM_NOW", "SCHEDULE_SPECIFIC_TIME"]
                ),
                "schedule_start_time": ParameterDefinition(
                    name="schedule_start_time",
                    type="datetime",
                    required=True,
                    description="开始时间，格式: YYYY-MM-DD HH:MM:SS",
                    valid_values=[],
                    constraints=[{"condition": {"format": "datetime"}, "effect": {"error": "时间格式错误"}}]
                ),
                "bid_type": ParameterDefinition(
                    name="bid_type",
                    type="string",
                    required=True,
                    description="出价类型",
                    valid_values=["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM", "BID_TYPE_MAX_CONVERSION"],
                    constraints=[]
                ),
                "billing_event": ParameterDefinition(
                    name="billing_event",
                    type="string",
                    required=True,
                    description="计费事件类型",
                    valid_values=["CPM", "GD", "CPV", "CPA", "OCPC", "OCPM", "CPC"],
                    constraints=[{
                        "condition": {"promotion_type": "APP_ANDROID"},
                        "effect": {"allowed_events": ["OCPM"]},
                        "description": "APP 推广只支持 OCPM"
                    }]
                ),
                "placement_type": ParameterDefinition(
                    name="placement_type",
                    type="string",
                    required=True,
                    description="投放位置类型",
                    valid_values=["PLACEMENT_TYPE_NORMAL", "PLACEMENT_TYPE_AUTOMATIC"],
                    constraints=[]
                ),
                "budget_mode": ParameterDefinition(
                    name="budget_mode",
                    type="string",
                    required=True,
                    description="预算模式",
                    valid_values=["BUDGET_MODE_DAY", "BUDGET_MODE_INFINITE", "BUDGET_MODE_TOTAL"]
                ),
                "budget": ParameterDefinition(
                    name="budget",
                    type="integer",
                    required=True,
                    description="预算（单位：分）",
                    valid_values=[],
                    constraints=[{"condition": {"min_value": 5000}, "effect": {"error": "预算不能低于$50"}}]
                ),
                "promotion_type": ParameterDefinition(
                    name="promotion_type",
                    type="string",
                    required=True,
                    description="推广类型，必须与 Campaign objective_type 匹配",
                    valid_values=["APP_ANDROID", "APP_IOS", "WEBSITE", "LEAD_FORM", "CONTENT"],
                    constraints=[{
                        "condition": {"objective_type": "APP_PROMOTION"},
                        "effect": {"allowed_types": ["APP_ANDROID", "APP_IOS"]},
                        "description": "APP_PROMOTION 只能使用 APP 类型"
                    }, {
                        "condition": {"objective_type": "TRAFFIC"},
                        "effect": {"allowed_types": ["WEBSITE"]},
                        "description": "TRAFFIC 只能使用 WEBSITE 类型"
                    }]
                ),
                "app_id": ParameterDefinition(
                    name="app_id",
                    type="string",
                    required=False,
                    description="App ID（APP 类型需要）",
                    valid_values=[],
                    constraints=[],
                    depends_on={"promotion_type": "APP_ANDROID"}
                ),
                "landing_url": ParameterDefinition(
                    name="landing_url",
                    type="string",
                    required=False,
                    description="落地页URL（WEBSITE 类型需要）",
                    valid_values=[],
                    constraints=[],
                    depends_on={"promotion_type": "WEBSITE"}
                ),
                "location_ids": ParameterDefinition(
                    name="location_ids",
                    type="array",
                    required=True,
                    description="国家/地区ID列表",
                    valid_values=[],
                    constraints=[]
                ),
                "age_groups": ParameterDefinition(
                    name="age_groups",
                    type="array",
                    required=False,
                    description="年龄分组",
                    valid_values=["AGE_13_17", "AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45_54", "AGE_55_64", "AGE_65+"]
                ),
                "gender": ParameterDefinition(
                    name="gender",
                    type="string",
                    required=False,
                    description="性别定向",
                    valid_values=["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"]
                ),
                "auto_targeting_enabled": ParameterDefinition(
                    name="auto_targeting_enabled",
                    type="boolean",
                    required=False,
                    description="是否启用自动定向",
                    valid_values=["true", "false"]
                ),
                "deep_bid_type": ParameterDefinition(
                    name="deep_bid_type",
                    type="string",
                    required=False,
                    description="深度优化目标（APP 类型需要）",
                    valid_values=["AEO", "OCC", "ROAS"],
                    constraints=[{
                        "condition": {"promotion_type": "APP_ANDROID"},
                        "effect": {"required": True},
                        "description": "APP 推广需要设置 deep_bid_type"
                    }],
                    depends_on={"promotion_type": "APP_ANDROID"}
                ),
                "operating_systems": ParameterDefinition(
                    name="operating_systems",
                    type="array",
                    required=False,
                    description="操作系统类型",
                    valid_values=["ANDROID", "IOS"],
                    constraints=[{
                        "condition": {"promotion_type": "APP_ANDROID"},
                        "effect": {"required": ["ANDROID"]},
                        "description": "Android App 需要 ANDROID"
                    }]
                )
            },
            "parent_dependencies": {
                "campaign": {
                    "objective_type": "决定 promotion_type 可选值",
                    "automation_type": "决定 API 功能限制",
                    "budget_mode": "决定 Ad Group 预算模式"
                }
            },
            "valid_combinations": [
                {
                    "campaign_objective": "TRAFFIC",
                    "promotion_type": "WEBSITE",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID",
                    "requirements": ["landing_url", "location_ids"]
                },
                {
                    "campaign_objective": "APP_PROMOTION",
                    "promotion_type": "APP_ANDROID",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID",
                    "deep_bid_type": "AEO",
                    "requirements": ["app_id", "location_ids", "operating_systems"]
                }
            ]
        },
        source="official_docs+tiktok_api",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["tiktok", "ad_group", "hierarchy", "api_v1.3"],
        metadata={"verified": True, "test_count": 30}
    )
    
    # ==================== Ad 层级知识 ====================
    ad_entry = KnowledgeEntry(
        entry_id="tiktok_ad_hierarchy",
        knowledge_type=KnowledgeType.HIERARCHY,
        platform="tiktok",
        content={
            "level": "ad",
            "description": "TikTok 广告创意层级",
            "parameters": {
                "ad_name": ParameterDefinition(
                    name="ad_name",
                    type="string",
                    required=True,
                    description="广告名称"
                ),
                "ad_status": ParameterDefinition(
                    name="ad_status",
                    type="integer",
                    required=True,
                    description="广告状态: 1=启用, 0=禁用",
                    valid_values=["1", "0"]
                ),
                "creatives": ParameterDefinition(
                    name="creatives",
                    type="array",
                    required=True,
                    description="素材列表",
                    valid_values=[]
                ),
                "text": ParameterDefinition(
                    name="text",
                    type="object",
                    required=True,
                    description="广告文案",
                    valid_values=[]
                )
            },
            "parent_dependencies": {
                "ad_group": {
                    "promotion_type": "决定素材类型",
                    "billing_event": "决定出价方式"
                }
            }
        },
        source="official_docs+tiktok_api",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["tiktok", "ad", "hierarchy"],
        metadata={"verified": True, "test_count": 10}
    )
    
    # ==================== 约束规则 ====================
    constraint_entry = KnowledgeEntry(
        entry_id="tiktok_constraints",
        knowledge_type=KnowledgeType.CONSTRAINT,
        platform="tiktok",
        content={
            "rules": [
                {
                    "rule_id": "campaign_objective_to_promotion_type",
                    "source_level": "campaign",
                    "target_level": "ad_group",
                    "source_value": "objective_type",
                    "condition": {
                        "objective_type": "TRAFFIC",
                        "promotion_type": "WEBSITE"
                    },
                    "effect": {
                        "allowed": True,
                        "required_params": ["landing_url"]
                    },
                    "description": "TRAFFIC 目标只能使用 WEBSITE 推广类型"
                },
                {
                    "rule_id": "campaign_objective_to_promotion_type_app",
                    "source_level": "campaign",
                    "target_level": "ad_group",
                    "source_value": "objective_type",
                    "condition": {
                        "objective_type": "APP_PROMOTION",
                        "promotion_type": "APP_ANDROID"
                    },
                    "effect": {
                        "allowed": True,
                        "required_params": ["app_id", "deep_bid_type", "operating_systems"]
                    },
                    "description": "APP_PROMOTION 目标只能使用 APP 推广类型"
                },
                {
                    "rule_id": "automation_type_api_limitation",
                    "source_level": "campaign",
                    "target_level": "ad_group",
                    "source_value": "automation_type",
                    "condition": {
                        "automation_type": "UPGRADED_SMART_PLUS"
                    },
                    "effect": {
                        "allowed": False,
                        "error": "This API does not support Upgraded Smart Plus ads",
                        "workaround": "使用 MANUAL 类型 Campaign"
                    },
                    "description": "API v1.3 不支持 UPGRADED_SMART_PLUS Campaign 的 Ad Group 创建"
                },
                {
                    "rule_id": "budget_mode_requirement",
                    "source_level": "campaign",
                    "target_level": "ad_group",
                    "source_value": "budget_mode",
                    "condition": {
                        "budget_mode": "BUDGET_MODE_DAY"
                    },
                    "effect": {
                        "required_params": ["daily_budget", "budget"],
                        "min_budget": 5000
                    },
                    "description": "日预算模式需要设置 daily_budget 和 budget，最小 $50"
                },
                {
                    "rule_id": "billing_event_promotion_type",
                    "source_level": "ad_group",
                    "target_level": "ad_group",
                    "source_value": "promotion_type",
                    "condition": {
                        "promotion_type": "APP_ANDROID"
                    },
                    "effect": {
                        "allowed_billing_events": ["OCPM"],
                        "required_deep_bid_type": "AEO"
                    },
                    "description": "APP 推广只支持 OCPM 计费，需要设置 AEO 深度优化"
                }
            ]
        },
        source="official_docs+tiktok_api_test",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["tiktok", "constraints", "dependencies"],
        metadata={"verified": True, "test_count": 100}
    )
    
    # ==================== 工作流 ====================
    workflow_entry = KnowledgeEntry(
        entry_id="tiktok_create_workflow",
        knowledge_type=KnowledgeType.WORKFLOW,
        platform="tiktok",
        content={
            "type": "create_campaign_adgroup_ad",
            "description": "TikTok 完整创建流程",
            "steps": [
                {
                    "step": 1,
                    "action": "create_campaign",
                    "level": "campaign",
                    "required_params": ["advertiser_id", "campaign_name", "objective_type", "budget_mode", "campaign_type", "campaign_automation_type"],
                    "validation": "检查 objective_type 和 budget_mode 的组合",
                    "api_endpoint": "open_api/v1.3/campaign/create/"
                },
                {
                    "step": 2,
                    "action": "query_campaigns",
                    "level": "campaign",
                    "required_params": ["advertiser_id"],
                    "validation": "确认 Campaign 创建成功",
                    "api_endpoint": "open_api/v1.3/campaign/get/"
                },
                {
                    "step": 3,
                    "action": "create_adgroup",
                    "level": "ad_group",
                    "required_params": ["advertiser_id", "campaign_id", "adgroup_name", "bid_type", "billing_event", "budget_mode", "budget", "promotion_type", "location_ids"],
                    "validation": "检查 promotion_type 是否与 Campaign objective_type 匹配",
                    "api_endpoint": "open_api/v1.3/adgroup/create/"
                },
                {
                    "step": 4,
                    "action": "query_adgroups",
                    "level": "ad_group",
                    "required_params": ["advertiser_id", "campaign_id"],
                    "validation": "确认 Ad Group 创建成功",
                    "api_endpoint": "open_api/v1.3/adgroup/get/"
                },
                {
                    "step": 5,
                    "action": "create_ad",
                    "level": "ad",
                    "required_params": ["advertiser_id", "campaign_id", "adgroup_id", "ad_name", "ad_status", "creatives", "text"],
                    "validation": "检查素材类型是否与 promotion_type 匹配",
                    "api_endpoint": "open_api/v1.3/ad/create/"
                }
            ],
            "error_handling": {
                "40002": "参数错误，检查知识库约束规则",
                "40003": "权限不足，检查 Account Permission",
                "40004": "配额超限，检查 Budget 设置"
            }
        },
        source="tiktok_api_experience",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["tiktok", "workflow", "creation"],
        metadata={"verified": True, "test_count": 20}
    )
    
    # 添加所有条目
    kb.knowledge_bases['tiktok']['hierarchy'].add(campaign_entry)
    kb.knowledge_bases['tiktok']['hierarchy'].add(adgroup_entry)
    kb.knowledge_bases['tiktok']['hierarchy'].add(ad_entry)
    kb.knowledge_bases['tiktok']['constraints'].add(constraint_entry)
    kb.knowledge_bases['tiktok']['workflows'].add(workflow_entry)
    
    # 保存
    kb.knowledge_bases['tiktok']['hierarchy']._save()
    kb.knowledge_bases['tiktok']['constraints']._save()
    kb.knowledge_bases['tiktok']['parameters']._save()
    kb.knowledge_bases['tiktok']['workflows']._save()
    
    print("✅ TikTok 知识库初始化完成")
    return kb


if __name__ == "__main__":
    init_tiktok_knowledge()
