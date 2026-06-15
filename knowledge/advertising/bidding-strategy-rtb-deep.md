# 广告竞价深度：RTB 协议/出价策略/竞价引擎优化

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解实时竞价

```
用户打开 App → 广告位出现 → 拍卖开始 → 多个广告主出价 → 最高价中标

就像拍卖行：
- 主持人（Ad Exchange）喊价
- 买家（DSP）举牌出价
- 最高价者获得拍卖权
- 但付的是第二高价（VBP）

时间限制：从请求到出价，只有 100ms！
```

### 广告竞价生态

```
用户 → App/网站 → SSP → Ad Exchange → DSP → 广告主
                    ↕               ↕
                 底价管理         出价决策
```

| 角色 | 职责 | 代表 |
|------|------|------|
| **SSP** | 供应方，卖广告位 | Google Ad Manager, 穿山甲 |
| **Ad Exchange** | 广告交易平台 | Google AdX, AppNexus |
| **DSP** | 需求方，买流量 | The Trade Desk, 巨量引擎 |
| **DMP** | 数据平台，用户画像 | CDX, 自研 DMP |

---

## 第二部分：OpenRTB 协议（逐行解析）

### 2.1 Bid Request 结构

```
OpenRTB 2.5 规范是行业标准。

Bid Request 核心字段：
┌─────────────────────────────────────────────────────┐
│ id: "req-123456"           ← 请求唯一 ID             │
│ imp: [                     ← 广告位列表              │
│   {                         │                       │
│     id: "imp-001",          │                       │
│     banner: {               │                       │
│       w: 320,               │                       │
│       h: 50,                │                       │
│       pos: 1,               │                       │
│       mimes: ["image/jpeg"] │                       │
│     },                      │                       │
│     bidfloor: 0.5,          │ ← 底价（美元）         │
│     bidfloorcur: "USD"      │                       │
│   }                         │                       │
│ ]                           │                       │
│ device: {                   │ ← 设备信息             │
│   ua: "Mozilla/5.0...",     │                       │
│   ip: "192.168.1.1",        │                       │
│   make: "Apple",            │                       │
│   model: "iPhone 14",       │                       │
│   os: "iOS",                │                       │
│   osver: "16.0",            │                       │
│   connectiontype: 4         │ ← 4=4G, 5=WIFI        │
│ }                           │                       │
│ user: {                     │ ← 用户信息             │
│   id: "user-789",           │                       │
│   buyeruid: "dsp-user-789", │ ← DSP 的用户 ID        │
│   yob: 1990,                │                       │
│   gender: "M"               │                       │
│ }                           │                       │
│ at: 1                      │ ← 竞价类型（1=VBP）    │
│ tmax: 100                  │ ← 超时时间（ms）       │
└─────────────────────────────────────────────────────┘
```

### 2.2 Go 实现 Bid Request 解析

