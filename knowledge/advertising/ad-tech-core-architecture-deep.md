# 广告系统架构深度解析

> 深入广告系统核心架构：AdServer、SSP、ADX、数据流设计。
> 包含真实生产环境广告系统架构设计。
> 适用对象：广告系统架构师、后端工程师

---

## 1. 广告系统架构

### 1.1 整体架构

```
广告系统整体架构：

┌─────────────────────────────────────────────────────────────┐
│                    广告系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  广告主侧 (Advertiser)                                       │
│  ├── 广告投放平台 (DSP)                                      │
│  ├── 创意管理                                                │
│  └── 效果分析                                                │
│                                                             │
│  媒体侧 (Publisher)                                          │
│  ├── 广告位管理 (SSP)                                        │
│  ├── 广告填充                                                │
│  └── 收入分析                                                │
│                                                             │
│  交易平台 (ADX)                                              │
│  ├── 竞价撮合                                                │
│  ├── 实时计费                                                │
│  └── 数据回流                                                │
│                                                             │
│  服务端 (AdServer)                                           │
│  ├── 广告请求处理                                            │
│  ├── 广告选择排序                                            │
│  ├── 频控限流                                                │
│  └── 数据统计                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现广告系统核心

```go
// ad_system.go

package ad

import (
    "context"
    "sync"
    "time"
)

type AdSystem struct {
    adServer     *AdServer
    dsp          map[string]*DSP
    ssp          map[string]*SSP
    metrics      *MetricsCollector
    mu           sync.RWMutex
}

type AdRequest struct {
    RequestID  string
    User       UserContext
    Site       SiteContext
    AdSlot     AdSlotContext
    Timestamp  int64
}

type AdResponse struct {
    RequestID  string
    Ads        []AdCreative
    BidPrice   float64
    TraceID    string
    Latency    time.Duration
}

type AdServer struct {
    config     *Config
    selector   *AdSelector
    frequency  *FrequencyController
    tracker    *EventTracker
}

type Config struct {
    MaxAdsPerRequest  int
    DefaultTTL        time.Duration
    FrequencyCap      int
    Timeout           time.Duration
}

func NewAdSystem(config *Config) *AdSystem {
    return &AdSystem{
        adServer: &AdServer{
            config:   config,
            selector: NewAdSelector(),
            frequency: NewFrequencyController(config.FrequencyCap),
            tracker:  NewEventTracker(),
        },
        dsp:   make(map[string]*DSP),
        ssp:   make(map[string]*SSP),
        metrics: NewMetricsCollector(),
    }
}

func (ads *AdSystem) HandleAdRequest(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    start := time.Now()
    
    // 1. 频控检查
    if !ads.adServer.frequency.Allow(req.User.UserID, req.AdSlot.SlotID) {
        return &AdResponse{
            RequestID: req.RequestID,
            Latency:   time.Since(start),
        }, nil
    }
    
    // 2. 广告选择
    ads, bidPrice, err := ads.adServer.selector.Select(ctx, req)
    if err != nil || len(ads) == 0 {
        return &AdResponse{
            RequestID: req.RequestID,
            Latency:   time.Since(start),
        }, err
    }
    
    // 3. 记录事件
    ads.adServer.tracker.TrackImpression(req.RequestID, req.User.UserID, ads[0].ID)
    
    // 4. 更新指标
    ads.metrics.RecordRequest(time.Since(start))
    
    return &AdResponse{
        RequestID: req.RequestID,
        Ads:       ads,
        BidPrice:  bidPrice,
        Latency:   time.Since(start),
    }, nil
}
```

---

## 2. AdServer 核心

### 2.1 架构设计

```
AdServer 核心组件：

├── 请求处理层
│   ├── 请求解析
│   ├── 参数校验
│   └── 限流控制
│
├── 广告选择层
│   ├── 召回
│   ├── 排序
│   └── 重排序
│
├── 频控层
│   ├── 用户级频控
│   ├── 创意级频控
│   └── 时段频控
│
└── 数据层
    ├── 广告库存
    ├── 用户画像
    └── 转化数据
```

### 2.2 Go 实现广告选择

```go
// ad_selector.go

package ad

import (
    "context"
    "sort"
)

type AdSelector struct {
    recall    *RecallEngine
    ranker    *Ranker
    reranker  *Reranker
}

func NewAdSelector() *AdSelector {
    return &AdSelector{
        recall:   NewRecallEngine(),
        ranker:   NewRanker(),
        reranker: NewReranker(),
    }
}

func (as *AdSelector) Select(ctx context.Context, req *AdRequest) ([]AdCreative, float64, error) {
    // 1. 召回
    candidates := as.recall.Recall(ctx, req)
    
    // 2. 排序
    scored := as.ranker.Rank(ctx, candidates, req)
    
    // 3. 重排序
    final := as.reranker.Rerank(scored, req)
    
    // 4. 计算底价
    bidPrice := as.calculateBidPrice(final)
    
    return final, bidPrice, nil
}

type RecallEngine struct {
    pools map[string]*AdPool
}

func NewRecallEngine() *RecallEngine {
    return &RecallEngine{
        pools: make(map[string]*AdPool),
    }
}

func (re *RecallEngine) Recall(ctx context.Context, req *AdRequest) []AdCreative {
    var candidates []AdCreative
    
    // 规则召回
    ruleAds := re.ruleRecall(req)
    candidates = append(candidates, ruleAds...)
    
    // 协同召回
    collabAds := re.collaborativeRecall(req)
    candidates = append(candidates, collabAds...)
    
    // 热门召回
    hotAds := re.hotRecall(req)
    candidates = append(candidates, hotAds...)
    
    return candidates
}
```

---

## 3. SSP 系统

### 3.1 架构设计

```
SSP (Supply Side Platform) 架构：

