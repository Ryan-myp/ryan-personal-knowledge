# 广告系统竞价引擎深度解析

> 深入广告竞价引擎：实时竞价、出价策略、质量分计算、反作弊。
> 包含真实生产环境竞价系统设计。
> 适用对象：广告系统工程师、架构师、算法工程师

---

## 1. 竞价引擎架构

### 1.1 整体架构

```
实时竞价 (RTB) 架构：

┌─────────────────────────────────────────────────────────────┐
│                    RTB 流程                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 用户访问网站/APP                                          │
│     └── 请求广告位                                           │
│                                                             │
│  2. Ad Exchange (广告交易平台)                                 │
│     ├── 收集广告请求                                           │
│     └── 发送竞价请求到 DSP                                     │
│                                                             │
│  3. DSP (需求方平台)                                          │
│     ├── 获取用户画像                                           │
│     ├── 计算出价                                               │
│     └── 返回竞价响应                                           │
│                                                             │
│  4. 竞价决策                                                  │
│     ├── 最高价中标 (第二价格拍卖)                                │
│     └── 质量分调整                                             │
│                                                             │
│  5. 广告展示                                                  │
│     └── 返回广告创意                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现竞价引擎核心

```go
// bidding_engine.go

package ad

import (
    "sync"
)

type BidRequest struct {
    ImpressionID string
    User         User
    Site         Site
    AdSlot       AdSlot
    Timestamp    int64
}

type BidResponse struct {
    ImpressionID string
    BidPrice     float64
    CreativeID   string
    Targeting    map[string]string
}

type BiddingEngine struct {
    bidders   map[string]*Bidder
    mu        sync.RWMutex
}

type Bidder struct {
    ID      string
    Name    string
    Strategy BiddingStrategy
}

type BiddingStrategy interface {
    CalculateBid(req *BidRequest) float64
}

func NewBiddingEngine() *BiddingEngine {
    return &BiddingEngine{
        bidders: make(map[string]*Bidder),
    }
}

func (be *BiddingEngine) RegisterBidder(id string, bidder *Bidder) {
    be.mu.Lock()
    defer be.mu.Unlock()
    be.bidders[id] = bidder
}

func (be *BiddingEngine) ProcessBid(req *BidRequest) (*BidResponse, error) {
    be.mu.RLock()
    defer be.mu.RUnlock()
    
    var highestBid float64
    var winningBidder string
    var winningCreative string
    
    for id, bidder := range be.bidders {
        bidPrice := bidder.Strategy.CalculateBid(req)
        if bidPrice > highestBid {
            highestBid = bidPrice
            winningBidder = id
            winningCreative = bidder.getCreative(req)
        }
    }
    
    return &BidResponse{
        ImpressionID: req.ImpressionID,
        BidPrice:     highestBid,
        CreativeID:   winningCreative,
    }, nil
}
```

---

## 2. 出价策略

### 2.1 常见出价策略

```
┌────────────────┬─────────────────────────────────────┬──────────────┐
│ 出价策略       │ 说明                                │ 适用场景     │
├────────────────┼─────────────────────────────────────┼──────────────┤
│ 固定出价       │ 固定价格出价                         │ 简单场景     │
│ 智能出价       │ 基于ROI自动调整                      │ 效果广告     │
│ 目标ROAS       │ 按目标回报设置出价                   │ 电商广告     │
│ 最大转化       │ 在预算内最大化转化                   │ 转化广告     │
│ 程序化出价     │ 基于机器学习实时调整                 │ 大规模投放   │
└────────────────┴─────────────────────────────────────┴──────────────┘
```

### 2.2 Go 实现智能出价

```go
// smart_bidding.go

package ad

import (
    "math"
)

type SmartBidder struct {
    budget      float64
    targetROAS  float64
    historicalData map[string]float64
}

func NewSmartBidder(budget, targetROAS float64) *SmartBidder {
    return &SmartBidder{
        budget:     budget,
        targetROAS: targetROAS,
    }
}

func (sb *SmartBidder) CalculateBid(req *BidRequest) float64 {
    // 基础出价
    baseBid := sb.calculateBaseBid(req)
    
    // 质量分调整
    qualityScore := sb.calculateQualityScore(req)
    baseBid *= qualityScore
    
    // ROI调整
    if sb.targetROAS > 0 {
        baseBid *= sb.targetROAS
    }
    
    // 预算控制
    baseBid = sb.applyBudgetConstraint(baseBid)
    
    return baseBid
}

