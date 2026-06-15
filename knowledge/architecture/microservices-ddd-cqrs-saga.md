# 架构实战：微服务拆分/DDD落地/CQRS/Saga

> 微服务边界划分/DDD 限界上下文/CQRS 读写分离/Saga 分布式事务

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要微服务拆分？

单体架构的问题：
- **代码膨胀**：100 万行代码，修改一行需要全量构建
- **团队瓶颈**：9 人团队只能串行开发
- **技术债**：老代码不敢改
- **扩展性差**：只能整体扩缩容

### 微服务拆分原则

```
单体应用 → 按业务域拆分 → 微服务

拆分原则：
1. 单一职责：每个服务只做一件事
2. 高内聚低耦合：服务内紧密，服务间松散
3. 独立部署：每个服务独立发布
4. 数据隔离：每个服务有自己的数据库
```

---

## 第二部分：DDD 限界上下文

### 2.1 限界上下文识别

```go
package domain

// 上下文枚举
type Context string

const (
    BiddingContext   Context = "bidding"
    CampaignContext  Context = "campaign"
    UserContext      Context = "user"
    ReportingContext Context = "reporting"
)

// 限界上下文：竞价
type BiddingContext struct {
    BidRepository    *BidRepository
    PricingStrategy  PricingStrategy
    FrequencyCap     *FrequencyCap
}

// 限界上下文：广告活动
type CampaignContext struct {
    CampaignRepo     *CampaignRepository
    BudgetManager    *BudgetManager
    TargetingEngine  *TargetingEngine
}

// 限界上下文：用户
type UserContext struct {
    UserProfileRepo  *UserProfileRepository
    PreferenceEngine *PreferenceEngine
}

// 限界上下文：报表
type ReportingContext struct {
    EventRepository  *EventRepository
    AggregationEngine *AggregationEngine
}
```

### 2.2 上下文映射

```go
// 上下文映射：Bidding ↔ Campaign
// 关系：合作（Partnership）— 预算共享

type BiddingService struct {
    campaignClient *CampaignClient
}

func (bs *BiddingService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 检查预算
    budgetOK, err := bs.campaignClient.CheckBudget(req.CampaignID)
    if err != nil || !budgetOK {
        return nil, nil
    }
    
    // 2. 执行竞价
    price, err := bs.calculateBid(req)
    if err != nil {
        return nil, err
    }
    
    // 3. 扣减预算
    err = bs.campaignClient.DeductBudget(req.CampaignID, price)
    if err != nil {
        return nil, err
    }
    
    return &BidResponse{Price: price}, nil
}

// 上下文映射：Bidding → Reporting
// 关系：发布/订阅（Publish/Subscribe）

type BiddingPublisher struct {
    eventBus EventBus
}

func (bp *BiddingPublisher) PublishBidEvent(bid *Bid) {
    bp.eventBus.Publish("bid.completed", bid)
}

type ReportingSubscriber struct {
    eventBus EventBus
}

func (rs *ReportingSubscriber) Subscribe() {
    rs.eventBus.Subscribe("bid.completed", func(event interface{}) {
        rs.aggregate(event.(*Bid))
    })
}
```

### 2.3 DDD 实体与值对象

```go
// 实体：有唯一 ID
type Campaign struct {
    ID        string
    Name      string
    Budget    float64
    Status    CampaignStatus
    CreatedAt time.Time
}

type CampaignStatus string

const (
    Active   CampaignStatus = "active"
    Paused   CampaignStatus = "paused"
    Ended    CampaignStatus = "ended"
)

// 值对象：不可变，通过值比较
type Targeting struct {
    Locations []string
    Ages      []AgeRange
    Interests []string
}

type AgeRange struct {
    Min int
    Max int
}

func (t Targeting) Matches(user *User) bool {
    // 检查用户是否符合定向条件
    for _, loc := range t.Locations {
        if user.Location == loc {
            return true
        }
    }
    return false
}

// 聚合根：管理实体和值对象
type BidAggregate struct {
    ID          string
    Campaign    *Campaign
    Impression  *Impression
    BidPrice    float64
    Status      BidStatus
}

type BidStatus string

const (
    Pending  BidStatus = "pending"
    Won      BidStatus = "won"
    Lost     BidStatus = "lost"
)
```

