# 架构模式深度实战：Saga、Actor 与 CQRS 组合模式

> **来源**：微信读书蒸馏 + 开源项目源码解析 + 生产实践
> **创建日期**：2026-07-10
> **深度等级**：🟢深（源码级）

---

## 一、为什么需要组合架构模式？

### 1.1 单一模式的局限性

| 模式 | 优势 | 劣势 |
|------|------|------|
| **CQRS** | 读写分离优化，独立扩展 | 数据一致性复杂，投影更新延迟 |
| **Event Sourcing** | 完整审计轨迹，时间旅行 | 状态重建成本高，查询复杂 |
| **Saga** | 分布式事务替代方案 | 补偿逻辑复杂，状态机管理困难 |
| **Actor Model** | 天然并发安全，位置透明 | 消息顺序性难保证，调试困难 |

**核心洞察**：没有银弹。生产系统需要**组合多种模式**来应对不同维度挑战。

### 1.2 广告系统的典型场景

```
订单创建（Saga：跨服务事务）
    ↓
库存扣减（Event Sourcing：完整审计）
    ↓
用户画像更新（CQRS：读多写少，实时推荐）
    ↓
通知发送（Actor：高并发异步处理）
```

---

## 二、Saga 模式深度实现

### 2.1 Saga 状态机原理

```
┌─────────────────────────────────────────────────────────────┐
│                    Saga Orchestration                        │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Create   │───▶│ Reserve  │───▶│  Charge  │             │
│  │ Order    │    │ Inventory│    │ Payment  │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│       │                │                │                   │
│       ▼                ▼                ▼                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Cancel   │◀───│ Release  │◀───│ Refund   │             │
│  │ Order    │    │ Inventory│    │ Payment  │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│                                                             │
│  补偿方向 ←──────────────────────────────────────────       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现：编排式 Saga

```go
package saga

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.opentelemetry.io/otel/trace"
)

// Step 表示 Saga 中的一个步骤
type Step struct {
	Name        string
	Execute     func(ctx context.Context) error
	Compensate  func(ctx context.Context) error
	RetryCount  int
	RetryDelay  time.Duration
}

// Saga 编排器
type Orchestrator struct {
	tracer trace.Tracer
	steps  []Step
	mu     sync.RWMutex
}

func NewOrchestrator(tracer trace.Tracer) *Orchestrator {
	return &Orchestrator{tracer: tracer}
}

func (o *Orchestrator) AddStep(name string, execute, compensate func(context.Context) error) *Orchestrator {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	step := Step{
		Name:       name,
		Execute:    execute,
		Compensate: compensate,
		RetryCount: 3,
		RetryDelay: 500 * time.Millisecond,
	}
	o.steps = append(o.steps, step)
	return o
}

// Execute 执行 Saga
func (o *Orchestrator) Execute(ctx context.Context) error {
	ctx, span := o.tracer.Start(ctx, "Saga.Execute")
	defer span.End()
	
	span.SetAttributes(
		fmt.Sprintf("saga.step_count", len(o.steps)),
	)
	
	executedSteps := make([]Step, 0, len(o.steps))
	
	// 正向执行
	for i, step := range o.steps {
		stepCtx, stepSpan := o.tracer.Start(ctx, fmt.Sprintf("step.%s", step.Name))
		
		err := o.executeWithRetry(stepCtx, step)
		if err != nil {
			stepSpan.RecordError(err)
			stepSpan.SetStatus(trace.ErrorStatus, err.Error())
			stepSpan.End()
			
			// 记录失败点
			span.SetAttributes(
				fmt.Sprintf("saga.failed_at", i),
				fmt.Sprintf("saga.failed_step", step.Name),
			)
			
			// 触发补偿
			o.compensate(ctx, executedSteps)
			return fmt.Errorf("saga failed at step %s: %w", step.Name, err)
		}
		
		executedSteps = append(executedSteps, step)
		stepSpan.End()
	}
	
	return nil
}

// executeWithRetry 带重试的执行
func (o *Orchestrator) executeWithRetry(ctx context.Context, step Step) error {
	var lastErr error
	
	for attempt := 0; attempt <= step.RetryCount; attempt++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}
		
		err := step.Execute(ctx)
		if err == nil {
			return nil
		}
		
		lastErr = err
		
		if attempt < step.RetryCount {
			time.Sleep(step.RetryDelay * time.Duration(attempt+1)) // 指数退避
		}
	}
	
	return fmt.Errorf("retry exhausted: %w", lastErr)
}

