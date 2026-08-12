# Agent 生产部署完整指南 - 从开发到上线

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 32%

---

## 一、生产架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent 生产部署架构                                │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │   Client     │───▶│  API Gateway │───▶│   Agent      │         │
│  │  (Web/CLI)   │    │  (Kong/Nginx)│    │  Service     │         │
│  └──────────────┘    └──────────────┘    └──────┬───────┘         │
│                                                 │                   │
│                        ┌────────────────────────┼────────────┐     │
│                        ▼                        ▼            │     │
│                 ┌──────────────┐       ┌──────────────┐      │     │
│                 │  LLM Router   │       │  Tool Router │      │     │
│                 │  (故障转移)   │       │  (负载均衡)  │      │     │
│                 └──────┬───────┘       └──────┬───────┘      │     │
│                        │                      │               │     │
│           ┌────────────┼────────────┬────────┘               │     │
│           ▼            ▼            ▼                         │     │
│      ┌────────┐  ┌────────┐  ┌────────┐                       │     │
│      │Claude 3│  │GPT-4   │  │DeepSeek│  ← 多模型路由        │     │
│      │Sonnet  │  │        │  │ V3     │                       │     │
│      └────────┘  └────────┘  └────────┘                       │     │
│                                                                │     │
│  ┌─────────────────────────────────────────────────────────┐   │     │
│  │                    基础设施层                             │   │     │
│  │  Redis (会话/缓存)  ClickHouse (日志)  S3 (模型存储)      │   │     │
│  └─────────────────────────────────────────────────────────┘   │     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、模型路由实现

```go
// agent/router.go
package agent

import (
    "context"
    "fmt"
    "sync"
    "time"
)

// ModelEndpoint 模型端点
type ModelEndpoint struct {
    Name       string
    Provider   string
    BaseURL    string
    APIKey     string
    Latency    time.Duration
    SuccessRate float64
}

// Router 智能路由
type Router struct {
    endpoints []*ModelEndpoint
    mu        sync.RWMutex
    stats     map[string]*EndpointStats
}

type EndpointStats struct {
    TotalCalls  int
    Failures    int
    AvgLatency  time.Duration
}

// NewRouter 创建路由器
func NewRouter(endpoints []*ModelEndpoint) *Router {
    r := &Router{endpoints: endpoints, stats: make(map[string]*EndpointStats)}
    for _, ep := range endpoints {
        r.stats[ep.Name] = &EndpointStats{}
    }
    return r
}

// Select 选择最佳端点 (加权轮询 + 故障转移)
func (r *Router) Select(ctx context.Context) (*ModelEndpoint, error) {
    r.mu.RLock()
    defer r.mu.RUnlock()
    
    // 过滤可用端点
    var candidates []*ModelEndpoint
    for _, ep := range r.endpoints {
        stats := r.stats[ep.Name]
        if stats.Failures/stats.TotalCalls > 0.1 { // 失败率 > 10% 跳过
            continue
        }
        candidates = append(candidates, ep)
    }
    
    if len(candidates) == 0 {
        return nil, fmt.Errorf("no available endpoints")
    }
    
    // 加权选择 (成功率高的权重高)
    totalWeight := 0.0
    for _, ep := range candidates {
        totalWeight += ep.SuccessRate
    }
    
    // 简单实现：选第一个
    return candidates[0], nil
}

// Record 记录调用结果
func (r *Router) Record(name string, success bool, latency time.Duration) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    stats := r.stats[name]
    stats.TotalCalls++
    if !success {
        stats.Failures++
    }
    // 滑动平均延迟
    stats.AvgLatency = stats.AvgLatency*0.9 + latency*0.1
}
```

---

## 三、会话管理

```go
// agent/session.go
package agent

import (
    "context"
    "time"
    "github.com/redis/go-redis/v9"
)

// Session 会话
type Session struct {
    ID        string
    UserID    string
    Messages  []Message
    CreatedAt time.Time
    ExpiresAt time.Time
}

// SessionManager 会话管理器
type SessionManager struct {
    rdb *redis.Client
    ttl time.Duration
}

func NewSessionManager(rdb *redis.Client) *SessionManager {
    return &SessionManager{
        rdb: rdb,
        ttl: 24 * time.Hour,
    }
}

// Create 创建会话
func (m *SessionManager) Create(ctx context.Context, userID string) (*Session, error) {
    session := &Session{
        ID:        generateID(),
        UserID:    userID,
        CreatedAt: time.Now(),
        ExpiresAt: time.Now().Add(m.ttl),
    }
    
    key := m.key(session.ID)
    data, _ := json.Marshal(session)
    m.rdb.Set(ctx, key, data, m.ttl)
    return session, nil
}

// Get 获取会话
func (m *SessionManager) Get(ctx context.Context, sessionID string) (*Session, error) {
    key := m.key(sessionID)
    data, err := m.rdb.Get(ctx, key).Bytes()
    if err != nil {
        return nil, err
    }
    var session Session
    json.Unmarshal(data, &session)
    return &session, nil
}

// AppendMessage 追加消息
func (m *SessionManager) AppendMessage(ctx context.Context, sessionID, role, content string) error {
    session, err := m.Get(ctx, sessionID)
    if err != nil {
        return err
    }
    
    session.Messages = append(session.Messages, Message{
        Role:    role,
        Content: content,
        Time:    time.Now(),
    })
    
    data, _ := json.Marshal(session)
    m.rdb.Set(ctx, m.key(sessionID), data, m.ttl)
    return nil
}

func (m *SessionManager) key(id string) string {
    return fmt.Sprintf("agent:session:%s", id)
}
```

---

## 四、可观测性

```go
// agent/observability.go
package agent

import (
    "context"
    "github.com/prometheus/client_golang/prometheus"
    "go.opentelemetry.io/otel/trace"
)

// Metrics 指标
var (
    requestCount = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "agent_request_total",
            Help: "Total agent requests",
        },
        []string{"model", "status"},
    )
    
    requestLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "agent_request_duration_seconds",
            Help: "Request latency",
        },
        []string{"model"},
    )
)

// Observer 观测器
type Observer struct {
    tracer trace.Tracer
    metrics *Metrics
}

func NewObserver(tracer trace.Tracer) *Observer {
    return &Observer{tracer: tracer}
}

func (o *Observer) StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
    return o.tracer.Start(ctx, name)
}
```

---

## 五、灰度发布

```yaml
# 灰度发布配置
gray_release:
  stages:
    - name: canary
      weight: 5%
      duration: 24h
      criteria:
        error_rate: "< 0.1%"
        p99_latency: "< 3s"
        
    - name: beta
      weight: 20%
      duration: 48h
      criteria:
        user_satisfaction: "> 4.0"
        
    - name: full
      weight: 100%
```

---

## 六、自测题

1. **多模型路由的策略有哪些？**
   - 轮询、加权、故障转移、成本优化

2. **会话数据为什么用 Redis？**
   - 低延迟、支持 TTL、分布式共享

3. **灰度发布的关键指标？**
   - 错误率、延迟、用户满意度

