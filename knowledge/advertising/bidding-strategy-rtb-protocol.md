# 广告竞价深度：RTB 协议/实时竞价系统/出价策略

> OpenRTB 协议规范 / 竞价引擎架构 / VBP 第二价格竞价 / CPM/CPC/oCPM 出价策略 / 实时竞价优化

---

## 第一部分：入门引导（5 分钟速览）

### 实时竞价 RTB 是什么？

```
用户访问 App → SSP → Ad Exchange → DSP → 返回广告
                    ↕               ↕
                 底价管理         出价决策
```

**RTB 核心流程：**
1. 用户打开 App，SSP 收到曝光请求
2. SSP 封装为 OpenRTB Bid Request 发给 Ad Exchange
3. Ad Exchange 并行转发给多个 DSP
4. DSP 在 100ms 内完成出价决策
5. Ad Exchange 选最高价，DSP 支付
6. 广告展示，DSP 记录曝光/点击/转化

---

## 第二部分：OpenRTB 协议深度

### 2.1 Bid Request 结构

```go
package openrtb

// BidRequest 竞价请求 - OpenRTB 2.5 规范
type BidRequest struct {
    ID              string          `json:"id"`               // 唯一请求 ID
    Imp             []Impression    `json:"imp"`              // 广告位列表
    Site            *Site           `json:"site,omitempty"`   // 网站信息
    App             *App            `json:"app,omitempty"`    // App 信息
    Device          *Device         `json:"device"`           // 设备信息
    User            *User           `json:"user,omitempty"`   // 用户信息
    Regs            *Regs           `json:"regs,omitempty"`   // 法规限制
    Ext             json.RawMessage `json:"ext,omitempty"`    // 扩展字段
}

// Impression 广告位
type Impression struct {
    ID            string        `json:"id"`                    // 广告位 ID
    Banner        *Banner       `json:"banner,omitempty"`      // 横幅广告
    Native        *NativeRequest `json:"native,omitempty"`     // 原生广告
    Video         *VideoRequest `json:"video,omitempty"`       // 视频广告
    BidFloor      float64       `json:"bidfloor,omitempty"`    // 底价
    BidFloorCur   string        `json:"bidfloorcur,omitempty"` // 底价货币
    TagID         string        `json:"tagid,omitempty"`       // 标签 ID
    Secure        bool          `json:"secure,omitempty"`      // HTTPS
    BidWatch      []string      `json:"bidwatch,omitempty"`    // 竞价追踪
    Ext           json.RawMessage `json:"ext,omitempty"`       // 扩展
}

// Banner 横幅广告
type Banner struct {
    W      int      `json:"w,omitempty"`       // 宽度
    H      int      `json:"h,omitempty"`       // 高度
    WMin   int      `json:"wmin,omitempty"`    // 最小宽度
    HMin   int      `json:"hmin,omitempty"`    // 最小高度
    Pos    Position `json:"pos,omitempty"`     // 位置
    Topfr  int      `json:"topframed,omitempty"` // 顶层框架
    Mimes  []string `json:"mimes,omitempty"`    // MIME 类型
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
    PosAtTop
    PosJustBelowBanner
    PosJustAboveFold
)

// Device 设备信息
type Device struct {
    UA        string      `json:"ua,omitempty"`         // User-Agent
    IP        string      `json:"ip,omitempty"`         // IP 地址
    DevID     string      `json:"devicexid,omitempty"`  // 设备 ID
    Make      string      `json:"make,omitempty"`       // 设备厂商
    Model     string      `json:"model,omitempty"`      // 设备型号
    OS        string      `json:"os,omitempty"`         // 操作系统
    OSVer     string      `json:"osver,omitempty"`      // 系统版本
    DNT       int         `json:"dnt,omitempty"`        // Do Not Track
    LMT       int         `json:"lmt,omitempty"`        // Limit Ad Tracking
    Carrier   string      `json:"carrier,omitempty"`    // 运营商
    Language  string      `json:"language,omitempty"`   // 语言
    ConnectionType ConnectionType `json:"connectiontype,omitempty"` // 连接类型
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
    ConnOffline
)

// User 用户信息
type User struct {
    ID     string            `json:"id,omitempty"`     // 用户 ID
   buyerExt json.RawMessage  `json:"buyeruid,omitempty"` // Buyer ID
    YOB    int               `json:"yob,omitempty"`    // 出生年份
    GENDER string            `json:"gender,omitempty"` // 性别
    Keywords string          `json:"keywords,omitempty"` // 关键词
    Ext    json.RawMessage   `json:"ext,omitempty"`    // 扩展
}

// BidResponse 竞价响应 - OpenRTB 2.5 规范
type BidResponse struct {
    ID       string    `json:"id"`              // 请求 ID
    SeatBid  []SeatBid `json:"seatbid"`         // 竞价响应列表
    Bidid    string    `json:"bidid,omitempty"` // 竞价 ID
    Cur      string    `json:"cur,omitempty"`   // 货币
    NBR      int       `json:"nbr,omitempty"`   // 无竞价原因
    Ext      json.RawMessage `json:"ext,omitempty"` // 扩展
}

type SeatBid struct {
    Bid  []Bid   `json:"bid"`       // 竞价列表
    Seat string  `json:"seat"`      // 竞价方 ID
    Group  int     `json:"group,omitempty"` // 是否组竞价
}

type Bid struct {
    ID       string  `json:"id"`          // 竞价 ID
    ImpID    string  `json:"impid"`       // 广告位 ID
    Price    float64 `json:"price"`       // 出价
    ADM      string  `json:"adm"`         // 广告创意 HTML
    NURL     string  `json:"nurl"`        // 通知 URL
    LURL     string  `json:"lurl"`        // 点击通知 URL
    IURL     string  `json:"iurl"`        // 创意图片 URL
    CID      string  `json:"cid"`         // 广告组 ID
    CrID     string  `json:"crid"`        // 创意 ID
    W       int      `json:"w,omitempty"` // 创意宽度
    H       int      `json:"h,omitempty"` // 创意高度
    Attr     []string `json:"attr,omitempty"` // 广告属性
    API      int      `json:"api,omitempty"` // API 框架
    Mtype    int      `json:"mtype,omitempty"` // 媒体类型
    Adomain  []string `json:"adomain,omitempty"` // 广告域名
    Ext      json.RawMessage `json:"ext,omitempty"` // 扩展
}

type Adomain []string // 广告域名列表
```

