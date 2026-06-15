# 微服务架构深度：DDD 落地/CQRS/Saga 实战

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解微服务拆分

```
单体应用 = 一家大型餐厅
  → 厨师、服务员、收银都在一个房间
  → 人多时拥挤，扩展困难

微服务 = 美食城
  → 每个摊位独立经营
  → 可以独立扩缩容
  → 一个摊位倒闭不影响其他摊位
```

### 为什么要拆分？

| 维度 | 单体 | 微服务 |
|------|------|--------|
| **团队规模** | 10 人以内 | 不限 |
| **技术栈** | 统一 | 可以不同 |
| **部署频率** | 每周 1 次 | 每天多次 |
| **故障隔离** | 一个 bug 全挂 | 部分降级 |
| **扩展性** | 整体扩展 | 按需扩展 |

---

## 第二部分：DDD 限界上下文（逐行解析）

### 2.1 如何识别限界上下文？

```
广告平台业务分析：

用户说："我想创建一个广告活动，设置预算，投放到 Facebook 和 Google"

拆解关键词：
- 创建广告活动 → CampaignContext
- 设置预算 → BudgetContext
- 投放到 Facebook → FacebookContext
- 投放到 Google → GoogleContext
- 竞价 → BiddingContext
- 展示/点击 → ReportingContext

每个上下文有自己的：
- 领域模型
- 业务规则
- 数据模型
- 团队
```

### 2.2 上下文映射

```
┌─────────────────────────────────────────────────────┐
│                    API Gateway                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  BiddingContext ──publish──→ ReportingContext       │
│       ↑                        ↑                    │
│       │                        │                    │
│  CampaignContext ←─share── BudgetContext           │
│                                                     │
│  关系类型：                                         │
│  - Partnership（合作）：共享核心域                  │
│  - Customer-Supplier（客户-供应商）：一方依赖另一方  │
│  - Conformist（服从者）：遵循上游的模型             │
│  - Anti-Corruption Layer（防腐层）：隔离上游变化    │
│  - Published Language（发布语言）：共享协议         │
│  - Separate Way（分离方式）：完全独立               │
└─────────────────────────────────────────────────────┘
```

### 2.3 Go 实现限界上下文

```go
package ddd

import (
    "context"
    "fmt"
)

// 竞价上下文
type BiddingContext struct {
    bidRepo        *BidRepository
    pricingEngine  *PricingEngine
    freqCap        *FrequencyCap
    budgetChecker  *BudgetChecker
}

// 广告活动上下文
type CampaignContext struct {
    campaignRepo   *CampaignRepository
    budgetManager  *BudgetManager
    targetingEngine *TargetingEngine
}

// 预算上下文
type BudgetContext struct {
    budgetRepo     *BudgetRepository
}

// 上下文之间的通信
type ContextCommunication struct {
    biddingCtx    *BiddingContext
    campaignCtx   *CampaignContext
    budgetCtx     *BudgetContext
}

// 竞价服务需要检查预算
func (cc *ContextCommunication) PlaceBid(ctx context.Context, bid *Bid) (*BidResponse, error) {
    // 1. 检查预算（调用 BudgetContext）
    if !cc.budgetCtx.HasBudget(bid.CampaignID) {
        return nil, fmt.Errorf("budget exceeded")
    }
    
    // 2. 执行竞价（调用 BiddingContext）
    result, err := cc.biddingCtx.Bid(ctx, bid)
    if err != nil {
        return nil, err
    }
    
    // 3. 扣减预算（调用 BudgetContext）
    err = cc.budgetCtx.DeductBudget(bid.CampaignID, result.Price)
    if err != nil {
        return nil, err
    }
    
    return result, nil
}
```

### 2.4 聚合根设计

```go
// 竞价聚合根
type BidAggregate struct {
    ID           string
    CampaignID   string
    ImpressionID string
    UserID       string
    BidPrice     float64
    Status       BidStatus
    CreatedAt    time.Time
}

type BidStatus string

const (
    BidPending  BidStatus = "pending"
    BidWon      BidStatus = "won"
    BidLost     BidStatus = "lost"
)

// 聚合根的业务规则
func (ba *BidAggregate) PlaceBid(price float64) error {
    // 业务规则：出价必须在范围内
    if price < ba.MinBid {
        return fmt.Errorf("bid price too low: %.2f < %.2f", price, ba.MinBid)
    }
    if price > ba.MaxBid {
        return fmt.Errorf("bid price too high: %.2f > %.2f", price, ba.MaxBid)
    }
    
    ba.BidPrice = price
    ba.Status = BidPending
    ba.CreatedAt = time.Now()
    
    return nil
}

// 竞价结果
func (ba *BidAggregate) SetResult(won bool, price float64) {
    if won {
        ba.Status = BidWon
        ba.WonPrice = price
    } else {
        ba.Status = BidLost
    }
}
```

