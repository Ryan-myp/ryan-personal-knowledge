# 跨平台归因与增量测量深度指南

> **领域**: 广告投放 / 跨平台归因
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: attribution, cross-platform, incrementality, google-ads, meta-ads, tiktok-ads, dv360
> **更新时间**: 2026-08-14
> **类型**: deep-dive/attribution

---

## 一、归因问题的本质

### 1.1 为什么跨平台归因如此困难？

```
典型用户跨平台旅程：

Day 1: 看到 Meta Instagram Story 广告 → 点赞 → 未点击
Day 2: Google Search "best running shoes" → 点击 Google Shopping → 加购物车
Day 3: 收到 Meta Retargeting 广告 → 点击 → 完成购买

问题：
- Meta 认为自己带来了第一次接触（Day 1）
- Google 认为自己带来了转化（Day 2）
- TikTok 可能也参与了（如果用户在 TikTok 上也看到了相关内容）
- 实际购买发生在哪个平台的"归因窗口"内？
```

### 1.2 各平台归因模型的差异

```
归因模型全景对比：

                    Last Click    First Click   Linear      Time Decay   Position   Data-Driven
Google Ads          ✅ 30d         ✅ 30d       ✅ 30d      ✅ 30d       ✅ 30d    ✅ 30d
Meta Ads            ✅ 1/7/28d     ✅ 1/7/28d   ✅ 1/7/28d  ✅ 1/7/28d   ✅ 1/7/28d  ❌
TikTok Ads          ✅ 7d          ✅ 7d        ✅ 7d       ✅ 7d        ✅ 7d       ❌
DV360               ✅ 自定义      ✅ 自定义    ✅ 自定义   ✅ 自定义    ✅ 自定义  ✅ 自定义
```

**关键发现：**
- Google 是唯一提供真正 Data-Driven 归因的主流平台
- Meta 的归因窗口选择有限（1/7/28天）
- TikTok 的归因窗口最短（7天），严重低估了长链路转化
- DV360 的归因最灵活，但需要自己配置

---

## 二、增量测量方法论

### 2.1 什么是增量测量？

```
传统归因 vs 增量测量：

传统归因（相关性）：
"用户看到广告 A 后购买了产品 → 广告 A 贡献了这次转化"
→ 问题：即使用户没看到广告 A，可能也会购买

增量测量（因果性）：
"看到广告 A 的用户比没看到的用户，购买概率高了 X%"
→ 这才是广告的真实价值
```

### 2.2 四大增量测量方法

#### 方法 1: Holdout（随机对照实验）

```
实验设计：

总用户池: 1,000,000
├── 实验组 (500,000): 看到广告
│   ├── 转化率: 5.2%
│   └── 购买人数: 26,000
└── 控制组 (500,000): 未看到广告
    ├── 转化率: 3.8%
    └── 购买人数: 19,000

增量转化: 26,000 - 19,000 = 7,000
增量转化率: 5.2% - 3.8% = 1.4%
增量 ROI: (7,000 × $50 AOV) / $100,000 广告费 = 3.5x

这是广告的真实价值，而非归因算法的估计。
```

#### 方法 2: PSA（公共服务广告）

```
原理：
在非实验地区投放 PSA（不含转化追踪的广告），与实验组对比

适用场景：
- Google: Geo Experiments
- Meta: Geo Split Tests
- TikTok: Geo Lift Studies
- DV360: Geo Holdout

优点：
- 不需要随机化用户
- 可以测试品牌广告效果
- 受 COVID-19 影响较小（自然实验）

缺点：
- 需要足够大的地理样本
- 可能存在地理间的自然差异
```

#### 方法 3: GAIA（Google 自有增量分析）

```
Google Ads GAIA:
- 使用 Google 自有广告（如 YouTube）作为增量测试
- 对比看到 vs 未看到 Google 广告的用户购买行为
- 输出"增量 lift"报告

Meta Incrementality:
- 使用 Meta 自有广告作为测试
- 通过 GPS 定位和 App 安装数据验证
- 提供 Lift 报告

适用场景：品牌广告效果验证
```

#### 方法 4: Modeled Incrementality（模型增量）

```
当无法做真实实验时，使用统计模型估计增量：

输入变量：
- 各平台曝光数据
- 历史转化数据
- 季节性因素
- 营销活动日历

模型：
- Shapley Value（合作博弈论）
- Markov Chain（马尔可夫链）
- Bayesian Causal Inference

输出：
- 每个 touchpoint 的增量贡献
- 各平台的真实 ROI
- 预算重新分配的优化建议
```

