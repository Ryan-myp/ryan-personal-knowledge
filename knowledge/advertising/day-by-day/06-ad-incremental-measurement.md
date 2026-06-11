# 增量测量：PSA/GEO/causal inference/uplift建模深度指南

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 增量测量核心

---

## 第一部分：增量测量的本质

### 1.1 为什么增量测量重要

```
增量测量的核心问题:

┌──────────────────────────────────────────────────────────────┐
│              增量 vs 有机                                     │
│                                                              │
│  场景: 品牌 A 投放 Google Ads + Facebook Display              │
│                                                              │
│  观测到的总转化 = 10,000                                      │
│  └─ 问题: 如果没有广告，会有多少转化？                          │
│                                                              │
│  回答:                                                       │
│  ├── 增量转化 (Incremental Conversions) = 有广告 - 无广告     │
│  ├── 有机转化 (Organic Conversions) = 无广告情况下的转化       │
│  └─ 增量 ROAS (Incremental ROAS) = 增量收入 / 广告支出        │
│                                                              │
│  关键洞察:                                                   │
│  ├── 如果有机转化 = 8,000                                     │
│  ├── 增量转化 = 10,000 - 8,000 = 2,000                       │
│  ├── 广告贡献 = 2,000 / 10,000 = 20%                         │
│  └─ 大多数转化是有机产生的，广告只是"抢功"                       │
│                                                              │
│  如果不做增量测量:                                            │
│  ├── 你会以为所有 10,000 转化都是广告带来的                    │
│  ├── 可能过度投放 (ROI 被高估)                                │
│  ├── 可能在不需要投放的渠道浪费预算                            │
│  └─ 最终: 广告 ROI 被严重高估                                 │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 增量测量的方法分类

```
┌──────────────────────────────────────────────────────────────┐
│              增量测量方法                                      │
│                                                              │
│  实验方法 (Experimental):                                    │
│  ├── PSA (Pseudo A/B Test) — 伪 A/B 测试                    │
│  ├── Geo Experiment — 地理实验                                │
│  ├── RCT (Randomized Controlled Trial) — 随机对照试验          │
│  └─ Held-out Test — 留存测试                                  │
│                                                              │
│  观察性方法 (Observational):                                 │
│  ├── Markov Attribution — 马尔可夫归因                       │
│  ├── Shapley Value — Shapley 值归因                         │
│  └─ Uplift Modeling — 提升建模                               │
│                                                              │
│  因果推断方法 (Causal):                                      │
│  ├── Propensity Score Matching — 倾向得分匹配                │
│  ├── Doubly Robust — 双重稳健估计                            │
│  ├── Synthetic Control — 合成控制                             │
│  └─ Instrumental Variables — 工具变量                         │
│                                                              │
│  选择指南:                                                   │
│  ├── 最准确: PSA / Geo Experiment (实验方法)                 │
│  ├── 最实用: PSA (成本低，可用)                               │
│  ├── 最便宜: 观察性方法 (但可能不准)                          │
│  └─ 最学术: 因果推断方法 (需要专业统计知识)                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：PSA (Pseudo A/B Test)

### 2.1 PSA 方法

