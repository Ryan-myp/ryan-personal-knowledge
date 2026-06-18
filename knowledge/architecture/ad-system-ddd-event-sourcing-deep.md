# 广告系统架构设计：DDD 计费/事件溯源/微服务拆分

> 从架构设计方法论角度，解析广告系统的核心架构模式

---

## 第一部分：广告系统为什么需要 DDD？

### 广告系统的领域复杂性

```
广告系统的领域模型：
┌─────────────────────────────────────────────────────────────────────┐
│ 核心域（Core Domain）：                                              │
│ • 竞价引擎（Bidding Engine）- 核心差异化能力                          │
│ • 排序算法（Ranking Algorithm）- 核心竞争力                            │
│ • 创意管理（Creative Management）                                    │
│                                                                     │
│ 支撑域（Supporting Domain）：                                        │
│ • 计费结算（Billing & Settlement）                                   │
│ • 报告分析（Reporting & Analytics）                                  │
│ • 审核系统（Audit & Compliance）                                     │
│                                                                     │
│ 通用域（Generic Domain）：                                           │
│ • 用户认证（Authentication）                                         │
│ • 通知系统（Notification）                                           │
│ • 文件存储（File Storage）                                           │
└─────────────────────────────────────────────────────────────────────┘

DDD 的价值：
1. 统一语言：业务和技术团队使用相同的术语
2. 边界清晰：每个 Bounded Context 有明确的职责
3. 独立演进：不同 Context 可以独立开发和部署
4. 测试友好：Context 之间松耦合，易于单元测试
```

---

## 第二部分：计费系统的 DDD 设计

### Bounded Context 划分

```
计费系统 Bounded Context：
┌─────────────────────────────────────────────────────────────────────┐
│ Billing Context                                                     │
│                                                                     │
│ Aggregate Root: Budget                                              │
│   • budget_id, campaign_id, daily_budget, total_budget              │
│   • spent_today, spent_total                                        │
│   • status: active/paused/exhausted                                 │
│                                                                     │
│ Entity: Transaction                                                 │
│   • transaction_id, budget_id, type (impression/click/conversion)   │
│   • amount, currency, timestamp                                     │
│                                                                     │
│ Value Object: Money                                                 │
│   • amount, currency                                                │
│                                                                     │
│ Repository: BudgetRepository                                        │
│   • Save, GetById, GetByCampaign                                    │
│                                                                     │
│ Service: BillingService                                             │
│   • DeductBudget (扣减预算)                                         │
│   • CheckBudget (检查预算)                                          │
│   • GenerateReport (生成账单)                                       │
│                                                                     │
│ 防腐层（ACL）：                                                      │
│ • 计费系统 → 广告系统：只读预算状态                                  │
│ • 计费系统 → 财务系统：推送交易记录                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 计费聚合根实现

```go
package billing

import (
	"errors"
	"time"
)

