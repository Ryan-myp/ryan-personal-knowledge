# SSP 深入解析 — Supply Side Platform

> 本文档深入解析 SSP（Supply Side Platform）的架构设计、核心算法、工程实现和实战经验。
> 适用对象：广告系统架构师、后端工程师、算法工程师

---

## 1. SSP 概述

### 1.1 什么是 SSP

SSP（Supply Side Platform）是**媒体侧**的 Ad Tech 平台，帮助 publishers（媒体/发布商）最大化广告收入。

```
┌─────────────────────────────────────────────────────────────┐
│                        Publisher                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Website │  │  Mobile  │  │  App     │  │  TV/CTV  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│       └─────────────┴─────────────┴─────────────┘           │
│                          │                                  │
│                    ┌─────▼─────┐                            │
│                    │   SSP    │ ◄── 媒体接入 SDK/API        │
│                    │Platform  │                            │
│                    └─────┬─────┘                            │
└──────────────────────────┼──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐    ┌─────▼─────┐
    │  DSP 1  │      │  DSP 2    │    │  DSP N    │
    │ (Google)│      │(Programic)│    │ (Custom)  │
    └─────────┘      └───────────┘    └───────────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │    RTB     │
                    │  Exchange   │
                    └─────────────┘
```

### 1.2 核心价值

| 价值点 | 说明 |
|--------|------|
| **收入最大化** | 多路竞价，选择最高出价 |
| **流量管理** | 频次控制、库存管理、优先级调度 |
| **反作弊** | 检测虚假流量、bot 请求 |
| **数据分析** | 收入报表、fill rate、eCPM 趋势 |
| **合规保障** | GDPR/CCPA 合规、品牌安全 |

### 1.3 与 DSP/ADX 的区别

| 平台 | 服务方 | 核心目标 |
|------|--------|----------|
| **DSP** | 广告主侧 | 以最低成本获取转化 |
| **SSP** | 媒体侧 | 以最高价格卖出库存 |
| **ADX** | 交易所 | 连接买卖双方的撮合层 |

---

## 2. 核心架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SSP 架构                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  SDK/Tag     │    │  Server-Side │    │  Mobile SDK  │          │
│  │  (Web)       │    │  Header Bidding│   │  (iOS/Android)│         │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│                    ┌────────▼────────┐                             │
│                    │   Gateway/API   │                             │
│                    │  (Kong/Traefik) │                             │
│                    └────────┬────────┘                             │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                  │
│         │                   │                   │                  │
│  ┌──────▼──────┐   ┌────────▼────────┐  ┌──────▼──────┐           │
│  │  Bid Request│   │  Inventory      │  │  Analytics  │           │
│  │  Handler    │   │  Manager        │  │  Engine     │           │
│  └──────┬──────┘   └────────┬────────┘  └─────────────┘           │
│         │                   │                                       │
│         │            ┌──────▼──────┐                             │
│         │            │  Frequency  │                             │
│         │            │  Capping    │                             │
│         │            │  Floor Price│                             │
│         │            └──────┬──────┘                             │
│         │                   │                                       │
│         └───────────────────┼───────────────────┐                  │
│                             │                   │                  │
│                    ┌────────▼────────┐  ┌──────▼──────┐           │
│                    │  Bidder Proxy   │  │  Waterfall  │           │
│                    │  (多路竞价)      │  │  Manager    │           │
│                    └────────┬────────┘  └──────┬──────┘           │
│                             │                 │                   │
│              ┌──────────────┼─────────────────┤                   │
│              │              │                 │                   │
│     ┌────────▼────────┐ ┌──▼────────┐  ┌─────▼─────┐            │
│     │  DSP Adapters   │ │ Premium   │  │  Direct   │            │
│     │  (标准化接口)    │ │ Deals     │  │  Deals    │            │
│     └────────┬────────┘ └───────────┘  └───────────┘            │
│              │                                                   │
│              └──────────────────┬────────────────────────────────┘
│                                 │
│                        ┌────────▼────────┐
│                        │   Bid Response  │
│                        │   Handler       │
│                        └────────┬────────┘
│                                 │
│                    ┌────────────▼────────────┐
│                    │   Win Notice / Postback │
│                    └─────────────────────────┘
│
├─────────────────────────────────────────────────────────────────────┤
│  数据存储层                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │  Redis   │ │  Kafka   │ │  Click-  │ │  MySQL   │             │
│  │ (频控/缓存)│ │ (事件流) │ │  stream  │ │ (元数据) │             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块说明