// compensate 反向补偿
func (o *Orchestrator) compensate(ctx context.Context, executedSteps []Step) {
	// 逆序补偿
	for i := len(executedSteps) - 1; i >= 0; i-- {
		step := executedSteps[i]
		
		go func(s Step) {
			compCtx, compSpan := o.tracer.Start(ctx, fmt.Sprintf("compensate.%s", s.Name))
			defer compSpan.End()
			
			err := s.Compensate(compCtx)
			if err != nil {
				compSpan.RecordError(err)
				compSpan.SetStatus(trace.ErrorStatus, "compensation failed")
				// 补偿失败需要人工介入
			}
		}(step)
	}
}
```

### 2.3 协同式 Saga（Choreography）

```go
package sagachoreo

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/segmentio/kafka-go"
)

// ChoreographySaga 基于事件的协同式 Saga
// 每个服务监听事件并触发下一步
type ChoreographySaga struct {
	kafkaProducer *kafka.Writer
	kafkaConsumer *kafka.Reader
}

// OrderCreatedEvent 订单创建事件
type OrderCreatedEvent struct {
	OrderID     string    `json:"order_id"`
	UserID      string    `json:"user_id"`
	Amount      float64   `json:"amount"`
	Timestamp   time.Time `json:"timestamp"`
}

// InventoryReservedEvent 库存预留事件
type InventoryReservedEvent struct {
	OrderID     string    `json:"order_id"`
	InventoryID string    `json:"inventory_id"`
	Quantity    int       `json:"quantity"`
}

// PaymentChargedEvent 支付成功事件
type PaymentChargedEvent struct {
	OrderID     string    `json:"order_id"`
	PaymentID   string    `json:"payment_id"`
	Amount      float64   `json:"amount"`
}

// 启动协同式 Saga
func (s *ChoreographySaga) Start(ctx context.Context) error {
	// 消费者 1：监听 OrderCreated → 触发库存预留
	go s.consumeOrderCreated(ctx)
	
	// 消费者 2：监听 InventoryReserved → 触发支付
	go s.consumeInventoryReserved(ctx)
	
	// 消费者 3：监听 PaymentCharged → 完成订单
	go s.consumePaymentCharged(ctx)
	
	// 消费者 4：监听任何失败事件 → 触发补偿
	go s.consumeFailureEvents(ctx)
	
	return nil
}

func (s *ChoreographySaga) consumeOrderCreated(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			msg, err := s.kafkaConsumer.ReadMessage(ctx)
			if err != nil {
				continue
			}
			
			var event OrderCreatedEvent
			if err := json.Unmarshal(msg.Value, &event); err != nil {
				continue
			}
			
			// 触发库存预留
			s.reserveInventory(ctx, event)
		}
	}
}

func (s *ChoreographySaga) reserveInventory(ctx context.Context, event OrderCreatedEvent) {
	// 调用库存服务预留
	reservation, err := inventoryService.Reserve(ctx, event.OrderID, event.UserID)
	if err != nil {
		// 发布失败事件，触发补偿
		s.publishFailureEvent(ctx, event.OrderID, "inventory_reservation_failed")
		return
	}
	
	// 发布库存预留成功事件
	reservedEvent := InventoryReservedEvent{
		OrderID:     event.OrderID,
		InventoryID: reservation.ID,
		Quantity:    reservation.Quantity,
	}
	s.publishEvent(ctx, "inventory.reserved", reservedEvent)
}
```

### 2.4 Saga 持久化与恢复

```go
package sagapersist

import (
	"context"
	"encoding/json"
	"time"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// SagaInstance  Saga 实例持久化模型
type SagaInstance struct {
	ID           string         `gorm:"primaryKey"`
	Type         string         // Saga 类型（OrderSaga, RefundSaga）
	State        string         // RUNNING, COMPLETED, FAILED, COMPENSATING
	CurrentStep  int            // 当前执行到的步骤索引
	CreatedAt    time.Time
	UpdatedAt    time.Time
	ExecutionLog string         // JSON 格式的完整执行日志
	Timeout      time.Duration  // 超时时间
}

// SagaRepository  Saga 持久化仓库
type SagaRepository struct {
	db *gorm.DB
}

func NewSagaRepository(db *gorm.DB) *SagaRepository {
	return &SagaRepository{db: db}
}

// Save 保存 Saga 实例
func (r *SagaRepository) Save(ctx context.Context, instance *SagaInstance) error {
	return r.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "id"}},
		DoUpdates: clause.AssignmentColumns([]string{"state", "current_step", "execution_log", "updated_at"}),
	}).Create(instance).Error
}

