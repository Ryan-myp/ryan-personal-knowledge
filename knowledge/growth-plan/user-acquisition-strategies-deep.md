# 用户获取策略深度实现 - 资深专家深度实现

## 一、获取渠道矩阵

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   用户获取渠道分类                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   渠道类型    │ 成本    │ 质量    │ 规模    │ 适合场景                 │
│   ───────────┼─────────┼────────┼────────┼─────────────────────────│
│   SEO/SEM    │ 中     │ 高     │ 大     │ 长期品牌建设             │
│   社交广告   │ 高     │ 中     │ 大     │ 快速获客                 │
│   KOL合作    │ 高     │ 高     │ 中     │ 垂直领域                 │
│   内容营销   │ 低     │ 高     │ 中     │ 知识型产品               │
│   裂变增长   │ 低     │ 中     │ 大     │ 社交属性强               │
│   应用商店   │ 中     │ 中     │ 大     │ 移动应用                 │
│   线下活动   │ 高     │ 高     │ 小     │ 本地化产品               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、渠道评估模型

```python
class ChannelEvaluator:
    def __init__(self):
        self.channels = {}
    
    def add_channel(self, name: str, metrics: dict):
        """添加渠道"""
        self.channels[name] = {
            'cost': metrics['cost'],
            'clicks': metrics['clicks'],
            'conversions': metrics['conversions'],
            'arpu': metrics['arpu'],
            'retention': metrics['retention']
        }
    
    def calculate_metrics(self) -> dict:
        """计算各渠道指标"""
        results = {}
        for name, data in self.channels.items():
            cpc = data['cost'] / data['clicks'] if data['clicks'] > 0 else float('inf')
            cvr = data['conversions'] / data['clicks'] if data['clicks'] > 0 else 0
            cac = cpc / cvr if cvr > 0 else float('inf')
            ltv = data['arpu'] / (1 - data['retention']) if data['retention'] < 1 else float('inf')
            roi = ltv / cac if cac > 0 else 0
            
            results[name] = {
                'cpc': cpc,
                'cvr': cvr,
                'cac': cac,
                'ltv': ltv,
                'roi': roi,
                'quality_score': self.quality_score(data)
            }
        return results
    
    def quality_score(self, metrics: dict) -> float:
        """渠道质量评分"""
        retention_weight = 0.4
        ltv_weight = 0.3
        cost_weight = 0.3
        
        return (
            metrics['retention'] * retention_weight +
            min(metrics['arpu'] / 100, 1.0) * ltv_weight +
            (1 - min(metrics['cost'] / 1000, 1.0)) * cost_weight
        )
    
    def recommend_channels(self, budget: float) -> list:
        """推荐渠道组合"""
        metrics = self.calculate_metrics()
        
        # 按ROI排序
        sorted_channels = sorted(
            metrics.items(),
            key=lambda x: x[1]['roi'],
            reverse=True
        )
        
        # 贪心算法分配预算
        allocation = []
        remaining_budget = budget
        for name, m in sorted_channels:
            if remaining_budget <= 0:
                break
            allocate = min(remaining_budget, m['cac'] * 100)  # 假设最多获取100用户
            allocation.append({
                'channel': name,
                'budget': allocate,
                'expected_users': allocate / m['cac'] if m['cac'] > 0 else 0
            })
            remaining_budget -= allocate
        
        return allocation
```

## 三、获客成本优化

```python
class CACOptimizer:
    def __init__(self):
        self.target_cac = 50.0  # 目标CAC
    
    def optimize_bidding(self, current_bid: float, cvr: float) -> float:
        """优化出价策略"""
        # 基于CVR调整出价
        optimal_bid = self.target_cac * cvr
        return max(0.1, optimal_bid)
    
    def calculate_break_even_cac(self, ltv: float, margin: float = 0.3) -> float:
        """计算盈亏平衡CAC"""
        return ltv * margin
    
    def dynamic_pricing(self, demand: float, supply: float) -> float:
        """动态定价"""
        ratio = demand / supply if supply > 0 else 1.0
        base_price = 10.0
        return base_price * (1 + ratio * 0.5)
```

## 四、归因模型

```python
class AttributionModel:
    def __init__(self, model_type: str = 'last_click'):
        self.model_type = model_type
    
    def last_click(self, touches: list) -> dict:
        """最后点击归因"""
        return {touches[-1]: 1.0}
    
    def first_click(self, touches: list) -> dict:
        """首次点击归因"""
        return {touches[0]: 1.0}
    
    def linear(self, touches: list) -> dict:
        """线性归因"""
        credit = 1.0 / len(touches)
        return {touch: credit for touch in touches}
    
    def time_decay(self, touches: list, half_life: float = 7.0) -> dict:
        """时间衰减归因"""
        import math
        total = 0
        credits = {}
        
        for i, touch in enumerate(reversed(touches)):
            days_ago = i
            weight = 0.5 ** (days_ago / half_life)
            credits[touch] = weight
            total += weight
        
        # 归一化
        for touch in credits:
            credits[touch] /= total
        
        return credits
    
    def data_driven(self, conversion_data: list) -> dict:
        """数据驱动归因 (Shapley值)"""
        # 简化版实现
        attribution = {}
        for conversion in conversion_data:
            touches = conversion['touches']
            for i, touch in enumerate(touches):
                position_weight = (i + 1) / len(touches)
                attribution[touch] = attribution.get(touch, 0) + position_weight
        
        # 归一化
        total = sum(attribution.values())
        if total > 0:
            for touch in attribution:
                attribution[touch] /= total
        
        return attribution
```

## 五、面试高频题

### Q1: 如何计算CAC？

```
CAC = 营销总成本 / 新增用户数
```

### Q2: 归因模型有哪些？

```
1. 最后点击归因
2. 首次点击归因
3. 线性归因
4. 时间衰减归因
5. 数据驱动归因 (Shapley值)
```

## 六、自测题

1. 如何评估渠道质量？
2. 什么场景适合裂变增长？
3. 归因模型如何选择？

---

## 参考文档

- [Channel Evaluation](https://www.growthhackers.com/articles/user-acquisition)
- [Attribution Models](https://blog.hubspot.com/marketing/attribution-models)
