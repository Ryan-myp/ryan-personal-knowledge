# gRPC 传输层深度解析：HTTP/2 框架下的 RPC 系统

> 来源：gRPC Go 源码 / HTTP/2 RFC 7540 / 《gRPC: Up and Running》
> 蒸馏日期：2026-07-10
> 板块：network | 深度等级：🟢

---

## 一、入门引导：为什么 gRPC 选择 HTTP/2？

### 1.1 传统 REST vs gRPC

```
REST API (HTTP/1.1):
客户端                          服务器
  |── GET /api/users/123 ──────►|
  |   Host: api.example.com     |
  |   Accept: application/json  |
  |◄── 200 OK ─────────────────|
  |   Content-Type: application/json
  |   {"id": 123, "name": "Ryan"}
  |
  |── POST /api/bids ──────────►|
  |   {"campaign_id": 456, ...} |
  |◄── 201 Created ────────────|
  |   {"bid_id": 789}           |

问题:
- 每次请求都是独立的 TCP 连接（或 keep-alive 但串行）
- JSON 序列化/反序列化开销大
- 强类型约束弱（合同靠文档维护）
- 无法服务端推送

gRPC (HTTP/2):
客户端                          服务器
  |── [SETTINGS] ──────────────►|  ← 连接建立，交换参数
  |◄── [SETTINGS] ──────────────|
  |                                |
  |── [HEADERS][DATA] ──────────►|  ← Stream 1: GetUser
  |◄── [HEADERS][DATA] ──────────|
  |── [HEADERS][DATA] ──────────►|  ← Stream 2: CreateBid
  |◄── [HEADERS][DATA] ──────────|
  |── [HEADERS][DATA] ──────────►|  ← Stream 3: ListBids
  |◄── [HEADERS][DATA] ──────────|
  |                                |
  |◄── [DATA] ───────────────────|  ← Server Streaming
  |◄── [DATA] ───────────────────|
  |◄── [DATA] ───────────────────|
```

### 1.2 HTTP/2 的关键特性

| 特性 | REST (HTTP/1.1) | gRPC (HTTP/2) |
|------|----------------|---------------|
| 多路复用 | ❌ 串行或 H2 连接合并 | ✅ 原生支持 |
| 二进制帧 | ❌ 文本协议 | ✅ 二进制协议 |
| 头部压缩 | ❌ 无 | ✅ HPACK |
| 服务端推送 | ❌ 无 | ✅ PUSH_PROMISE |
| 流量控制 | ❌ 无 | ✅ WINDOW_UPDATE |
| 强类型契约 | ❌ OpenAPI 文档 | ✅ .proto 文件 |

---

## 二、HTTP/2 帧结构深度解析

### 2.1 帧格式

```
┌──────────────────────────────────────────────────────────────────┐
│                          HTTP/2 Frame                           │
├─────────────┬───────────┬───────────┬───────────┬───────────────┤
│ Length (24) │ Type(8)   │ R(1)      │ Stream ID(31)│              │
│             │           │ Flags(7)  │           │               │
├─────────────┴───────────┴───────────┴───────────┴───────────────┤
│                         Frame Payload                           │
├─────────────────────────────────────────────────────────────────┤
│                              ...                                │
└─────────────────────────────────────────────────────────────────┘

Length:  0~16384 字节 (默认帧大小)
Type:    0x0=DATA, 0x1=HEADERS, 0x2=PRIORITY, 0x3=RST_STREAM,
         0x4=SETTINGS, 0x5=PUSH_PROMISE, 0x6=PING, 0x7=GOAWAY,
         0x8=WINDOW_UPDATE, 0x9=CONTINUATION
Flags:   各帧类型的标志位组合
Stream:  1~2^31-1 (0 = 连接级)
R:       Reserved bit (必须为 0)
```

### 2.2 帧交互流程

