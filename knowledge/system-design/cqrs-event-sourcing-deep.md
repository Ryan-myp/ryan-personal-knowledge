# CQRS 与 Event Sourcing 架构深度解析

> 深入 CQRS（命令查询职责分离）和 Event Sourcing（事件溯源）架构模式。
> 适用对象：分布式系统架构师、领域驱动设计实践者

---

## 1. CQRS 核心概念

### 1.1 为什么需要 CQRS

```
传统架构问题:
┌─────────────────────────────────────────────────────────────────┐
│                        单一模型                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   写入: 复杂业务逻辑、一致性要求高                              │
│   读取: 高频查询、多种视图需求、缓存优化                        │
│                                                                 │
│   问题:                                                         │
│   • ORM 难以同时优化读写                                        │
│   • 查询复杂导致 SQL 膨胀                                       │
│   • 读写争用锁                                                 │
│   • 水平扩展困难                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 CQRS 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       CQRS 架构模式                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐              │
│   │ Command  │────▶│  Command │────▶│  Write   │              │
│   │ Handler  │     │  Model   │     │  Side    │              │
│   └──────────┘     └──────────┘     └────┬─────┘              │
│                                          │                     │
│                                          ▼                     │
│                                    ┌──────────┐               │
│                                    │  Event   │               │
│                                    │  Store   │               │
│                                    └────┬─────┘               │
│                                         │                      │
│                    ┌────────────────────┼─────────────────┐   │
│                    │                    │                  │   │
│                    ▼                    ▼                  │   │
│              ┌──────────┐        ┌──────────┐            │   │
│              │  Query   │        │  Project │            │   │
│              │  Handler │◀───────│  Builder │            │   │
│              └────┬─────┘        └──────────┘            │   │
│                   │                                       │   │
│                   ▼                                       │   │
│              ┌──────────┐                                 │   │
│              │  Read    │                                 │   │
│              │  Model   │                                 │   │
│              └──────────┘                                 │   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Go 实现示例

```go
package cqrs

import (
    "context"
    "sync"
)

// Command 命令接口
type Command interface {
    CommandName() string
}

// Query 查询接口
type Query interface {
    QueryName() string
}

// CommandHandler 命令处理器
type CommandHandler interface {
    Handle(ctx context.Context, cmd Command) error
}

// QueryHandler 查询处理器
type QueryHandler interface {
    Handle(ctx context.Context, query Query) (interface{}, error)
}

// CommandBus 命令总线
type CommandBus struct {
    handlers map[string]CommandHandler
    mu       sync.RWMutex
}

func NewCommandBus() *CommandBus {
    return &CommandBus{
        handlers: make(map[string]CommandHandler),
    }
}

func (cb *CommandBus) Register(cmd Command, handler CommandHandler) {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    cb.handlers[cmd.CommandName()] = handler
}

func (cb *CommandBus) Dispatch(ctx context.Context, cmd Command) error {
    cb.mu.RLock()
    handler, ok := cb.handlers[cmd.CommandName()]
    cb.mu.RUnlock()
    
    if !ok {
        return fmt.Errorf("no handler for command: %s", cmd.CommandName())
    }
    
    return handler.Handle(ctx, cmd)
}

// QueryBus 查询总线
type QueryBus struct {
    handlers map[string]QueryHandler
    mu       sync.RWMutex
}

func NewQueryBus() *QueryBus {
    return &QueryBus{
        handlers: make(map[string]QueryHandler),
    }
}

func (qb *QueryBus) Register(query Query, handler QueryHandler) {
    qb.mu.Lock()
    defer qb.mu.Unlock()
    qb.handlers[query.QueryName()] = handler
}

func (qb *QueryBus) Dispatch(ctx context.Context, query Query) (interface{}, error) {
    qb.mu.RLock()
    handler, ok := qb.handlers[query.QueryName()]
    qb.mu.RUnlock()
    
    if !ok {
        return nil, fmt.Errorf("no handler for query: %s", query.QueryName())
    }
    
    return handler.Handle(ctx, query)
}
```

---

## 2. Event Sourcing 核心概念

### 2.1 事件溯源原理

```
传统方式 vs Event Sourcing:

传统方式:
┌─────────────────────────────────────────────────────────────────┐
│  Order Table                                                     │
│  ┌────────┬──────────┬─────────┬─────────────┐                 │
│  │ ID     │ Status   │ Amount  │ UpdatedAt   │                 │
│  ├────────┼──────────┼─────────┼─────────────┤                 │
│  │ 1001   │ paid     │ 99.00   │ 2026-01-01  │ ← 当前状态      │
│  └────────┴──────────┴─────────┴─────────────┘                 │
│                                                                 │
│  问题: 历史状态丢失，无法审计                                   │
└─────────────────────────────────────────────────────────────────┘