// Budget 预算聚合根
type Budget struct {
	ID          string
	CampaignID  string
	DailyBudget float64
	TotalBudget float64
	SpentToday  float64
	SpentTotal  float64
	Status      BudgetStatus
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

type BudgetStatus string

const (
	BudgetActive    BudgetStatus = "active"
	BudgetPaused    BudgetStatus = "paused"
	BudgetExhausted BudgetStatus = "exhausted"
)

// Deduct 扣减预算
func (b *Budget) Deduct(amount float64) error {
	if b.Status == BudgetPaused {
		return errors.New("budget is paused")
	}

	// 1. 检查今日预算
	if b.SpentToday+amount > b.DailyBudget {
		return errors.New("daily budget exceeded")
	}

	// 2. 检查总预算
	if b.SpentTotal+amount > b.TotalBudget {
		return errors.New("total budget exceeded")
	}

	// 3. 扣减
	b.SpentToday += amount
	b.SpentTotal += amount
	b.UpdatedAt = time.Now()

	// 4. 检查是否耗尽
	if b.SpentTotal >= b.TotalBudget {
		b.Status = BudgetExhausted
	}

	return nil
}

// ResetDaily 重置每日预算（每天零点调用）
func (b *Budget) ResetDaily() {
	b.SpentToday = 0
	if b.Status == BudgetExhausted && b.SpentTotal < b.TotalBudget {
		b.Status = BudgetActive
	}
}

// Transaction 交易实体
type Transaction struct {
	ID         string
	BudgetID   string
	Type       TransactionType
	Amount     float64
	Currency   string
	Timestamp  time.Time
}

type TransactionType string

const (
	TransactionImpression TransactionType = "impression"
	TransactionClick      TransactionType = "click"
	TransactionConversion TransactionType = "conversion"
)
```

---

## 第三部分：事件溯源在广告系统的应用

### 为什么广告系统需要事件溯源？

```
事件溯源（Event Sourcing）在广告系统中的价值：
1. 审计追踪：所有预算变更都可追溯
2. 数据一致性：竞价→计费→报告的数据一致性
3. 回放能力：重现历史状态，用于调试和测试
4. 实时计算：事件流驱动实时聚合

广告事件流：
CampaignCreated → BudgetSet → AdCreated → Impression → Click → Conversion
```

### 事件溯源架构

```
┌─────────────────────────────────────────────────────────────────────┐
│ 事件溯源架构                                                         │
│                                                                     │
│ Command → Handler → Aggregate → Events → Event Store → Projections │
│                                                                     │
│ 示例：扣减预算                                                       │
│ 1. Command: DeductBudget{BudgetID: "b1", Amount: 2.5}               │
│ 2. Handler: 调用 BudgetAggregate.Deduct(2.5)                        │
│ 3. Aggregate: 扣减成功，生成 BudgetDeducted 事件                     │
│ 4. Event Store: 存储事件                                             │
│ 5. Projection: 更新 BudgetSnapshot（查询用）                         │
│                                                                     │
│ 事件表:                                                              │
│ ┌────────┬────────────┬────────────┬────────────┬──────────────┐   │
│ │ EventID│ EventType  │ AggregateID│ Payload    │ Timestamp    │   │
│ ├────────┼────────────┼────────────┼────────────┼──────────────┤   │
│ │ 1      │ CampaignCr │ camp_001   │ {...}      │ 2024-01-01   │   │
│ │ 2      │ BudgetSet  │ b_001      │ {...}      │ 2024-01-01   │   │
│ │ 3      │ Impression │ imp_001    │ {...}      │ 2024-01-01   │   │
│ │ 4      │ BudgetDed  │ b_001      │ {...}      │ 2024-01-01   │   │
│ └────────┴────────────┴────────────┴────────────┴──────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Go 实现事件溯源

```go
package eventstore

import (
	"context"
	"encoding/json"
	"time"
)

// Event 领域事件
type Event struct {
	EventID     string    `json:"event_id"`
	EventType   string    `json:"event_type"`
	AggregateID string    `json:"aggregate_id"`
	Payload     []byte    `json:"payload"`
	Timestamp   time.Time `json:"timestamp"`
	Version     int64     `json:"version"`
}

// EventStore 事件存储接口
type EventStore interface {
	Append(ctx context.Context, aggregateID string, events []Event) error
	Load(ctx context.Context, aggregateID string) ([]Event, error)
}

// BudgetAggregate 预算聚合根
type BudgetAggregate struct {
	ID          string
	DailyBudget float64
	TotalBudget float64
	SpentToday  float64
	SpentTotal  float64
	Status      string
	Version     int64
}

// ApplyEvent 应用事件到聚合根
func (a *BudgetAggregate) ApplyEvent(event Event) error {
	var payload map[string]interface{}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return err
	}

	switch event.EventType {
	case "BudgetCreated":
		a.TotalBudget = payload["total_budget"].(float64)
		a.DailyBudget = payload["daily_budget"].(float64)
		a.Status = "active"
	case "BudgetDeducted":
		a.SpentToday += payload["amount"].(float64)
		a.SpentTotal += payload["amount"].(float64)
		if a.SpentTotal >= a.TotalBudget {
			a.Status = "exhausted"
		}
	case "BudgetResetDaily":
		a.SpentToday = 0
		if a.Status == "exhausted" && a.SpentTotal < a.TotalBudget {
			a.Status = "active"
		}
	}

	a.Version++
	return nil
}

// DeductCommand 扣减命令
type DeductCommand struct {
	BudgetID string
	Amount   float64
}

// HandleDeduct 处理扣减命令
func (a *BudgetAggregate) HandleDeduct(cmd DeductCommand) ([]Event, error) {
	events := []Event{}

	if a.Status == "paused" {
		return nil, errors.New("budget is paused")
	}

	if a.SpentToday+cmd.Amount > a.DailyBudget {
		return nil, errors.New("daily budget exceeded")
	}

	if a.SpentTotal+cmd.Amount > a.TotalBudget {
		return nil, errors.New("total budget exceeded")
	}

	// 生成事件
	payload, _ := json.Marshal(map[string]interface{}{
		"amount": cmd.Amount,
	})
	events = append(events, Event{
		EventType:   "BudgetDeducted",
		AggregateID: a.ID,
		Payload:     payload,
		Timestamp:   time.Now(),
	})

	// 应用事件
	for _, event := range events {
		a.ApplyEvent(event)
	}

	return events, nil
}
```

---

## 第四部分：微服务拆分策略

### 广告系统微服务拆分

```
微服务拆分原则：
1. 按领域拆分（DDD Bounded Context）
2. 独立部署和扩展
3. 数据隔离（每个服务有自己的数据库）
4. 异步通信（事件驱动）

广告系统微服务拆分：
┌─────────────────────────────────────────────────────────────────────┐
│ 核心服务（Core Services）：                                          │
│ • Campaign Service（广告系列管理）                                    │
│ • Bidder Service（竞价服务）                                         │
│ • Ranker Service（排序服务）                                         │
│ • Tracker Service（追踪服务）                                         │
│                                                                     │
│ 支撑服务（Supporting Services）：                                    │
│ • Billing Service（计费服务）                                         │
│ • Creative Service（创意管理）                                       │
│ • Report Service（报告服务）                                         │
│ • Audit Service（审核服务）                                           │
│                                                                     │
│ 基础设施服务（Infrastructure Services）：                            │
│ • User Service（用户服务）                                           │
│ • Notification Service（通知服务）                                   │
│ • Config Service（配置服务）                                         │
│ • Monitor Service（监控服务）                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 服务间通信

```
服务间通信模式：
1. 同步调用（gRPC/HTTP）：
   • Bidder → Ranker：获取排序分数
   • Tracker → Billing：扣减预算

2. 异步事件（Kafka）：
   • Bidder → Kafka：竞价事件
   • Tracker → Kafka：追踪事件
   • Billing → Kafka：计费事件

3. 事件溯源：
   • 每个服务的内部状态变更通过事件流传递
```

### gRPC 服务定义

```protobuf
// bidding.proto
syntax = "proto3";
package bidding;

service BidderService {
  rpc PlaceBid (BidRequest) returns (BidResponse);
  rpc GetBidHistory (BidHistoryRequest) returns (BidHistoryResponse);
}

message BidRequest {
  string request_id = 1;
  string campaign_id = 2;
  string user_id = 3;
  string device_id = 4;
  string ip_address = 5;
  double budget_remaining = 6;
  repeated string interests = 7;
}

message BidResponse {
  string bid_id = 1;
  double bid_price = 2;
  bool win = 3;
  string ad_id = 4;
  string tracking_url = 5;
}

// billing.proto
syntax = "proto3";
package billing;

service BillingService {
  rpc DeductBudget (DeductRequest) returns (DeductResponse);
  rpc GetBudget (BudgetRequest) returns (BudgetResponse);
  rpc GenerateInvoice (InvoiceRequest) returns (InvoiceResponse);
}

message DeductRequest {
  string budget_id = 1;
  double amount = 2;
  string campaign_id = 3;
  string transaction_type = 4; // impression/click/conversion
}

message DeductResponse {
  bool success = 1;
  string error_message = 2;
  double remaining_budget = 3;
}
```

---

## 第五部分：自测题

### Q1: 为什么广告计费系统要用事件溯源？

**A**:
- 审计追踪：所有预算变更可追溯
- 数据一致性：竞价→计费→报告的数据一致性
- 回放能力：重现历史状态用于调试
- 实时计算：事件流驱动实时聚合

### Q2: 微服务拆分的原则？

**A**:
- 按领域拆分（DDD Bounded Context）
- 独立部署和扩展
- 数据隔离（每个服务有自己的数据库）
- 异步通信（事件驱动）

### Q3: 服务间通信怎么选择？

**A**:
- 同步调用（gRPC）：需要即时响应的场景（竞价→排序）
- 异步事件（Kafka）：最终一致性的场景（追踪→计费）
- 事件溯源：内部状态变更的持久化

---

## 第六部分：生产实践

### 1. 计费系统设计要点

```
计费系统设计要点：
1. 原子操作：预算扣减必须是原子的（Redis Lua 或 DB 事务）
2. 幂等性：同一笔交易不会重复扣费
3. 对账：每日对账，发现不一致及时纠正
4. 预警：预算即将耗尽时预警
5. 限流：防止突发流量打垮计费系统
```

### 2. 事件溯源最佳实践

```
事件溯源最佳实践：
1. 事件命名：使用过去式（BudgetDeducted, CampaignCreated）
2. 事件版本：每个事件有版本号，支持向后兼容
3. 事件存储：按 AggregateID 分区，支持高效查询
4. 投影更新：异步更新投影，避免阻塞事件写入
5. 事件压缩：定期压缩旧事件，减少存储
```

### 3. 微服务拆分建议

```
微服务拆分建议：
1. 初期：单体架构，按模块划分包
2. 中期：拆分为 3-5 个核心服务
3. 后期：拆分为 8-12 个服务
4. 不要过早拆分：先验证业务逻辑，再拆分
```
