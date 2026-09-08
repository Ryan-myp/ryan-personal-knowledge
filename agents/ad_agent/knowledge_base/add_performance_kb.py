#!/usr/bin/env python3.13
"""
添加性能基准数据到知识库
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


def add_performance_data():
    """添加性能基准数据"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb = LLMWikiKnowledgeBase(base_path)
    
    # ==================== TikTok 性能基准 ====================
    tiktok_perf = KnowledgeEntry(
        entry_id="tiktok_performance_benchmark",
        knowledge_type=KnowledgeType.PERFORMANCE_DATA,
        platform="tiktok",
        content={
            "data_type": "performance_benchmark",
            "description": "TikTok 广告性能基准数据（2024年）",
            "benchmarks": {
                "ctr": {
                    "video_ads": {"min": 0.5, "avg": 1.2, "max": 3.0, "unit": "%"},
                    "image_ads": {"min": 0.3, "avg": 0.8, "max": 2.0, "unit": "%"}
                },
                "cpc": {
                    "app_installs": {"min": 0.5, "avg": 1.5, "max": 5.0, "currency": "USD"},
                    "website_traffic": {"min": 0.3, "avg": 1.0, "max": 3.0, "currency": "USD"}
                },
                "cpm": {
                    "general": {"min": 2.0, "avg": 5.0, "max": 15.0, "currency": "USD"}
                },
                "conversion_rate": {
                    "app_installs": {"min": 5, "avg": 15, "max": 30, "unit": "%"},
                    "purchases": {"min": 1, "avg": 3, "max": 10, "unit": "%"}
                }
            },
            "factors_affecting_performance": [
                "创意质量（前3秒留存率）",
                "受众匹配度",
                "投放时段",
                "地理位置"
            ],
            "optimization_tips": [
                "使用竖版视频（9:16）获得更好效果",
                "前3秒必须抓住注意力",
                "添加字幕提高无声观看体验",
                "测试多种创意变体"
            ]
        },
        source=KnowledgeSource.HISTORICAL_DATA,
        source_ref="Ryan-Expert-Skills+Industry Report 2024",
        created_at=datetime.now().isoformat(),
        tags=["tiktok", "performance", "benchmark"],
        metadata={"verified": True, "last_updated": "2024-08"}
    )
    kb.dynamic_kbs['performance'].add(tiktok_perf)
    
    # ==================== Meta 性能基准 ====================
    meta_perf = KnowledgeEntry(
        entry_id="meta_performance_benchmark",
        knowledge_type=KnowledgeType.PERFORMANCE_DATA,
        platform="meta",
        content={
            "data_type": "performance_benchmark",
            "description": "Meta 广告性能基准数据（2024年）",
            "benchmarks": {
                "ctr": {
                    "feed_ads": {"min": 0.5, "avg": 0.9, "max": 2.0, "unit": "%"},
                    "story_ads": {"min": 0.8, "avg": 1.5, "max": 3.0, "unit": "%"},
                    "reels_ads": {"min": 1.0, "avg": 2.0, "max": 4.0, "unit": "%"}
                },
                "cpc": {
                    "clicks": {"min": 0.2, "avg": 0.8, "max": 3.0, "currency": "USD"},
                    "link_clicks": {"min": 0.3, "avg": 1.0, "max": 4.0, "currency": "USD"}
                },
                "cpm": {
                    "general": {"min": 5.0, "avg": 10.0, "max": 25.0, "currency": "USD"}
                },
                "conversion_rate": {
                    "lead_generation": {"min": 5, "avg": 15, "max": 30, "unit": "%"},
                    "purchases": {"min": 1, "avg": 2.5, "max": 8, "unit": "%"}
                }
            },
            "factors_affecting_performance": [
                "创意相关性",
                "受众精准度",
                "出价竞争力",
                "账户质量得分"
            ],
            "optimization_tips": [
                "使用 Advantage+ 创意自动优化",
                "保持受众重叠度低于 30%",
                "定期更新创意避免疲劳",
                "利用 Lookalike 受众扩展"
            ]
        },
        source=KnowledgeSource.HISTORICAL_DATA,
        source_ref="Meta Benchmark Report 2024",
        created_at=datetime.now().isoformat(),
        tags=["meta", "performance", "benchmark"],
        metadata={"verified": True, "last_updated": "2024-08"}
    )
    kb.dynamic_kbs['performance'].add(meta_perf)
    
    # ==================== Google Ads 性能基准 ====================
    google_perf = KnowledgeEntry(
        entry_id="google_performance_benchmark",
        knowledge_type=KnowledgeType.PERFORMANCE_DATA,
        platform="google",
        content={
            "data_type": "performance_benchmark",
            "description": "Google Ads 性能基准数据（2024年）",
            "benchmarks": {
                "ctr": {
                    "search_ads": {"min": 2.0, "avg": 3.5, "max": 8.0, "unit": "%"},
                    "display_ads": {"min": 0.1, "avg": 0.3, "max": 0.5, "unit": "%"},
                    "video_ads": {"min": 0.5, "avg": 1.0, "max": 2.0, "unit": "%"}
                },
                "cpc": {
                    "search": {"min": 0.5, "avg": 2.5, "max": 10.0, "currency": "USD"},
                    "display": {"min": 0.1, "avg": 0.5, "max": 2.0, "currency": "USD"}
                },
                "cpm": {
                    "display": {"min": 1.0, "avg": 3.0, "max": 10.0, "currency": "USD"}
                },
                "conversion_rate": {
                    "search": {"min": 2, "avg": 5, "max": 15, "unit": "%"},
                    "shopping": {"min": 1, "avg": 3, "max": 8, "unit": "%"}
                }
            },
            "factors_affecting_performance": [
                "关键词质量得分",
                "广告相关性",
                "落地页体验",
                "出价策略"
            ],
            "optimization_tips": [
                "使用 Smart Bidding 策略",
                "保持质量得分 7+ 以上",
                "定期清理低效关键词",
                "利用扩展（Extensions）提高 CTR"
            ]
        },
        source=KnowledgeSource.HISTORICAL_DATA,
        source_ref="Google Ads Benchmark 2024",
        created_at=datetime.now().isoformat(),
        tags=["google", "performance", "benchmark"],
        metadata={"verified": True, "last_updated": "2024-08"}
    )
    kb.dynamic_kbs['performance'].add(google_perf)
    
    print("✅ 性能基准数据添加完成")


if __name__ == '__main__':
    add_performance_data()