Event Sourcing:
┌─────────────────────────────────────────────────────────────────┐
│  Order Events                                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Event 1: OrderCreated (2026-01-01 10:00:00)              │  │
│  │   - OrderID: 1001                                        │  │
│  │   - Amount: 99.00                                        │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ Event 2: PaymentReceived (2026-01-01 10:05:00)          │  │
│  │   - OrderID: 1001                                        │  │
│  │   - Amount: 99.00                                        │  │
│  │   - PaymentMethod: credit_card                           │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ Event 3: OrderShipped (2026-01-02 14:00:00)             │  │
│  │   - OrderID: 1001                                        │  │
│  │   - TrackingNumber: SF123456789                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  优势: 完整审计轨迹、支持时间旅行、便于重构                     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
package eventsourcing

import (
    "context"
    "crypto/sha256"
    "encoding/json"
    "fmt"
    "time"
)

// DomainEvent 领域事件
type DomainEvent struct {
    EventID     string    `json:"event_id"`
    AggregateID string    `json:"aggregate_id"`
    EventType   string    `json:"event_type"`
    Data        []byte    `json:"data"`
    Timestamp   time.Time `json:"timestamp"`
    Version     int       `json:"version"`
}

// EventStore 事件存储接口
type EventStore interface {
    Save(ctx context.Context, events []DomainEvent) error
    Load(ctx context.Context, aggregateID string) ([]DomainEvent, error)
}

// AggregateRoot 聚合根基类
type AggregateRoot struct {
    ID           string
    Version      int
    appliedEvents []DomainEvent
}

// Apply 应用事件到聚合根
func (a *AggregateRoot) Apply(event DomainEvent) {
    a.appliedEvents = append(a.appliedEvents, event)
    a.Version++
    
    // 分发到具体处理逻辑
    switch event.EventType {
    case "order_created":
        a.handleOrderCreated(event)
    case "payment_received":
        a.handlePaymentReceived(event)
    case "order_shipped":
        a.handleOrderShipped(event)
    }
}

func (a *AggregateRoot) handleOrderCreated(event DomainEvent) {
    // 应用 OrderCreated 事件
}

func (a *AggregateRoot) handlePaymentReceived(event DomainEvent) {
    // 应用 PaymentReceived 事件
}

func (a *AggregateRoot) handleOrderShipped(event DomainEvent) {
    // 应用 OrderShipped 事件
}

// GetUncommittedEvents 获取未提交事件
func (a *AggregateRoot) GetUncommittedEvents() []DomainEvent {
    events := a.appliedEvents
    a.appliedEvents = nil
    return events
}

// Event Sourced Aggregate 示例
type OrderAggregate struct {
    AggregateRoot
    Status     string
    Amount     float64
    TrackingNo string
}

func NewOrderAggregate(orderID string, amount float64) *OrderAggregate {
    return &OrderAggregate{
        AggregateRoot: AggregateRoot{ID: orderID},
        Amount:        amount,
    }
}

func (o *OrderAggregate) Create() []DomainEvent {
    event := DomainEvent{
        EventID:     generateEventID(),
        AggregateID: o.ID,
        EventType:   "order_created",
        Data:        toJSON(map[string]interface{}{"amount": o.Amount}),
        Timestamp:   time.Now(),
    }
    o.Apply(event)
    return []DomainEvent{event}
}

func (o *OrderAggregate) ReceivePayment(paymentMethod string) []DomainEvent {
    event := DomainEvent{
        EventID:     generateEventID(),
        AggregateID: o.ID,
        EventType:   "payment_received",
        Data:        toJSON(map[string]interface{}{"method": paymentMethod, "amount": o.Amount}),
        Timestamp:   time.Now(),
    }
    o.Apply(event)
    return []DomainEvent{event}
}

func (o *OrderAggregate) Ship(trackingNo string) []DomainEvent {
    event := DomainEvent{
        EventID:     generateEventID(),
        AggregateID: o.ID,
        EventType:   "order_shipped",
        Data:        toJSON(map[string]interface{}{"tracking_no": trackingNo}),
        Timestamp:   time.Now(),
    }
    o.Apply(event)
    return []DomainEvent{event}
}

func generateEventID() string {
    data := fmt.Sprintf("%d", time.Now().UnixNano())
    hash := sha256.Sum256([]byte(data))
    return fmt.Sprintf("%x", hash[:8])
}

func toJSON(v interface{}) []byte {
    b, _ := json.Marshal(v)
    return b
}
```

---

## 3. 投影 (Projection) 模式

### 3.1 投影构建器

```go
package projection

import (
    "context"
    "database/sql"
)

// Projection 投影接口
type Projection interface {
    Name() string
    HandleEvent(ctx context.Context, event DomainEvent) error
}

// ProjectionBuilder 投影构建器
type ProjectionBuilder struct {
    db      *sql.DB
    events  chan DomainEvent
    done    chan struct{}
}