```
客户端                          服务器
  |── SETTINGS ────────────────►|  ← 连接初始化
  |◄── SETTINGS ───────────────|  ← 确认参数
  |── HEADERS (Stream 1) ────►|
  |   :method: POST            |
  |   :path: /bid.Service/Bid  |
  |   :authority: api.weread.com|
  |   content-type: application/grpc|
  |◄── HEADERS (Stream 1) ────|
  |   :status: 200             |
  |   grpc-status: 0           |
  |── DATA (Stream 1) ───────►|  ← 请求体
  |◄── DATA (Stream 1) ───────|  ← 响应体
  |── RST_STREAM (Stream 1) ─►|  ← 可选：快速关闭流
  |   error_code: NO_ERROR     |
```

---

## 三、gRPC 流类型深度解析

### 3.1 四种 RPC 模式

```go
// 1. Unary RPC (标准请求-响应)
// 客户端发送一个请求，服务端返回一个响应
type BidServiceClient interface {
    Bid(ctx context.Context, req *BidRequest) (*BidResponse, error)
}

// 2. Server Streaming RPC (服务端流式)
// 客户端发送一个请求，服务端返回多个响应
type CampaignServiceClient interface {
    ListCampaigns(ctx context.Context, req *CampaignFilter) (stream.CampaignStream, error)
}
// stream.CampaignStream:
//   Next() (*Campaign, error)  // 逐个接收

// 3. Client Streaming RPC (客户端流式)
// 客户端发送多个请求，服务端返回一个响应
type DataUploadServiceClient interface {
    UploadMetrics(ctx context.Context) (stream.MetricUploadStream, error)
}
// stream.MetricUploadStream:
//   Send(*Metric) error       // 逐个发送
//   CloseAndRecv() (*Summary, error)

// 4. Bidirectional Streaming RPC (双向流式)
// 双方都可以独立发送和接收
type RealTimeBidServiceClient interface {
    RealTimeBid(ctx context.Context) (stream.BidStream, error)
}
// stream.BidStream:
//   Send(*BidRequest) error   // 发送竞价请求
//   Recv() (*BidResponse, error)  // 接收竞价结果
```

### 3.2 流式场景：实时竞价

```go
// 实时竞价的双向流式实现
type RealTimeBidder struct {
    stream BidStream
    ctx    context.Context
    cancel context.CancelFunc
    
    // 并发安全
    mu      sync.Mutex
    pending map[uint64]*PendingBid
}

func (b *RealTimeBidder) Start() error {
    ctx, cancel := context.WithCancel(context.Background())
    b.ctx = ctx
    b.cancel = cancel
    b.pending = make(map[uint64]*PendingBid)
    
    // 打开双向流
    stream, err := b.client.RealTimeBid(ctx)
    if err != nil {
        return err
    }
    b.stream = stream
    
    // 启动接收协程
    go b.receiveLoop()
    
    // 启动发送协程
    go b.sendLoop()
    
    return nil
}

func (b *RealTimeBidder) receiveLoop() {
    for {
        resp, err := b.stream.Recv()
        if err == io.EOF {
            return
        }
        if err != nil {
            log.Printf("recv error: %v", err)
            return
        }
        
        b.mu.Lock()
        pending := b.pending[resp.RequestId]
        b.mu.Unlock()
        
        if pending != nil {
            select {
            case pending.Chan <- resp:
            default:
                // 消费者处理慢，丢弃响应
            }
        }
    }
}

func (b *RealTimeBidder) sendLoop() {
    ticker := time.NewTicker(1 * time.Millisecond) // ~1ms 间隔
    defer ticker.Stop()
    
    for {
        select {
        case <-b.ctx.Done():
            return
        case <-ticker.C:
            // 从消息队列获取竞价请求
            req := b.queue.Dequeue()
            if req == nil {
                continue
            }
            
            b.mu.Lock()
            req.ID = nextID()
            b.pending[req.ID] = &PendingBid{Chan: make(chan *BidResponse, 1)}
            b.mu.Unlock()
            
            if err := b.stream.Send(req); err != nil {
                log.Printf("send error: %v", err)
                return
            }
            
            // 等待响应（超时 5ms）
            select {
            case resp := <-b.pending[req.ID].Chan:
                b.handleResponse(resp)
            case <-time.After(5 * time.Millisecond):
                b.handleTimeout(req.ID)
            }
        }
    }
}
```

