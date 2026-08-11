# 广告系统架构深度解析

> 深入广告系统核心架构：DSP、SSP、Ad Exchange、DMP。
> 包含真实生产环境架构设计和性能优化。
> 适用对象：广告系统架构师、后端工程师

---

## 1. 广告系统架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    广告生态系统                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ Advertiser│  │  DSP   │    │SSP/Ad   │                │
│  │  (广告主) │───►│(需求方)│───►│ Exchange │───► Publisher  │
│  └─────────┘    └─────────┘    └─────────┘   (发布方)       │
│                        │           │                         │
│                        ▼           ▼                         │
│                   ┌─────────────────────┐                   │
│                   │      DMP            │                   │
│                   │   (数据管理平台)     │                   │
│                   └─────────────────────┘                   │
│                                                             │
│  关键流程：                                                  │
│  1. 用户访问网站/App                                        │
│  2. SSP 向 Ad Exchange 发送请求                              │
│  3. Ad Exchange 向 DSP 询价                                  │
│  4. DSP 计算出价并响应                                       │
│  5. Ad Exchange 选择最高出价                                 │
│  6. 广告展示给用户                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心系统

| 系统 | 角色 | 核心功能 |
|------|------|----------|
| DSP | 需求方平台 | 出价决策、创意管理、效果追踪 |
| SSP | 供应方平台 | 库存管理、出价优化、收益最大化 |
| Ad Exchange | 广告交换平台 | 竞价撮合、计费结算 |
| DMP | 数据管理平台 | 用户画像、受众细分、数据服务 |

---

## 2. DSP 架构

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      DSP 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 API Gateway                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│          ┌──────────────┼──────────────┐                   │
│          ▼              ▼              ▼                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ Bidding   │  │ Audience  │  │ Creative  │              │
│  │ Service   │  │ Service   │  │ Service   │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                      │
│  ┌─────▼──────────────▼──────────────▼─────┐               │
│  │            Real-time Engine             │               │
│  │  ├── 请求解析                           │               │
│  │  ├── 受众匹配                           │               │
│  │  ├── 出价计算                           │               │
│  │  └── 响应生成                           │               │
│  └─────────────────────────────────────────┘               │
│                         │                                   │
│          ┌──────────────┼──────────────┐                   │
│          ▼              ▼              ▼                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ User Prof│  │ Campaign  │  │ Analytics │              │
│  │   ile    │  │  Manager  │  │  Engine   │              │
│  └───────────┘  └───────────┘  └───────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 竞价引擎

```go
// bidding_engine.go

package dsp

import (
    "context"
    "time"
)

type BiddingEngine struct {
    audienceSvc *AudienceService
    pricingSvc  *PricingService
    budgetSvc   *BudgetService
}

type BidRequest struct {
    ImpressionID string
    User         *User
    Placement    *Placement
    Budget       float64
    Deadline     time.Time
}

type BidResponse struct {
    ImpressionID string
    BidPrice     float64
    AdID         string
    Targeting    map[string]string
}

func (e *BiddingEngine) ProcessBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 受众匹配
    audiences := e.audienceSvc.Match(req.User)
    if len(audiences) == 0 {
        return nil, nil // 不匹配，不出价
    }
    
    // 2. 出价计算
    bidPrice := e.pricingSvc.Calculate(req, audiences)
    
    // 3. 预算检查
    if !e.budgetSvc.Check(req.CampaignID, bidPrice) {
        return nil, nil // 预算不足
    }
    
    // 4. 生成响应
    return &BidResponse{
        ImpressionID: req.ImpressionID,
        BidPrice:     bidPrice,
        AdID:         req.AdID,
        Targeting:    audiences,
    }, nil
}
```

---

## 3. SSP 架构

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      SSP 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Ad Server                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│          ┌──────────────┼──────────────┐                   │
│          ▼              ▼              ▼                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ Inventory │  │ Floor    │  │ Waterfall │              │
│  │ Manager   │  │ Price    │  │  Engine   │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                      │
│  ┌─────▼──────────────▼──────────────▼─────┐               │
│  │            Bid Request Builder          │               │
│  │  ├── 库存准备                           │               │
│  │  ├── 受众信息添加                        │               │
│  │  └── 请求格式化                         │               │
│  └─────────────────────────────────────────┘               │
│                         │                                   │
│          ┌──────────────┼──────────────┐                   │
│          ▼              ▼              ▼                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ Analytics │  │ Reporting │  │ Settlement│              │
│  │  Engine   │  │  Engine   │  │  Engine   │              │
│  └───────────┘  └───────────┘  └───────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. DMP 架构

