#!/usr/bin/env python3
"""
添加更多错误模式和案例研究
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


def add_more_errors_and_cases():
    """添加更多错误模式和案例研究"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    ep_kb = kb.expertise_kbs['error_patterns']
    cs_kb = kb.expertise_kbs['case_studies']
    
    # ==================== 更多错误模式 ====================
    error_patterns = [
        {
            'entry_id': 'ep_invalid_targeting',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'meta',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'INVALID_TARGETING',
                'error_message': 'Invalid targeting specification',
                'cause': '定向参数格式错误或地区不支持',
                'solutions': [
                    '检查 location_ids 是否在支持列表中',
                    '使用 audiences/search 验证定向参数',
                    '确认目标地区广告政策合规'
                ],
                '常见场景': ['创建 AdSet', '修改定向']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'targeting', 'meta'],
            'confidence': 0.92,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_insufficient_budget',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'all',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'INSUFFICIENT_BALANCE',
                'error_message': 'Insufficient account balance',
                'cause': '账户余额不足或付款方案未设置',
                'solutions': [
                    '检查账户余额',
                    '添加付款方案',
                    '联系平台客服解锁额度'
                ],
                '常见场景': ['Campaign 创建', '预算调整']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'budget', 'payment'],
            'confidence': 0.95,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_pixel_not_found',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'meta',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'PIXEL_NOT_FOUND',
                'error_message': 'Pixel ID is invalid or not accessible',
                'cause': 'Pixel ID 错误或无权访问',
                'solutions': [
                    '检查 Pixel ID 是否正确',
                    '确认 Pixel 所有权',
                    '使用 Business Manager 授权'
                ],
                '常见场景': ['转化追踪设置', 'Ad 创建']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'pixel', 'meta'],
            'confidence': 0.9,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_creative_rejected',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'all',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'CREATIVE_REJECTED',
                'error_message': 'Ad creative was rejected due to policy violation',
                'cause': '素材违反平台广告政策',
                'solutions': [
                    '查看拒绝原因详情',
                    '修改素材后重新提交',
                    '联系平台审核团队申诉'
                ],
                '常见场景': ['素材审核', '广告上线']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'creative', 'policy'],
            'confidence': 0.93,
            'usage_count': 0
        },
        {
            'entry_id': 'ep_google_ads_404',
            'knowledge_type': KnowledgeType.ERROR_PATTERN,
            'platform': 'google',
            'source': KnowledgeSource.API_TEST,
            'content': {
                'error_code': 'NOT_FOUND',
                'error_message': 'Customer ID not found or access denied',
                'cause': '客户ID错误或权限不足',
                'solutions': [
                    '检查 Customer ID 格式（需去掉连字符）',
                    '确认开发者令牌权限',
                    '联系 Google Ads 支持'
                ],
                '常见场景': ['API 调用', '账户查询']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['error', 'google', 'api'],
            'confidence': 0.88,
            'usage_count': 0
        }
    ]
    
    for ep in error_patterns:
        ep_kb.add(KnowledgeEntry(**ep))
    
    # ==================== 案例研究 ====================
    case_studies = [
        {
            'entry_id': 'case_ecommerce_roas_optimization',
            'knowledge_type': KnowledgeType.CASE_STUDY,
            'platform': 'meta',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '电商客户 ROAS 优化案例',
                'description': '通过精细化定向和素材优化，将 ROAS 从 2.5 提升至 4.8',
                'business_type': 'ecommerce',
                'challenge': '初期 ROAS 仅 2.5，远低于目标 4.0',
                'solution': [
                    '拆分 AdGroup 按产品类别',
                    '为高价值产品设置独立 Campaign',
                    '使用动态商品广告（DPA）',
                    '优化素材展示产品卖点'
                ],
                'results': {
                    'roas_before': 2.5,
                    'roas_after': 4.8,
                    'improvement': '92%'
                },
                'key_learnings': [
                    '细分受众比泛定向效果更好',
                    '动态素材能显著提升 CTR',
                    '持续 A/B 测试是优化的关键'
                ]
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['case-study', 'ecommerce', 'roas', 'optimization'],
            'confidence': 0.85,
            'usage_count': 0
        },
        {
            'entry_id': 'case_app_install_scaling',
            'knowledge_type': KnowledgeType.CASE_STUDY,
            'platform': 'tiktok',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': '游戏 App 安装量规模化案例',
                'description': '通过 UGC 素材和 KOL 合作，将 CPI 降低 40%',
                'business_type': 'gaming',
                'challenge': '新游戏上线，需要快速获得大量安装',
                'solution': [
                    '制作 10+ 种 UGC 风格素材',
                    '与 TikTok 游戏 KOL 合作',
                    '使用 APP_INSTALLS 目标优化',
                    '设置 CBO 自动预算分配'
                ],
                'results': {
                    'installs_before': '500/day',
                    'installs_after': '2000/day',
                    'cpi_reduction': '40%'
                },
                'key_learnings': [
                    'UGC 素材在 TikTok 表现最佳',
                    'KOL 合作能快速提升品牌认知',
                    'CBO 适合放量阶段'
                ]
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['case-study', 'gaming', 'app-install', 'scaling'],
            'confidence': 0.88,
            'usage_count': 0
        },
        {
            'entry_id': 'case_google_search_leads',
            'knowledge_type': KnowledgeType.CASE_STUDY,
            'platform': 'google',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'title': 'B2B 线索收集案例',
                'description': '通过搜索广告和落地页优化，将线索成本降低 35%',
                'business_type': 'b2b',
                'challenge': '线索成本高（$50/条），转化率仅 2%',
                'solution': [
                    '优化关键词匹配类型',
                    '添加否定关键词排除无关流量',
                    '改进落地页加载速度',
                    '使用智能出价（Target CPA）'
                ],
                'results': {
                    'cpl_before': 50,
                    'cpl_after': 32.5,
                    'conversion_rate_before': '2%',
                    'conversion_rate_after': '4.5%'
                },
                'key_learnings': [
                    '否定关键词能显著降低成本',
                    '落地页体验直接影响转化',
                    '智能出价需要足够转化数据'
                ]
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['case-study', 'b2b', 'leads', 'google-search'],
            'confidence': 0.82,
            'usage_count': 0
        }
    ]
    
    for cs in case_studies:
        cs_kb.add(KnowledgeEntry(**cs))
    
    print("✅ 错误模式和案例研究添加完成")


if __name__ == '__main__':
    add_more_errors_and_cases()
