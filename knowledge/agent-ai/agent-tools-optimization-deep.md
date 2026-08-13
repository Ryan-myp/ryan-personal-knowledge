# Agent工具调用优化 - 资深专家深度实现

## 一、工具注册与发现

### 1.1 工具注册系统

```go
// 工具注册表
type ToolRegistry struct {
    tools      map[string]*Tool
    categories map[string][]string
    versions   map[string]string
}

// 工具定义
type Tool struct {
    Name        string
    Description string
    Parameters  map[string]ParameterSchema
    Return      TypeSchema
    Handler     func(context.Context, map[string]interface{}) (interface{}, error)
    Version     string
    Category    string
    Tags        []string
}

// 参数Schema
type ParameterSchema struct {
    Type        string `json:"type"`
    Description string `json:"description"`
    Required    bool   `json:"required"`
    Default     interface{} `json:"default,omitempty"`
    Enum        []interface{} `json:"enum,omitempty"`
    MinLength   int   `json:"minLength,omitempty"`
    MaxLength   int   `json:"maxLength,omitempty"`
}
```

### 1.2 智能发现机制

```go
// 工具发现器
type ToolDiscovery struct {
    registry *ToolRegistry
    indexer  *ToolIndexer
}

// 发现工具
func (d *ToolDiscovery) FindTools(query string, context Context) ([]*Tool, error) {
    // 1. 语义搜索
    semanticResults := d.indexer.SemanticSearch(query)
    
    // 2. 关键词匹配
    keywordResults := d.indexer.KeywordMatch(query)
    
    // 3. 上下文过滤
    filtered := d.filterByContext(semanticResults, context)
    filtered = append(filtered, d.filterByContext(keywordResults, context)...)
    
    // 4. 去重和排序
    return d.deduplicateAndSort(filtered), nil
}

// 上下文过滤
func (d *ToolDiscovery) filterByContext(tools []*Tool, context Context) []*Tool {
    var result []*Tool
    for _, tool := range tools {
        if d.matchesContext(tool, context) {
            result = append(result, tool)
        }
    }
    return result
}

// 匹配上下文
func (d *ToolDiscovery) matchesContext(tool *Tool, context Context) bool {
    // 检查工具适用的场景
    for _, scene := range tool.Categories {
        if context.HasScene(scene) {
            return true
        }
    }
    
    // 检查工具适用的用户类型
    for _, userType := range tool.UserTypes {
        if context.UserType == userType {
            return true
        }
    }
    
    return false
}
```

## 二、工具选择优化

### 2.1 选择策略

```go
// 工具选择器
type ToolSelector struct {
    strategy    SelectStrategy
    evaluator   *ToolEvaluator
    cache       *ToolCache
}

// 选择策略
type SelectStrategy interface {
    Select(tools []*Tool, context Context) (*Tool, error)
}

// 贪婪选择策略
type GreedySelector struct{}

func (g *GreedySelector) Select(tools []*Tool, context Context) (*Tool, error) {
    var best *Tool
    var bestScore float64
    
    for _, tool := range tools {
        score := g.evaluate(tool, context)
        if score > bestScore {
            bestScore = score
            best = tool
        }
    }
    
    if best == nil {
        return nil, errors.New("no suitable tool found")
    }
    
    return best, nil
}

// 评估函数
func (g *GreedySelector) evaluate(tool *Tool, context Context) float64 {
    score := 0.0
    
    // 相关性分数 (40%)
    score += 0.4 * g.relevanceScore(tool, context)
    
    // 性能分数 (30%)
    score += 0.3 * g.performanceScore(tool)
    
    // 可靠性分数 (20%)
    score += 0.2 * g.reliabilityScore(tool)
    
    // 成本分数 (10%)
    score += 0.1 * g.costScore(tool)
    
    return score
}
```

### 2.2 并行调用优化

```go
// 并行工具调用
func (s *ToolSelector) ParallelExecute(tools []*Tool, context Context) ([]ToolResult, error) {
    var wg sync.WaitGroup
    results := make([]ToolResult, len(tools))
    errors := make([]error, len(tools))
    
    for i, tool := range tools {
        wg.Add(1)
        go func(idx int, t *Tool) {
            defer wg.Done()
            
            // 设置超时
            ctx, cancel := context.WithTimeout(context, s.timeout)
            defer cancel()
            
            // 执行工具
            result, err := s.executeTool(ctx, t, context)
            results[idx] = result
            errors[idx] = err
        }(i, tool)
    }
    
    wg.Wait()
    
    // 汇总结果
    return s.aggregateResults(results, errors)
}

// 执行单个工具
func (s *ToolSelector) executeTool(ctx context.Context, tool *Tool, context Context) (ToolResult, error) {
    // 检查缓存
    cacheKey := s.generateCacheKey(tool, context)
    if cached, ok := s.cache.Get(cacheKey); ok {
        return cached, nil
    }
    
    // 执行工具
    result, err := tool.Handler(ctx, context.Params)
    if err != nil {
        return ToolResult{}, err
    }
    
    // 缓存结果
    s.cache.Set(cacheKey, ToolResult{
        Tool:    tool.Name,
        Result:  result,
        Cost:    time.Since(startTime),
        Success: true,
    })
    
    return ToolResult{
        Tool:    tool.Name,
        Result:  result,
        Cost:    time.Since(startTime),
        Success: true,
    }, nil
}
```

