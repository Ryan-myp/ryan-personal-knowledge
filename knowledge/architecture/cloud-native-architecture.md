# 云原生架构：Service Mesh/Serverless/边缘计算

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解云原生

```
传统架构 = 自建房屋
  → 自己建水管、电线、网络
  → 维护成本高
  → 扩展困难

云原生 = 住酒店
  → 基础设施由酒店提供
  → 按需付费
  → 随时扩展
```

### 云原生核心原则

```
1. 容器化：应用打包成容器
2. 微服务：拆分为小服务
3. DevOps：自动化部署
4. CI/CD：持续集成/持续交付
5. Service Mesh：服务治理
6. Serverless：无服务器
7. GitOps：配置即代码
```

---

## 第二部分：Service Mesh

### 2.1 Service Mesh 原理

```
Service Mesh = 基础设施层

传统架构：
App → App → App（服务间直接通信）

Service Mesh 架构：
App → Sidecar Proxy → Sidecar Proxy → Sidecar Proxy

Sidecar 负责：
- 服务发现
- 负载均衡
- 熔断降级
- 流量控制
- 监控日志
- 安全认证
```

### 2.2 Go 实现 Sidecar Proxy

```go
package mesh

import (
    "context"
    "net/http"
    "time"
)

// SidecarProxy Sidecar 代理
type SidecarProxy struct {
    server       *http.Server
    circuitBreaker *CircuitBreaker
    rateLimiter    *RateLimiter
    metrics      *MetricsCollector
}

// RoundTrip 请求转发
func (sp *SidecarProxy) RoundTrip(req *http.Request) (*http.Response, error) {
    // 1. 限流
    if !sp.rateLimiter.Allow() {
        return nil, fmt.Errorf("rate limited")
    }
    
    // 2. 熔断检查
    if !sp.circuitBreaker.AllowRequest() {
        return nil, fmt.Errorf("circuit breaker open")
    }
    
    // 3. 记录指标
    start := time.Now()
    
    // 4. 转发请求
    resp, err := sp.forwardRequest(req)
    
    // 5. 记录结果
    duration := time.Since(start)
    sp.metrics.RecordRequest(req.URL.Path, duration, err)
    
    if err != nil {
        sp.circuitBreaker.RecordFailure()
        return nil, err
    }
    
    sp.circuitBreaker.RecordSuccess()
    return resp, nil
}

func (sp *SidecarProxy) forwardRequest(req *http.Request) (*http.Response, error) {
    // 服务发现
    target, err := sp.discovery.FindTarget(req.URL.Host)
    if err != nil {
        return nil, err
    }
    
    // 负载均衡
    instance := sp.loadBalancer.Select(target.Instances)
    
    // 转发
    req.URL.Host = instance.Address
    return http.DefaultTransport.RoundTrip(req)
}
```

### 2.3 Istio 核心组件

```
Istio 架构：

Control Plane（控制面）：
- Pilot：服务发现和配置分发
- Citadel：证书管理
- Galley：配置验证

Data Plane（数据面）：
- Envoy：Sidecar 代理
- 负责流量转发、负载均衡、熔断等
```

---

## 第三部分：Serverless

### 3.1 Serverless 原理

```
Serverless = 事件驱动 + 按需执行

传统部署：
EC2/K8s → 一直运行 → 按实例付费

Serverless：
Lambda/FaaS → 事件触发 → 按调用次数付费

优势：
1. 无需管理服务器
2. 自动扩缩容
3. 按实际使用付费
4. 开发效率高

劣势：
1. 冷启动延迟
2. 执行时长限制
3. 厂商锁定
```

### 3.2 Go 实现 Serverless 函数

```go
package serverless

import (
    "context"
    "encoding/json"
    "fmt"
)

// Handler 函数处理器接口
type Handler interface {
    Handle(ctx context.Context, event Event) (Response, error)
}

// Event 事件
type Event struct {
    ID        string                 `json:"id"`
    Type      string                 `json:"type"`
    Payload   map[string]interface{} `json:"payload"`
    Timestamp time.Time              `json:"timestamp"`
}

// Response 响应
type Response struct {
    StatusCode int                    `json:"statusCode"`
    Body       map[string]interface{} `json:"body"`
}

// Function 无服务器函数
type Function struct {
    name    string
    handler Handler
}

// NewFunction 创建函数
func NewFunction(name string, handler Handler) *Function {
    return &Function{
        name:    name,
        handler: handler,
    }
}

// Invoke 调用函数
func (f *Function) Invoke(ctx context.Context, event Event) (*Response, error) {
    start := time.Now()
    
    // 执行处理
    resp, err := f.handler.Handle(ctx, event)
    
    // 记录执行时间
    duration := time.Since(start)
    log.Printf("Function %s executed in %v", f.name, duration)
    
    if err != nil {
        return &Response{
            StatusCode: 500,
            Body:       map[string]interface{}{"error": err.Error()},
        }, nil
    }
    
    return &resp, nil
}

// 使用示例
type BidHandler struct{}

func (h *BidHandler) Handle(ctx context.Context, event Event) (Response, error) {
    // 处理竞价事件
    payload := event.Payload
    
    // 执行竞价逻辑
    result := executeBid(payload)
    
    return Response{
        StatusCode: 200,
        Body:       result,
    }, nil
}
```