```
PSA 是平台内部实现的增量测量方法:

设定:
├─ N 个用户 (Users)                                         │
├─ 每个渠道 i: 实验组 (Exposed) vs 对照组 (Holdout)           │
├─ 对照组: 不展示广告的用户 (随机选择)                         │
└─ 实验组: 正常展示广告的用户                                 

流程:
├─ Step 1: 用户分层 (Stratification)                          │
│   ├── 按用户 ID 哈希                                         │
│   ├── 随机选择 p% 用户进入对照组                               │
│   ├── 其余 1-p% 用户进入实验组                                 │
│   └─ p 通常 5-10% (Google PSA 默认 5%)                       │
│                                                              │
├─ Step 2: 广告展示                                            │
│   ├── 实验组: 正常竞价、正常展示                               │
│   └─ 对照组: 不参与竞价 (不展示广告)                           │
│                                                              │
├─ Step 3: 转化追踪                                            │
│   ├── 两组用户都追踪转化                                       │
│   ├── 实验组: 转化 = C_exposed                              │
│   └─ 对照组: 转化 = C_holdout                               │
│                                                              │
├─ Step 4: 增量计算                                            │
│   ├── 增量转化 = C_exposed - C_holdout                      │
│   ├── 增量 ROAS = (R_exposed - R_holdout) / Ad Spend        │
│   └─ 有机转化 = C_holdout (对照组转化 = 有机转化)              │
│                                                              │
├─ Step 5: 统计显著性检验                                       │
│   ├── H0: ΔCR = 0 (无增量效果)                               │
│   ├── H1: ΔCR > 0 (有增量效果)                               │
│   └─ p-value < 0.05 → 显著                                  │
│                                                              │
└─ Step 6: 预算优化                                            │
    ├── 增量 ROAS 高的渠道 → 增加预算                          │
    ├── 增量 ROAS 低的渠道 → 减少预算                          │
    └─ 增量 ROAS < 1 → 停止投放 (亏损)                         

示例:
├─ 实验组: 1,000,000 用户, 50,000 转化, $200,000 广告支出      │
│   └─ CR_exposed = 5%                                        │
├─ 对照组: 50,000 用户, 2,000 转化                             │
│   └─ CR_holdout = 4%                                        │
├─ 增量转化 = 50,000 - 2,000 = 48,000                         │
│   └─ 等等，对照组用户少，应该按等比例计算                       │
├─ 正确计算:                                                  │
│   ├── 预期实验组有机转化 = (50,000/1,000,000) × 50,000 = 2,500│
│   ├── 对照组转化 = 2,000                                     │
│   ├── 有机转化率 = 2,000/50,000 = 4%                         │
│   ├── 预期实验组有机转化 = 1,000,000 × 4% = 40,000           │
│   ├── 增量转化 = 50,000 - 40,000 = 10,000                   │
│   ├── 增量 ROAS = (10,000 × $100) / $200,000 = 5.0          │
│   └─ 有机 ROAS = 40,000 × $100 / $200,000 = 20.0            │

经济解释:
├─ 总转化 50,000，其中 40,000 是有机产生的                      │
│   └─ 广告只贡献了 20% (10,000)                               │
├─ 有机 ROAS = 20.0 (如果不花钱也能获得 20x 回报)               │
│   └─ 这不需要广告支出                                          │
├─ 增量 ROAS = 5.0 (广告真正带来的回报)                        │
│   └─ 这才是你应该关注的                                         │
└─ 如果增量 ROAS < 1 → 广告亏损 → 停止投放                     │
```

### 2.2 PSA 的局限性与修正

```
PSA 的局限性:

1. 样本量要求:
   ├── 对照组需要有足够用户                                       │
   ├── p = 5% 时，需要总用户 > 100,000                         │
   └─ 小广告系列可能没有统计显著性                               

2. 时间延迟:
   ├── PSA 需要一定时间积累数据                                   │
   └─ 不适合实时优化                                            

3. 跨渠道效应:
   ├── 如果同时控制多个渠道，会产生交互效应                       │
   └─ 需要设计多变量实验                                        

4. 自选择偏差:
   ├── 广告展示本身可能影响用户行为                               │
   └─ 需要随机化 (RCT) 来消除                                  

修正方法:
├─ 分层 PSA: 按用户特征分层 (年龄/性别/地区)                    │
│   └─ 每层独立计算增量                                         │
│                                                              │
├─ 加权 PSA: 加权用户样本，代表总体                             │
│   └─ 使用逆概率加权 (IPTW)                                   │
│                                                              │
└─ 组合 PSA + 观察性方法:                                       │
    ├── PSA 提供校准基准                                         │
    └─ 观察性方法填补 PSA 空白                                   │
```

---

## 第三部分：Geo Experiment (地理实验)

### 3.1 Geo-Lift 方法

