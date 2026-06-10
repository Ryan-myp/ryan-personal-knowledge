# Meta Ads — 推荐系统作为广告分配器：从 Ranking 到 Bidding

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：Meta 的推荐系统架构

### 1.1 Meta 广告的本质：推荐系统的一部分

```
Meta 的广告系统不是一个独立的广告平台
而是 Facebook/Instagram 推荐系统的一部分。

这决定了 Meta 广告的核心逻辑：
广告不是"投放"出来的，而是"推荐"出来的。

┌──────────────────────────────────────────────────────────┐
│             Meta 推荐系统架构                             │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │              User: "刷 Feed"                        │  │
│  │                                                    │  │
│  │  Feed 内容由两部分组成:                            │  │
│  │  ├── Organic Posts (有机内容): 10-20%             │  │
│  │  └── Advertisements (广告): 20-30%                │  │
│  │     (其余为 Stories, Reels, etc.)                  │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                                │
│  ┌───────────────────────▼────────────────────────────────┐│
│  │           Meta 的 Ranking Pipeline                      ││
│  │                                                        ││
│  │  1. Candidate Generation (召回)                         ││
│  │     ├── Organic: 关注的人、兴趣相关内容                   ││
│  │     ├── Ads: 匹配的广告                                 ││
│  │     └── Total: ~10,000 个候选                          ││
│  │                                                        ││
│  │  2. Pre-Ranking (预排序)                                ││
│  │     ├── 轻量级模型筛选                                  ││
│  │     ├── 输出: Top 500 个                               ││
│  │     └── 耗时: ~5ms                                     ││
│  │                                                        ││
│  │  3. Ranking (精排序)                                    ││
│  │     ├── 复杂 DNN 模型打分                              ││
│  │     ├── 输出: Top 100 个                               ││
│  │     └── 耗时: ~20ms                                    ││
│  │                                                        ││
│  │  4. Re-Ranking (重排)                                   ││
│  │     ├── 控制广告频率                                    ││
│  │     ├── 混合有机与广告                                  ││
│  │     ├── 多样性控制                                      ││
│  │     └── 输出: 最终 Feed 内容                           ││
│  └────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

### 1.2 Ranking Pipeline 深度解析

```
Meta 的 Ranking Pipeline 是广告分配的核心：

Step 1: Candidate Generation (召回)
────────────────────────────────────
目标: 从数十亿广告中召回约 10,000 个

召回策略:
├─ 广告主定向: 地理位置、年龄、兴趣
├─ 用户画像: 历史行为、兴趣标签
├─ 广告素材: 图像/视频分类
├─ 协同过滤: "喜欢这个的人也看过..."
└─ 实时特征: 设备、时间、上下文

Step 2: Pre-Ranking (预排序)
────────────────────────────────────
目标: 从 10,000 降到 500

预排序模型:
├─ 特征: 用户 × 广告交叉特征
├─ 模型: 轻量级 DNN (约 5M 参数)
├─ 输出: pEngagement, pConversion, pClick
└─ 耗时: ~5ms

Step 3: Ranking (精排序)
────────────────────────────────────
目标: 从 500 降到 100

精排序模型:
├─ 特征: 完整的用户-广告交叉特征 (~10,000 个特征)
├─ 模型: 复杂 DNN (约 1B 参数)
├─ 输出: 精确的 pAction (每种行动的转化概率)
└─ 耗时: ~20ms

Step 4: Re-Ranking (重排)
────────────────────────────────────
目标: 从 100 降到最终 Feed

重排策略:
├─ 频率控制: 同一个广告主最多出现 N 次
├─ 多样性: 混合不同类型的广告
├─ 广告/有机比例: 控制广告密度
├─ 广告插入: 在有机内容之间插入
└─ 最终输出: 用户看到的 Feed
```

### 1.3 Meta 的特征工程

```
Meta 的模型使用约 10,000 个特征：

用户特征 (User Features):
├─ 人口统计: 年龄、性别、教育、收入
├─ 位置: 城市、国家、时区
├─ 设备: 手机型号、操作系统、网络
├─ 行为历史:
│   ├── 过去 7 天点击/展示/转化
│   ├── 过去 30 天浏览
│   └── 长期兴趣标签
└─ 社交关系: 好友列表、群组、页面