func (sb *SmartBidder) calculateBaseBid(req *BidRequest) float64 {
    // 基于用户价值计算
    userValue := sb.getUserValue(req.User)
    return userValue * 0.01 // 转换为出价
}

func (sb *SmartBidder) calculateQualityScore(req *BidRequest) float64 {
    // 点击率预估
    ctr := sb.predictCTR(req)
    // 转化率预估
    cvr := sb.predictCVR(req)
    
    // 质量分 = CTR * CVR * 100
    return math.Min(1.0, ctr*cvr*100)
}

func (sb *SmartBidder) predictCTR(req *BidRequest) float64 {
    // 简化版CTR预估
    return 0.02 + req.User.Age*0.001
}

func (sb *SmartBidder) predictCVR(req *BidRequest) float64 {
    // 简化版CVR预估
    return 0.05 + req.User.PurchaseHistory*0.01
}
```

---

## 3. 质量分计算

### 3.1 质量分因素

```
质量分计算因素：

1. 点击率 (CTR)
   └── 历史点击表现

2. 转化率 (CVR)
   └── 历史转化表现

3. 创意质量
   └── 素材清晰度、吸引力

4. 落地页体验
   └── 加载速度、相关性

5. 广告相关性
   └── 与用户兴趣匹配度
```

### 3.2 Go 实现质量分

```go
// quality_score.go

package ad

type QualityScore struct {
    CTR        float64
    CVR        float64
    Creative   float64
    LandingPage float64
    Relevance  float64
    Total      float64
}

func CalculateQualityScore(
    ctr, cvr, creative, landingPage, relevance float64,
) *QualityScore {
    // 加权计算
    total := ctr*0.3 + cvr*0.25 + creative*0.2 + landingPage*0.15 + relevance*0.1
    
    return &QualityScore{
        CTR:        ctr,
        CVR:        cvr,
        Creative:   creative,
        LandingPage: landingPage,
        Relevance:  relevance,
        Total:      total,
    }
}

func (qs *QualityScore) GetLevel() string {
    switch {
    case qs.Total >= 0.9:
        return "优秀"
    case qs.Total >= 0.7:
        return "良好"
    case qs.Total >= 0.5:
        return "一般"
    default:
        return "较差"
    }
}
```

---

## 4. 反作弊系统

### 4.1 作弊类型

```
广告作弊类型：

1. 点击作弊
   ├── 机器点击
   ├── 点击农场
   └── 诱导点击

2. 展示作弊
   ├── 不可见广告
   ├── 堆叠广告
   └── 自动刷新

3. 转化作弊
   ├── 虚假转化
   ├── 刷单
   └── 机器人转化
```

### 4.2 Go 实现反作弊检测

```go
// anti_fraud.go

package ad

import (
    "time"
)

type FraudDetector struct {
    clickPatterns map[string][]time.Time
    ipPatterns    map[string]int
    devicePatterns map[string]int
}

func NewFraudDetector() *FraudDetector {
    return &FraudDetector{
        clickPatterns: make(map[string][]time.Time),
        ipPatterns:    make(map[string]int),
        devicePatterns: make(map[string]int),
    }
}

func (fd *FraudDetector) DetectClickFraud(click ClickEvent) bool {
    // 点击频率检测
    if fd.isRapidClicks(click.IP, click.Time) {
        return true
    }
    
    // IP异常检测
    if fd.isSuspiciousIP(click.IP) {
        return true
    }
    
    // 设备异常检测
    if fd.isSuspiciousDevice(click.DeviceID) {
        return true
    }
    
    return false
}

func (fd *FraudDetector) isRapidClicks(ip string, clickTime time.Time) bool {
    fd.clickPatterns[ip] = append(fd.clickPatterns[ip], clickTime)
    
    // 检查最近1秒内的点击数
    recentClicks := 0
    for _, t := range fd.clickPatterns[ip] {
        if clickTime.Sub(t) < time.Second {
            recentClicks++
        }
    }
    
    return recentClicks > 10 // 超过10次/秒视为异常
}

func (fd *FraudDetector) isSuspiciousIP(ip string) bool {
    fd.ipPatterns[ip]++
    return fd.ipPatterns[ip] > 100 // 同一IP超过100次点击
}

func (fd *FraudDetector) isSuspiciousDevice(deviceID string) bool {
    fd.devicePatterns[deviceID]++
    return fd.devicePatterns[deviceID] > 50
}
```

---

## 5. 竞价优化

### 5.1 优化策略

```
竞价优化策略：

1. 出价优化
   ├── 基于历史数据调整
   ├── A/B 测试
   └── 机器学习模型