---

## 第三部分：CQRS 读写分离

### 3.1 为什么需要 CQRS？

```
传统 CRUD：
读和写共享同一个模型

问题：
- 读操作复杂（JOIN 多表）
- 写操作简单（INSERT/UPDATE）
- 模型难以同时优化读写

CQRS 解决：
- 写模型：面向业务规则
- 读模型：面向查询优化
```

### 3.2 Go 实现 CQRS

```go
package cqrs

import (
    "context"
)

// Command 命令（写操作）
type Command interface {
    GetName() string
}

// Query 查询（读操作）
type Query interface {
    GetName() string
}

// 创建竞价命令
type CreateBidCommand struct {
    CampaignID   string
    ImpressionID string
    UserID       string
    BidPrice     float64
}

func (c *CreateBidCommand) GetName() string {
    return "CreateBid"
}

// 竞价查询
type GetCampaignStatsQuery struct {
    CampaignID string
    StartDate  time.Time
    EndDate    time.Time
}

func (q *GetCampaignStatsQuery) GetName() string {
    return "GetCampaignStats"
}

// Command Handler（写模型）
type CommandHandler struct {
    repository *BidRepository
    eventBus   EventBus
}

func (ch *CommandHandler) Handle(ctx context.Context, cmd Command) error {
    switch c := cmd.(type) {
    case *CreateBidCommand:
        bid := NewBid(c.CampaignID, c.ImpressionID, c.UserID, c.BidPrice)
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

// Query Handler（读模型）
type QueryHandler struct {
    readDB *sql.DB
}

func (qh *QueryHandler) Handle(ctx context.Context, query Query) (interface{}, error) {
    switch q := query.(type) {
    case *GetCampaignStatsQuery:
        // 直接查优化过的读模型
        var stats CampaignStats
        err := qh.readDB.QueryRow(`
            SELECT COUNT(*) as impressions,
                   SUM(cost) as total_cost,
                   AVG(cost) as avg_cost
            FROM campaign_stats
            WHERE campaign_id = ?
              AND date BETWEEN ? AND ?
        `, q.CampaignID, q.StartDate, q.EndDate).Scan(
            &stats.Impressions,
            &stats.TotalCost,
            &stats.AvgCost,
        )
        
        return stats, err
    }
    return nil, nil
}
```

### 3.3 Event Sourcing（事件溯源）

```
CQRS + Event Sourcing = 完整的审计日志

写操作不是直接更新数据，而是追加事件：

传统方式：
UPDATE bids SET price = 100 WHERE id = 1

事件溯源方式：
INSERT INTO events (id, type, data, timestamp)
VALUES (1, 'BID_PRICE_CHANGED', '{"bid_id": 1, "old_price": 50, "new_price": 100}', NOW())

查询时：
1. 读取所有事件
2. 重放事件重建状态
```

```go
// 事件溯源
type EventSourcedAggregate struct {
    ID        string
    Events    []DomainEvent
    State     AggregateState
}

type DomainEvent interface {
    GetType() string
    GetTimestamp() time.Time
    GetPayload() map[string]interface{}
}

type BidCreatedEvent struct {
    BidID      string
    CampaignID string
    Price      float64
    Timestamp  time.Time
}

func (e *BidCreatedEvent) GetType() string {
    return "BID_CREATED"
}

func (e *BidCreatedEvent) GetTimestamp() time.Time {
    return e.Timestamp
}

func (e *BidCreatedEvent) GetPayload() map[string]interface{} {
    return map[string]interface{}{
        "bid_id":      e.BidID,
        "campaign_id": e.CampaignID,
        "price":       e.Price,
    }
}

// 重放事件重建状态
func (esa *EventSourcedAggregate) ReplayEvents() {
    for _, event := range esa.Events {
        switch event.GetType() {
        case "BID_CREATED":
            esa.State.BidCreated(event.(*BidCreatedEvent))
        case "BID_PRICE_CHANGED":
            esa.State.BidPriceChanged(event.(*BidPriceChangedEvent))
        case "BID_WINNER_DETERMINED":
            esa.State.BidWinnerDetermined(event.(*BidWinnerDeterminedEvent))
        }
    }
}
```

---

## 第四部分：Saga 分布式事务

### 4.1 Saga 是什么？

