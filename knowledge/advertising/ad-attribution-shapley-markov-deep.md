# 广告归因深度：MTA/TTA/Shapley Value/马尔可夫链

> 从 Last Click 到 Shapley Value，逐层解析多触点归因算法

---

## 第一部分：归因模型演进

### 归因模型发展史

```
归因模型演进：
1. Last Click (1990s) → 简单粗暴，忽略其他触点
2. First Click (2000s) → 只看重获客渠道
3. Linear (2000s) → 均匀分配，过于简单
4. Time Decay (2010s) → 靠近转化的触点权重更高
5. Position Based (2010s) → 首尾触点权重高（40%-40%-20%）
6. MTA (Marketing Mix Attribution) (2015+) → 基于数据的多触点归因
7. Shapley Value (2018+) → 博弈论最优解
8. Markov Chain (2020+) → 基于转化路径的归因
9. ML-based (2022+) → 深度学习归因（CNN/RNN/Transformer）
```

### 归因的核心问题

```
归因挑战：
1. 触点重叠：用户可能通过多个渠道接触广告
2. 时序依赖：触点的顺序影响转化概率
3. 跨设备：用户在手机/平板/PC 间切换
4. 跨渠道：搜索/展示/社交/邮件等多渠道协同
5. 延迟效应：点击广告后可能几天后才转化
6. 反事实推断：如果移除某个触点，转化概率会怎样？
```

---

## 第二部分：MTA（多触点归因）

### MTA 数据模型

```
转化路径（Conversion Path）：
┌─────────────────────────────────────────────────────────────┐
│ User: user_123                                               │
│                                                              │
│ Timeline:                                                    │
│ Day 1:  Display Ad (Facebook) → No Click                    │
│ Day 3:  Search Ad (Google) → Click                          │
│ Day 5:  Email Newsletter → Click                            │
│ Day 7:  Display Ad (YouTube) → Click                        │
│ Day 10: Organic Search → Conversion                         │
│                                                              │
│ Touchpoints: [FB_Display, Google_Search, Email, YouTube_Display] │
│ Conversion: YES (Day 10)                                    │
│                                                              │
│ 归因问题：哪个触点贡献最大？                                  │
└─────────────────────────────────────────────────────────────┘
```

### 各种 MTA 模型实现

