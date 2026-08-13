# 微服务架构设计深度实现 - 资深专家

## 一、架构模式

### 1.1 服务拆分策略

```go
// 服务边界定义
type ServiceBoundary struct {
    Name        string
    Domain      string
    BoundedContext string
    APIs        []APISpec
    DataModel   DataModel
}

type APISpec struct {
    Path        string
    Method      string
    Request     Schema
    Response    Schema
    Auth        AuthType
    RateLimit   int
}

type AuthType string

const (
    JWTAuth      AuthType = "jwt"
    OAuth2Auth   AuthType = "oauth2"
    APIKeyAuth   AuthType = "api_key"
    NoAuth       AuthType = "none"
)

// 服务依赖图
type ServiceDependencyGraph struct {
    nodes    map[string]*ServiceNode
    edges    map[string][]string
}

type ServiceNode struct {
    Name           string
    Version        string
    Dependencies   []string
    HealthCheck    string
    MetricsPort    int
}

// 构建依赖图
func (g *ServiceDependencyGraph) AddService(name string, deps []string) {
    g.nodes[name] = &ServiceNode{
        Name:         name,
        Dependencies: deps,
    }
    g.edges[name] = deps
}

// 检测循环依赖
func (g *ServiceDependencyGraph) DetectCycles() [][]string {
    var cycles [][]string
    visited := make(map[string]bool)
    recStack := make(map[string]bool)
    
    for node := range g.nodes {
        if !visited[node] {
            cycle := g.dfs(node, visited, recStack, []string{})
            if len(cycle) > 0 {
                cycles = append(cycles, cycle)
            }
        }
    }
    
    return cycles
}

func (g *ServiceDependencyGraph) dfs(node string, visited, recStack map[string]bool, path []string) []string {
    visited[node] = true
    recStack[node] = true
    path = append(path, node)
    
    for _, dep := range g.edges[node] {
        if !visited[dep] {
            cycle := g.dfs(dep, visited, recStack, path)
            if len(cycle) > 0 {
                return cycle
            }
        } else if recStack[dep] {
            // 找到循环
            cycle := []string{dep}
            for _, p := range path {
                cycle = append(cycle, p)
                if p == dep {
                    break
                }
            }
            return cycle
        }
    }
    
    recStack[node] = false
    return nil
}
```

### 1.2 数据一致性

```go
// Saga模式实现
type Saga struct {
    ID          string
    Steps       []*SagaStep
    Status      SagaStatus
    Compensation []func() error
}

type SagaStep struct {
    Name       string
    Action     func() error
    Compensate func() error
}

type SagaStatus string

const (
    SagaPending   SagaStatus = "pending"
    SagaRunning   SagaStatus = "running"
    SagaCompleted SagaStatus = "completed"
    SagaCompensating SagaStatus = "compensating"
    SagaFailed    SagaStatus = "failed"
)

// 执行Saga
func (s *Saga) Execute() error {
    s.Status = SagaRunning
    executedSteps := []*SagaStep{}
    
    for _, step := range s.Steps {
        if err := step.Action(); err != nil {
            // 补偿已执行的步骤
            s.Status = SagaCompensating
            for i := len(executedSteps) - 1; i >= 0; i-- {
                if err := executedSteps[i].Compensate(); err != nil {
                    log.Errorf("compensation failed: %v", err)
                }
            }
            s.Status = SagaFailed
            return err
        }
        executedSteps = append(executedSteps, step)
    }
    
    s.Status = SagaCompleted
    return nil
}
```

## 二、服务治理

### 2.1 服务发现

```go
// 服务注册中心
type ServiceRegistry struct {
    services map[string][]*ServiceInstance
    ttl      time.Duration
    renewer  *Renewer
}

type ServiceInstance struct {
    ID          string
    ServiceName string
    Host        string
    Port        int
    Metadata    map[string]string
    Healthy     bool
    RegisteredAt time.Time
}

// 注册服务
func (r *ServiceRegistry) Register(instance *ServiceInstance) error {
    key := instance.ServiceName
    if r.services[key] == nil {
        r.services[key] = [] *ServiceInstance{}
    }
    
    // 检查是否已存在
    for _, existing := range r.services[key] {
        if existing.ID == instance.ID {
            existing.Host = instance.Host
            existing.Port = instance.Port
            existing.Metadata = instance.Metadata
            existing.RegisteredAt = time.Now()
            return nil
        }
    }
    
    r.services[key] = append(r.services[key], instance)
    return nil
}

// 发现服务
func (r *ServiceRegistry) Discover(serviceName string) ([]*ServiceInstance, error) {
    instances, ok := r.services[serviceName]
    if !ok {
        return nil, fmt.Errorf("service not found: %s", serviceName)
    }
    
    // 过滤健康实例
    var healthy []*ServiceInstance
    for _, instance := range instances {
        if instance.Healthy && time.Since(instance.RegisteredAt) < r.ttl {
            healthy = append(healthy, instance)
        }
    }
    
    return healthy, nil
}
```