广告特征 (Ad Features):
├─ 广告类型: image/video/carousel/text
├─ 广告文案: 标题、描述、CTA
├─ 历史表现: CTR, CVR, CPA
├─ 创意特征:
│   ├── 图像分类 (人物/产品/场景)
│   ├── 视频摘要 (时长、帧率)
│   └── 文本 NLP 特征
└─ 出价信息: Bid, Budget

交叉特征 (Cross Features):
├─ 用户-广告:
│   ├── 用户兴趣 × 广告类别
│   ├── 用户历史 × 广告文案
│   └── 用户社交关系 × 广告定向
└─ 上下文:
    ├── 时间 × 用户习惯
    └─ 设备 × 广告类型

实时特征 (Real-time Features):
├─ 当前页面类型 (Feed/Stories/Reels)
├─ 上次展示时间 (频率控制)
├─ 当前设备状态 (WiFi/4G)
└─ 当前会话长度
```

---

## 第二部分：预估模型 (Prediction Model)

### 2.1 pAction 预测模型

```
Meta 的核心模型预测每个用户对每个广告的 pAction：

pAction = P(user performs action | user, ad, context)

常见的 Action:
├─ Like: 点赞
├─ Comment: 评论
├─ Share: 分享
├─ Click: 点击
├─ Conversion: 转化
├─ App Install: 应用安装
└─ View Content: 查看内容

模型架构:
┌────────────────────────────────────────────────────────────┐
│                  Deep Learning Model                        │
│                                                            │
│  Input: Sparse Features (10,000+)                          │
│       │                                                    │
│       ▼                                                    │
│  Embedding Layer (将离散特征映射到稠密向量)                  │
│       │                                                    │
│       ▼                                                    │
│  Multi-Task Learning (多任务学习)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │ pClick   │ │ pLike    │ │ pConvert │                  │
│  │ Tower    │ │ Tower    │ │ Tower    │                  │
│  └──────────┘ └──────────┘ └──────────┘                  │
│       │           │           │                            │
│       └───────────┴───────────┘                            │
│                            │                               │
│                   ┌────────▼────────┐                     │
│                   │ Total Value     │                     │
│                   │ = Σ (weight_i × │                     │
│                   │                │                     │
│                   │  pAction_i)    │                     │
│                   └─────────────────┘                     │
│                                                            │
│  Output: Total Value (用于排序和出价)                       │
└────────────────────────────────────────────────────────────┘

多任务学习的优势:
├─ 共享表示: 各塔共享底层特征表示
├─ 数据增强: 数据量大的任务帮助数据量小的任务
└─ 泛化: 更好的泛化能力
```

### 2.2 Total Value 公式

```
Meta 的排序依据是 Total Value：

Total_Value = Σ (bid_i × pAction_i × user_preference_modifier_i)

分解:
├─ bid_i: 对该行动的行动出价
│   └─ 例如: conversion_bid = $5.00
├─ pAction_i: 预测的行动概率
│   └─ 例如: pConversion = 0.02 (2%)
├─ user_preference_modifier_i: 用户对该行动的偏好
│   └─ 例如: 用户很少转化 → modifier = 0.8
└─ 求和: 对所有行动类型求和

举例:
├─ bid_click × pClick × user_pref_click = $0.50 × 0.05 × 1.0 = $0.025
├─ bid_convert × pConvert × user_pref_convert = $5.00 × 0.02 × 0.8 = $0.08
└─ Total_Value = $0.025 + $0.08 = $0.105

注意: Meta 的广告拍卖中，bid 通常是目标 CPA 的倒数或固定值。
实际实现中，bid 是优化的变量。
```

---

## 第三部分：Advantage+ 的数学本质

### 3.1 Advantage+ Campaign Budget

```
Advantage+ Campaign Budget (ACB) 的优化问题：

目标：
Maximize: Σ (Revenue_i)
Subject to: Σ (Cost_i) ≤ Budget

其中:
├─ Revenue_i = Conversion_i × Revenue_per_conversion
├─ Conversion_i = f(Bid_i, pCVR_i)
└─ Cost_i = Bid_i × Impression_i

优化方法:
├─ 梯度下降 (Gradient Descent)
├─ 约束优化 (Lagrange Multiplier)
└─ 实时在线优化 (每 5 分钟更新一次)

