# 微服务分布式事务深度实战

## 一、分布式事务挑战

### 1.1 为什么需要分布式事务？

单体架构：单一数据库，ACID 保证
微服务架构：多个服务，多个数据库，跨服务调用

**传统方案的问题：**
- 2PC (两阶段提交)：阻塞式锁定，性能差，单点故障
- TCC (尝试-提交-取消)：代码侵入性强，实现复杂

### 1.2 最终一致性

```
强一致性 vs 最终一致性:

强一致性 (ACID):
├── 所有节点同时看到相同数据
├── 延迟高 (等待所有节点确认)
└── 可用性低 (任何节点故障影响整体)

最终一致性 (BASE):
├── 数据最终会一致
├── 延迟低 (本地事务立即提交)
└── 可用性高 (节点故障不影响整体)
```

## 二、Saga 模式

### 2.1 Saga 两种实现

**编排模式 (Orchestration)：**

```
中央协调器 (Orchestrator)
├── 控制整个 Saga 流程
├── 决定下一步执行哪个服务
├── 失败时协调补偿
└── 集中管理状态

流程:
Orchestrator → 服务 A → 服务 B → 服务 C
              ↖ 补偿 B ← 补偿 A ← 失败
```

**协同模式 (Choreography)：**

```
事件驱动，服务间通过事件协作
├── 服务 A 完成 → 发布事件
├── 服务 B 监听事件 → 执行 → 发布事件
└── 服务 C 监听事件 → 执行

流程:
服务 A → 事件 → 服务 B → 事件 → 服务 C
                ↑
                补偿事件
```

### 2.2 Go 实现 Saga 编排器

```go
package saga

import (
	"context"
	"fmt"
)

type SagaStep struct {
	Name       string
	Execute    func(ctx context.Context) error
	Compensate func(ctx context.Context) error
}

type Saga struct {
	steps   []SagaStep
	index   int
	results map[string]interface{}
}

func NewSaga() *Saga {
	return &Saga{
		steps:   make([]SagaStep, 0),
		results: make(map[string]interface{}),
	}
}

func (s *Saga) AddStep(name string, execute func(ctx context.Context) error, compensate func(ctx context.Context) error) *Saga {
	s.steps = append(s.steps, SagaStep{
		Name:       name,
		Execute:    execute,
		Compensate: compensate,
	})
	return s
}

func (s *Saga) Execute(ctx context.Context) error {
	for s.index < len(s.steps) {
		step := s.steps[s.index]
		if err := step.Execute(ctx); err != nil {
			fmt.Printf("Step %s failed: %v\n", step.Name, err)
			s.compensate(ctx)
			return err
		}
		s.index++
	}
	return nil
}

func (s *Saga) compensate(ctx context.Context) {
	for s.index >= 0 {
		s.index--
		step := s.steps[s.index]
		if err := step.Compensate(ctx); err != nil {
			fmt.Printf("Compensation for %s failed: %v\n", step.Name, err)
		}
	}
}
```

### 2.3 电商订单 Saga 示例

```go
func CreateOrderSaga(orderID, userID string) *Saga {
	saga := NewSaga()
	
	var inventoryID string
	var paymentID string
	
	saga.AddStep("CreateOrder",
		func(ctx context.Context) error {
			order := &Order{ID: orderID, UserID: userID, Status: "pending"}
			return db.CreateOrder(order)
		},
		func(ctx context.Context) error {
			db.DeleteOrder(orderID)
		},
	)
	
	saga.AddStep("DeductInventory",
		func(ctx context.Context) error {
			result := inventoryService.Deduct(orderID, 1)
			inventoryID = result.ID
			return nil
		},
		func(ctx context.Context) error {
			inventoryService.Refund(inventoryID)
		},
	)
	
	saga.AddStep("ProcessPayment",
		func(ctx context.Context) error {
			result := paymentService.Charge(orderID, 99.98)
			paymentID = result.ID
			return nil
		},
		func(ctx context.Context) error {
			paymentService.Refund(paymentID)
		},
	)
	
	saga.AddStep("ConfirmOrder",
		func(ctx context.Context) error {
			return db.UpdateOrderStatus(orderID, "confirmed")
		},
		func(ctx context.Context) error {
			db.UpdateOrderStatus(orderID, "cancelled")
		},
	)
	
	return saga
}
```

## 三、TCC 模式

### 3.1 Try-Confirm-Cancel

