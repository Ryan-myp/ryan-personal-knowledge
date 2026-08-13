# 广告系统架构深度：归因建模/反作弊/流量分配

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解广告系统架构

```
广告系统 = 一个巨大的拍卖市场

参与者：
- 广告主（卖家）：想卖东西
- 用户（买家）：想买
- 平台（交易所）：撮合交易

核心流程：
1. 用户打开 App → 广告位出现
2. 多个广告主竞价 → 最高价中标
3. 广告展示 → 记录曝光/点击/转化
4. 归因分析 → 评估效果
5. 反作弊 → 防止欺诈
```

### 广告系统核心挑战

```
1. 实时性：竞价必须在 100ms 内完成
2. 高并发：峰值 QPS 100万+
3. 准确性：CTR/CVR 预估误差 < 5%
4. 安全性：防止欺诈点击
5. 公平性：合理分配流量
```

---

## 第二部分：归因建模

### 2.1 归因模型对比

| 模型 | 规则 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **Last Click** | 100% 给最后一次点击 | 简单 | 忽略前面触点 | 简单场景 |
| **First Click** | 100% 给第一次点击 | 重视获客 | 忽略后续转化 | 拉新场景 |
| **Linear** | 平均分配 | 公平 | 不考虑重要性 | 均衡重视 |
| **Time Decay** | 越近越重要 | 重视近期 | 参数主观 | 短期转化 |
| **Position-Based** | 首尾各 40% | 平衡 | 参数主观 | 兼顾拉新和转化 |
| **Data-Driven** | 基于数据计算 | 准确 | 需要大量数据 | 成熟期 |

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

### 2.3 马尔可夫链归因

```
马尔可夫链的核心思想：
移除某个渠道后，转化率的变化 = 该渠道的价值

步骤：
1. 构建状态转移矩阵
2. 计算原始转化率
3. 逐个移除渠道，计算新转化率
4. 价值 = 原始转化率 - 新转化率
```

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

---

## 第三部分：反作弊系统

### 3.1 欺诈类型

| 类型 | 说明 | 占比 | 检测难度 |
|------|------|------|---------|
| **点击欺诈** | 虚假点击消耗预算 | 15-20% | 中 |
| **刷量** | 虚假安装/注册 | 10-15% | 高 |
| **机器人流量** | 非人类用户 | 5-10% | 低 |
| **流量劫持** | 中间人攻击 | < 5% | 中 |
| **SDK 欺诈** | 伪造 SDK 报告 | 5-10% | 高 |

### 3.2 设备指纹

```go
package fingerprint

import (
    "crypto/sha256"
    "fmt"
    "hash/crc32"
    "strings"
)

type DeviceInfo struct {
    UserAgent        string
    ScreenSize       string
    Language         string
    TimeZone         string
    CanvasHash       string
    WebglHash        string
    AudioHash        string
    HardwareConcurency int
    Platform         string
    DoNotTrack       bool
    MaxTouchPoints   int
    DeviceMemory     int
}

func GenerateFingerprint(info DeviceInfo) string {
    // 1. 收集设备特征
    features := []string{
        info.UserAgent,
        info.ScreenSize,
        info.Language,
        info.TimeZone,
        info.CanvasHash,
        info.WebglHash,
        info.AudioHash,
        fmt.Sprintf("%d", info.HardwareConcurrency),
        info.Platform,
        fmt.Sprintf("%v", info.DoNotTrack),
        fmt.Sprintf("%d", info.MaxTouchPoints),
        fmt.Sprintf("%d", info.DeviceMemory),
    }
    
    // 2. 拼接特征
    fingerprint := strings.Join(features, "|")
    
    // 3. SHA256 哈希
    hash := sha256.Sum256([]byte(fingerprint))
    
    return fmt.Sprintf("%x", hash[:16])
}

// Canvas Hash 生成
func GenerateCanvasHash(canvas *html.CanvasElement) string {
    ctx := canvas.getContext("2d")
    
    // 绘制测试图形
    ctx.fillRect(0, 0, 100, 100)
    ctx.fillStyle = "#f60"
    ctx.fillRect(10, 10, 50, 50)
    ctx.fillStyle = "rgba(126, 146, 198, 0.5)"
    ctx.fillText("Test", 2, 15)
    
    // 获取渲染结果
    dataURL := canvas.toDataURL()
    
    // CRC32 哈希
    return fmt.Sprintf("%x", crc32.ChecksumIEEE([]byte(dataURL)))
}
```

### 3.3 行为分析