### 2.2 Bid Response 生成

```go
func (be *BidEngine) GenerateResponse(req *BidRequest) (*BidResponse, error) {
    seatBids := make([]SeatBid, 0)
    
    for _, imp := range req.Imp {
        // 1. 检查底价
        if imp.BidFloor > 0 {
            // 检查是否有满足底价的创意
        }
        
        // 2. 获取匹配的广告
        ads := be.matchAds(req, imp)
        if len(ads) == 0 {
            continue
        }
        
        // 3. 计算出价
        bid := be.calculateBid(req, imp, ads[0])
        
        // 4. 构建竞价响应
        seatBids = append(seatBids, SeatBid{
            Seat: "dsp-001",
            Group: 0,
            Bid: []Bid{
                {
                    ID:      uuid.New().String(),
                    ImpID:   imp.ID,
                    Price:   bid.Price,
                    ADM:     bid.Creative.HTML,
                    NURL:    fmt.Sprintf("https://bid.ad-platform.com/notify?bid_id=%s", bid.ID),
                    LURL:    fmt.Sprintf("https://bid.ad-platform.com/log?bid_id=%s&imp=%s", bid.ID, imp.ID),
                    IURL:    bid.Creative.ImageURL,
                    CID:     bid.CampaignID,
                    CrID:    bid.CreativeID,
                    W:       bid.Creative.Width,
                    H:       bid.Creative.Height,
                    Adomain: []string{bid.Campaign.Advertiser},
                },
            },
        })
    }
    
    return &BidResponse{
        ID:      req.ID,
        SeatBid: seatBids,
        Cur:     "CNY",
    }, nil
}
```