---

## 四、gRPC 流量控制与背压

### 4.1 HTTP/2 流控机制

```
┌─────────────────────────────────────────────────────┐
│              HTTP/2 Flow Control                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  连接级窗口 (Connection Window): 65535 bytes         │
│  流级窗口 (Stream Window): 65535 bytes              │
│                                                     │
│  发送方:                                            │
│    - 不能超过窗口大小发送数据                        │
│    - 收到 WINDOW_UPDATE 后增加窗口                   │
│                                                     │
│  接收方:                                            │
│    - 处理完数据后发送 WINDOW_UPDATE                  │
│    - 如果处理慢 → 窗口耗尽 → 发送方暂停              │
│                                                     │
│  效果: 自动背压 (Backpressure)                       │
└─────────────────────────────────────────────────────┘
```

### 4.2 gRPC 流控实现

```go
// gRPC 默认使用 HTTP/2 的流控机制
// 但可以在应用层添加额外的背压控制

type BackpressureController struct {
    maxQueueSize int           // 最大队列大小
    currentSize  atomic.Int64
    dropPolicy   DropPolicy    // 丢弃策略
}

func (c *BackpressureController) TryEnqueue(item interface{}) bool {
    size := c.currentSize.Add(1)
    if size > int64(c.maxQueueSize) {
        c.currentSize.Add(-1) // 回滚
        
        switch c.dropPolicy {
        case DropOldest:
            // 丢弃最旧的消息
            return c.replaceOldest(item)
        case DropNewest:
            // 丢弃新消息
            c.currentSize.Add(-1)
            return false
        case Block:
            // 阻塞直到有空位
            return c.blockAndWait(item)
        }
    }
    return true
}

// gRPC 服务端流控配置
func configureServer() *grpc.Server {
    return grpc.NewServer(
        // 最大并发流数
        grpc.MaxConcurrentStreams(1000),
        // 最大消息大小
        grpc.MaxRecvMsgSize(4*1024*1024),  // 4MB
        grpc.MaxSendMsgSize(4*1024*1024),  // 4MB
        // 心跳机制（检测死连接）
        grpc.KeepaliveParams(keepalive.ServerParameters{
            Time:                10 * time.Second,   // ping 间隔
            Timeout:             20 * time.Second,   // 超时时间
            PermitWithoutStream: true,               // 即使没有活跃流也允许 ping
        }),
        // 拦截器：添加背压检查
        grpc.UnaryInterceptor(backpressureUnaryInterceptor()),
        grpc.StreamInterceptor(backpressureStreamInterceptor()),
    )
}

func backpressureUnaryInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, 
        info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        // 检查背压状态
        if controller.IsOverloaded() {
            return nil, status.Error(codes.ResourceExhausted, "server overloaded")
        }
        
        return handler(ctx, req)
    }
}
```

---

## 五、gRPC 负载均衡

### 5.1 客户端负载均衡

```
gRPC 客户端负载均衡架构:

┌──────────────────────────────────────────────────────┐
│                    gRPC Client                       │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Resolver    │  │  Balancer   │  │  Picker      │  │
│  │ (DNS/LB)    │─►│ (RoundRobin)│─►│ (Pick Next)  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│        │                                    │        │
│        ▼                                    ▼        │
│  ┌─────────────────────────────────────────────┐    │
│  │              SubConn Pool                    │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │    │
│  │  │SC-1  │ │SC-2  │ │SC-3  │ │SC-4  │  ...  │    │
│  │  │srv-a │ │srv-b │ │srv-c │ │srv-d │       │    │
│  │  └──────┘ └──────┘ └──────┘ └──────┘       │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### 5.2 RoundRobin 负载均衡器

```go
// gRPC RoundRobin 负载均衡器核心逻辑
type RoundRobinBalancer struct {
    subConns []subConn       // 可用子连接列表
    currentIndex int          // 当前索引（简单轮询）
    resolver state.Resolver  // 服务发现
}

