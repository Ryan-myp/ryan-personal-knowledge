# 广告归因模型深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告系统  
> **难度**: 高级

---

## 一、归因模型概述

### 1.1 什么是归因？

**广告归因** 是确定哪个广告触点对转化做出贡献的过程。

```
用户转化路径:
展示 A → 点击 A → 展示 B → 点击 B → 转化

归因目标: 确定 A 和 B 各自的贡献值
```

### 1.2 归因模型分类

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        归因模型分类                                        │
├────────────────────────────┬──────────────────────────────────────────────┤
│ 模型类型                   │ 说明                                        │
├────────────────────────────┼──────────────────────────────────────────────┤
│ Last Click                │ 100% 归因给最后一次点击                         │
│ First Click               │ 100% 归因给第一次点击                         │
│ Linear                    │ 所有触点均分归因                            │
│ Time Decay                │ 越接近转化的触点权重越高                    │
│ Position-Based            │ 首尾各 40%，中间均分 20%                   │
│ Markov Chain              │ 基于状态转移概率                            │
│ Shapley Value             │ 合作博弈论，公平分配                        │
│ Data-Driven (ML)          │ 基于历史数据学习                            │
└────────────────────────────┴──────────────────────────────────────────────────┘
```

---

## 二、传统归因模型

### 2.1 Last Click / First Click

```python
# last_click_attribution.py
def last_click_attribution(conversion_path: List[str]) -> Dict[str, float]:
    """最后点击归因"""
    attribution = {}
    last_touch = conversion_path[-1]
    attribution[last_touch] = 1.0
    return attribution

def first_click_attribution(conversion_path: List[str]) -> Dict[str, float]:
    """首次点击归因"""
    attribution = {}
    first_touch = conversion_path[0]
    attribution[first_touch] = 1.0
    return attribution
```

### 2.2 Linear 归因

```python
def linear_attribution(conversion_path: List[str]) -> Dict[str, float]:
    """线性归因 - 均分"""
    n = len(conversion_path)
    return {touch: 1.0/n for touch in conversion_path}
```

### 2.3 Time Decay 归因

```python
import numpy as np

def time_decay_attribution(conversion_path: List[str], half_life: float = 1.0) -> Dict[str, float]:
    """时间衰减归因 - 越接近转化权重越高"""
    n = len(conversion_path)
    weights = []
    
    for i in range(n):
        # 距离转化的时间差
        time_diff = n - i
        # 指数衰减
        weight = np.exp(-time_diff * np.log(2) / half_life)
        weights.append(weight)
    
    # 归一化
    total = sum(weights)
    return {touch: w/total for touch, w in zip(conversion_path, weights)}
```

### 2.4 Position-Based 归因

```python
def position_based_attribution(conversion_path: List[str]) -> Dict[str, float]:
    """位置归因 - 首尾各40%，中间均分20%"""
    n = len(conversion_path)
    if n == 1:
        return {conversion_path[0]: 1.0}
    
    attribution = {}
    # 首次点击 40%
    attribution[conversion_path[0]] = 0.4
    # 最后点击 40%
    attribution[conversion_path[-1]] = 0.4
    
    # 中间触点均分 20%
    middle_count = n - 2
    if middle_count > 0:
        middle_weight = 0.2 / middle_count
        for touch in conversion_path[1:-1]:
            attribution[touch] = middle_weight
    
    return attribution
```

---

## 三、Shapley 值归因

### 3.1 核心概念

**Shapley 值** 来自合作博弈论，用于公平分配贡献。

```
定义:
- N: 所有触点的集合
- v(S): 子集 S 的转化价值
- φ_i: 触点 i 的 Shapley 值

公式:
φ_i = Σ_{S⊆N\{i}} [|S]! * (n-|S|-1)! / n! * [v(S∪{i}) - v(S)]
```

### 3.2 实现

```python
from itertools import combinations
from typing import List, Dict, Set

class ShapleyAttribution:
    """Shapley 值归因"""
    
    def __init__(self, conversion_data: Dict[frozenset, float]):
        """
        conversion_data: {frozenset(触点): 转化率}
        """
        self.conversion_data = conversion_data
    
    def compute(self, touches: List[str]) -> Dict[str, float]:
        """计算 Shapley 值"""
        n = len(touches)
        attribution = {t: 0.0 for t in touches}
        
        # 遍历所有子集
        for i, touch in enumerate(touches):
            remaining = touches[:i] + touches[i+1:]
            
            for r in range(len(remaining) + 1):
                for S in combinations(remaining, r):
                    S = frozenset(S)
                    
                    # 计算边际贡献
                    v_S = self.conversion_data.get(S, 0.0)
                    v_S_plus_i = self.conversion_data.get(S | {touch}, 0.0)
                    marginal = v_S_plus_i - v_S
                    
                    # Shapley 权重
                    weight = self._shapley_weight(len(S), n)
                    attribution[touch] += weight * marginal
        
        # 归一化
        total = sum(attribution.values())
        if total > 0:
            attribution = {t: v/total for t, v in attribution.items()}
        
        return attribution
    
    def _shapley_weight(self, s: int, n: int) -> float:
        """计算 Shapley 权重"""
        from math import factorial
        return factorial(s) * factorial(n - s - 1) / factorial(n)