### 4.1 数据流

```
数据收集 → 数据处理 → 数据存储 → 数据服务

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Data Input │───►│  Data Proc  │───►│  Data Store │───►│ Data API    │
│  (采集)      │    │  (处理)      │    │  (存储)      │    │  (服务)      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
  ┌─────────┐       ┌─────────┐       ┌─────────┐       ┌─────────┐
  │ SDK     │       │  ETL    │       │  HDFS   │       │ REST    │
  │ Tag     │       │ Streaming│      │ ClickHouse│     │ GraphQL │
  │ API     │       │  Spark  │       │  Redis  │       │  Batch  │
  └─────────┘       └─────────┘       └─────────┘       └─────────┘
```

### 4.2 用户画像

```go
// user_profile.go

package dmp

type UserProfile struct {
    UserID      string         `json:"user_id"`
    Demographics map[string]interface{} `json:"demographics"`
    Interests   []string       `json:"interests"`
    Behaviors   []BehaviorEvent `json:"behaviors"`
    Segments    []string       `json:"segments"`
    Score       float64        `json:"score"`
    UpdatedAt   time.Time      `json:"updated_at"`
}

type BehaviorEvent struct {
    EventType string    `json:"event_type"`
    EventTime time.Time `json:"event_time"`
    Context   map[string]interface{} `json:"context"`
}
```

---

## 5. 性能优化

### 5.1 竞价延迟优化

```
目标：端到端延迟 < 100ms

优化策略：
1. 预计算受众匹配
2. 缓存出价结果
3. 并行处理请求
4. 本地缓存热点数据
5. 异步日志和指标

性能指标：
- P50: < 10ms
- P99: < 50ms
- 可用性: 99.99%
```

### 5.2 Go 实现高性能竞价

```go
// high_perf_bidding.go

package dsp

import (
    "sync"
    "time"
)

type Cache struct {
    data sync.Map
    ttl  time.Duration
}

func (c *Cache) Get(key string) (interface{}, bool) {
    v, ok := c.data.Load(key)
    if !ok {
        return nil, false
    }
    item := v.(*cacheItem)
    if time.Now().After(item.expiry) {
        c.data.Delete(key)
        return nil, false
    }
    return item.value, true
}

func (c *Cache) Set(key string, value interface{}) {
    c.data.Store(key, &cacheItem{
        value:   value,
        expiry:  time.Now().Add(c.ttl),
    })
}

type cacheItem struct {
    value  interface{}
    expiry time.Time
}
```

---

## 6. 监控告警

### 6.1 关键指标

```
业务指标：
- ECPM (千次展示收益)
- CTR (点击率)
- CVR (转化率)
- Fill Rate (填充率)

技术指标：
- 竞价延迟 P50/P99
- 请求成功率
- 系统可用性
- 资源使用率
```

### 6.2 告警规则

```yaml
alerts:
  - name: 竞价延迟过高
    metric: bidding_latency_p99
    threshold: 100ms
    duration: 5m
    
  - name: 请求失败率过高
    metric: request_error_rate
    threshold: 1%
    duration: 2m
    
  - name: 内存使用过高
    metric: memory_usage_percent
    threshold: 85%
    duration: 10m
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 竞价延迟高 | P99 > 100ms | `top`, `pprof` | 优化缓存/并行化 |
| 请求失败 | 错误率 > 1% | 查看日志 | 检查依赖服务 |
| 数据不一致 | 指标异常 | 对比源数据 | 修复数据管道 |
| 内存泄漏 | 内存持续增长 | `pprof heap` | 修复泄漏点 |

### 7.2 排查工具

```bash
# 查看服务状态
curl http://localhost:8080/metrics

# 查看请求链路
curl http://localhost:8080/trace?id=xxx

# 查看 goroutine
curl http://localhost:6060/debug/pprof/goroutine

# 查看内存
curl http://localhost:6060/debug/pprof/heap
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| DSP | 实时竞价引擎 |
| SSP | 库存管理 + 瀑布流 |
| DMP | 用户画像 + 受众细分 |
| Exchange | 竞价撮合 |

### 8.2 最佳实践

- [ ] 优化竞价延迟
- [ ] 实现高效缓存
- [ ] 完善监控告警
- [ ] 建立故障预案
- [ ] 持续性能优化

---

*最后更新：2026-08-11*
*作者：Ryan*
