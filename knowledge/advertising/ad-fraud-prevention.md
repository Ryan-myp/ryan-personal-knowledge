# 广告反作弊深度：规则引擎/机器学习/设备指纹

> 点击欺诈/刷量/机器人检测/设备指纹/行为分析

---

## 第一部分：入门引导（5 分钟速览）

### 为什么反作弊很重要？

广告欺诈每年造成数百亿美元损失：
- **点击欺诈**：虚假点击消耗预算
- **刷量**：虚假安装/注册
- **机器人流量**：非人类用户
- **流量劫持**：中间人攻击

---

## 第二部分：设备指纹

### 2.1 设备指纹生成

```go
package fingerprint

import (
    "crypto/sha256"
    "fmt"
    "net"
    "strings"
)

type DeviceInfo struct {
    UserAgent   string
    ScreenSize  string
    Language    string
    TimeZone    string
    CanvasHash  string
    WebglHash   string
    AudioHash   string
    HardwareConcurency int
    Platform    string
    DoNotTrack  bool
    MaxTouchPoints int
    DeviceMemory int
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
```

### 2.2 IP 信誉评分

```go
type IPReputation struct {
    reputationScores map[string]float64
}

func (ir *IPReputation) GetScore(ip string) float64 {
    if score, ok := ir.reputationScores[ip]; ok {
        return score
    }
    
    // 计算 IP 信誉
    score := ir.calculateIPReputation(ip)
    ir.reputationScores[ip] = score
    
    return score
}

func (ir *IPReputation) calculateIPReputation(ip string) float64 {
    score := 1.0 // 默认满分
    
    // 1. 检查是否为数据中心 IP
    if ir.isDatacenterIP(ip) {
        score -= 0.3
    }
    
    // 2. 检查是否为代理/VPN
    if ir.isProxyIP(ip) {
        score -= 0.4
    }
    
    // 3. 检查 Tor 节点
    if ir.isTorNode(ip) {
        score -= 0.5
    }
    
    // 4. 检查 IP 历史
    if ir.hasSuspiciousHistory(ip) {
        score -= 0.2
    }
    
    return math.Max(0, score)
}
```

---

## 第三部分：行为分析

### 3.1 点击模式分析

```go
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

func (ca *ClickAnalyzer) detectPatterns(clicks []ClickEvent) []FraudSignal {
    signals := make([]FraudSignal, 0)
    
    // 按设备分组
    byDevice := make(map[string][]ClickEvent)
    for _, click := range clicks {
        byDevice[click.DeviceID] = append(byDevice[click.DeviceID], click)
    }
    
    // 检测设备轮换
    for deviceID, deviceClicks := range byDevice {
        ips := make(map[string]bool)
        for _, click := range deviceClicks {
            ips[click.IP] = true
        }
        
        if len(ips) > 10 { // 一个设备对应多个 IP
            signals = append(signals, FraudSignal{
                Type:      "device_rotation",
                DeviceID:  deviceID,
                Severity:  "medium",
                Score:     0.7,
            })
        }
    }
    
    return signals
}
```

### 3.2 转化漏斗分析

```go
type FunnelAnalyzer struct {
    stages []FunnelStage
}

type FunnelStage struct {
    Name      string
    Threshold float64 // 正常转化率阈值
}

func (fa *FunnelAnalyzer) Analyze(conversions []Conversion) []FraudSignal {
    signals := make([]FraudSignal, 0)
    
    // 1. 计算各阶段转化率
    rates := fa.calculateConversionRates(conversions)
    
    // 2. 检测异常
    for stage, rate := range rates {
        if rate > fa.stages[stage].Threshold*2 {
            // 转化率异常高
            signals = append(signals, FraudSignal{
                Type:      "high_conversion_rate",
                Stage:     stage,
                Severity:  "high",
                Score:     0.8,
            })
        }
        
        if rate < fa.stages[stage].Threshold*0.1 && rate > 0 {
            // 转化率异常低（可能是僵尸流量）
            signals = append(signals, FraudSignal{
                Type:      "low_conversion_rate",
                Stage:     stage,
                Severity:  "medium",
                Score:     0.6,
            })
        }
    }
    
    return signals
}
```

