# 广告归因系统深度解析

> 深入广告归因核心：归因模型、多渠道归因、反作弊、数据一致性。
> 包含真实生产环境架构设计。
> 适用对象：广告系统工程师、数据分析师、后端架构师

---

## 1. 归因模型

### 1.1 归因模型类型

```
┌─────────────────────────────────────────────────────────────┐
│                    归因模型分类                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  最后点击归因 (Last Click)                                   │
│  ─────────────────────────                                  │
│  100% 功劳归因给最后一次点击                                 │
│  优点：简单、直观                                            │
│  缺点：忽略其他触点的贡献                                    │
│                                                             │
│  首次点击归因 (First Click)                                  │
│  ─────────────────────────                                  │
│  100% 功劳归因给第一次点击                                   │
│  优点：强调引流渠道                                          │
│  缺点：忽略转化渠道                                          │
│                                                             │
│  线性归因 (Linear)                                           │
│  ─────────────────────────                                  │
│  所有触点平分功劳                                            │
│  优点：公平                                                 │
│  缺点：不够精确                                              │
│                                                             │
│  时间衰减归因 (Time Decay)                                   │
│  ─────────────────────────                                  │
│  越接近转化的触点，功劳越大                                  │
│  优点：重视转化前触点                                        │
│  缺点：参数调优复杂                                          │
│                                                             │
│  位置归因 (Position-Based)                                   │
│  ─────────────────────────                                  │
│  首次和最后一次各 40%，中间平分 20%                          │
│  优点：强调首尾触点                                          │
│  缺点：忽略了中间触点                                        │
│                                                             │
│  Shapley Value 归因                                          │
│  ─────────────────────────                                  │
│  基于博弈论，考虑所有可能的组合                               │
│  优点：最公平、最准确                                        │
│  缺点：计算复杂度高                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Shapley Value 实现

```go
// shapley.go

package attribution

import (
    "math"
)

type AttributionModel struct {
    channels []string
    conversions [][]string
}

type ShapleyValue struct {
    channel string
    value   float64
}

func NewAttributionModel(channels []string, conversions [][]string) *AttributionModel {
    return &AttributionModel{
        channels:    channels,
        conversions: conversions,
    }
}

func (m *AttributionModel) CalculateShapley() []ShapleyValue {
    n := len(m.channels)
    results := make([]ShapleyValue, n)
    
    // 生成所有子集
    subsets := generateSubsets(n)
    
    for i, channel := range m.channels {
        total := 0.0
        count := 0
        
        for _, subset := range subsets {
            if !subset.Contains(i) {
                marginal := m.marginalContribution(subset, i)
                weight := m.shapleyWeight(len(subset), n)
                total += marginal * weight
                count++
            }
        }
        
        results[i] = ShapleyValue{
            channel: channel,
            value:   total / float64(count),
        }
    }
    
    return results
}

func (m *AttributionModel) marginalContribution(subset []int, channel int) float64 {
    // 计算包含和不包含该渠道的转化差异
    without := m.calculateConversions(subset)
    
    subset = append(subset, channel)
    with := m.calculateConversions(subset)
    
    return with - without
}

func (m *AttributionModel) shapleyWeight(k, n int) float64 {
    // Shapley 权重公式
    return math factorial float64(k) * math factorial float64(n-k-1) / 
           math factorial float64(n)
}

func generateSubsets(n int) [][]int {
    var subsets [][]int
    for i := 0; i < (1 << n); i++ {
        subset := []int{}
        for j := 0; j < n; j++ {
            if i&(1<<j) != 0 {
                subset = append(subset, j)
            }
        }
        subsets = append(subsets, subset)
    }
    return subsets
}
```

---

## 2. 多渠道归因

### 2.1 触点追踪

```
触点路径:

曝光 A → 点击 B → 曝光 C → 点击 D → 转化
 │        │        │        │
 ├─广告1──┤        ├─广告2──┤
 │        ├─自然搜索──┤
 │        │        ├─直接访问──┤
 └────────────────────────────┘
```

### 2.2 归因计算

```go
// multi_channel.go

package attribution

import (
    "time"
)

type Touchpoint struct {
    ID         string
    Channel    string
    Type       string  // impression, click
    Timestamp  time.Time
    Value      float64
}

type AttributionResult struct {
    Touchpoints []Touchpoint
    Model       string
    Weights     map[string]float64
    Conversion  float64
}

func (m *AttributionModel) MultiChannelAttribution(
    touchpoints []Touchpoint,
    conversionValue float64,
) *AttributionResult {
    // 1. 按时间排序
    sort.Sort(byTime(touchpoints))
    
    // 2. 选择归因模型
    var weights map[string]float64
    switch m.model {
    case "last_click":
        weights = lastClickWeights(touchpoints)
    case "time_decay":
        weights = timeDecayWeights(touchpoints)
    case "shapley":
        weights = m.calculateShapleyWeights(touchpoints)
    default:
        weights = lastClickWeights(touchpoints)
    }
    
    return &AttributionResult{
        Touchpoints: touchpoints,
        Model:       m.model,
        Weights:     weights,
        Conversion:  conversionValue,
    }
}
```

---

## 3. 反作弊

### 3.1 作弊模式

```
┌─────────────────────────────────────────────────────────────┐
│                    广告作弊模式                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 点击欺诈 (Click Fraud)                                   │
│     ├── 点击农场：批量点击虚假账号                            │
│     ├── 恶意竞争：点击对手广告消耗预算                        │
│     └── 自动化工具：脚本批量点击                              │
│                                                             │
│  2. 曝光欺诈 (Impression Fraud)                              │
│     ├── 隐形曝光：不可见的广告位                              │
│     ├── 机器人流量：非人类用户                               │
│     └── 设备农场：批量设备模拟                                │
│                                                             │
│  3. 转化欺诈 (Conversion Fraud)                              │
│     ├── 虚假转化：伪造购买/注册行为                           │
│     └── 归因劫持：窃取他人转化                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 风控规则

