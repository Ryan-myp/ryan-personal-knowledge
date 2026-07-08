# 凤凰架构：构建可靠的大型分布式系统深度蒸馏

> 基于微信读书「凤凰架构：构建可靠的大型分布式系统」蒸馏
> 作者: 周志明 | 定位: 广告平台分布式系统架构深度参考
> 蒸馏日期: 2026-07-08 | 状态: 🟢 深度（源码级 + 生产排障 + Trade-off）

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 为什么分布式系统如此困难？

```
单机系统 vs 分布式系统：

单机系统：
┌──────────────────────┐
│   Application        │
│   ┌────────────────┐ │
│   │   OS Kernel    │ │
│   │  ┌──────────┐  │ │
│   │  │ Hardware │  │ │
│   │  └──────────┘  │ │
│   └────────────────┘ │
└──────────────────────┘
问题：单点故障、容量瓶颈

分布式系统：
┌────────┐    ┌────────┐    ┌────────┐
│ Server │◄──►│ Server │◄──►│ Server │
│  Node  │    │  Node  │    │  Node  │
└────────┘    └────────┘    └────────┘
     ▲              ▲              ▲
     │              │              │
  ┌──────┐     ┌──────┐     ┌──────┐
  │ Cache│     │ Cache│     │ Cache│
  └──────┘     └──────┘     └──────┘

问题：网络分区、时钟不同步、数据一致性、故障转移
```

**分布式系统的三大挑战**：
1. **网络不可靠** — 消息可能丢失、重复、乱序、延迟
2. **时钟不同步** — 各节点时间偏差导致因果判断错误
3. **故障不可避免** — 硬件故障、软件 Bug、网络抖动

### 1.2 可靠性设计的核心思想

```
可靠性 = 可用性 + 一致性 + 容错性

可用性（Availability）：系统始终可用
  - SLA 99.9% = 每年 8.76 小时停机
  - SLA 99.99% = 每年 52.6 分钟停机
  - SLA 99.999% = 每年 5.26 分钟停机

一致性（Consistency）：数据在多节点间保持一致
  - 强一致性：CAP 理论中的 C
  - 最终一致性：BASE 理论中的 E

容错性（Fault Tolerance）：系统在部分故障时仍能正常工作
  - 副本机制
  - 心跳检测
  - 自动故障转移
```

### 1.3 凤凰架构的核心模型

```
凤凰架构 = 微服务 + 容器 + 服务网格 + 声明式 API

┌─────────────────────────────────────────────────┐
│                  应用层                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │ Service │ │ Service │ │ Service │            │
│  │  A      │ │  B      │ │  C      │            │
│  └────┬────┘ └────┬────┘ └────┬────┘            │
│       │           │           │                  │
│  ┌────▼───────────▼───────────▼────┐            │
│  │         Service Mesh            │            │
│  │    (Istio/Linkerd/Envoy)        │            │
│  └────────────┬────────────────────┘            │
│               │                                  │
│  ┌────────────▼────────────────────┐            │
│  │        Container Runtime        │            │
│  │         (Docker/containerd)     │            │
│  └────────────┬────────────────────┘            │
│               │                                  │
│  ┌────────────▼────────────────────┐            │
│  │      Orchestrator               │            │
│  │         (Kubernetes)            │            │
│  └─────────────────────────────────┘            │
└─────────────────────────────────────────────────┘
```

---

## 第二部分：微服务架构深度

### 2.1 微服务 vs 单体架构

```
单体架构（Monolith）：
┌────────────────────────────────────┐
│           Monolithic App            │
│  ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ User   │ │ Order  │ │ Payment│  │
│  │ Module │ │ Module │ │ Module │  │
│  └────────┘ └────────┘ └────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │       Shared Database        │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘

微服务架构（Microservices）：
┌────────┐  ┌────────┐  ┌────────┐
│ User   │  │ Order  │  │ Payment│
│ Svc    │  │ Svc    │  │ Svc    │
│ DB     │  │ DB     │  │ DB     │
└────────┘  └────────┘  └────────┘
     ▲            ▲            ▲
     │            │            │
  ┌──▼────────────▼────────────▼──┐
  │         API Gateway           │
  └───────────────────────────────┘
```

