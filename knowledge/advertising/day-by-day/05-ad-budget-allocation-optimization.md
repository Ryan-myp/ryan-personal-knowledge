# 广告预算分配算法：从线性规划到在线优化

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 预算优化核心

---

## 第一部分：预算分配问题建模

### 1.1 问题定义

```
┌──────────────────────────────────────────────────────────────┐
│              预算分配问题                                       │
│                                                              │
│  给定:                                                       │
│  ├── 总预算 B (Budget)                                        │
│  ├── N 个广告渠道/广告系列 (Channels)                          │
│  ├── 每个渠道的 CPA_i (每次转化成本)                           │
│  └─ 每个渠道的 ROI_i (投资回报率)                              │
│                                                              │
│  目标:                                                       │
│  ├── 最大化转化量: Maximize Σ (b_i / CPA_i)                   │
│  ├── 最大化 ROAS: Maximize Σ (b_i × ROI_i) / B              │
│  ├── 最大化收入: Maximize Σ (b_i × revenue_i)               │
│  └─ 约束: Σ b_i ≤ B, b_i ≥ 0                                │
│                                                              │
│  这就是经典的资源分配问题 (Resource Allocation Problem)       │
│  └─ 可以用线性规划 (Linear Programming) 求解                   │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 线性规划模型

```
预算分配的线性规划模型:

最大化:
├─ Maximize: Σ (b_i × ROI_i) / B (ROAS 最大化)
└─ 或 Maximize: Σ (b_i / CPA_i) (转化量最大化)

约束:
├─ Σ b_i ≤ B (总预算)
├─ b_i ≥ 0 (非负)
├─ b_i ≤ b_i_max (每个渠道上限)
└─ b_i ≥ b_i_min (每个渠道下限)

解法:
├─ Simplex Method — 精确解
├─ Interior Point Method — 高效大规模
└─ 贪心算法 (Greedy) — 近似解，简单

贪心算法:
├─ 排序: 按 ROI_i 降序排列
├─ 分配: 先分配 ROI 最高的渠道
├─ 分配: 分配完一个渠道后剩余预算
└─ 重复: 直到预算用完

示例:
├─ B = $10,000
├─ Channel A: ROI = 5.0, CPA = $20
├─ Channel B: ROI = 3.0, CPA = $30
├─ Channel C: ROI = 2.0, CPA = $50
└─ Channel D: ROI = 1.5, CPA = $80

贪心分配:
├─ 先分配 A: $5,000 (ROI=5.0)
├─ 再分配 B: $3,000 (ROI=3.0)
├─ 再分配 C: $1,500 (ROI=2.0)
└─ D 无预算 (ROI=1.5 最低)

总转化 = 5000/20 + 3000/30 + 1500/50 = 250 + 100 + 30 = 380
总 ROAS = (5000×5 + 3000×3 + 1500×2) / 10000 = (25000+9000+3000)/10000 = 3.7
```

---

## 第二部分：边际 ROI 理论

### 2.1 边际 ROI 原理

```
边际 ROI (Marginal ROI) 是预算分配的核心:

定义:
├─ Marginal ROI_i = ΔRevenue_i / ΔBudget_i                  │
├─ 每增加 $1 预算，带来多少收入                                 │
└─ 当 Marginal ROI_i = Marginal ROI_j 时达到最优分配          │

直觉:
├─ 如果你有两个渠道 A 和 B                                    │
├─ A 的边际 ROI = $5/$1 (每投入$1 带来$5 收入)                │
├─ B 的边际 ROI = $3/$1 (每投入$1 带来$3 收入)                │
├─ 你应该优先把钱投给 A                                      │
├─ 但 A 的边际 ROI 会随着预算增加而递减                        │
└─ 当 A 的边际 ROI 降到 $3 时，A 和 B 应该平分预算            │

数学表达:
├─ Maximize: Σ f_i(b_i)                                      │
│   └─ f_i(b) = 渠道 i 的收入函数                               │
│                                                              │
├─ 约束: Σ b_i = B                                           │
│                                                              │
├─ 最优条件 (KKT 条件):                                      │
│   └─ f'_i(b_i) = λ (所有渠道的边际收入相等)                  │
│   └─ λ = Lagrange Multiplier (边际预算价值)                  │
│                                                              │
├─ 解释: 最优时，每个渠道的最后一块钱产生的收入相等              │
└─ 如果某个渠道的边际收入更高，应该给它更多预算                  │
```

### 2.2 收入函数建模

```
收入函数 f_i(b) 的建模:

