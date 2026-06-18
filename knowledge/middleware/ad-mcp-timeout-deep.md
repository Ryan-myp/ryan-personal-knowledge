# MCP 超时策略深度：超时配置/重试/熔断/优雅降级

> 从 HTTP 超时到熔断降级，逐层解析 MCP 调用的可靠性保障

---

## 第一部分：超时配置

### 超时层级

```
MCP 超时层级：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Context 超时（最高层）                                             │
│    - 用户请求的总超时                                                │
│    - 默认：30s                                                       │
│                                                                     │
│ 2. HTTP Client 超时（中间层）                                        │
│    - HTTPMCPToolCaller 的 Client.Timeout                             │
│    - 默认：30s                                                       │
│    - 高风险操作：60s                                                 │
│                                                                     │
│ 3. 路由超时（路由层）                                                │
│    - MCPToolRoute.Timeout                                          │
│    - 不同工具不同超时                                                │
│                                                                     │
│ 4. 连接超时（最底层）                                                │
│    - Dial Timeout: 连接建立超时                                      │
│    - TLS Handshake Timeout: TLS 握手超时                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 超时配置实现

```go
package mcp

import (
    "context"
    "net/http"
    "time"
)

// TimeoutConfig 超时配置
type TimeoutConfig struct {
    // 连接超时
    DialTimeout time.Duration
    
    // TLS 握手超时
    TLSHandshakeTimeout time.Duration
    
    // 请求超时（整个 HTTP 请求）
    RequestTimeout time.Duration
    
    // 响应头超时
    ResponseHeaderTimeout time.Duration
}

// DefaultTimeouts 默认超时配置
var DefaultTimeouts = TimeoutConfig{
    DialTimeout:           5 * time.Second,
    TLSHandshakeTimeout:   10 * time.Second,
    RequestTimeout:        30 * time.Second,
    ResponseHeaderTimeout: 30 * time.Second,
}

// HighRiskTimeouts 高风险操作超时配置
var HighRiskTimeouts = TimeoutConfig{
    DialTimeout:           5 * time.Second,
    TLSHandshakeTimeout:   10 * time.Second,
    RequestTimeout:        60 * time.Second,  // 高风险操作给更多时间
    ResponseHeaderTimeout: 60 * time.Second,
}

// NewHTTPMCPToolCallerWithTimeouts 创建带超时配置的 HTTP 调用器
func NewHTTPMCPToolCallerWithTimeouts(baseURL string, timeouts TimeoutConfig) *HTTPMCPToolCaller {
    client := &http.Client{
        Timeout:               timeouts.RequestTimeout,
        DialContext:           (&net.Dialer{Timeout: timeouts.DialTimeout}).DialContext,
        TLSHandshakeTimeout:   timeouts.TLSHandshakeTimeout,
        ResponseHeaderTimeout: timeouts.ResponseHeaderTimeout,
    }
    
    return &HTTPMCPToolCaller{
        BaseURL: baseURL,
        Client:  client,
    }
}
```

### 超时传播

```go
// 超时传播链：
// Context 超时 → HTTP Client 超时 → 路由超时 → 连接超时

// 1. Context 超时优先
func (c *HTTPMCPToolCaller) CallTool(ctx context.Context, req MCPToolRequest) (*MCPToolResult, error) {
    // 1. 检查 context 是否已超时
    select {
    case <-ctx.Done():
        return nil, fmt.Errorf("context deadline exceeded: %w", ctx.Err())
    default:
    }
    
    // 2. 创建带超时的 context
    timeout := c.timeout
    if deadline, ok := ctx.Deadline(); ok {
        // 取 context 超时和配置超时的较小值
        remaining := time.Until(deadline)
        if remaining < timeout {
            timeout = remaining
        }
    }
    
    // 3. 创建带超时的 request
    reqCtx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()
    
    // 4. 发起请求
    return c.doRequest(reqCtx, req)
}
```

---

## 第二部分：重试策略

### 重试策略

```
重试策略：
┌─────────────────────────────────────────────────────────────────────┐
│ 可重试的错误：                                                       │
│ • 网络超时                                                           │
│ • 5xx 服务器错误                                                     │
│ • 503 Service Unavailable                                           │
│ • 连接被拒绝                                                         │
│                                                                     │
│ 不可重试的错误：                                                     │
│ • 4xx 客户端错误（参数错误、权限不足等）                              │
│ • 400 Bad Request                                                    │
│ • 401 Unauthorized                                                   │
│ • 403 Forbidden                                                      │
│ • 404 Not Found                                                      │
│ • 429 Too Many Requests（由速率限制器处理）                          │
│ • 业务逻辑错误（参数校验失败等）                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 重试实现