| 模块 | 职责 | 关键技术点 |
|------|------|-----------|
| **Gateway** | 请求接入、限流、鉴权 | Kong/Traefik、JWT、WAF |
| **Bid Request Handler** | 构建 bid request、签名 | OpenRTB 协议、加密签名 |
| **Inventory Manager** | 库存管理、floor price、频控 | Redis、一致性哈希 |
| **Bidder Proxy** | 向多个 DSP 发送请求、聚合响应 | 并发 HTTP、超时控制 |
| **Waterfall Manager** | 传统瀑布流管理 | 优先级队列、阶梯降价 |
| **Analytics Engine** | 数据采集、实时计算 | Kafka、Flink、ClickHouse |
| **Anti-Fraud** | 欺诈检测、黑名单 | 规则引擎、ML 模型 |

---

## 3. 核心算法

### 3.1 竞价策略

#### 3.1.1 First-Price vs Second-Price

```go
// First-Price: 最高出价者以自己的出价成交
func FirstPriceAuction(bids []Bid) Bid {
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].Price > bids[j].Price
    })
    return bids[0]
}

// Second-Price: 最高出价者以第二高出价成交（VCG 变种）
func SecondPriceAuction(bids []Bid) Bid {
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].Price > bids[j].Price
    })
    if len(bids) > 1 {
        return bids[1] // 返回第二高出价
    }
    return bids[0]
}
```

**对比**：
| 特性 | First-Price | Second-Price |
|------|-------------|--------------|
| 出价策略 | 需猜测对手出价 | 可直报真实价值 |
| 收入稳定性 | 高（广告主愿付溢价） | 低（易被压价） |
| 市场趋势 | 当前主流（RTB 标准） | 逐渐淘汰 |

#### 3.1.2 Floor Price 策略

```go
type FloorPriceManager struct {
    redis *redis.Client
}

// 获取 floor price：优先用动态 floor，降级到静态 floor
func (m *FloorPriceManager) GetFloor(ctx context.Context, slot Slot) (float64, error) {
    // 1. 检查动态 floor（基于历史 eCPM）
    key := fmt.Sprintf("floor:dynamic:%s:%s", slot.AdUnitID, slot.Country)
    dynamicFloor, err := m.redis.Get(ctx, key).Float64()
    if err == nil && dynamicFloor > 0 {
        return dynamicFloor, nil
    }
    
    // 2. 降级到静态 floor
    staticFloor := m.getStaticFloor(slot)
    return staticFloor, nil
}

// 动态 floor：基于过去 24h 的 p25 eCPM
func (m *FloorPriceManager) UpdateDynamicFloor(slot Slot, eCPMs []float64) {
    // 计算 p25 分位数作为 floor
    sort.Float64s(eCPMs)
    idx := int(float64(len(eCPMs)) * 0.25)
    if idx >= len(eCPMs) {
        idx = len(eCPMs) - 1
    }
    
    key := fmt.Sprintf("floor:dynamic:%s:%s", slot.AdUnitID, slot.Country)
    m.redis.Set(context.Background(), key, eCPMs[idx], 24*time.Hour)
}
```

### 3.2 频次控制（Frequency Capping）

