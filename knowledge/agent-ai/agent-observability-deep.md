# Agent 可观测性深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、可观测性架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent 可观测性架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据采集层                                │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │   Traces    │  │   Metrics   │  │      Logs           │  │   │
│  │  │   链路追踪   │  │   指标采集   │  │      结构化日志      │  │   │
│  │  ├─────────────┤  ├─────────────┤  ├─────────────────────┤  │   │
│  │  │ • LLM 调用  │  │ • Token 用量 │  │ • 工具调用日志      │  │   │
│  │  │ • 工具调用  │  │ • 延迟分布   │  │ • 错误堆栈          │  │   │
│  │  │ • 内存状态  │  │ • 成功率     │  │ • 上下文快照        │  │   │
│  │  │ • 状态转换  │  │ • 并发数     │  │ • 用户交互记录      │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据存储层                                │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  Traces  →  Jaeger / Tempo / X-AI Trace                     │   │
│  │  Metrics →  Prometheus / VictoriaMetrics                    │   │
│  │  Logs    →  Loki / ELK / Datadog                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    可视化层                                  │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  Grafana Dashboard / LangSmith / Arize Phoenix / Weights&Biases│  │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Tracing 实现

### 2.1 OpenTelemetry 集成

```go
// 文件: observability/tracing.go
package observability

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
)

// AgentSpan 智能体 Span
type AgentSpan struct {
    span     trace.Span
    tracer   trace.Tracer
    agentID  string
}

func NewAgentSpan(ctx context.Context, agentID string, spanName string) *AgentSpan {
    tracer := otel.Tracer("agent/" + agentID)
    span, newCtx := tracer.Start(ctx, spanName)
    return &AgentSpan{
        span:    span,
        tracer:  tracer,
        agentID: agentID,
    }
}

func (as *AgentSpan) End() {
    as.span.End()
}

func (as *AgentSpan) SetAttribute(key string, value interface{}) {
    as.span.SetAttributes(attribute.Key(key), attribute.ValueOf(value))
}

func (as *AgentSpan) SetError(err error) {
    if err != nil {
        as.span.RecordError(err)
        as.span.SetStatus(codes.Error, err.Error())
    }
}
```

### 2.2 完整调用链追踪

```go
// 文件: observability/call_chain.go
package observability

import (
    "context"
    "time"
)

// CallChain 调用链记录
type CallChain struct {
    TraceID    string          `json:"trace_id"`
    SpanID     string          `json:"span_id"`
    ParentID   string          `json:"parent_id"`
    Type       string          `json:"type"` // llm, tool, agent
    Name       string          `json:"name"`
    Start      time.Time       `json:"start"`
    End        time.Time       `json:"end"`
    DurationMs int64           `json:"duration_ms"`
    Status     string          `json:"status"` // success, error, timeout
    Attributes map[string]interface{} `json:"attributes"`
    Children   []*CallChain    `json:"children"`
}

// TraceRecorder 追踪记录器
type TraceRecorder struct {
    traces   map[string]*CallChain
    mu       sync.Mutex
}

func NewTraceRecorder() *TraceRecorder {
    return &TraceRecorder{
        traces: make(map[string]*CallChain),
    }
}

// RecordLLMCalls 记录 LLM 调用
func (tr *TraceRecorder) RecordLLMCalls(
    ctx context.Context,
    model string,
    prompt string,
    response string,
    latency time.Duration,
    tokens int,
) *CallChain {
    
    traceID := generateTraceID()
    chain := &CallChain{
        TraceID:    traceID,
        Type:       "llm",
        Name:       model,
        Start:      time.Now(),
        End:        time.Now().Add(latency),
        DurationMs: latency.Milliseconds(),
        Status:     "success",
        Attributes: map[string]interface{}{
            "model":    model,
            "tokens":   tokens,
            "prompt_len": len(prompt),
            "response_len": len(response),
        },
    }
    
    tr.mu.Lock()
    tr.traces[traceID] = chain
    tr.mu.Unlock()
    
    return chain
}

// RecordToolCalls 记录工具调用
func (tr *TraceRecorder) RecordToolCalls(
    ctx context.Context,
    toolName string,
    input map[string]interface{},
    output interface{},
    latency time.Duration,
    err error,
) *CallChain {
    
    traceID := generateTraceID()
    status := "success"
    if err != nil {
        status = "error"
    }
    
    chain := &CallChain{
        TraceID:    traceID,
        Type:       "tool",
        Name:       toolName,
        Start:      time.Now(),
        End:        time.Now().Add(latency),
        DurationMs: latency.Milliseconds(),
        Status:     status,
        Attributes: map[string]interface{}{
            "tool_name": toolName,
            "input":     input,
            "output":    output,
            "error":     err,
        },
    }
    
    tr.mu.Lock()
    tr.traces[traceID] = chain
    tr.mu.Unlock()
    
    return chain
}
```