func (b *RoundPicker) Pick(info balancer.PickInfo) (balancer.PickResult, error) {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    // 获取可用的 subConn 列表
    readyConns := b.getReadySubConns()
    if len(readyConns) == 0 {
        return balancer.PickResult{}, balancer.ErrNoSubConnAvailable
    }
    
    // 简单轮询
    idx := b.currentIndex % len(readyConns)
    b.currentIndex++
    
    sc := readyConns[idx]
    
    return balancer.PickResult{
        SubConn: sc,
        Done: func(info balancer.DoneInfo) {
            if info.Err != nil {
                // 请求失败，标记 subConn 为不健康
                b.markUnhealthy(sc)
            }
        },
    }, nil
}

// 加权轮询（考虑服务器负载）
type WeightedRoundRobinBalancer struct {
    servers []WeightedServer
    weights []int  // 权重数组
}

type WeightedServer struct {
    address string
    weight  int    // 权重（基于 CPU/内存/延迟计算）
    current int    // 当前已分配请求数
}

func (b *WeightedRoundRobinBalancer) Pick() *WeightedServer {
    // NAL (Nearest Available Load) 算法
    totalWeight := 0
    for _, s := range b.servers {
        totalWeight += s.weight
    }
    
    // 选择 (weight - current_requests) 最大的服务器
    bestIdx := -1
    bestScore := math.MinInt64
    
    for i, s := range b.servers {
        score := int64(s.weight) - int64(s.current)
        if score > bestScore {
            bestScore = score
            bestIdx = i
        }
    }
    
    if bestIdx >= 0 {
        b.servers[bestIdx].current++
        return &b.servers[bestIdx]
    }
    
    return nil
}
```

---

## 六、gRPC 错误处理与重试

### 6.1 gRPC 状态码

```go
// 常用 gRPC 状态码
const (
    OK                  Status = 0   // 成功
    Canceled            Status = 1   // 取消
    Unknown             Status = 2   // 未知错误
    InvalidArgument     Status = 3   // 参数无效
    DeadlineExceeded    Status = 4   // 超时
    NotFound            Status = 5   // 未找到
    AlreadyExists       Status = 6   // 已存在
    PermissionDenied    Status = 7   // 权限不足
    ResourceExhausted   Status = 8   // 资源耗尽（背压）
    FailedPrecondition  Status = 9   // 前置条件失败
    Aborted             Status = 10  // 中止
    Unimplemented       Status = 12  // 未实现
    Internal            Status = 13  // 内部错误
    Unavailable         Status = 14  // 不可用（服务降级）
    DataLoss            Status = 15  // 数据丢失
    Unauthenticated     Status = 16  // 未认证
)
```

### 6.2 重试策略

```go
// gRPC 重试配置
type RetryConfig struct {
    MaxRetries        int           // 最大重试次数
    InitialBackoff    time.Duration // 初始退避时间
    MaxBackoff        time.Duration // 最大退避时间
    BackoffMultiplier float64       // 退避倍数
    RetryableCodes    []codes.Code  // 可重试的状态码
}

// 指数退避重试
func (c *RetryConfig) Backoff(attempt int) time.Duration {
    duration := c.InitialBackoff
    for i := 0; i < attempt; i++ {
        duration *= time.Duration(c.BackoffMultiplier)
    }
    // 添加抖动 (jitter) 避免 thundering herd
    jitter := time.Duration(rand.Int63n(int64(duration / 2)))
    duration += jitter
    
    if duration > c.MaxBackoff {
        duration = c.MaxBackoff
    }
    
    return duration
}

