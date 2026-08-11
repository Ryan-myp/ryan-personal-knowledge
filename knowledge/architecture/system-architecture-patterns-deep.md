# 系统架构设计模式深度解析

> 深入系统架构设计模式：微服务、事件驱动、CQRS、Saga、API Gateway。
> 包含真实生产环境架构设计。
> 适用对象：架构师、技术负责人

---

## 1. 微服务架构

### 1.1 架构模式

```
微服务架构模式：

┌─────────────────────────────────────────────────────────────┐
│                  微服务架构                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API Gateway (API 网关)                                      │
│  ├── 路由转发                                                │
│  ├── 认证授权                                                │
│  ├── 限流熔断                                                │
│  └── 日志监控                                                │
│                                                             │
│  服务注册中心                                                 │
│  ├── Eureka / Consul / Nacos                               │
│  └── 服务发现与健康检查                                      │
│                                                             │
│  服务集群                                                     │
│  ├── 用户服务                                                │
│  ├── 订单服务                                                │
│  ├── 支付服务                                                │
│  ├── 商品服务                                                │
│  └── ...                                                     │
│                                                             │
│  基础设施                                                     │
│  ├── 消息队列                                                │
│  ├── 配置中心                                                │
│  ├── 链路追踪                                                │
│  └── 日志收集                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现 API Gateway

```go
// api_gateway.go

package gateway

import (
    "context"
    "net/http"
    "net/http/httputil"
    "net/url"
)

type Gateway struct {
    services map[string]*Service
}

type Service struct {
    Name     string
    URL      *url.URL
    Client   *http.Client
}

func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // 路由匹配
    service := g.matchService(r)
    if service == nil {
        http.Error(w, "service not found", http.StatusNotFound)
        return
    }
    
    // 反向代理
    proxy := httputil.NewSingleHostReverseProxy(service.URL)
    proxy.ServeHTTP(w, r)
}

func (g *Gateway) matchService(r *http.Request) *Service {
    path := r.URL.Path
    for _, service := range g.services {
        if len(path) > len(service.Name) && path[:len(service.Name)] == service.Name {
            return service
        }
    }
    return nil
}
```

---

## 2. 事件驱动架构

### 2.1 架构模式

```
事件驱动架构 (EDA)：

┌─────────────────────────────────────────────────────────────┐
│                  事件驱动架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Event Producer (事件生产者)                                  │
│  ├── 业务服务                                                │
│  └── 发布事件到 Broker                                        │
│                                                             │
│  Event Broker (事件代理)                                      │
│  ├── Kafka / RabbitMQ / Pulsar                              │
│  └── 消息持久化和分发                                         │
│                                                             │
│  Event Consumer (事件消费者)                                  │
│  ├── 订阅事件                                                │
│  ├── 处理业务逻辑                                             │
│  └── 触发下游操作                                             │
│                                                             │
│  Event Store (事件存储)                                       │
│  └── 持久化事件历史                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现事件总线

```go
// event_bus.go

package event

import (
    "sync"
)

type EventHandler func(event Event)

type Event struct {
    Type      string
    Payload   map[string]interface{}
    Timestamp int64
}

type EventBus struct {
    handlers map[string][]EventHandler
    mu       sync.RWMutex
}

func NewEventBus() *EventBus {
    return &EventBus{
        handlers: make(map[string][]EventHandler),
    }
}

func (eb *EventBus) Subscribe(eventType string, handler EventHandler) {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    eb.handlers[eventType] = append(eb.handlers[eventType], handler)
}

func (eb *EventBus) Unsubscribe(eventType string, handler EventHandler) {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    
    handlers := eb.handlers[eventType]
    for i, h := range handlers {
        if h == handler {
            eb.handlers[eventType] = append(handlers[:i], handlers[i+1:]...)
            break
        }
    }
}

func (eb *EventBus) Publish(event Event) {
    eb.mu.RLock()
    defer eb.mu.RUnlock()
    
    for _, handler := range eb.handlers[event.Type] {
        go handler(event)
    }
}
```

---

## 3. CQRS 模式

### 3.1 架构说明

```
CQRS (Command Query Responsibility Segregation)：

命令侧 (Command Side)：
├── Command Handler
├── Domain Model
├── Event Sourcing
└── Write Model

查询侧 (Query Side)：
├── Query Handler
├── Read Model
├── Projections
└── Read Model (优化)
```

