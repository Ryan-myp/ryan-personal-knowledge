# 高可用架构设计：容灾/降级/熔断/限流

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解高可用

```
医院的高可用设计：
1. 多院区部署 → 一个院区停电不影响其他院区
2. 备用发电机 → 主电源故障时自动切换
3. 降级服务 → 急诊优先，非紧急科室暂停
4. 限流 → 高峰期限制挂号数量，避免挤兑
```

### 高可用核心指标

```
SLA（服务等级协议）：
- 99%：每年 downtime 87.6 小时
- 99.9%：每年 downtime 8.76 小时
- 99.99%：每年 downtime 52.6 分钟
- 99.999%：每年 downtime 5.26 分钟

广告平台目标：99.99%
→ 每月最多 downtime 4.38 分钟
```

---

## 第二部分：容灾设计

### 2.1 容灾级别

```
Level 0：本地容错
  → 单点故障，无容灾

Level 1：本地高可用
  → 主备模式，本地故障切换

Level 2：同城双活
  → 同城两个 AZ，同时提供服务

Level 3：异地容灾
  → 异地数据中心，故障切换

Level 4：异地多活
  → 多个异地数据中心，同时提供服务
```

### 2.2 Go 实现容灾切换

```go
package failover

import (
    "context"
    "fmt"
    "sync"
    "time"
)

// DataCenter 数据中心
type DataCenter struct {
    ID         string
    Status     string // active/passive
    Latency    time.Duration
    LastHealth time.Time
}

// DisasterRecovery 容灾管理器
type DisasterRecovery struct {
    dataCenters []*DataCenter
    activeDC    *DataCenter
    mu          sync.RWMutex
    healthCheck *HealthChecker
}

// HealthChecker 健康检查器
type HealthChecker struct {
    interval    time.Duration
    timeout     time.Duration
    unhealthyCount int
}

// NewDisasterRecovery 创建容灾管理器
func NewDisasterRecovery(dcs []*DataCenter) *DisasterRecovery {
    dr := &DisasterRecovery{
        dataCenters: dcs,
        activeDC:    dcs[0],
        healthCheck: &HealthChecker{
            interval: 10 * time.Second,
            timeout:  5 * time.Second,
        },
    }
    
    // 启动健康检查
    go dr.startHealthCheck()
    
    return dr
}

// startHealthCheck 启动健康检查
func (dr *DisasterRecovery) startHealthCheck() {
    ticker := time.NewTicker(dr.healthCheck.interval)
    defer ticker.Stop()
    
    for range ticker.C {
        for _, dc := range dr.dataCenters {
            if dc.Status == "passive" {
                continue
            }
            
            healthy := dr.healthCheck.check(dc)
            if !healthy {
                dr.handleFailure(dc)
            }
        }
    }
}

// check 健康检查
func (hc *HealthChecker) check(dc *DataCenter) bool {
    // 模拟健康检查
    // 实际实现：发送 HTTP 请求或 TCP 连接
    start := time.Now()
    // ... 健康检查逻辑 ...
    latency := time.Since(start)
    
    if latency > hc.timeout {
        return false
    }
    
    dc.Latency = latency
    dc.LastHealth = time.Now()
    return true
}

// handleFailure 处理故障
func (dr *DisasterRecovery) handleFailure(failedDC *DataCenter) {
    dr.mu.Lock()
    defer dr.mu.Unlock()
    
    // 标记为 passive
    failedDC.Status = "passive"
    
    // 切换到备用 DC
    for _, dc := range dr.dataCenters {
        if dc != failedDC && dc.Status != "passive" {
            dr.activeDC = dc
            break
        }
    }
    
    fmt.Printf("Failover triggered. Active DC changed from %s to %s\n",
        failedDC.ID, dr.activeDC.ID)
}

// GetActiveDC 获取当前活跃 DC
func (dr *DisasterRecovery) GetActiveDC() *DataCenter {
    dr.mu.RLock()
    defer dr.mu.RUnlock()
    return dr.activeDC
}
```

---

## 第三部分：熔断器设计

### 3.1 熔断器原理

```
熔断器（Circuit Breaker）的状态机：

Closed（闭合）→ 正常运行
   ↓ 失败次数超过阈值
Open（断开）→ 拒绝请求
   ↓ 等待一段时间后
Half-Open（半开）→ 试探性允许请求
   ↓ 成功
Closed（闭合）→ 恢复正常
   ↓ 失败
Open（断开）→ 继续拒绝
```

### 3.2 Go 实现熔断器

