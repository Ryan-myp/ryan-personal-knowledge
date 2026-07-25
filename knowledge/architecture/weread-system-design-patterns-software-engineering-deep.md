# 微信读书精华：系统设计 + 设计模式的艺术 + 大话软件工程 蒸馏笔记

> 来源：《搞定系统设计：面试敲开大厂的门》- Alex Xu
>       《设计模式的艺术》- 刘伟
>       《大话软件工程：需求分析与软件设计》- 李鸿君
> 状态：未读完（高价值，基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：系统设计方法论

### 系统设计流程

```
系统设计六步法：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 需求分析                                                          │
│    ├── 功能需求：系统要做什么                                         │
│    ├── 非功能需求：性能/可用性/扩展性                                │
│    └── 约束条件：技术栈/时间/预算                                    │
│                                                                     │
│ 2. 高层设计                                                          │
│    ├── 组件划分：服务/模块/接口                                      │
│    ├── 数据流：请求/响应/事件                                        │
│    └── 技术选型：语言/框架/数据库                                    │
│                                                                     │
│ 3. 详细设计                                                          │
│    ├── 接口定义：API/Schema                                          │
│    ├── 数据库设计：表结构/索引/分片                                  │
│    └── 算法设计：核心逻辑/优化                                       │
│                                                                     │
│ 4. 实现                                                               │
│    ├── 编码规范：命名/注释/测试                                      │
│    ├── 代码审查：质量门禁                                            │
│    └── 持续集成：自动化构建                                          │
│                                                                     │
│ 5. 测试                                                               │
│    ├── 单元测试：覆盖率 > 80%                                        │
│    ├── 集成测试：接口验证                                            │
│    └── 压力测试：性能基准                                            │
│                                                                     │
│ 6. 部署和维护                                                        │
│    ├── 灰度发布：逐步放量                                            │
│    ├── 监控告警：实时监控                                            │
│    └── 故障处理：应急预案                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 常见系统设计模式

```
设计模式应用：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 缓存模式                                                          │
│    ├── 缓存穿透：布隆过滤器                                          │
│    ├── 缓存击穿：互斥锁                                             │
│    └── 缓存雪崩：随机过期                                           │
│                                                                     │
│ 2. 限流模式                                                          │
│    ├── 令牌桶：平滑限流                                             │
│    ├── 漏桶：匀速处理                                               │
│    └── 滑动窗口：精确统计                                           │
│                                                                     │
│ 3. 重试模式                                                          │
│    ├── 指数退避：避免雪崩                                           │
│    ├── 抖动：分散重试                                               │
│    └── 幂等性：保证一致性                                           │
│                                                                     │
│ 4. 降级模式                                                          │
│    ├── 功能降级：关闭非核心功能                                     │
│    ├── 数据降级：使用缓存/默认值                                    │
│    └── 服务降级：返回友好提示                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：设计模式实践

### Go 中的设计模式

```
Go 设计模式示例：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 工厂模式                                                          │
│    type AdHandler interface {                                       │
│        Process(req *AdRequest) error                                │
│    }                                                                │
│    func NewAdHandler(platform string) AdHandler {                   │
│        switch platform {                                            │
│        case "facebook": return &FacebookHandler{}                   │
│        case "google": return &GoogleHandler{}                       │
│        }                                                            │
│    }                                                                │
│                                                                     │
│ 2. 策略模式                                                          │
│    type BidStrategy interface {                                     │
│        CalculateBid(req *BidRequest) float64                        │
│    }                                                                │
│    type FixedBidStrategy struct {}                                  │
│    type DynamicBidStrategy struct {}                                │
│                                                                     │
│ 3. 观察者模式                                                        │
│    type Observer interface {                                        │
│        Update(status string)                                        │
│    }                                                                │
│    type AdCampaign struct {                                         │
│        observers []Observer                                          │
│    }                                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 架构模式

```
架构模式选择：
┌────────────────┬────────────┬────────────┬────────────┐
│     模式       │  适用场景  │  优点      │  缺点      │
├────────────────┼────────────┼────────────┼────────────┤
│ MVC            │ Web 应用   │ 分离关注点 │ 耦合度高   │
│ MVVM           │ 前端应用   │ 数据绑定   │ 学习曲线   │
│ 微服务         │ 大型系统   │ 独立部署   │ 运维复杂   │
│ 事件驱动       │ 实时系统   │ 高响应性   │ 数据一致   │
│ CQRS           │ 读写分离   │ 性能优化   │ 实现复杂   │
└────────────────┴────────────┴────────────┴────────────┘

