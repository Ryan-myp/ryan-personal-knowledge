# 广告归因建模：Data-Driven/Markov/Shapley值深度推导

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 归因建模核心

---

## 第一部分：归因问题的本质

### 1.1 为什么归因是核心问题

```
归因问题的本质:

┌──────────────────────────────────────────────────────────────┐
│              归因核心问题                                       │
│                                                              │
│  用户旅程:                                                   │
│  ├── Touchpoint 1: Google Search Ad (品牌搜索)                 │
│  ├── Touchpoint 2: Facebook Display Ad (再营销)                │
│  ├── Touchpoint 3: YouTube Video Ad (视频曝光)                 │
│  ├── Touchpoint 4: Google Search Ad (精准搜索)                 │
│  └─ Conversion: Purchase ($100)                               │
│                                                              │
│  问题: $100 的转化收入如何分配给 4 个 Touchpoint？              │
│  ├── 最后触点归因: 100% → Touchpoint 4                        │
│  ├── 首次触点归因: 100% → Touchpoint 1                        │
│  ├── 线性归因: 每个 25%                                      │
│  ├── 时间衰减: 越近权重越高                                    │
│  ├── 位置归因: 首次 40%/最终 40%/中间 20%                     │
│  └─ Data-Driven: 基于模型计算每个 touchpoint 的贡献             │
│                                                              │
│  归因的核心挑战:                                             │
│  ├── 多触点 (Multi-Touch): 用户可能接触多个渠道               │
│  ├── 滞后效应 (Lagged Effect): 曝光后可能几天才转化             │
│  ├── 交叉效应 (Cross-Device): 手机浏览 → 桌面购买             │
│  └─ 反事实 (Counterfactual): 如果没有这个触点会怎样？           │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 归因模型分类

```
┌──────────────────────────────────────────────────────────────┐
│              归因模型分类                                       │
│                                                              │
│  规则型归因 (Rule-Based):                                     │
│  ├── Last Click — 最后点击 100%                              │
│  ├── First Click — 首次点击 100%                              │
│  ├── Linear — 线性分配 (所有触点平分)                          │
│  ├── Time Decay — 时间衰减 (越近权重越高)                       │
│  ├── Position-Based — 位置归因 (首末各40%，中间20%)             │
│  └─ Custom — 自定义权重                                       │
│                                                              │
│  数据驱动归因 (Data-Driven):                                  │
│  ├── Shapley Value — 合作博弈论                               │
│  ├── Markov Chain — 马尔可夫链                                 │
│  ├── MTAA (Multi-Touch Attribution) — 多点触归因               │
│  └─ Geo Experiment — 地理实验                                  │
│                                                              │
│  因果推断归因 (Causal):                                       │
│  ├── PSA (Pseudo A/B Test) — 伪 A/B 测试                      │
│  ├── Geo Experiment — 地理实验                                 │
│  ├── Uplift Modeling — 提升建模                               │
│  └─ Doubly Robust — 双重稳健估计                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：Shapley Value (合作博弈论)

### 2.1 Shapley Value 定义

```
Shapley Value 来自合作博弈论 (Nobel Prize 2012):

设定:
├─ N 个触点 (channels/touchpoints): {1, 2, ..., n}
├─ 特征函数 v(S): 任意子集 S ⊆ N 的转化概率
└─ 目标: 计算每个触点 i 的 Shapley 值 φ_i

Shapley 值公式:
├─ φ_i(v) = Σ_{S⊆N\{i}} |S|! × (n-|S|-1)! / n! × [v(S∪{i}) - v(S)]
│   │   │   │   │
│   │   │   │   └─ 边际贡献: v(S∪{i}) - v(S)
│   │   │   └─ S 的大小
│   │   └─ S 的大小阶乘
│   └─ n 的阶乘

经济解释:
├─ φ_i = 触点 i 在所有可能 coalition 中的平均边际贡献             │
├─ 考虑所有可能的触点排列                                         │
├─ 对于每个排列，计算 i 加入 coalition 时的边际贡献                 │
└─ 取所有排列的平均值                                            

示例: 3 个触点 A, B, C

所有排列 (3! = 6 种):
├─ [A, B, C]: A 的边际贡献 = v({A}) - v(∅)                     │
│   └─ B 的边际贡献 = v({A,B}) - v({A})                         │
│   └─ C 的边际贡献 = v({A,B,C}) - v({A,B})                     │
├─ [A, C, B]: A 的边际贡献 = v({A}) - v(∅)                      │
│   └─ C 的边际贡献 = v({A,C}) - v({A})                          │
│   └─ B 的边际贡献 = v({A,B,C}) - v({A,C})                     │
├─ [B, A, C]: B 的边际贡献 = v({B}) - v(∅)                      │
│   └─ A 的边际贡献 = v({A,B}) - v({B})                          │
│   └─ C 的边际贡献 = v({A,B,C}) - v({A,B})                     │
├─ [B, C, A]: ...                                               │
├─ [C, A, B]: ...                                               │
└─ [C, B, A]: ...

φ_A = Σ_所有排列 A的边际贡献 / 6
φ_B = Σ_所有排列 B的边际贡献 / 6
φ_C = Σ_所有排列 C的边际贡献 / 6

Shapley 值的性质:
├─ 效率 (Efficiency): Σ φ_i = v(N) - v(∅) = 总转化概率            │
├─ 对称性 (Symmetry): 同等贡献的触点获得同等分配                   │
├─ 零贡献 (Null Player): 对任何 coalition 无贡献则为 0             │
└─ 可加性 (Additivity): 多个游戏的 Shapley 值 = 各游戏之和          │
```

