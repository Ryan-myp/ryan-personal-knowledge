# 事件驱动架构深度解析

> 深入事件驱动架构：事件溯源、CQRS、消息队列、分布式事件。
> 源码级分析，包含生产环境实践。
> 适用对象：架构师、后端工程师

---

## 1. 事件溯源

### 1.1 核心概念

```
事件溯源原理：

├── 状态 = 事件流
│   └── 通过事件重建状态
│
├── 不可变性
│   └── 事件一旦创建不可修改
│
└── 时间点回溯
    └── 可以回溯到任意时间点
```

### 1.2 Go 实现事件溯源

```go
// event_sourcing.go

package eda

import (
    "sync"
    "time"
)

type EventStore struct {
    events  map[string][]DomainEvent
    mu      sync.RWMutex
}

type DomainEvent struct {
    EventID     string    `json:"event_id"`
    AggregateID string    `json:"aggregate_id"`
    Type        string    `json:"type"`
    Data        []byte    `json:"data"`
    Timestamp   time.Time `json:"timestamp"`
    Version     int       `json:"version"`
}

type Aggregate struct {
    ID          string
    Events      []DomainEvent
    State       interface{}
    Version     int
}

func (es *EventStore) Append(event DomainEvent) error {
    es.mu.Lock()
    defer es.mu.Unlock()
    
    es.events[event.AggregateID] = append(
        es.events[event.AggregateID], event,
    )
    return nil
}

func (es *EventStore) GetEvents(aggregateID string) []DomainEvent {
    es.mu.RLock()
    defer es.mu.RUnlock()
    return es.events[aggregateID]
}

func (agg *Aggregate) LoadFromEvents(events []DomainEvent) {
    agg.Events = events
    agg.Version = len(events)
    
    // 重放事件
    for _, event := range events {
        agg.Apply(event)
    }
}
```

---

## 2. CQRS

### 2.1 架构设计

```
CQRS架构：

├── 命令侧 (Command Side)
│   ├── 写入模型
│   ├── 业务逻辑
│   └── 事件发布
│
├── 查询侧 (Query Side)
│   ├── 读取模型
│   ├── 视图模型
│   └── 缓存优化
│
└── 事件同步
    └── 异步更新
```

### 2.2 Go 实现 CQRS

```go
// cqrs.go

package eda

import (
    "context"
    "sync"
)

type CommandHandler struct {
    repository *Repository
    eventBus   *EventBus
}

type QueryHandler struct {
    readModel *ReadModel
}

type Command struct {
    ID          string
    AggregateID string
    Type        string
    Data        map[string]interface{}
}

type Query struct {
    ID      string
    Type    string
    Filter  map[string]interface{}
}

type Result struct {
    Success bool
    Data    interface{}
    Error   error
}

func (ch *CommandHandler) Handle(ctx context.Context, cmd *Command) (*Result, error) {
    // 1. 加载聚合
    agg := ch.repository.Load(cmd.AggregateID)
    
    // 2. 执行命令
    err := agg.Execute(cmd)
    if err != nil {
        return nil, err
    }
    
    // 3. 保存聚合
    events := agg.GetUncommittedEvents()
    ch.repository.Save(agg)
    
    // 4. 发布事件
    ch.eventBus.Publish(events...)
    
    return &Result{Success: true}, nil
}

func (qh *QueryHandler) Handle(ctx context.Context, query *Query) (*Result, error) {
    // 查询读取模型
    data := qh.readModel.Query(query)
    return &Result{Data: data}, nil
}
```

---

## 3. 消息队列

### 3.1 Kafka架构

```
Kafka消息队列：

├── Producer (生产者)
│   └── 发送消息
│
├── Broker (代理)
│   ├── 存储消息
│   └── 处理请求
│
├── Consumer (消费者)
│   └── 消费消息
│
└── ZooKeeper
    └── 协调管理
```

### 3.2 Go 实现消息队列

```go
// message_queue.go

package eda

import (
    "sync"
)

type MessageQueue interface {
    Produce(topic string, message []byte) error
    Consume(topic string, handler func([]byte)) error
    Subscribe(topic string) (<-chan []byte, error)
}

type KafkaProducer struct {
    brokers []string
    mu      sync.Mutex
}

type KafkaConsumer struct {
    brokers []string
    topic   string
    mu      sync.Mutex
}

type EventBus struct {
    handlers map[string][]func([]byte)
    mu       sync.Mutex
}

func NewEventBus() *EventBus {
    return &EventBus{
        handlers: make(map[string][]func([]byte)),
    }
}

func (eb *EventBus) Publish(topic string, data []byte) {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    
    for _, handler := range eb.handlers[topic] {
        go handler(data)
    }
}

func (eb *EventBus) Subscribe(topic string, handler func([]byte)) {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    
    eb.handlers[topic] = append(eb.handlers[topic], handler)
}
```

---

## 4. 分布式事件

### 4.1 事件流架构

```
分布式事件流：

├── 事件发布
│   ├── 领域事件
│   └── 基础设施事件
│
├── 事件处理
│   ├── 同步处理
│   └── 异步处理
│
├── 事件存储
│   ├── 持久化
│   └── 归档
│
└── 事件回放
    ├── 数据修复
    └── 功能扩展
```

### 4.2 Go 实现分布式事件

```go
// distributed_events.go

package eda

import (
    "sync"
)

type DistributedEventStore struct {
    partitions map[int]*Partition
    mu         sync.Mutex
}

type Partition struct {
    ID       int
    Events   []DomainEvent
    Offset   int64
    mu       sync.Mutex
}

func (ds *DistributedEventStore) Append(topic string, event DomainEvent) error {
    partition := ds.getPartition(topic, event.AggregateID)
    partition.mu.Lock()
    defer partition.mu.Unlock()
    
    event.Version = int(partition.Offset)
    partition.Events = append(partition.Events, event)
    partition.Offset++
    
    return nil
}

func (ds *DistributedEventStore) Replay(topic string, fromOffset int64) []DomainEvent {
    partition := ds.getPartition(topic, "")
    partition.mu.Lock()
    defer partition.mu.Unlock()
    
    var events []DomainEvent
    for _, event := range partition.Events {
        if int64(event.Version) >= fromOffset {
            events = append(events, event)
        }
    }
    return events
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 模式 | 作用 |
|------|------|
| 事件溯源 | 状态重建 |
| CQRS | 读写分离 |
| 消息队列 | 异步解耦 |
| 分布式事件 | 事件流处理 |

### 5.2 最佳实践

- [ ] 合理设计事件模型
- [ ] 保证事件幂等性
- [ ] 监控事件延迟
- [ ] 设计事件回放机制

---

*最后更新：2026-08-11*
*作者：Ryan*