```
Geo-Lift: 通过地理区域随机实验测量增量

设定:
├─ N 个地理区域 (states/counties/cities)                       │
├─ K 个实验区域 (实验组) — 投放广告                              │
├─ N-K 个对照区域 (对照组) — 不投放广告                         │
└─ 实验期: T 天                                                

流程:
├─ Step 1: 区域选择 (Stratification)                           │
│   ├── 按人口/收入/历史销售/季节匹配                            │
│   ├── 配对 (Pairing): 找特征相似的配对区域                     │
│   └─ 随机分配: 在匹配的区域中随机选择实验/对照                   │
│                                                              │
├─ Step 2: 数据收集                                            │
│   ├── 实验前基线: T_1 天                                      │
│   ├── 实验期: T_2 天                                          │
│   └─ 实验后: T_3 天 (可选: 测残留效应)                        │
│                                                              │
├─ Step 3: 分析方法                                            │
│   └─ 见下方详细分析                                            │
│                                                              │
└─ Step 4: 增量计算                                            │
    ├── Incremental Lift = Δ                                   │
    ├── Incremental ROAS = ΔRevenue / Ad Spend                 │
    └─ Incremental CPA = Ad Spend / Incremental Conversions    │

分析方法:

1. Difference-in-Differences (DiD):
├─ 公式: Δ = (Y_exp_post - Y_exp_pre) - (Y_ctrl_post - Y_ctrl_pre)
│   Y = 销售/转化/用户数                                         │
│                                                              │
├─ 假设: 如果没有实验，实验组和对照组的变化趋势相同                │
│   └─ Parallel Trends Assumption                              │
│                                                              │
├─ 优点:                                                       │
│   ├── 消除时间趋势                                             │
│   ├── 消除组间差异                                             │
│   └─ 简单易懂                                                  │
│                                                              │
└─ 缺点:                                                       │
    ├── 需要平行趋势假设                                         │
    └─ 对异常值敏感                                             

2. Synthetic Control (合成控制):
├─ 用多个对照区域的加权组合，构造"合成对照组"                     │
│   └─ w1 × Region_1 + w2 × Region_2 + ... = Synthetic        │
│                                                              │
├─ 优化: 最小化实验前实验组与合成的差异                           │
│   └─ Min Σ (Y_exp - Y_synthetic)^2                          │
│                                                              │
├─ 优点:                                                       │
│   ├── 不依赖平行趋势假设                                       │
│   ├── 可以处理多个对照区域                                     │
│   └─ 更灵活                                                   │
│                                                              │
└─ 缺点:                                                       │
    ├── 需要足够多的对照区域                                     │
    └─ 计算复杂                                                 

3. Panel Method (面板方法):
├─ 多层模型 (Multi-level Model)                                │
│   └─ Region 作为随机效应                                      │
│                                                              │
├─ 时间序列分解:                                               │
│   └─ Y = Trend + Seasonality + Treatment Effect + Noise      │
│                                                              │
└─ 优点: 利用所有数据，更精确                                    │
```

### 3.2 Geo Experiment 代码实现

```python
import numpy as np
import pandas as pd
from statsmodels.formula.api import ols

def perform_did(sales_df: pd.DataFrame,
                period: str,
                treatment_region: list,
                control_region: list) -> dict:
    """
    执行 Difference-in-Differences (DiD) 分析
    
    参数:
    ├── sales_df: 销售数据 (region, period, sales)
    ├── period: 'pre' 或 'post'
    ├── treatment_region: 实验组区域列表
    └─ control_region: 对照组区域列表
    
    返回:
    └─ 增量分析结果
    """
    # 创建处理变量
    sales_df['treated'] = sales_df['region'].isin(treatment_region).astype(int)
    sales_df['post'] = (sales_df['period'] == 'post').astype(int)
    sales_df['did'] = sales_df['treated'] * sales_df['post']
    
    # DiD 回归
    model = ols('sales ~ treated + post + did', data=sales_df).fit()
    
    # 提取增量效应
    increment = model.params['did']
    p_value = model.pvalues['did']
    ci = model.conf_int()['did']
    
    return {
        'increment': increment,
        'p_value': p_value,
        'confidence_interval': ci,
        'significant': p_value < 0.05,
        'coefficient': model.params['did']
    }

def synthetic_control(sales_df: pd.DataFrame,
                       treatment_region: str,
                       control_regions: list) -> dict:
    """
    合成控制方法
    
    参数:
    ├── sales_df: 销售数据 (region, date, sales)
    ├── treatment_region: 实验组区域
    └─ control_regions: 对照区域列表
    
    返回:
    └─ 增量分析结果
    """
    # 获取数据
    treat_sales = sales_df[sales_df['region'] == treatment_region]['sales'].values
    control_sales = sales_df[sales_df['region'].isin(control_regions)]
    
    # 优化权重: 最小化实验前的差异
    # 简化: 等权平均
    control_weights = np.ones(len(control_regions)) / len(control_regions)
    synthetic_sales = np.average(
        control_sales.pivot_table(index='date', columns='region', values='sales')[control_regions].values,
        axis=1,
        weights=control_weights
    )
    
    # 计算增量 (实验期)
    pre_mask = sales_df['period'] == 'pre'
    post_mask = sales_df['period'] == 'post'
    
    pre_diff = np.mean(treat_sales[pre_mask] - synthetic_sales[pre_mask])
    post_diff = np.mean(treat_sales[post_mask] - synthetic_sales[post_mask])
    
    increment = post_diff - pre_diff
    
    return {
        'increment': increment,
        'pre_difference': pre_diff,
        'post_difference': post_diff,
    }
```

