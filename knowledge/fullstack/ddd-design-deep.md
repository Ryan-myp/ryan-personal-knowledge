# DDD领域驱动设计 - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DDD分层架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   用户界面层 (UI Layer)                                                  │
│   ├── Controllers                                                        │
│   ├── ViewModels                                                         │
│   └── DTOs                                                              │
│                                                                         →
│   应用层 (Application Layer)                                             │
│   ├── Application Services                                                │
│   ├── Commands                                                           │
│   └── Events                                                             │
│                                                                         →
│   领域层 (Domain Layer)                                                  │
│   ├── Entities                                                           │
│   ├── Value Objects                                                      │
│   ├── Aggregates                                                         │
│   ├── Domain Events                                                      │
│   └── Domain Services                                                    │
│                                                                         →
│   基础设施层 (Infrastructure Layer)                                        │
│   ├── Repositories                                                       │
│   ├── Message Queues                                                     │
│   ├── Database Access                                                    │
│   └── External Services                                                  │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、聚合根实现

```go
type OrderAggregate struct {
    ID         string
    CustomerID string
    Items      []OrderItem
    Status     OrderStatus
    CreatedAt  time.Time
}

func (o *OrderAggregate) AddItem(item OrderItem) error {
    if o.Status != OrderStatusDraft {
        return fmt.Errorf("order is not in draft status")
    }
    o.Items = append(o.Items, item)
    o.AddDomainEvent(&OrderItemAddedEvent{
        OrderID: o.ID,
        Item:    item,
    })
    return nil
}

func (o *OrderAggregate) Confirm() error {
    if len(o.Items) == 0 {
        return fmt.Errorf("order has no items")
    }
    o.Status = OrderStatusConfirmed
    o.AddDomainEvent(&OrderConfirmedEvent{
        OrderID: o.ID,
    })
    return nil
}
```

## 三、面试高频题

### Q1: DDD核心概念？

```
A:
1. 聚合根
2. 值对象
3. 领域服务
4. 仓储
```

### Q2: 如何选择聚合边界？

```
A:
1. 事务一致性
2. 业务语义
3. 访问频率
```

## 四、自测题

1. 解释DDD分层
2. 如何设计聚合根？
3. 如何实现领域事件？

---

## 参考文档

- [DDD官方文档](https://domaindrivendesign.org/)
- [CQRS模式](https://docs.microsoft.com/en-us/azure/architecture/patterns/cqrs)
