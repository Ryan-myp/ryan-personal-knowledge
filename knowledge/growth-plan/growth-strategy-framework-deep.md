# 增长策略全景深度实现 - 资深专家深度实现

## 一、增长策略框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长策略全景                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   获取策略        │ 留存策略        │ 变现策略        │ 推荐策略          │
│   ────────────────┼────────────────┼────────────────┼─────────────────│
│   • SEO/SEM      │ • Push推送     │ • 定价策略     │ • 邀请奖励       │
│   • 内容营销     │ • 用户教育     │ • 会员体系     │ • 社交分享       │
│   • 渠道投放     │ • 产品优化     │ • 交叉销售     │ • 病毒裂变       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、策略实现

```python
class GrowthStrategy:
    def __init__(self):
        self.tactics = {}
    
    def acquire_users(self, channels: list) -> dict:
        """用户获取"""
        return {
            'channel': channels,
            'cac': self.calculate_cac(channels),
            'volume': self.estimate_volume(channels),
            'quality': self.assess_quality(channels)
        }
    
    def retain_users(self, strategies: list) -> dict:
        """用户留存"""
        return {
            'strategies': strategies,
            'retention_1d': 0.4,
            'retention_7d': 0.25,
            'retention_30d': 0.15
        }
    
    def monetize(self, pricing_model: str) -> dict:
        """变现策略"""
        models = {
            'freemium': {'arpu': 50, 'conversion': 0.05},
            'subscription': {'arpu': 100, 'churn': 0.05},
            'ad_based': {'arpu': 10, 'impression': 100}
        }
        return models.get(pricing_model, models['freemium'])
    
    def viral_loop(self, incentive: dict) -> dict:
        """病毒循环"""
        k_factor = incentive['invite_rate'] * incentive['conversion_rate']
        return {
            'k_factor': k_factor,
            'is_viral': k_factor > 1,
            'growth_prediction': self.predict_growth(k_factor)
        }
    
    def calculate_cac(self, channels: list) -> float:
        """计算获客成本"""
        total_cost = sum(self.channel_cost(c) for c in channels)
        total_users = sum(self.channel_users(c) for c in channels)
        return total_cost / total_users if total_users > 0 else 0
    
    def predict_growth(self, k_factor: float, initial_users: int, periods: int) -> list:
        """预测增长"""
        growth = [initial_users]
        for _ in range(periods):
            new_users = growth[-1] * k_factor
            growth.append(growth[-1] + new_users)
        return growth
```

## 三、面试高频题

### Q1: 如何设计增长策略？

```
1. 明确北极星指标
2. 分析用户旅程
3. 识别增长杠杆
4. 设计实验验证
```

### Q2: 如何平衡增长和质量？

```
1. 关注LTV而非短期GMV
2. 建立质量预警机制
3. 持续优化留存
```

## 四、自测题

1. 增长策略框架？
2. 病毒系数计算？
3. CAC如何优化？

---

## 参考文档

- [Growth Strategy](https://www.growthhackers.com/growth-hacking)
- [Pirate Metrics](https://a16z.com/pirate-metrics-a-framework-for-startup-metrics/)
