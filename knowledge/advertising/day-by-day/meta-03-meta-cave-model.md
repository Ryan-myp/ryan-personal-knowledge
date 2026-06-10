# Meta Ads — CAVE 模型与深层转化预测

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：CAVE 模型深度解析

### 1.1 CAVE (Conversion Event) 模型

```
CAVE 模型是 Meta 深层转化预测的核心：

目标: 预测用户在未来 N 天内完成特定转化的概率

P(Conversion | User, Ad, Context, Time Window)

模型输入:
├─ 用户特征 (User Features):
│   ├── 历史转化行为 (过去 7/30/90 天)
│   ├── 页面互动历史
│   ├── 应用使用历史
│   └── 社交关系图谱
├─ 广告特征 (Ad Features):
│   ├── 创意类型 (image/video/carousel)
│   ├── 文案 NLP 特征
│   ├── 创意图像 CV 特征
│   └── 广告主历史表现
├─ 上下文特征 (Context Features):
│   ├── 时间 (小时/星期几/节假日)
│   ├── 设备 (mobile/desktop)
│   ├── 网络 (WiFi/4G)
│   └── 地理位置
└─ 序列特征 (Sequential Features):
    ├── 用户最近 10 次行为
    ├── 时间衰减权重
    └── 行为类型 (view/click/convert)

模型架构:
┌──────────────────────────────────────────────────────────────┐
│                   CAVE Model Architecture                     │
│                                                              │
│  Input:                                                      │
│  ├── Dense Features (人口统计、设备、时间)                    │
│  ├── Sparse Features (用户 ID、创意 ID、类别)                 │
│  └── Sequential Features (用户行为序列)                      │
│                                                              │
│  Encoding:                                                   │
│  ├── Embedding Layer: Sparse → Dense                         │
│  ├── Dense Network: MLP for Dense Features                   │
│  └── LSTM/Transformer: For Sequential Features               │
│                                                              │
│  Fusion:                                                     │
│  ├── Concatenate all encoded features                        │
│  └── Multi-Layer Fusion Network                              │
│                                                              │
│  Output:                                                     │
│  └── pConversion(t): P(convert within t days)               │
│      t = 1, 7, 28 days                                      │
│                                                              │
│  Training:                                                   │
│  ├── Loss: Binary Cross-Entropy + Survival Loss              │
│  ├── Hard Negative Mining                                   │
│  └── Calibration: Platt Scaling / Isotonic Regression        │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 CAVE 的训练数据

```
训练数据构建：

Positive samples:
├─ 用户点击广告 + 在 N 天内转化
├─ 标注: 1 (转化)
└─ 标注: conversion_time (转化时间)

Negative samples:
├─ 用户点击广告 + 未转化
├─ 标注: 0 (未转化)
└─ 标注: observation_time (观察时长)

Censored samples:
├─ 用户点击广告 + 观察期结束
├─ 可能已转化但未记录
└─ 生存分析处理

数据均衡：
├─ 正负样本比通常 ~1:100
├─ 使用采样策略 (undersampling)
├─ 或使用权重 (class weights)
└─ 或使用焦点损失 (Focal Loss)
```

---

## 第二部分：生存分析在广告中的应用

### 2.1 为什么用生存分析？

```
传统分类 vs 生存分析：

传统分类:
├─ 问题: P(convert) = ?
├─ 回答: 是/否
└─ 缺点: 忽略时间维度

生存分析:
├─ 问题: P(convert | time t) = ?
├─ 回答: 在时间 t 内转化的概率
└─ 优势: 考虑时间维度，更精确

生存分析在广告中的特殊价值：
1. 转化延迟: 用户可能几天甚至几周后转化
2. 右删失: 观察期结束时仍未转化的用户
3. 事件时间: 从点击到转化的时间很重要
```

### 2.2 Cox 比例风险模型

```
Cox Proportional Hazards Model:

h(t | x) = h₀(t) × exp(β₁x₁ + β₂x₂ + ...)

其中:
├─ h(t): 风险函数 (hazard function)
├─ h₀(t): 基础风险函数
├─ x: 特征向量
└─ β: 系数

在广告中的解释：
├─ β₁ > 0: 特征 x₁ 增加风险 (加快转化)
├─ β₁ < 0: 特征 x₁ 降低风险 (减慢转化)
└─ exp(β₁): 风险比 (Hazard Ratio)

实现:
```python
import lifelines
from lifelines import CoxPHFitter

# 准备数据
data = pd.DataFrame({
    'time': [1, 3, 7, 14, 28, 3, 10, 5],
    'event': [1, 1, 1, 0, 1, 1, 1, 1],  # 1=转化, 0=删失
    'age': [25, 30, 35, 28, 22, 40, 33, 29],
    'device': [1, 0, 1, 1, 0, 0, 1, 1],  # 1=mobile
    'past_conversion': [1, 0, 1, 0, 1, 0, 1, 1],
})

# 拟合 Cox 模型
cph = CoxPHFitter()
cph.fit(data, duration_col='time', event_col='event')

# 查看系数
cph.print_summary()

# 预测生存函数
s = cph.predict_survival_function(new_data)
```
```

### 2.3 Deep Survival 模型

```
深度学习 + 生存分析：

DeepSurv 模型架构：