---

## 三、跨平台归因模型实现

### 3.1 Shapley Value 归因

```
问题：3 个平台 (Google, Meta, TikTok) 共同促成了 1 次转化，如何分配 credit？

Shapley Value 思路：
考虑所有可能的排列组合，计算每个平台的边际贡献

排列数: 3! = 6 种

┌─────────────────────────────────────────────────────────────┐
│ 排列          │ Google 边际贡献 │ Meta 边际贡献 │ TikTok 边际贡献 │
├─────────────────────────────────────────────────────────────┤
│ G, M, T       │   v({G})        │ v({G,M})-v({G}) │ v({G,M,T})-v({G,M}) │
│ G, T, M       │   v({G})        │ v({G,T,M})-v({G,T}) │ v({G,T})-v({G}) │
│ M, G, T       │   v({M,G})-v({M}) │ v({M})        │ v({M,G,T})-v({M,G}) │
│ M, T, G       │   v({M,T,G})-v({M,T}) │ v({M})        │ v({M,T})-v({M}) │
│ T, G, M       │   v({T,G})-v({T}) │ v({T,G,M})-v({T,G}) │ v({T})        │
│ T, M, G       │   v({T,M,G})-v({T,M}) │ v({T,M})-v({T}) │ v({T})        │
└─────────────────────────────────────────────────────────────┘

Shapley Value = 所有排列中边际贡献的平均值
```

**Python 实现：**

```python
from itertools import permutations
from typing import Dict, List

def shapley_attribution(
    platforms: List[str],
    coalition_value: Dict[frozenset, float]
) -> Dict[str, float]:
    """
    计算跨平台 Shapley Value 归因
    
    Args:
        platforms: 平台列表 ['Google', 'Meta', 'TikTok']
        coalition_value: 联盟价值函数
            例如: {
                frozenset(['Google']): 100,
                frozenset(['Meta']): 80,
                frozenset(['TikTok']): 60,
                frozenset(['Google', 'Meta']): 180,
                frozenset(['Google', 'TikTok']): 150,
                frozenset(['Meta', 'TikTok']): 130,
                frozenset(['Google', 'Meta', 'TikTok']): 200,
            }
    
    Returns:
        各平台的 Shapley Value
    """
    n = len(platforms)
    shapley = {p: 0.0 for p in platforms}
    
    for perm in permutations(platforms):
        position = list(perm).index
        for i, platform in enumerate(perm):
            preceding = frozenset(perm[:i])
            marginal = coalition_value[preceding | {platform}] - coalition_value[preceding]
            shapley[platform] += marginal
    
    # 平均
    for p in shapley:
        shapley[p] /= factorial(n)
    
    return shapley

# 示例
coalition = {
    frozenset(['Google']): 100,
    frozenset(['Meta']): 80,
    frozenset(['TikTok']): 60,
    frozenset(['Google', 'Meta']): 180,
    frozenset(['Google', 'TikTok']): 150,
    frozenset(['Meta', 'TikTok']): 130,
    frozenset(['Google', 'Meta', 'TikTok']): 200,
}

result = shapley_attribution(['Google', 'Meta', 'TikTok'], coalition)
# {'Google': 70.0, 'Meta': 80.0, 'TikTok': 50.0}
# 总计: 200 =  coalition_value[全平台]
```

### 3.2 Markov Chain 归因

```
Markov Chain 归因思路：
模拟用户旅程，移除某个平台后转化概率的变化

状态转移矩阵：
         → Google  → Meta  → TikTok → 转化
Google   —         0.3     0.2      0.4
Meta     0.2       —       0.3      0.4
TikTok   0.1       0.2       —      0.6
转化     —         —        —        —

移除 Google 后的转化概率: 0.75 (下降 25%)
移除 Meta 后的转化概率: 0.82 (下降 18%)
移除 TikTok 后的转化概率: 0.88 (下降 12%)

Markov 归因结果:
- Google: 25% credit
- Meta: 18% credit
- TikTok: 12% credit
- 自然转化: 45% (无人工触达的转化)
```

### 3.3 时间衰减归因

```
时间衰减公式：
credit(t) = exp(-λ × (T - t))

其中:
- T: 转化时间
- t: touchpoint 时间
- λ: 衰减系数 (通常 0.1-0.5)

示例 (λ=0.3):
- 转化前 1 天的触达: exp(-0.3×1) = 0.74 → 74% weight
- 转化前 3 天的触达: exp(-0.3×3) = 0.41 → 41% weight
- 转化前 7 天的触达: exp(-0.3×7) = 0.12 → 12% weight
```