```go
type FrequencyController struct {
    redis *redis.Client
}

// 检查是否超过频次限制
func (c *FrequencyController) Check(ctx context.Context, req BidRequest) (int, error) {
    // 多维度计数：用户 ID + 广告主 ID + 创意 ID + 时间窗口
    window := req.Cap.Window // 如 24h
    limit := req.Cap.Limit  // 如 5 次
    
    keys := []string{
        fmt.Sprintf("freq:u:%s:a:%s", req.UserID, req.AdvertiserID),
        fmt.Sprintf("freq:u:%s:c:%s", req.UserID, req.CreativeID),
        fmt.Sprintf("freq:i:%s", req.ImpressionID),
    }
    
    // 使用 Redis 滑动窗口
    pipe := c.redis.Pipeline()
    for _, key := range keys {
        pipe.Expire(ctx, key, window)
    }
    pipe.Exec(ctx)
    
    counts, _ := c.redis.MGet(ctx, keys...).Int64s()
    maxCount := int64(0)
    for _, count := range counts {
        if count > maxCount {
            maxCount = count
        }
    }
    
    return int(maxCount), nil
}
```

### 3.3 收入优化算法

#### 3.3.1 多路竞价聚合

```go
// 多路竞价：同时向多个 DSP 发送请求，选择最优响应
func (h *BidHandler) HandleBid(ctx context.Context, req BidRequest) (*BidResponse, error) {
    // 1. 检查频次
    count, _ := h.freqCtrl.Check(ctx, req)
    if count >= req.Cap.Limit {
        return nil, ErrFrequencyCap
    }
    
    // 2. 获取 floor price
    floor, _ := h.floorMgr.GetFloor(ctx, req.Slot)
    
    // 3. 并发请求多个 DSP
    type bidResult struct {
        bidder string
        resp   *openrtb.Bid
        err    error
    }
    
    resultCh := make(chan bidResult, len(req.Bidders))
    
    for _, bidder := range req.Bidders {
        go func(b string) {
            resp, err := h.callBidder(ctx, b, req)
            resultCh <- bidResult{bidder: b, resp: resp, err: err}
        }(bidder.ID)
    }
    
    // 4. 收集响应，选择最优
    var wins []Bid
    for i := 0; i < len(req.Bidders); i++ {
        select {
        case result := <-resultCh:
            if result.err != nil {
                continue
            }
            if result.resp.Price < floor {
                continue // 低于 floor，丢弃
            }
            wins = append(wins, result.resp)
        case <-time.After(200 * time.Millisecond):
            // 超时放弃
        }
    }
    
    if len(wins) == 0 {
        return nil, ErrNoWinningBid
    }
    
    // 选择最高出价（first-price）
    sort.Slice(wins, func(i, j int) bool {
        return wins[i].Price > wins[j].Price
    })
    
    // 5. 发送 win notice
    winner := wins[0]
    h.sendWinNotice(ctx, winner)
    
    return &BidResponse{
        Price: winner.Price,
        Creative: winner.Creative,
        Bidder: winner.Bidder,
    }, nil
}
```

---

## 4. 工程实践

### 4.1 性能优化

#### 4.1.1 延迟预算分配

```go
// 总延迟预算：200ms
// 分配策略：
// - Bid Request 构建：20ms
// - 频次检查：5ms
// - Floor Price 查询：5ms
// - DSP 并发请求：150ms（最慢的那个）
// - 响应聚合：10ms
// - 回传：10ms

const (
    TotalBudget      = 200 * time.Millisecond
    RequestBuildBudget = 20 * time.Millisecond
    CheckBudget      = 10 * time.Millisecond
    DSPBudget        = 150 * time.Millisecond
    ResponseBudget   = 20 * time.Millisecond
)
```

#### 4.1.2 连接池与超时

```go
type BidderClient struct {
    httpClient *http.Client
}

func NewBidderClient() *BidderClient {
    return &BidderClient{
        httpClient: &http.Client{
            Transport: &http.Transport{
                MaxIdleConns:        1000,
                MaxIdleConnsPerHost: 100,
                IdleConnTimeout:     90 * time.Second,
            },
            Timeout: 150 * time.Millisecond, // 单 DSP 超时
        },
    }
}
```

### 4.2 可靠性保障

#### 4.2.1 降级策略

