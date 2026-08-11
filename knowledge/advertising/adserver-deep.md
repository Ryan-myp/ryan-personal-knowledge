# Ad Server 深入解析 — 广告服务器的架构与设计

> 本文档深入解析 Ad Server（广告服务器）的核心架构、请求处理流程、数据库设计和性能优化。
> 适用对象：广告系统架构师、后端工程师、技术负责人

---

## 1. Ad Server 概述

### 1.1 什么是 Ad Server

Ad Server 是广告技术栈的核心组件，负责：
- **广告库存管理**：管理广告位、创意、定向规则
- **广告竞价**：处理 RTB 请求或内部竞价
- **广告返回**：返回获胜广告给请求方
- **曝光计费**：记录曝光、点击、转化事件
- **报表生成**：生成收入、填充率、eCPM 等报表

### 1.2 系统定位

```
┌─────────────────────────────────────────────────────────────────────┐
│                           广告生态                                   │
│                                                                     │
│   ┌─────────┐        ┌─────────┐        ┌─────────┐               │
│   │  Ad     │        │  Ad     │        │  Ad     │               │
│   │  Network│        │  Server │        │  Network│               │
│   │  (供应) │◄──────►│ (核心)  │◄──────►│ (需求)  │               │
│   └─────────┘        └────┬────┘        └─────────┘               │
│                           │                                        │
│                    ┌──────▼──────┐                               │
│                    │   SSP/DSP   │                               │
│                    │   Exchange  │                               │
│                    └─────────────┘                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 与 SSP/DSP 的关系

| 组件 | 定位 | 核心功能 |
|------|------|----------|
| **Ad Server** | 媒体侧核心 | 广告管理、竞价、计费 |
| **SSP** | 媒体侧平台 | 多 Ad Server 聚合、收入优化 |
| **DSP** | 广告主侧平台 | 出价策略、投放管理 |
| **ADX** | 交易所 | 撮合买卖双方 |

---

## 2. 核心架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Ad Server 架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  请求接入层                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Web Tag     │  │  Mobile SDK  │  │  Server-Side │             │
│  │  (GPT/DFP)   │  │  (iOS/Android)│  │  Header      │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼──────┐                                 │
│                    │   API GW   │  Kong/Traefik + JWT              │
│                    └──────┬──────┘                                 │
│                           │                                         │
│  业务逻辑层                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Ad Request  │  │  Auction     │  │  Targeting   │             │
│  │  Handler     │  │  Engine      │  │  Engine      │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼──────┐                                 │
│                    │  Ad Selector │                                │
│                    │  (选择器)    │                                 │
│                    └──────┬──────┘                                 │
│                           │                                         │
│  数据存储层                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │  MySQL   │ │  Redis   │ │  Kafka   │ │  S3/MinIO│             │
│  │(元数据)  │ │(缓存/频控)│ │(事件流)  │ │(创意存储)│             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
│                                                                     │
│  分析层                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                           │
│  │  Click   │ │  Impression│ │  Conversion│                         │
│  │  Logger  │ │  Logger  │ │  Tracker │                           │
│  └──────────┘ └──────────┘ └──────────┘                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块

| 模块 | 职责 | 关键技术 |
|------|------|----------|
| **Ad Request Handler** | 解析请求、参数校验 | OpenRTB、自定义协议 |
| **Auction Engine** | 竞价决策、胜负判定 | 多路并发、超时控制 |
| **Targeting Engine** | 定向匹配、优先级排序 | 规则引擎、Bloom Filter |
| **Ad Selector** | 创意选择、轮播控制 | 权重算法、轮询策略 |
| **Counter** | 计数、频控 | Redis INCR、滑动窗口 |
| **Logger** | 事件记录 | Kafka 异步写入 |
| **Report Engine** | 报表生成 | ClickHouse 聚合 |

---

## 3. 请求处理流程

### 3.1 完整时序图

```
Publisher    Ad Server     Auction    DSP     Counter    Logger
   │            │            │         │          │          │
   │  Ad Request│            │         │          │          │
   ├───────────►│            │         │          │          │
   │            │ 1. Validate │         │          │          │
   │            ├───────────►│         │          │          │
   │            │            │         │          │          │
   │            │ 2. Check Freq │      │          │          │
   │            ├───────────────────────►│          │          │
   │            │            │         │          │          │
   │            │ 3. Get Floor │       │          │          │
   │            ├────────────────────────►│          │          │
   │            │            │         │          │          │
   │            │ 4. Query Targeting │      │          │          │
   │            ├─────────────────────────────►│          │          │
   │            │            │         │          │          │
   │            │ 5. Call DSPs (并发) │     │          │          │
   │            ├─────────────────────────────►│          │          │
   │            │            │    ────►│          │          │
   │            │            │◄────┐   │          │          │
   │            │            │     │   │          │          │
   │            │            │◄────┴───┤          │          │
   │            │            │         │          │          │
   │            │ 6. Select Winner│     │          │          │
   │            ├───────────────────►│          │          │
   │            │            │         │          │          │
   │            │ 7. Record Impression│        │          │
   │            ├─────────────────────────────────►│          │
   │            │            │         │          │          │
   │            │ 8. Return Ad   │         │          │          │
   │            ├──────────────────────────────────────────────►│
   │◄───────────│            │         │          │          │
   │            │            │         │          │          │
   │  User clicks ad             │          │          │
   │◄───────────────────────────────────────────────────────►│
   │            │            │         │          │          │
   │  Click event    │         │          │          │
   ├────────────────────────────────────────────────────────►│
   │            │            │         │          │          │