```go
package openrtb

import (
    "encoding/json"
    "fmt"
)

// BidRequest 竞价请求
type BidRequest struct {
    ID       string      `json:"id"`
    Imp      []Impression `json:"imp"`
    Device   *Device     `json:"device"`
    User     *User       `json:"user"`
    Site     *Site       `json:"site,omitempty"`
    App      *App        `json:"app,omitempty"`
    Regs     *Regs       `json:"regs,omitempty"`
    Ext      json.RawMessage `json:"ext,omitempty"`
}

// Impression 广告位
type Impression struct {
    ID          string       `json:"id"`
    Banner      *Banner      `json:"banner,omitempty"`
    Native      *Native      `json:"native,omitempty"`
    Video       *Video       `json:"video,omitempty"`
    BidFloor    float64      `json:"bidfloor,omitempty"`
    BidFloorCur string       `json:"bidfloorcur,omitempty"`
    TagID       string       `json:"tagid,omitempty"`
    Secure      bool         `json:"secure,omitempty"`
    Ext         json.RawMessage `json:"ext,omitempty"`
}

// Banner 横幅广告
type Banner struct {
    W      int      `json:"w,omitempty"`
    H      int      `json:"h,omitempty"`
    WMin   int      `json:"wmin,omitempty"`
    HMin   int      `json:"hmin,omitempty"`
    Pos    Position `json:"pos,omitempty"`
    Topfr  int      `json:"topframed,omitempty"`
    Mimes  []string `json:"mimes,omitempty"`
}

// Position 广告位置
type Position int

const (
    PosUnknown Position = iota
    PosFullscreen
    PosAboveFold
    PosBelowFold
    PosInHeader
    PosInBody
    PosInSidebar
)

// Device 设备信息
type Device struct {
    UA           string           `json:"ua,omitempty"`
    IP           string           `json:"ip,omitempty"`
    DevID        string           `json:"devicexid,omitempty"`
    Make         string           `json:"make,omitempty"`
    Model        string           `json:"model,omitempty"`
    OS           string           `json:"os,omitempty"`
    OSVer        string           `json:"osver,omitempty"`
    DNT          int              `json:"dnt,omitempty"`
    LMT          int              `json:"lmt,omitempty"`
    Carrier      string           `json:"carrier,omitempty"`
    Language     string           `json:"language,omitempty"`
    ConnectionType ConnectionType `json:"connectiontype,omitempty"`
}

type ConnectionType int

const (
    ConnUnknown ConnectionType = iota
    ConnEthernet
    ConnWifi
    ConnCellular
    ConnCellular2G
    ConnCellular3G
    ConnCellular4G
    ConnCellular5G
)

// User 用户信息
type User struct {
    ID     string            `json:"id,omitempty"`
    BuyerUID string          `json:"buyeruid,omitempty"`
    YOB    int               `json:"yob,omitempty"`
    Gender string            `json:"gender,omitempty"`
    Keywords string          `json:"keywords,omitempty"`
    Ext    json.RawMessage   `json:"ext,omitempty"`
}

// ParseBidRequest 解析 Bid Request
func ParseBidRequest(data []byte) (*BidRequest, error) {
    var req BidRequest
    err := json.Unmarshal(data, &req)
    if err != nil {
        return nil, fmt.Errorf("parse bid request: %w", err)
    }
    
    // 验证必填字段
    if req.ID == "" {
        return nil, fmt.Errorf("missing request ID")
    }
    if len(req.Imp) == 0 {
        return nil, fmt.Errorf("no impressions")
    }
    
    return &req, nil
}
```

### 2.3 Bid Response 结构

```
Bid Response 是 DSP 返回的竞价响应。

┌─────────────────────────────────────────────────────┐
│ id: "req-123456"           ← 对应请求 ID             │
│ seatbid: [                 ← 竞价响应列表            │
│   {                         │                       │
│     bid: [                  │                       │
│       {                       │                       │
│         id: "bid-001",      │                       │
│         impid: "imp-001",   │                       │
│         price: 0.85,        │ ← 出价（美元）         │
│         adm: "<html>...</html>", │ ← 广告创意 HTML   │
│         nurl: "https://...", │ ← 通知 URL           │
│         lurl: "https://...", │ ← 点击通知 URL       │
│         iurl: "https://...", │ ← 创意图片 URL       │
│         cid: "camp-001",    │ ← 广告组 ID           │
│         crid: "creative-001",│ ← 创意 ID             │
│         w: 320,             │                       │
│         h: 50,              │                       │
│         adomain: ["brand.com"],│ ← 广告域名          │
│         attr: [1, 2, 3]     │ ← 广告属性            │
│       }                      │                       │
│     ],                      │                       │
│     seat: "dsp-001",        │ ← 竞价方 ID           │
│     group: 0                │ ← 是否组竞价           │
│   }                         │                       │
│ ]                           │                       │
│ cur: "USD"                  ← 货币                  │
└─────────────────────────────────────────────────────┘
```