```go
package attribution

import (
	"math"
	"sort"
)

// Touchpoint 触点
type Touchpoint struct {
	Channel string  // Facebook, Google, Email, ...
	Timestamp float64 // 时间戳
}

// ConversionPath 转化路径
type ConversionPath struct {
	UserID       string
	Touchpoints  []Touchpoint
	Converted    bool
	ConversionTS float64
}

// LastClick 最后一次点击归因
func LastClick(paths []ConversionPath) map[string]float64 {
	scores := make(map[string]float64)
	totalPaths := len(paths)
	
	for _, path := range paths {
		if !path.Converted {
			continue
		}
		
		// 找到最后一个点击的触点
		lastTP := path.Touchpoints[len(path.Touchpoints)-1]
		scores[lastTP.Channel] += 1.0 / float64(totalPaths)
	}
	
	return scores
}

// FirstClick 第一次点击归因
func FirstClick(paths []ConversionPath) map[string]float64 {
	scores := make(map[string]float64)
	totalPaths := len(paths)
	
	for _, path := range paths {
		if !path.Converted || len(path.Touchpoints) == 0 {
			continue
		}
		
		firstTP := path.Touchpoints[0]
		scores[firstTP.Channel] += 1.0 / float64(totalPaths)
	}
	
	return scores
}

// Linear 线性归因
func Linear(paths []ConversionPath) map[string]float64 {
	scores := make(map[string]float64)
	totalPaths := len(paths)
	
	for _, path := range paths {
		if !path.Converted || len(path.Touchpoints) == 0 {
			continue
		}
		
		contribution := 1.0 / float64(len(path.Touchpoints))
		for _, tp := range path.Touchpoints {
			scores[tp.Channel] += contribution / float64(totalPaths)
		}
	}
	
	return scores
}

// TimeDecay 时间衰减归因
func TimeDecay(paths []ConversionPath, halfLife float64) map[string]float64 {
	scores := make(map[string]float64)
	totalPaths := len(paths)
	
	for _, path := range paths {
		if !path.Converted || len(path.Touchpoints) == 0 {
			continue
		}
		
		// 计算每个触点的衰减权重
		var totalWeight float64
		weights := make([]float64, len(path.Touchpoints))
		
		for i, tp := range path.Touchpoints {
			timeDiff := path.ConversionTS - tp.Timestamp
			weight := math.Pow(0.5, timeDiff/halfLife)
			weights[i] = weight
			totalWeight += weight
		}
		
		// 归一化并累加
		for i, tp := range path.Touchpoints {
			normWeight := weights[i] / totalWeight
			scores[tp.Channel] += normWeight / float64(totalPaths)
		}
	}
	
	return scores
}

// PositionBased 位置归因
func PositionBased(paths []ConversionPath) map[string]float64 {
	scores := make(map[string]float64)
	totalPaths := len(paths)
	
	for _, path := range paths {
		if !path.Converted || len(path.Touchpoints) == 0 {
			continue
		}
		
		n := len(path.Touchpoints)
		if n == 1 {
			scores[path.Touchpoints[0].Channel] += 1.0 / float64(totalPaths)
			continue
		}
		
		// 首触点 40%，末触点 40%，中间均匀分配 20%
		first := path.Touchpoints[0]
		last := path.Touchpoints[n-1]
		middleCount := n - 2
		
		scores[first.Channel] += 0.4 / float64(totalPaths)
		scores[last.Channel] += 0.4 / float64(totalPaths)
		
		if middleCount > 0 {
			middleContribution := 0.2 / float64(middleCount)
			for _, tp := range path.Touchpoints[1:n-1] {
				scores[tp.Channel] += middleContribution / float64(totalPaths)
			}
		}
	}
	
	return scores
}
```

---

## 第三部分：Shapley Value 归因

### 为什么 Shapley Value 是最优的？

```
Shapley Value 满足四个公理：
1. 有效性 (Efficiency): 所有触点的归因总和 = 1
2. 对称性 (Symmetry): 贡献相同的触点获得相同归因
3. 哑元 (Dummy): 不影响转化的触点归因 = 0
4. 可加性 (Additivity): 多个游戏的 Shapley Value 之和 = 联合 Shapley Value

这些公理保证了 Shapley Value 是唯一满足所有公平性条件的归因方法。
```

### Shapley Value 计算

```
Shapley Value 公式：
φ_i(v) = Σ_{S ⊆ N\{i}} [|S|!(n-|S|-1)! / n!] × [v(S∪{i}) - v(S)]

其中：
- N: 所有触点集合
- S: 不包含触点 i 的子集
- v(S): 触点集合 S 的转化率（特征函数）
- φ_i(v): 触点 i 的 Shapley Value

计算步骤：
1. 枚举所有可能的触点子集（2^n - 2 个，排除空集和全集）
2. 对每个子集 S，计算 v(S∪{i}) - v(S)（边际贡献）
3. 加权平均所有子集的边际贡献

示例：3 个触点 A, B, C
- 子集数量：2^3 - 2 = 6 个
- 对触点 A：
  - S={} → v({A}) - v({}) = 0.1 - 0 = 0.1
  - S={B} → v({A,B}) - v({B}) = 0.15 - 0.05 = 0.1
  - S={C} → v({A,C}) - v({C}) = 0.12 - 0.03 = 0.09
  - S={B,C} → v({A,B,C}) - v({B,C}) = 0.2 - 0.08 = 0.12
  - φ_A = (2×0.1 + 1×0.1 + 1×0.09 + 2×0.12) / 6 = 0.105
```

