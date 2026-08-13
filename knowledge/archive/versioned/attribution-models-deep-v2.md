# 广告归因深度：从最后点击到马尔可夫链

> 逐行解析归因模型 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解归因

```
用户旅程：
早上 8 点：看到 Banner 广告 → 没点击
上午 10 点：搜索"运动鞋" → 点击搜索广告
下午 2 点：刷朋友圈 → 看到社交广告 → 点击
晚上 8 点：收到邮件 → 点击邮件链接 → 下单购买

问题：这个订单应该归功于哪个渠道？
- Banner？它带来了第一次曝光
- 搜索？它带来了第一次点击
- 社交？它带来了最后一次点击
- 邮件？它促成了最终转化
```

### 为什么归因很重要？

```
错误归因的后果：
- 把功劳给错了渠道 → 预算分配错误
- 砍掉真正有效的渠道 → 转化率下降
- 重复投资低效渠道 → ROI 降低

正确归因的价值：
- 知道哪个渠道真正带来转化
- 优化预算分配
- 提高整体 ROI
```

---

## 第二部分：归因模型深度

### 2.1 常见归因模型对比

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
    "time"
)

// Touchpoint 用户触点
type Touchpoint struct {
    Channel   string    // 渠道：banner, search, social, email
    Timestamp time.Time // 时间戳
    Cost      float64   // 花费
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
    HalfLife time.Duration // 半衰期，默认 1 小时
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
    FirstWeight float64 // 首次触点权重，默认 0.4
    LastWeight  float64 // 最后触点权重，默认 0.4
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

### 2.3 归因模型选择指南

```
如何选择归因模型？

1. 数据量 < 1000 转化 → Last Click（简单）
2. 数据量 1000-10000 → Linear/Time Decay（平衡）
3. 数据量 > 10000 → Data-Driven（准确）

推荐：
- 初期：Last Click
- 中期：Time Decay 或 Position Based
- 成熟期：Data-Driven（马尔可夫链/Shapley Value）
```

---

## 第三部分：马尔可夫链归因

### 3.1 马尔可夫链原理

```
马尔可夫链的核心思想：
移除某个渠道后，转化率的变化 = 该渠道的价值

步骤：
1. 构建状态转移矩阵
2. 计算原始转化率
3. 逐个移除渠道，计算新转化率
4. 价值 = 原始转化率 - 新转化率
```

### 3.2 Go 实现马尔可夫链

```go
package markov

import (
    "fmt"
    "math"
)

// MarkovAttribution 马尔可夫归因
type MarkovAttribution struct {
    transitionMatrix map[string]map[string]float64
    conversionRate   float64
}

// Calculate 计算渠道价值
func (m *MarkovAttribution) Calculate(touchpaths [][]Touchpoint) map[string]float64 {
    // 1. 构建状态转移矩阵
    m.buildTransitionMatrix(touchpaths)
    
    // 2. 计算原始转化率
    m.conversionRate = m.calculateConversionRate()
    
    // 3. 逐个移除渠道，计算影响
    channelValue := make(map[string]float64)
    channels := m.getChannelList(touchpaths)
    
    for _, channel := range channels {
        // 移除该渠道
        modifiedMatrix := m.removeChannel(channel)
        
        // 计算新转化率
        modifiedConversion := m.calculateConversionRateWithMatrix(modifiedMatrix)
        
        // 价值 = 原始转化率 - 新转化率
        channelValue[channel] = m.conversionRate - modifiedConversion
    }
    
    // 4. 归一化
    totalValue := 0.0
    for _, v := range channelValue {
        totalValue += v
    }
    
    for k, v := range channelValue {
        if totalValue > 0 {
            channelValue[k] = v / totalValue
        }
    }
    
    return channelValue
}

// buildTransitionMatrix 构建状态转移矩阵
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

// calculateConversionRate 计算转化率
func (m *MarkovAttribution) calculateConversionRate() float64 {
    // 简化的转化率计算
    // 实际实现需要更复杂的算法
    return 0.05 // 5%
}

// removeChannel 移除渠道
func (m *MarkovAttribution) removeChannel(channel string) map[string]map[string]float64 {
    modified := make(map[string]map[string]float64)
    
    for from, transitions := range m.transitionMatrix {
        if from == channel {
            continue
        }
        
        modified[from] = make(map[string]float64)
        for to, count := range transitions {
            if to == channel {
                continue
            }
            modified[from][to] = count
        }
    }
    
    return modified
}

// getChannelList 获取所有渠道列表
func (m *MarkovAttribution) getChannelList(touchpaths [][]Touchpoint) []string {
    channels := make(map[string]bool)
    
    for _, path := range touchpaths {
        for _, tp := range path {
            channels[tp.Channel] = true
        }
    }
    
    result := make([]string, 0, len(channels))
    for channel := range channels {
        result = append(result, channel)
    }
    
    return result
}
```

### 3.3 Shapley Value 归因

```
Shapley Value 是博弈论中的概念，用于公平分配合作收益。

核心思想：
考虑所有可能的渠道组合，计算每个渠道的平均边际贡献

例如：
组合 {banner} → 转化率 2%
组合 {banner, search} → 转化率 5%
banner 的边际贡献 = 5% - 2% = 3%

组合 {search} → 转化率 3%
组合 {banner, search} → 转化率 5%
banner 的边际贡献 = 5% - 3% = 2%

banner 的平均边际贡献 = (3% + 2%) / 2 = 2.5%
```

---

## 第四部分：增量测试与 MMM

### 4.1 增量测试

```
增量测试（Incrementality Test）：
通过 A/B 测试来确定渠道的真实效果

实验组：看到广告的用户
对照组：没看到广告的用户

lift = (实验组转化率 - 对照组转化率) / 对照组转化率

如果 lift > 0，说明广告有效果
如果 lift ≈ 0，说明广告是自然转化
```

```go
package incrementality

import (
    "math"
)

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
    if controlConversion == 0 {
        return 0
    }
    
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

func (t *IncrementalityTest) hasConversion(userID string) bool {
    // 检查用户是否转化
    return false // 简化实现
}

// 统计显著性检验
func (t *IncrementalityTest) IsSignificant(alpha float64) bool {
    treatmentConv := t.calculateConversion(t.treatmentGroup)
    controlConv := t.calculateConversion(t.controlGroup)
    
    // 计算 Z-score
    n1 := float64(len(t.treatmentGroup))
    n2 := float64(len(t.controlGroup))
    
    p := (treatmentConv*n1 + controlConv*n2) / (n1 + n2)
    se := math.Sqrt(p*(1-p)*(1/n1 + 1/n2))
    
    if se == 0 {
        return false
    }
    
    z := (treatmentConv - controlConv) / se
    
    // 查表判断显著性
    return math.Abs(z) > 1.96 // alpha=0.05
}
```

### 4.2 营销组合建模 (MMM)

```
MMM（Marketing Mix Modeling）：
通过多元回归分析来评估各渠道的贡献

conversions = β0 + β1×adSpend1 + β2×adSpend2 + ... + ε

优点：
- 不需要用户级数据
- 可以建模长期效应
- 包括线下渠道

缺点：
- 需要大量历史数据
- 模型假设较多
```

```go
package mmm

import (
    "math"
)

type MMMModel struct {
    adSpend     []float64 // 广告支出
    channels    []string  // 媒体渠道
    conversions []float64 // 转化数
    seasonality []float64 // 季节性因素
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

func (m *MMMModel) estimateBetas(X [][]float64, y []float64) []float64 {
    // OLS: β = (X'X)^(-1) X'y
    // 简化实现
    n := len(y)
    p := len(X[0])
    
    betas := make([]float64, p)
    
    // 简化：使用梯度下降
    learningRate := 0.01
    iterations := 1000
    
    for iter := 0; iter < iterations; iter++ {
        // 计算预测值
        predictions := make([]float64, n)
        for i := 0; i < n; i++ {
            for j := 0; j < p; j++ {
                predictions[i] += betas[j] * X[i][j]
            }
        }
        
        // 计算梯度
        gradients := make([]float64, p)
        for j := 0; j < p; j++ {
            for i := 0; i < n; i++ {
                gradients[j] += (predictions[i] - y[i]) * X[i][j]
            }
            gradients[j] /= float64(n)
        }
        
        // 更新参数
        for j := 0; j < p; j++ {
            betas[j] -= learningRate * gradients[j]
        }
    }
    
    return betas
}
```

---

## 第五部分：生产排障案例

### 5.1 归因数据不准确

```
现象：归因报告显示搜索渠道贡献很大，但增量测试显示 lift≈0

排查：
1. 检查归因模型是否合理
2. 检查数据收集是否完整
3. 检查是否有 cookie 丢失

根因：Last Click 模型高估了搜索渠道

解决方案：
1. 改用 Time Decay 或 Data-Driven
2. 实施增量测试
3. 使用多触点归因
```

### 5.2 增量测试结果不显著

```
现象：A/B 测试结果显示 lift 为正，但不显著

排查：
1. 样本量是否足够
2. 实验周期是否足够长
3. 是否有外部因素干扰

解决方案：
1. 增加样本量
2. 延长实验周期
3. 控制外部变量
```

---

## 第六部分：自测题

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
增量测试如何确定显著性？

<details>
<summary>查看答案</summary>

1. **假设检验**：H0: 两组无差异
2. **P 值**：< 0.05 认为显著
3. **置信区间**：95% 置信区间
4. **样本量**：需要足够的样本
5. **Go 实现**：Z-score 检验

</details>

---

*本文档基于广告归因原理和生产实战整理。*