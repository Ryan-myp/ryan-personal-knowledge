# 跨渠道预算分配深度：Performance Max 级 AI 自动分配

> 一个目标 CPA，AI 自动在搜索/YouTube/Display/Gmail 分配预算

---

## 第一部分：为什么需要跨渠道预算分配？

### 传统做法

```
传统预算分配：
1. 广告主手动设置各渠道预算
2. 每天看数据，手动调整
3. 渠道之间数据隔离，无法统一优化
4. 一个转化可能经过多个渠道，无法归因

问题：
- 搜索渠道 ROI 5.0，但预算已用完
- Display 渠道 ROI 1.0，但预算还有剩余
- 广告主不知道该怎么分配
```

### AI 自动分配

```
Performance Max 的做法：
1. 广告主只设一个目标 CPA
2. AI 自动在搜索/YouTube/Display/Gmail 分配预算
3. 实时调整各渠道投入
4. 跨渠道归因，全局最优
```

---

## 第二部分：跨渠道预算分配架构

### 2.1 渠道矩阵

```
渠道类型：
├── 搜索广告 (Search)
├── 展示广告 (Display)
├── YouTube 视频 (Video)
├── Gmail 广告 (Gmail)
├── Maps 广告 (Maps)
├── App 安装 (App)
└── 发现页 (Discover)

信号维度：
├── 用户意图强度
├── 渠道转化概率
├── 渠道竞争程度
├── 渠道成本
└── 渠道容量
```

### 2.2 优化目标

```
目标函数：
最大化 Total Conversions = Σ (Channel_i_Budget × Channel_i_CVR × Channel_i_ROI)

约束条件：
1. Total Budget ≤ 总预算
2. 每个渠道有最低/最高预算
3. CPA ≤ 目标 CPA
4. ROAS ≥ 目标 ROAS
```

---

## 第三部分：核心算法

### 3.1 边际收益分配

```go
// MarginalAllocation 边际收益分配算法
// 核心思想：每次把预算分配给边际收益最大的渠道

type ChannelBudget struct {
    ChannelID    string
    Budget       float64
    Impressions  int64
    Clicks       int64
    Conversions  int64
    CPA          float64
    ROI          float64
    PredictedCVR float64 // 预测转化率
}

// Allocate 分配预算
func (a *Allocator) Allocate(totalBudget float64, channels []*ChannelBudget) error {
    // 1. 初始化：每个渠道分配 10%
    for _, ch := range channels {
        ch.Budget = totalBudget * 0.1
    }
    
    // 2. 迭代分配（每次分配 1% 的预算）
    iterations := 100
    for i := 0; i < iterations; i++ {
        // 计算每个渠道的边际收益
        marginalReturns := make(map[string]float64)
        for _, ch := range channels {
            mr := a.calculateMarginalReturn(ch)
            marginalReturns[ch.ChannelID] = mr
        }
        
        // 找到边际收益最大的渠道
        bestChannel := ""
        bestMR := 0.0
        for id, mr := range marginalReturns {
            if mr > bestMR {
                bestMR = mr
                bestChannel = id
            }
        }
        
        // 分配 1% 预算给最佳渠道
        for _, ch := range channels {
            if ch.ChannelID == bestChannel {
                ch.Budget += totalBudget * 0.01
            }
        }
    }
    
    return nil
}

// calculateMarginalReturn 计算边际收益
func (a *Allocator) calculateMarginalReturn(ch *ChannelBudget) float64 {
    // 边际收益 = 新增预算带来的预期转化数
    // = 预算 × 预测CVR × 预测ROI
    return ch.Budget * ch.PredictedCVR * ch.ROI
}
```

### 3.2 预测模型

```go
// PredictionModel 预测模型
type PredictionModel struct {
    // 用户意图模型
    intentModel IntentModel
    
    // 渠道转化模型
    cvrModel CVRModel
    
    // 成本模型
    costModel CostModel
}

// PredictChannelPerformance 预测渠道表现
func (m *PredictionModel) PredictChannelPerformance(userIntent UserIntent, channel string) *Prediction {
    // 1. 预测用户在该渠道的转化概率
    cvr := m.cvrModel.PredictCVR(userIntent, channel)
    
    // 2. 预测该渠道的成本
    cpc := m.costModel.PredictCPC(channel, userIntent.Competition)
    
    // 3. 预测 ROI
    roi := cvr * (1.0 / cpc)
    
    // 4. 综合评分
    score := cvr * roi * userIntent.Intensity
    
    return &Prediction{
        CVR:     cvr,
        CPC:     cpc,
        ROI:     roi,
        Score:   score,
        Channel: channel,
    }
}
```