---

## 第三部分：出价策略深度

### 3.1 CPM / CPC / oCPM 对比

| 策略 | 付费方式 | 适用场景 | DSP 风险 | 广告主风险 |
|------|---------|---------|---------|-----------|
| **CPM** | 按千次曝光 | 品牌曝光 | 低 | 低 |
| **CPC** | 按点击 | 流量获取 | 中 | 中 |
| **oCPM** | 按转化出价 | 效果广告 | 高 | 低 |
| **oCPC** | 按转化出价 | 效果广告 | 高 | 低 |

### 3.2 oCPM 出价算法（逐行解析）

```
oCPM 核心公式：
bid = pCTR × pCVR × targetCPA

pCTR: 预测点击率
pCVR: 预测转化率
targetCPA: 目标每次转化成本

例如：
pCTR = 2% (0.02)
pCVR = 5% (0.05)
targetCPA = ¥100

bid = 0.02 × 0.05 × 100 = ¥0.1
```

```go
package bidding

import (
    "fmt"
    "math"
)

// BidEngine 竞价引擎
type BidEngine struct {
    ctrModel    *CTRModel
    cvrModel    *CVRModel
    budgetMgr   *BudgetManager
    freqCap     *FrequencyCap
    targetCPA   float64
    minBid      float64
    maxBid      float64
}

// Bid 执行竞价
func (be *BidEngine) Bid(req *BidRequest) (*BidResponse, error) {
    // 1. 频次控制检查
    if be.freqCap.IsExceeded(req.User.ID, req.Imp[0].ID) {
        return nil, nil // 不出价
    }
    
    // 2. 预算检查
    if !be.budgetMgr.HasBudget(req.Imp[0].CampaignID) {
        return nil, nil
    }
    
    // 3. 预测 CTR
    ctr := be.ctrModel.Predict(req)
    
    // 4. 预测 CVR
    cvr := be.cvrModel.Predict(req)
    
    // 5. 计算出价
    bidPrice := ctr * cvr * be.targetCPA
    
    // 6. 应用出价限制
    bidPrice = math.Max(bidPrice, be.minBid)
    bidPrice = math.Min(bidPrice, be.maxBid)
    
    // 7. 获取创意
    creative := be.getCreative(req.Imp[0].CampaignID)
    if creative == nil {
        return nil, nil
    }
    
    // 8. 构建响应
    return &BidResponse{
        RequestID: req.ID,
        BidPrice:  bidPrice,
        Creative:  creative,
    }, nil
}

// CTR 预测模型
type CTRModel struct {
    weights []float64
}

func (m *CTRModel) Predict(req *BidRequest) float64 {
    // 1. 提取特征
    features := m.extractFeatures(req)
    
    // 2. 线性模型
    logit := 0.0
    for i, f := range features {
        logit += f * m.weights[i]
    }
    
    // 3. Sigmoid 激活函数
    return 1.0 / (1.0 + math.Exp(-logit))
}

func (m *CTRModel) extractFeatures(req *BidRequest) []float64 {
    features := []float64{
        // 用户特征
        float64(req.User.Age) / 100.0,
        genderToFloat(req.User.Gender),
        locationToFloat(req.User.Location),
        
        // 上下文特征
        hourToFloat(req.Device.Hour),
        weekdayToFloat(req.Device.Weekday),
        connectionTypeToFloat(req.Device.ConnectionType),
        
        // 广告特征
        categoryToFloat(req.Imp[0].AdCategory),
        adFormatToFloat(req.Imp[0].Format),
        
        // 交叉特征
        userAge × categoryToFloat(req.Imp[0].AdCategory),
    }
    
    return features
}
```

### 3.3 出价优化