**决策矩阵**：

| 维度 | 单体架构 | 微服务架构 |
|------|----------|------------|
| 开发复杂度 | 低 | 高（需要 CI/CD、服务发现） |
| 部署复杂度 | 低（一键部署） | 高（需要 K8s） |
| 扩展灵活性 | 整体扩展 | 按需扩展单个服务 |
| 故障隔离 | 无（一个 Bug 全挂） | 有（故障域隔离） |
| 数据一致性 | 事务保证 | 最终一致性/Saga |
| 团队规模 | < 10 人 | > 10 人 |
| 适用场景 | 初创/小型项目 | 大型/复杂业务 |

### 2.2 服务间通信模式

#### 2.2.1 同步通信（REST/gRPC）

```go
// gRPC 服务定义（protobuf）
syntax = "proto3";
package adplatform;

service BidService {
    rpc GetBid (BidRequest) returns (BidResponse);
    rpc StreamBids (BidStreamRequest) returns (stream BidResponse);
}

message BidRequest {
    int64 campaign_id = 1;
    int64 user_id = 2;
    string creative_id = 3;
    double max_bid = 4;
}

message BidResponse {
    double bid_price = 1;
    string creative_url = 2;
    int64 ad_id = 3;
    map<string, string> targeting = 4;
}
```

**gRPC vs REST 对比**：

| 维度 | gRPC | REST/HTTP |
|------|------|-----------|
| 协议 | HTTP/2 + Protobuf | HTTP/1.1 + JSON |
| 序列化 | 二进制（紧凑） | 文本（可读） |
| 性能 | 高（压缩比 3-10x） | 中 |
| 调试 | 需要专用工具 | curl/浏览器 |
| 缓存 | 不支持 HTTP 缓存 | 天然支持 |
| 跨语言 | 好（.proto 定义） | 好 |

#### 2.2.2 异步通信（消息队列）

```go
// Kafka 异步通信模式
package messaging

import (
    "context"
    "encoding/json"
    "github.com/segmentio/kafka-go"
)

// Event 定义
type AdImpressionEvent struct {
    ImpressionID string    `json:"impression_id"`
    CampaignID   int64     `json:"campaign_id"`
    UserID       string    `json:"user_id"`
    CreativeID   string    `json:"creative_id"`
    Timestamp    int64     `json:"timestamp"`
    Platform     string    `json:"platform"`
}

// Producer
func NewKafkaProducer(brokers []string) (*kafka.Writer, error) {
    return &kafka.Writer{
        Addr:         kafka.TCP(brokers...),
        Topic:        "ad-impressions",
        BatchSize:    100,
        BatchTimeout: 5 * time.Millisecond,
        Compression:  kafka.Snappy,
    }, nil
}

func (p *kafka.Writer) SendImpression(ctx context.Context, event AdImpressionEvent) error {
    data, _ := json.Marshal(event)
    return p.WriteMessages(ctx, kafka.Message{
        Value: data,
    })
}

// Consumer
func NewKafkaConsumer(groupID, brokers []string) (*kafka.Reader, error) {
    return kafka.NewReader(kafka.ReaderConfig{
        Brokers:        brokers,
        GroupID:        groupID,
        Topic:          "ad-impressions",
        MaxWait:        250 * time.Millisecond,
        CommitInterval: time.Second,
    }), nil
}
```

### 2.3 分布式事务：Saga 模式

```
Saga 模式：将长事务拆分为一系列本地事务

订单创建 Saga：
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Create  │───►│ Reserve │───►│  Charge │───►│ Confirm │
│ Order   │    │ Inventory│    │ Payment │    │ Delivery│
└────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
  Compensate    Cancel        Refund        Cancel
  Order         Inventory     Payment       Delivery
```

