# 竞价策略优化深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、出价策略架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       竞价策略优化架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  出价策略 = f(目标价值, 竞争强度, 预算约束, 历史表现)                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    出价策略分类                              │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                             │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │   │
│  │  │   自动出价      │  │   手动出价      │  │  智能出价   │  │   │
│  │  ├─────────────────┤  ├─────────────────┤  ├─────────────┤  │   │
│  │  │ • Target CPA   │  │ • 固定出价      │  │ • pCTR 出价 │  │   │
│  │  │ • Target ROAS  │  │ • 区间出价      │  │ • 强化学习  │  │   │
│  │  │ • Maximize     │  │ • 阶梯出价      │  │ • 贝叶斯优化│  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────┘  │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  核心优化目标:                                                       │
│  ├─ 最大化转化价值 (Maximize Value)                                 │
│  ├─ 控制成本 (Target CPA/ROAS)                                      │
│  └─ 平衡预算消耗 (Budget Pacing)                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心出价算法

### 2.1 pCTR 出价算法

```go
// 文件: bidding/ptrc_bidding.go
package bidding

import (
    "context"
    "math"
)

// PTRCBidding pCTR 出价策略
type PTRCBidding struct {
    targetCPA  float64  // 目标转化成本
    pCTRModel  *CTRModel
}

// CalculateBid 计算出价
func (b *PTRCBidding) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
    // 1. 预测 pCTR
    pCTR, err := b.pCTRModel.Predict(ctx, req)
    if err != nil {
        return 0, err
    }
    
    // 2. 预测 pCVR
    pCVR, err := b.pCVRModel.Predict(ctx, req)
    if err != nil {
        return 0, err
    }
    
    // 3. 计算期望转化价值
    expectedValue := pCTR * pCVR * b.targetCPA
    
    // 4. 应用保守系数 (避免高估)
    conservativeFactor := 0.9
    bid := expectedValue * conservativeFactor
    
    return bid, nil
}

// Beta分布建模不确定性
func (b *PTRCBidding) CalculateBidWithUncertainty(
    ctx context.Context,
    req *BidRequest,
    confidence float64,
) (float64, error) {
    // 获取 pCTR 的均值和方差
    mean, variance := b.pCTRModel.GetPrediction(req)
    
    // Beta 分布分位数
    // 使用正态近似: Q = mean - z * sqrt(variance)
    zScore := normalInverseCDF(confidence)
    adjustedCTR := mean - zScore*math.Sqrt(variance)
    
    // 计算保守出价
    pCVR, _ := b.pCVRModel.Predict(ctx, req)
    expectedValue := adjustedCTR * pCVR * b.targetCPA
    
    return expectedValue * 0.9, nil
}
```

### 2.2 目标 CPA 出价

```go
// 文件: bidding/target_cpa.go
package bidding

import (
    "context"
    "time"
)

// TargetCPABidding 目标 CPA 出价策略
type TargetCPABidding struct {
    targetCPA   float64
    bidOptimizer *BidOptimizer
    history     *ConversionHistory
}

// CalculateBid 计算目标 CPA 出价
func (b *TargetCPABidding) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
    // 1. 获取历史转化数据
    historicalCVR := b.history.GetCVR(req.AdID, req.UserSegment)
    
    // 2. 预测当前 pCVR
    predictedCVR, _ := b.bidOptimizer.PredictCVR(ctx, req)
    
    // 3. 融合历史与预测
    blendedCVR := 0.7*predictedCVR + 0.3*historicalCVR
    
    // 4. 计算出价
    if blendedCVR <= 0 {
        return b.getMinBid(), nil
    }
    
    bid := b.targetCPA * blendedCVR
    
    // 5. 应用预算约束
    bid = b.applyBudgetConstraint(ctx, bid)
    
    return bid, nil
}

// applyBudgetConstraint 应用预算约束
func (b *TargetCPABidding) applyBudgetConstraint(ctx context.Context, bid float64) float64 {
    // 获取剩余预算
    budget, remaining := b.getRemainingBudget(ctx)
    
    // 计算时间剩余比例
    elapsed := time.Since(b.startTime)
    timeRatio := elapsed / b.duration
    
    // 计算期望消耗
    expectedSpend := bid * b.estimateImpressions()
    
    // 如果预算紧张，降低出价
    if expectedSpend > remaining {
        bid *= remaining / expectedSpend
    }
    
    return bid
}
```

---