```go
func (h *BidHandler) HandleWithFallback(ctx context.Context, req BidRequest) (*BidResponse, error) {
    // 1. 正常 RTB 竞价
    resp, err := h.HandleBid(ctx, req)
    if err == nil {
        return resp, nil
    }
    
    // 2. 降级到 Waterfall
    log.Warn("RTB failed, fallback to waterfall", "err", err)
    return h.HandleWaterfall(ctx, req)
}

func (h *BidHandler) HandleWaterfall(ctx context.Context, req BidRequest) (*BidResponse, error) {
    // 按优先级依次请求
    for _, tier := range req.Waterfall {
        resp, err := h.callTier(ctx, tier, req)
        if err == nil && resp.Price >= req.FloorPrice {
            return resp, nil
        }
    }
    return nil, ErrNoFill
}
```

#### 4.2.2 监控指标

```go
type Metrics struct {
    BidLatency       prometheus.Histogram // 竞价延迟 P50/P95/P99
    FillRate         prometheus.Gauge     // Fill Rate
    eCPM             prometheus.Histogram // 实际 eCPM
    BidderLatency    map[string]prometheus.Histogram // 各 DSP 延迟
    ErrorRate        prometheus.Gauge     // 错误率
    FloorHitRate     prometheus.Gauge     // Floor 命中率
}
```

---

## 5. 常见问题与解决方案

### 5.1 低 Fill Rate

**现象**：很多请求没有返回广告

**排查步骤**：
1. 检查 floor price 是否设置过高
2. 检查 DSP 连接是否正常
3. 检查频次控制是否过严
4. 检查用户定向是否过于严格

```go
// 动态调整 floor price
func (m *FloorPriceManager) AdjustFloor(slot Slot, fillRate float64) {
    if fillRate < 0.3 {
        // Fill rate 太低，降低 floor
        m.decreaseFloor(slot, 0.9)
    } else if fillRate > 0.9 {
        // Fill rate 太高，可以提高 floor
        m.increaseFloor(slot, 1.1)
    }
}
```

### 5.2 高延迟

**现象**：P99 延迟超过 200ms

**优化方案**：
1. 并行请求 DSP，不串行
2. 使用连接池，避免重复建连
3. 设置合理的超时时间
4. 预热热门广告主的缓存

### 5.3 作弊流量

**检测策略**：
1. 设备指纹重复
2. IP 代理池识别
3. 行为异常（点击率过高/过低）
4. 地理位置不一致

---

## 6. 实战案例

### 6.1 某头部 SSP 架构

```
流量规模：100亿 QD（日请求量）
P99 延迟：< 100ms
Fill Rate：> 85%
收入：$10M+/天

架构要点：
- 全球 20+ 区域部署
- 每个区域独立竞价，避免跨区延迟
- 使用 eBPF 进行零拷贝网络处理
- Redis Cluster 存储频控数据
- Kafka 做实时事件流处理
```

### 6.2 收入优化效果

| 优化项 | 优化前 | 优化后 | 提升 |
|--------|--------|--------|------|
| Fill Rate | 72% | 85% | +13% |
| eCPM | $2.1 | $2.8 | +33% |
| 延迟 P99 | 180ms | 95ms | -47% |
| 作弊率 | 8% | 2% | -75% |

---

## 7. 延伸阅读