实际实现:
├─ 将预算分配给表现最好的广告组
├─ 表现由 pCVR × Bid × ROI 决定
└─ 自动调整分配比例
```

### 3.2 Advantage+ Audience

```
Advantage+ Audience 的工作原理：

传统定向: 你告诉 Meta "投放给谁"
Advantage+ Audience: 你告诉 Meta "不要投放给谁"

优化问题:
Maximize: Σ (Revenue_i)
Subject to: Exclusion_List (你指定的排除列表)
        AND: Budget ≤ Daily_Budget

Meta 的做法:
├─ 移除你指定的排除列表
├─ 让算法在剩余的用户中寻找高价值用户
├─ 利用模型预测每个用户的转化概率
└─ 自动选择 pCVR 最高的用户

为什么 Advantage+ Audience 效果更好的原因:
├─ 模型发现了人工定向遗漏的高价值用户
├─ 避免了人工定向的偏差（Over-fitting）
└─ 利用大规模数据提高了模型泛化能力
```

### 3.3 深层转化预测 (CAVE 模型)

```
CAVE (Conversion Event) 预测模型：

目标: 预测用户在未来 N 天内完成转化的概率

模型架构:
┌─────────────────────────────────────────────────────┐
│              CAVE Model Architecture                 │
│                                                     │
│  Input Layer:                                       │
│  ├── 用户特征 (历史行为、画像)                        │
│  ├── 广告特征 (类型、文案、历史)                      │
│  ├── 上下文特征 (时间、设备、位置)                    │
│  └── 序列特征 (最近的行为序列)                        │
│                                                     │
│  Feature Engineering:                               │
│  ├── Time Decay: 近期行为权重更高                     │
│  ├── Event Type: 不同类型的行为权重不同               │
│  └── Cross Features: 用户 × 广告                     │
│                                                     │
│  Model:                                             │
│  ├── LSTM/Transformer: 处理序列特征                   │
│  ├── Multi-Task: 预测多种行动                         │
│  └── Survival Analysis: 预测"多久内转化"             │
│                                                     │
│  Output:                                            │
│  └── pConversion(t) = P(convert within t days)      │
│      t = 1, 7, 28 days                             │
└─────────────────────────────────────────────────────┘