```go
// 出价优化器
type BidOptimizer struct {
    bidHistory map[string]*BidHistory
}

type BidHistory struct {
    Impressions int     // 曝光次数
    Clicks      int     // 点击次数
    Conversions int     // 转化次数
    Spent       float64 // 总花费
}

func (bo *BidOptimizer) OptimizeBid(req *BidRequest, campaignID string) float64 {
    history := bo.getHistory(campaignID)
    
    if history == nil || history.Impressions < 100 {
        // 冷启动：使用基础出价
        return bo.calculateBaseBid(req)
    }
    
    // 计算历史 CPA
    avgCPA := history.Spent / float64(history.Conversions)
    
    // 出价调整因子
    adjustmentFactor := 1.0
    if history.Conversions == 0 {
        adjustmentFactor = 0.5 // 无转化，保守出价
    } else if float64(history.Conversions)/float64(history.Clicks) > 0.1 {
        adjustmentFactor = 1.2 // 转化率高，提高出价
    }
    
    bid := req.TargetCPA * history.CTR * history.CVR * adjustmentFactor
    
    // 应用出价限制
    bid = math.Max(bid, bo.minBid)
    bid = math.Min(bid, bo.maxBid)
    
    return bid
}
```

---

## 第四部分：竞价引擎性能优化

### 4.1 为什么需要 < 100ms？

```
RTT（Round Trip Time）预算：
- 网络往返：20-50ms
- 服务端处理：30-50ms
- 数据库查询：5-10ms
- 模型预测：5-10ms

总计：60-120ms

如果超过 100ms：
- 用户会感知到延迟
- SSP 会超时，放弃竞价
- 收入下降
```

### 4.2 优化策略

```go
// 优化 1: 并行查询
func (be *BidEngine) BidParallel(req *BidRequest) (*BidResponse, error) {
    type result struct {
        profile *UserProfile
        ads     []*Ad
        err     error
    }
    
    ch := make(chan result, 2)
    
    // 并行查询用户画像和广告库存
    go func() {
        profile, err := be.getUserProfile(req.User.ID)
        ch <- result{profile: profile, err: err}
    }()
    
    go func() {
        ads, err := be.getAds(req.Imp[0].AdSlotID)
        ch <- result{ads: ads, err: err}
    }()
    
    // 等待结果
    var profile *UserProfile
    var ads []*Ad
    
    for i := 0; i < 2; i++ {
        r := <-ch
        if r.err != nil {
            return nil, r.err
        }
        if r.profile != nil {
            profile = r.profile
        }
        if r.ads != nil {
            ads = r.ads
        }
    }
    
    // 计算出价
    return be.calculateBid(req, profile, ads)
}

// 优化 2: 内存缓存
type Cache struct {
    profiles map[string]*UserProfile
    ads      map[string][]*Ad
}

func (c *Cache) GetProfile(userID string) (*UserProfile, bool) {
    profile, ok := c.profiles[userID]
    if ok {
        return profile, true
    }
    
    // 缓存未命中，查询数据库
    profile = c.db.GetProfile(userID)
    c.profiles[userID] = profile
    
    return profile, true
}

// 优化 3: 对象池
var bidReqPool = sync.Pool{
    New: func() interface{} {
        return &BidRequest{
            Impressions: make([]Impression, 0, 1),
        }
    },
}

func GetBidRequest() *BidRequest {
    return bidReqPool.Get().(*BidRequest)
}

func PutBidRequest(req *BidRequest) {
    req.Impressions = req.Impressions[:0]
    bidReqPool.Put(req)
}

// 优化 4: 预计算 CTR/CVR
type PrecomputedCTR struct {
    index map[string]float64 // key → CTR
}

func (p *PrecomputedCTR) GetCTR(key string) float64 {
    if ctr, ok := p.index[key]; ok {
        return ctr
    }
    return 0.01 // 默认 CTR
}
```

### 4.3 批量竞价