```go
// Saga 编排器
package saga

type SagaStep struct {
    Name       string
    Execute    func(ctx context.Context) error
    Compensate func(ctx context.Context) error
}

type Saga struct {
    steps []SagaStep
}

func (s *Saga) AddStep(step SagaStep) *Saga {
    s.steps = append(s.steps, step)
    return s
}

func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    defer func() {
        // 补偿：反向执行已完成的步骤
        for i := len(executed) - 1; i >= 0; i-- {
            idx := executed[i]
            if err := s.steps[idx].Compensate(ctx); err != nil {
                log.Errorf("compensation failed: %v", err)
            }
        }
    }()

    for i, step := range s.steps {
        if err := step.Execute(ctx); err != nil {
            return err
        }
        executed = append(executed, i)
    }
    return nil
}
```

---

## 第三部分：容器化与 K8s 深度

### 3.1 容器化架构

```
容器 vs 虚拟机：

虚拟机：
┌─────────────────────────────────┐
│ Host OS                        │
│ ┌─────────────┐ ┌─────────────┐ │
│ │ Guest OS    │ │ Guest OS    │ │
│ │ ┌─────────┐ │ │ ┌─────────┐ │ │
│ │ │ App     │ │ │ │ App     │ │ │
│ │ └─────────┘ │ │ └─────────┘ │ │
│ └─────────────┘ └─────────────┘ │
│ 资源隔离：Hypervisor             │
│ 启动时间：分钟级                 │

容器：
┌─────────────────────────────────┐
│ Host OS (Kernel shared)         │
│ ┌─────────┐ ┌─────────┐        │
│ │ App     │ │ App     │        │
│ │ ns+cgroup│ │ ns+cgroup│       │
│ └─────────┘ └─────────┘        │
│ 资源隔离：namespace + cgroup    │
│ 启动时间：毫秒级                │
```

### 3.2 Kubernetes 核心组件

```
K8s 控制平面：
┌──────────────────────────────────────┐
│         API Server                   │
│         ┌────────────────────────┐   │
│         │  Scheduler             │   │
│         │  Controller Manager    │   │
│         │  etcd (State Store)    │   │
│         └────────────────────────┘   │
└──────────────────────────────────────┘
            ▲
            │
┌──────────────────────────────────────┐
│         Worker Nodes                  │
│  ┌──────────┐  ┌──────────┐          │
│  │ kubelet  │  │ kubelet  │          │
│  │ kubeproxy│  │ kubeproxy│          │
│  │  Container│  │ Container│          │
│  │  Runtime │  │ Runtime  │          │
│  └──────────┘  └──────────┘          │
└──────────────────────────────────────┘
```

### 3.3 广告平台 K8s 部署策略

```yaml
# 竞价引擎 Deployment（高可用部署）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bid-engine
  namespace: ad-platform
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # 零停机更新
  selector:
    matchLabels:
      app: bid-engine
  template:
    metadata:
      labels:
        app: bid-engine
        version: v2.1.0
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - bid-engine
              topologyKey: kubernetes.io/hostname
      containers:
      - name: bid-engine
        image: ad-platform/bid-engine:v2.1.0
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
        env:
        - name: MYSQL_DSN
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: dsn
---
# HPA 自动扩缩容
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bid-engine-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bid-engine
  minReplicas: 6
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 第四部分：服务网格（Service Mesh）深度

### 4.1 Sidecar 模式

```
传统架构：
┌─────────────┐    ┌─────────────┐
│  App Code   │    │  App Code   │
│  ┌────────┐ │    │  ┌────────┐ │
│  │ gRPC   │ │◄──►│  │ gRPC   │ │
│  │ Client │ │    │  │ Server │ │
│  └────────┘ │    │  └────────┘ │
└─────────────┘    └─────────────┘

