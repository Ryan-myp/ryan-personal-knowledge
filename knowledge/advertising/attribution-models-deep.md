# 广告归因深度：最后点击/线性/时间衰减/马尔可夫链

> 归因模型对比/多触点归因/Shapley Value/增量测试/MMM

---

## 第一部分：入门引导（5 分钟速览）

### 为什么归因很重要？

广告主需要知道：
- **哪个渠道带来了转化？**
- **预算应该分配给谁？**
- **ROI 是多少？**

```
用户旅程：
展示 Banner → 点击搜索广告 → 点击社交广告 → 转化

归因问题：转化应该归功于哪个渠道？
```

---

## 第二部分：归因模型

### 2.1 常见归因模型

| 模型 | 规则 | 适用场景 | 优点 | 缺点 |
|------|------|---------|------|------|
| **Last Click** | 100% 给最后一次点击 | 简单场景 | 简单直观 | 忽略前面触点 |
| **First Click** | 100% 给第一次点击 | 拉新场景 | 重视获客 | 忽略后续转化 |
| **Linear** | 平均分配 | 均衡重视 | 公平 | 不考虑重要性 |
| **Time Decay** | 越近越重要 | 短期转化 | 重视近期 | 参数主观 |
| **Position-Based** | 首尾各 40%，中间平分 | 兼顾拉新和转化 | 平衡 | 参数主观 |
| **Data-Driven** | 基于数据计算 | 有足够数据 | 准确 | 需要大量数据 |

### 2.2 Go 实现归因模型

```go
package attribution

import (
    "math"
)

// Touchpoint 用户触点
type Touchpoint struct {
    Channel   string
    Timestamp time.Time
    Cost      float64
}

// AttributionModel 归因模型接口
type AttributionModel interface {
    Name() string
    Calculate(touchpoints []Touchpoint, conversion float64) map[string]float64
}

// LastClickAttribution 最后点击归因
type LastClickAttribution struct{}

func (a *LastClickAttribution) Name() string {
    return "last_click"
}

func (a *LastClickAttribution) Calculate(touchpoints []Touchpoint, conversion float64) map[string]float64 {
    result := make(map[string]float64)
    
    if len(touchpoints) == 0 {
        return result
    }
    
    // 找到最后一次点击
    last := touchpoints[len(touchpoints)-1]
    result[last.Channel] = conversion
    
    return result
}

// LinearAttribution 线性归因
type LinearAttribution struct{}

func (a *LinearAttribution) Name() string {
    return "linear"
}

func (a *LinearAttribution) Calculate(touchpoints []Touchpoint, conversion float64) map[string]float64 {
    result := make(map[string]float64)
    
    if len(touchpoints) == 0 {
        return result
    }
    
    // 平均分配
    share := conversion / float64(len(touchpoints))
    for _, tp := range touchpoints {
        result[tp.Channel] += share
    }
    
    return result
}

// TimeDecayAttribution 时间衰减归因
type TimeDecayAttribution struct {
    HalfLife time.Duration // 半衰期
}

func (a *TimeDecayAttribution) Name() string {
    return "time_decay"
}

func (a *TimeDecayAttribution) Calculate(touchpoints []Touchpoint, conversion float64) map[string]float64 {
    result := make(map[string]float64)
    totalWeight := 0.0
    
    // 计算每个触点的权重
    weights := make([]float64, len(touchpoints))
    for i, tp := range touchpoints {
        timeDiff := conversionTime.Sub(tp.Timestamp)
        // 指数衰减：weight = 0.5^(timeDiff/halfLife)
        weight := math.Pow(0.5, timeDiff.Hours()/a.HalfLife.Hours())
        weights[i] = weight
        totalWeight += weight
    }
    
    // 归一化并分配
    for i, tp := range touchpoints {
        result[tp.Channel] = conversion * (weights[i] / totalWeight)
    }
    
    return result
}

// PositionBasedAttribution 位置归因
type PositionBasedAttribution struct {
    FirstWeight float64 // 首次触点权重
    LastWeight  float64 // 最后触点权重
}

func (a *PositionBasedAttribution) Name() string {
    return "position_based"
}

func (a *PositionBasedAttribution) Calculate(touchpoints []Touchpoint, conversion float64) map[string]float64 {
    result := make(map[string]float64)
    
    if len(touchpoints) == 0 {
        return result
    }
    
    firstWeight := a.FirstWeight * conversion
    lastWeight := a.LastWeight * conversion
    middleWeight := (1 - a.FirstWeight - a.LastWeight) * conversion
    
    // 首次和最后
    result[touchpoints[0].Channel] += firstWeight
    result[touchpoints[len(touchpoints)-1].Channel] += lastWeight
    
    // 中间平均分配
    if len(touchpoints) > 2 {
        middleShare := middleWeight / float64(len(touchpoints)-2)
        for _, tp := range touchpoints[1:len(touchpoints)-1] {
            result[tp.Channel] += middleShare
        }
    }
    
    return result
}
```

---

## 第三部分：马尔可夫链归因