func NewProjectionBuilder(db *sql.DB) *ProjectionBuilder {
    return &ProjectionBuilder{
        db:     db,
        events: make(chan DomainEvent, 1000),
        done:   make(chan struct{}),
    }
}

// Subscribe 订阅事件流
func (pb *ProjectionBuilder) Subscribe(eventStream <-chan DomainEvent) {
    go func() {
        for event := range eventStream {
            pb.dispatch(event)
        }
    }()
}

// dispatch 分发事件到对应的投影处理器
func (pb *ProjectionBuilder) dispatch(event DomainEvent) {
    ctx := context.Background()
    
    switch event.EventType {
    case "order_created":
        pb.handleOrderCreated(ctx, event)
    case "payment_received":
        pb.handlePaymentReceived(ctx, event)
    case "order_shipped":
        pb.handleOrderShipped(ctx, event)
    }
}

func (pb *ProjectionBuilder) handleOrderCreated(ctx context.Context, event DomainEvent) {
    // 更新订单视图
    pb.updateOrderView(ctx, event, "created")
}

func (pb *ProjectionBuilder) handlePaymentReceived(ctx context.Context, event DomainEvent) {
    // 更新支付视图
    pb.updatePaymentView(ctx, event)
}

func (pb *ProjectionBuilder) updateOrderView(ctx context.Context, event DomainEvent, status string) {
    _, err := pb.db.ExecContext(ctx,
        "UPDATE order_views SET status = ? WHERE order_id = ?",
        status, event.AggregateID,
    )
    if err != nil {
        // 记录错误，继续处理
        logError(err)
    }
}
```

### 3.2 读模型优化

```sql
-- 优化的读模型表
CREATE TABLE order_views (
    order_id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    
    -- 查询优化索引
    INDEX idx_status (status),
    INDEX idx_created (created_at),
    INDEX idx_amount_range (amount)
);

-- 常见查询
-- 1. 按状态查询
SELECT * FROM order_views WHERE status = 'paid';

-- 2. 按时间范围查询
SELECT * FROM order_views 
WHERE created_at BETWEEN '2026-01-01' AND '2026-01-31';

-- 3. 分页查询
SELECT * FROM order_views 
ORDER BY created_at DESC 
LIMIT 20 OFFSET 0;
```

---

## 4. 一致性模型

### 4.1 最终一致性实现

```go
package consistency

import (
    "context"
    "time"
)

// EventuallyConsistentService 最终一致性服务
type EventuallyConsistentService struct {
    commandBus  *CommandBus
    queryBus    *QueryBus
    eventStream EventStream
}

// 写操作 - 立即生效
func (s *EventuallyConsistentService) CreateOrder(ctx context.Context, cmd *CreateOrderCommand) error {
    return s.commandBus.Dispatch(ctx, cmd)
}

// 读操作 - 可能短暂延迟
func (s *EventuallyConsistentService) GetOrder(ctx context.Context, orderID string) (*OrderView, error) {
    // 尝试读取
    view, err := s.queryBus.Dispatch(ctx, &GetOrderQuery{OrderID: orderID})
    if err != nil {
        return nil, err
    }
    
    // 检查数据新鲜度
    if time.Since(view.UpdatedAt) > 5*time.Second {
        // 触发重新投影
        s.eventStream.PublishRebuildEvent(orderID)
    }
    
    return view.(*OrderView), nil
}

// EventStream 事件流接口
type EventStream interface {
    Publish(event DomainEvent) error
    Subscribe(handler EventHandler) <-chan DomainEvent
    PublishRebuildEvent(aggregateID string) error
}

// EventHandler 事件处理器
type EventHandler func(ctx context.Context, event DomainEvent) error
```

---

## 5. 重构与迁移

### 5.1 逐步迁移策略

```
迁移路径:

Step 1: 双写阶段
┌─────────────┐     ┌─────────────┐
│  现有系统   │────▶│  事件流     │
│  (读写一体) │     │  (新系统)   │
└─────────────┘     └─────────────┘
       │                   │
       └───────────────────┘
              投影构建读模型

Step 2: 读写分离
┌─────────────┐     ┌─────────────┐
│  写操作     │────▶│  事件流     │
│  (新系统)   │     │             │
└─────────────┘     └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │  读模型     │
                    │  (优化视图) │
                    └─────────────┘

Step 3: 完全迁移
┌─────────────┐     ┌─────────────┐
│  新 CQRS    │     │  新读模型   │
│  系统       │────▶│             │
└─────────────┘     └─────────────┘
```

---

## 6. 生产实践 Checklist

- [ ] 设计不可变的事件 Schema（使用 Avro/Protobuf）
- [ ] 实现幂等的事件处理器
- [ ] 设置事件保留策略（归档/删除）
- [ ] 监控投影构建延迟
- [ ] 建立事件版本管理机制
- [ ] 准备回滚方案（快照 + 重放）

---

**参考**: Udi Dahan CQRS 指南、Martin Fowler Event Sourcing、Axon Framework 文档
