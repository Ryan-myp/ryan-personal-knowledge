# 微服务架构设计深度实现 - 资深专家

## 一、服务拆分策略

### 1.1 边界定义

```go
// 服务边界定义
type ServiceBoundary struct {
    Name             string
    Domain           string
    BoundedContext   string
    APIs             []APISpec
    DataModel        DataModel
    Dependencies     []string
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
    nodes map[string]*ServiceNode
    edges map[string][]string
}

type ServiceNode struct {
    Name         string
    Version      string
    Dependencies []string
    HealthCheck  string
    MetricsPort  int
}

// 循环依赖检测
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

### 1.2 数据隔离

```go
// 数据库隔离策略
type DatabaseIsolation struct {
    ServiceName  string
    DatabaseName string
    Schema       string
    Tables       []string
    Connection   *sql.DB
}

// 多租户数据隔离
type TenantIsolation struct {
    Mode          string // shared, isolated, hybrid
    TenantID      string
    DatabaseName  string
    SchemaName    string
}

func (t *TenantIsolation) GetConnection() (*sql.DB, error) {
    switch t.Mode {
    case "isolated":
        // 独立数据库
        dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s sslmode=require",
            t.Host, t.User, t.Password, t.DatabaseName)
        return sql.Open("postgres", dsn)
        
    case "shared":
        // 共享数据库，tenant_id字段隔离
        dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s sslmode=require",
            t.Host, t.User, t.Password, t.DatabaseName)
        return sql.Open("postgres", dsn)
        
    case "hybrid":
        // 混合模式
        return t.getHybridConnection()
        
    default:
        return nil, fmt.Errorf("unknown isolation mode: %s", t.Mode)
    }
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
    ID           string
    ServiceName  string
    Host         string
    Port         int
    Metadata     map[string]string
    Healthy      bool
    RegisteredAt time.Time
}

// 健康检查
func (r *ServiceRegistry) HealthCheck(instance *ServiceInstance) error {
    resp, err := http.Get(fmt.Sprintf("http://%s:%d/health", instance.Host, instance.Port))
    if err != nil {
        instance.Healthy = false
        return err
    }
    defer resp.Body.Close()
    
    instance.Healthy = resp.StatusCode == http.StatusOK
    return nil
}

// 服务发现
func (r *ServiceRegistry) Discover(serviceName string) ([]*ServiceInstance, error) {
    instances, ok := r.services[serviceName]
    if !ok {
        return nil, fmt.Errorf("service not found: %s", serviceName)
    }
    
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

// 最少连接数
type LeastConnectionsLB struct {
    instances map[string]*InstanceStats
}

type InstanceStats struct {
    ActiveConnections int
    TotalRequests     int
}

func (lb *LeastConnectionsLB) Next() (*ServiceInstance, error) {
    minConn := math.MaxInt32
    var selected *ServiceInstance
    
    for name, stats := range lb.instances {
        if stats.ActiveConnections < minConn {
            minConn = stats.ActiveConnections
            selected = lb.instances[name].Instance
        }
    }
    
    return selected, nil
}
```

## 三、分布式事务

### 3.1 Saga模式

```go
// Saga事务
type Saga struct {
    ID           string
    Steps        []*SagaStep
    Status       SagaStatus
    Compensation []func() error
}

type SagaStep struct {
    Name       string
    Action     func() error
    Compensate func() error
}

type SagaStatus string

const (
    SagaPending    SagaStatus = "pending"
    SagaRunning    SagaStatus = "running"
    SagaCompleted  SagaStatus = "completed"
    SagaCompensating SagaStatus = "compensating"
    SagaFailed     SagaStatus = "failed"
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

### 3.2 TCC模式

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
    TCCPending   TCCStatus = "pending"
    TCCTrying    TCCStatus = "trying"
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

## 四、面试高频题

### Q1: 如何设计服务拆分？

```
A:
1. 按业务域拆分（DDD）
2. 高内聚低耦合
3. 独立部署独立演进
4. 数据隔离
5. 渐进式拆分
```

### Q2: 如何处理分布式事务？

```
A:
1. 两阶段提交(2PC) - 强一致性，性能差
2. Saga模式 - 最终一致，适合长事务
3. TCC模式 - 性能较好，实现复杂
4. 本地消息表 - 异步解耦
5. 可靠消息最终一致
```

### Q3: 服务发现如何实现？

```
A:
1. 客户端发现：服务列表在客户端缓存
2. 服务端发现：通过Load Balancer
3. 第三方注册中心：Consul/Etcd/ZK
4. K8s原生服务发现
```

## 五、自测题

1. 解释微服务拆分原则
2. 如何实现服务发现？
3. 分布式事务方案对比？

---

## 参考文档

- [微服务架构模式](https://microservices.io/patterns/)
- [Domain-Driven Design](https://domaindrivendesign.org/)
- [Distributed Systems Patterns](https://distributedsystemspatterns.com/)
