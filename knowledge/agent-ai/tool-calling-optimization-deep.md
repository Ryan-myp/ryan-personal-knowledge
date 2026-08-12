# Agent 工具调用优化深度实现 - 注册发现到熔断器

> **版本**: v2.1  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/工具调用  
> **代码密度**: 30%

---

## 一、工具注册与发现

```
工具注册发现架构:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ Tool A      │    │ Tool B      │    │ Tool C      │            │
│  │ search      │    │ calculate   │    │ store       │            │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘            │
│         │                  │                  │                    │
│         └──────────────────┼──────────────────┘                    │
│                            ▼                                       │
│                  ┌──────────────────┐                              │
│                  │  Tool Registry   │                              │
│                  │  (服务发现)       │                              │
│                  └────────┬─────────┘                              │
│                           │                                        │
│         ┌─────────────────┼─────────────────┐                    │
│         ▼                 ▼                 ▼                    │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐            │
│  │ Tool Caller │   │ Tool Router │   │  Monitor    │            │
│  │  (调用方)    │   │  (路由)      │   │  (监控)     │            │
│  └─────────────┘   └─────────────┘   └─────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、智能路由

```go
// tool/routing.go
package tool

import (
    "context"
    "strings"
)

// ToolRouter 工具路由器
type ToolRouter struct {
    tools map[string]Tool
    index map[string][]string // 关键词 → 工具列表
}

// Register 注册工具
func (r *ToolRouter) Register(tool Tool) {
    r.tools[tool.Name()] = tool
    for _, keyword := range tool.Keywords() {
        r.index[keyword] = append(r.index[keyword], tool.Name())
    }
}

// Route 智能路由
func (r *ToolRouter) Route(ctx context.Context, query string) ([]string, error) {
    // 1. 关键词匹配
    keywords := tokenize(query)
    candidates := make(map[string]int)
    
    for _, kw := range keywords {
        if tools, ok := r.index[kw]; ok {
            for _, t := range tools {
                candidates[t]++
            }
        }
    }
    
    // 2. 排序 (TF-IDF加权)
    type score struct {
        name string
        score int
    }
    var scored []score
    for name, count := range candidates {
        scored = append(scored, score{name, count})
    }
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].score > scored[j].score
    })
    
    // 3. 返回Top-N
    result := make([]string, 0, min(3, len(scored)))
    for _, s := range scored {
        result = append(result, s.name)
        if len(result) >= 3 {
            break
        }
    }
    
    return result, nil
}
```

---

## 三、并行调用优化

```go
// tool/parallel.go
package tool

import (
    "context"
    "sync"
    "time"
)

// ParallelCaller 并行调用器
type ParallelCaller struct {
    maxConcurrent int
    timeout       time.Duration
}

// CallParallel 并行调用多个工具
func (c *ParallelCaller) CallParallel(ctx context.Context, calls []ToolCall) ([]CallResult, error) {
    ctx, cancel := context.WithTimeout(ctx, c.timeout)
    defer cancel()
    
    var wg sync.WaitGroup
    results := make([]CallResult, len(calls))
    errors := make([]error, len(calls))
    
    // 信号量控制并发
    sem := make(chan struct{}, c.maxConcurrent)
    
    for i, call := range calls {
        wg.Add(1)
        sem <- struct{}{}
        
        go func(idx int, tc ToolCall) {
            defer wg.Done()
            defer func() { <-sem }()
            
            result, err := tc.Tool.Execute(ctx, tc.Input)
            results[idx] = CallResult{
                ToolName: tc.Tool.Name(),
                Output:   result,
                Error:    err,
            }
            errors[idx] = err
        }(i, call)
    }
    
    wg.Wait()
    
    // 检查错误
    for _, err := range errors {
        if err != nil {
            return results, err
        }
    }
    
    return results, nil
}

type ToolCall struct {
    Tool   Tool
    Input  interface{}
}

type CallResult struct {
    ToolName string
    Output   interface{}
    Error    error
}
```

---

## 四、熔断器模式

```go
// tool/circuit_breaker.go
package tool

import (
    "sync"
    "time"
)

// CircuitState 熔断器状态
type CircuitState int

const (
    CircuitClosed CircuitState = iota
    CircuitOpen
    CircuitHalfOpen
)

// CircuitBreaker 熔断器
type CircuitBreaker struct {
    mu           sync.Mutex
    state        CircuitState
    failureCount int
    successCount int
    threshold    int       // 失败阈值
    resetTimeout time.Duration
    lastFailure  time.Time
}

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(threshold int, resetTimeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        state:        CircuitClosed,
        threshold:    threshold,
        resetTimeout: resetTimeout,
    }
}

// Execute 执行调用 (带熔断)
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    // 检查是否需要打开
    if cb.state == CircuitOpen {
        if time.Since(cb.lastFailure) > cb.resetTimeout {
            cb.state = CircuitHalfOpen
        } else {
            return ErrCircuitOpen
        }
    }
    
    // 执行调用
    err := fn()
    
    if err != nil {
        cb.failureCount++
        cb.lastFailure = time.Now()
        if cb.failureCount >= cb.threshold {
            cb.state = CircuitOpen
            return ErrCircuitOpen
        }
        return err
    }
    
    // 成功
    cb.failureCount = 0
    cb.successCount++
    if cb.state == CircuitHalfOpen && cb.successCount >= 3 {
        cb.state = CircuitClosed
    }
    return nil
}

var (
    ErrCircuitOpen = errors.New("circuit breaker is open")
)
```

---

## 五、自测题

1. **工具路由为什么需要关键词索引？**
   - O(1)查找比O(n)遍历高效得多

2. **熔断器的三个阶段？**
   - Closed(正常) → Open(熔断) → HalfOpen(试探)