```

---

## 四、数据驱动归因 (ML)

### 4.1 模型架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    数据驱动归因模型                                   │
│                                                                     │
│  输入层                                                              │
│  ├── 触点序列特征                                                    │
│  ├── 时间间隔特征                                                    │
│  ├── 用户特征                                                        │
│  └── 上下文特征                                                      │
│                                                                     │
│  特征工程                                                            │
│  ├── 触点嵌入 (Embedding)                                            │
│  ├── 位置编码                                                        │
│  └── 时间编码                                                        │
│                                                                     │
│  模型层                                                              │
│  ├── LSTM/GRU (序列建模)                                             │
│  ├── Transformer (注意力机制)                                        │
│  └── XGBoost (特征重要性)                                           │
│                                                                     │
│  输出层                                                              │
│  └── 归因权重                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 PyTorch 实现

```python
# attribution_model.py
import torch
import torch.nn as nn

class AttributionNN(nn.Module):
    """归因神经网络"""
    
    def __init__(self, touch_vocab_size: int, embed_dim: int = 64):
        super().__init__()
        self.embed = nn.Embedding(touch_vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, 128, batch_first=True)
        self.attention = nn.Sequential(
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
            nn.Softmax(dim=1)
        )
        self.output = nn.Linear(128, 1)
    
    def forward(self, touch_ids: torch.Tensor) -> torch.Tensor:
        # Embedding
        embeds = self.embed(touch_ids)  # (batch, seq_len, dim)
        
        # LSTM
        lstm_out, _ = self.lstm(embeds)  # (batch, seq_len, 128)
        
        # Attention
        attn_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
        context = torch.sum(attn_weights * lstm_out, dim=1)  # (batch, 128)
        
        # Output
        output = self.output(context)  # (batch, 1)
        return output.squeeze(-1)
```

---

## 五、跨设备归因

### 5.1 挑战与方案

```
挑战:
├── 用户 ID 不统一
├── 设备切换频繁
└── 隐私保护限制

解决方案:
├── Probabilistic Matching (概率匹配)
├── Deterministic Matching (确定性匹配)
├── Clean Room (数据清洗室)
└── Privacy-Preserving Attribution (隐私保护归因)
```

### 5.2 概率匹配

```python
# probabilistic_matching.py
import hashlib
from typing import List, Tuple

class ProbabilisticMatcher:
    """概率匹配器"""
    
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
    
    def match(self, device_a: dict, device_b: dict) -> Tuple[float, bool]:
        """匹配两个设备"""
        score = self._compute_similarity(device_a, device_b)
        is_match = score >= self.threshold
        return score, is_match
    
    def _compute_similarity(self, a: dict, b: dict) -> float:
        """计算相似度"""
        scores = []
        
        # IP 匹配
        if a.get('ip') == b.get('ip'):
            scores.append(0.3)
        
        # User-Agent 匹配
        if a.get('ua') == b.get('ua'):
            scores.append(0.2)
        
        # 时间窗口
        time_diff = abs(a.get('last_active', 0) - b.get('last_active', 0))
        if time_diff < 3600:  # 1小时内
            scores.append(0.3)
        
        # 地理位置
        if a.get('geo') == b.get('geo'):
            scores.append(0.2)
        
        return sum(scores)
```

---

## 六、评估与优化

### 6.1 评估指标

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        归因模型评估指标                                    │
├────────────────────┬──────────────────────────────────────────────────────┤
│ 指标               │ 说明                                                │
├────────────────────┼──────────────────────────────────────────────────────┤
│ Conversion Lift    │ 归因后转化提升幅度                                  │
│ ROAS               │ 广告回报率                                               │
│ Attribution Error  │ 归因误差 (与真实值对比)                           │
│ Model Stability    │ 模型稳定性 (波动性)                                  │
└────────────────────┴──────────────────────────────────────────────────────┘
```

### 6.2 A/B 测试

```python
# ab_test.py
class AttributionABTest:
    """归因模型 A/B 测试"""
    
    def __init__(self):
        self.experiment_groups = {
            "last_click": [],
            "shapley": [],
            "ml_attribution": [],
        }
    
    def assign(self, user_id: str, variant: str):
        """分配实验组"""
        self.experiment_groups[variant].append(user_id)
    
    def evaluate(self) -> dict:
        """评估实验结果"""
        results = {}
        for variant, users in self.experiment_groups.items():
            # 计算该组的 ROAS
            roas = self._calculate_roas(users, variant)
            results[variant] = {
                "roas": roas,
                "conversions": len(users),
            }
        return results
```

---

## 七、生产实践

### 7.1 实时归因

```
实时归因流程:
├── 事件采集 (Kafka)
├── 流式处理 (Flink/Spark Streaming)
├── 归因计算 (实时模型)
├── 结果存储 (Redis/ClickHouse)
└── 报表生成 (实时看板)
```

### 7.2 批处理归因

```
批处理归因流程:
├── T+1 数据同步
├── Hadoop/Spark 离线处理
├── 全量归因计算
├── 结果入库
└── 报表更新
```

---

## 八、总结

| 项目 | 关键信息 |
|------|---------|
| **核心模型** | Last Click, Shapley, ML-based |
| **关键挑战** | 跨设备、归因窗口、虚假转化 |
| **生产实践** | 实时+离线混合架构 |
| **评估指标** | ROAS, Lift, Attribution Error |

---

## 九、自测题

1. **Last Click 归因的优缺点？**
   - 优点: 简单直观；缺点: 忽略其他触点贡献

2. **Shapley 值的核心思想？**
   - 基于边际贡献，公平分配

3. **跨设备归因的主要挑战？**
   - 用户 ID 不统一、隐私限制

4. **如何评估归因模型效果？**
   - A/B 测试、ROAS 对比、转化提升

EOF
echo "✅ 已创建: advertising/attribution-model-deep.md"