```go
package circuitbreaker

import (
    "sync"
    "time"
)

type State int

const (
    StateClosed State = iota
    StateOpen
    StateHalfOpen
)

// CircuitBreaker 熔断器
type CircuitBreaker struct {
    mu              sync.Mutex
    state           State
    failureCount    int
    successCount    int
    lastFailTime    time.Time
    timeout         time.Duration  // Open → Half-Open 的等待时间
    failureThreshold int          // 失败阈值
    halfOpenMax     int           // Half-Open 允许的最大请求数
    halfOpenSuccess int           // Half-Open 成功次数
}

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(timeout time.Duration, failureThreshold, halfOpenMax int) *CircuitBreaker {
    return &CircuitBreaker{
        state:            StateClosed,
        timeout:          timeout,
        failureThreshold: failureThreshold,
        halfOpenMax:      halfOpenMax,
    }
}

// AllowRequest 判断是否允许请求
func (cb *CircuitBreaker) AllowRequest() bool {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateClosed:
        return true
    case StateOpen:
        // 检查是否过了超时时间
        if time.Since(cb.lastFailTime) > cb.timeout {
            cb.state = StateHalfOpen
            cb.successCount = 0
            return true
        }
        return false
    case StateHalfOpen:
        return cb.successCount < cb.halfOpenMax
    }
    return false
}

// RecordSuccess 记录成功
func (cb *CircuitBreaker) RecordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateClosed:
        cb.failureCount = 0
    case StateHalfOpen:
        cb.successCount++
        if cb.successCount >= cb.halfOpenMax {
            cb.state = StateClosed
            cb.failureCount = 0
        }
    }
}

// RecordFailure 记录失败
func (cb *CircuitBreaker) RecordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.failureCount++
    cb.lastFailTime = time.Now()
    
    if cb.state == StateHalfOpen {
        // Half-Open 时失败，回到 Open
        cb.state = StateOpen
    } else if cb.failureCount >= cb.failureThreshold {
        cb.state = StateOpen
    }
}

// 使用示例
type Service struct {
    cb *CircuitBreaker
}

func (s *Service) Call() error {
    if !s.cb.AllowRequest() {
        return fmt.Errorf("circuit breaker is open")
    }
    
    err := s.doCall()
    if err != nil {
        s.cb.RecordFailure()
        return err
    }
    
    s.cb.RecordSuccess()
    return nil
}
```

---

## 第四部分：限流设计

### 4.1 限流算法

```
1. 固定窗口：固定时间段内限制请求数
   → 简单但存在临界问题

2. 滑动窗口：窗口随时间滑动
   → 更平滑，但计算复杂

3. 令牌桶：以固定速率产生令牌
   → 允许突发流量

4. 漏桶：以固定速率处理请求
   → 平滑流量，不允许突发
```

### 4.2 Go 实现限流器

```go
package ratelimit

import (
    "sync"
    "time"
)

// TokenBucket 令牌桶限流器
type TokenBucket struct {
    tokens     chan struct{}
    refillRate int       // 每秒产生的令牌数
    maxTokens  int       // 最大令牌数
    mu         sync.Mutex
}

// NewTokenBucket 创建令牌桶
func NewTokenBucket(rate, burst int) *TokenBucket {
    tb := &TokenBucket{
        tokens:     make(chan struct{}, burst),
        refillRate: rate,
        maxTokens:  burst,
    }
    
    // 初始令牌
    for i := 0; i < burst; i++ {
        tb.tokens <- struct{}{}
    }
    
    // 定期补充令牌
    go tb.refill()
    
    return tb
}

// refill 补充令牌
func (tb *TokenBucket) refill() {
    ticker := time.NewTicker(time.Second / time.Duration(tb.refillRate))
    defer ticker.Stop()
    
    for range ticker.C {
        select {
        case tb.tokens <- struct{}{}:
        default:
            // 令牌已满，丢弃
        }
    }
}

// Wait 等待令牌
func (tb *TokenBucket) Wait(ctx context.Context) error {
    select {
    case <-tb.tokens:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}

// TryWait 尝试获取令牌（不阻塞）
func (tb *TokenBucket) TryWait() bool {
    select {
    case <-tb.tokens:
        return true
    default:
        return false
    }
}

// LeakyBucket 漏桶限流器
type LeakyBucket struct {
    mu       sync.Mutex
    queue    []time.Time
    rate     time.Duration // 处理速率
}

func (lb *LeakyBucket) Allow() bool {
    lb.mu.Lock()
    defer lb.mu.Unlock()
    
    now := time.Now()
    
    // 清理过期的请求
    cutoff := now.Add(-lb.rate)
    i := 0
    for i < len(lb.queue) && lb.queue[i].Before(cutoff) {
        i++
    }
    lb.queue = lb.queue[i:]
    
    // 如果队列满，拒绝
    if len(lb.queue) >= 100 { // 队列大小限制
        return false
    }
    
    // 添加请求
    lb.queue = append(lb.queue, now)
    return true
}
```