---

## 第三部分：微服务拆分实战

### 3.1 服务拆分方案

```
广告平台微服务拆分：

┌─────────────────────────────────────────────────────┐
│                     API Gateway                       │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│ Bidding  │ Campaign │ User     │ Reporting│ Ad      │
│ Service  │ Service  │ Service  │ Service  │ Creative│
│          │          │          │          │ Service │
├──────────┴──────────┴──────────┴──────────┴─────────┤
│                  Message Queue                        │
├─────────────────────────────────────────────────────┤
│              Database (per service)                   │
│  bidding_db  campaign_db  user_db  reporting_db      │
└─────────────────────────────────────────────────────┘
```

### 3.2 服务间通信

```go
// gRPC 服务定义
// bidding.proto
service BiddingService {
    rpc Bid(BidRequest) returns (BidResponse) {}
    rpc StreamBids(stream BidRequest) returns (stream BidResponse) {}
}

// 服务实现
type BiddingServer struct {
    pb.UnimplementedBiddingServer
    bidEngine *BidEngine
}

func (s *BiddingServer) Bid(ctx context.Context, req *pb.BidRequest) (*pb.BidResponse, error) {
    // 1. 验证请求
    if err := validateRequest(req); err != nil {
        return nil, status.Error(codes.InvalidArgument, err.Error())
    }
    
    // 2. 执行竞价
    result, err := s.bidEngine.Bid(ctx, req)
    if err != nil {
        return nil, status.Error(codes.Internal, err.Error())
    }
    
    // 3. 返回结果
    return &pb.BidResponse{
        RequestId: req.RequestId,
        Price:     result.Price,
        AdId:      result.AdID,
    }, nil
}
```

### 3.3 服务发现与负载均衡

```go
type ServiceRegistry struct {
    services map[string][]string
    mu       sync.RWMutex
}

func (sr *ServiceRegistry) Register(service, address string) {
    sr.mu.Lock()
    defer sr.mu.Unlock()
    
    sr.services[service] = append(sr.services[service], address)
}

func (sr *ServiceRegistry) Deregister(service, address string) {
    sr.mu.Lock()
    defer sr.mu.Unlock()
    
    addresses := sr.services[service]
    for i, addr := range addresses {
        if addr == address {
            sr.services[service] = append(addresses[:i], addresses[i+1:]...)
            break
        }
    }
}

func (sr *ServiceRegistry) Get(service string) (string, error) {
    sr.mu.RLock()
    defer sr.mu.RUnlock()
    
    addresses := sr.services[service]
    if len(addresses) == 0 {
        return "", fmt.Errorf("service not found: %s", service)
    }
    
    // 简单轮询
    idx := time.Now().UnixNano() % int64(len(addresses))
    return addresses[idx], nil
}
```

---

## 第四部分：CQRS 读写分离

### 4.1 CQRS 架构

```
Command（写） → Command Handler → Domain Model → Event Store
                                                          ↓
Query（读）  ← Query Handler ← Read Model ← Event Processor
```

### 4.2 Go 实现 CQRS

```go
package cqrs

import (
    "context"
)

// Command 命令
type Command interface {
    GetName() string
}

// Query 查询
type Query interface {
    GetName() string
}

// EventHandler 事件处理器
type EventHandler interface {
    Handle(event interface{})
}

// Command Handler
type CommandHandler struct {
    repository *BidRepository
    eventBus   EventBus
}

func (ch *CommandHandler) Handle(ctx context.Context, cmd Command) error {
    switch c := cmd.(type) {
    case *CreateBidCommand:
        bid := NewBid(c.CampaignID, c.ImpressionID, c.UserID)
        err := ch.repository.Save(ctx, bid)
        if err != nil {
            return err
        }
        
        // 发布事件
        ch.eventBus.Publish(&BidCreatedEvent{
            BidID:      bid.ID,
            CampaignID: bid.CampaignID,
            Price:      bid.Price,
        })
        
        return nil
    }
    return nil
}

// Read Model 查询
type ReadModel struct {
    db *sql.DB
}

func (rm *ReadModel) GetCampaignStats(ctx context.Context, campaignID string) (*CampaignStats, error) {
    var stats CampaignStats
    err := rm.db.QueryRow(`
        SELECT COUNT(*) as total_bids, 
               SUM(price) as total_spent,
               AVG(price) as avg_price
        FROM bids 
        WHERE campaign_id = ?
    `, campaignID).Scan(&stats.TotalBids, &stats.TotalSpent, &stats.AvgPrice)
    
    return &stats, err
}
```