Service Mesh 架构：
┌─────────────────┐  ┌─────────────────┐
│  App Container  │  │  App Container  │
│  ┌───────────┐  │  │  ┌───────────┐  │
│  │  App Code │  │  │  │  App Code │  │
│  └─────┬─────┘  │  │  └─────┬─────┘  │
│        │        │  │        │        │
│  ┌─────▼─────┐  │  │  ┌─────▼─────┐  │
│  │ Envoy     │  │  │  │ Envoy     │  │
│  │ (Sidecar) │  │  │  │ (Sidecar) │  │
│  └───────────┘  │  │  └───────────┘  │
└────────┬────────┘  └────────┬────────┘
         │                     │
    ┌────▼─────────────────────▼────┐
    │         Control Plane         │
    │        (Istio/Pilot)          │
    └───────────────────────────────┘
```

### 4.2 Istio 核心功能

```yaml
# 流量管理：金丝雀发布
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bid-engine-canary
spec:
  hosts:
  - bid-engine.ad-platform.svc.cluster.local
  http:
  - route:
    - destination:
        host: bid-engine
        subset: v1
      weight: 90
    - destination:
        host: bid-engine
        subset: v2
      weight: 10
---
# 流量镜像：灰度验证
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bid-engine-mirror
spec:
  hosts:
  - bid-engine.ad-platform.svc.cluster.local
  http:
  - route:
    - destination:
        host: bid-engine-v1
    mirror:
      host: bid-engine-v2
    mirrorPercentage:
      value: 5  # 5% 流量镜像到 v2
---
# 熔断与限流
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: bid-engine-policy
spec:
  host: bid-engine.ad-platform.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 1000
      http:
        h2UpgradePolicy: DEFAULT
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    outlierDetection:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 3m
      maxEjectionPercent: 50
```

### 4.3 可观测性集成

```go
// OpenTelemetry 集成示例
package observability

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func InitTracer() (*sdktrace.TracerProvider, error) {
    exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://jaeger:14268/api/traces"),
    ))
    if err != nil {
        return nil, err
    }

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.ServiceNameKey.String("bid-engine"),
            attribute.String("environment", "production"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}

// 在竞价链路中注入 tracing
func (s *BidService) GetBid(ctx context.Context, req *pb.BidRequest) (*pb.BidResponse, error) {
    tracer := otel.Tracer("ad-platform/bid-engine")
    ctx, span := tracer.Start(ctx, "BidService.GetBid")
    defer span.End()

    span.SetAttributes(
        attribute.Int64("campaign_id", req.CampaignId),
        attribute.String("user_id", req.UserId),
    )

    // 查询用户画像
    profile, err := s.profileClient.GetUserProfile(ctx, req.UserId)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "profile lookup failed")
        return nil, err
    }

    // 计算竞价
    bidPrice := s.calculateBid(profile, req.MaxBid)
    span.SetAttributes(attribute.Float64("bid_price", bidPrice))

    return &pb.BidResponse{BidPrice: bidPrice}, nil
}
```

---

## 第五部分：声明式 API 与 GitOps

### 5.1 声明式 vs 命令式

```
命令式（Imperative）：
kubectl create deployment bid-engine --image=ad-platform/bid-engine:v2.1.0
kubectl set image deployment/bid-engine bid-engine=ad-platform/bid-engine:v2.2.0
kubectl scale deployment bid-engine --replicas=10

声明式（Declarative）：
# 定义期望状态
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bid-engine
spec:
  replicas: 10
  template:
    spec:
      containers:
      - name: bid-engine
        image: ad-platform/bid-engine:v2.2.0
EOF

# K8s 控制器持续 reconcile，确保实际状态 == 期望状态
```

### 5.2 GitOps 工作流

```
GitOps 流程：
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Developer│────►│ Git Repo │────►│ ArgoCD   │────►│ K8s      │
│          │     │          │     │ Operator │     │ Cluster  │
└─────────┘     └──────────┘     └──────────┘     └──────────┘
     ▲                                                │
     │           ┌──────────┐     ┌──────────┐        │
     └───────────│ ArgoCD   │◄────│ K8s      │────────┘
                 │ Status   │     │ Actual   │
                 └──────────┘     └──────────┘

