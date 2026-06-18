# 广告实验平台深度：A/B 测试/灰度发布/多臂老虎机

> 广告系统的实验平台设计，从 A/B 测试到多臂老虎机到强化学习

---

## 第一部分：为什么广告系统需要实验平台？

### 实验驱动决策

```
广告系统实验场景：
1. 竞价策略：固定出价 vs 目标 CPA vs 目标 ROAS
2. 排序模型：LR vs DeepFM vs DIN
3. 创意模板：简约风 vs 色彩风 vs 生活方式
4. 定向策略：兴趣定向 vs 行为定向 vs Lookalike
5. 出价算法：Bandit vs DQN vs PPO

实验平台核心价值：
• 数据驱动：用数据代替直觉做决策
• 风险控制：小流量验证，避免全量失败
• 快速迭代：快速试错，快速优化
```

### 实验平台架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    实验平台架构                                       │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
│  │ 实验管理    │  │ 流量分配    │  │ 数据采集    │                   │
│  │ • 创建实验  │  │ • 用户分桶  │  │ • 曝光事件  │                   │
│  │ • 配置参数  │  │ • 灰度发布  │  │ • 点击事件  │                   │
│  │ • 设置指标  │  │ • 权重调整  │  │ • 转化事件  │                   │
│  └────────────┘  └────────────┘  └────────────┘                   │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据分析引擎                               │   │
│  │  • 统计分析（t-test/Chi-square/Bayesian）                     │   │
│  │  • 显著性检验（p-value < 0.05）                              │   │
│  │  • 增量计算（Incrementality）                                 │   │
│  │  • 多变量分析                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
│  │ 决策引擎    │  │ 报告生成    │  │ 自动部署    │                   │
│  │ • 获胜判定  │  │ • 可视化    │  │ • 全量发布  │                   │
│  │ • 自动胜出  │  │ • 趋势分析  │  │ • 回滚      │                   │
│  └────────────┘  └────────────┘  └────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：A/B 测试实现

### 用户分桶

```go
package experiment

import (
    "hash/fnv"
    "math/rand"
)

// BucketAssignment 分桶结果
type BucketAssignment struct {
    UserID    string
    Bucket    string // control/treatment_a/treatment_b
    Weight    float64
    Experiment string
}

// BucketManager 分桶管理器
type BucketManager struct {
    buckets map[string][]BucketConfig // experiment -> buckets
}

type BucketConfig struct {
    Name   string
    Weight float64
}

// Assign 用户分桶
func (m *BucketManager) Assign(userID string, experiment string) (*BucketAssignment, error) {
    configs, ok := m.buckets[experiment]
    if !ok {
        return nil, fmt.Errorf("experiment not found: %s", experiment)
    }
    
    // 1. 计算哈希
    h := fnv.New32a()
    h.Write([]byte(userID + ":" + experiment))
    hash := h.Sum32()
    
    // 2. 根据权重分配
    randVal := float64(hash) / float64(math.MaxUint32)
    cumulative := 0.0
    
    for _, bucket := range configs {
        cumulative += bucket.Weight
        if randVal < cumulative {
            return &BucketAssignment{
                UserID:     userID,
                Bucket:     bucket.Name,
                Weight:     bucket.Weight,
                Experiment: experiment,
            }, nil
        }
    }
    
    // 默认 control
    return &BucketAssignment{
        UserID:     userID,
        Bucket:     "control",
        Weight:     1.0,
        Experiment: experiment,
    }, nil
}

// 示例：创建实验
// manager.AddExperiment("bid_strategy", []BucketConfig{
//     {Name: "fixed_bid", Weight: 0.33},
//     {Name: "target_cpa", Weight: 0.33},
//     {Name: "target_roas", Weight: 0.34},
// })
```

### 统计显著性检验