### 2.2 Shapley Value 在归因中的应用

```
归因中的 Shapley Value:

特征函数 v(S) 的定义:
├─ v(∅) = 自然转化率 (No Ads Conversion Rate)                     │
├─ v(S) = 包含触点集 S 的转化概率                                  │
│   └─ 需要: 用户旅程数据 + 转化数据                               │
│                                                              │
计算方式:
├─ 精确计算: O(2^n) — 仅适用于 n ≤ 20                            │
├─ 近似计算: Monte Carlo 采样 — O(K × n)                         │
│   ├── K = 采样次数 (1000-10000)                               │
│   ├── 随机采样排列                                             │
│   └─ 取平均边际贡献                                            │
└─ 启发式近似: Banzhaf Value / Owen Value                        

实际实现 (Google Ads):
├─ 使用 Monte Carlo 采样                                         │
├─ 用户旅程: 按时间排序的触点序列                                  │
├─ v(S) = 实验组转化率 - 对照组转化率                             │
│   └─ 实验组: 包含 S 的旅程                                      │
│   └─ 对照组: 不包含 S 的旅程                                    │
└─ 输出: 每个触点的 Shapley 值 = 贡献度                            

Google Data-Driven Attribution:
├─ 基于 Shapley Value                                            │
├─ 考虑所有触点 (Search/Display/Video/...)                        │
├─ 考虑触点顺序 (Sequence matters)                               │
├─ 考虑触点间隔时间 (Time gap between touchpoints)               │
└─ 输出: 每个触点的贡献百分比                                    

Shapley 值的优势:
├─ 理论保证: 满足 Shapley Axioms                                  │
├─ 公平分配: 每个触点得到应得份额                                  │
├─ 考虑协同效应: v({A,B}) ≠ v({A}) + v({B})                     │
└─ 灵活: 可适配任何触点集                                         

Shapley 值的局限:
├─ 计算复杂: O(2^n) 精确，O(K×n) 近似                           │
├─ 需要大量数据                                                    │
├─ 需要定义 v(S) — 依赖数据质量                                   │
└─ 不适用于实时竞价                                               
```

---

## 第三部分：Markov Chain 归因

### 3.1 Markov 链模型