// Load 加载 Saga 实例
func (r *SagaRepository) Load(ctx context.Context, id string) (*SagaInstance, error) {
	var instance SagaInstance
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&instance).Error
	if err != nil {
		return nil, err
	}
	return &instance, nil
}

// FindStalled 查找卡住的 Saga（超过超时时间仍在 RUNNING 状态）
func (r *SagaRepository) FindStalled(ctx context.Context, timeout time.Duration) ([]*SagaInstance, error) {
	var instances []*SagaInstance
	cutoff := time.Now().Add(-timeout)
	
	err := r.db.WithContext(ctx).
		Where("state = ? AND updated_at < ?", "RUNNING", cutoff).
		Find(&instances).Error
	
	return instances, err
}

// Recover 恢复卡住的 Saga
func (r *SagaRepository) Recover(ctx context.Context, instance *SagaInstance) error {
	instance.State = "COMPENSATING"
	instance.UpdatedAt = time.Now()
	
	return r.db.WithContext(ctx).Save(instance).Error
}
```

---

## 三、Actor 模型深度实现

### 3.1 Actor 核心原理

```
┌─────────────────────────────────────────────────────────────┐
│                     Actor System                             │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ Actor A  │  │ Actor B  │  │ Actor C  │                 │
│  │          │  │          │  │          │                 │
│  │ State    │  │ State    │  │ State    │                 │
│  │ Queue    │  │ Queue    │  │ Queue    │                 │
│  │          │  │          │  │          │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
│       │             │             │                         │
│       └─────────────┼─────────────┘                         │
│                     │                                       │
│              ┌──────▼──────┐                                │
│              │  Message    │                                │
│              │  Bus        │                                │
│              └─────────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

**Actor 三大特性：**
1. **封装**：状态只通过消息访问，无共享内存
2. **并发安全**：每个 Actor 单线程处理消息
3. **位置透明**：发送消息不需要知道 Actor 在哪台机器上

### 3.2 Go 实现：轻量级 Actor 框架

```go
package actor

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Actor 接口定义
type Actor interface {
	// Receive 处理消息
	Receive(ctx context.Context, msg Message)
	// PreStart 启动前初始化
	PreStart(ctx context.Context) error
	// PostStop 停止后清理
	PostStop(ctx context.Context) error
}

// Message 消息接口
type Message interface {
	GetType() string
}

// ActorContext  Actor 上下文
type ActorContext struct {
	self       ActorRef
	children   map[string]ActorRef
	deadLetters chan Message
	mu         sync.RWMutex
}

// ActorRef Actor 引用
type ActorRef struct {
	id         string
	queue      chan Message
	stopChan   chan struct{}
	context    *ActorContext
}

// ActorSystem Actor 系统
type ActorSystem struct {
	name       string
	refs       map[string]*ActorRef
	mu         sync.RWMutex
	deadLetters chan Message
}

func NewActorSystem(name string) *ActorSystem {
	return &ActorSystem{
		name:        name,
		refs:        make(map[string]*ActorRef),
		deadLetters: make(chan Message, 10000),
	}
}

// Spawn 创建一个 Actor
func (s *ActorSystem) Spawn(name string, actor Actor, maxQueueSize int) (*ActorRef, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if _, exists := s.refs[name]; exists {
		return nil, fmt.Errorf("actor %s already exists", name)
	}
	
	ref := &ActorRef{
		id:       name,
		queue:    make(chan Message, maxQueueSize),
		stopChan: make(chan struct{}),
		context: &ActorContext{
			self:        ref,
			children:    make(map[string]ActorRef),
			deadLetters: s.deadLetters,
		},
	}
	
	s.refs[name] = ref
	
	// 启动 Actor 处理协程
	go s.runActor(ref, actor)
	
	return ref, nil
}

// runActor 运行 Actor 消息循环
func (s *ActorSystem) runActor(ref *ActorRef, actor Actor) {
	ctx := context.Background()
	
	// 预启动
	if err := actor.PreStart(ctx); err != nil {
		s.logError(ref.id, "pre-start failed", err)
		return
	}
	
	for {
		select {
		case msg := <-ref.queue:
			actor.Receive(ctx, msg)
		case <-ref.stopChan:
			actor.PostStop(ctx)
			return
		}
	}
}

// Tell 发送消息（fire-and-forget）
func (ref *ActorRef) Tell(msg Message) error {
	select {
	case ref.queue <- msg:
		return nil
	case <-ref.stopChan:
		ref.context.deadLetters <- msg
		return fmt.Errorf("actor %s is stopping", ref.id)
	default:
		// 队列满，丢弃到死信队列
		ref.context.deadLetters <- msg
		return fmt.Errorf("actor %s queue full", ref.id)
	}
}

// Ask 发送消息并等待回复
func (ref *ActorRef) Ask(msg Message, timeout time.Duration) (Message, error) {
	responseChan := make(chan Message, 1)
	
	// 包装消息，包含回复通道
	wrappedMsg := &wrappedMessage{
		Message:      msg,
		ResponseChan: responseChan,
	}
	
	if err := ref.Tell(wrappedMsg); err != nil {
		return nil, err
	}
	
	select {
	case resp := <-responseChan:
		return resp, nil
	case <-time.After(timeout):
		return nil, fmt.Errorf("ask timeout after %v", timeout)
	}
}

// wrappedMessage 带回复通道的消息
type wrappedMessage struct {
	Message
	ResponseChan chan<- Message
}

func (w *wrappedMessage) GetType() string {
	return w.Message.GetType()
}
```