- [OpenRTB 2.x 规范](https://www.iab.com/wp-content/uploads/2024/05/OpenRTB-v2.6-FINAL.pdf)
- [IAB Tech Lab - SSP Guidelines](https://www.iab.com/technologies/ssp/)
- [Real-Time Bidding: How It Works](https://www.profitabledisplay.com/real-time-bidding/)

---

*最后更新：2026-08-11*
*作者：Ryan*

---

## 自测题

<details>
<summary>Q1: SSP的核心职责是什么？与DSP的本质区别在哪里？</summary>

**答案：**
- **SSP职责**：管理广告位库存、执行竞价决策、保障填充率和eCPM最大化
- **DSP职责**：管理广告主预算、出价策略、创意投放，追求ROI最大化
- **本质区别**：
  - SSP代表媒体利益方（卖方）
  - DSP代表广告主利益方（买方）
  - 同一RTB交易中，SSP负责"卖"，DSP负责"买"

**记忆口诀**：SSP=Supply Side Platform（供应方），DSP=Demand Side Platform（需求方）
</details>

<details>
<summary>Q2: SSP如何决定将请求路由到哪个SSP Server实例？</summary>

**答案：**
采用三层路由策略：

| 层级 | 策略 | 目标 |
|------|------|------|
| 第一层 | 地理位置就近分配 | 降低网络延迟 |
| 第二层 | 广告位分组亲和性 | 缓存局部性优化 |
| 第三层 | 负载均衡轮询 | 避免单点过载 |

```python
def route_request(req: SSPRequest) -> SSPServer:
    """三级路由策略"""
    # 1. 地理就近
    zone = find_geo_zone(req.user_location)
    candidates = get_servers_in_zone(zone)
    
    # 2. 广告位亲和性
    slot_group = req.slot_id % GROUP_COUNT
    affinity = filter_by_affinity(candidates, slot_group)
    
    # 3. 负载均衡
    return least_loaded(affinity or candidates)
```

</details>

<details>
<summary>Q3: 在SSP的实时竞价流程中，什么情况下会触发内部竞价而非外部RTB？</summary>

**答案：**
触发内部竞价的条件：

| 条件 | 判断逻辑 | 原因 |
|------|----------|------|
| 直投订单 | `req.priority_level == 1` | 保量合同优先执行 |
| 私有市场 | `req.private_auction == True` | PM区块限制参与方 |
| 预算耗尽 | ` bidder_budget < min_bid` | 排除无预算买方 |
| 低频流量 | `fill_rate_target > 0.8` | 保守策略保填充 |

```go
func shouldDoInternalAuction(req *BidRequest) bool {
    // 直投订单最高优先级
    if req.PriorityLevel <= PRIORITY_DIRECT_DEAL {
        return true
    }
    // 预算不足时走内部兜底
    if req.TotalBudget < req.MinBid * expectedBidders {
        return true
    }
    return false
}
```

</details>

<details>
<summary>Q4: SSP如何通过预计算优化提升竞价决策性能？</summary>

**答案：**
三层预计算架构：

1. **离线预计算**（小时级）
   - 广告位历史eCPM排序
   - 媒体质量分层标签
   - 买家偏好聚类模型

2. **近线预计算**（分钟级）
   - 实时流量波动预测
   - 动态出价调整系数
   - 异常检测基线

3. **在线预计算**（请求级）
   - 候选广告主快速过滤
   - 价格弹性预估值
   - 竞对出价分布预估

```python
class SSPPreCompute:
    def __init__(self):
        self.offline_cache = TTLCache(ttl=3600)    # 小时级
        self.nearline_cache = TTLCache(ttl=60)     # 分钟级
        self.online_cache = TTLCache(ttl=5)        # 请求级
    
    def get_slot_ranking(self, slot_id: str) -> List[float]:
        """获取广告位历史eCPM排名"""
        key = f"slot_rank:{slot_id}"
        return self.offline_cache.get(key, default=[])
```

</details>

<details>
<summary>Q5: SSP如何处理跨域的频次控制问题？</summary>

**答案：**
采用分布式频次计数器方案：

| 方案 | 实现方式 | 准确率 | 开销 |
|------|----------|--------|------|
| Redis计数 | INCR + EXPIRE | 99%+ | 高 |
| Bloom Filter | 位图压缩 | 有误判 | 低 |
| 本地+同步 | 先本地后分布式 | 95% | 最低 |

```go
type FrequencyController struct {
    redis    *redis.Client
    localMap sync.Map
}

func (fc *FrequencyController) IsExceeded(userId, adId string, limit int) bool {
    // 1. 先查本地缓存
    if fc.localHit(userId, adId, limit) {
        return true
    }
    // 2. 查Redis分布式计数器
    key := fmt.Sprintf("freq:%s:%s", userId, adId)
    count, _ := fc.redis.Incr(key).Result()
    if count == 1 {
        fc.redis.Expire(key, 24*time.Hour)
    }
    return count > int32(limit)
}
```

</details>

---

*最后更新：2026-08-12*
*升级：添加自测题（5道）*