```
Markov Chain 归因基于移除效应:

核心思想: 移除触点 i，观察转化概率下降多少

设定:
├─ 触点集合: {A, B, C, D, ...}
├─ 状态转移矩阵 P: P(i→j) = 从触点 i 转移到触点 j 的概率
└─ 吸收态 (Absorbing State): Conversion / No Conversion

转移矩阵示例 (4 个触点):
┌─────┬─────┬─────┬─────┬───────┬─────────┐
│ From│  A  │  B  │  C  │   D   │  Conv   │
├─────┼─────┼─────┼─────┼───────┼─────────┤
│  A  │ 0.1 │ 0.3 │ 0.2 │  0.1  │  0.3    │
│  B  │ 0.2 │ 0.1 │ 0.3 │  0.1  │  0.3    │
│  C  │ 0.1 │ 0.2 │ 0.1 │  0.2  │  0.4    │
│  D  │ 0.1 │ 0.1 │ 0.2 │  0.1  │  0.5    │
│Conv │  0  │  0  │  0  │   0   │   1     │
│None │  0  │  0  │  0  │   0   │   1     │
└─────┴─────┴─────┴───────┴─────────┘

计算触点 i 的影响力:
├─ Step 1: 计算完整矩阵 P 的转化概率: v(N)                     │
│   └─ 解吸收马尔可夫链: v(N) = (I - Q)^{-1} R                 │
│       Q = 转移矩阵 (不含吸收态)                                 │
│       R = 转移到吸收态的概率                                    │
│                                                              │
├─ Step 2: 移除触点 i，得到 P(-i)，计算转化概率: v(N\{i})       │
│   └─ 移除 i: 将 P 中涉及 i 的行和列设为 0 (或重归一化)          │
│                                                              │
├─ Step 3: 计算移除效应:                                        │
│   └─ Impact(i) = v(N) - v(N\{i})                              │
│                                                              │
└─ Step 4: 归一化:                                              │
    └─ Attribution(i) = Impact(i) / Σ_j Impact(j)             

经济解释:
├─ Impact(i) = 移除触点 i 导致的转化概率下降                      │
├─ 越大 Impact 的触点 = 越关键 (没有它就转化不了)                 │
└─ 归一化后 = 每个触点的贡献百分比                               

Markov 链的优势:
├─ 考虑触点序列: P(i→j) ≠ P(j→i)                               │
├─ 考虑协同效应: v({A,B}) ≠ v({A}) + v({B})                    │
├─ 计算效率: O(n^3) (矩阵求逆)                                  │
└─ 可扩展: 支持任意数量的触点                                    

Markov 链的局限:
├─ 马尔可夫假设: P(i→j) 只依赖当前状态                            │
├─ 需要估计转移概率 P — 数据稀疏时不准                            │
└─ 不适合实时 (需要重新估计 P)                                   
```

---

## 第四部分：PSA (Pseudo A/B Test) 归因

### 4.1 PSA 方法

```
PSA (Pseudo A/B Test) / Randomized Controlled Trial:

核心思想: 通过实验测量每个渠道的真实增量效果

设定:
├─ 实验组: 暴露于广告的用户                                     │
├─ 对照组: 未暴露于广告的用户 (Randomly Selected)               │
└─ 观测指标: 转化率/购买金额                                    

PSA 流程:
├─ Step 1: 按渠道分层                                            │
│   └─ 每个渠道: 暴露组 vs 未暴露组                               │
│                                                              │
├─ Step 2: 随机抽样                                               │
│   ├── 对每个渠道，随机选 10-20% 的用户不展示广告                │
│   └─ 其他用户正常展示广告                                       │
│                                                              │
├─ Step 3: 计算增量                                              │
│   ├── ΔCR_i = CR_exposed_i - CR_unexposed_i                  │
│   └─ ΔCR_i = 渠道 i 的增量转化率                               │
│                                                              │
├─ Step 4: 计算贡献                                              │
│   ├── Contribution_i = ΔCR_i × Revenue / Σ ΔCR_j              │
│   └─ 每个渠道的归因 = 其增量 / 总增量                            │
│                                                              │
└─ Step 5: 预算优化                                              │
    ├── Maximize: Σ_i budget_i × ΔCR_i                           │
    └─ s.t. Σ budget_i ≤ Total Budget                         

PSA 的优势:
├─ 因果推断: 直接测量增量效果                                    │
├─ 不依赖模型假设                                                │
├─ 可检测渠道间的替代/互补效应                                    │
└─ 被认为是归因的 "gold standard"                               

PSA 的局限:
├─ 成本高: 需要大量不展示 (浪费)                                  │
├─ 需要时间: 实验周期长                                          │
├─ 统计误差: 需要大样本                                          │
└─ 伦理问题: 故意不给某些用户看广告                             

Google PSA:
├─ 随机选 5-10% 的用户不展示广告                                  │
├─ 每周/每月更新                                                 │
├─ 与 Data-Driven Attribution 结合                               │
└─ 输出: 每个渠道的增量 ROAS                                    

Meta Lift Study:
├─ Geo-Lift: 按地区随机划分                                     │
├─ 实验组地区: 正常投放                                          │
├─ 对照组地区: 停止投放                                          │
└─ 比较两地区销售差异                                           
```