## 三、强化学习出价

### 3.1 DQN 出价Agent

```go
// 文件: bidding/dqn_agent.go
package bidding

import (
    "github.com/gonum/blas"
    "github.com/gonum/mat"
)

// DQNAgent Deep Q-Network 出价 Agent
type DQNAgent struct {
    network       *NeuralNetwork
    targetNetwork *NeuralNetwork
    replayBuffer  *ReplayBuffer
    epsilon       float64
    learningRate  float64
    gamma         float64 // 折扣因子
}

// State 状态空间
type State struct {
    CurrentBid    float32
    BudgetLeft    float32
    TimeRemaining float32
    ImpressionCnt float32
    ConversionCnt float32
}

// Action 动作空间 (出价调整幅度)
type Action int

const (
    BidIncrease  Action = iota // 提高出价
    BidDecrease                // 降低出价
    BidKeep                    // 保持出价
)

// Train 训练 Agent
func (a *DQNAgent) Train(ctx context.Context, transitions []Transition) error {
    for _, t := range transitions {
        // 1. 选择动作 (ε-greedy)
        action := a.selectAction(t.State)
        
        // 2. 执行动作，获取奖励
        nextState, reward := a.executeAction(ctx, t.State, action)
        
        // 3. 存储到回放缓冲区
        a.replayBuffer.Push(t.State, action, reward, nextState, t.Done)
        
        // 4. 样本学习
        if a.replayBuffer.Size() > BATCH_SIZE {
            batch := a.replayBuffer.Sample(BATCH_SIZE)
            a.learn(batch)
        }
    }
    
    // 5. 定期更新目标网络
    a.syncTargetNetwork()
    
    return nil
}

// learn 学习
func (a *DQNAgent) learn(batch []Transition) {
    for _, t := range batch {
        // 计算目标 Q 值
        targetQ := t.Reward
        if !t.Done {
            maxNextQ := a.targetNetwork.Predict(t.NextState)
            targetQ += a.gamma * maxNextQ
        }
        
        // 当前 Q 值
        currentQ := a.network.Predict(t.State, t.Action)
        
        // 计算 loss
        loss := (targetQ - currentQ) * (targetQ - currentQ)
        
        // 反向传播更新权重
        a.network.Backpropagate(loss)
    }
}
```

### 3.2 上下文多臂老虎机

```go
// 文件: bidding/contextual_bandit.go
package bidding

import (
    "math"
    "sort"
)

// ContextualBandit 上下文多臂老虎机
type ContextualBandit struct {
    arms      []*Arm
    context   Context
}

type Arm struct {
    Name        string
    Pulls       int
    TotalReward float64
    Parameters  *mat.Dense // UCB 参数
}

// SelectArm 选择臂 (UCB1 算法)
func (b *ContextualBandit) SelectArm() *Arm {
    n := 0
    for _, arm := range b.arms {
        n += arm.Pulls
    }
    
    bestUCB := -1.0
    var selected *Arm
    
    for _, arm := range b.arms {
        if arm.Pulls == 0 {
            return arm // 优先选择未尝试过的臂
        }
        
        // UCB1 公式: mean + sqrt(2 * ln(n) / k)
        mean := arm.TotalReward / float64(arm.Pulls)
        ucb := mean + math.Sqrt(2.0*math.Log(float64(n))/float64(arm.Pulls))
        
        if ucb > bestUCB {
            bestUCB = ucb
            selected = arm
        }
    }
    
    return selected
}

// Update 更新臂的统计信息
func (b *ContextualBandit) Update(chosenArm *Arm, reward float64) {
    chosenArm.Pulls++
    chosenArm.TotalReward += reward
}
```

---

## 四、预算分配优化

### 4.1 实时预算 pacing

```go
// 文件: bidding/budget_pacing.go
package bidding

import (
    "context"
    "time"
)

// BudgetPacer 预算 pacing 控制器
type BudgetPacer struct {
    totalBudget    float64
    startTime      time.Time
    duration       time.Duration
    currentSpend   float64
    alpha          float64 // 学习率
}

// CalculateBidAdjustment 计算出价调整因子
func (p *BudgetPacer) CalculateBidAdjustment(ctx context.Context) float64 {
    elapsed := time.Since(p.startTime)
    timeRatio := elapsed / p.duration
    
    // 期望消耗进度
    expectedRatio := timeRatio
    
    // 实际消耗进度
    actualRatio := p.currentSpend / p.totalBudget
    
    // 偏差
    deviation := actualRatio - expectedRatio
    
    // 调整因子: 超支则降低出价，不足则提高出价
    adjustment := 1.0 - p.alpha*deviation
    
    // 限制调整幅度
    if adjustment < 0.5 {
        adjustment = 0.5
    }
    if adjustment > 1.5 {
        adjustment = 1.5
    }
    
    return adjustment
}

// UpdateSpend 更新已消耗预算
func (p *BudgetPacer) UpdateSpend(amount float64) {
    p.currentSpend += amount
}
```