## 三、工具链设计

### 3.1 链式调用

```go
// 工具链
type ToolChain struct {
    tools      []*Tool
    dependencies map[string][]string
    executor   *ToolExecutor
}

// 执行工具链
func (c *ToolChain) Execute(input interface{}) (interface{}, error) {
    var current interface{} = input
    
    for _, tool := range c.tools {
        // 检查前置依赖
        if !c.checkDependencies(tool, current) {
            return nil, errors.New("dependency not satisfied")
        }
        
        // 执行工具
        var err error
        current, err = tool.Handler(context.Background(), map[string]interface{}{
            "input": current,
        })
        if err != nil {
            return nil, err
        }
    }
    
    return current, nil
}

// 依赖检查
func (c *ToolChain) checkDependencies(tool *Tool, input interface{}) bool {
    deps, ok := c.dependencies[tool.Name]
    if !ok {
        return true
    }
    
    // 检查输入是否满足所有依赖
    for _, dep := range deps {
        if !c.hasDependency(dep, input) {
            return false
        }
    }
    
    return true
}
```

### 3.2 熔断器模式

```go
// 熔断器
type CircuitBreaker struct {
    state      CircuitState
    failureCnt int
    threshold  int
    resetTimeout time.Duration
    openTime   time.Time
}

type CircuitState int

const (
    Closed CircuitState = iota
    Open
    HalfOpen
)

// 执行方法
func (cb *CircuitBreaker) Execute(fn func() error) error {
    switch cb.state {
    case Open:
        if time.Since(cb.openTime) > cb.resetTimeout {
            cb.state = HalfOpen
        } else {
            return errors.New("circuit breaker open")
        }
    case HalfOpen:
        err := fn()
        if err != nil {
            cb.state = Open
            cb.openTime = time.Now()
        } else {
            cb.state = Closed
            cb.failureCnt = 0
        }
        return err
    default:
        err := fn()
        if err != nil {
            cb.failureCnt++
            if cb.failureCnt >= cb.threshold {
                cb.state = Open
                cb.openTime = time.Now()
            }
        } else {
            cb.failureCnt = 0
        }
        return err
    }
}
```

## 四、监控与可观测性

### 4.1 工具监控

```go
// 工具监控器
type ToolMonitor struct {
    metrics  *MetricsCollector
    tracer   *Tracer
    logger   *Logger
}

// 记录工具调用
func (m *ToolMonitor) RecordCall(tool *Tool, start time.Time, err error) {
    duration := time.Since(start)
    
    // 记录指标
    m.metrics.Increment("tool.calls.total")
    m.metrics.Histogram("tool.calls.duration", duration)
    
    if err != nil {
        m.metrics.Increment("tool.calls.error")
        m.metrics.Increment(fmt.Sprintf("tool.calls.error.%s", tool.Name))
        m.logger.Error("tool call failed", "tool", tool.Name, "error", err)
    } else {
        m.metrics.Increment("tool.calls.success")
    }
    
    // 记录追踪
    m.tracer.RecordCall(tool.Name, start, duration, err)
}

// 性能分析
func (m *ToolMonitor) AnalyzePerformance() {
    // 1. 平均调用时间
    avgDuration := m.metrics.Average("tool.calls.duration")
    
    // 2. P99延迟
    p99Duration := m.metrics.Percentile("tool.calls.duration", 0.99)
    
    // 3. 错误率
    errorRate := m.metrics.Ratio("tool.calls.error", "tool.calls.total")
    
    // 4. 吞吐量
    throughput := m.metrics.Rate("tool.calls.total", "1m")
    
    // 告警
    if p99Duration > m.maxP99Duration {
        m.logger.Warn("high p99 latency", "p99", p99Duration)
    }
    
    if errorRate > m.maxErrorRate {
        m.logger.Warn("high error rate", "rate", errorRate)
    }
}
```

## 五、面试高频题

### Q1: 如何实现工具的智能选择？

```
A:
1. 语义搜索匹配
2. 多因素评分
3. 上下文感知过滤
4. 缓存优化
```

### Q2: 如何处理工具调用超时？

```
A:
1. 设置合理超时
2. 并行调用备选
3. 熔断器保护
4. 降级处理
```

### Q3: 如何优化工具链性能？

```
A:
1. 并行执行无依赖工具
2. 缓存常用结果
3. 懒加载工具
4. 批量处理请求
```

## 六、自测题

1. 解释工具注册流程
2. 如何实现工具的智能选择？
3. 工具链如何设计？

---

## 参考文档

- [Agent记忆系统](../agent-ai/agent-memory-expert-deep.md)
- [Agent安全护栏](../agent-ai/agent-security-guardrails-deep.md)
- [Multi-Agent编排](../agent-ai/multi-agent-orchestration-comparison-deep.md)