---

## 第五部分：Geo Experiment 归因

### 5.1 Geo-Lift 方法

```
Geo-Lift: 通过地理实验测量增量效果

设定:
├─ N 个地理区域 (states/counties/cities)
├─ K 个实验区域 (实验组)
├─ N-K 个对照区域 (对照组)
└─ 实验组: 投放广告
    对照组: 不投放广告

流程:
├─ Step 1: 区域划分                                              │
│   ├── 按特征匹配: 实验组和对照组区域相似                         │
│   ├── 特征: 人口/收入/历史销售/季节                              │
│   └─ 随机分配: 在匹配的区域中随机选择                           │
│                                                              │
├─ Step 2: 数据收集                                              │
│   ├── 实验前 T 天数据 (基线)                                   │
│   ├── 实验期 T' 天数据                                        │
│   └─ 实验后 T'' 天数据 (可选: 测残留效应)                       │
│                                                              │
├─ Step 3: 分析                                                 │
│   ├── Difference-in-Differences (DiD):                         │
│   │   └─ Δ = (Y_exp_post - Y_exp_pre) - (Y_ctrl_post - Y_ctrl_pre) │
│   ├── Synthetic Control:                                      │
│   │   └─ 合成对照: 用其他区域加权构造虚拟对照组                  │
│   └─ Panel Method:                                            │
│       └─ 多层模型 (区域随机效应)                               │
│                                                              │
└─ Step 4: 增量计算                                              │
    ├── Incremental Lift = Δ                                    │
    ├── Incremental ROAS = Incremental Revenue / Ad Spend      │
    └─ Incremental CPA = Ad Spend / Incremental Conversions   

Geo-Lift 的优势:
├─ 因果推断: 真实增量                                            │
├─ 避免自选择偏差: 随机分配区域                                   │
├─ 可测跨渠道效应: 实验组所有渠道都投放                            │
└─ 可测品牌效应: 非直接转化                                      

Geo-Lift 的局限:
├─ 需要足够多的区域                                             │
├─ 区域间存在差异 (即使匹配)                                     │
├─ 实验成本高 (整个区域不投放)                                    │
└─ 不适用于小市场                                               
```

---

## 第六部分：归因模型对比

```
┌──────────────────────────────────────────────────────────────┐
│              归因模型对比                                       │
│                                                              │
│  | 模型          | 因果性  | 复杂度 | 数据要求  | 实用性  │
│  |--------------|-------|-------|---------|--------|
│  | Last Click   | 低    | 低    | 低      | 高     │
│  | First Click  | 低    | 低    | 低      | 中     │
│  | Linear       | 低    | 低    | 低      | 中     │
│  | Time Decay   | 低    | 中    | 低      | 中     │
│  | Position     | 低    | 低    | 低      | 中     │
│  | Shapley      | 中    | 高    | 高      | 高     │
│  | Markov       | 中    | 中    | 中      | 高     │
│  | PSA          | 高    | 高    | 极高    | 中 (高成本)|
│  | Geo-Lift     | 高    | 高    | 高      | 中 (高成本)|
│  | Uplift Model | 高    | 极高  | 极高    | 低     │
└──────────────────────────────────────────────────────────────┘
```

---

## 第七部分：自测题

### 问题 1
Shapley Value 的四个公理是什么？

<details>
<summary>查看答案</summary>

1. Efficiency: Σ φ_i = v(N)
2. Symmetry: 同等贡献获得同等分配
3. Null Player: 无贡献则为0
4. Additivity: 多游戏之和 = 各游戏之和
</details>

### 问题 2
Markov 链归因的 "移除效应" 是什么意思？

<details>
<summary>查看答案</summary>

移除触点 i，重新计算转化概率，观察下降多少。
Impact(i) = v(N) - v(N\{i})
移除后转化概率下降越多 = 触点越关键
</details>

### 问题 3
PSA 和 Geo-Lift 的区别是什么？

<details>
<summary>查看答案</summary>

PSA: 按用户随机划分 (暴露 vs 不暴露)
Geo-Lift: 按地理区域随机划分 (投放 vs 不投放)
PSA 成本低但需要大量用户，Geo-Lift 成本高但更真实
</details>

---

*今天花 90 分钟：深入掌握广告归因建模*
*答不出自测题？回去重读对应章节。*