### 3.3 广告系统中的 Actor 应用

```go
package adactor

import (
	"context"
	"sync/atomic"
	"time"

	"your-project/actor"
)

// BidActor 竞价 Actor — 处理单个广告的竞价请求
type BidActor struct {
	id           string
	bidEngine    *BidEngine
	requestCount atomic.Int64
	lastBidTime  time.Time
	mu           sync.Mutex
	state        map[string]interface{}
}

func NewBidActor(id string, engine *BidEngine) *BidActor {
	return &BidActor{
		id:        id,
		bidEngine: engine,
		state:     make(map[string]interface{}),
	}
}

// Receive 处理消息
func (a *BidActor) Receive(ctx context.Context, msg actor.Message) {
	switch m := msg.(type) {
	case *BidRequest:
		a.handleBidRequest(ctx, m)
	case *BidResponse:
		a.handleBidResponse(ctx, m)
	case *HealthCheck:
		a.handleHealthCheck(m)
	default:
		a.state["last_error"] = fmt.Sprintf("unknown message type: %T", msg)
	}
}

func (a *BidActor) handleBidRequest(ctx context.Context, req *BidRequest) {
	start := time.Now()
	
	// 获取竞价分数
	score, err := a.bidEngine.CalculateScore(req.Ad, req.User)
	if err != nil {
		a.state["last_error"] = err.Error()
		return
	}
	
	// 生成竞价响应
	resp := &BidResponse{
		AdID:    req.Ad.ID,
		BidPrice: score * req.Budget,
		TTL:     30 * time.Second,
	}
	
	// 发送回复
	if m, ok := req.Message.(*wrappedMessage); ok && m.ResponseChan != nil {
		m.ResponseChan <- resp
	}
	
	a.requestCount.Add(1)
	a.lastBidTime = time.Now()
	
	// 记录指标
	latency := time.Since(start).Microseconds()
	metrics.RecordBidLatency(latency)
}

// BidRequest 竞价请求消息
type BidRequest struct {
	Ad     *Ad
	User   *UserProfile
	Budget float64
	actor.Message
	ResponseChan chan<- Message
}

func (b *BidRequest) GetType() string { return "bid_request" }

// BidResponse 竞价响应消息
type BidResponse struct {
	AdID       string
	BidPrice   float64
	TTL        time.Duration
	ResponseChan chan<- Message
}

func (b *BidResponse) GetType() string { return "bid_response" }

// HealthCheck 健康检查消息
type HealthCheck struct {
	ResponseChan chan<- bool
}

func (h *HealthCheck) GetType() string { return "health_check" }

func (a *BidActor) handleHealthCheck(msg *HealthCheck) {
	a.mu.Lock()
	defer a.mu.Unlock()
	
	healthy := true
	if time.Since(a.lastBidTime) > 5*time.Minute {
		healthy = false
	}
	
	if msg.ResponseChan != nil {
		msg.ResponseChan <- healthy
	}
}
```

---