---

## 三、Metrics 指标体系

### 3.1 Agent 核心指标

```go
// 文件: observability/metrics.go
package observability

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

// AgentMetrics Agent 指标收集器
type AgentMetrics struct {
    // LLM 指标
    llmCallsTotal       prometheus.Counter
    llmLatency          prometheus.Histogram
    llmTokensTotal      prometheus.Counter
    llmErrorsTotal      prometheus.Counter
    
    // 工具指标
    toolCallsTotal      prometheus.Counter
    toolLatency         prometheus.Histogram
    toolErrorsTotal     prometheus.Counter
    
    // Agent 指标
    agentTurnsTotal     prometheus.Counter
    agentTurnsDuration  prometheus.Histogram
    agentIterations     prometheus.Histogram
    agentMemoryOps      prometheus.Counter
    agentCostTotal      prometheus.Counter
    
    // 质量指标
    userSatisfaction    prometheus.Gauge
    taskCompletionRate  prometheus.Gauge
    hallucinationRate   prometheus.Gauge
}

func NewAgentMetrics(agentID string) *AgentMetrics {
    vars := prometheus.VariableLabels{"agent_id"}
    
    return &AgentMetrics{
        llmCallsTotal: promauto.NewCounter(prometheus.CounterOpts{
            Name: "agent_llm_calls_total",
            Help: "Total LLM calls",
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
        
        llmLatency: promauto.NewHistogram(prometheus.HistogramOpts{
            Name: "agent_llm_latency_seconds",
            Help: "LLM call latency",
            Buckets: prometheus.ExponentialBuckets(0.1, 2, 10),
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
        
        llmTokensTotal: promauto.NewCounter(prometheus.CounterOpts{
            Name: "agent_llm_tokens_total",
            Help: "Total LLM tokens used",
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
        
        toolCallsTotal: promauto.NewCounter(prometheus.CounterOpts{
            Name: "agent_tool_calls_total",
            Help: "Total tool calls",
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
        
        agentTurnsTotal: promauto.NewCounter(prometheus.CounterOpts{
            Name: "agent_turns_total",
            Help: "Total agent turns",
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
        
        agentCostTotal: promauto.NewCounter(prometheus.CounterOpts{
            Name: "agent_cost_total",
            Help: "Total agent cost in USD",
            ConstLabels: map[string]string{"agent_id": agentID},
        }),
    }
}

// RecordLLMCall 记录 LLM 调用
func (m *AgentMetrics) RecordLLMCall(latency time.Duration, tokens int, cost float64) {
    m.llmCallsTotal.Inc()
    m.llmTokensTotal.Add(float64(tokens))
    m.llmLatency.Observe(latency.Seconds())
    m.agentCostTotal.IncBy(cost)
}
```

### 3.2 业务指标

```go
// 文件: observability/business_metrics.go
package observability

// BusinessMetrics 业务指标
type BusinessMetrics struct {
    taskSuccessRate  *prometheus.GaugeVec
    avgTaskDuration  *prometheus.HistogramVec
    userRetention    *prometheus.CounterVec
}

// 监控指标:
// ├─ 任务完成率: Task Success Rate
// ├─ 平均任务耗时: Average Task Duration
// ├─ 用户留存率: User Retention
// ├─ 工具调用失败率: Tool Error Rate
// ├─ LLM 幻觉率: Hallucination Rate
// └─ 用户满意度: User Satisfaction Score
```

---

## 四、日志系统

### 4.1 结构化日志