```go
// fraud_detection.go

package fraud

import (
    "time"
)

type FraudDetector struct {
    rules []FraudRule
}

type FraudRule interface {
    Name() string
    Check(touchpoint Touchpoint) bool
    Severity() int
}

// 规则 1：频率限制
type RateLimitRule struct {
    maxClicksPerMinute int
}

func (r *RateLimitRule) Name() string { return "rate_limit" }
func (r *RateLimitRule) Severity() int { return 3 }

func (r *RateLimitRule) Check(tp Touchpoint) bool {
    count := r.getClickCount(tp.DeviceID, time.Now().Add(-time.Minute))
    return count > r.maxClicksPerMinute
}

// 规则 2：IP 异常
type IPAnomalyRule struct {
    maxClicksPerIP int
}

func (r *IPAnomalyRule) Name() string { return "ip_anomaly" }
func (r *IPAnomalyRule) Severity() int { return 2 }

func (r *IPAnomalyRule) Check(tp Touchpoint) bool {
    count := r.getClickCountByIP(tp.IP, time.Now().Add(-time.Hour))
    return count > r.maxClicksPerIP
}

// 规则 3：设备指纹
type DeviceFingerprintRule struct{}

func (r *DeviceFingerprintRule) Name() string { return "device_fingerprint" }
func (r *DeviceFingerprintRule) Severity() int { return 4 }

func (r *DeviceFingerprintRule) Check(tp Touchpoint) bool {
    return r.isSuspiciousDevice(tp.DeviceFingerprint)
}
```

---

## 4. 数据一致性

### 4.1 最终一致性保证

```
┌─────────────────────────────────────────────────────────────┐
│                  归因数据一致性                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 数据收集阶段                                             │
│     ├── 实时采集曝光/点击事件                                │
│     └── 使用 Kafka 缓冲                                     │
│                                                             │
│  2. 数据处理阶段                                             │
│     ├── Flink 流处理计算归因                                 │
│     └── 窗口聚合，最终一致性                                 │
│                                                             │
│  3. 数据存储阶段                                             │
│     ├── ClickHouse 存储明细数据                              │
│     └── Redis 缓存聚合结果                                  │
│                                                             │
│  4. 对账阶段                                                 │
│     ├── 定时对账任务                                         │
│     └── 补偿缺失数据                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 对账机制

```go
// reconciliation.go

package attribution

import (
    "time"
)

type ReconciliationJob struct {
    startTime time.Time
    endTime   time.Time
}

func (j *ReconciliationJob) Execute() error {
    // 1. 汇总各渠道数据
    channelData := j.aggregateChannelData()
    
    // 2. 汇总归因数据
    attributionData := j.aggregateAttributionData()
    
    // 3. 差异分析
    diffs := j.compare(channelData, attributionData)
    
    // 4. 补偿处理
    for _, diff := range diffs {
        j.compensate(diff)
    }
    
    return nil
}

func (j *ReconciliationJob) compensate(diff Diff) error {
    // 补偿缺失的归因数据
    return nil
}
```

---

## 5. 性能优化

### 5.1 预计算优化

```go
// precompute.go

package attribution

import (
    "sync"
    "time"
)

type PrecomputedAttribution struct {
    mu          sync.RWMutex
    cache       map[string]*AttributionResult
    lastUpdate  time.Time
}

func NewPrecomputedAttribution() *PrecomputedAttribution {
    return &PrecomputedAttribution{
        cache: make(map[string]*AttributionResult),
    }
}

func (p *PrecomputedAttribution) Get(userID string) *AttributionResult {
    p.mu.RLock()
    result, ok := p.cache[userID]
    p.mu.RUnlock()
    
    if ok && time.Since(p.lastUpdate) < 5*time.Minute {
        return result
    }
    
    // 重新计算
    p.calculate(userID)
    return p.cache[userID]
}

func (p *PrecomputedAttribution) calculate(userID string) {
    // 执行归因计算
    result := p.computeAttribution(userID)
    
    p.mu.Lock()
    p.cache[userID] = result
    p.mu.Unlock()
}
```

---

## 6. 实战案例

### 6.1 电商归因

```
电商转化路径：

Google 广告曝光 → Google 广告点击 → 搜索品牌词 → 直接访问 → 购买

归因结果：
- Last Click: 直接访问 100%
- Time Decay: 搜索品牌词 40%, 直接访问 35%, Google 25%
- Shapley: Google 25%, 搜索品牌词 30%, 直接访问 45%
```

### 6.2 效果指标

| 指标 | 计算公式 | 目标值 |
|------|----------|--------|
| 归因准确率 | 实际转化/归因转化 | > 90% |
| 数据一致性 | 对账差异率 | < 1% |
| 处理延迟 | P99 延迟 | < 5min |
| 作弊拦截率 | 拦截数/总请求 | > 95% |

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 归因模型 | Shapley Value/时间衰减/位置归因 |
| 反作弊 | 多维度规则引擎 |
| 一致性 | 对账补偿机制 |
| 性能 | 预计算 + 缓存 |

### 7.2 最佳实践

- [ ] 选择合适的归因模型
- [ ] 建立反作弊规则
- [ ] 定期数据对账
- [ ] 预计算优化性能

---

*最后更新：2026-08-11*
*作者：Ryan*