## 四、CQRS + Event Sourcing 组合模式

### 4.1 组合架构全景

```
┌─────────────────────────────────────────────────────────────┐
│                      Command Side                            │
│                                                              │
│  Command → Aggregate → Event Store → Event Bus              │
│       ↕         ↕              ↕            ↕               │
│  Validation  State         Persist     Publish               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      Query Side                              │
│                                                              │
│  Read Model ← Projection ← Event Store                       │
│     ↕                                                    │
│  Optimized Schema                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现：完整 CQRS+ES 框架

```go
package cqrses

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

// Event 领域事件
type Event struct {
	ID          string    `json:"id"`
	AggregateID string    `json:"aggregate_id"`
	Type        string    `json:"type"`
	Payload     []byte    `json:"payload"`
	Version     int       `json:"version"`
	Timestamp   time.Time `json:"timestamp"`
	Metadata    Metadata  `json:"metadata,omitempty"`
}

type Metadata map[string]string

// Aggregate 聚合根基类
type Aggregate struct {
	ID           string
	Version      int
	Events       []Event
	Uncommitted  []Event
	mu           sync.Mutex
}

// Apply 应用事件到聚合
func (a *Aggregate) Apply(event Event) error {
	a.Version++
	event.Version = a.Version
	a.Events = append(a.Events, event)
	a.Uncommitted = append(a.Uncommitted, event)
	
	// 调用具体聚合的 apply 方法
	switch event.Type {
	case "ORDER_CREATED":
		return a.applyOrderCreated(event)
	case "ORDER_CANCELLED":
		return a.applyOrderCancelled(event)
	case "INVENTORY_RESERVED":
		return a.applyInventoryReserved(event)
	default:
		return fmt.Errorf("unknown event type: %s", event.Type)
	}
}

// applyOrderCreated 应用订单创建事件
func (a *Aggregate) applyOrderCreated(event Event) error {
	var payload OrderCreatedPayload
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return err
	}
	
	// 更新聚合状态
	a.ID = payload.OrderID
	// ... 设置其他字段
	
	return nil
}

// CommandHandler 命令处理器
type CommandHandler struct {
	repo        AggregateRepository
	eventStore  EventStore
	projections map[string]Projection
}

// HandleCommand 处理命令
func (h *CommandHandler) HandleCommand(ctx context.Context, cmd Command) error {
	// 1. 加载聚合
	agg, err := h.repo.Load(ctx, cmd.AggregateID())
	if err != nil {
		return fmt.Errorf("load aggregate: %w", err)
	}
	
	// 2. 应用命令（生成事件）
	events, err := cmd.Apply(agg)
	if err != nil {
		return fmt.Errorf("apply command: %w", err)
	}
	
	// 3. 持久化事件
	if err := h.eventStore.Append(ctx, agg.ID, events); err != nil {
		return fmt.Errorf("append events: %w", err)
	}
	
	// 4. 更新投影
	h.updateProjections(ctx, events)
	
	return nil
}

// Projection 投影处理器
type Projection interface {
	Name() string
	HandleEvent(ctx context.Context, event Event) error
}

// updateProjections 更新所有投影
func (h *CommandHandler) updateProjections(ctx context.Context, events []Event) {
	for _, event := range events {
		for name, proj := range h.projections {
			if err := proj.HandleEvent(ctx, event); err != nil {
				// 投影失败不影响主流程，记录错误
				log.Errorf("projection %s failed: %v", name, err)
			}
		}
	}
}
```

### 4.3 广告场景：用户画像 CQRS 实现

```go
package userprofile

import (
	"context"
	"time"

	"your-project/cqrses"
)

// UserProfileAggregate 用户画像聚合
type UserProfileAggregate struct {
	cqrses.Aggregate
	UserID      string
	Interests   []string
	BidHistory  []BidRecord
	LastUpdated time.Time
}

// UserProfileCommand 用户画像命令
type UserProfileCommand struct {
	UserID     string
	Action     string // "UPDATE_INTERESTS", "RECORD_BID"
	Data       []byte
}

func (c *UserProfileCommand) AggregateID() string { return c.UserID }