```

### 3.2 核心代码实现

#### 3.2.1 请求处理

```go
type AdServer struct {
    auction   *AuctionEngine
    counter   *FrequencyCounter
    logger    *EventLogger
    targeting *TargetingEngine
}

func (s *AdServer) HandleAdRequest(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    // 1. 参数校验
    if err := s.validateRequest(req); err != nil {
        return nil, err
    }
    
    // 2. 频次检查
    if ok, err := s.counter.Check(ctx, req); err != nil || !ok {
        return s.handleNoFill(req, "frequency_cap")
    }
    
    // 3. 定向匹配
    targets, err := s.targeting.Match(ctx, req)
    if err != nil {
        return nil, err
    }
    
    // 4. 发起竞价
    auctionResult, err := s.auction.Run(ctx, req, targets)
    if err != nil {
        return s.handleNoFill(req, "auction_error")
    }
    
    // 5. 记录曝光
    go s.logger.LogImpression(ctx, auctionResult)
    
    // 6. 返回广告
    return &AdResponse{
        AdID:      auctionResult.WinningBid.AdID,
        Creative:  auctionResult.WinningBid.Creative,
        Price:     auctionResult.WinningBid.Price,
        Tracker:   auctionResult.Trackers,
    }, nil
}
```

#### 3.2.2 竞价引擎

```go
type AuctionEngine struct {
    bidders []Bidder
    floor   *FloorManager
}

func (a *AuctionEngine) Run(ctx context.Context, req *AdRequest, targets Targets) (*AuctionResult, error) {
    // 获取 floor price
    floor, err := a.floor.Get(req)
    if err != nil {
        floor = 0.01 // 默认最低 floor
    }
    
    // 并发请求所有 bidder
    type bidResult struct {
        bidder string
        bid    *Bid
        err    error
    }
    
    resultCh := make(chan bidResult, len(a.bidders))
    
    for _, bidder := range a.bidders {
        go func(b Bidder) {
            bid, err := b.Bid(ctx, req, targets)
            resultCh <- bidResult{bidder: b.Name(), bid: bid, err: err}
        }(bidder)
    }
    
    // 收集响应
    var bids []*Bid
    for i := 0; i < len(a.bidders); i++ {
        select {
        case result := <-resultCh:
            if result.err != nil {
                continue
            }
            if result.bid != nil && result.bid.Price >= floor {
                bids = append(bids, result.bid)
            }
        case <-time.After(150 * time.Millisecond):
            // 超时放弃
        }
    }
    
    if len(bids) == 0 {
        return &AuctionResult{NoFill: true}, nil
    }
    
    // First-Price  auction
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].Price > bids[j].Price
    })
    
    return &AuctionResult{
        WinningBid: bids[0],
        Bids:       bids,
    }, nil
}
```

---

## 4. 数据库设计

### 4.1 核心表结构

#### 4.1.1 广告位表

```sql
CREATE TABLE ad_units (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    publisher_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    ad_type ENUM('banner', 'native', 'video', 'interstitial') NOT NULL,
    width INT,
    height INT,
    floor_price DECIMAL(10,6) DEFAULT 0.01,
    frequency_cap INT DEFAULT 3,
    status ENUM('active', 'paused', 'deleted') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_publisher (publisher_id, status),
    INDEX idx_status (status)
);
```

#### 4.1.2 广告创意表

```sql
CREATE TABLE creatives (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    campaign_id BIGINT NOT NULL,
    name VARCHAR(200),
    ad_type ENUM('image', 'video', 'html') NOT NULL,
    url VARCHAR(500),
    click_url VARCHAR(500),
    tracking_urls JSON,
    width INT,
    height INT,
    duration INT,  -- 视频时长
    status ENUM('active', 'paused', 'rejected') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_campaign (campaign_id, status)
);
```

#### 4.1.3 广告库存表

```sql
CREATE TABLE inventory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ad_unit_id BIGINT NOT NULL,
    date DATE NOT NULL,
    total_slots INT DEFAULT 0,
    sold_slots INT DEFAULT 0,
    fill_rate DECIMAL(5,4) DEFAULT 0.0000,
    revenue DECIMAL(12,2) DEFAULT 0.00,
    UNIQUE KEY uk_date_unit (date, ad_unit_id),
    INDEX idx_date (date)
);
```

#### 4.1.4 竞价日志表

```sql
CREATE TABLE bid_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_id VARCHAR(64) NOT NULL,
    ad_unit_id BIGINT,
    bidder_name VARCHAR(100),
    bid_price DECIMAL(10,6),
    win_price DECIMAL(10,6),
    is_win TINYINT DEFAULT 0,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_request (request_id),
    INDEX idx_date (DATE(created_at))
);
```

### 4.2 高频访问优化

```go
// Redis 缓存设计
type CacheKeys struct {
    // 广告位信息（TTL: 1h）
    AdUnit = "ad:unit:%d"
    
    // 频次计数（TTL: 24h）
    FreqUser = "freq:u:%s:a:%d"
    FreqIP = "freq:ip:%s:a:%d"
    
    // Floor Price（TTL: 1h）
    FloorPrice = "floor:%d"
}
```

---

## 5. 性能优化

### 5.1 延迟预算

```
总延迟预算：200ms

