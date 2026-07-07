# CQRS 与 Event Sourcing 深度实战

## 一、CQRS 核心原理

### 1.1 读写分离架构

传统架构中，同一个模型既要处理写操作又要处理查询。当查询复杂时，会影响写入性能。CQRS 将读写模型分离，各自优化。

**适用场景：**
- 读多写少（10:1 以上）
- 复杂查询场景
- 需要独立扩展读写能力

### 1.2 为什么需要 CQRS？

```
传统 CRUD 架构:
┌─────────────┐
│  Domain Model │
│  (读写共用)   │
└──────┬──────┘
       │
  ┌────┴────┐
  │ 查询    │ 写入
  │ 复杂    │ 简单
  └─────────┘

CQRS 架构:
┌─────────────┐    ┌─────────────┐
│  Command    │    │  Query      │
│  Model      │    │  Model      │
└──────┬──────┘    └──────┬──────┘
       │                  │
  ┌────┴────┐        ┌────┴────┐
  │ 优化写入 │        │ 优化查询 │
  └─────────┘        └─────────┘
```

**Trade-off 分析：**

| 维度 | 传统 CRUD | CQRS |
|------|-----------|------|
| 实现复杂度 | 低 | 高 |
| 读性能 | 一般 | 高（可独立优化） |
| 写性能 | 高 | 高 |
| 数据一致性 | 强 | 最终一致 |
| 适用场景 | 简单 CRUD | 复杂查询 + 审计需求 |

### 1.3 Go 实现 CQRS

```go
package cqrs

import (
	"context"
	"fmt"
	"reflect"
	"sync"
)

// Command 命令接口
type Command interface {
	Validate() error
}

// Query 查询接口
type Query interface{}

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

func (bus *CommandBus) Register(cmdType string, handler CommandHandler) {
	bus.mu.Lock()
	defer bus.mu.Unlock()
	bus.handlers[cmdType] = handler
}

func (bus *CommandBus) Dispatch(ctx context.Context, cmd Command) error {
	if err := cmd.Validate(); err != nil {
		return err
	}
	
	cmdType := reflect.TypeOf(cmd).String()
	handler, ok := bus.handlers[cmdType]
	if !ok {
		return fmt.Errorf("no handler for command: %s", cmdType)
	}
	
	return handler.Handle(ctx, cmd)
}

// QueryBus 查询总线
type QueryBus struct {
	handlers map[string]QueryHandler
	mu       sync.RWMutex
}

func (bus *QueryBus) Register(queryType string, handler QueryHandler) {
	bus.mu.Lock()
	defer bus.mu.Unlock()
	bus.handlers[queryType] = handler
}

func (bus *QueryBus) Query(ctx context.Context, query Query) (interface{}, error) {
	queryType := reflect.TypeOf(query).String()
	handler, ok := bus.handlers[queryType]
	if !ok {
		return nil, fmt.Errorf("no handler for query: %s", queryType)
	}
	return handler.Handle(ctx, query)
}
```

## 二、Event Sourcing 深度解析

### 2.1 核心概念

Event Sourcing 不存储当前状态，而是存储所有状态变更事件。通过重放事件重建状态。

**优势：**
- 完整审计轨迹
- 支持时间旅行
- 易于调试和追踪

### 2.2 事件溯源 vs 传统存储

```
传统存储:
┌─────────────┐
│  Order Table │
│  id: 1       │
│  status: paid│
│  total: 99.9 │
└─────────────┘
只能看到当前状态

事件溯源:
┌─────────────┐
│  Event 1:    │
│  OrderCreated│
├─────────────┤
│  Event 2:    │
│  ItemAdded   │
├─────────────┤
│  Event 3:    │
│  OrderPaid   │
└─────────────┘
可以看到完整历史
```

### 2.3 Go 实现

