# 增长黑客实战案例库 - 资深专家深度实现

## 一、增长框架

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   增长黑客 AARRR 模型                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Acquisition   →   Activation   →   Retention   →   Revenue   →   Referral
│   用户获取       │   首次激活       │   用户留存       │   变现   │   自发传播
│                                                                         │
│   ──────────────────────────────────────────────────────────────────   │
│                                                                         │
│   关键指标:                                                               │
│   • CAC (获客成本) < LTV (用户生命周期价值)                               │
│   • DAU/MAU > 20% 表示健康留存                                            │
│   • NPS > 50 表示高满意度                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心算法

```python
class GrowthHacker:
    def __init__(self):
        self.cac = 0.0
        self.ltv = 0.0
        self.retention_rate = 0.0
    
    def calculate_ltv(self, arpu: float, churn_rate: float) -> float:
        """计算用户生命周期价值"""
        return arpu / churn_rate
    
    def is_profitable(self, cac: float, ltv: float) -> bool:
        """检查是否盈利"""
        return ltv > cac * 3  # LTV:CAC > 3:1
    
    def optimize_channels(self, channels: list) -> dict:
        """渠道优化"""
        results = {}
        for channel in channels:
            cpc = channel['cost'] / channel['clicks']
            cvr = channel['conversions'] / channel['clicks']
            cac = cpc / cvr
            ltv = self.calculate_ltv(channel['arpu'], channel['churn'])
            roi = ltv / cac if cac > 0 else 0
            results[channel['name']] = {
                'cac': cac,
                'ltv': ltv,
                'roi': roi,
                'recommend': self.is_profitable(cac, ltv)
            }
        return results
```

## 三、裂变机制

```python
class ViralLoop:
    def __init__(self, invite_rate: float, conversion_rate: float):
        self.invite_rate = invite_rate  # 邀请率
        self.conversion_rate = conversion_rate  # 转化率
    
    def calculate_k_factor(self, initial_users: int) -> int:
        """计算K因子 (每个用户带来多少新用户)"""
        return int(initial_users * self.invite_rate * self.conversion_rate)
    
    def predict_growth(self, weeks: int, initial: int) -> list:
        """预测增长曲线"""
        growth = [initial]
        current = initial
        for _ in range(weeks):
            k = self.calculate_k_factor(current)
            current += k
            growth.append(current)
        return growth
    
    def optimize_invite_design(self) -> dict:
        """优化邀请设计"""
        return {
            'incentive': '现金奖励/积分',
            'friction': '一键分享',
            'targeting': '高价值用户优先',
            'timing': '使用后30秒邀请'
        }
```

## 四、A/B测试框架

```python
import numpy as np
from scipy import stats

class ABTest:
    def __init__(self, variant_a: list, variant_b: list):
        self.a = variant_a
        self.b = variant_b
    
    def test(self, alpha: float = 0.05) -> dict:
        """执行A/B测试"""
        # T检验
        t_stat, p_value = stats.ttest_ind(self.a, self.b)
        
        # 效应量
        Cohen_d = (np.mean(self.b) - np.mean(self.a)) / np.sqrt(
            (np.var(self.a) + np.var(self.b)) / 2
        )
        
        return {
            'p_value': p_value,
            'significant': p_value < alpha,
            'effect_size': Cohen_d,
            'recommendation': 'variant_b' if p_value < alpha else 'no_difference'
        }
    
    def calculate_sample_size(self, min_detect: float, power: float = 0.8) -> int:
        """计算所需样本量"""
        # 基于效应量的样本量计算
        from statsmodels.stats.power import NormalIndPower
        analysis = NormalIndPower()
        effect_size = min_detect / np.std(self.a)
        return int(analysis.solve_power(effect_size, power=power, alpha=0.05, ratio=1.0))
```

## 五、面试高频题

### Q1: 如何计算LTV？

```
LTV = ARPU / Churn Rate
其中:
ARPU = 平均收入 per 用户
Churn Rate = 流失率
```

### Q2: 什么是K因子？

```
K因子 = 每个用户邀请人数 × 转化率
K > 1 表示病毒式增长
```

### Q3: A/B测试如何设计？

```
1. 确定目标指标
2. 计算样本量
3. 随机分组
4. 运行实验
5. 统计分析
6. 决策上线
```

## 六、自测题

1. 解释AARRR模型
2. 如何计算K因子？
3. A/B测试的关键要素？

---

## 参考文档

- [Lean Startup](https://leankit.com/glossary/aarrr-framework/)
- [Growth Hacking](https://en.wikipedia.org/wiki/Growth_hacking)