├── 广告位管理
│   ├── 广告位注册
│   ├── 广告位配置
│   └── 广告位监控
│
├── 请求处理
│   ├── 请求接收
│   ├── 底价设置
│   └── 请求转发
│
└── 收益优化
    ├── 底价优化
    ├── 填充率监控
    └── 收益分析
```

### 3.2 Go 实现 SSP

```go
// ssp.go

package ad

import (
    "context"
    "sync"
)

type SSP struct {
    id           string
    sites        map[string]*Site
    adExchanges  map[string]*ADX
    floorPrice   float64
    mu           sync.RWMutex
}

type Site struct {
    ID      string
    Domain  string
    Apps    []string
    Settings SiteSettings
}

type SiteSettings struct {
    FloorPrice    float64
    MaxAds        int
    AllowedAdTypes []string
}

type ADX struct {
    ID   string
    URL  string
    Auth string
}

func NewSSP(id string, floorPrice float64) *SSP {
    return &SSP{
        id:         id,
        sites:      make(map[string]*Site),
        adExchanges: make(map[string]*ADX),
        floorPrice: floorPrice,
    }
}

func (ssp *SSP) AddSite(site *Site) {
    ssp.mu.Lock()
    defer ssp.mu.Unlock()
    ssp.sites[site.ID] = site
}

func (ssp *SSP) AddADX(adx *ADX) {
    ssp.mu.Lock()
    defer ssp.mu.Unlock()
    ssp.adExchanges[adx.ID] = adx
}

func (ssp *SSP) ProcessRequest(ctx context.Context, req *SSPRequest) *SSPResponse {
    ssp.mu.RLock()
    defer ssp.mu.RUnlock()
    
    site := ssp.sites[req.SiteID]
    if site == nil {
        return &SSPResponse{Success: false, Error: "site not found"}
    }
    
    // 转发到ADX
    for _, adx := range ssp.adExchanges {
        resp := ssp.forwardToADX(ctx, adx, req, site.Settings.FloorPrice)
        if resp != nil && len(resp.Ads) > 0 {
            return resp
        }
    }
    
    return &SSPResponse{Success: true, Ads: []AdCreative{}}
}
```

---

## 4. ADX 交易平台

### 4.1 核心流程

```
ADX 交易流程：

1. 接收 SSP 请求
   └── 验证广告位

2. 广播竞价请求
   └── 发送给所有 DSP

3. 收集竞价响应
   └── 等待超时

4. 竞价决策
   └── 最高价中标

5. 返回广告
   └── 返回给 SSP
```

### 4.2 Go 实现 ADX

```go
// adx.go

package ad

import (
    "context"
    "sync"
    "time"
)

type ADX struct {
    id        string
    dspMap    map[string]*DSPClient
    timeout   time.Duration
    mu        sync.Mutex
}

type DSPClient struct {
    id     string
    url    string
    client *http.Client
}

type ADXRequest struct {
    ImpressionID string
    AdSlot       AdSlotInfo
    User         UserInfo
    FloorPrice   float64
}

type ADXResponse struct {
    ImpressionID string
    WinnerDSP    string
    WinPrice     float64
    Creative     AdCreative
}

func NewADX(id string, timeout time.Duration) *ADX {
    return &ADX{
        id:      id,
        timeout: timeout,
        dspMap:  make(map[string]*DSPClient),
    }
}

func (adx *ADX) RegisterDSP(dsp *DSPClient) {
    adx.mu.Lock()
    defer adx.mu.Unlock()
    adx.dspMap[dsp.id] = dsp
}

func (adx *ADX) RunAuction(ctx context.Context, req *ADXRequest) (*ADXResponse, error) {
    adx.mu.RLock()
    dspClients := make([]*DSPClient, 0, len(adx.dspMap))
    for _, dsp := range adx.dspMap {
        dspClients = append(dspClients, dsp)
    }
    adx.mu.RUnlock()
    
    // 并发请求所有DSP
    type bidResult struct {
        dspID string
        bid   float64
        cre   AdCreative
    }
    
    resultCh := make(chan bidResult, len(dspClients))
    var wg sync.WaitGroup
    
    for _, dsp := range dspClients {
        wg.Add(1)
        go func(d *DSPClient) {
            defer wg.Done()
            bid := d.SendBid(ctx, req)
            if bid.Price >= req.FloorPrice {
                resultCh <- bidResult{
                    dspID: d.id,
                    bid:   bid.Price,
                    cre:   bid.Creative,
                }
            }
        }(dsp)
    }
    
    go func() {
        wg.Wait()
        close(resultCh)
    }()
    
    // 选择最高价
    var winner bidResult
    maxBid := 0.0
    for r := range resultCh {
        if r.bid > maxBid {
            maxBid = r.bid
            winner = r
        }
    }
    
    return &ADXResponse{
        ImpressionID: req.ImpressionID,
        WinnerDSP:    winner.dspID,
        WinPrice:     winner.bid,
        Creative:     winner.cre,
    }, nil
}
```

---

## 5. 总结

### 5.1 核心组件回顾

| 组件 | 职责 |
|------|------|
| AdServer | 广告请求处理、选择排序 |
| SSP | 媒体侧广告位管理、收益优化 |
| ADX | 交易平台、竞价撮合 |
| DSP | 广告主侧出价策略 |

### 5.2 最佳实践

- [ ] 合理设计频控策略
- [ ] 优化广告选择算法
- [ ] 建立实时监控体系
- [ ] 持续优化收益指标

---

*最后更新：2026-08-11*
*作者：Ryan*
