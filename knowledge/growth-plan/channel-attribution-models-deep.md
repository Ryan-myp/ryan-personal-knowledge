# 渠道归因模型深度实现 - 资深专家深度实现

## 一、归因模型对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   渠道归因模型对比                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模型            │ 分配逻辑              │ 优点              │ 缺点          │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   最后点击        │ 100%给最后一个触点    │ 简单            │ 忽略前置触点  │
│   (Last Click)   │                     │                 │             │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   首次点击        │ 100%给第一个触点    │ 强调拉新        │ 忽略转化触点  │
│   (First Click)  │                     │                 │             │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   线性归因        │ 平均分配给所有触点  │ 公平            │ 无法体现重要性│
│   (Linear)       │                     │                 │             │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   时间衰减        │ 越接近转化权重越高  │ 合理            │ 参数需调优    │
│   (Time Decay)   │                     │                 │             │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   位置归因        │ 首尾各40%,中间20%  │ 平衡            │ 固定比例      │
│   (Position)     │                     │                 │             │
│   ───────────────┼─────────────────────┼─────────────────┼─────────────│
│   数据驱动        │ 基于历史数据学习  │ 最准确          │ 需要大量数据  │
│   (Data-Driven)  │                     │                 │             │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Shapley值归因

```python
import numpy as np
from itertools import combinations

class ShapleyAttribution:
    def __init__(self, channel_performance: dict):
        """
        channel_performance: {
            'channel_a': {'conversions': 100},
            'channel_b': {'conversions': 80},
            ...
        }
        """
        self.channels = list(channel_performance.keys())
        self.performance = channel_performance
    
    def coalition_value(self, coalition: list) -> float:
        """计算联盟价值"""
        value = 0
        for channel in coalition:
            value += self.performance.get(channel, {}).get('conversions', 0)
        return value
    
    def marginal_contribution(self, channel: str, coalition: list) -> float:
        """计算边际贡献"""
        coalition_without = [c for c in coalition if c != channel]
        value_with = self.coalition_value(coalition)
        value_without = self.coalition_value(coalition_without)
        return value_with - value_without
    
    def calculate_shapley(self) -> dict:
        """计算Shapley值"""
        n = len(self.channels)
        shapley_values = {ch: 0.0 for ch in self.channels}
        
        for i, channel in enumerate(self.channels):
            # 计算该渠道的边际贡献
            total_marginal = 0
            permutations = list(combinations([c for j, c in enumerate(self.channels) if j != i], n-1))
            
            for coalition in permutations:
                mc = self.marginal_contribution(channel, list(coalition) + [channel])
                total_marginal += mc
            
            # Shapley值 = 平均边际贡献
            shapley_values[channel] = total_marginal / len(permutations)
        
        # 归一化
        total = sum(shapley_values.values())
        if total > 0:
            for ch in shapley_values:
                shapley_values[ch] /= total
        
        return shapley_values
    
    def compare_models(self, touch_sequence: list) -> dict:
        """比较不同归因模型"""
        n = len(touch_sequence)
        
        return {
            'last_click': self.last_click(touch_sequence),
            'first_click': self.first_click(touch_sequence),
            'linear': self.linear(touch_sequence),
            'time_decay': self.time_decay(touch_sequence),
            'position': self.position(touch_sequence),
            'shapley': self.shapley(touch_sequence)
        }
    
    def last_click(self, touches: list) -> dict:
        attribution = {t: 0 for t in set(touches)}
        last = touches[-1]
        attribution[last] = 1.0
        return attribution
    
    def first_click(self, touches: list) -> dict:
        attribution = {t: 0 for t in set(touches)}
        first = touches[0]
        attribution[first] = 1.0
        return attribution
    
    def linear(self, touches: list) -> dict:
        attribution = {t: 0 for t in set(touches)}
        credit = 1.0 / len(touches)
        for t in touches:
            attribution[t] += credit
        return attribution
    
    def time_decay(self, touches: list, half_life: float = 3.0) -> dict:
        import math
        attribution = {t: 0 for t in set(touches)}
        total_weight = 0
        
        for i, t in enumerate(reversed(touches)):
            weight = 0.5 ** (i / half_life)
            attribution[t] += weight
            total_weight += weight
        
        for t in attribution:
            attribution[t] /= total_weight
        
        return attribution
    
    def position(self, touches: list) -> dict:
        attribution = {t: 0 for t in set(touches)}
        n = len(touches)
        
        if n == 1:
            attribution[touches[0]] = 1.0
        else:
            attribution[touches[0]] = 0.4
            attribution[touches[-1]] = 0.4
            middle_credit = 0.2 / (n - 2) if n > 2 else 0
            for t in touches[1:-1]:
                attribution[t] += middle_credit
        
        return attribution
    
    def shapley(self, touches: list) -> dict:
        unique_touches = list(set(touches))
        attribution = {t: 0 for t in unique_touches}
        
        for i, channel in enumerate(unique_touches):
            total_mc = 0
            for k in range(len(unique_touches)):
                for coalition in combinations([c for j, c in enumerate(unique_touches) if j != k], k):
                    coalition_list = list(coalition) + [channel]
                    mc = self.marginal_contribution(channel, coalition_list)
                    total_mc += mc
            
            attribution[channel] = total_mc / (len(unique_touches) * 2 ** (len(unique_touches) - 1))
        
        # 归一化
        total = sum(attribution.values())
        if total > 0:
            for ch in attribution:
                attribution[ch] /= total
        
        return attribution
```

## 三、面试高频题

### Q1: 什么是Shapley值？

```
Shapley值是合作博弈论中的概念
用于公平分配联盟总价值给每个参与者
```

### Q2: 何时使用数据驱动归因？

```
1. 数据量充足 (>10万转化)
2. 多渠道复杂触达
3. 需要高精度归因
```

## 六、自测题

1. 解释各种归因模型
2. Shapley值如何计算？
3. 归因模型如何选择？

---

## 参考文档

- [Shapley Values](https://en.wikipedia.org/wiki/Shapley_value)
- [Attribution Models](https://support.google.com/analytics/answer/2444872)