```go
package mcp

import (
    "context"
    "fmt"
    "math/rand"
    "net/http"
    "time"
)

// RetryConfig 重试配置
type RetryConfig struct {
    MaxAttempts    int           // 最大重试次数
    InitialDelay   time.Duration // 初始延迟
    MaxDelay       time.Duration // 最大延迟
    BackoffFactor  float64       // 退避因子
    RetryableCodes []int         // 可重试的 HTTP 状态码
}

// DefaultRetryConfig 默认重试配置
var DefaultRetryConfig = RetryConfig{
    MaxAttempts:    3,
    InitialDelay:   500 * time.Millisecond,
    MaxDelay:       5 * time.Second,
    BackoffFactor:  2.0,
    RetryableCodes: []int{
        http.StatusTooManyRequests,  // 429
        http.StatusInternalServerError, // 500
        http.StatusBadGateway,       // 502
        http.StatusServiceUnavailable, // 503
        http.StatusGatewayTimeout,   // 504
    },
}

// RetryableCall 可重试的调用
func RetryableCall(ctx context.Context, config RetryConfig, call func() (*MCPToolResult, error)) (*MCPToolResult, error) {
    var lastErr error
    delay := config.InitialDelay
    
    for attempt := 1; attempt <= config.MaxAttempts; attempt++ {
        result, err := call()
        if err == nil {
            return result, nil
        }
        
        lastErr = err
        
        // 检查是否可重试
        if !isRetryableError(err) {
            return nil, err
        }
        
        // 最后一次尝试，不等待
        if attempt == config.MaxAttempts {
            break
        }
        
        // 指数退避 + 抖动
        jitter := time.Duration(rand.Int63n(int64(delay) / 2))
        waitTime := delay + jitter
        time.Sleep(waitTime)
        
        // 增加延迟
        delay = time.Duration(float64(delay) * config.BackoffFactor)
        if delay > config.MaxDelay {
            delay = config.MaxDelay
        }
    }
    
    return nil, fmt.Errorf("all %d attempts failed: %w", config.MaxAttempts, lastErr)
}

func isRetryableError(err error) bool {
    // 网络超时
    if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
        return true
    }
    
    // 连接错误
    if strings.Contains(err.Error(), "connection refused") {
        return true
    }
    
    // HTTP 状态码检查
    if httpErr, ok := err.(*HTTPError); ok {
        for _, code := range DefaultRetryConfig.RetryableCodes {
            if httpErr.StatusCode == code {
                return true
            }
        }
    }
    
    return false
}
```

---

## 第三部分：熔断降级

### 熔断器配置

```go
package mcp

import (
    "context"
    "sync"
    "time"
)

// MCPBreaker MCP 熔断器
type MCPBreaker struct {
    name           string
    state          BreakerState
    failureCount   int
    successCount   int
    windowSize     time.Duration
    failureThreshold int
    successThreshold  int
    resetTimeout     time.Duration
    lastFailure      time.Time
    lastSuccess      time.Time
    mu             sync.RWMutex
}

type BreakerState int

const (
    StateClosed BreakerState = iota
    StateOpen
    StateHalfOpen
)

// NewMCPBreaker 创建 MCP 熔断器
func NewMCPBreaker(name string) *MCPBreaker {
    return &MCPBreaker{
        name:             name,
        state:            StateClosed,
        windowSize:       60 * time.Second,
        failureThreshold: 5,
        successThreshold: 3,
        resetTimeout:     30 * time.Second,
    }
}

// Allow 是否允许请求
func (b *MCPBreaker) Allow(ctx context.Context) bool {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    switch b.state {
    case StateClosed:
        return true
    case StateOpen:
        if time.Since(b.lastFailure) > b.resetTimeout {
            b.state = StateHalfOpen
            b.successCount = 0
            return true
        }
        return false
    case StateHalfOpen:
        return true
    }
    return false
}

// RecordSuccess 记录成功
func (b *MCPBreaker) RecordSuccess() {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    b.lastSuccess = time.Now()
    b.successCount++
    
    if b.state == StateHalfOpen && b.successCount >= b.successThreshold {
        b.state = StateClosed
        b.failureCount = 0
    }
}

// RecordFailure 记录失败
func (b *MCPBreaker) RecordFailure() {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    b.lastFailure = time.Now()
    b.failureCount++
    
    if b.state == StateClosed && b.failureCount >= b.failureThreshold {
        b.state = StateOpen
    }
}

// GetState 获取状态
func (b *MCPBreaker) GetState() BreakerState {
    b.mu.RLock()
    defer b.mu.RUnlock()
    return b.state
}
```