---

## 第四部分：Uplift Modeling (提升建模)

### 4.1 Uplift 定义

```
Uplift Modeling: 预测每个个体对广告的"提升"

设定:
├─ 每个用户有四种可能状态:                                      │
│   ├── Sure Things: 无论是否广告都会转化 (不可提升)              │
│   ├── Lost Causes: 无论是否广告都不会转化 (无法提升)            │
│   ├── Persuadables: 广告会转化，不广告不会 (可提升!)            │
│   └─ Sleeping Ducks: 广告反而减少转化 (负面效果!)              │
│                                                              │
├─ 目标: 找出 Persuadables (最该投放广告的用户)                  │
└─ 排除 Sure Things (浪费钱) 和 Lost Causes (没效果)            

Uplift = E[Y|T=1] - E[Y|T=0] = P(转化|广告) - P(转化|无广告)

分类:
├─ Uplift > 0: 正向效果 (Persuadable)                          │
├─ Uplift = 0: 无效果 (Sure Thing / Lost Cause)                │
├─ Uplift < 0: 负向效果 (Sleeping Duck)                        │
└─ Uplift ≈ 0: 需要排除 (不投放广告)                           

为什么重要:
├─ 传统模型预测 P(转化|特征) — 找出最可能转化的人                 │
│   └─ 但不区分 Persuadables 和 Sure Things                     │
│                                                              │
├─ Uplift 模型预测 Uplift — 找出广告真正影响的人                 │
│   └─ 只投放 Persuadables，节省预算                            │
│                                                              │
└─ 实际效果: 节省 20-40% 广告预算，同时保持转化量                  │
```

### 4.2 Uplift 建模方法

```
Uplift 建模方法:

1. Two-Model Approach (双模型法):
├─ 模型 1: P(Y=1|X, T=1) — 广告组转化率                        │
├─ 模型 2: P(Y=1|X, T=0) — 对照组转化率                        │
└─ Uplift = Model_1(X) - Model_2(X)

2. Class Transformation (类转换法):
├─ 目标变量: Y_uplift = Y × (2T - 1)                           │
│   └─ T=1, Y=1 → 1 (广告 + 转化 → 正向)                       │
│   └─ T=1, Y=0 → -1 (广告 + 无转化 → 负向)                     │
│   └─ T=0, Y=1 → -1 (无广告 + 转化 → 负向)                     │
│   └─ T=0, Y=0 → 1 (无广告 + 无转化 → 正向)                    │
└─ 训练模型预测 Y_uplift

3. X-Learner (最先进):
├─ Step 1: 分别训练 Treatment/Control 模型                      │
│   └─ 同 Two-Model                                            │
│                                                              │
├─ Step 2: 计算每个用户的"伪 uplift"                            │
│   └─ tau_i = Y_i - E[Y_i|T=0] (对 treatment 组)              │
│   └─ tau_i = E[Y_i|T=1] - Y_i (对 control 组)                │
│                                                              │
├─ Step 3: 训练第三个模型预测 tau                               │
│   └─ 使用伪 uplift 作为标签                                   │
│                                                              │
└─ Step 4: 加权组合                                              │
    └─ Uplift = w × Model_3(X) + (1-w) × (Model_1 - Model_2)  

4. Causal Forest (因果森林):
├─ 基于随机森林                                                 │
├─ 使用双重机器学习 (Double ML)                                 │
└─ 可以捕获复杂的交互效应                                       

评估:
├─ Qini Curve (类似 ROC Curve)                                 │
│   └─ 按 Uplift 排序，看 Top K 的累积提升                      │
│                                                              │
├─ AUUC (Area Under Uplift Curve)                              │
│   └─ 量化模型排序能力                                         │
│                                                              │
└─ Incremental Lift @ Top K                                   │
    └─ 直接测量 Top K 用户的实际提升                            

实际使用:
├─ Meta: 使用 Uplift 优化受众选择                               │
├─ Google: 使用 PSA 数据训练 Uplift 模型                       │
└─ Amazon: DSP 使用 Uplift 定向                                 
```