```go
package eventsourcing

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

// Event 领域事件
type Event struct {
	ID        string    `json:"id"`
	Type      string    `json:"type"`
	Aggregate string    `json:"aggregate"`
	Data      []byte    `json:"data"`
	Version   int       `json:"version"`
	Timestamp time.Time `json:"timestamp"`
}

// Aggregate 聚合根基类
type Aggregate struct {
	ID      string
	Version int
	Events  []Event
	mu      sync.Mutex
}

// EventStore 事件存储接口
type EventStore interface {
	Save(events []Event) error
	Get(aggregateID string) ([]Event, error)
}

// Order 订单聚合根
type Order struct {
	*Aggregate
	UserID  string
	Items   []OrderItem
	Status  string
	Total   float64
}

type OrderItem struct {
	ProductID string
	Qty       int
	Price     float64
}

func NewOrder(id, userID string, items []OrderItem) *Order {
	order := &Order{
		Aggregate: &Aggregate{ID: id},
		UserID:    userID,
		Items:     items,
		Status:    "created",
	}
	
	total := 0.0
	for _, item := range items {
		total += item.Price * float64(item.Qty)
	}
	order.Total = total
	
	data, _ := json.Marshal(map[string]interface{}{
		"user_id": userID,
		"items":   items,
		"total":   total,
	})
	event := Event{
		ID:        generateID(),
		Type:      "OrderCreated",
		Aggregate: id,
		Data:      data,
		Version:   1,
		Timestamp: time.Now(),
	}
	
	order.Events = append(order.Events, event)
	order.Version++
	return order
}

func (o *Order) Pay(paymentID string) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	if o.Status != "created" {
		return fmt.Errorf("order not in created status")
	}
	
	data, _ := json.Marshal(map[string]interface{}{
		"payment_id": paymentID,
	})
	event := Event{
		ID:        generateID(),
		Type:      "OrderPaid",
		Aggregate: o.ID,
		Data:      data,
		Version:   o.Version + 1,
		Timestamp: time.Now(),
	}
	
	o.Events = append(o.Events, event)
	o.Version++
	o.Status = "paid"
	return nil
}

func (o *Order) RebuildFromEvents(events []Event) {
	o.Events = events
	o.Version = len(events)
	
	for _, event := range events {
		switch event.Type {
		case "OrderCreated":
			var data map[string]interface{}
			json.Unmarshal(event.Data, &data)
			o.UserID = data["user_id"].(string)
			o.Total = data["total"].(float64)
			o.Status = "created"
		case "OrderPaid":
			o.Status = "paid"
		}
	}
}
```

## 三、投影 (Projection)

### 3.1 投影模式

```
事件流:
├── OrderCreated ──→ 订单列表投影
├── OrderPaid  ──→ 支付统计投影
├── OrderShipped ──→ 物流跟踪投影
└── OrderCancelled ──→ 取消统计投影

每个投影独立优化查询
```

### 3.2 Go 实现投影

```go
package projection

import (
	"context"
	"sync"
)

type Projection interface {
	Name() string
	Handle(event Event) error
	Query(ctx context.Context, params map[string]interface{}) (interface{}, error)
}

type OrderListProjection struct {
	orders map[string]*OrderView
	mu     sync.RWMutex
}

type OrderView struct {
	ID     string
	UserID string
	Status string
	Total  float64
}

func (p *OrderListProjection) Name() string {
	return "OrderList"
}

func (p *OrderListProjection) Handle(event Event) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	switch event.Type {
	case "OrderCreated":
		var data map[string]interface{}
		json.Unmarshal(event.Data, &data)
		p.orders[event.Aggregate] = &OrderView{
			ID:     event.Aggregate,
			UserID: data["user_id"].(string),
			Status: "created",
			Total:  data["total"].(float64),
		}
	case "OrderPaid":
		if order, ok := p.orders[event.Aggregate]; ok {
			order.Status = "paid"
		}
	}
	return nil
}

func (p *OrderListProjection) Query(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	
	// 根据 params 过滤
	userID, ok := params["user_id"]
	if !ok {
		return p.orders, nil
	}
	
	result := make(map[string]*OrderView)
	for id, order := range p.orders {
		if order.UserID == userID.(string) {
			result[id] = order
		}
	}
	return result, nil
}
```

## 四、自测题

1. CQRS 的核心思想是什么？
2. Event Sourcing 相比传统存储有什么优势？
3. 投影的作用是什么？如何实现？

## 五、动手验证

```bash
# 1. 实现 Event Store
# 2. 创建聚合根
# 3. 实现投影
# 4. 测试 CQRS 查询
```