---

## 第四部分：机器学习反欺诈

### 4.1 特征工程

```go
type FraudFeatures struct {
    // 设备特征
    DeviceScore    float64 // 设备信誉
    IPReputation   float64 // IP 信誉
    FingerprintAge int     // 指纹存在天数
    
    // 行为特征
    ClickRate      float64 // 点击频率
    TimeOfDay      int     // 一天中的小时
    DayOfWeek      int     // 一周中的星期几
    
    // 地理特征
    DistanceFromHome float64 // 离家距离
    CountryRisk      float64 // 国家风险
    
    // 历史特征
    PreviousFraudCount int // 历史欺诈次数
    AccountAge         int // 账号年龄
}

func ExtractFeatures(event Event) FraudFeatures {
    return FraudFeatures{
        DeviceScore:    GetDeviceScore(event.DeviceID),
        IPReputation:   GetIPReputation(event.IP),
        FingerprintAge: GetFingerprintAge(event.Fingerprint),
        ClickRate:      CalculateClickRate(event.UserID),
        TimeOfDay:      event.Timestamp.Hour(),
        DayOfWeek:      int(event.Timestamp.Weekday()),
        DistanceFromHome: CalculateDistance(event.Location, GetUserHome(event.UserID)),
        CountryRisk:    GetCountryRisk(event.Location.Country),
        PreviousFraudCount: CountPreviousFrauds(event.UserID),
        AccountAge:     GetAccountAge(event.UserID),
    }
}
```

### 4.2 随机森林模型

```go
type RandomForest struct {
    trees []*DecisionTree
    nFeatures int
}

func (rf *RandomForest) Predict(features []float64) float64 {
    predictions := make([]float64, len(rf.trees))
    
    for i, tree := range rf.trees {
        predictions[i] = tree.Predict(features)
    }
    
    // 多数投票
    fraudCount := 0
    for _, pred := range predictions {
        if pred > 0.5 {
            fraudCount++
        }
    }
    
    return float64(fraudCount) / float64(len(rf.trees))
}

func (rf *RandomForest) Train(events []Event, labels []int) {
    nTrees := 100
    rf.trees = make([]*DecisionTree, nTrees)
    rf.nFeatures = len(events[0].Features)
    
    for i := 0; i < nTrees; i++ {
        // Bootstrap 采样
        bootstrapEvents, bootstrapLabels := rf.bootstrapSample(events, labels)
        
        // 训练决策树
        rf.trees[i] = NewDecisionTree(bootstrapEvents, bootstrapLabels, rf.nFeatures)
    }
}
```

---

## 第五部分：自测题

### 问题 1
设备指纹如何防止伪造？

<details>
<summary>查看答案</summary>

1. **多特征组合**：Canvas/WebGL/Audio 指纹
2. **硬件信息**：CPU 核心数、内存
3. **浏览器指纹**：User-Agent + 插件
4. **行为特征**：鼠标移动、打字节奏
5. **Go 实现**：SHA256 哈希

</details>

### 问题 2
如何检测点击农场？

<details>
<summary>查看答案</summary>

1. **IP 聚集**：同一 IP 大量点击
2. **设备聚集**：同一设备大量账号
3. **时间规律**：固定时间间隔点击
4. **行为异常**：无页面浏览直接点击
5. **Go 实现**：ClickAnalyzer

</details>

### 问题 3
机器学习反欺诈相比规则引擎有什么优势？

<details>
<summary>查看答案</summary>

1. **自适应**：自动学习新模式
2. **综合判断**：考虑多个特征
3. **减少误报**：更精确的阈值
4. **可扩展**：轻松添加新特征
5. **Go 实现**：RandomForest

</details>

---

*本文档基于广告反作弊原理整理。*