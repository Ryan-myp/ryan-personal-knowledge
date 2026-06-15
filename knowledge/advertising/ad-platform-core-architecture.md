# 广告平台核心架构：DSP/SSP/Ad Exchange

> 实时竞价 RTB / VBP / 频次控制 / 创意管理 / 归因建模 / 反作弊系统

---

## 第一部分：入门引导（5 分钟速览）

### 广告生态核心角色

```
用户 → 网站/App → SSP → Ad Exchange → DSP → 广告主
                              ↕
                         数据平台 (DMP/CDP)
```

| 角色 | 职责 | 代表平台 |
|------|------|---------|
| **DSP** | 需求方平台，买流量 | The Trade Desk, 巨量引擎 |
| **SSP** | 供应方平台，卖库存 | Google Ad Manager, 穿山甲 |
| **Ad Exchange** | 广告交易平台，撮合 | Google AdX, AppNexus |
| **DMP** | 数据管理平台，用户画像 | CDX, DMP 自研 |

### 实时竞价流程

```
1. 用户访问 App → SSP 收到曝光请求
2. SSP 向 Ad Exchange 发起 auction
3. Ad Exchange 转发给各 DSP
4. DSP 实时计算出价（基于用户画像、上下文、历史数据）
5. Ad Exchange 收集出价，选择最高价广告
6. 广告展示，DSP 记录曝光/点击/转化
```

---

## 第二部分：DSP 核心架构

### 2.1 竞价引擎

```go
package dsp

import (
    "context"
)

type BidEngine struct {
    userProfiler *UserProfiler
    ctrModel     *CTRModel
    cvrModel     *CVRModel
    budgetMgr    *BudgetManager
    freqCap      *FrequencyCap
}

type BidRequest struct {
    RequestID string    `json:"id"`
    Impression Impression `json:"imp"`
    User       User       `json:"user"`
    Device     Device     `json:"device"`
    App        App        `json:"app"`
}

type BidResponse struct {
    RequestID string  `json:"id"`
    BidPrice  float64 `json:"price"`
    AdID      string  `json:"adId"`
    Targeting map[string]string `json:"targeting"`
}

func (be *BidEngine) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 频次控制检查
    if be.freqCap.IsExceeded(req.User.ID, req.Impression.AdSlotID) {
        return nil, nil // 不出价
    }
    
    // 2. 预算检查
    if !be.budgetMgr.HasBudget(req.Impression.CampaignID) {
        return nil, nil
    }
    
    // 3. 预测 CTR/CVR
    ctr := be.ctrModel.Predict(req)
    cvr := be.cvrModel.Predict(req)
    
    // 4. 计算出价（基于 eCPM 最大化）
    targetCPA := be.getTargetCPA(req.Impression.CampaignID)
    bidPrice := ctr * cvr * targetCPA
    
    // 5. 应用出价上限/下限
    bidPrice = be.applyBidFloorCeiling(bidPrice, req.Impression)
    
    // 6. 返回竞价响应
    ad := be.selectAd(req.Impression.CampaignID, bidPrice)
    
    return &BidResponse{
        RequestID: req.RequestID,
        BidPrice:  bidPrice,
        AdID:      ad.ID,
        Targeting: ad.Targeting,
    }, nil
}
```

### 2.2 CTR/CVR 预估模型

```go
type CTRModel struct {
    // 特征工程
    features []Feature
    // 模型参数（可以是简单的加权求和，也可以是深度学习模型）
    weights []float64
}

type Feature struct {
    Name  string
    Value float64
}

func (m *CTRModel) Predict(req *BidRequest) float64 {
    // 提取特征
    features := m.extractFeatures(req)
    
    // 计算 CTR（简化版加权求和）
    ctr := 0.0
    for i, f := range features {
        ctr += f.Value * m.weights[i]
    }
    
    // Sigmoid 映射到 [0, 1]
    return 1.0 / (1.0 + math.Exp(-ctr))
}

func (m *CTRModel) extractFeatures(req *BidRequest) []Feature {
    features := []Feature{
        {Name: "user_age", Value: float64(req.User.Age)},
        {Name: "user_gender", Value: req.User.Gender},
        {Name: "location", Value: encodeLocation(req.User.Location)},
        {Name: "ad_category", Value: encodeCategory(req.Impression.AdCategory)},
        {Name: "time_of_day", Value: float64(req.Device.Time.Hour())},
        {Name: "device_type", Value: encodeDeviceType(req.Device.Type)},
        // 更多特征...
    }
    return features
}
```

### 2.3 预算管理