### 熔断降级策略

```
熔断降级策略：
┌─────────────────────────────────────────────────────────────────────┐
│ Closed（正常）                                                       │
│    → 请求正常执行                                                    │
│    → 失败 → failureCount++                                           │
│    → failureCount >= threshold → Open                                │
│                                                                     │
│ Open（熔断）                                                         │
│    → 请求被拒绝，直接返回降级结果                                     │
│    → 等待 resetTimeout 后 → HalfOpen                                 │
│                                                                     │
│ HalfOpen（试探）                                                     │
│    → 允许少量请求通过                                                │
│    → 成功 → successCount++                                           │
│    → successCount >= threshold → Closed                              │
│    → 失败 → Open                                                     │
│                                                                     │
│ 降级结果：                                                           │
│ • 缓存的旧数据                                                       │
│ • 默认值                                                             │
│ • 友好的错误提示                                                     │
│ • 空列表/空结果                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：优雅降级

### 降级策略

```
MCP 调用降级策略：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 缓存降级                                                          │
│    - 从 Redis 读取缓存数据                                           │
│    - TTL 过期后返回 stale 数据                                       │
│    - 后台异步刷新缓存                                                │
│                                                                     │
│ 2. 默认值降级                                                        │
│    - 返回合理的默认值                                                │
│    - 空列表/空对象                                                   │
│    - 友好的错误提示                                                  │
│                                                                     │
│ 3. 降级到备用服务器                                                  │
│    - 主服务器超时 → 切换到备用服务器                                 │
│    - 备用服务器也超时 → 返回缓存数据                                 │
│                                                                     │
│ 4. 降级到本地查询                                                    │
│    - MCP 不可用 → 查本地数据库                                       │
│    - 数据可能不是最新的                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 降级实现

```go
package mcp

import (
    "context"
    "time"
)

// FallbackHandler 降级处理器
type FallbackHandler struct {
    cache       Cache
    defaultData map[string]interface{}
}

// CallWithFallback 带降级的调用
func (h *FallbackHandler) CallWithFallback(
    ctx context.Context,
    toolName string,
    args map[string]interface{},
    primaryCall func(context.Context, string, map[string]interface{}) (*MCPToolResult, error),
) (*MCPToolResult, error) {
    // 1. 尝试主调用
    result, err := primaryCall(ctx, toolName, args)
    if err == nil {
        // 成功：写入缓存
        h.cache.Set(toolName, result, 5*time.Minute)
        return result, nil
    }
    
    // 2. 主调用失败：尝试缓存
    cached, ok := h.cache.Get(toolName)
    if ok {
        return cached, nil
    }
    
    // 3. 缓存也没有：返回默认值
    if defaultData, ok := h.defaultData[toolName]; ok {
        return &MCPToolResult{
            Data: defaultData,
        }, nil
    }
    
    // 4. 没有默认值：返回错误
    return nil, err
}
```

---

## 第五部分：自测题

### Q1: 超时配置的层级？

**A**: Context 超时 → HTTP Client 超时 → 路由超时 → 连接超时。取最小值。

### Q2: 哪些错误可以重试？

**A**: 网络超时、5xx 错误、429。不可重试：4xx 客户端错误、业务逻辑错误。

### Q3: 熔断器的三种状态？

**A**: Closed（正常）/ Open（熔断，直接降级）/ HalfOpen（试探，少量请求通过）。

---

## 第六部分：生产实践

### 1. 超时配置

```
超时配置要点：
1. 查询操作 30s
2. 创建操作 30s
3. 发布操作 60s
4. 批量操作 120s
```

### 2. 重试策略

```
重试策略要点：
1. 最多 3 次重试
2. 指数退避 + 抖动
3. 只重试可恢复的错误
4. 记录重试日志
```

### 3. 降级策略

```
降级策略要点：
1. 缓存兜底
2. 默认值兜底
3. 备用服务器兜底
4. 友好的错误提示
```