---

## 第五部分：Saga 分布式事务

### 5.1 Saga 编排

```go
package saga

import (
    "context"
)

// Saga 步骤
type Step struct {
    Name      string
    Execute   func(context.Context) error
    Compensate func(context.Context) error
}

// Saga 编排器
type SagaEngine struct {
    steps []Step
}

func (se *SagaEngine) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    
    // 正向执行
    for i, step := range se.steps {
        err := step.Execute(ctx)
        if err != nil {
            // 执行补偿
            for j := len(executed) - 1; j >= 0; j-- {
                compensateErr := se.steps[executed[j]].Compensate(ctx)
                if compensateErr != nil {
                    log.Printf("compensation failed: %v", compensateErr)
                }
            }
            return err
        }
        executed = append(executed, i)
    }
    
    return nil
}

// 广告预算扣减 Saga
func NewBudgetDeductionSaga() *SagaEngine {
    return &SagaEngine{
        steps: []Step{
            {
                Name: "reserve_budget",
                Execute: func(ctx context.Context) error {
                    // 预留预算
                    return reserveBudget(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    // 释放预留
                    return releaseReservation(ctx)
                },
            },
            {
                Name: "deduct_budget",
                Execute: func(ctx context.Context) error {
                    // 扣减预算
                    return deductBudget(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    // 恢复预留
                    return restoreReserved(ctx)
                },
            },
            {
                Name: "record_bid",
                Execute: func(ctx context.Context) error {
                    // 记录竞价
                    return recordBid(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    // 删除记录
                    return deleteBidRecord(ctx)
                },
            },
        },
    }
}
```

### 5.2 Saga 补偿机制

```go
// 补偿事件
type CompensationEvent struct {
    OriginalEvent interface{}
    CompensatedAt time.Time
    Success       bool
}

// Saga 状态机
type SagaState int

const (
    SagaRunning SagaState = iota
    SagaCompleted
    SagaCompensating
    SagaFailed
)

type SagaInstance struct {
    ID       string
    State    SagaState
    Steps    []StepState
    Error    error
}

type StepState struct {
    Name       string
    Completed  bool
    Compensated bool
}
```

---

## 第六部分：自测题

### 问题 1
DDD 中实体和值对象的区别是什么？

<details>
<summary>查看答案</summary>

1. **实体**：有唯一 ID，通过身份识别
2. **值对象**：无 ID，通过值比较
3. **可变性**：实体可变，值对象不可变
4. **广告场景**：Campaign 是实体，Targeting 是值对象
5. **Go 实现**：struct 表示实体，value object 封装值

</details>

### 问题 2
CQRS 相比传统 CRUD 有什么优势？

<details>
<summary>查看答案</summary>

1. **读写分离**：读模型可以独立优化
2. **扩展性**：读写可以独立扩展
3. **事件溯源**：可以重建历史状态
4. **性能**：读模型可以用 Elasticsearch
5. **广告场景**：竞价写 + 报表读

</details>

### 问题 3
Saga 相比 2PC 有什么优势？

<details>
<summary>查看答案</summary>

1. **无锁**：不需要分布式锁
2. **高性能**：不需要两阶段提交
3. **容错性**：单步失败只补偿该步
4. **实现简单**：不需要事务管理器
5. **Go 实现**：SagaEngine 编排

</details>

---

*本文档基于架构实战原理整理。*