```go
type BudgetManager struct {
    dailyBudgets map[string]float64  // campaign_id → 日预算
    spentToday   map[string]float64  // campaign_id → 今日已花费
    hourlyBudgets map[string]float64 // campaign_id → 小时预算
    spentHourly   map[string]float64 // campaign_id → 小时已花费
}

func (bm *BudgetManager) HasBudget(campaignID string) bool {
    budget, ok := bm.dailyBudgets[campaignID]
    if !ok {
        return false
    }
    
    spent := bm.spentToday[campaignID]
    return spent < budget
}

func (bm *BudgetManager) Deduct(campaignID string, amount float64) error {
    if !bm.HasBudget(campaignID) {
        return fmt.Errorf("budget exhausted")
    }
    
    bm.spentToday[campaignID] += amount
    
    // 检查小时预算
    hourlyBudget, ok := bm.hourlyBudgets[campaignID]
    if ok && bm.spentHourly[campaignID]+amount > hourlyBudget {
        return fmt.Errorf("hourly budget exceeded")
    }
    
    return nil
}

// 使用 Redis 实现分布式预算扣减
func (bm *BudgetManager) DeductWithRedis(campaignID string, amount float64, redis *redis.Client) error {
    key := fmt.Sprintf("budget:%s:today", campaignID)
    
    // Lua 脚本保证原子性
    script := `
        local budget = redis.call('GET', KEYS[1] .. ':limit')
        if not budget then return -1 end
        local spent = redis.call('GET', KEYS[1]) or '0'
        if tonumber(spent) + tonumber(ARGV[1]) > tonumber(budget) then
            return 0
        end
        redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
        return 1
    `
    
    result, err := redis.Eval(context.Background(), script, []string{key}, amount).Int64()
    if err != nil || result == 0 {
        return fmt.Errorf("budget exceeded")
    }
    return nil
}
```

---

## 第三部分：SSP 核心架构

### 3.1 库存管理

```go
type SSP struct {
    adManager *AdManager
    bidder    *Bidder
    freqCap   *FrequencyCap
}

type AdRequest struct {
    RequestID string    `json:"id"`
    Publisher  Publisher `json:"publisher"`
    Impression Impression `json:"imp"`
    User       User      `json:"user"`
}

type AdResponse struct {
    RequestID string  `json:"id"`
    Ad        []Ad    `json:"ad"`
    Price     float64 `json:"price"`
}

func (ssp *SSP) HandleAdRequest(req *AdRequest) (*AdResponse, error) {
    // 1. 检查频次控制
    if ssp.freqCap.IsExceeded(req.User.ID, req.Impression.AdSlotID) {
        return &AdResponse{RequestID: req.RequestID}, nil
    }
    
    // 2. 发起竞价请求到 Ad Exchange
    bidReq := &BidRequest{
        RequestID: req.RequestID,
        Impression: req.Impression,
        User:       req.User,
        Device:     req.Impression.Device,
    }
    
    // 3. 获取竞价结果
    responses, err := ssp.bidder.Bid(bidReq)
    if err != nil || len(responses) == 0 {
        return &AdResponse{RequestID: req.RequestID}, nil
    }
    
    // 4. 选择最优广告（最高出价）
    best := responses[0]
    for _, r := range responses[1:] {
        if r.BidPrice > best.BidPrice {
            best = r
        }
    }
    
    // 5. 返回广告响应
    return &AdResponse{
        RequestID: req.RequestID,
        Price:     best.BidPrice,
        Ad:        []Ad{{ID: best.AdID}},
    }, nil
}
```

### 3.2 底价管理

```go
type FloorPriceManager struct {
    staticFloors map[string]float64  // ad_slot_id → 底价
    dynamicFloors *DynamicFloor       // 动态底价
}

type DynamicFloor struct {
    model *PriceModel
}

func (fm *FloorPriceManager) GetFloor(adSlotID string, bid float64) float64 {
    // 1. 获取静态底价
    staticFloor, ok := fm.staticFloors[adSlotID]
    if !ok {
        return 0
    }
    
    // 2. 获取动态底价
    dynamicFloor := fm.dynamicFloors.Calculate(adSlotID, bid)
    
    // 3. 取较大值
    if dynamicFloor > staticFloor {
        return dynamicFloor
    }
    return staticFloor
}
```

---

## 第四部分：Ad Exchange 核心架构

### 4.1 竞价撮合