```
分布式系统中，没有一个单一的数据库事务可以跨多个服务

Saga 方案：
将分布式事务拆分为一系列本地事务
每个本地事务有对应的补偿操作

编排式 Saga：
┌─────────────────────────────────────────────────────┐
│                    Orchestrator                       │
│  1. ReserveBudget → 2. ExecuteBid → 3. RecordBid    │
│                    ↓                                 │
│  如果 2 失败：                                      │
│  1. ReleaseBudget（补偿）                           │
└─────────────────────────────────────────────────────┘
```

### 4.2 Go 实现 Saga

```go
package saga

import (
    "context"
)

// Step  Saga 步骤
type Step struct {
    Name       string
    Execute    func(context.Context) error
    Compensate func(context.Context) error
}

// SagaEngine Saga 引擎
type SagaEngine struct {
    steps []Step
}

// Execute 执行 Saga
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
                    // 补偿失败，记录日志
                    log.Printf("compensation failed for step %s: %v",
                        se.steps[executed[j]].Name, compensateErr)
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
                Name: "execute_bid",
                Execute: func(ctx context.Context) error {
                    // 执行竞价
                    return executeBid(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    // 竞价失败，无需补偿
                    return nil
                },
            },
            {
                Name: "deduct_budget",
                Execute: func(ctx context.Context) error {
                    // 扣减预算
                    return deductBudget(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    // 扣减失败，恢复预留
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
                    // 记录失败，删除记录
                    return deleteBidRecord(ctx)
                },
            },
        },
    }
}
```

### 4.3 Choreography Saga（协同式 Saga）

```
编排式 Saga：有中央协调器
协同式 Saga：每个服务发布事件，其他服务监听

Event Flow:
1. BidService 发布 BidRequested
2. BudgetService 监听 → 预留预算 → 发布 BudgetReserved
3. PricingService 监听 → 计算价格 → 发布 PriceCalculated
4. RecordingService 监听 → 记录竞价 → 发布 BidRecorded
5. 任何一步失败 → 发布补偿事件

优点：
- 服务之间松耦合
- 易于扩展

缺点：
- 难以追踪整体流程
- 调试困难
```

---

## 第五部分：生产排障案例

### 5.1 Saga 补偿失败

```
现象：竞价成功但预算扣减失败，补偿也失败

排查：
1. 检查 Saga 日志
2. 检查补偿方法是否正确
3. 检查数据库连接

解决方案：
1. 实现幂等性
2. 使用死信队列
3. 人工介入
```

```go
// 幂等性保证
func (s *SagaService) ExecuteStep(ctx context.Context, step Step, id string) error {
    // 检查是否已执行
    if s.isStepExecuted(id) {
        return nil
    }
    
    err := step.Execute(ctx)
    if err != nil {
        return err
    }
    
    // 标记已执行
    s.markStepExecuted(id)
    
    return nil
}
```

### 5.2 CQRS 数据不一致

```
现象：写操作成功，但读操作查不到

排查：
1. 检查事件发布是否成功
2. 检查读模型更新是否延迟
3. 检查是否有并发问题

解决方案：
1. 使用最终一致性
2. 添加重试机制
3. 监控数据一致性
```

```go
// 事件处理重试
func (eh *EventHandler) Handle(event DomainEvent) error {
    maxRetries := 3
    for i := 0; i < maxRetries; i++ {
        err := eh.processEvent(event)
        if err == nil {
            return nil
        }
        
        if i < maxRetries-1 {
            time.Sleep(time.Duration(i+1) * time.Second)
        }
    }
    
    return fmt.Errorf("event processing failed after %d retries", maxRetries)
}
```

---

## 第六部分：自测题

### 问题 1
DDD 中聚合根的作用是什么？

<details>
<summary>查看答案</summary>

1. **一致性边界**：保证聚合内数据一致
2. **事务边界**：一个聚合一个事务
3. **业务规则**：封装业务逻辑
4. **引用方式**：其他聚合通过 ID 引用
5. **Go 实现**：BidAggregate

</details>

### 问题 2
CQRS 相比传统 CRUD 有什么优势？

<details>
<summary>查看答案</summary>

1. **读写分离**：读模型可以独立优化
2. **扩展性**：读写可以独立扩展
3. **事件溯源**：可以重建历史状态
4. **性能**：读模型可以用 Elasticsearch
5. **Go 实现**：CommandHandler/QueryHandler

</details>

### 问题 3
Saga 相比 2PC 有什么优势？

<details>
<summary>查看答案</summary>

1. **无锁**：不需要分布式锁
2. **高性能**：不需要两阶段提交
3. **容错性**：单步失败只补偿该步
4. **实现简单**：不需要事务管理器
5. **Go 实现**：SagaEngine

</details>

---

*本文档基于微服务架构实战整理。*