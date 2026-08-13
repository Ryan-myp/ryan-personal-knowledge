# 微服务架构模式深度解析

> 深入微服务核心模式：服务发现、API网关、Saga、Circuit Breaker、Sidecar。
> 适用对象：架构师、后端工程师

---

## 1. 核心架构模式

```
┌─────────────────────────────────────────────────────────────────┐
│                     微服务架构全景图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client                                                         │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────┐                                               │
│  │ API Gateway │ ← 路由、限流、认证、日志                       │
│  └──────┬──────┘                                               │
│         │                                                       │
│    ┌────┼────┬────┬────┬────┐                                  │
│    ▼    ▼    ▼    ▼    ▼    ▼                                  │
│  SvcA SvcB SvcC SvcD SvcE SvcF  ← 业务服务                     │
│    │    │    │    │    │    │                                  │
│    ▼    ▼    ▼    ▼    ▼    ▼                                  │
│  [DB] [Cache] [MQ] [Search] [Stream]  ← 数据存储层            │
│                                                                 │
│  支撑组件: Service Mesh (Istio/Linkerd)                         │
│           Config Center (Nacos/Apollo)                          │
│           Registry (Consul/Etcd)                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 服务发现与注册

### 2.1 注册中心对比

```go
// 服务发现接口
type ServiceRegistry interface {
    Register(service *ServiceInstance) error
    Deregister(service *ServiceInstance) error
    Discover(serviceName string) ([]*ServiceInstance, error)
    Watch(serviceName string, watcher ServiceWatcher)
}

// 健康检查
type HealthCheck interface {
    Check(instance *ServiceInstance) bool
    GetStatus(instance *ServiceInstance) HealthStatus
}
```

### 2.2 Consensus 算法

```
Raft 选举流程:
1. Follower → Candidate (超时)
2. Candidate → 请求投票
3. 获得多数派投票 → Leader
4. Leader → 复制日志 → 确认提交

Zab (ZooKeeper):
1. 广播提议
2. Prepare 阶段
3. Commit 阶段
4. 同步更新
```

---

## 3. 分布式事务

### 3.1 Saga 模式

```
订单服务 ──▶ 库存服务 ──▶ 支付服务 ──▶ 积分服务
  │             │             │             │
  ▼             ▼             ▼             ▼
补偿: 取消订单   恢复库存     退款         撤销积分

补偿事务:
- 幂等性保证
- 最终一致性
- 手动补偿 vs 自动补偿
```

### 3.2 TCC 模式

```
Try: 预留资源
Confirm: 确认提交
Cancel: 取消预留
```

---

## 4. 熔断与限流

### 4.1 Circuit Breaker

```go
type CircuitBreaker struct {
    state       CircuitState  // CLOSED, OPEN, HALF_OPEN
    threshold   int           // 失败阈值
    timeout     time.Duration // 恢复超时
    halfOpenMax int           // HALF_OPEN 最大请求数
}

// 状态转换
// CLOSED → OPEN: 失败率超过阈值
// OPEN → HALF_OPEN: 超时后
// HALF_OPEN → CLOSED: 成功请求达到阈值
// HALF_OPEN → OPEN: 请求失败
```

### 4.2 限流算法

```
令牌桶 (Token Bucket):
- 匀速产生令牌
- 请求消耗令牌
- 突发流量可借用

漏桶 (Leaky Bucket):
- 匀速流出
- 突发流量排队
- 平滑输出

滑动窗口 (Sliding Window):
- 时间片统计
- 动态调整
- 精确控制
```

---

## 5. Sidecar 模式

```
┌─────────────────────────────────────────────────────────────────┐
│                     Sidecar 架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Application Container                                  │   │
│  │  ┌─────────────┐    ┌─────────────┐                     │   │
│  │  │  App Main   │◄──►│  Sidecar    │                     │   │
│  │  │  Process    │    │  Proxy      │                     │   │
│  │  └─────────────┘    └─────────────┘                     │   │
│  │          │                  │                           │   │
│  │          ▼                  ▼                           │   │
│  │      [DB/Cache]       [Service Mesh]                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Sidecar 职责:                                                  │
│  ├── 服务发现与注册                                             │
│  ├── 负载均衡                                                   │
│  ├── 熔断限流                                                   │
│  ├── 链路追踪                                                   │
│  ├── 安全认证                                                   │
│  └── 流量管理                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. API 网关模式

```yaml
# 网关配置示例
apiVersion: gateway.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: rate-limit
spec:
  workloadSelector:
    labels:
      app: gateway
  configPatches:
    - applyTo: HTTP_FILTER
      match:
        context: SIDECAR_INBOUND
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.filters.http.local_ratelimit
          typed_config:
            "@type": type.googleapis.com/udpa.type.v1.TypedStruct
            type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
            value:
              stat_prefix: http_local_rate_limiter
              token_bucket:
                max_tokens: 1000
                tokens_per_fill: 1000
                fill_interval: 60s
```

---

## 7. 实践 Checklist

- [ ] 服务治理：注册中心、配置中心
- [ ] 通信：gRPC/REST、序列化、负载均衡
- [ ] 容错：熔断、降级、限流、重试
- [ ] 事务：Saga、TCC、本地消息表
- [ ] 可观测：日志、监控、链路追踪
- [ ] 部署：容器化、CI/CD、灰度发布

---

**参考**: Martin Fowler Microservices、Netflix ArchUnit、Istio 官方文档