---

## 第三部分：出价策略

### 3.1 CPM / CPC / oCPM 对比

| 策略 | 付费方式 | 适用场景 | DSP 风险 |
|------|---------|---------|---------|
| **CPM** | 按千次曝光 | 品牌曝光 | 低 |
| **CPC** | 按点击 | 流量获取 | 中 |
| **oCPM** | 按转化出价 | 效果广告 | 高 |
| **oCPC** | 按转化出价 | 效果广告 | 高 |

### 3.2 oCPM 出价算法

```go
// oCPM 出价公式
// bid = pCTR * pCVR * targetCPA

func (be *BidEngine) CalculateOCPMBid(req *BidRequest, ad *Ad) float64 {
    // 1. 获取目标 CPA
    targetCPA := ad.Campaign.TargetCPA
    
    // 2. 获取 CTR 预估
    ctr := be.ctrModel.Predict(req)
    
    // 3. 获取 CVR 预估
    cvr := be.cvrModel.Predict(req, ad)
    
    // 4. 计算出价
    bid := ctr * cvr * targetCPA
    
    // 5. 应用出价上限/下限
    bid = math.Max(bid, ad.Campaign.MinBid)
    bid = math.Min(bid, ad.Campaign.MaxBid)
    
    return bid
}

// CTR 预估模型
type CTRModel struct {
    // LR 模型
    weights []float64
}

func (m *CTRModel) Predict(req *BidRequest) float64 {
    features := m.extractFeatures(req)
    logit := 0.0
    
    for i, f := range features {
        logit += f * m.weights[i]
    }
    
    // Sigmoid
    return 1.0 / (1.0 + math.Exp(-logit))
}

func (m *CTRModel) extractFeatures(req *BidRequest) []float64 {
    // 用户特征
    features := []float64{
        float64(req.User.Age) / 100,
        float64(req.Device.Gender),
        // ...
    }
    
    // 上下文特征
    features = append(features, []float64{
        float64(req.App.Category),
        float64(req.Device.Hour),
        float64(req.Device.Weekday),
        // ...
    }...)
    
    // 广告特征
    features = append(features, []float64{
        float64(req.Ad.Category),
        float64(req.Ad.Campaign.DaysRunning),
        // ...
    }...)
    
    return features
}

// CVR 预估模型
type CVRModel struct {
    // 深度学习模型
    model *tf.Model
}

func (m *CVRModel) Predict(req *BidRequest, ad *Ad) float64 {
    // 输入: 用户 + 广告 + 上下文
    input := m.buildInput(req, ad)
    
    // 预测 CVR
    cvr := m.model.Predict(input)
    
    // Clip 到 [0, 1]
    return math.Max(0, math.Min(1, cvr))
}

func (m *CVRModel) buildInput(req *BidRequest, ad *Ad) []float64 {
    // 用户向量
    userVec := m.userEncoder.Encode(req.User.ID)
    
    // 广告向量
    adVec := m.adEncoder.Encode(ad.ID)
    
    // 上下文向量
    ctxVec := m.ctxEncoder.Encode(req)
    
    // 拼接
    return append(append(userVec, adVec...), ctxVec...)
}
```

### 3.3 出价优化

```go
// 出价优化器
type BidOptimizer struct {
    bidHistory map[string]*BidHistory
    model      *PriceModel
}

type BidHistory struct {
    Impressions int     // 曝光次数
    Clicks      int     // 点击次数
    Conversions int     // 转化次数
    Spent       float64 // 总花费
    CPAs        []float64 // 历史 CPA
}

func (bo *BidOptimizer) OptimizeBid(req *BidRequest, ad *Ad) float64 {
    history := bo.getHistory(ad.CampaignID)
    
    if history == nil || history.Impressions < 100 {
        // 冷启动：使用基础出价
        return bo.calculateBaseBid(req, ad)
    }
    
    // 计算历史 CPA
    avgCPA := history.Spent / float64(history.Conversions)
    targetCPA := ad.Campaign.TargetCPA
    
    if history.Conversions == 0 {
        // 无转化：保守出价
        return avgCPA * 0.5
    }
    
    // 根据转化率调整出价
    conversionRate := float64(history.Conversions) / float64(history.Clicks)
    targetCTR := float64(history.Clicks) / float64(history.Impressions)
    
    // 出价调整因子
    adjustmentFactor := 1.0
    if conversionRate < targetCTR*0.1 {
        adjustmentFactor = 0.7 // 降低出价
    } else if conversionRate > targetCTR*0.3 {
        adjustmentFactor = 1.3 // 提高出价
    }
    
    bid := req.TargetCPA * targetCTR * conversionRate
    bid *= adjustmentFactor
    
    // 应用出价限制
    bid = math.Max(bid, ad.Campaign.MinBid)
    bid = math.Min(bid, ad.Campaign.MaxBid)
    
    return bid
}
```