### 4.2 多广告主预算分配

```go
// 文件: bidding/multi_advertiser_allocation.go
package bidding

import (
    "github.com/gonum/optimize"
)

// MultiAdvertiserAllocation 多广告主预算分配
type MultiAdvertiserAllocation struct {
    advertisers []*Advertiser
    totalBudget float64
}

type Advertiser struct {
    ID       string
    Budget   float64
    Target   string // CPA, ROAS
    Efficiency float64 // 单位预算收益
}

// Allocate 分配预算
func (a *MultiAdvertiserAllocation) Allocate() map[string]float64 {
    // 线性规划优化
    vars := make([]float64, len(a.advertisers))
    bounds := make([]optimize.Bounds, len(a.advertisers))
    
    for i, adv := range a.advertisers {
        bounds[i] = optimize.Bounds{Min: 0, Max: adv.Budget}
    }
    
    // 目标函数: 最大化总转化价值
    objective := func(x []float64) float64 {
        totalValue := 0.0
        for i, adv := range a.advertisers {
            totalValue += x[i] * adv.Efficiency
        }
        return -totalValue // 负号因为优化器是最小化
    }
    
    result, err := optimize.Minimize(objective, vars, bounds, nil)
    if err != nil {
        return a.equalAllocation()
    }
    
    // 转换为分配结果
    allocation := make(map[string]float64)
    for i, adv := range a.advertisers {
        allocation[adv.ID] = result.X[i]
    }
    
    return allocation
}

func (a *MultiAdvertiserAllocation) equalAllocation() map[string]float64 {
    equal := a.totalBudget / float64(len(a.advertisers))
    allocation := make(map[string]float64)
    for _, adv := range a.advertisers {
        allocation[adv.ID] = equal
    }
    return allocation
}
```

---

## 五、性能基准

```
┌─────────────────────────────────────────────────────────────────┐
│                    出价策略性能基准                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  策略类型            ROI提升    计算延迟    实现复杂度           │
│  ─────────────────────────────────────────────────────────    │
│  固定出价            0%        <1ms       简单                  │
│  pCTR 出价          +15%       5ms       中等                  │
│  目标 CPA           +25%      10ms       中等                  │
│  强化学习出价        +35%      20ms       复杂                  │
│  多臂老虎机          +20%       8ms       中等                  │
│                                                                 │
│  推荐方案:                                                       │
│  ├─ 新广告主 (冷启动): 固定出价 + 多臂老虎机探索                 │
│  ├─ 成长期: pCTR 出价 + 目标 CPA                                 │
│  └─ 成熟期: 强化学习出价                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 六、实战排障指南

```
问题 1: 出价过高导致亏损
症状: eCPM 高但 ROI 低
原因:
  - pCTR 预测偏高
  - 未考虑转化概率
解决方案:
  - 使用保守系数
  - 引入 pCVR 预估
  - 定期校准模型

问题 2: 预算消耗过快
症状: 上午就花完全天预算
原因:
  - pacing 策略失效
  - 竞争加剧未及时调整
解决方案:
  - 启用实时 pacing
  - 增加价格敏感度
  - 动态调整出价上限

问题 3: 强化学习收敛慢
症状: 初期性能波动大
原因:
  - 探索不足
  - 奖励设计不合理
解决方案:
  - 使用 UCB 初始化
  - 调整探索率衰减
  - 增加课程学习
```

---

## 七、参考资料

```
核心论文:
├── "Contextual Bandits for Online Advertising"
├── "Reinforcement Learning for Bidding in Display Advertising"
└── "Budget Pacing in Online Advertising Auctions"

开源实现:
├── Google Optimize (AB 测试)
├── TensorFlow Agents (强化学习)
└── Gonum (数值计算)

最佳实践:
├── Google Ads 自动出价
├── Facebook Automation Rules
└── Programmatic Bidding
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