---

## 第四部分：实时调整

### 4.1 动态预算分配

```go
type RealtimeAllocator struct {
    channels map[string]*ChannelBudget
    model    *PredictionModel
    window   time.Duration // 调整窗口
}

// Adjust 实时调整预算
func (a *RealtimeAllocator) Adjust() error {
    // 1. 获取最近 window 时间的数据
    recentData := a.getRecentData(a.window)
    
    // 2. 更新渠道表现
    for channelID, data := range recentData {
        ch := a.channels[channelID]
        ch.Impressions = data.Impressions
        ch.Clicks = data.Clicks
        ch.Conversions = data.Conversions
        ch.CPA = data.Spend / float64(data.Conversions)
        ch.ROI = data.Revenue / data.Spend
    }
    
    // 3. 重新分配预算
    totalBudget := a.getTotalBudget()
    a.Allocator.Allocate(totalBudget, a.channels)
    
    return nil
}
```

### 4.2 约束处理

```go
// ApplyConstraints 应用约束
func (a *RealtimeAllocator) ApplyConstraints() {
    for _, ch := range a.channels {
        // 最低预算约束
        if ch.Budget < a.minBudget {
            ch.Budget = a.minBudget
        }
        
        // 最高预算约束
        if ch.Budget > a.maxBudget {
            ch.Budget = a.maxBudget
        }
        
        // CPA 约束
        if ch.CPA > a.targetCPA * 1.5 {
            ch.Budget *= 0.8 // 减少预算
        }
        
        // ROAS 约束
        if ch.ROI < a.targetROAS * 0.5 {
            ch.Budget *= 0.5 // 大幅减少预算
        }
    }
    
    // 重新归一化，确保总预算不变
    a.normalizeBudgets()
}
```

---

## 第五部分：生产实战

### 5.1 效果数据

```
| 指标 | 手动分配 | AI 自动分配 | 提升 |
|------|---------|------------|------|
| 总转化数 | 1000 | 1350 | +35% |
| 平均 CPA | ¥25 | ¥18 | -28% |
| 平均 ROAS | 3.2 | 4.5 | +41% |
| 预算利用率 | 75% | 98% | +31% |
```

### 5.2 实际场景

```
场景：电商广告主，日预算 10 万，目标 CPA ¥50

AI 分配结果：
┌──────────┬────────┬────────┬──────────┐
│ 渠道     │ 预算   │ CPA    │ 转化率   │
├──────────┼────────┼────────┼──────────┤
│ 搜索     │ 40000  │ ¥45    │ 8.5%     │
│ Display  │ 20000  │ ¥55    │ 5.2%     │
│ YouTube  │ 25000  │ ¥48    │ 6.8%     │
│ Gmail    │ 10000  │ ¥60    │ 3.5%     │
│ Maps     │ 5000   │ ¥40    │ 9.2%     │
└──────────┴────────┴────────┴──────────┘

每小时自动调整一次，根据实时数据优化分配
```

---

## 第六部分：自测题

### 问题 1
边际收益分配算法的核心思想是什么？

<details>
<summary>查看答案</summary>

边际收益分配算法的核心思想：

1. **每次把预算分配给边际收益最大的渠道**
2. 边际收益 = 新增预算带来的预期转化数
3. 初始时每个渠道分配相同预算
4. 迭代分配：每次分配 1% 预算给边际收益最大的渠道
5. 最终达到全局最优分配
</details>

### 问题 2
跨渠道预算分配需要处理哪些约束？

<details>
<summary>查看答案</summary>

需要处理的约束：

1. **总预算约束**：所有渠道预算之和 = 总预算
2. **最低预算约束**：每个渠道有最低预算
3. **最高预算约束**：每个渠道有最高预算
4. **CPA 约束**：渠道 CPA 不能超过目标的 1.5 倍
5. **ROAS 约束**：渠道 ROAS 不能低于目标的 50%
6. **容量约束**：每个渠道有最大展示容量
</details>

---

*本文档基于跨渠道预算分配生产实战整理。*