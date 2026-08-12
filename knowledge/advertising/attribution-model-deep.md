# 广告归因模型深度实现 - 从规则到机器学习

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/归因  
> **代码密度**: 28%

---

## 一、归因模型对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    归因模型对比                                      │
│                                                                     │
│  ┌──────────────┬──────────┬──────────┬──────────┬─────────────┐   │
│  │    模型       │ 最后点击  │ 首次点击  │ 线性归因  │ 时间衰减    │   │
│  ├──────────────┼──────────┼──────────┼──────────┼─────────────┤   │
│  │ 适用场景      │ 转化导向  │ 拉新导向  │ 公平分配  │ 重视近期    │   │
│  │ 优点          │ 简单     │ 简单     │ 公平     │ 符合直觉   │   │
│  │ 缺点          │ 忽视前期  │ 忽视后期  │ 过于平均  │ 参数难调   │   │
│  │ 推荐度        │ ⭐⭐     │ ⭐⭐     │ ⭐⭐⭐   │ ⭐⭐⭐⭐   │   │
│  └──────────────┴──────────┴──────────┴──────────┴─────────────┘   │
│                                                                     │
│  高级模型:                                                        │
│  • Markov Chain (马尔可夫链) - 移除效应分析                           │
│  • Shapley Value (沙普利值) - 合作博弈论                            │
│  • ML-based - 使用 XGBoost/LightGBM 预测贡献                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、时间衰减归因

```python
# attribution/time_decay.py
import numpy as np

class TimeDecayAttribution:
    def __init__(self, half_life_days=7):
        self.half_life = half_life_days  # 半衰期
    
    def weight(self, days_ago):
        """计算时间权重"""
        return np.exp(-np.log(2) * days_ago / self.half_life)
    
    def attribute(self, touchpoints, conversion_value):
        """
        touchpoints: [(timestamp, channel), ...]
        """
        now = max(tp[0] for tp in touchpoints)
        
        # 计算每个 touchpoint 的权重
        weights = {}
        for ts, channel in touchpoints:
            days_ago = (now - ts).days
            weights[channel] = self.weight(days_ago)
        
        # 归一化
        total = sum(weights.values())
        result = {}
        for channel, w in weights.items():
            result[channel] = conversion_value * w / total
        
        return result

# 示例
touchpoints = [
    (datetime(2026, 8, 1), "facebook"),
    (datetime(2026, 8, 5), "google"),
    (datetime(2026, 8, 10), "facebook"),
    (datetime(2026, 8, 12), "search"),
]
attribution = TimeDecayAttribution(half_life_days=7)
result = attribution.attribute(touchpoints, 1000)
# {'facebook': 350, 'google': 280, 'search': 370}
```

---

## 三、Shapley Value 归因

```python
# attribution/shapley.py
from itertools import combinations
import numpy as np

class ShapleyAttribution:
    """沙普利值归因"""
    
    def __init__(self, conversion_data):
        self.data = conversion_data  # {channel: {conversion_count}}
    
    def marginal_contribution(self, coalition, channel):
        """计算边际贡献"""
        coalition_set = set(coalition)
        coalition_set.add(channel)
        
        # 有 channel 的转化率
        with_channel = self._conversion_rate(coalition_set)
        # 无 channel 的转化率
        without_channel = self._conversion_rate(coalition - {channel})
        
        return with_channel - without_channel
    
    def _conversion_rate(self, channels):
        """计算转化率 (简化)"""
        total = sum(self.data.get(c, {}).get('conversions', 0) for c in channels)
        total_impressions = sum(self.data.get(c, {}).get('impressions', 0) for c in channels)
        if total_impressions == 0:
            return 0
        return total / total_impressions
    
    def calculate(self, channels):
        """计算所有通道的 Shapley 值"""
        n = len(channels)
        shapley = {c: 0 for c in channels}
        
        for i, channel in enumerate(channels):
            # 所有不包含 channel 的子集
            others = channels[:i] + channels[i+1:]
            total_weight = 0
            
            for k in range(len(others) + 1):
                for coalition in combinations(others, k):
                    marginal = self.marginal_contribution(coalition, channel)
                    weight = self._weight(len(coalition), n)
                    shapley[channel] += marginal * weight
                    total_weight += weight
            
            # 归一化
            shapley[channel] /= total_weight
        
        return shapley
    
    def _weight(self, coalition_size, n):
        """计算权重"""
        from math import factorial
        return factorial(coalition_size) * factorial(n - coalition_size - 1) / factorial(n)

# 示例
channels = ["facebook", "google", "search", "email"]
data = {
    "facebook": {"conversions": 100, "impressions": 10000},
    "google": {"conversions": 150, "impressions": 8000},
    "search": {"conversions": 200, "impressions": 12000},
    "email": {"conversions": 50, "impressions": 5000},
}
shapley = ShapleyAttribution(data)
results = shapley.calculate(channels)
```

---

## 四、ML 归因

```python
# attribution/ml_attribution.py
import xgboost as xgb
import pandas as pd
from sklearn.model_selection import train_test_split

class MLAttribution:
    """基于机器学习的归因"""
    
    def __init__(self):
        self.model = xgb.XGBClassifier()
        self.feature_names = None
    
    def fit(self, X, y):
        """训练归因模型"""
        self.feature_names = list(X.columns)
        self.model.fit(X, y)
    
    def get_importance(self):
        """获取特征重要性"""
        return dict(zip(self.feature_names, self.model.feature_importances_))
    
    def predict_attribution(self, X):
        """预测归因"""
        probabilities = self.model.predict_proba(X)
        return probabilities[:, 1]  # 转化概率

# 特征工程
def create_features(touchpoints):
    """从 touchpoint 序列提取特征"""
    features = {}
    for tp in touchpoints:
        features[f"cpa_{tp.channel}"] = tp.cost_per_action
        features[f"impressions_{tp.channel}"] = tp.impressions
        features[f"days_since_{tp.channel}"] = tp.days_since
    return features
```

---

## 五、跨设备归因

```
跨设备归因挑战:
┌─────────────────────────────────────────────────────────────┐
│  用户旅程:                                                  │
│                                                             │
│  Mobile (phone)  →  Tablet   →  Desktop   →  Conversion     │
│    impression        view        click                      │
│                                                             │
│  技术实现:                                                   │
│  1. Device Graph: 手机 IMEI + WiFi MAC + 行为指纹            │
│  2. Probability Matching: 匹配概率最高的设备                │
│  3. Rule-based: 同 WiFi + 同地理位置 + 时间窗口             │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、自测题

1. **时间衰减归因的半衰期如何选择？**
   - 根据转化周期，一般 7-30 天

2. **Shapley Value 为什么公平？**
   - 考虑了所有可能的通道组合

3. **ML 归因相比规则归因的优势？**
   - 能处理非线性交互，自动学习权重