```go
// 文件: observability/logger.go
package observability

import (
    "context"
    "github.com/uber-go/zap"
    goctx "context"
)

// AgentLogger Agent 日志记录器
type AgentLogger struct {
    logger *zap.Logger
    fields []zap.Field
}

func NewAgentLogger(agentID string) *AgentLogger {
    logger, _ := zap.NewProduction()
    return &AgentLogger{
        logger: logger,
        fields: []zap.Field{
            zap.String("agent_id", agentID),
            zap.String("timestamp", time.Now().UTC().Format(time.RFC3339)),
        },
    }
}

// Info 记录信息日志
func (l *AgentLogger) Info(ctx context.Context, msg string, fields ...zap.Field) {
    allFields := append(l.fields, fields...)
    l.logger.Info(msg, allFields...)
}

// Error 记录错误日志
func (l *AgentLogger) Error(ctx context.Context, msg string, err error, fields ...zap.Field) {
    allFields := append(fields, zap.Error(err))
    allFields = append(l.fields, allFields...)
    l.logger.Error(msg, allFields...)
}

// StructuredLog 结构化日志模板
type StructuredLog struct {
    Timestamp   time.Time       `json:"timestamp"`
    Level       string          `json:"level"`
    AgentID     string          `json:"agent_id"`
    TraceID     string          `json:"trace_id"`
    SpanID      string          `json:"span_id"`
    Event       string          `json:"event"`
    Data        json.RawMessage `json:"data"`
}
```

### 4.2 上下文快照

```go
// 文件: observability/context_snapshot.go
package observability

import (
    "encoding/json"
    "time"
)

// ContextSnapshot 上下文快照
type ContextSnapshot struct {
    Timestamp    time.Time               `json:"timestamp"`
    AgentID      string                  `json:"agent_id"`
    TurnNumber   int                     `json:"turn_number"`
    MemoryState  map[string]interface{}  `json:"memory_state"`
    ToolStates   map[string]ToolState    `json:"tool_states"`
    LLMContext   LLMContextSnapshot      `json:"llm_context"`
    Performance  PerformanceSnapshot     `json:"performance"`
}

type ToolState struct {
    Name       string                 `json:"name"`
    Input      map[string]interface{} `json:"input"`
    Output     map[string]interface{} `json:"output"`
    LatencyMs  int64                  `json:"latency_ms"`
    Status     string                 `json:"status"`
}

// CaptureSnapshot 捕获当前状态快照
func CaptureSnapshot(agentID string, turnNumber int) *ContextSnapshot {
    return &ContextSnapshot{
        Timestamp:  time.Now(),
        AgentID:    agentID,
        TurnNumber: turnNumber,
        MemoryState: getCurrentMemoryState(),
        ToolStates:  getAllToolStates(),
        LLMContext:  getLLMContextSnapshot(),
        Performance: getPerformanceSnapshot(),
    }
}
```

---

## 五、Grafana 仪表盘配置

```json
{
  "dashboard": {
    "title": "Agent Performance Overview",
    "panels": [
      {
        "title": "LLM Call Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(agent_llm_latency_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Token Usage",
        "type": "graph", 
        "targets": [
          {
            "expr": "rate(agent_llm_tokens_total[5m])"
          }
        ]
      },
      {
        "title": "Agent Turns",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(agent_turns_total[5m])"
          }
        ]
      },
      {
        "title": "Task Success Rate",
        "type": "gauge",
        "targets": [
          {
            "expr": "agent_task_completion_rate"
          }
        ]
      }
    ]
  }
}
```

---

## 六、性能基准

```
┌─────────────────────────────────────────────────────────────────┐
│                    可观测性开销基准                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  功能                    开销        影响                        │
│  ─────────────────────────────────────────────────────────    │
│  基础 Tracing           <1ms       <1% 延迟增加                │
│  结构化日志             <0.5ms     <0.5%                       │
│  Metrics 收集           <0.1ms     <0.1%                       │
│  上下文快照             5ms        5% (可选)                    │
│  全量日志采样           10ms       10% (生产关闭)               │
│                                                                 │
│  推荐配置:                                                       │
│  ├─ 开发环境: 全量采集 (100% 采样)                               │
│  ├─ 生产环境: 关键路径 100%, 其他 10%                           │
│  └─ 成本敏感: 仅 Metrics + 错误 Tracing                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、实战排障指南

```
问题 1: Tracing 丢失
症状: Trace 不完整，缺少部分 Span
解决方案:
  - 检查 Context Propagation
  - 确认 Span 父子关系正确
  - 增加采样率

问题 2: 指标丢失
症状: Prometheus scrape 失败
解决方案:
  - 检查 exporter 健康
  - 验证 scrape config
  - 增加 scrape timeout

问题 3: 日志量大
症状: 存储成本过高
解决方案:
  - 降低采样率
  - 启用日志聚合
  - 设置 retention policy
```

---

## 八、参考资料

```
核心论文:
├── "Observability for AI Systems"
├── "Production LLM Applications"
└── "MLOps: Machine Learning Operations"

开源工具:
├── OpenTelemetry
├── LangSmith
├── Arize Phoenix
└── Weights & Biases

最佳实践:
├── OpenAI Observability
└── Anthropic CloudWatch
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