1. 线性模型 (最简单):
   └─ f_i(b) = r_i × b, 其中 r_i = 平均 ROI
      └─ 边际 ROI = r_i (常数)
      └─ 最优: 全投给 r_i 最大的渠道

2. 对数模型 (递减边际 ROI):
   └─ f_i(b) = a_i × log(1 + b_i/b_0)
      └─ 边际 ROI = a_i / (b_i + b_0) → 递减
      └─ 更符合实际 (预算越多，ROI 越低)

3. 幂函数模型 (更灵活):
   └─ f_i(b) = a_i × b_i^α, 其中 0 < α < 1
      └─ 边际 ROI = a_i × α × b_i^(α-1) → 递减

4. S 形模型 (Sigmoid):
   └─ f_i(b) = L / (1 + e^(-k(b-b_0)))
      └─ 初期 ROI 低 (需要测试)
      └─ 中期 ROI 高 (规模效应)
      └─ 后期 ROI 低 (饱和)

实际中:
├─ 用历史数据拟合 f_i(b)                                     │
├─ 通常用幂函数或对数模型                                      │
└─ 定期更新参数 (在线学习)                                    
```

---

## 第三部分：预算分配算法

### 3.1 贪心算法 (Greedy)

```
贪心算法实现:

算法:
├─ Step 1: 计算每个渠道的边际 ROI                              │
│   └─ mROI_i = (Revenue_i - Revenue_{i-1}) / (Budget_i - Budget_{i-1})
│                                                              │
├─ Step 2: 分配预算                                           │
│   └─ 每次分配 $1 给 mROI 最高的渠道                           │
│   └─ 更新该渠道的 mROI                                       │
│   └─ 重复直到预算用完                                         │
│                                                              │
├─ Step 3: 优化 (Batch Assignment)                            │
│   └─ 每次分配 $Δ 而不是 $1 (加速收敛)                        │
│   └─ 当 mROI 最高的渠道边际 ROI 低于下一个时，停止             │
│                                                              │
└─ 收敛性: 贪心算法在边际 ROI 递减时保证最优解                  │

复杂度:
├─ 精确贪心: O(B/Δ × N) — B=预算, Δ=步长, N=渠道数
├─ 排序贪心: O(N log N) — 按 ROI 排序后分配
└─ 近似贪心: O(N) — 只分配前 K 个渠道

实际使用:
├─ Google Ads: 使用贪心近似                                    │
├─ Meta: 预算分配 + 自动优化                                    │
└─ Amazon: Portfolio 预算分配                                  │
```

### 3.2 动态预算分配 (在线优化)

```
在线预算分配 (Online Budget Allocation):

问题:
├─ 初始不知道 ROI_i                                         │
├─ ROI_i 随时间变化                                          │
└─ 需要在探索 (Exploitation) 和利用 (Exploration) 之间平衡      │

算法: 上下文多臂老虎机 (Contextual Multi-Armed Bandit)

设定:
├─ T 轮 (天/小时/秒)                                        │
├─ N 个渠道 (手臂)                                          │
├─ 每轮选择分配预算 b_i                                       │
├─ 每轮观测到收入 R_i                                        │
└─ 目标: 最大化 Σ_t Σ_i R_i(t)

算法: Thompson Sampling

├─ Step 1: 初始化每个渠道的 ROI 分布                           │
│   └─ ROI_i ~ Beta(α_i, β_i)                                │
│                                                              │
├─ Step 2: 每轮采样                                          │
│   └─ 从每个渠道的 Beta 分布中采样 r_i                        │
│   └─ 选择 r_i 最高的 K 个渠道                               │
│                                                              │
├─ Step 3: 分配预算                                          │
│   └─ 按采样 ROI 比例分配                                    │
│                                                              │
├─ Step 4: 更新 Beta 参数                                    │
│   └─ 观测到收入 R → α_i += R, β_i += Cost                  │
│                                                              │
└─ 收敛: 随着观测增加，Beta 分布收敛到真实 ROI                 │