### Shapley Value 实现

```go
// ShapleyValue 计算 Shapley Value
func ShapleyValue(characteristicFunc func([]string) float64, channels []string) map[string]float64 {
	n := len(channels)
	shapleyValues := make(map[string]float64)
	
	// 枚举所有子集
	for i := 0; i < (1 << n); i++ {
		subset := []string{}
		for j := 0; j < n; j++ {
			if i&(1<<j) != 0 {
				subset = append(subset, channels[j])
			}
		}
		
		if len(subset) == 0 || len(subset) == n {
			continue
		}
		
		// 计算每个 channel 在该子集中的 Shapley 贡献
		for _, channel := range subset {
			// 移除 channel 后的子集
			withoutChannel := []string{}
			for _, c := range subset {
				if c != channel {
					withoutChannel = append(withoutChannel, c)
				}
			}
			
			// 边际贡献
			vWith := characteristicFunc(subset)
			vWithout := characteristicFunc(withoutChannel)
			marginalContribution := vWith - vWithout
			
			// 权重：|S|!(n-|S|-1)! / n!
			weight := factorial(float64(len(subset)-1)) * 
			          factorial(float64(n-len(subset))) / 
			          factorial(float64(n))
			
			shapleyValues[channel] += weight * marginalContribution
		}
	}
	
	// 归一化
	total := 0.0
	for _, v := range shapleyValues {
		total += v
	}
	
	if total > 0 {
		for k := range shapleyValues {
			shapleyValues[k] /= total
		}
	}
	
	return shapleyValues
}

func factorial(n float64) float64 {
	result := 1.0
	for i := 2.0; i <= n; i++ {
		result *= i
	}
	return result
}
```

### 蒙特卡洛近似 Shapley Value

```
精确计算 Shapley Value 的复杂度：O(2^n)
当触点数量 > 20 时，2^20 = 1M 次计算，不可接受

解决方案：蒙特卡洛采样近似
1. 随机采样 M 个子集（M << 2^n）
2. 计算采样子集的边际贡献
3. 加权平均得到近似 Shapley Value

复杂度：O(M × n)，M 通常为 1000-10000
```

```go
// MonteCarloShapley 蒙特卡洛近似 Shapley Value
func MonteCarloShapley(characteristicFunc func([]string) float64, 
                       channels []string, iterations int) map[string]float64 {
	n := len(channels)
	shapleyValues := make(map[string]float64)
	
	for iter := 0; iter < iterations; iter++ {
		// 随机排列
		permuted := shuffle(channels)
		
		// 按排列顺序计算边际贡献
		subset := []string{}
		for _, channel := range permuted {
			vBefore := characteristicFunc(subset)
			subset = append(subset, channel)
			vAfter := characteristicFunc(subset)
			
			marginal := vAfter - vBefore
			shapleyValues[channel] += marginal
		}
	}
	
	// 平均
	for k := range shapleyValues {
		shapleyValues[k] /= float64(iterations)
	}
	
	// 归一化
	total := 0.0
	for _, v := range shapleyValues {
		total += v
	}
	
	if total > 0 {
		for k := range shapleyValues {
			shapleyValues[k] /= total
		}
	}
	
	return shapleyValues
}
```

---

## 第四部分：马尔可夫链归因

### 马尔可夫链归因原理

```
马尔可夫链归因：
1. 将转化路径建模为马尔可夫链
2. 计算每个触点的转移概率
3. 移除某个触点后，计算转化率变化
4. 转化率变化 = 该触点的归因值

优势：
- 不需要枚举所有子集（O(2^n) → O(n²)）
- 考虑触点间的顺序依赖
- 可以处理大规模触点
```

### 实现

