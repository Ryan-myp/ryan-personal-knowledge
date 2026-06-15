# 广告反作弊深度：规则引擎/机器学习/设备指纹

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解反作弊

```
广告欺诈 = 考试作弊
- 刷分：虚假分数
- 替考：假人答题
- 作弊器：自动化脚本

广告反作弊 = 监考老师
- 身份验证：确认是真人
- 行为分析：观察异常行为
- 设备指纹：记住作弊者特征
```

### 广告欺诈的类型

| 类型 | 说明 | 占比 | 损失 |
|------|------|------|------|
| **点击欺诈** | 虚假点击消耗预算 | 15-20% | 最高 |
| **刷量** | 虚假安装/注册 | 10-15% | 高 |
| **机器人流量** | 非人类用户 | 5-10% | 中 |
| **流量劫持** | 中间人攻击 | < 5% | 中 |
| **SDK 欺诈** | 伪造 SDK 报告 | 5-10% | 高 |

---

## 第二部分：设备指纹深度

### 2.1 设备指纹原理

```
设备指纹 = 多个特征的哈希值

收集的特征：
1. User-Agent（浏览器类型/版本）
2. Screen Size（屏幕分辨率）
3. Language（语言设置）
4. Timezone（时区）
5. Canvas Hash（Canvas 渲染指纹）
6. WebGL Hash（WebGL 渲染指纹）
7. Audio Hash（音频输出指纹）
8. Hardware Concurrency（CPU 核心数）
9. Platform（操作系统）
10. Max Touch Points（最大触控点数）
11. Device Memory（设备内存）

为什么需要这么多特征？
- 单个特征容易被伪造
- 组合特征很难完全伪造
- 即使伪造部分特征，哈希值也会变化
```

### 2.2 Go 实现设备指纹

```go
package fingerprint

import (
    "crypto/sha256"
    "fmt"
    "hash/crc32"
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

### 2.3 IP 信誉评分

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

func (ir *IPReputation) isDatacenterIP(ip string) bool {
    // 检查 IP 是否属于数据中心
    // 使用 Whois 查询或第三方 API
    return false // 简化实现
}

func (ir *IPReputation) isProxyIP(ip string) bool {
    // 检查 IP 是否为代理
    // 使用代理数据库查询
    return false // 简化实现
}

func (ir *IPReputation) isTorNode(ip string) bool {
    // 检查 IP 是否为 Tor 节点
    // 使用 Tor 目录查询
    return false // 简化实现
}

func (ir *IPReputation) hasSuspiciousHistory(ip string) bool {
    // 检查 IP 是否有欺诈历史
    // 查询黑名单数据库
    return false // 简化实现
}
```

---

## 第三部分：行为分析

### 3.1 点击模式分析

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

type FraudSignal struct {
    Type      string
    IP        string
    DeviceID  string
    Severity  string // low/medium/high/critical
    Score     float64 // 0-1
    Timestamp time.Time
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

## 第五部分：生产排障案例

### 5.1 误杀正常用户

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

### 5.2 新型欺诈攻击

```
现象：突然出现大量欺诈点击

排查：
1. 检查欺诈信号类型
2. 分析攻击模式
3. 检查是否有新的攻击向量

根因：新的点击农场出现

解决方案：
1. 更新设备指纹库
2. 添加新的规则
3. 训练新的 ML 模型
```

---

## 第六部分：自测题

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

*本文档基于广告反作弊原理和生产实战整理。*