```go
// 批量竞价减少网络往返
func (be *BidEngine) BatchBid(reqs []*BidRequest) ([]*BidResponse, error) {
    // 1. 批量查询用户画像
    userIDs := make([]string, 0, len(reqs))
    for _, req := range reqs {
        userIDs = append(userIDs, req.User.ID)
    }
    
    profiles := be.batchGetProfiles(userIDs)
    
    // 2. 批量查询广告库存
    slotIDs := make([]string, 0, len(reqs))
    for _, req := range reqs {
        slotIDs = append(slotIDs, req.Imp[0].AdSlotID)
    }
    
    ads := be.batchGetAds(slotIDs)
    
    // 3. 批量计算出价
    responses := make([]*BidResponse, len(reqs))
    for i, req := range reqs {
        profile := profiles[req.User.ID]
        ad := ads[req.Imp[0].AdSlotID]
        
        responses[i] = &BidResponse{
            RequestID: req.ID,
            BidPrice:  be.calculateBid(req, profile, ad),
            Creative:  ad.Creative,
        }
    }
    
    return responses, nil
}
```

---

## 第五部分：生产排障案例

### 5.1 竞价延迟高

```
现象：P99 竞价延迟从 50ms 飙升到 200ms

排查：
1. pprof profile -cpu=10s -output=cpu.pprof
2. go tool pprof cpu.pprof
3. top 10 → 发现 getUserProfile 耗时过长
4. 检查 Redis 连接池

根因：Redis 连接池耗尽，等待连接超时

解决方案：
1. 增大连接池大小
2. 添加连接池监控
3. 使用本地缓存减少 Redis 查询
```

```go
// 监控竞价延迟
func recordBidLatency(latency time.Duration, status string) {
    bidLatency.WithLabelValues(status).Observe(latency.Seconds() * 1000)
}

// Prometheus 查询
// histogram_quantile(0.99, rate(bid_latency_ms_bucket[5m]))
```

### 5.2 出价策略问题

```
现象：某个 campaign 花费过快，预算提前用完

排查：
1. 检查出价是否过高
2. 检查 CTR/CVR 预估是否准确
3. 检查频次控制是否生效

根因：CTR 预估偏高，导致出价过高

解决方案：
1. 校准 CTR 模型
2. 添加出价上限
3. 使用动态出价调整
```

### 5.3 内存泄漏

```
现象：竞价服务内存持续增长

排查：
1. pprof heap -inuse_space -output=heap.pprof
2. go tool pprof heap.pprof
3. top 10 → 发现 BidRequest 对象未回收

根因：对象池使用不当

解决方案：
1. 确保 PutBidRequest 被调用
2. 添加 deferred Put
3. 监控对象池大小
```

---

## 第六部分：自测题

### 问题 1
为什么竞价引擎需要 < 100ms？

<details>
<summary>查看答案</summary>

1. **RTT 预算**：网络 + 服务端处理 + 数据库
2. **超时机制**：SSP 等待超时
3. **用户体验**：用户感知延迟
4. **收入影响**：超时 = 失去竞价机会
5. **优化方案**：并行查询 + 内存缓存

</details>

### 问题 2
oCPM 相比 CPM/CPC 有什么优势？

<details>
<summary>查看答案</summary>

1. **目标 CPA**：以转化为目标出价
2. **自动出价**：根据 CTR/CVR 自动调整
3. **ROI 更高**：避免无效曝光
4. **算法复杂**：需要精准的 CTR/CVR 预估
5. **DSP 风险高**：需要精准模型

</details>

### 问题 3
如何优化竞价引擎性能？

<details>
<summary>查看答案</summary>

1. **并行查询**：用户画像 + 广告库存并行
2. **内存缓存**：避免 Redis 网络 IO
3. **对象池**：减少 GC 压力
4. **预计算**：CTR/CVR 预计算
5. **批量处理**：减少网络往返

</details>

---

*本文档基于广告竞价原理和生产实战整理。*