UCB (Upper Confidence Bound):
├─ 选择 UCB_i 最高的渠道                                      │
│   └─ UCB_i = μ_i + c × √(log t / n_i)                     │
│       μ_i = 历史平均 ROI                                    │
│       n_i = 历史分配次数                                     │
│       c = 探索系数                                           │
│       t = 总轮数                                             │
└─ 自然平衡: 探索 (高不确定性) 和利用 (高均值)                  │

实际实现 (Python):
```python
import numpy as np
from scipy.stats import beta

class BudgetAllocator:
    """
    基于 Thompson Sampling 的预算分配器
    """
    def __init__(self, num_channels: int, total_budget: float):
        self.num_channels = num_channels
        self.total_budget = total_budget
        # Beta 分布参数 (先验)
        self.alpha = np.ones(num_channels)  # 成功
        self.beta = np.ones(num_channels)   # 失败
        self.budget = np.zeros(num_channels)
    
    def allocate(self) -> np.ndarray:
        """分配预算"""
        # Thompson Sampling: 从 Beta 分布中采样
        samples = np.array([
            beta.rvs(self.alpha[i], self.beta[i])
            for i in range(self.num_channels)
        ])
        
        # 按采样 ROI 比例分配
        total_sample = samples.sum()
        allocation = self.total_budget * samples / total_sample
        
        # 确保非负
        allocation = np.maximum(allocation, 0)
        
        return allocation
    
    def update(self, channel: int, revenue: float, cost: float):
        """更新 Beta 参数"""
        # 收入/成本 = ROI
        if cost > 0:
            roi = revenue / cost
            # 将 ROI 映射到 Beta 参数
            # ROI > 1 → 成功, ROI < 1 → 失败
            self.alpha[channel] += max(0, roi - 1)
            self.beta[channel] += max(0, 1 - roi)
        
        self.budget[channel] += cost
```

### 3.3 Pacing (预算消耗速率控制)

```
Pacing 是控制预算消耗速率的核心:

问题:
├─ 预算应该在一天内均匀消耗，而不是提前耗尽                      │
└─ 但如果全天表现都很好，应该允许提前花完 (赚更多)               │

Pacing 公式:
├─ pacing_factor(t) = min(1.0, (B_t - S_t) / (B_t × (1 - t/T)))
│   B_t = 总预算
│   S_t = 已花费
│   t = 当前时间 (0-1, 0=开始, 1=结束)
│   T = 总时间
│                                                              │
├─ 如果 pacing_factor > 1.0 → 花费太快 → 降低出价               │
├─ 如果 pacing_factor < 1.0 → 花费太慢 → 提高出价               │
└─ 如果 pacing_factor ≈ 1.0 → 正常消耗                        

动态 Pacing:
├─ bid(t) = base_bid × pacing_factor(t)                       │
│   └─ base_bid = 基础出价 (由优化目标决定)                      │
│                                                              │
├─ 预测模型:                                                  │
│   ├── 预测剩余时间的转化量                                    │
│   ├── 如果预测转化量 < 目标 → 提高出价                        │
│   └─ 如果预测转化量 > 目标 → 降低出价                        │
│                                                              │
├─ 机器学习方法:                                               │
│   ├── 预测 pAction(t) = P(转化|展示, 时间)                   │
│   ├── bid(t) = target_cpa × pAction(t) × pacing(t)          │
│   └─ 使用 LSTM/Transformer 预测转化概率                      │

Google Ads Pacing:
├─ 智能 pacing (Smart Pacing)                                 │
│   ├── 基于历史数据预测                                       │
│   ├── 考虑时段因素 (白天/夜晚)                                │
│   ├── 考虑竞价强度 (竞争程度)                                 │
│   └─ 实时调整出价                                             │
│                                                              │
└─ Meta Pacing:
    ├── Auto Pacing — 自动优化                                 │
    ├── Manual Pacing — 手动控制                                │
    └─ Accelerated Pacing — 加速 (不控制速率，尽快展示)           │
```

---

## 第四部分：频次控制 (Frequency Capping)

### 4.1 频次控制模型