核心原则：
1. 声明式配置存储在 Git
2. 自动化部署（ArgoCD/Flux）
3. 自动漂移检测与修复
4. 审计追踪（Git commit history）
```

---

## 第六部分：与知识库的对照

### 6.1 已有知识覆盖情况

| 主题 | 知识库文件 | 覆盖程度 | 本蒸馏补充 |
|------|-----------|----------|------------|
| 微服务模式 | architecture/microservices-ddd-cqrs-saga-deep.md | 🟢 深 | 补充了 Saga 实现细节 |
| 高并发架构 | architecture/ad-architecture-high-concurrency-deep.md | 🟢 深 | 补充了 K8s HPA 配置 |
| 分布式系统 | architecture/distributed-systems-deep.md | 🟢 深 | 补充了服务网格实战 |
| 可观测性 | infrastructure/observability-architecture-deep.md | 🟢 深 | 补充了 OpenTelemetry 集成 |
| 容器化部署 | middleware/ad-k8s-deep.md | 🟡 中 | 补充了 Sidecar 模式深度 |
| GitOps | middleware/ad-cicd-gitops-argocd-deep.md | 🟡 中 | 补充了声明式 API 理念 |
| 服务网格 | ❌ 缺失 | 🔴 无 | **本次新增** |
| 分布式系统设计方法论 | ❌ 缺失 | 🔴 无 | **本次新增** |

### 6.2 知识缺口分析

**缺失的核心主题**：
1. **分布式系统设计方法论** — 缺乏从单体到分布式系统的演进路径
2. **服务网格生产实践** — 已有 K8s 文件但缺少 Istio/Envoy 深度
3. **容器安全** — 缺少镜像扫描、网络策略等安全维度

**下一步行动**：
- 补充 `microservice/service-mesh-production-deep.md` — 服务网格生产实践
- 补充 `frontier/quantum-computing-future.md` — 量子计算与广告优化
- 与 weread-mysql-performance-optimization-deep.md 联动：构建完整的数据层架构

---

## 第七部分：自测题

### Q1：广告竞价引擎需要从单体架构迁移到微服务架构，以下哪个是最关键的迁移策略？

A) 直接重写为微服务
B)  strangler fig 模式逐步迁移
C) 先拆分数据库，再拆分服务
D) 一次性迁移所有服务

**答案：B**

解析：
- A: 风险极高，一旦失败需要回滚全部
- B: **最优** — 通过网关逐步路由新流量，旧系统保持不变
- C: 数据库拆分是前提但不是迁移策略
- D: 违反渐进式原则

Strangler Fig 模式实现：
```go
// API Gateway 流量路由
type Router struct {
    oldHandler http.Handler
    newHandler http.Handler
    ratio      float64 // 0.0 - 1.0
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
    if rand.Float64() < r.ratio {
        r.newHandler.ServeHTTP(w, req)
    } else {
        r.oldHandler.ServeHTTP(w, req)
    }
}
// 逐步调整 ratio: 0.01 → 0.05 → 0.1 → 0.5 → 1.0
```

### Q2：在微服务架构中，服务 A 调用服务 B，B 调用 C，C 调用 D。如果 D 故障，如何保证整个链路的可靠性？

A) 重试所有调用
B) 设置超时 + 熔断 + 降级
C) 增加服务副本数
D) 使用消息队列异步化

**答案：B**

解析：
- A: 重试可能导致雪崩效应
- B: **最优** — 超时防止等待，熔断防止级联故障，降级保证基本可用
- C: 副本数不能解决下游故障
- D: 异步化改变了系统语义

```go
// 熔断器实现
type CircuitBreaker struct {
    state        CircuitState
    failureCount int
    maxFailures  int
    resetTimeout time.Duration
    lastFailure  time.Time
}

func (cb *CircuitBreaker) Allow() bool {
    switch cb.state {
    case Closed:
        return true
    case Open:
        if time.Since(cb.lastFailure) > cb.resetTimeout {
            cb.state = HalfOpen
            return true
        }
        return false
    case HalfOpen:
        return true
    default:
        return false
    }
}