// gRPC 重试拦截器
func retryInterceptor(ctx context.Context, method string, 
    req, reply interface{}, cc *grpc.ClientConn, 
    invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
    
    config := getRetryConfig(method)  // 按方法配置
    var lastErr error
    
    for attempt := 0; attempt <= config.MaxRetries; attempt++ {
        if attempt > 0 {
            backoff := config.Backoff(attempt - 1)
            timer := time.NewTimer(backoff)
            select {
            case <-ctx.Done():
                timer.Stop()
                return ctx.Err()
            case <-timer.C:
            }
        }
        
        err := invoker(ctx, method, req, reply, cc, opts...)
        if err == nil {
            return nil
        }
        
        lastErr = err
        code := grpc.ErrCode(err)
        
        // 检查是否可重试
        if !config.isRetryable(code) {
            return err
        }
    }
    
    return lastErr
}
```

---

## 七、生产排障案例

### 7.1 案例：gRPC 连接泄漏

**现象**：服务重启后 gRPC 连接数持续增长，最终 OOM。

```bash
# 检查 gRPC 连接状态
$ netstat -an | grep :50051 | wc -l
# 正常: ~100, 异常: >10000

# 检查 TIME_WAIT 状态
$ netstat -an | grep TIME_WAIT | wc -l
# 如果大量 TIME_WAIT，说明连接未正确复用

# 检查 gRPC 连接池
$ curl localhost:55678/debug/requests  # pprof endpoint
```

**根因**：每次请求创建新的 gRPC 连接，而非复用连接池。

**解决**：
```go
// 错误的做法：每次请求创建新连接
func BadHandler(w http.ResponseWriter, r *http.Request) {
    conn, _ := grpc.Dial("server:50051", grpc.WithInsecure())
    client := pb.NewBidServiceClient(conn)
    client.Bid(r.Context(), req)
    conn.Close()  // 频繁创建/销毁连接
}

// 正确的做法：共享连接
var (
    bidClient pb.BidServiceClient
    once sync.Once
)