```go
package behavior

import (
    "time"
)

type ClickAnalyzer struct {
    clickHistory map[string][]ClickEvent
}

type ClickEvent struct {
    UserID    string
    AdID      string
    Timestamp time.Time
    IP        string
    DeviceID  string
    Location  Location
}

func (ca *ClickAnalyzer) DetectFraud(clicks []ClickEvent) []FraudSignal {
    signals := make([]FraudSignal, 0)
    
    // 1. 频率检测
    freqSignals := ca.detectFrequency(clicks)
    signals = append(signals, freqSignals...)
    
    // 2. 模式检测
    patternSignals := ca.detectPatterns(clicks)
    signals = append(signals, patternSignals...)
    
    // 3. 异常检测
    anomalySignals := ca.detectAnomalies(clicks)
    signals = append(signals, anomalySignals...)
    
    return signals
}

func (ca *ClickAnalyzer) detectFrequency(clicks []ClickEvent) []FraudSignal {
    signals := make([]FraudSignal, 0)
    
    // 按 IP 分组
    byIP := make(map[string][]ClickEvent)
    for _, click := range clicks {
        byIP[click.IP] = append(byIP[click.IP], click)
    }
    
    // 检测高频点击
    for ip, ipClicks := range byIP {
        if len(ipClicks) > 100 { // 每分钟超过 100 次
            signals = append(signals, FraudSignal{
                Type:      "high_frequency",
                IP:        ip,
                Severity:  "high",
                Score:     0.9,
                Timestamp: time.Now(),
            })
        }
    }
    
    return signals
}

type FraudSignal struct {
    Type      string
    IP        string
    DeviceID  string
    Severity  string // low/medium/high/critical
    Score     float64 // 0-1
    Timestamp time.Time
}
```

---

## 第四部分：流量分配

### 4.1 流量调度架构

```
用户请求 → 流量分发层 → 竞价层 → 广告选择 → 创意返回
              ↓
         策略引擎（权重/优先级/预算）
```

### 4.2 Go 实现流量分配器

```go
package traffic

import (
    "context"
    "math/rand"
    "sort"
    "sync"
)

// TrafficAllocator 流量分配器
type TrafficAllocator struct {
    mu           sync.RWMutex
    strategies   map[string]*Strategy
    defaultStrat string
}

type Strategy struct {
    Name      string
    Weight    float64    // 权重 0-1
    Pools     []Pool
    Enabled   bool
}

type Pool struct {
    Name     string
    Ads      []*Ad
    Priority int
}

type Ad struct {
    ID         string
    CampaignID string
    BidPrice   float64
    CTR        float64
    CVR        float64
    Status     string // active, paused, ended
}

// Allocate 分配流量
func (ta *TrafficAllocator) Allocate(ctx context.Context, req *TrafficRequest) (*Ad, error) {
    ta.mu.RLock()
    defer ta.mu.RUnlock()
    
    // 1. 选择策略
    strategy := ta.selectStrategy(req)
    if strategy == nil || !strategy.Enabled {
        return nil, ErrNoStrategy
    }
    
    // 2. 按权重分配流量
    pool := ta.selectPool(strategy, req)
    if pool == nil {
        return nil, ErrNoPool
    }
    
    // 3. 从池中选取广告
    ad := ta.selectAd(pool, req)
    if ad == nil {
        return nil, ErrNoAd
    }
    
    return ad, nil
}

func (ta *TrafficAllocator) selectStrategy(req *TrafficRequest) *Strategy {
    // 根据请求特征选择策略
    if req.Region == "us" {
        return ta.strategies["us_strategy"]
    }
    if req.DeviceType == "mobile" {
        return ta.strategies["mobile_strategy"]
    }
    
    return ta.strategies[ta.defaultStrat]
}

func (ta *TrafficAllocator) selectPool(strategy *Strategy, req *TrafficRequest) *Pool {
    // 加权随机选择池
    totalWeight := 0.0
    for _, pool := range strategy.Pools {
        totalWeight += float64(pool.Priority)
    }
    
    if totalWeight == 0 {
        return nil
    }
    
    r := rand.Float64() * totalWeight
    cumulative := 0.0
    
    for _, pool := range strategy.Pools {
        cumulative += float64(pool.Priority)
        if r <= cumulative {
            return &pool
        }
    }
    
    return &strategy.Pools[0]
}

func (ta *TrafficAllocator) selectAd(pool *Pool, req *TrafficRequest) *Ad {
    // 按 eCPM 排序选择
    sort.Slice(pool.Ads, func(i, j int) bool {
        eCPMi := pool.Ads[i].CTR * pool.Ads[i].CVR * pool.Ads[i].BidPrice
        eCPMj := pool.Ads[j].CTR * pool.Ads[j].CVR * pool.Ads[j].BidPrice
        return eCPMi > eCPMj
    })
    
    if len(pool.Ads) > 0 {
        return pool.Ads[0]
    }
    return nil
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

### 5.2 反作弊误杀

```
现象：大量正常用户被标记为欺诈

排查：
1. 检查误杀率
2. 分析被误杀用户的特征
3. 检查规则阈值

根因：点击频率阈值太低

解决方案：
1. 调整阈值
2. 使用机器学习模型
3. 添加人工审核流程
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
设备指纹如何防止伪造？

<details>
<summary>查看答案</summary>

1. **多特征组合**：Canvas/WebGL/Audio 指纹
2. **硬件信息**：CPU 核心数、内存
3. **浏览器指纹**：User-Agent + 插件
4. **行为特征**：鼠标移动、打字节奏
5. **Go 实现**：SHA256 哈希

</details>

### 问题 3
流量分配策略有哪些？

<details>
<summary>查看答案</summary>

1. **轮询**：均匀分配
2. **加权随机**：按权重分配
3. **eCPM 优先**：选择最高 eCPM
4. **多臂老虎机**：探索 + 利用
5. **Go 实现**：TrafficAllocator

</details>

---

*本文档基于广告系统架构原理整理。*