### 3.1 马尔可夫链原理

```
状态转移矩阵：
从 Channel A 转移到 Channel B 的概率

移除某个 Channel 后，转化率的变化 = 该 Channel 的价值
```

### 3.2 Go 实现

```go
type MarkovAttribution struct {
    transitionMatrix map[string]map[string]float64 // 状态转移矩阵
    conversionRate   map[string]float64             // 转化率
}

func (m *MarkovAttribution) Calculate(touchpaths [][]Touchpoint) map[string]float64 {
    // 1. 构建状态转移矩阵
    m.buildTransitionMatrix(touchpaths)
    
    // 2. 计算原始转化率
    originalConversion := m.calculateConversionRate()
    
    // 3. 逐个移除 Channel，计算影响
    channelValue := make(map[string]float64)
    channels := m.getChannelList(touchpaths)
    
    for _, channel := range channels {
        // 移除该 Channel
        modifiedMatrix := m.removeChannel(channel)
        
        // 计算新转化率
        modifiedConversion := m.calculateConversionRateWithMatrix(modifiedMatrix)
        
        // 价值 = 原始转化率 - 新转化率
        channelValue[channel] = originalConversion - modifiedConversion
    }
    
    // 4. 归一化
    totalValue := 0.0
    for _, v := range channelValue {
        totalValue += v
    }
    
    for k, v := range channelValue {
        channelValue[k] = v / totalValue
    }
    
    return channelValue
}

func (m *MarkovAttribution) buildTransitionMatrix(touchpaths [][]Touchpoint) {
    matrix := make(map[string]map[string]float64)
    
    for _, path := range touchpaths {
        for i := 0; i < len(path)-1; i++ {
            from := path[i].Channel
            to := path[i+1].Channel
            
            if _, ok := matrix[from]; !ok {
                matrix[from] = make(map[string]float64)
            }
            
            matrix[from][to]++
        }
    }
    
    // 归一化
    for from, transitions := range matrix {
        total := 0.0
        for _, count := range transitions {
            total += count
        }
        
        for to := range transitions {
            transitions[to] /= total
        }
        
        matrix[from] = transitions
    }
    
    m.transitionMatrix = matrix
}
```

---

## 第四部分：增量测试与 MMM

### 4.1 增量测试

```go
type IncrementalityTest struct {
    treatmentGroup []string // 实验组
    controlGroup   []string // 对照组
}

func (t *IncrementalityTest) CalculateLift() float64 {
    // 实验组转化率
    treatmentConversion := t.calculateConversion(t.treatmentGroup)
    
    // 对照组转化率
    controlConversion := t.calculateConversion(t.controlGroup)
    
    // 提升幅度
    lift := (treatmentConversion - controlConversion) / controlConversion
    
    return lift
}

func (t *IncrementalityTest) calculateConversion(users []string) float64 {
    conversions := 0
    for _, userID := range users {
        if t.hasConversion(userID) {
            conversions++
        }
    }
    
    return float64(conversions) / float64(len(users))
}
```

### 4.2 营销组合建模 (MMM)

```go
type MMMModel struct {
    // 广告支出
    adSpend []float64
    // 媒体渠道
    channels []string
    // 转化率
    conversions []float64
    // 季节性因素
    seasonality []float64
}

func (m *MMMModel) Fit() map[string]float64 {
    // 多元回归：conversions = β0 + β1*adSpend1 + β2*adSpend2 + ... + ε
    
    // 1. 构建特征矩阵
    X := m.buildFeatureMatrix()
    
    // 2. 构建目标向量
    y := m.conversions
    
    // 3. OLS 估计
    betas := m.estimateBetas(X, y)
    
    // 4. 计算 ROI
    roi := make(map[string]float64)
    for i, channel := range m.channels {
        roi[channel] = betas[i+1] / m.adSpend[i]
    }
    
    return roi
}
```

---

## 第五部分：自测题

### 问题 1
为什么需要多触点归因？

<details>
<summary>查看答案</summary>

1. **用户旅程复杂**：多次接触才能转化
2. **Last Click 偏差**：忽略前面触点
3. **公平分配**：每个渠道获得合理 credit
4. **预算优化**：知道哪些渠道真正有效
5. **Go 实现**：Linear/TimeDecay/PositionBased

</details>

### 问题 2
马尔可夫链归因相比规则归因有什么优势？

<details>
<summary>查看答案</summary>

1. **数据驱动**：基于实际转化路径
2. **考虑顺序**：触点顺序影响转化
3. **移除效应**：计算 Channel 的真实价值
4. **无参数**：不需要手动设置权重
5. **缺点**：需要大量数据

</details>

### 问题 3
MMM 相比 GA 有什么优势？

<details>
<summary>查看答案</summary>

1. **隐私合规**：不需要用户级数据
2. **长期效果**：可以建模品牌效应
3. **全渠道**：包括线下渠道
4. **预算优化**：直接给出 ROI
5. **Go 实现**：多元回归

</details>

---

*本文档基于广告归因原理整理。*