```go
type TCCService interface {
	Try(ctx context.Context, data interface{}) error
	Confirm(ctx context.Context, data interface{}) error
	Cancel(ctx context.Context, data interface{}) error
}

func (s *TransferService) Transfer(from, to string, amount float64) error {
	// Try 阶段
	if err := s.Try(from, -amount); err != nil {
		return err
	}
	if err := s.Try(to, amount); err != nil {
		s.Cancel(from, -amount)
		return err
	}
	
	// Confirm 阶段
	if err := s.Confirm(from, -amount); err != nil {
		s.Cancel(to, amount)
		return err
	}
	if err := s.Confirm(to, amount); err != nil {
		s.Cancel(from, -amount)
		return err
	}
	
	return nil
}
```

## 四、本地消息表模式

### 4.1 原理

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  业务服务    │     │  本地消息表   │     │  消息消费者   │
│             │     │              │     │             │
│ 1. 执行业务  │     │ 2. 插入消息  │     │ 3. 定时扫描  │
│    事务      │────>│    (同一事务)│────>│ 4. 发送消息  │
│             │     │ 5. 标记已发送 │     │ 6. 更新状态  │
└─────────────┘     └──────────────┘     └─────────────┘
```

### 4.2 Go 实现

```go
package localmessage

import (
	"context"
	"time"
)

type LocalMessage struct {
	ID        string
	Service   string
	Event     string
	Payload   string
	Status    string // pending, sent, failed
	CreatedAt time.Time
	UpdatedAt time.Time
}

type MessageRepository interface {
	Create(msg *LocalMessage) error
	UpdateStatus(id, status string) error
	FindPending(limit int) ([]*LocalMessage, error)
}

type MessageSender interface {
	Send(ctx context.Context, event string, payload string) error
}

type LocalMessageService struct {
	repo  MessageRepository
	sender MessageSender
}

func (s *LocalMessageService) ExecuteWithMessage(ctx context.Context, service, event string, payload string, fn func(ctx context.Context) error) error {
	msg := &LocalMessage{
		Service:   service,
		Event:     event,
		Payload:   payload,
		Status:    "pending",
		CreatedAt: time.Now(),
	}
	
	if err := s.repo.Create(msg); err != nil {
		return err
	}
	
	if err := fn(ctx); err != nil {
		return err
	}
	
	s.repo.UpdateStatus(msg.ID, "sent")
	return s.sender.Send(ctx, event, payload)
}

func (s *LocalMessageService) RetryPendingMessages(ctx context.Context) error {
	messages, err := s.repo.FindPending(100)
	if err != nil {
		return err
	}
	
	for _, msg := range messages {
		if err := s.sender.Send(ctx, msg.Event, msg.Payload); err != nil {
			msg.Status = "failed"
			msg.UpdatedAt = time.Now()
			continue
		}
		s.repo.UpdateStatus(msg.ID, "sent")
	}
	
	return nil
}
```

## 五、最大努力通知模式

### 5.1 原理

```
┌─────────────┐     ┌─────────────┐
│  通知方      │     │  被通知方    │
│             │     │             │
│ 1. 发送通知  │────>│ 2. 处理     │
│ 2. 重试 N 次│<----│ 3. 返回结果  │
│ 4. 告警     │     │             │
└─────────────┘     └─────────────┘
```

### 5.2 Go 实现

```go
package besteffort

import (
	"context"
	"fmt"
	"time"
)

type Notifier struct {
	maxRetries int
	interval   time.Duration
}

func (n *Notifier) Notify(ctx context.Context, url string, payload interface{}) error {
	var lastErr error
	for i := 0; i < n.maxRetries; i++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		
		lastErr = n.doNotify(ctx, url, payload)
		if lastErr == nil {
			return nil
		}
		
		fmt.Printf("Retry %d/%d for %s: %v\n", i+1, n.maxRetries, url, lastErr)
		time.Sleep(n.interval)
	}
	
	return fmt.Errorf("max retries exceeded: %w", lastErr)
}
```

## 六、自测题

1. Saga 和 TCC 各有什么适用场景？
2. 如何保证 Saga 补偿操作的幂等性？
3. 分布式事务的最终一致性如何保证？

## 七、动手验证

```bash
# 1. 实现 Saga 编排器
# 2. 实现 TCC 服务
# 3. 测试补偿逻辑
# 4. 验证最终一致性
```