---

## 第四部分：竞价引擎性能优化

### 4.1 超低延迟优化

```go
// 竞价引擎 - 追求 < 50ms 延迟
type OptimizedBidEngine struct {
    // 内存缓存 - 避免 Redis 网络 IO
    userProfiles map[string]*UserProfile
    adCreative   map[string]*AdCreative
    
    // 并行竞价
    workerPool *sync.Pool
    
    // 预计算 CTR/CVR
    ctrIndex     map[string]float64
    cvrIndex     map[string]float64
}

func (be *OptimizedBidEngine) Bid(req *BidRequest) (*BidResponse, error) {
    // 1. 并行查询用户画像和广告库存
    type result struct {
        profile *UserProfile
        ads     []*Ad
        err     error
    }
    
    ch := make(chan result, 2)
    
    go func() {
        profile, err := be.getUserProfile(req.User.ID)
        ch <- result{profile: profile, err: err}
    }()
    
    go func() {
        ads, err := be.getAds(req.Imp[0].AdSlotID)
        ch <- result{ads: ads, err: err}
    }()
    
    // 2. 等待结果
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
    
    // 3. 快速出价
    bestBid := be.calculateBestBid(req, profile, ads)
    
    return &BidResponse{
        // ...
    }, nil
}

// 批量竞价 - 减少网络往返
func (be *OptimizedBidEngine) BatchBid(reqs []*BidRequest) ([]*BidResponse, error) {
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
            // ...
        }
    }
    
    return responses, nil
}
```

### 4.2 内存优化

```go
// 使用对象池减少 GC 压力
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

// 使用 byte slice 替代 string 减少内存分配
func encodeRequest(req *BidRequest) []byte {
    // 预分配 buffer
    buf := make([]byte, 0, 1024)
    
    // 序列化到 buffer
    buf = append(buf, []byte(`{"id":"`)...)
    buf = append(buf, []byte(req.ID)...)
    buf = append(buf, []byte(`","imp":`)...)
    // ...
    
    return buf
}
```

---

## 第五部分：自测题

### 问题 1
oCPM 相比 CPM/CPC 有什么优势？

<details>
<summary>查看答案</summary>

1. **目标 CPA**：以转化为目标出价
2. **自动出价**：根据 CTR/CVR 自动调整
3. **ROI 更高**：避免无效曝光
4. **算法复杂**：需要精准的 CTR/CVR 预估
5. **DSP 风险高**：需要精准模型

</details>

### 问题 2
竞价引擎如何优化到 < 50ms？

<details>
<summary>查看答案</summary>

1. **并行查询**：用户画像 + 广告库存并行
2. **内存缓存**：避免 Redis 网络 IO
3. **批量处理**：减少网络往返
4. **预计算**：CTR/CVR 预计算
5. **对象池**：减少 GC 压力

</details>

### 问题 3
OpenRTB Bid Request 中必填字段有哪些？

<details>
<summary>查看答案</summary>

1. **id**: 请求唯一 ID
2. **imp**: 广告位数组（不能为空）
3. **imp[].id**: 广告位 ID
4. **扩展字段**: site 或 app（二选一）
5. **可选**: device, user

</details>

---

*本文档基于广告竞价原理整理。*