### 2.2 负载均衡

```go
// 负载均衡器
type LoadBalancer interface {
    Next(serviceName string) (*ServiceInstance, error)
}

// 轮询负载均衡
type RoundRobinLB struct {
    counter int64
}

func (lb *RoundRobinLB) Next(serviceName string) (*ServiceInstance, error) {
    instances, err := registry.Discover(serviceName)
    if err != nil {
        return nil, err
    }
    
    if len(instances) == 0 {
        return nil, fmt.Errorf("no instances available")
    }
    
    idx := atomic.AddInt64(&lb.counter, 1) % int64(len(instances))
    return instances[idx], nil
}

// 加权轮询
type WeightedRoundRobinLB struct {
    instances []*ServiceInstance
    weights   []int
    current   int64
}

func (lb *WeightedRoundRobinLB) Next() (*ServiceInstance, error) {
    totalWeight := 0
    for _, w := range lb.weights {
        totalWeight += w
    }
    
    current := atomic.AddInt64(&lb.current, 1) % int64(totalWeight)
    
    cumulative := 0
    for i, weight := range lb.weights {
        cumulative += weight
        if current < int64(cumulative) {
            return lb.instances[i], nil
        }
    }
    
    return lb.instances[0], nil
}
```

## 三、分布式事务

### 3.1 TCC模式

```go
// TCC事务
type TCCTransaction struct {
    ID         string
    Try        func() error
    Confirm    func() error
    Cancel     func() error
    Status     TCCStatus
}

type TCCStatus string

const (
    TCCPending  TCCStatus = "pending"
    TCCTrying   TCCStatus = "trying"
    TCCConfirmed TCCStatus = "confirmed"
    TCCCancelled TCCStatus = "cancelled"
)

// 执行TCC
func (t *TCCTransaction) Execute() error {
    t.Status = TCCTrying
    
    // Try阶段
    if err := t.Try(); err != nil {
        t.Status = TCCCancelled
        return err
    }
    
    // Confirm阶段
    if err := t.Confirm(); err != nil {
        // 取消Try
        t.Cancel()
        t.Status = TCCCancelled
        return err
    }
    
    t.Status = TCCConfirmed
    return nil
}
```

### 3.2 本地消息表

```go
// 本地消息表
type LocalMessageTable struct {
    db *sql.DB
}

// 发送消息
func (m *LocalMessageTable) Send(msg *Message) error {
    tx, err := m.db.Begin()
    if err != nil {
        return err
    }
    
    // 1. 执行业务操作
    _, err = tx.Exec("UPDATE accounts SET balance = balance - ? WHERE id = ?", msg.Amount, msg.From)
    if err != nil {
        tx.Rollback()
        return err
    }
    
    // 2. 记录消息
    _, err = tx.Exec(`
        INSERT INTO local_messages (id, topic, payload, status, created_at)
        VALUES (?, ?, ?, 'pending', NOW())
    `, msg.ID, msg.Topic, msg.Payload)
    if err != nil {
        tx.Rollback()
        return err
    }
    
    return tx.Commit()
}

// 消息生产者
func (m *LocalMessageTable) ProduceMessage(topic string, payload interface{}) error {
    msg := &Message{
        ID:      uuid.New().String(),
        Topic:   topic,
        Payload: payload,
    }
    
    return m.Send(msg)
}
```

## 四、面试高频题

### Q1: 如何设计服务拆分？

```
A:
1. 按业务域拆分
2. 高内聚低耦合
3. 独立部署独立演进
4. 数据隔离
```

### Q2: 如何处理分布式事务？

```
A:
1. 两阶段提交(2PC)
2. Saga模式
3. TCC模式
4. 本地消息表
5. 可靠消息最终一致
```

## 五、自测题

1. 解释服务拆分原则
2. 如何实现服务发现？
3. 分布式事务方案对比？

---

## 参考文档

- [API网关深度](./api-gateway-deep.md)
- [gRPC优化](./grpc-optimization-deep.md)
- [K8s网络深入](../devops/k8s-network-plugin-deep.md)