分配：
- 请求解析：5ms
- 缓存查询：5ms
- 频次检查：5ms
- 竞价处理：150ms（最慢路径）
- 响应构建：10ms
- 网络传输：25ms
```

### 5.2 并发优化

```go
// 使用 goroutine 并发请求多个 DSP
func (a *AuctionEngine) BidConcurrent(ctx context.Context, req *AdRequest) []*Bid {
    var wg sync.WaitGroup
    var mu sync.Mutex
    var bids []*Bid
    
    for _, bidder := range a.bidders {
        wg.Add(1)
        go func(b Bidder) {
            defer wg.Done()
            
            bid, err := b.Bid(ctx, req)
            if err != nil {
                return
            }
            
            mu.Lock()
            bids = append(bids, bid)
            mu.Unlock()
        }(bidder)
    }
    
    wg.Wait()
    return bids
}
```

### 5.3 缓存策略

| 数据 | 缓存类型 | TTL | 失效策略 |
|------|----------|-----|----------|
| 广告位配置 | Redis | 1h | 配置变更时失效 |
| 频次计数 | Redis | 24h | 自然过期 |
| Floor Price | Redis | 1h | 统计更新时刷新 |
| 热门创意 | Redis | 5min | LRU 淘汰 |

---

## 6. 监控指标

### 6.1 核心指标

```go
type Metrics struct {
    // 请求量
    RequestCount prometheus.Counter
    
    // 延迟
    RequestLatency prometheus.Histogram
    
    // Fill Rate
    FillRate prometheus.Gauge
    
    // eCPM
    eCPM prometheus.Histogram
    
    // 错误率
    ErrorRate prometheus.Gauge
    
    // 各 bidder 表现
    BidderLatency map[string]prometheus.Histogram
}
```

### 6.2 告警规则

| 指标 | 阈值 | 级别 | 动作 |
|------|------|------|------|
| P99 延迟 | > 300ms | P1 | 通知 OnCall |
| Fill Rate | < 60% | P0 | 自动降级 |
| 错误率 | > 5% | P0 | 自动熔断 |
| eCPM | 下跌 > 20% | P1 | 通知运营 |

---

## 7. 常见问题

### 7.1 低 Fill Rate

**排查步骤**：
1. 检查 floor price 是否过高
2. 检查 bidder 连接是否正常
3. 检查定向条件是否过严
4. 检查频次控制是否过严

### 7.2 高延迟

**优化方案**：
1. 并行请求而非串行
2. 设置合理超时
3. 使用连接池
4. 预热缓存

### 7.3 数据不一致

**解决方案**：
1. 使用分布式事务
2. 异步对账
3. 最终一致性保障

---

## 8. 实战案例

### 8.1 某大型媒体 Ad Server

```
日请求量：500亿
P99 延迟：85ms
Fill Rate：88%
收入：$5M+/天

架构要点：
- 全球 15 个区域部署
- 每个区域独立竞价
- 使用 eBPF 优化网络栈
- ClickHouse 实时分析
```

### 8.2 性能优化效果

| 优化项 | 优化前 | 优化后 | 提升 |
|--------|--------|--------|------|
| P99 延迟 | 250ms | 85ms | -66% |
| Fill Rate | 75% | 88% | +13% |
| 错误率 | 3% | 0.1% | -97% |
| 资源成本 | $100K/月 | $60K/月 | -40% |

---

## 9. 延伸阅读

- [Google DFP/Studio 架构](https://support.google.com/dfp_premium/answer/7161350)
- [OpenRTB 2.x Specification](https://www.iab.com/wp-content/uploads/2024/05/OpenRTB-v2.6-FINAL.pdf)
- [Ad Tech 架构设计原则](https://www.adtechsummit.com/)

---

*最后更新：2026-08-11*
*作者：Ryan*