┌─────────────────────────────────────────────────────┐
│              DeepSurv Architecture                   │
│                                                     │
│  Input: Dense Features (user, ad, context)          │
│       │                                             │
│       ▼                                             │
│  Dense Network:                                     │
│  ├── Layer 1: 512 neurons, ReLU, Dropout            │
│  ├── Layer 2: 256 neurons, ReLU, Dropout            │
│  └── Layer 3: 128 neurons, ReLU, Dropout            │
│       │                                             │
│       ▼                                             │
│  Hazard Output:                                     │
│  ├── h(x) = exp(f(x))                              │
│  └── f(x): 网络输出                                 │
│                                                     │
│  Loss: Partial Likelihood Loss                      │
│  L = -Σᵢ δᵢ [f(xᵢ) - log(Σⱼ∈Rᵢ exp(f(xⱼ)))]      │
│                                                     │
│  where:                                             │
│  ├── δᵢ: 是否观察到事件 (1=是, 0=否)                 │
│  ├── Rᵢ: 风险集 (时间 ≥ tᵢ 的用户)                  │
│  └── 该损失函数考虑了删失数据                         │
└─────────────────────────────────────────────────────┘
```

---

## 第三部分：深层转化预测实战

### 3.1 转化价值最大化

```
基于 CAVE 模型的转化价值最大化：

目标：在预算约束下最大化总转化价值

Maximize: Σᵢ vᵢ × pᵢ(t) × bᵢ
Subject to: Σᵢ cᵢ ≤ Budget

其中:
├─ vᵢ: 转化价值 (订单金额)
├─ pᵢ(t): 在时间 t 内转化的概率 (CAVE 模型)
└─ bᵢ: 出价

优化策略：
1. 按 vᵢ × pᵢ(t) 排序所有候选展示
2. 从高到低选择，直到预算耗尽
3. 动态调整: 每 5 分钟重新排序

实际实现：
```python
class ConversionValueMaximizer:
    """转化价值最大化器"""
    
    def __init__(self, caev_model, daily_budget: float):
        self.model = caev_model
        self.budget = daily_budget
        self.spend = 0.0
    
    def rank_impressions(self, impressions: list) -> list:
        """
        按转化价值排序
        
        参数:
        └── impressions: 候选展示列表
        
        返回:
        └── 按 v × p(t) 排序的展示列表
        """
        scored = []
        for imp in impressions:
            # 预测 p(t=7)
            p_7d = self.model.predict(imp, t=7)
            # 转化价值
            v = imp.get('expected_value', 50.0)
            # 综合价值
            score = v * p_7d
            imp['score'] = score
            scored.append(imp)
        
        # 按 score 降序
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored
    
    def select_with_budget(self, ranked: list, max_cpc: float = 5.0) -> list:
        """
        在预算约束下选择展示
        
        参数:
        ├── ranked: 排序后的展示列表
        └── max_cpc: 最大 CPC
        
        返回:
        └── 选中的展示列表
        """
        selected = []
        for imp in ranked:
            # 预估 CPC
            est_cpc = max_cpc * (1 - imp['score'] / max(
                [i['score'] for i in ranked], default=1))
            
            # 检查预算
            if self.spend + est_cpc > self.budget:
                break
            
            selected.append(imp)
            self.spend += est_cpc
        
        return selected
```

---

## 第四部分：排障与优化

### 4.1 模型校准

```
模型校准 (Calibration) 的重要性：

问题：模型预测的 pConversion 可能不准确
例如：模型预测 p=0.1 的事件，实际转化率只有 0.05

解决方法：
1. Platt Scaling (Logistic Calibration):
   P_calibrated = 1 / (1 + exp(A × logit(P) + B))

2. Isotonic Regression:
   └─ 非参数方法，更灵活

3. Temperature Scaling:
   └─ 简单有效，调整输出概率的"温度"

验证方法：
├─ Calibration Plot: P_predicted vs P_actual
├─ Brier Score: 概率预测的 MSE
└─ Log Loss: 对数损失
```

### 4.2 特征工程

```
CAVE 模型的关键特征：

用户行为特征：
├─ 过去 N 天的互动次数
├─ 过去 N 天的转化次数
├─ 上次互动时间 (小时)
├─ 平均会话时长
└─ 页面浏览深度

广告特征：
├─ 创意类型
├─ 历史 CTR/CVR
├─ 广告主行业
└─ 文案情感 (NLP)

时间特征：
├─ 小时 (0-23)
├─ 星期几 (0-6)
├─ 是否周末
└─ 是否节假日

设备特征：
├─ 设备类型 (mobile/desktop)
├─ 操作系统
├─ 网络类型 (WiFi/4G)
└─ 屏幕尺寸
```

---

## 自测题

### 问题 1
生存分析相比传统分类在转化预测中的优势是什么？

<details>
<summary>查看答案</summary>

- 考虑时间维度: 预测"多久内转化"而非仅"是否转化"
- 处理删失数据: 观察期结束仍未转化的用户
- 更精确的概率估计
</details>

### 问题 2
Cox 模型中的 Hazard Ratio exp(β) 如何解释？

<details>
<summary>查看答案</summary>

- exp(β) > 1: 特征增加风险(加快转化)
- exp(β) < 1: 特征降低风险(减慢转化)
- exp(β) = 1: 无影响
</details>

### 问题 3
模型校准的目的是什么？

<details>
<summary>查看答案</summary>

- 使预测概率与实际频率一致
- 例如: 预测 p=0.1 的事件, 实际应该有 10% 转化
- 提高出价决策的准确性
</details>

---

## 动手验证

### 4.1 Cox 模型示例

```python
import lifelines
from lifelines import CoxPHFitter
import pandas as pd

# 模拟数据
data = pd.DataFrame({
    'time': [1, 3, 7, 14, 28, 3, 10, 5],
    'event': [1, 1, 1, 0, 1, 1, 1, 1],
    'age': [25, 30, 35, 28, 22, 40, 33, 29],
    'device': [1, 0, 1, 1, 0, 0, 1, 1],
})

cph = CoxPHFitter()
cph.fit(data, duration_col='time', event_col='event')
cph.print_summary()
```

---

*今天花 90 分钟：深入理解 CAVE 模型和生存分析*
*答不出自测题？回去重读对应章节。*