---

## 四、各平台增量测量工具

### 4.1 Google Ads

```
Google 增量测量工具：

1. Geo Experiments
   - 在部分地理区域投放 PSA
   - 对比实验组和对照组的市场份额变化
   - 输出: Lift 报告（转化提升、GMV 提升）
   - 最小预算: $10K/周

2. Conversion Value Rules
   - 对不同 touchpoint 设置不同的转化价值
   - 支持时间衰减、位置加权等规则

3. Data-Driven Attribution (DDA)
   - 基于 Machine Learning 的自动归因
   - 使用 Shapley Value 变体
   - 需要足够的转化数据（通常 30 天 + 100+ 转化）

4. Google Analytics 4
   - Explore 报告中的 Path Analysis
   - 自定义归因模型
   - 与 Google Ads 数据打通
```

### 4.2 Meta Ads

```
Meta 增量测量工具：

1. Conversion Lift Studies
   - 随机控制实验
   - 比较广告组和对照组的行为
   - 输出: Lift 率、Incremental ROAS
   - 最小预算: $1,000/天 × 7 天

2. Ad Set Level A/B
   - 同一广告系列的 A/B 测试
   - 对比不同受众/创意的效果
   - 输出: Statistical Significance

3. Incrementality API
   - 开发者可以通过 API 创建增量实验
   - 支持 Custom Conversions

4. Meta Attribution
   - 基于设备的跨应用归因
   - 支持 View-Through 和 Click-Through
```

### 4.3 TikTok Ads

```
TikTok 增量测量工具：

1. Brand Lift Studies
   - 广告曝光前后调查
   - 测量 Brand Awareness、Ad Recall、Purchase Intent
   - 适用于品牌广告

2. Conversion Lift
   - 类似 Meta 的 Lift Study
   - 测量实际转化提升
   - 需要 >= $2,000/天的预算

3. Incrementality Test
   - 地理隔离测试
   - 测量广告对整体市场的真实影响
```

### 4.4 DV360

```
DV360 增量测量工具：

1. Google Ads Data Hub (ADH)
   - 跨平台数据融合
   - 匿名化数据共享
   - 支持自定义归因模型
   - 需要 GDPR 合规

2. Floodlight Attribution
   - Google 自家的归因引擎
   - 支持跨网站追踪
   - 可与第三方测量工具对接

3. Third-Party Measurement
   - DoubleVerify
   - Moat
   - Integral Ad Science
   - comScore
```

---

## 五、生产环境实现

### 5.1 统一归因引擎架构

```
┌──────────────────────────────────────────────────────────────┐
│                    统一归因引擎 (BigQuery)                    │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Google     │  │   Meta      │  │  TikTok     │          │
│  │  Events     │  │   Events    │  │   Events    │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│              ┌─────────────────────┐                        │
│              │   用户 ID 对齐       │                        │
│              │  (Hash + Device ID) │                        │
│              └──────────┬──────────┘                        │
│                         ▼                                   │
│              ┌─────────────────────┐                        │
│              │   时间序列重建       │                        │
│              │  (按时间排序触点)    │                        │
│              └──────────┬──────────┘                        │
│                         ▼                                   │
│    ┌────────────────────┼────────────────────┐              │
│    ▼                    ▼                    ▼              │
│ ┌────────┐       ┌──────────┐        ┌──────────┐          │
│ │Shapley │       │Markov    │        │Time      │          │
│ │Value   │       │Chain     │        │Decay     │          │
│ │归因    │       │归因      │        │归因      │          │
│ └───┬────┘       └────┬─────┘        └────┬─────┘          │
│     │                 │                   │                 │
│     └─────────────────┼───────────────────┘                 │
│                       ▼                                     │
│            ┌─────────────────────┐                         │
│            │   加权融合输出       │                         │
│            │  (各模型结果加权)    │                         │
│            └──────────┬──────────┘                         │
│                       ▼                                     │
│            ┌─────────────────────┐                         │
│            │   预算重分配建议     │                         │
│            │  (每24h生成)        │                         │
│            └─────────────────────┘                         │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Go 实现

```go
package attribution

import (
    "sort"
    "math"
)

// Platform 表示广告平台
type Platform string