---

## 第四部分：边缘计算

### 4.1 边缘计算原理

```
边缘计算 = 在靠近用户的地方处理数据

传统架构：
User → Cloud → Process → Cloud → User

边缘计算架构：
User → Edge Node → Process → User

优势：
1. 低延迟：减少网络往返
2. 带宽节省：本地处理
3. 隐私保护：数据不离境

应用场景：
- 实时竞价（广告）
- IoT 数据处理
- CDN 动态内容
```

### 4.2 Go 实现边缘节点

```go
package edge

import (
    "context"
    "sync"
    "time"
)

// EdgeNode 边缘节点
type EdgeNode struct {
    id         string
    location   string
    cache      *LocalCache
    upstream   *UpstreamClient
    mu         sync.RWMutex
}

// LocalCache 本地缓存
type LocalCache struct {
    data   map[string]*cacheItem
    maxAge time.Duration
}

type cacheItem struct {
    value     interface{}
    createdAt time.Time
}

// ProcessRequest 处理请求
func (en *EdgeNode) ProcessRequest(ctx context.Context, req *Request) (*Response, error) {
    // 1. 检查本地缓存
    if cached := en.cache.Get(req.Key); cached != nil {
        return &Response{
            Data:   cached,
            Source: "cache",
        }, nil
    }
    
    // 2. 向上游请求
    resp, err := en.upstream.Fetch(ctx, req)
    if err != nil {
        return nil, err
    }
    
    // 3. 缓存结果
    en.cache.Set(req.Key, resp.Data)
    
    return &Response{
        Data:   resp.Data,
        Source: "upstream",
    }, nil
}

// UpstreamClient 上游客户端
type UpstreamClient struct {
    baseURL string
    client  *http.Client
}

func (uc *UpstreamClient) Fetch(ctx context.Context, req *Request) (*Response, error) {
    // 请求上游服务
    // ...
    return nil, nil
}
```

---

## 第五部分：生产排障案例

### 5.1 Service Mesh 性能问题

```
现象：Service Mesh 引入后延迟增加

排查：
1. 检查 Sidecar 代理开销
2. 检查 mTLS 证书轮换
3. 检查链路追踪 overhead

根因：Sidecar 增加了网络跳数

解决方案：
1. 优化 Sidecar 配置
2. 使用 eBPF 替代 Sidecar
3. 启用连接池
```

### 5.2 Serverless 冷启动

```
现象：Lambda 函数冷启动时间长

排查：
1. 检查函数初始化时间
2. 检查依赖库大小
3. 检查运行时配置

根因：Go 函数初始化慢

解决方案：
1. 使用 Provisioned Concurrency
2. 优化函数体积
3. 使用 warmed invocation
```

---

## 第六部分：自测题

### 问题 1
Service Mesh 相比传统服务通信有什么优势？

<details>
<summary>查看答案</summary>

1. **解耦**：服务逻辑和基础设施分离
2. **可观测性**：内置监控和日志
3. **安全**：mTLS 自动管理
4. **流量控制**：灰度发布、熔断、限流
5. **Go 实现**：Sidecar Proxy

</details>

### 问题 2
Serverless 的优缺点是什么？

<details>
<summary>查看答案</summary>

1. **优点**：无需管理服务器、自动扩缩容
2. **缺点**：冷启动延迟、厂商锁定
3. **适用场景**：事件驱动、不规则流量
4. **不适用**：长时间运行、状态密集
5. **Go 实现**：Function Handler

</details>

### 问题 3
边缘计算适合什么场景？

<details>
<summary>查看答案</summary>

1. **低延迟要求**：实时竞价
2. **带宽敏感**：视频处理
3. **数据本地化**：IoT 设备
4. **隐私合规**：数据不离境
5. **Go 实现**：EdgeNode

</details>

---

*本文档基于云原生架构原理整理。*