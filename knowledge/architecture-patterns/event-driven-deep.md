# 事件驱动架构 (EDA) 深度实战

## 一、EDA 核心原理

### 1.1 事件驱动 vs 同步调用

传统同步调用中，服务之间紧密耦合，任何一个服务故障都会影响整个链路。EDA 通过事件实现异步解耦。

**同步调用问题：**
```
OrderService ──→ InventoryService ──→ PaymentService
     │                   │                       │
     └──── 阻塞等待 ──────┘                       │
                                                  │
                                         任一故障 → 整体失败
```

**EDA 优势：**
```
OrderService ──→ [OrderCreated Event] ──→ InventoryService
                                     ──→ PaymentService
                                     ──→ NotificationService
                                     
  服务间松耦合，故障隔离
```

### 1.2 核心组件

```
Event Producer (事件生产者)
├── 业务逻辑产生事件
├── 发布事件到 Event Bus
└── 示例: 订单创建 → OrderCreated 事件

Event Bus / Message Broker (事件总线)
├── 接收事件
├── 路由事件
├── 保证交付
└── 示例: Kafka, RabbitMQ, Redis Streams

Event Consumer (事件消费者)
├── 订阅感兴趣的事件
├── 处理事件
└── 示例: 库存服务监听 OrderCreated

Event Store (事件存储)
├── 持久化所有事件
├── 支持事件重放
└── 用于 Event Sourcing
```

## 二、Kafka 实现 EDA

### 2.1 Kafka 架构

```
Producer (生产者)
├── 发送消息到 Topic
└── 分区策略: Key Hash / Round Robin

Topic (主题)
├── 逻辑分类
└── 示例: orders, payments, inventory

Partition (分区)
├── 物理存储单元
├── 并行处理
└── 有序性保证 (分区内)

Consumer Group (消费者组)
├── 负载均衡
├── 每个分区只能被组内一个消费者消费
└── 扩容: 增加消费者

Broker (节点)
├── 存储分区数据
├── 处理读写请求
└── 副本同步
```

### 2.2 Go 实现

```go
package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

type OrderCreated struct {
	OrderID   string    `json:"order_id"`
	UserID    string    `json:"user_id"`
	Items     []Item    `json:"items"`
	Total     float64   `json:"total"`
	Timestamp time.Time `json:"timestamp"`
}

type Item struct {
	ProductID string  `json:"product_id"`
	Qty       int     `json:"qty"`
	Price     float64 `json:"price"`
}

func main() {
	writer := kafka.NewWriter(kafka.WriterConfig{
		Brokers:  []string{"localhost:9092"},
		Topic:    "orders",
		Balancer: &kafka.LeastBytes{},
	})
	defer writer.Close()

	order := OrderCreated{
		OrderID: "ORD-001",
		UserID:  "USER-123",
		Items: []Item{
			{ProductID: "PROD-001", Qty: 2, Price: 49.99},
		},
		Total:     99.98,
		Timestamp: time.Now(),
	}

	data, _ := json.Marshal(order)

	ctx := context.Background()
	err := writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(order.OrderID),
		Value: data,
		Time:  time.Now(),
	})
	if err != nil {
		log.Fatalf("Failed to send message: %v", err)
	}

	log.Println("Order created event published")
}
```

## 三、事件处理模式

### 3.1 事件幂等处理

```go
type EventProcessor struct {
	processedEvents map[string]bool
	mu              sync.RWMutex
}

func (p *EventProcessor) Process(event Event) error {
	p.mu.RLock()
	if p.processedEvents[event.ID] {
		p.mu.RUnlock()
		return nil // 已处理，跳过
	}
	p.mu.RUnlock()

	err := p.handleEvent(event)
	if err != nil {
		return err
	}

	p.mu.Lock()
	p.processedEvents[event.ID] = true
	p.mu.Unlock()

	return nil
}
```

### 3.2 可靠消息投递

```go
type ReliableMessageQueue struct {
	broker   MessageBroker
	store    *MessageStore
	retryCnt int
}

func (q *ReliableMessageQueue) Send(msg Message) error {
	// 持久化消息
	if err := q.store.Save(msg); err != nil {
		return err
	}

	// 发送到 Broker
	if err := q.broker.Publish(msg); err != nil {
		return q.retrySend(msg)
	}

	// 标记为已发送
	q.store.MarkSent(msg.ID)
	return nil
}

func (q *ReliableMessageQueue) retrySend(msg Message) error {
	q.retryCnt++
	if q.retryCnt > 3 {
		return q.deadLetterQueue.Add(msg)
	}

	time.Sleep(time.Duration(q.retryCnt) * time.Second)
	return q.Send(msg)
}
```

## 四、事件模式详解

### 4.1 发布-订阅模式

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Publisher  │────>│  Event Bus  │────>│  Subscriber │
│             │     │             │     │    A        │
│  OrderCreated│     │  Topics:    │     └─────────────┘
│  ItemAdded  │     │  - orders   │     ┌─────────────┐
│  OrderPaid  │     │  - payments │────>│  Subscriber │
└─────────────┘     └─────────────┘     │    B        │
                                        └─────────────┘
```

### 4.2 事件溯源中的事件处理

```go
type EventSourcedAggregate struct {
	ID        string
	Version   int
	Events    []Event
	IsNew     bool
}

func (a *EventSourcedAggregate) Apply(event Event) error {
	if a.IsNew && a.Version > 0 {
		return fmt.Errorf("aggregate already has events")
	}
	
	a.Events = append(a.Events, event)
	a.Version++
	
	switch event.Type {
	case "OrderCreated":
		a.applyOrderCreated(event)
	case "OrderPaid":
		a.applyOrderPaid(event)
	case "OrderCancelled":
		a.applyOrderCancelled(event)
	}
	
	return nil
}

func (a *EventSourcedAggregate) applyOrderCreated(event Event) {
	// 解析事件数据
	var data OrderCreatedData
	json.Unmarshal(event.Data, &data)
	a.UserID = data.UserID
	a.Items = data.Items
	a.Total = data.Total
	a.Status = "created"
}

func (a *EventSourcedAggregate) applyOrderPaid(event Event) {
	a.Status = "paid"
	a.PaymentID = string(event.Data)
}

func (a *EventSourcedAggregate) applyOrderCancelled(event Event) {
	a.Status = "cancelled"
}
```

### 4.3 事件版本管理

```go
type EventVersionManager struct {
	schemas map[string][]EventSchema
	mu      sync.RWMutex
}

type EventSchema struct {
	Version int
	Schema  []byte
}

func (m *EventVersionManager) RegisterSchema(eventType string, version int, schema []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	
	m.schemas[eventType] = append(m.schemas[eventType], EventSchema{
		Version: version,
		Schema:  schema,
	})
}

func (m *EventVersionManager) GetLatestSchema(eventType string) ([]byte, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	
	schemas, ok := m.schemas[eventType]
	if !ok || len(schemas) == 0 {
		return nil, fmt.Errorf("no schema for event type: %s", eventType)
	}
	
	latest := schemas[len(schemas)-1]
	return latest.Schema, nil
}
```

## 五、自测题

1. EDA 相比传统同步调用有什么优势？
2. Kafka 的分区策略有哪些？
3. 如何实现事件的幂等处理？
4. 事件溯源中如何处理事件版本升级？

## 六、动手验证

```bash
# 1. 搭建 Kafka 集群
# 2. 实现事件生产者
# 3. 实现事件消费者
# 4. 测试事件处理
```