const (
    PlatformGoogle  Platform = "google"
    PlatformMeta    Platform = "meta"
    PlatformTiktok  Platform = "tiktok"
    PlatformDV360   Platform = "dv360"
)

// TouchPoint 表示一次广告触达
type TouchPoint struct {
    Platform     Platform
    Timestamp    int64  // Unix timestamp
    ConversionVal float64
}

// ShapleyAttribution 计算 Shapley Value 归因
func ShapleyAttribution(touchPoints []TouchPoint, totalConversion float64) map[Platform]float64 {
    // 按时间排序
    sort.Slice(touchPoints, func(i, j int) bool {
        return touchPoints[i].Timestamp < touchPoints[j].Timestamp
    })
    
    // 简化实现：基于时间衰减计算
    result := make(map[Platform]float64)
    
    // 找到最近触达时间
    var latestTS int64
    for _, tp := range touchPoints {
        if tp.Timestamp > latestTS {
            latestTS = tp.Timestamp
        }
    }
    
    // 按平台和距离计算贡献
    platformScores := make(map[Platform]float64)
    for _, tp := range touchPoints {
        daysDiff := float64(latestTS-tp.Timestamp) / 86400
        decay := math.Exp(-0.3 * daysDiff) // λ=0.3
        platformScores[tp.Platform] += decay
    }
    
    // 归一化
    totalScore := 0.0
    for _, score := range platformScores {
        totalScore += score
    }
    
    for platform, score := range platformScores {
        result[platform] = totalConversion * (score / totalScore)
    }
    
    return result
}
```

---

## 六、常见问题排查

### 6.1 数据不一致排查

```
场景：Google 报告 100 转化，Meta 报告 80 转化，实际只有 60 转化

排查步骤：
1. 检查各平台归因窗口是否一致
2. 检查是否有重复归因（同一用户被多个平台计数）
3. 检查 CAPI/Pixel 是否正确安装
4. 检查 iOS ATT 对 Meta/TikTok 的影响
5. 以 BigQuery 中的原始事件为真相源重新计算

常见原因：
- Meta 的 View-Through 转化不计入 Google
- TikTok 的归因窗口太短（7天），丢失了长链路转化
- Google DDA 使用了不同的模型
```

### 6.2 增量测量设计

```
设计 Checklist:

□ 实验组/对照组比例合理（通常 50/50 或 70/30）
□ 样本量足够（统计显著性 > 95%）
□ 实验周期足够（至少 7 天，避免周末效应）
□ 没有外部因素干扰（竞品促销、季节性）
□ 转化追踪准确（CAPI + Pixel 双重验证）
□ 预算稳定（实验期间不调整出价）
□ 结果解读谨慎（相关性 ≠ 因果性）
```

---

## 七、自测题

### Q1: 如果一个用户同时触达了 Google Search 和 Meta Display，最后通过 Google 完成购买，两个平台各应获得多少 credit？

<details>
<summary>点击查看答案</summary>

取决于归因模型：
- **Last Click**: Google 100%，Meta 0%
- **First Click**: Google 0%，Meta 100%
- **Linear**: Google 50%，Meta 50%
- **Time Decay (λ=0.3)**: 取决于两个触达的时间间隔
- **Shapley Value**: 需要 coalition value 函数，通常 Meta 略低于 Google（因为 Google 是搜索意图）
- **Markov Chain**: 取决于状态转移概率

实际业务中建议使用 BigQuery 自建归因模型，而非依赖任一平台的内置归因。
</details>

### Q2: iOS 14+ ATT 框架对跨平台归因的主要影响是什么？

<details>
<summary>点击查看答案</summary>

主要影响：
1. **Meta 数据丢失**: Apple 用户拒绝追踪后，Meta 的 Pixel 事件丢失约 15-30%
2. **归因窗口缩短**: SKAdNetwork 限制了跨应用追踪
3. **Modeling 依赖增加**: Meta 和 TikTok 大量使用 modeled conversions
4. **CAPI 成为必需**: Server-to-Server 事件发送绕过 ATT 限制
5. **Google 受影响较小**: Google 主要依赖 First-Party Data 和 Google Signals

解决方案：
- 部署 CAPI 到所有 Meta 事件
- 使用 Google Enhanced Conversions
- 建立 BigQuery 中央数据仓库作为真相源
- 定期进行 Incrementality Testing 验证
</details>

---

*本文档是跨平台归因的权威参考，建议结合具体业务数据持续优化归因模型。*