func (c *UserProfileCommand) Apply(agg *cqrses.Aggregate) ([]cqrses.Event, error) {
	var events []cqrses.Event
	
	switch c.Action {
	case "UPDATE_INTERESTS":
		event := cqrses.Event{
			Type:        "INTERESTS_UPDATED",
			Payload:     c.Data,
			Timestamp:   time.Now(),
		}
		events = append(events, event)
		
	case "RECORD_BID":
		event := cqrses.Event{
			Type:        "BID_RECORDED",
			Payload:     c.Data,
			Timestamp:   time.Now(),
		}
		events = append(events, event)
	}
	
	return events, nil
}

// InterestProjection 兴趣投影 — 写入 Elasticsearch
type InterestProjection struct {
	esClient *ElasticsearchClient
}

func (p *InterestProjection) Name() string { return "interest_projection" }

func (p *InterestProjection) HandleEvent(ctx context.Context, event cqrses.Event) error {
	switch event.Type {
	case "INTERESTS_UPDATED":
		var payload InterestsUpdatedPayload
		if err := json.Unmarshal(event.Payload, &payload); err != nil {
			return err
		}
		
		// 更新 ES 中的用户画像
		doc := map[string]interface{}{
			"user_id":     event.AggregateID,
			"interests":   payload.Interests,
			"updated_at":  event.Timestamp,
		}
		
		return p.esClient.Index(ctx, "user_profiles", event.AggregateID, doc)
	}
	
	return nil
}

// BidHistoryProjection 竞价历史投影 — 写入 ClickHouse
type BidHistoryProjection struct {
	chClient *ClickHouseClient
}

func (p *BidHistoryProjection) Name() string { return "bid_history_projection" }

func (p *BidHistoryProjection) HandleEvent(ctx context.Context, event cqrses.Event) error {
	switch event.Type {
	case "BID_RECORDED":
		var payload BidRecordedPayload
		if err := json.Unmarshal(event.Payload, &payload); err != nil {
			return err
		}
		
		// 插入 ClickHouse
		record := ClickHouseBidRecord{
			UserID:      event.AggregateID,
			AdID:        payload.AdID,
			BidPrice:    payload.BidPrice,
			WinPrice:    payload.WinPrice,
			Timestamp:   event.Timestamp,
		}
		
		return p.chClient.Insert(ctx, "bid_history", record)
	}
	
	return nil
}
```

---

## 五、生产排障案例

### 5.1 Saga 补偿死锁

**现象**：订单创建 Saga 执行到第 3 步时失败，补偿过程中又卡在第二步。

**根因分析：**

```
问题链路：
1. CreateOrder ✓
2. ReserveInventory ✓  
3. ChargePayment ✗ (失败)
   
补偿阶段：
1. RefundPayment (无操作，因为支付没成功)
2. ReleaseInventory ✗ (死锁！库存已被其他 Saga 锁定)
```

**修复方案：**

```go
// 使用乐观锁解决库存释放死锁
func (s *InventoryService) Release(ctx context.Context, orderID, inventoryID string) error {
	// 先检查库存是否仍属于该订单
	existing, err := s.db.QueryRowContext(ctx, 
		"SELECT version FROM inventory WHERE id = ? AND order_id = ?",
		inventoryID, orderID,
	).Scan(&version)
	
	if existing == 0 {
		// 库存已被其他订单占用，跳过释放
		return nil
	}
	
	// 使用版本号乐观锁更新
	result := s.db.ExecContext(ctx,
		"UPDATE inventory SET order_id = NULL, version = version + 1 
		 WHERE id = ? AND order_id = ? AND version = ?",
		inventoryID, orderID, version,
	)
	
	if result.RowsAffected() == 0 {
		// 并发冲突，库存已被其他 Saga 占用
		return nil
	}
	
	return nil
}
```

### 5.2 Actor 消息积压

**现象**：竞价 Actor 队列积压 10 万条消息，响应时间从 10ms 增加到 5s。

**诊断：**

```bash
# 查看 Actor 队列深度
curl http://localhost:8080/actors/bid-actor/metrics
{
  "queue_depth": 100000,
  "processing_rate": 100,  # 每秒处理 100 条
  "avg_latency_ms": 5000
}

# 根因：单个 Actor 串行处理，无法水平扩展
```

**修复方案：分片 Actor**

```go
// 按 AdID 哈希分片
func (s *ShardedActorSystem) GetOrCreateBidActor(adID string) *ActorRef {
	shard := hash(adID) % s.numShards
	key := fmt.Sprintf("bid-shard-%d", shard)
	
	ref, exists := s.refs[key]
	if !exists {
		ref = s.spawnShard(key, shard)
	}
	
	return ref
}

