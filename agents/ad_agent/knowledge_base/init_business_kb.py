#!/usr/bin/env python3
"""
业务层知识库初始化脚本
包含：业务策略、出价策略、定向策略、素材指南
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base import (
    LLMWikiKnowledgeBase, KnowledgeType, KnowledgeSource,
    BusinessStrategyKB, BiddingStrategyKB, TargetingStrategyKB, CreativeGuideKB,
    KnowledgeEntry
)


def init_business_knowledge():
    """初始化业务层知识"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== 业务策略 ====================
    business_strategy_kb = kb.business_kbs['strategy']
    
    # 电商业务策略
    ecommerce_strategy = {
        'entry_id': 'strategy_ecommerce_general',
        'knowledge_type': KnowledgeType.BUSINESS_STRATEGY,
        'platform': 'all',
        'source': KnowledgeSource.MANUAL_EXPERT,
        'source_ref': 'Ryan-Expert-Skills',
        'content': {
            'business_type': 'ecommerce',
            'description': '电商类业务通用策略',
            'objectives': ['CONVERSIONS', 'PURCHASE'],
            'targeting': {
                'interests': ['Shopping', 'E-commerce', 'Online shopping'],
                'lookalike': 'Recommended: 1-3% similarity',
                'retargeting': 'Cart abandoners, product viewers'
            },
            'budget_recommendation': {
                'daily_min': 50,
                'daily_recommended': 100,
                'currency': 'USD'
            },
            'bidding': {
                'strategy': 'Cost cap or Target ROAS',
                'roas_target': 300
            },
            'creative_tips': [
                'Use carousel ads for product catalog',
                'Show product benefits in first 3 seconds',
                'Include social proof (reviews, ratings)'
            ]
        },
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'tags': ['ecommerce', 'business', 'strategy'],
        'metadata': {'version': '1.0', 'confidence': 0.9},
        'confidence': 0.9,
        'usage_count': 0
    }
    business_strategy_kb.add(KnowledgeEntry(**ecommerce_strategy))
    
    # 游戏业务策略
    gaming_strategy = {
        'entry_id': 'strategy_gaming_general',
        'knowledge_type': KnowledgeType.BUSINESS_STRATEGY,
        'platform': 'all',
        'source': KnowledgeSource.MANUAL_EXPERT,
        'source_ref': 'Ryan-Expert-Skills',
        'content': {
            'business_type': 'gaming',
            'description': '游戏类业务通用策略',
            'objectives': ['APP_INSTALLS', 'EVENTS'],
            'targeting': {
                'interests': ['Mobile games', 'Gaming', 'Entertainment'],
                'behavior': ['Mobile app users', 'Game players'],
                'lookalike': 'Recommended: 1-5% similarity'
            },
            'budget_recommendation': {
                'daily_min': 100,
                'daily_recommended': 500,
                'currency': 'USD'
            },
            'bidding': {
                'strategy': 'Lowest cost with cap',
                'bid_cap': 2.0
            },
            'creative_tips': [
                'Show gameplay footage in first 5 seconds',
                'Use UGC-style creatives',
                'Highlight unique game features'
            ]
        },
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'tags': ['gaming', 'business', 'strategy'],
        'metadata': {'version': '1.0', 'confidence': 0.85},
        'confidence': 0.85,
        'usage_count': 0
    }
    business_strategy_kb.add(KnowledgeEntry(**gaming_strategy))
    
    # App 推广策略
    app_strategy = {
        'entry_id': 'strategy_app_general',
        'knowledge_type': KnowledgeType.BUSINESS_STRATEGY,
        'platform': 'all',
        'source': KnowledgeSource.MANUAL_EXPERT,
        'source_ref': 'Ryan-Expert-Skills',
        'content': {
            'business_type': 'app',
            'description': 'App 推广通用策略',
            'objectives': ['APP_INSTALLS', 'APP_EVENTS'],
            'targeting': {
                'interests': ['Mobile apps', 'Technology'],
                'lookalike': 'Recommended: 1-3% similarity'
            },
            'budget_recommendation': {
                'daily_min': 50,
                'daily_recommended': 200,
                'currency': 'USD'
            },
            'bidding': {
                'strategy': 'Lowest cost',
                'bid_cap': 1.5
            },
            'creative_tips': [
                'Show app interface in screenshots',
                'Highlight app benefits',
                'Use video demos'
            ]
        },
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'tags': ['app', 'business', 'strategy'],
        'metadata': {'version': '1.0', 'confidence': 0.8},
        'confidence': 0.8,
        'usage_count': 0
    }
    business_strategy_kb.add(KnowledgeEntry(**app_strategy))
    
    # ==================== 出价策略 ====================
    bidding_kb = kb.business_kbs['bidding']
    
    bidding_strategies = [
        {
            'entry_id': 'bidding_cost_efficiency',
            'knowledge_type': KnowledgeType.BIDDING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'objective': 'cost_efficiency',
                'description': '成本效率优先出价策略',
                'strategy_name': 'Lowest Cost',
                'description_detail': '适用于预算有限、追求最大转化量的场景',
                'bid_suggestion': {
                    'bid_type': 'NO_BID',
                    'cost_cap': None,
                    'roas_target': None
                },
                '适用场景': ['冷启动', '预算测试', '放量阶段']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['bidding', 'cost_efficiency'],
            'confidence': 0.9,
            'usage_count': 0
        },
        {
            'entry_id': 'bidding_target_roas',
            'knowledge_type': KnowledgeType.BIDDING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'objective': 'target_roas',
                'description': '目标 ROI 出价策略',
                'strategy_name': 'Target ROAS',
                'description_detail': '适用于有明确 ROI 目标的电商业务',
                'bid_suggestion': {
                    'bid_type': 'TARGET_ROAS',
                    'roas_target': 300  # 300%
                },
                '适用场景': ['稳定投放期', '电商转化', '效果优化']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['bidding', 'roas'],
            'confidence': 0.85,
            'usage_count': 0
        },
        {
            'entry_id': 'bidding_cost_cap',
            'knowledge_type': KnowledgeType.BIDDING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'objective': 'cost_control',
                'description': '成本上限出价策略',
                'strategy_name': 'Cost Cap',
                'description_detail': '控制单次转化成本在指定范围内',
                'bid_suggestion': {
                    'bid_type': 'COST_CAP',
                    'cost_cap': 10.0  # $10
                },
                '适用场景': ['成本敏感', '稳定期优化']
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['bidding', 'cost_cap'],
            'confidence': 0.8,
            'usage_count': 0
        }
    ]
    
    for bid in bidding_strategies:
        bidding_kb.add(KnowledgeEntry(**bid))
    
    # ==================== 定向策略 ====================
    targeting_kb = kb.business_kbs['targeting']
    
    targeting_strategies = [
        {
            'entry_id': 'targeting_interest_based',
            'knowledge_type': KnowledgeType.TARGETING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'strategy_name': '兴趣定向',
                'description': '基于用户兴趣标签的定向',
                '适用平台': ['meta', 'tiktok', 'google'],
                'recommendations': {
                    'meta': {
                        'interests': ['Shopping', 'Fashion', 'Electronics'],
                        'layers': 'Combine 2-3 interest layers'
                    },
                    'tiktok': {
                        'interests': ['Shopping', 'Fashion', 'Beauty'],
                        'dmp': 'Custom audience recommended'
                    },
                    'google': {
                        'audiences': ['In-market', 'Affinity'],
                        'keywords': 'Shopping-related keywords'
                    }
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['targeting', 'interest'],
            'confidence': 0.85,
            'usage_count': 0
        },
        {
            'entry_id': 'targeting_lookalike',
            'knowledge_type': KnowledgeType.TARGETING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'strategy_name': '相似受众',
                'description': '基于种子受众的相似人群扩展',
                '适用平台': ['meta', 'tiktok', 'google'],
                'recommendations': {
                    'seed_source': ['Customer list', 'Website visitors', 'App users'],
                    'similarity_range': '1-5%',
                    'optimization': 'Larger seed = better performance'
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['targeting', 'lookalike'],
            'confidence': 0.9,
            'usage_count': 0
        },
        {
            'entry_id': 'targeting_retargeting',
            'knowledge_type': KnowledgeType.TARGETING_STRATEGY,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'strategy_name': '再营销',
                'description': '针对已有互动的用户进行再营销',
                '适用平台': ['meta', 'tiktok', 'google'],
                'recommendations': {
                    'cart_abandoners': 'High priority, short window (7-30 days)',
                    'product_viewers': 'Medium priority, longer window (30-90 days)',
                    'past_customers': 'Highest priority, longest window (90+ days)'
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['targeting', 'retargeting'],
            'confidence': 0.95,
            'usage_count': 0
        }
    ]
    
    for target in targeting_strategies:
        targeting_kb.add(KnowledgeEntry(**target))
    
    # ==================== 素材指南 ====================
    creative_kb = kb.business_kbs['creative']
    
    creative_guides = [
        {
            'entry_id': 'creative_video_spec',
            'knowledge_type': KnowledgeType.CREATIVE_GUIDE,
            'platform': 'all',
            'source': KnowledgeSource.OFFICIAL_DOCS,
            'content': {
                'guide_type': 'video_specifications',
                'description': '视频素材规格要求',
                'platforms': {
                    'meta': {
                        'supported_formats': ['MP4', 'MOV'],
                        'recommended_size': '1080x1080 (1:1)',
                        'min_duration': 4,
                        'max_duration': 240,
                        'file_size_limit': '4GB'
                    },
                    'tiktok': {
                        'supported_formats': ['MP4', 'MOV'],
                        'recommended_size': '1080x1920 (9:16)',
                        'min_duration': 0.5,
                        'max_duration': 60,
                        'file_size_limit': '72MB'
                    },
                    'google': {
                        'supported_formats': ['MP4', 'MOV', 'WebM'],
                        'recommended_size': '1920x1080 (16:9)',
                        'min_duration': 4,
                        'max_duration': 300,
                        'file_size_limit': '1GB'
                    }
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['creative', 'video', 'spec'],
            'confidence': 1.0,
            'usage_count': 0
        },
        {
            'entry_id': 'creative_image_spec',
            'knowledge_type': KnowledgeType.CREATIVE_GUIDE,
            'platform': 'all',
            'source': KnowledgeSource.OFFICIAL_DOCS,
            'content': {
                'guide_type': 'image_specifications',
                'description': '图片素材规格要求',
                'platforms': {
                    'meta': {
                        'supported_formats': ['JPG', 'PNG', 'GIF'],
                        'recommended_size': '1200x628 (1.91:1)',
                        'min_size': '600x600',
                        'file_size_limit': '30MB'
                    },
                    'tiktok': {
                        'supported_formats': ['JPG', 'PNG'],
                        'recommended_size': '1080x1080 (1:1)',
                        'file_size_limit': '5MB'
                    },
                    'google': {
                        'supported_formats': ['JPG', 'PNG', 'GIF'],
                        'recommended_size': '1200x628 (1.91:1)',
                        'file_size_limit': '5MB'
                    }
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['creative', 'image', 'spec'],
            'confidence': 1.0,
            'usage_count': 0
        },
        {
            'entry_id': 'creative_best_practices',
            'knowledge_type': KnowledgeType.CREATIVE_GUIDE,
            'platform': 'all',
            'source': KnowledgeSource.MANUAL_EXPERT,
            'content': {
                'guide_type': 'best_practices',
                'description': '素材创作最佳实践',
                'tips': [
                    'Hook viewers in first 3 seconds',
                    'Use text overlay for sound-off viewing',
                    'Show product in use',
                    'Include clear CTA',
                    'Test multiple creative variations'
                ],
                'a_b_testing': {
                    'recommended': True,
                    'min_variants': 3,
                    'test_duration': '7 days'
                }
            },
            'created_at': datetime.now().isoformat(),
            'tags': ['creative', 'best_practices'],
            'confidence': 0.85,
            'usage_count': 0
        }
    ]
    
    for guide in creative_guides:
        creative_kb.add(KnowledgeEntry(**guide))
    
    print("✅ 业务层知识库初始化完成")


if __name__ == '__main__':
    init_business_knowledge()