---

## 第五部分：增量测量最佳实践

```
增量测量最佳实践:

1. PSA:
├─ p = 5-10% (对照组比例)
├─ 至少持续 2-4 周积累数据
├─ 按渠道独立实验 (避免交互)
└─ 定期校准 (每月/每季度)

2. Geo Experiment:
├─ 至少 10 个区域 (5 实验 + 5 对照)
├─ 实验前基线 ≥ 4 周
├─ 实验期 ≥ 4 周 (消除季节效应)
└─ 使用 DiD + Synthetic Control 双重验证

3. Uplift Modeling:
├─ 需要 RCT 数据 (随机分配)
├─ 使用 X-Learner 或 Causal Forest
├─ 用 Qini Curve 评估
└─ 定期更新模型 (数据漂移)

4. 组合方法:
├─ PSA 校准观察性归因模型
├─ Geo Experiment 验证 PSA
├─ Uplift 优化受众选择
└─ 三管齐下: 最准确
```

---

*今天花 90 分钟：深入掌握广告增量测量技术*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
PSA 中对照组的转化代表什么？

<details>
<summary>查看答案</summary>

对照组转化 = 有机转化 (No-Ad Conversion)
因为对照组没有看到广告，他们的转化是自然产生的。
增量转化 = 实验组转化 - 对照组转化
</details>

### 问题 2
Uplift Modeling 要找出哪类用户？

<details>
<summary>查看答案</summary>

Persuadables: 广告会转化，不广告不会的用户。
排除 Sure Things (不管有没有广告都会转化) 和 Lost Causes (不管有没有广告都不会转化)。
</details>

### 问题 3
DiD (Difference-in-Differences) 的假设是什么？

<details>
<summary>查看答案</summary>

Parallel Trends Assumption (平行趋势假设):
如果没有实验，实验组和对照组的变化趋势应该相同。
</details>

---

*今天花 90 分钟：深入掌握广告增量测量技术*
*答不出自测题？回去重读对应章节。*

---

### 增量测量的 Go 实现

```go
package increment

import (
	"fmt"
	"math"
)

type UpliftModel struct {
	controlData   []Metric
	treatmentData []Metric
}

type Metric struct {
	Value float64
	Type  string
}

func (m *UpliftModel) AddControl(v []Metric)   { m.controlData = v }
func (m *UpliftModel) AddTreatment(v []Metric) { m.treatmentData = v }

func (m *UpliftModel) CalculateUplift(metric string) float64 {
	var ctrl, treat float64
	for _, v := range m.controlData { if v.Type == metric { ctrl += v.Value } }
	for _, v := range m.treatmentData { if v.Type == metric { treat += v.Value } }
	cN := float64(len(m.controlData))
	tN := float64(len(m.treatmentData))
	cM := ctrl / cN
	tM := treat / tN
	if cM == 0 { return 0 }
	return (tM - cM) / cM
}

func (m *UpliftModel) PValue(metric string) float64 {
	u := m.CalculateUplift(metric)
	n := float64(len(m.controlData) + len(m.treatmentData))
	return math.Exp(-u*u*n/2)
}

func main() {
	m := &UpliftModel{}
	m.AddControl([]Metric{{Value: 100, Type: "c"}, {120, "c"}, {90, "c"}})
	m.AddTreatment([]Metric{{150, "c"}, {130, "c"}, {160, "c"}})
	fmt.Printf("Uplift: %.2f%%\n", m.CalculateUplift("c")*100)
}
```