2. 定向优化
   ├── 人群包优化
   ├── 时段优化
   └── 地域优化

3. 创意优化
   ├── 素材A/B测试
   ├── 自动创意
   └── 动态创意
```

### 5.2 Go 实现竞价优化

```go
// bidding_optimizer.go

package ad

type BiddingOptimizer struct {
    historicalData map[string][]float64
    learningRate   float64
}

func NewBiddingOptimizer() *BiddingOptimizer {
    return &BiddingOptimizer{
        historicalData: make(map[string][]float64),
        learningRate:   0.1,
    }
}

func (bo *BiddingOptimizer) OptimizeBid(impressionID string, currentBid float64, conversion float64) float64 {
    // 记录历史数据
    bo.historicalData[impressionID] = append(bo.historicalData[impressionID], conversion)
    
    // 计算平均转化率
    avgConversion := bo.calculateAvgConversion(impressionID)
    
    // 调整出价
    if conversion > avgConversion {
        // 转化好，提高出价
        return currentBid * (1 + bo.learningRate)
    } else if conversion < avgConversion {
        // 转化差，降低出价
        return currentBid * (1 - bo.learningRate)
    }
    
    return currentBid
}

func (bo *BiddingOptimizer) calculateAvgConversion(impressionID string) float64 {
    data := bo.historicalData[impressionID]
    if len(data) == 0 {
        return 0.01
    }
    
    sum := 0.0
    for _, v := range data {
        sum += v
    }
    return sum / float64(len(data))
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 竞价引擎 | 实时出价 + 质量分 |
| 出价策略 | 智能出价 + ROI优化 |
| 质量分 | CTR + CVR + 创意质量 |
| 反作弊 | 行为分析 + 异常检测 |

### 6.2 最佳实践

- [ ] 实时优化出价策略
- [ ] 建立反作弊机制
- [ ] 持续监控质量分
- [ ] A/B 测试迭代优化
- [ ] 建立数据反馈闭环

---

*最后更新：2026-08-11*
*作者：Ryan*

---

## 自测题

<details>
<summary>Q1: 出价引擎的核心目标函数是什么？如何平衡eCPM与广告主ROI？</summary>

**答案：**
核心目标函数：
```
maximize: eCPM = bid_price × QCTR × 1000
subject to: ROI_constraint = spend / revenue >= target_roi
```

**平衡策略**：
- 高ROI广告主：降低bid_price，扩大覆盖面
- 低ROI广告主：提高bid_price，精准投放
- 动态调整：根据历史转化数据实时修正

</details>

<details>
<summary>Q2: 为什么出价引擎需要使用实时特征而非离线特征？</summary>

**答案：**
| 特征类型 | 时效性 | 准确性 | 适用场景 |
|----------|--------|--------|----------|
| 离线特征 | 小时级 | 稳定 | 用户画像 |
| 实时特征 | 秒级 | 动态 | 行为序列 |
| 融合特征 | 毫秒级 | 最优 | 出价决策 |

实时特征价值：
- 捕捉用户即时意图（如搜索关键词）
- 避免"过期"行为导致误判
- 提升CTR预估准确度15-30%

</details>

<details>
<summary>Q3: 出价引擎如何处理预算耗尽的边界情况？</summary>

**答案：**
三级预算控制机制：

```python
class BudgetController:
    def check_budget(self, campaign_id: str, bid: float) -> bool:
        # 1. 本地预检（毫秒级）
        if self.local_budget[campaign_id] < bid:
            return False
        
        # 2. 分布式扣除
        success = redis.decrby(f"budget:{campaign_id}", bid)
        
        # 3. 兜底检查
        if success < 0:
            redis.incrby(f"budget:{campaign_id}", bid)  # 回滚
            return False
        return True
```

</details>

<details>
<summary>Q4: 如何实现出价策略的A/B测试框架？</summary>

**答案：**
分流+监控双机制：
- **实验组**：新策略（如深度学习出价）
- **对照组**：基准策略（如规则出价）
- **监控指标**：eCPM、ROI、填充率、转化率

</details>

<details>
<summary>Q5: 出价引擎的模型服务如何进行实时推理加速？</summary>

**答案：**
三层加速架构：
1. **特征缓存**：Redis缓存高频特征（TTL=5s）
2. **模型预估**：TensorFlow Serving + GPU推理
3. **结果缓存**：相同请求直接返回（防抖）

</details>

---

*最后更新：2026-08-12*
*升级：添加自测题（5道）*