```
频次控制: 控制每个用户看到的广告次数

设定:
├─ N 个用户 (Users)
├─ F_max — 每个用户在时间窗口 T 内的最大展示次数               │
├─ 每次展示的成本: c (CPM/CPC)
└─ 每次展示的期望转化: p (CTR × CVR)

频次衰减模型:
├─ P(转化 | f 次展示) = p × (1 - e^(-λf))                   │
│   p = 首次展示转化率                                         │
│   λ = 衰减参数 (越大衰减越快)                                 │
│   f = 展示次数                                               │
│                                                              │
├─ 边际转化 = P(f) - P(f-1) = p × e^(-λ(f-1)) × (1-e^(-λ))  │
│                                                              │
└─ 经济学解释:                                                │
    ├── 第一次展示: 转化率最高                                   │
    ├── 第二次展示: 转化率降低                                   │
    ├── 第三次及以后: 转化率急剧降低                             │
    └─ 超过最佳频次后: 边际转化 < 边际成本 → 不应该展示          │

最佳频次 (Optimal Frequency):
├─ 找到 f* 使得:边际 ROI(f*) ≥ 边际成本                          │
│   └─ 边际 ROI = (P(f) - P(f-1)) × Value / Cost               │
│                                                              │
├─ 典型最佳频次:                                               │
│   ├── Search Ads: 1-2 次                                     │
│   ├── Display Ads: 3-5 次                                    │
│   └─ Video Ads: 2-4 次                                      │
│                                                              │
└─ 实际限制:                                                  │
    ├── Facebook: F_max = 1-50 (默认 5)                        │
    ├── Google: F_max = 1-50 (默认 5)                         │
    └─ TikTok: F_max = 1-30 (默认 3)                          │
```

### 4.2 频次控制实现

```
频次控制实现:

数据结构:
├─ User-Frequency Map: {user_id: {ad_id: count}}                │
├─ 使用 Redis (高速读写)                                       │
└─ 过期时间: TTL = T (时间窗口，如 7 天)                        

算法:
├─ Step 1: 接收 Bid Request                                    │
│   └─ 包含 user_id, ad_id, ad_group_id                        │
│                                                              │
├─ Step 2: 查询频次                                           │
│   └─ frequency = Redis.get(user_id:ad_id)                   │
│   └─ 如果 None → frequency = 0                              │
│                                                              │
├─ Step 3: 检查频次限制                                        │
│   └─ 如果 frequency ≥ F_max → 不竞价 (Reject)                │
│                                                              │
├─ Step 4: 竞价                                               │
│   └─ 正常竞价逻辑                                             │
│                                                              │
├─ Step 5: 更新频次                                           │
│   └─ 如果中标 → Redis.incr(user_id:ad_id)                   │
│   └─ 设置 TTL = T                                            │
│                                                              │
└─ 频次上限策略:                                               │
    ├── 全局: 所有广告 (Ad Group/Ad Level)                     │
    ├── 按广告系列: Campaign Level                              │
    └─ 按渠道: Channel Level                                  

优化:
├─ 频次感知出价: bid = base_bid × (1 - frequency/F_max)       │
│   └─ 频次越高，出价越低                                       │
│                                                              │
├─ 频次分组出价:                                              │
│   ├── f=0: 100% 出价 (新用户)                                │
│   ├── f=1: 90% 出价 (再看一次)                               │
│   ├── f=2: 80% 出价                                        │
│   ├── f=3: 70% 出价                                        │
│   └─ f≥4: 50% 出价 (接近上限)                                │
│                                                              │
└─ 个性化频次控制:                                             │
    └─ 高价值用户: F_max = 10 (允许更多展示)                    │
    └─ 低价值用户: F_max = 2 (避免广告疲劳)                     │
```

---

## 第五部分：创意轮替 (Ad Rotation)

### 5.1 创意轮替策略