推荐：
• 小型项目：MVC
• 中大型项目：微服务 + 事件驱动
• 高并发：CQRS + 事件溯源
```

---

## 第三部分：软件工程实践

### 需求分析

```
需求分析方法：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 需求收集                                                          │
│    ├── 用户访谈：直接沟通                                           │
│    ├── 问卷调查：大规模收集                                         │
│    └── 数据分析：行为日志                                           │
│                                                                     │
│ 2. 需求分析                                                          │
│    ├── 功能性需求：用例图/流程图                                    │
│    ├── 非功能性需求：性能/安全/可用性                               │
│    └── 约束条件：技术/时间/预算                                     │
│                                                                     │
│ 3. 需求验证                                                          │
│    ├── 需求评审：多方确认                                           │
│    ├── 原型验证：可视化确认                                         │
│    └── 测试用例：可测试性验证                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 软件设计

```
设计原则：
┌─────────────────────────────────────────────────────────────────────┐
│ SOLID 原则：                                                         │
│ 1. 单一职责：一个类只有一个变化理由                                  │
│ 2. 开闭原则：对扩展开放，对修改关闭                                  │
│ 3. 里氏替换：子类可以替换父类                                       │
│ 4. 接口隔离：接口要小而专                                           │
│ 5. 依赖倒置：依赖抽象，不依赖具体                                    │
│                                                                     │
│ 其他原则：                                                           │
│ • DRY：不要重复自己                                                  │
│ • KISS：保持简单                                                     │
│ • YAGNI：不要过早优化                                               │
│ • GRASP：对象设计模式                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: 系统设计的六步法？

**A**: 需求分析、高层设计、详细设计、实现、测试、部署维护。

### Q2: Go 中最常用的设计模式？

**A**: 工厂模式（创建处理器）、策略模式（竞价策略）、观察者模式（状态通知）。

### Q3: SOLID 五大原则？

**A**: 单一职责、开闭原则、里氏替换、接口隔离、依赖倒置。

---

## Go 代码实战：系统设计模式核心实现

### 1. 观察者模式（事件总线）

```go
package eventbus

import (
	"context"
	"sync"
)

// Event 事件
type Event struct {
	Type      string
	Payload   interface{}
	Timestamp int64
}

// Subscriber 订阅者
type Subscriber struct {
	ID    string
	Topic string // * 表示订阅所有
	Handler func(context.Context, *Event) error
}

// EventBus 事件总线
type EventBus struct {
	mu         sync.RWMutex
	subscribers map[string][]*Subscriber
	topics     map[string]bool
}

func NewEventBus() *EventBus {
	return &EventBus{
		subscribers: make(map[string][]*Subscriber),
		topics:      make(map[string]bool),
	}
}

func (eb *EventBus) Subscribe(topic string, handler func(context.Context, *Event) error) string {
	id := generateID()
	sub := &Subscriber{
		ID:      id,
		Topic:   topic,
		Handler: handler,
	}
	
	eb.mu.Lock()
	eb.topics[topic] = true
	eb.subscribers[topic] = append(eb.subscribers[topic], sub)
	eb.mu.Unlock()
	
	return id
}

func (eb *EventBus) Publish(ctx context.Context, event *Event) error {
	eb.mu.RLock()
	defer eb.mu.RUnlock()
	
	// 精确匹配
	for _, sub := range eb.subscribers[event.Type] {
		if err := sub.Handler(ctx, event); err != nil {
			// 单个订阅者失败，继续处理其他
			log.Error("handler error", "subscriber", sub.ID, "error", err)
		}
	}
	
	// 通配符匹配（所有订阅者）
	for _, sub := range eb.subscribers["*"] {
		if err := sub.Handler(ctx, event); err != nil {
			log.Error("wildcard handler error", "subscriber", sub.ID, "error", err)
		}
	}
	
	return nil
}

func (eb *EventBus) Unsubscribe(id string) {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	for topic, subs := range eb.subscribers {
		for i, sub := range subs {
			if sub.ID == id {
				eb.subscribers[topic] = append(subs[:i], subs[i+1:]...)
				break
			}
		}
	}
}
```

### 2. 适配器模式（统一 API 接口）

```go
package adapter

import (
	"context"
	"fmt"
)

// AdPlatform 广告平台接口（抽象）
type AdPlatform interface {
	Name() string
	CreateCampaign(ctx context.Context, campaign *Campaign) (*Campaign, error)
	GetStats(ctx context.Context, campaignID string) (*Stats, error)
	PauseCampaign(ctx context.Context, campaignID string) error
}

// Campaign 广告系列（通用模型）
type Campaign struct {
	ID          string
	Name        string
	Budget      float64
	Status      string
	Platform    string
	CreatedAt   int64
}

// Stats 统计数据（通用模型）
type Stats struct {
	Impressions int64   `json:"impressions"`
	Clicks      int64   `json:"clicks"`
	Conversions int64   `json:"conversions"`
	Spend       float64 `json:"spend"`
}

// GoogleAdsAdapter Google Ads 适配器
type GoogleAdsAdapter struct {
	client *GoogleAdsClient
}