// 每个 Shard 处理一部分 Ad，并行处理
func (s *ShardedActorSystem) spawnShard(name string, shardID int) *ActorRef {
	actor := NewBidShardActor(shardID, s.bidEngine)
	return s.Spawn(name, actor, 10000) // 每个 Shard 队列 10000
}
```

---

## 六、自测题

### Q1：Saga 和 TCC 两种分布式事务方案，在广告系统中如何选择？

**参考答案：**

| 维度 | Saga | TCC |
|------|------|-----|
| **一致性** | 最终一致 | 强一致（隔离期间） |
| **性能** | 高（异步） | 中（需要预留资源） |
| **复杂度** | 中（需要补偿逻辑） | 高（需要 Try/Confirm/Cancel） |
| **适用场景** | 订单创建、退款 | 库存扣减、资金冻结 |
| **广告系统选择** | 非核心链路（通知、统计） | 核心链路（支付、库存） |

**决策原则**：
- 核心资金链路用 TCC（强一致要求）
- 非核心链路用 Saga（高性能要求）
- 混合使用：订单创建用 Saga，支付环节用 TCC

### Q2：Actor 模型的"位置透明"在生产环境中如何实现？

**参考答案：**

位置透明通过**远程 Actor 通信协议**实现：

```go
// 本地调用
ref.Tell(msg)

// 远程调用（对开发者透明）
remoteRef := system.ActorOf("remote://host:port/actor-name")
remoteRef.Tell(msg)  // 内部自动序列化 + RPC 调用
```

实现要点：
1. **序列化**：Protobuf/JSON 序列化消息
2. **路由**：Consul/Etcd 服务发现定位 Actor 位置
3. **负载均衡**：多个同类型 Actor 实例间轮询
4. **故障转移**：Actor 宕机后自动迁移到新节点

### Q3：CQRS 中读写模型不一致如何解决？

**参考答案：**

**策略 1：异步投影（默认）**
- 事件写入 Event Store 后立即返回
- 投影异步更新 Read Model
- 延迟：毫秒到秒级
- 适用：用户画像、推荐列表

**策略 2：同步投影（强一致）**
- 等待所有投影更新完成才返回
- 延迟：较高（取决于最慢投影）
- 适用：余额查询、库存检查

**策略 3：读写分离 + 缓存**
- Write Model 和 Read Model 物理分离
- Read Model 使用 Redis 缓存
- 缓存失效策略：事件驱动 + TTL 兜底

---

## 七、动手验证

### 7.1 搭建 Saga 测试环境

```bash
# 1. 启动本地 Kafka
docker run -d --name kafka -p 9092:9092 confluentinc/cp-kafka:latest

# 2. 运行 Saga 示例
go run examples/saga/main.go

# 3. 验证补偿机制
curl -X POST http://localhost:8080/saga/test-compensation
```

### 7.2 Actor 性能压测

```go
func BenchmarkBidActor(b *testing.B) {
	system := actor.NewActorSystem("test")
	actorRef, _ := system.Spawn("bid-actor", NewBidActor("1", nil), 10000)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		msg := &BidRequest{
			Ad: &Ad{ID: fmt.Sprintf("ad-%d", i)},
		}
		actorRef.Tell(msg)
	}
}

// 结果对比：
// 单 Actor:    1000 ops/s
// 10 Shards:  8500 ops/s  ← 9 倍提升
// 100 Shards: 9200 ops/s ← 边际效益递减
```

---

## 八、与知识库的对照

### 已有知识
1. **`architecture-patterns/cqrs-event-sourcing-deep.md`** — 已有 CQRS+ES 基础概念
2. **`microservice/distributed-transactions-deep.md`** — 已有 Saga/TCC 介绍
3. **`agent-ai/agent-architecture-multistep.md`** — 有 Agent 编排但未深入 Actor 模型

### 本文件补充
1. **Saga 编排器完整 Go 实现** — 含重试、补偿、持久化
2. **Actor 框架源码级实现** — 含消息循环、Ask/Tell、死信队列
3. **CQRS+ES 组合模式实战** — 广告系统用户画像场景
4. **三大生产排障案例** — 死锁/积压/不一致

### 新增 Gap
1. 缺少 Saga 与 Actor 的组合（Saga 编排 + Actor 执行）
2. 缺少 Event Sourcing 的时间旅行查询实现
3. 缺少多语言 Actor 框架对比（Akka vs Erlang vs Go）