```
Ad Rotation 策略:

1. 均匀轮替 (Equally):
   ├── 每个创意展示相同次数                                   │
   ├── 公平，但可能浪费在低效创意上                            │
   └─ 适合: 测试新创意阶段                                    

2. 按性能轮替 (By Performance):
   ├── 高 CTR 创意获得更多展示                                │
   ├── 低 CTR 创意减少展示或暂停                              │
   └─ 适合: 已有历史数据的广告系列                             

3. 最优探索 (Thompson Sampling):
   ├── 同时探索 (展示所有创意) 和利用 (展示最佳创意)            │
   ├── 自适应: 随着数据增加，逐渐偏向最佳创意                    │
   └─ 适合: 需要平衡探索和利用的广告系列                       

4. 上下文适配 (Contextual):
   ├── 不同时间段展示不同创意                                  │
   ├── 不同受众展示不同创意                                   │
   └─ 动态创意优化 (DCO) — 自动组合创意元素                   

创意 A/B 测试:
├─ 设置: 两个创意 A 和 B，各分配 50% 流量                     │
├─ 观测: 点击率、转化率、CPA                                 │
├─ 统计检验: t-test / χ²-test                               │
│   └─ p-value < 0.05 → 差异显著                             │
├─ 结论:                                                    │
│   ├── A 显著优于 B → 100% 展示 A                          │
│   ├── B 显著优于 A → 100% 展示 B                          │
│   └─ 无显著差异 → 继续测试或暂停低表现                      │
└─ 多臂老虎机 (Multi-Armed Bandit):                           │
    ├── 比 A/B 测试更高效 (更快发现最佳)                       │
    ├── 动态调整流量分配                                      │
    └─ 适合: 快速迭代优化的广告系列                            │
```

### 5.2 动态创意优化 (DCO)

```
DCO (Dynamic Creative Optimization):

核心思想: 自动组合创意元素，找到最佳组合

创意元素:
├─ 图片 (Image): 多张可选                                     │
├─ 视频 (Video): 多个可选                                     │
├─ 标题 (Headline): 多个可选                                  │
├─ 描述 (Description): 多个可选                               │
├─ CTA: 多个可选                                              │
└─ Logo: 多个可选                                            

组合空间:
├─ 如果每个元素有 3 个选项，5 个元素                            │
│   └─ 组合数 = 3^5 = 243 种组合                              │
│                                                              │
├─ 问题: 如何找到最佳组合？                                    │
│   ├── 暴力搜索: 测试所有组合 → 不可行                         │
│   └─ 机器学习: 预测每个元素的价值 → 可行                      │
│                                                              │
├─ 方法 1: Factorization (因式分解)                            │
│   ├── 假设创意价值 = Σ 元素价值 (线性)                        │
│   ├── 预测每个元素的点击概率                                  │
│   ├── 选择元素价值之和最大的组合作为最佳组合                    │
│   └─ 简单高效，但忽略元素间交互                               │
│                                                              │
├─ 方法 2: Interaction Model (交互模型)                        │
│   ├── 考虑元素间交互 (非加和)                                │
│   ├── 使用 DeepFM / Attention 模型                           │
│   ├── 学习元素组合的点击概率                                  │
│   └─ 更准确，但需要更多数据                                   │
│                                                              │
├─ 方法 3: Reinforcement Learning (强化学习)                   │
│   ├── 每个创意组合是一个"动作"                                 │
│   ├── 点击/转化是奖励                                         │
│   ├── 使用 Thompson Sampling / UCB 选择最佳组合               │
│   └─ 自适应: 不断优化组合策略                                 │
│                                                              │
└─ 实际实现 (Google/DSP):                                     │
    ├── 预计算: 基于历史数据，计算每个元素的价值                  │
    ├── 实时: 根据用户画像，选择最佳元素组合                    │
    └─ 反馈: 收集点击/转化数据，更新模型                        │
```

---

## 第六部分：自测题

### 问题 1
预算分配的最优条件是什么？

<details>
<summary>查看答案</summary>

最优时，所有渠道的边际 ROI 相等: f'_i(b_i) = λ (λ 是 Lagrange Multiplier)
如果某个渠道的边际 ROI 更高，应该给它更多预算。
</details>

### 问题 2
Thompson Sampling 如何用于预算分配？

<details>
<summary>查看答案</summary>

1. 每个渠道的 ROI 用 Beta 分布建模
2. 每轮从 Beta 分布中采样
3. 按采样 ROI 比例分配预算
4. 观测收入后更新 Beta 参数
5. 自然平衡探索和利用
</details>

### 问题 3
频次控制的最佳频次通常是多少？

<details>
<summary>查看答案</summary>

- Search Ads: 1-2 次
- Display Ads: 3-5 次
- Video Ads: 2-4 次
超出最佳频次后边际转化 < 边际成本
</details>

---

*今天花 90 分钟：深入掌握广告预算分配与优化策略*
*答不出自测题？回去重读对应章节。*