---

## 第五部分：降级设计

### 5.1 降级策略

```
1. 功能降级
   → 非核心功能关闭
   → 例如：关闭推荐功能

2. 数据降级
   → 使用缓存数据代替实时数据
   → 例如：使用缓存的用户画像

3. 流程降级
   → 跳过非必要步骤
   → 例如：跳过频次控制检查

4. 服务降级
   → 调用降级服务
   → 例如：调用备用广告源
```

### 5.2 Go 实现降级

```go
package degradation

import (
    "context"
    "sync"
)

// DegradationManager 降级管理器
type DegradationManager struct {
    features map[string]*Feature
    mu       sync.RWMutex
}

type Feature struct {
    Name       string
    Enabled    bool
    Degraded   bool
    LastChange time.Time
}

// NewDegradationManager 创建降级管理器
func NewDegradationManager() *DegradationManager {
    return &DegradationManager{
        features: make(map[string]*Feature),
    }
}

// EnableFeature 启用功能
func (dm *DegradationManager) EnableFeature(name string) {
    dm.mu.Lock()
    defer dm.mu.Unlock()
    
    if feature, ok := dm.features[name]; ok {
        feature.Enabled = true
        feature.Degraded = false
        feature.LastChange = time.Now()
    }
}

// DisableFeature 禁用功能
func (dm *DegradationManager) DisableFeature(name string) {
    dm.mu.Lock()
    defer dm.mu.Unlock()
    
    if feature, ok := dm.features[name]; ok {
        feature.Enabled = false
        feature.Degraded = false
        feature.LastChange = time.Now()
    }
}

// EnableDegradation 启用降级
func (dm *DegradationManager) EnableDegradation(name string) {
    dm.mu.Lock()
    defer dm.mu.Unlock()
    
    if feature, ok := dm.features[name]; ok {
        feature.Degraded = true
        feature.LastChange = time.Now()
    }
}

// IsFeatureAvailable 检查功能是否可用
func (dm *DegradationManager) IsFeatureAvailable(name string) bool {
    dm.mu.RLock()
    defer dm.mu.RUnlock()
    
    if feature, ok := dm.features[name]; ok {
        return feature.Enabled && !feature.Degraded
    }
    return false
}

// 使用示例
type Service struct {
    dm *DegradationManager
}

func (s *Service) GetRecommendations(ctx context.Context, userID string) ([]string, error) {
    // 检查推荐功能是否可用
    if !s.dm.IsFeatureAvailable("recommendations") {
        // 降级：返回默认推荐
        return s.getDefaultRecommendations(userID)
    }
    
    // 正常调用
    return s.getRecommendations(ctx, userID)
}
```

---

## 第六部分：生产排障案例

### 6.1 雪崩效应

```
现象：一个服务故障导致整个系统崩溃

排查：
1. 监控大盘 → 发现多个服务同时超时
2. 链路追踪 → 发现依赖链过长
3. 日志 → 发现级联故障

根因：缺少熔断和限流

解决方案：
1. 添加熔断器
2. 添加限流器
3. 添加降级策略
4. 缩短超时时间
```

### 6.2 熔断器误触发

```
现象：熔断器频繁触发，影响正常请求

排查：
1. 检查失败原因
2. 检查阈值设置
3. 检查网络延迟

根因：网络抖动导致短暂超时

解决方案：
1. 提高失败阈值
2. 增加 Half-Open 试探次数
3. 添加重试机制
4. 优化超时时间
```

---

## 第七部分：自测题

### 问题 1
熔断器的三种状态如何转换？

<details>
<summary>查看答案</summary>

1. **Closed**：正常状态，允许请求
2. **Open**：故障过多，拒绝请求
3. **Half-Open**：试探性允许少量请求
4. **转换**：Closed → Open（失败超阈值），Open → Half-Open（超时后），Half-Open → Closed（成功）
5. **Go 实现**：CircuitBreaker 结构体

</details>

### 问题 2
令牌桶和漏桶有什么区别？

<details>
<summary>查看答案</summary>

1. **令牌桶**：允许突发流量
2. **漏桶**：不允许突发流量
3. **令牌桶**：适合有波动的流量
4. **漏桶**：适合均匀处理的场景
5. **Go 实现**：TokenBucket/LeakyBucket

</details>

### 问题 3
降级的策略有哪些？

<details>
<summary>查看答案</summary>

1. **功能降级**：关闭非核心功能
2. **数据降级**：使用缓存数据
3. **流程降级**：跳过非必要步骤
4. **服务降级**：调用降级服务
5. **Go 实现**：DegradationManager

</details>

---

*本文档基于高可用架构原理整理。*