```go
package experiment

import (
    "math"
    "gonum.org/v1/gonum/stat"
)

// TTest 双样本 t 检验
func TTest(control []float64, treatment []float64) (float64, float64) {
    meanC, stdC := stat.MeanStdDev(control, nil)
    meanT, stdT := stat.MeanStdDev(treatment, nil)
    
    nC, nT := float64(len(control)), float64(len(treatment))
    se := math.Sqrt(stdC*stdC/nC + stdT*stdT/nT)
    
    if se == 0 {
        return 0, 1.0
    }
    
    tScore := (meanT - meanC) / se
    
    // 简化 p-value 计算
    pValue := 2 * (1 - cdfT(tScore, nC+nT-2))
    
    return tScore, pValue
}

// BayesianTest 贝叶斯测试
func BayesianTest(control []float64, treatment []float64) (float64, float64) {
    // Beta-Binomial 模型
    alphaC, betaC := updateBetaParams(control)
    alphaT, betaT := updateBetaParams(treatment)
    
    // 模拟计算 P(treatment > control)
    wins := 0
    trials := 100000
    
    for i := 0; i < trials; i++ {
        c := randBeta(alphaC, betaC)
        t := randBeta(alphaT, betaT)
        if t > c {
            wins++
        }
    }
    
    lift := (alphaT/(alphaT+betaT) - alphaC/(alphaC+betaC)) / (alphaC/(alphaC+betaC))
    
    return float64(wins) / float64(trials), lift
}
```

---

## 第三部分：多臂老虎机（Multi-Armed Bandit）

### 为什么用 Bandit 而不是 A/B 测试？

```
A/B 测试的问题：
• 固定分配：control 和 treatment 的流量比例固定
• 浪费：低效的 treatment 也分到大量流量
• 延迟：需要等实验结束才知道哪个更好

Bandit 的优势：
• 动态分配：自动增加好方案的流量
• 探索利用平衡：epsilon-greedy / UCB / Thompson Sampling
• 实时优化：边测试边优化
```

### Bandit 实现

```go
package bandit

import (
    "math"
    "math/rand"
)

// Arm 老虎机臂
type Arm struct {
    ID          string
    Pulls       int
    Rewards     float64
    MeanReward  float64
}

// Bandit 多臂老虎机
type Bandit struct {
    Arms []*Arm
    Epsilon float64 // epsilon-greedy
}

// SelectArm 选择臂（epsilon-greedy）
func (b *Bandit) SelectArm() *Arm {
    if rand.Float64() < b.Epsilon {
        // 探索：随机选择
        return b.Arms[rand.Intn(len(b.Arms))]
    }
    // 利用：选择平均奖励最高的
    var best *Arm
    bestReward := -math.MaxFloat64
    for _, arm := range b.Arms {
        if arm.MeanReward > bestReward {
            bestReward = arm.MeanReward
            best = arm
        }
    }
    return best
}

// Pull 拉动臂
func (b *Bandit) Pull(arm *Arm, reward float64) {
    arm.Pulls++
    arm.Rewards += reward
    arm.MeanReward = arm.Rewards / float64(arm.Pulls)
}

// UCB 选择
func (b *Bandit) SelectArmUCB(totalPulls int) *Arm {
    var best *Arm
    bestScore := -math.MaxFloat64
    
    for _, arm := range b.Arms {
        if arm.Pulls == 0 {
            return arm // 优先选择未测试的
        }
        // UCB1 公式
        exploitation := arm.MeanReward
        exploration := math.Sqrt(2 * math.Log(float64(totalPulls)) / float64(arm.Pulls))
        score := exploitation + exploration
        
        if score > bestScore {
            bestScore = score
            best = arm
        }
    }
    return best
}
```

---

## 第四部分：自测题

### Q1: A/B 测试的样本量如何计算？

**A**: 基于统计功效（power=0.8）、显著性水平（alpha=0.05）、最小可检测效应（MDE）。公式：n = 2 * (Z_alpha/2 + Z_beta)^2 * sigma^2 / delta^2

### Q2: Bandit 和 A/B 测试的区别？

**A**: A/B 测试是探索为主，Bandit 是探索利用平衡。A/B 测试公平比较，Bandit 偏向好的方案。

### Q3: 实验平台的核心指标？

**A**: 统计显著性（p-value）、效应量（lift）、置信区间、统计功效（power）。

---

## 第五部分：生产实践

### 1. 实验设计

```
实验设计要点：
1. 单一变量：每次只测试一个变量
2. 随机分桶：确保对照组和实验组可比
3. 足够样本：基于 MDE 计算样本量
4. 足够时长：至少跑 1-2 个完整周期
```

### 2. 灰度发布

```
灰度发布策略：
1. 1% → 5% → 20% → 50% → 100%
2. 每个阶段监控关键指标
3. 异常时立即回滚
4. 按用户/地域/平台逐步放量
```

### 3. 实验报告

```
实验报告内容：
1. 实验目的和假设
2. 实验设计和分桶
3. 关键指标对比
4. 统计显著性结果
5. 结论和建议
```
