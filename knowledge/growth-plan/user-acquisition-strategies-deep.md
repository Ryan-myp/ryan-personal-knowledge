# 用户获取策略深度实现 - 资深专家深度实现

## 一、获客策略框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   用户获取策略矩阵                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   策略类型        │ 成本              │ 速度              │ 持续性        │
│   ────────────────┼─────────────────┼─────────────────┼─────────────│
│   内容营销        │ 低               │ 慢               │ 高           │
│   ────────────────┼─────────────────┼─────────────────┼─────────────│
│   SEO/SEM        │ 中-高            │ 中               │ 中           │
│   ────────────────┼─────────────────┼─────────────────┼─────────────│
│   社交裂变        │ 低               │ 快               │ 中           │
│   ────────────────┼─────────────────┼─────────────────┼─────────────│
│   KOL合作        │ 高               │ 快               │ 低           │
│   ────────────────┼─────────────────┼─────────────────┼─────────────│
│   付费广告        │ 高               │ 最快             │ 低           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、获客渠道实现

```python
class AcquisitionChannel:
    def __init__(self, name: str, cost_model: str):
        self.name = name
        self.cost_model = cost_model  # 'cpc', 'cpm', 'cpa'
        self.metrics = {}
    
    def track_performance(self, data: dict):
        """追踪渠道表现"""
        self.metrics = {
            'impressions': data.get('impressions', 0),
            'clicks': data.get('clicks', 0),
            'conversions': data.get('conversions', 0),
            'cost': data.get('cost', 0)
        }
        self.calculate_kpis()
    
    def calculate_kpis(self):
        """计算关键指标"""
        m = self.metrics
        m['ctr'] = m['clicks'] / m['impressions'] if m['impressions'] > 0 else 0
        m['cvr'] = m['conversions'] / m['clicks'] if m['clicks'] > 0 else 0
        m['cac'] = m['cost'] / m['conversions'] if m['conversions'] > 0 else float('inf')
        m['cost_per_click'] = m['cost'] / m['clicks'] if m['clicks'] > 0 else 0
    
    def is_profitable(self, ltv: float) -> bool:
        """是否盈利"""
        return self.metrics.get('cac', float('inf')) < ltv / 3

class AcquisitionOptimizer:
    def __init__(self):
        self.channels = {}
        self.budget = 100000
    
    def allocate_budget(self) -> dict:
        """预算分配"""
        allocation = {}
        for name, channel in self.channels.items():
            roi = self.calculate_channel_roi(name)
            allocation[name] = {
                'budget': self.budget * (roi / sum(self.channels[c].calculate_channel_roi(c) for c in self.channels)),
                'expected_users': self.estimate_users(name, roi)
            }
        return allocation
    
    def calculate_channel_roi(self, channel: str) -> float:
        """计算渠道ROI"""
        c = self.channels[channel]
        if not c.metrics.get('conversions', 0):
            return 0
        revenue = c.metrics['conversions'] * 100  # 假设ARPU=100
        return revenue / c.metrics['cost'] if c.metrics['cost'] > 0 else 0
```

## 三、面试高频题

### Q1: 如何选择获客渠道？

```
1. 目标用户在哪里
2. 渠道成本与LTV对比
3. 可规模和可持续性
```

### Q2: CAC和LTV的关系？

```
LTV/CAC ≥ 3 是健康标准
LTV:CAC = 1 时盈亏平衡
```

## 四、自测题

1. 获客渠道有哪些？
2. 如何计算CAC？
3. 如何判断渠道健康？

---

## 参考文档

- [Customer Acquisition](https://www.forbes.com/sites/forbestechcouncil/2021/07/06/customer-acquisition-cost/)
- [Growth Channels](https://www.growthhackers.com/growth-hacking/channels)
