#!/usr/bin/env python3
"""
经验层知识库初始化脚本
包含：最佳实践、案例研究、错误模式、实用技巧
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


def init_expertise_knowledge():
    """初始化经验层知识"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== 最佳实践 ====================
    bp_kb = kb.expertise_kbs['best_practices']
    
    best_practices = [
        {
            'entry_id': 'bp_campaign_structure',
            'knowledge_type': KnowledgeType.BEST_PRACTICE,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '广告账户结构最佳实践',
                'description': '如何组织广告账户以提高管理效率',
                'recommendations': [
                    '使用清晰的命名规范：{业务}-{产品}-{定向}-{格式}',
                    '每个 Campaign 只放一个目标',
                    'AdGroup 数量控制在 5-15 个',
                    '使用标签 (Labels) 进行分类管理'
                ],
                '适用场景': ['新账户搭建', '账户重构'],
                '预期效果': '提升管理效率 50%+'
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['best-practice', 'structure', 'management'],
            'confidence': 0.9,
            'usage_count': 0
        },
        {
            'entry_id': 'bp_budget_allocation',
            'knowledge_type': KnowledgeType.BEST_PRACTICE,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '预算分配最佳实践',
                'description': '如何科学分配广告预算',
                'recommendations': [
                    '测试阶段：小预算多组合（$50-100/天）',
                    '放量阶段：集中预算到表现最好的 AdGroup',
                    '使用 CBO 自动预算分配',
                    '保持至少 3-5 个活跃 AdGroup'
                ],
                '适用场景': ['预算规划', '账户优化'],
                '预期效果': '提升 ROAS 20-30%'
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['best-practice', 'budget', 'optimization'],
            'confidence': 0.85,
            'usage_count': 0
        },
        {
            'entry_id': 'bp_creative_testing',
            'knowledge_type': KnowledgeType.BEST_PRACTICE,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '素材测试最佳实践',
                'description': '如何进行有效的素材 A/B 测试',
                'recommendations': [
                    '每次测试只改变一个变量',
                    '测试周期至少 3-7 天',
                    '每组素材至少 3 个变体',
                    '使用相同定向和预算进行对比'
                ],
                '适用场景': ['素材优化', '创意测试'],
                '预期效果': '提升 CTR 30%+'
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['best-practice', 'creative', 'testing'],
            'confidence': 0.88,
            'usage_count': 0
        }
    ]
    
    for bp in best_practices:
        bp_kb.add(KnowledgeEntry(**bp))
    
    # ==================== 错误模式 ====================
    ep_kb = kb.expertise_kbs['error_patterns']
    
    error_patterns = [
        {
            'entry_id': 'ep_invalid_objective',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'meta',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'INVALID_PARAMETER',
                'error_message': 'Objective is invalid for this ad account',
                'cause': '使用了不支持的 objective 类型',
                'solutions': [
                    '检查账户支持的 objective 列表',
                    '使用 campaign/get 查询可用目标',
                    '联系 Meta 支持确认账户权限'
                ],
                '常见场景': ['新账户首次投放', '跨账户复制']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'objective', 'validation'],
            'confidence': 0.95,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_budget_too_low',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'tiktok',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'BUDGET_TOO_LOW',
                'error_message': 'Your budget setting must not be less than $50',
                'cause': '预算低于平台最低限制',
                'solutions': [
                    '提高日预算至 $50 以上',
                    '检查预算单位（分 vs 美元）',
                    '确认平台最低预算要求'
                ],
                '常见场景': ['新 Campaign 创建', '预算调整']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'budget', 'tiktok'],
            'confidence': 0.95,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_tiktok_adgroup_limitation',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'tiktok',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'API_NOT_SUPPORTED',
                'error_message': 'This API does not support Upgraded Smart Plus ads',
                'cause': 'API v1.3 不支持智能广告系列',
                'solutions': [
                    '使用 MANUAL 类型 Campaign',
                    '升级至 API v2.0（需申请权限）',
                    '通过广告后台手动创建'
                ],
                '常见场景': ['创建 Ad Group', 'API 版本限制']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'api-limitation', 'tiktok'],
            'confidence': 0.98,
            'usage_count': 0
        }
    ]
    
    for ep in error_patterns:
        ep_kb.add(KnowledgeEntry(**ep))
    
    # ==================== 技巧 ====================
    tip_kb = kb.expertise_kbs['tips']
    
    tips = [
        {
            'entry_id': 'tip_name_convention',
            'knowledge_type': KnowledgeType.TIP,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '命名规范技巧',
                'description': '统一的命名规范有助于数据分析和团队协作',
                'format': '{Date}_{Platform}_{CampaignType}_{Audience}_{Creative}',
                '示例': ['20240101_Meta_APPINSTALL_Retargeting_Carousel',
                         '20240101_TikTok_PRODUCT_SALES_NewUser_SquareVideo']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['tip', 'naming', 'organization'],
            'confidence': 0.85,
            'usage_count': 0
        },
        {
            'entry_id': 'tip_learning_phase',
            'knowledge_type': KnowledgeType.TIP,
            'platform': 'meta',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '学习期优化技巧',
                'description': 'Meta 广告学习期需要足够的转化数据',
                'tips': [
                    '每个 AdGroup 每周需要 50+ 转化才能完成学习',
                    '学习期间不要频繁修改设置',
                    '使用 CBO 可以加速学习过程',
                    '保持预算稳定，避免大幅波动'
                ]
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['tip', 'learning-phase', 'optimization'],
            'confidence': 0.9,
            'usage_count': 0
        },
        {
            'entry_id': 'tip_audience_overlap',
            'knowledge_type': KnowledgeType.TIP,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '受众重叠检查技巧',
                'description': '避免同一受众在不同 AdGroup 中重复竞价',
                'tips': [
                    '使用 Meta 的 Audience Overlap 工具检查',
                    '相似受众重叠度应低于 30%',
                    '分层投放：冷流量 + 热流量分开',
                    '定期清理低效受众'
                ]
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['tip', 'audience', 'optimization'],
            'confidence': 0.88,
            'usage_count': 0
        }
    ]
    
    for tip in tips:
        tip_kb.add(KnowledgeEntry(**tip))
    
    print("✅ 经验层知识库初始化完成")


if __name__ == '__main__':
    init_expertise_knowledge()