```go
// MarkovAttribution 马尔可夫链归因
func MarkovAttribution(paths []ConversionPath) map[string]float64 {
	// 1. 构建转移矩阵
	transitions := buildTransitionMatrix(paths)
	
	// 2. 计算基础转化率
	baseConversion := calculateConversionRate(paths)
	
	// 3. 对每个触点，计算移除后的转化率
	scores := make(map[string]float64)
	channels := getUniqueChannels(paths)
	
	for _, channel := range channels {
		// 移除该触点
		modifiedPaths := removeChannel(paths, channel)
		removedConversion := calculateConversionRate(modifiedPaths)
		
		// 归因值 = 基础转化率 - 移除后转化率
		scores[channel] = baseConversion - removedConversion
	}
	
	// 4. 归一化
	normalize(scores)
	
	return scores
}

// buildTransitionMatrix 构建转移矩阵
func buildTransitionMatrix(paths []ConversionPath) [][]float64 {
	channels := getUniqueChannels(paths)
	channelIndex := make(map[string]int)
	for i, ch := range channels {
		channelIndex[ch] = i
	}
	
	n := len(channels)
	matrix := make([][]float64, n)
	
	// 统计转移次数
	transitions := make(map[string]int)
	for _, path := range paths {
		for i := 0; i < len(path.Touchpoints)-1; i++ {
			from := path.Touchpoints[i].Channel
			to := path.Touchpoints[i+1].Channel
			key := from + "->" + to
			transitions[key]++
		}
	}
	
	// 计算转移概率
	for i := 0; i < n; i++ {
		matrix[i] = make([]float64, n)
		totalFrom := 0
		
		// 统计从 channel[i] 出发的总次数
		for key, count := range transitions {
			if strings.HasPrefix(key, channels[i]+"->") {
				totalFrom += count
			}
		}
		
		// 计算概率
		for j := 0; j < n; j++ {
			key := channels[i] + "->" + channels[j]
			if count, ok := transitions[key]; ok {
				matrix[i][j] = float64(count) / float64(totalFrom)
			}
		}
	}
	
	return matrix
}
```

---

## 第五部分：自测题

### Q1: Shapley Value 和马尔可夫链归因的区别？

**A**:
- **Shapley Value**: 精确计算，考虑所有子集，复杂度 O(2^n)，需要蒙特卡洛近似
- **马尔可夫链**: 近似计算，考虑转移概率，复杂度 O(n²)，更适合大规模触点
- 生产环境推荐：马尔可夫链（性能好）+ Shapley Value（验证基准）

### Q2: 归因模型如何选择？

**A**:
- 简单场景：Last Click（快速上线）
- 中等场景：Time Decay / Position Based（平衡精度和复杂度）
- 高精度场景：Shapley Value / 马尔可夫链
- 推荐：先用 Last Click 快速验证，再逐步升级到 Shapley Value

### Q3: 归因数据需要保留多久？

**A**:
- 转化窗口：点击后 30 天，曝光后 7 天（行业标准）
- 数据保留：至少 90 天（覆盖长转化路径）
- 历史数据：用于训练模型，建议保留 1 年+

---

## 第六部分：生产实践

### 1. 归因数据管道

```
归因数据流：
1. 触点事件 → Kafka
2. Flink 实时聚合 → Redis（短期路径）
3. 离线批处理 → ClickHouse（长期路径）
4. 归因计算 → Spark/Shapley
5. 结果 → MySQL/ClickHouse
6. 查询 → API → Dashboard
```

### 2. 归因 Dashboard

```
关键指标：
1. 各渠道归因值（Shapley/马尔可夫）
2. 渠道协同效应（Channel Synergy）
3. 归因窗口敏感性（不同窗口的归因变化）
4. 跨设备归因（Device Graph）
5. 归因模型对比（Last Click vs Shapley vs 马尔可夫）
```

### 3. 归因优化建议

```
基于归因结果的优化：
1. 高归因值渠道 → 增加预算
2. 低归因值但高转化渠道 → 优化创意
3. 渠道协同 → 制定组合策略
4. 触点顺序 → 优化用户旅程
```