```go
type AdExchange struct {
    dssp []string  // 连接的 DSP 列表
    ssp  []string  // 连接的 SSP 列表
    auctionEngine *AuctionEngine
}

type AuctionEngine struct {
    priceType string // first_price, second_price
}

// 第二价格竞价（VBP）
func (ae *AuctionEngine) SecondPriceAuction(bids []Bid) *WinResult {
    if len(bids) == 0 {
        return nil
    }
    
    // 排序
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].Price > bids[j].Price
    })
    
    winner := bids[0]
    secondPrice := 0.0
    if len(bids) > 1 {
        secondPrice = bids[1].Price
    }
    
    // 应用底价
    price := math.Max(winner.Price, secondPrice)
    
    return &WinResult{
        Winner: winner.DSP,
        Price:  price,
    }
}

// 第一价格竞价（FPB）
func (ae *AuctionEngine) FirstPriceAuction(bids []Bid) *WinResult {
    if len(bids) == 0 {
        return nil
    }
    
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].Price > bids[j].Price
    })
    
    return &WinResult{
        Winner: bids[0].DSP,
        Price:  bids[0].Price,
    }
}
```

### 4.2 高并发竞价引擎

```go
type ConcurrentBidEngine struct {
    workerPool *WorkerPool
    dspClients []*DSPClient
}

func (be *ConcurrentBidEngine) Bid(req *BidRequest) ([]*BidResponse, error) {
    results := make(chan *BidResponse, len(be.dspClients))
    errors := make(chan error, len(be.dspClients))
    
    // 并行向各 DSP 发起竞价请求
    for _, client := range be.dspClients {
        go func(c *DSPClient) {
            resp, err := c.Bid(req)
            if err != nil {
                errors <- err
                return
            }
            results <- resp
        }(client)
    }
    
    // 收集结果
    responses := make([]*BidResponse, 0)
    for i := 0; i < len(be.dspClients); i++ {
        select {
        case resp := <-results:
            responses = append(responses, resp)
        case err := <-errors:
            log.Printf("bid error: %v", err)
        }
    }
    
    return responses, nil
}
```

---

## 第五部分：频次控制与创意管理

### 5.1 频次控制

```go
type FrequencyCap struct {
    redis *redis.Client
}

// 检查用户是否超出频次限制
func (fc *FrequencyCap) IsExceeded(userID, adSlotID string, maxImpressions int) bool {
    key := fmt.Sprintf("freq:%s:%s", userID, adSlotID)
    
    // 检查过去 24 小时内的展示次数
    count, err := fc.redis.ZCard(context.Background(), key).Result()
    if err != nil {
        return false // 出错时放行
    }
    
    return int(count) >= maxImpressions
}

// 记录展示
func (fc *FrequencyCap) RecordImpression(userID, adSlotID string) {
    key := fmt.Sprintf("freq:%s:%s", userID, adSlotID)
    now := time.Now().Unix()
    
    // 使用 ZADD 添加时间戳
    fc.redis.ZAdd(context.Background(), key, redis.Z{
        Score:  float64(now),
        Member: fmt.Sprintf("%d", now),
    })
    
    // 过期时间 24 小时
    fc.redis.Expire(context.Background(), key, 24*time.Hour)
}

// 创意管理
type CreativeManager struct {
    pool []*Creative
}

type Creative struct {
    ID        string
    CampaignID string
    Type      string // banner, video, native
    URL       string
    Width     int
    Height    int
    HTML      string
}

func (cm *CreativeManager) GetCreative(campaignID, adSlotID string) *Creative {
    // 根据广告位尺寸筛选创意
    for _, c := range cm.pool {
        if c.CampaignID == campaignID && c.Width > 0 && c.Height > 0 {
            // 检查尺寸匹配
            if cm.isSizeMatch(c, adSlotID) {
                return c
            }
        }
    }
    return nil
}
```

---

## 第六部分：自测题

### 问题 1
DSP 竞价时为什么需要 CTR/CVR 预估？

<details>
<summary>查看答案</summary>

1. **出价依据**：bid = CTR × CVR × target CPA
2. **ROI 最大化**：只出高转化概率的广告
3. **特征工程**：用户画像 + 上下文特征
4. **实时性**：必须在 100ms 内完成预估
5. **模型选择**：LR/GBDT/深度学习

</details>

### 问题 2
第一价格竞价（FPB）vs 第二价格竞价（VBP）的区别？

<details>
<summary>查看答案</summary>

1. **FPB**：最高价获胜，按自己出价付费
2. **VBP**：最高价获胜，按第二高出价付费
3. **策略差异**：FPB 需要猜测对手出价，VBP 可如实出价
4. **收入差异**：FPB 平台收入更高，VBP 对广告主更友好
5. **趋势**：越来越多平台转向 FPB

</details>

### 问题 3
频次控制如何实现才高效？

<details>
<summary>查看答案</summary>

1. **Redis ZSet**：使用时间戳作为 score
2. **过期策略**：24 小时自动过期
3. **分布式**：Redis 集群保证高可用
4. **降级方案**：本地缓存 + Redis 兜底
5. **Go 实现**：使用 redis ZADD/ZREMRANGEBYSCORE

</details>

---

*本文档基于广告平台架构原理整理。*