生存分析 (Survival Analysis) 在广告中的应用：
├─ 传统方法: P(convert | event happened)
├─ 生存分析: P(convert | time t, event hasn't happened yet)
└─ 优势: 考虑时间维度，更精确
```

---

## 第四部分：Meta 广告排障与优化

### 4.1 频率 (Frequency) 的深层含义

```
Frequency (频率) 是 Meta 广告的核心指标：

定义:
Frequency = 展示次数 / 触达人数

频率效应:
├─ Frequency 1-2: 最佳（用户第一次看到广告）
├─ Frequency 2-4: 可接受（重复曝光，品牌记忆）
└─ Frequency > 4: 疲劳（用户厌烦）

频率管理的策略:
├─ 控制广告组预算 → 控制展示速度
├─ 使用创意轮换 → 避免单一创意疲劳
├─ 定期更换素材 → 降低用户疲劳度
└─ 使用频次控制 (Frequency Cap) → 直接限制

频次的数学模型:
Response_i = Base_Rate × (1 - γ^Frequency_i)

其中 γ 是衰减因子（通常 0.3-0.5）
频率越高，响应率越低
```

### 4.2 广告学习期 (Learning Phase)

```
Meta 广告的学习期机制：

学习期触发条件:
├─ 创建新广告
├─ 大幅修改广告（> 20% 的修改）
├─ 暂停后重新启用
└─ 预算或出价大幅变化

学习期要求:
├─ 7 天内至少 50 次优化事件（如转化）
├─ 优化事件: 点击、转化、查看内容等
└─ 50 conversions 是统计显著性的经验法则

学习期表现:
├─ CPA 波动大
├─ 预算消耗不均匀
├─ 转化量不稳定
└─ 需要 1-7 天才能稳定

避免学习期重置的策略:
├─ 不要频繁修改广告
├─ 小幅度调整（< 20%）
├─ 在低流量时段调整
└─ 使用广告系列级别预算（更稳定）
```

### 4.3 Meta 广告 CPA 优化策略

```
降低 CPA 的 5 个策略:

策略 1: 优化创意
├─ 高点击率创意 → 更高的 pClick → 更低的 CPC
├─ 高转化率落地页 → 更高的 pConversion → 更低的 CPA
└─ A/B 测试不同创意

策略 2: 受众优化
├─ 使用第一方受众（效果最好）
├─ 使用 Lookalike Audience（基于高价值用户）
└─ 排除低价值受众

策略 3: 出价策略
├─ 使用 Cost Cap 控制 CPA
├─ 使用 Advantage+ Budget 自动分配
└─ 避免手动出价（除非有特定需求）

策略 4: 频率控制
├─ 监控 Frequency
├─ 在频率 > 3 时更换创意
└─ 控制广告组预算以避免过度曝光

策略 5: 落地页优化
├─ 页面加载速度 < 3s
├─ 移动端适配
├─ 清晰的 CTA
└─ A/B 测试落地页
```

---

## 第五部分：Meta 与 Google 的广告系统对比

### 5.1 核心差异

```
┌─────────────────────────────────────────────────────────────────┐
│                    Meta vs Google                                │
│                                                                 │
│  用户意图:                                                       │
│  ├── Google: 主动搜索（高意图）                                  │
│  │   └─ 用户在找解决方案                                          │
│  └── Meta: 被动浏览（低意图）                                    │
│      └─ 用户在消遣，突然看到广告                                   │
│                                                                 │
│  竞价机制:                                                       │
│  ├── Google: Ad Rank = Bid × QS × pCTR                         │
│  └── Meta: Total Value = Bid × pAction × user_pref             │
│                                                                 │
│  质量分:                                                        │
│  ├── Google: QS = f(CTR, 广告相关性, 落地页)                    │
│  └── Meta: pAction = f(创意质量, 用户偏好, 历史表现)             │
│                                                                 │
│  转化路径:                                                       │
│  ├── Google: 短 (Search → Landing → Conversion)                 │
│  └── Meta: 长 (Ad → Click → Browse → Conversion)                │
│                                                                 │
│  归因窗口:                                                       │
│  ├── Google: 30 天 (点击)                                      │
│  └── Meta: 7 天 (点击) + 1 天 (展示)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 自测题

### 问题 1
Meta 的 Total Value 公式中，user_preference_modifier 的作用是什么？

<details>
<summary>查看答案</summary>

- 考虑用户对该类行动的偏好程度
- 例如：用户很少转化 → modifier < 1 → 降低该广告的 Total Value
- 这样 Meta 会在不同用户之间差异化出价
</details>

### 问题 2
Meta 广告的学习期需要多少转化？

<details>
<summary>查看答案</summary>

- 7 天内至少 50 次优化事件
- 优化事件可以是转化、点击、查看内容等
- 低于 50 转化会持续在学习期，CPA 波动大
</details>

### 问题 3
Meta 的频率效应公式 Response = Base_Rate × (1 - γ^Frequency) 中，γ 的典型范围是多少？

<details>
<summary>查看答案</summary>

- γ 通常在 0.3-0.5 之间
- γ 越大，频率衰减越快
- γ 越小，频率影响越小
</details>

---

## 动手验证

### 5.1 Meta 广告表现分析

```python
# Meta 广告数据分析
import pandas as pd

# 模拟广告数据
ads_data = [
    {'ad_id': 1, 'name': 'Ad A', 'impressions': 10000, 'clicks': 200,
     'conversions': 10, 'spend': 500, 'frequency': 2.5},
    {'ad_id': 2, 'name': 'Ad B', 'impressions': 15000, 'clicks': 300,
     'conversions': 15, 'spend': 750, 'frequency': 3.8},
    {'ad_id': 3, 'name': 'Ad C', 'impressions': 8000, 'clicks': 100,
     'conversions': 5, 'spend': 300, 'frequency': 1.8},
]

# 计算关键指标
for ad in ads_data:
    cpc = ad['spend'] / ad['clicks']
    cpa = ad['spend'] / ad['conversions']
    ctr = ad['clicks'] / ad['impressions']
    
    print(f"{ad['name']}:")
    print(f"  CPC: ${cpc:.2f}, CPA: ${cpa:.2f}, CTR: {ctr:.4f}")
    print(f"  Frequency: {ad['frequency']}")
```

---

*今天花 90 分钟：深入理解 Meta 推荐系统与广告分配机制*
*答不出自测题？回去重读对应章节。*