func (a *GoogleAdsAdapter) Name() string { return "google_ads" }

func (a *GoogleAdsAdapter) CreateCampaign(ctx context.Context, campaign *Campaign) (*Campaign, error) {
	// 转换通用模型为 Google Ads SDK 模型
	gc := convertToGoogleCampaign(campaign)
	result, err := a.client.CreateCampaign(ctx, gc)
	if err != nil {
		return nil, err
	}
	return convertFromGoogleCampaign(result), nil
}

func (a *GoogleAdsAdapter) GetStats(ctx context.Context, campaignID string) (*Stats, error) {
	data, err := a.client.GetStats(ctx, campaignID)
	if err != nil {
		return nil, err
	}
	return &Stats{
		Impressions: data.Impressions,
		Clicks:      data.Clicks,
		Conversions: data.Conversions,
		Spend:       data.Spend,
	}, nil
}

func (a *GoogleAdsAdapter) PauseCampaign(ctx context.Context, campaignID string) error {
	return a.client.PauseCampaign(ctx, campaignID)
}

// MetaAdsAdapter Meta Ads 适配器
type MetaAdsAdapter struct {
	client *MetaAdsClient
}

func (a *MetaAdsAdapter) Name() string { return "meta_ads" }

func (a *MetaAdsAdapter) CreateCampaign(ctx context.Context, campaign *Campaign) (*Campaign, error) {
	mc := convertToMetaCampaign(campaign)
	result, err := a.client.CreateAdAccountCampaign(ctx, mc)
	if err != nil {
		return nil, err
	}
	return convertFromMetaCampaign(result), nil
}

func (a *MetaAdsAdapter) GetStats(ctx context.Context, campaignID string) (*Stats, error) {
	data, err := a.client.GetInsights(ctx, campaignID)
	if err != nil {
		return nil, err
	}
	return &Stats{
		Impressions: data.Reach + data.Impressions,
		Clicks:      data.LinkClicks,
		Conversions: data.Actions,
		Spend:       data.Spend,
	}, nil
}

func (a *MetaAdsAdapter) PauseCampaign(ctx context.Context, campaignID string) error {
	return a.client.UpdateCampaignStatus(ctx, campaignID, "PAUSED")
}

// PlatformRegistry 平台注册表（工厂模式）
type PlatformRegistry struct {
	adapters map[string]AdPlatform
}

func NewPlatformRegistry() *PlatformRegistry {
	return &PlatformRegistry{
		adapters: make(map[string]AdPlatform),
	}
}

func (r *PlatformRegistry) Register(p AdPlatform) {
	r.adapters[p.Name()] = p
}

func (r *PlatformRegistry) Get(name string) (AdPlatform, error) {
	p, ok := r.adapters[name]
	if !ok {
		return nil, fmt.Errorf("platform %s not registered", name)
	}
	return p, nil
}
```

### 自测题

<details>
<summary>Q1: EventBus 的 Publish 中为什么单个 handler 失败不影响其他 handler？</summary>

**答案**：

**解耦原则**：观察者模式中，每个订阅者是独立的。一个 handler 失败不应该影响其他 handler——这是 **fault isolation** 的核心思想。

**Trade-off**：
- 优点：一个模块崩溃不影响其他模块
- 缺点：需要每个 handler 自己做错误处理和重试

生产环境用 goroutine 异步执行每个 handler，避免阻塞发布者。

</details>

<details>
<summary>Q2: Adapter 模式的 convertToXXX 函数为什么不能省略？直接调用各平台 SDK 不行吗？</summary>

**答案**：

**核心目的**：**隔离变化**。

| 方案 | 优点 | 缺点 |
|------|------|------|
| 直接调用 SDK | 简单 | 业务代码耦合各平台 API |
| Adapter 模式 | 业务代码只依赖抽象接口 | 需要写转换代码 |

广告平台有 4+ 个平台（Google/Meta/TikTok/Amazon），每个平台的 API 字段名、分页方式、认证方式都不同。Adapter 让上层业务代码完全不知道底层差异。

</details>

<details>
<summary>Q3: Observer 模式中，如果订阅者数量巨大（10万+），Publish 的性能瓶颈在哪？如何优化？</summary>

**答案**：

**瓶颈**：串行遍历 10 万个 handler → O(n) 线性扫描。

**优化方案**：
```go
// 方案1: 分片并行（推荐）
// 将 subscribers 分成 N 个 shard，每个 shard 独立 goroutine 处理

// 方案2: 异步发布
// Publish 只把事件放入 channel，由 worker pool 消费

// 方案3: 主题聚合
// 相同 topic 的 handler 合并为 batch 处理

// 方案4: 使用 fan-out queue（Kafka topic）
// 替代内存中的 subscriber 列表
```

广告平台推荐方案2+4：事件入 Kafka，消费者组处理实际逻辑。

</details>