### 3.2 Go 实现 CQRS

```go
// cqrs.go

package cqrs

import (
    "sync"
)

type Command interface {
    GetID() string
}

type Query interface {
    GetID() string
}

type Handler interface {
    Handle(cmd interface{}) error
}

type QueryHandler interface {
    HandleQuery(query Query) (interface{}, error)
}

type CQRS struct {
    commands  map[string]Handler
    queries   map[string]QueryHandler
    mu        sync.RWMutex
}

func NewCQRS() *CQRS {
    return &CQRS{
        commands: make(map[string]Handler),
        queries:  make(map[string]QueryHandler),
    }
}

func (cqrs *CQRS) RegisterCommand(name string, handler Handler) {
    cqrs.mu.Lock()
    defer cqrs.mu.Unlock()
    cqrs.commands[name] = handler
}

func (cqrs *CQRS) RegisterQuery(name string, handler QueryHandler) {
    cqrs.mu.Lock()
    defer cqrs.mu.Unlock()
    cqrs.queries[name] = handler
}

func (cqrs *CQRS) ExecuteCommand(cmd Command) error {
    cqrs.mu.RLock()
    handler, ok := cqrs.commands[cmd.GetID()]
    cqrs.mu.RUnlock()
    
    if !ok {
        return ErrCommandNotFound
    }
    
    return handler.Handle(cmd)
}

func (cqrs *CQRS) ExecuteQuery(query Query) (interface{}, error) {
    cqrs.mu.RLock()
    handler, ok := cqrs.queries[query.GetID()]
    cqrs.mu.RUnlock()
    
    if !ok {
        return nil, ErrQueryNotFound
    }
    
    return handler.HandleQuery(query)
}
```

---

## 4. Saga 模式

### 4.1 编排与协同

```
Saga 两种实现模式：

1. 编排式 (Orchestration)
   ├── 中心化编排器
   ├── 明确定义流程
   └── 适合简单场景

2. 协同式 (Choreography)
   ├── 事件驱动
   ├── 去中心化
   └── 适合复杂场景
```

### 4.2 Go 实现编排式 Saga

```go
// saga_orchestration.go

package saga

import (
    "context"
    "fmt"
)

type Step struct {
    Name         string
    Action       func(ctx context.Context) error
    Compensate   func(ctx context.Context) error
}

type Saga struct {
    Name   string
    Steps  []*Step
}

func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    defer s.compensate(ctx, executed)
    
    for i, step := range s.Steps {
        if err := step.Action(ctx); err != nil {
            executed = append(executed, i)
            return fmt.Errorf("step %s failed: %w", step.Name, err)
        }
        executed = append(executed, i)
    }
    return nil
}

func (s *Saga) compensate(ctx context.Context, executed []int) {
    for i := len(executed) - 1; i >= 0; i-- {
        step := s.Steps[executed[i]]
        if err := step.Compensate(ctx); err != nil {
            // 记录补偿失败
        }
    }
}
```

---

## 5. API Gateway 模式

### 5.1 功能架构

```
API Gateway 核心功能：

┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  请求处理                                                    │
│  ├── 路由 (Routing)                                         │
│  ├── 负载均衡 (Load Balancing)                              │
│  └── 协议转换 (Protocol Translation)                        │
│                                                             │
│  安全                                                        │
│  ├── 认证 (Authentication)                                  │
│  ├── 授权 (Authorization)                                   │
│  └── 限流 (Rate Limiting)                                   │
│                                                             │
│  可观测性                                                    │
│  ├── 日志 (Logging)                                         │
│  ├── 监控 (Monitoring)                                      │
│  └── 链路追踪 (Tracing)                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 总结

### 6.1 架构模式对比

| 模式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 微服务 | 大型系统 | 独立部署 | 复杂度高 |
| 事件驱动 | 异步场景 | 解耦 | 调试困难 |
| CQRS | 读写比例悬殊 | 读写优化 | 数据一致 |
| Saga | 分布式事务 | 最终一致 | 补偿复杂 |

### 6.2 最佳实践

- [ ] 根据场景选择架构模式
- [ ] 合理划分服务边界
- [ ] 设计幂等操作
- [ ] 建立可观测性
- [ ] 持续演进架构

---

*最后更新：2026-08-11*
*作者：Ryan*