func GetBidClient() pb.BidServiceClient {
    once.Do(func() {
        conn, _ := grpc.Dial("server:50051",
            grpc.WithTransportCredentials(insecure.NewCredentials()),
            grpc.WithDefaultCallOptions(
                grpc.MaxCallRecvMsgSize(4*1024*1024),
                grpc.MaxCallSendMsgSize(4*1024*1024),
            ),
            grpc.WithKeepaliveParams(keepalive.ClientParameters{
                Time:                10 * time.Second,
                Timeout:             5 * time.Second,
                PermitWithoutStream: true,
            }),
        )
        bidClient = pb.NewBidServiceClient(conn)
    })
    return bidClient
}
```

### 7.2 案例：gRPC 超时传播

**现象**：API Gateway → BidService 链路中，Gateway 设置了 100ms 超时，但 BidService 实际处理了 500ms。

**根因**：gRPC 的 context deadline 没有被正确传播。

**解决**：
```go
// 确保 context 在 gRPC 调用中正确传播
func (s *Gateway) HandleBidRequest(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 检查父 context 是否有 deadline
    if deadline, ok := ctx.Deadline(); ok {
        // 给下游留 20% 余量
        remaining := time.Until(deadline)
        serviceDeadline := remaining * 0.8
        
        if serviceDeadline < 10*time.Millisecond {
            return nil, status.Error(codes.DeadlineExceeded, "insufficient time for downstream")
        }
        
        // 创建带 deadline 的子 context
        childCtx, cancel := context.WithTimeout(ctx, serviceDeadline)
        defer cancel()
        
        return s.bidClient.Bid(childCtx, req)
    }
    
    return s.bidClient.Bid(ctx, req)
}
```

---

## 八、Trade-off 分析

### 8.1 gRPC vs REST 选型

| 维度 | gRPC | REST | 建议 |
|------|------|------|------|
| 性能 | 高（二进制+HPACK） | 中（JSON+文本） | 内部服务用 gRPC |
| 调试 | 难（二进制） | 易（curl/wget） | 对外 API 用 REST |
| 跨语言 | 好（.proto 生成） | 好（OpenAPI 生成） | 都适合 |
| Web 兼容 | 差（浏览器不支持） | 好 | 前端用 REST/GraphQL |
| 缓存 | 难（HTTP/2 无缓存） | 好（HTTP 缓存） | 读多写少用 REST |
| CDN 友好 | 差 | 好 | 静态资源用 REST |

### 8.2 gRPC 最佳实践

```go
// 生产环境 gRPC 配置模板
func ProductionGRPCServer() *grpc.Server {
    return grpc.NewServer(
        grpc.MaxConcurrentStreams(1000),      // 限制并发流
        grpc.MaxRecvMsgSize(10*1024*1024),    // 10MB 接收上限
        grpc.MaxSendMsgSize(10*1024*1024),    // 10MB 发送上限
        grpc.KeepaliveParams(keepalive.ServerParameters{
            Time:    30 * time.Second,         // 30s 心跳
            Timeout: 20 * time.Second,         // 20s 超时
        }),
        grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
            MinTime:             15 * time.Second,  // 最小 ping 间隔
            PermitWithoutStream: true,
        }),
        // 限流拦截器
        grpc.UnaryInterceptor(unaryLoggingInterceptor(
            grpc_recovery.UnaryRecovery(),
            grpc_validator.UnaryValidator(),
            grpc_zap.UnaryLogger(logger),
            grpc_prometheus.UnaryServerInterceptor,
        )),
    )
}
```

---

## 九、自测题

### Q1：为什么 gRPC 不用 HTTP/1.1 而用 HTTP/2？

**答**：HTTP/1.1 是文本协议，每次请求需要独立的 TCP 连接（或 keep-alive 但串行）。gRPC 需要低延迟、高并发的 RPC 调用，HTTP/2 的二进制帧、多路复用、头部压缩、服务端推送等特性完美匹配。特别是多路复用——竞价引擎需要同时发起多个 Bid 请求，HTTP/1.1 的串行模型无法满足。

### Q2：gRPC 的流控如何防止服务端被压垮？

**答**：两层流控：
1. **HTTP/2 层**：WINDOW_UPDATE 机制，接收方处理完数据后才通知发送方可以继续发送
2. **gRPC 层**：MaxRecvMsgSize 限制单条消息大小，MaxConcurrentStreams 限制并发流数
配合背压拦截器，当队列满时直接返回 ResourceExhausted 错误。

### Q3：gRPC 如何实现连接的健康检查？

**答**：通过 Keepalive 机制：
- 客户端定期发送 Ping，服务端回复 Pong
- 如果在 Timeout 时间内没收到 Pong，连接被关闭
- `PermitWithoutStream: true` 确保即使没有活跃 RPC 也保持连接活跃
- 结合 health checking protocol v1，可以查询特定服务的健康状态

---

## 十、与知识库的对照

### 已有内容
- `network/tcp-congestion-control-deep.md` — TCP 是 gRPC 的基础
- `network/dns-architecture-deep.md` — DNS 解析是 gRPC 服务发现的第一步
- `network/http3-quic-deep.md` — gRPC 可以运行在 HTTP/3 上（gRPC-Web over QUIC）

### 补充内容
- 填补了 gRPC 传输层的系统性知识空白
- 涵盖 HTTP/2 帧、流控、负载均衡、重试等核心机制
- 生产排障案例直接关联广告系统的微服务架构

### 缺失内容（后续可扩展）
- gRPC 服务网格集成（Istio sidecar）
- gRPC-Web 浏览器兼容方案
- gRPC 监控与追踪（OpenTelemetry）
- Protobuf 序列化深度（wire format / varint / zigzag）
