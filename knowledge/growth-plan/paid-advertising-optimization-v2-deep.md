# 付费投放优化深度实现 - 资深专家深度实现

## 一、投放策略框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   付费投放优化流程                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. 目标设定 → 2. 预算分配 → 3. 渠道选择 → 4. 创意测试                  │
│         ↓           ↓           ↓           ↓                          │
│   5. 数据追踪 → 6. 效果分析 → 7. 优化迭代 → 8. 规模扩张                  │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、投放优化实现

```python
import numpy as np

class AdOptimizer:
    def __init__(self):
        self.budget = 100000
        self.channels = ['facebook', 'google', 'tiktok', 'wechat']
    
    def allocate_budget(self) -> dict:
        """预算分配"""
        # 基于历史ROI动态分配
        roi_by_channel = {
            'facebook': 3.5,
            'google': 4.2,
            'tiktok': 2.8,
            'wechat': 5.1
        }
        
        total_roi = sum(roi_by_channel.values())
        allocation = {
            channel: (roi / total_roi) * self.budget
            for channel, roi in roi_by_channel.items()
        }
        
        return allocation
    
    def test_creative(self, creatives: list) -> dict:
        """创意测试"""
        results = {}
        for creative in creatives:
            # 模拟A/B测试
            ctr = np.random.uniform(0.02, 0.08)
            cvr = np.random.uniform(0.05, 0.15)
            results[creative['id']] = {
                'ctr': ctr,
                'cvr': cvr,
                'cost_per_click': 2.5,
                'cost_per_action': 2.5 / cvr
            }
        
        # 选择最优创意
        best = max(results.items(), key=lambda x: x[1]['cvr'])
        return {
            'results': results,
            'winner': best[0],
            'winner_metrics': best[1]
        }
    
    def optimize_bidding(self, bid_strategy: str) -> dict:
        """出价优化"""
        strategies = {
            'manual': {'control': 'full', 'efficiency': 'medium'},
            'auto': {'control': 'low', 'efficiency': 'high'},
            'target_roas': {'control': 'medium', 'efficiency': 'highest'}
        }
        return strategies.get(bid_strategy, strategies['manual'])
    
    def calculate_roi(self, spend: float, revenue: float) -> float:
        """计算ROI"""
        return (revenue - spend) / spend * 100
    
    def forecast_performance(self, budget: float, channel: str) -> dict:
        """性能预测"""
        baselines = {
            'facebook': {'ctr': 0.03, 'cvr': 0.08},
            'google': {'ctr': 0.04, 'cvr': 0.12},
            'tiktok': {'ctr': 0.02, 'cvr': 0.05}
        }
        
        baseline = baselines.get(channel, baselines['facebook'])
        estimated_impressions = budget / baseline['ctr'] / 2.5
        estimated_conversions = estimated_impressions * baseline['cvr']
        
        return {
            'channel': channel,
            'budget': budget,
            'estimated_impressions': int(estimated_impressions),
            'estimated_conversions': int(estimated_conversions),
            'estimated_cpa': budget / estimated_conversions if estimated_conversions > 0 else 0
        }
```

## 三、面试高频题

### Q1: 如何优化投放ROI？

```
1. 提高CTR (创意优化)
2. 提高CVR (落地页优化)
3. 降低CPA (出价优化)
4. 提高LTV (用户质量筛选)
```

### Q2: 如何处理超成本？

```
1. 立即暂停广告
2. 分析原因 (素材/定向/出价)
3. 调整策略后重新投放
```

## 四、自测题

1. 预算分配方法？
2. A/B测试设计？
3. ROI计算？

---

## 参考文档

- [Ad Optimization](https://hubspot.com/marketing/advertising)
- [Media Buying](https://www.wordstream.com/blog/ws/2016/10/25/how-to-calculate-roi)