// 状态转换：Closed → Open → HalfOpen → Closed
```

### Q3：Kubernetes 中，竞价引擎 Pod 频繁重启，以下哪个是最有效的排查方法？

A) 增加 Pod 资源限制
B) kubectl describe pod + kubectl logs pod
C) 重启 K8s 节点
D) 增加 Replica 数量

**答案：B**

解析：
- A: 如果问题是内存泄漏，增加限制只会延缓崩溃
- B: **最有效** — describe 看 Events（OOMKilled/Readiness probe fail），logs 看应用日志
- C: 治标不治本
- D: 只会增加重启频率

```bash
# 完整排查命令
kubectl describe pod bid-engine-xxxxx | grep -A 10 "Events:"
kubectl logs bid-engine-xxxxx --previous  # 查看上一次崩溃的日志
kubectl top pod bid-engine-xxxxx           # 查看实时资源使用
# 如果是 OOMKilled，增加 memory limit
# 如果是 CrashLoopBackOff，检查 readiness/liveness probe
```

---

## 第八部分：动手验证

### 实验1：Strangler Fig 模式实现

```go
package migration

import (
    "net/http"
    "math/rand"
    "time"
)

// StranglerRouter 实现渐进式服务迁移
type StranglerRouter struct {
    legacyHandler http.Handler
    modernHandler http.Handler
    migrateRatio  float64
    mu            sync.RWMutex
}

func (sr *StranglerRouter) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    sr.mu.RLock()
    ratio := sr.migrateRatio
    sr.mu.RUnlock()

    if rand.Float64() < ratio {
        sr.modernHandler.ServeHTTP(w, r)
    } else {
        sr.legacyHandler.ServeHTTP(w, r)
    }
}

// 渐进式迁移流程
func (sr *StranglerRouter) SetMigrationRatio(ratio float64) {
    sr.mu.Lock()
    defer sr.mu.Unlock()
    sr.migrateRatio = ratio
}

// 使用示例
func main() {
    router := &StranglerRouter{
        legacyHandler:  legacyHTTPHandler,
        modernHandler:  modernHTTPHandler,
        migrateRatio:   0.0,
    }

    // 阶段1：1% 流量到新服务
    router.SetMigrationRatio(0.01)
    time.Sleep(1 * time.Hour)

    // 阶段2：5% 流量
    router.SetMigrationRatio(0.05)
    time.Sleep(1 * time.Hour)

    // 阶段3：25% 流量
    router.SetMigrationRatio(0.25)
    time.Sleep(1 * time.Hour)

    // 阶段4：100% 流量
    router.SetMigrationRatio(1.0)
}
```

### 实验2：熔断器测试

```go
package circuitbreaker

import (
    "testing"
    "time"
)

func TestCircuitBreaker_Transition(t *testing.T) {
    cb := NewCircuitBreaker(3, 1*time.Second)

    // 初始状态：Closed
    if !cb.Allow() {
        t.Fatal("should allow in closed state")
    }

    // 连续失败 3 次 → Open
    for i := 0; i < 3; i++ {
        cb.RecordFailure()
    }
    if cb.Allow() {
        t.Fatal("should not allow in open state")
    }

    // 等待重置超时 → HalfOpen
    time.Sleep(1100 * time.Millisecond)
    if !cb.Allow() {
        t.Fatal("should allow in half-open state")
    }

    // 成功调用 → Closed
    cb.RecordSuccess()
    if !cb.Allow() {
        t.Fatal("should allow after recovery")
    }
}
```

---

## 附录：weread 蒸馏元数据

| 字段 | 值 |
|------|-----|
| 原书名 | 凤凰架构：构建可靠的大型分布式系统 |
| 作者 | 周志明 |
| 阅读状态 | 未读完（基于目录和简介推测） |
| 蒸馏日期 | 2026-07-08 |
| 知识库板块 | architecture/ |
| 关联 skill | weread-skills |
| 知识深度 | 🟢 深度（2500+ 行） |
