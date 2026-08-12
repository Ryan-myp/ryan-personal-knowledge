# Agent 可观测性深度实现 - 从Trace到Evaluation

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/可观测性  
> **代码密度**: 32%

---

## 一、可观测性架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 可观测性三层架构                            │
│                                                                     │
│  Layer 1: Infrastructure (基础设施)                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Metrics: Prometheus (QPS/延迟/错误率)                      │   │
│  │  • Traces: Jaeger/Tempo (调用链追踪)                         │   │
│  │  • Logs: Loki/ELK (结构化日志)                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Layer 2: Agent Specific (Agent专属)                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Tool Calls: 工具调用次数/成功率/延迟                       │   │
│  │  • Memory Access: 记忆检索命中率/延迟                        │   │
│  │  • Token Usage: Token消耗/成本                                │   │
│  │  • Safety Events: 安全事件/拦截率                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  Layer 3: Business (业务层)                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Task Completion: 任务完成率                               │   │
│  │  • User Satisfaction: 用户满意度                              │   │
│  │  • Cost per Task: 单次任务成本                                │   │
│  │  • Quality Score: 输出质量评分                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、完整实现

```go
// agent/observability.go
package agent

import (
    "context"
    "time"
    
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

// Observability 可观测性系统
type Observability struct {
    // 基础设施指标
    duration       *prometheus.HistogramVec
    requestsTotal  *prometheus.CounterVec
    errorsTotal    *prometheus.CounterVec
    
    // Agent专属指标
    toolCalls      *prometheus.CounterVec
    toolErrors     *prometheus.CounterVec
    tokenUsage     *prometheus.HistogramVec
    
    // 业务指标
    taskComplete   *prometheus.CounterVec
    safetyHits     *prometheus.CounterVec
}

// NewObservability 创建可观测性实例
func NewObservability() *Observability {
    return &Observability{
        duration: promauto.NewHistogramVec(
            &prometheus.HistogramOpts{
                Name:    "agent_request_duration_seconds",
                Help:    "Agent请求延迟分布",
                Buckets: prometheus.ExponentialBuckets(0.01, 2, 10),
            },
            []string{"agent", "action"},
        ),
        requestsTotal: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "agent_requests_total",
                Help: "Agent请求总数",
            },
            []string{"agent"},
        ),
        errorsTotal: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "agent_errors_total",
                Help: "Agent错误总数",
            },
            []string{"agent", "error_type"},
        ),
        toolCalls: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "agent_tool_calls_total",
                Help: "工具调用总数",
            },
            []string{"agent", "tool"},
        ),
        tokenUsage: promauto.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "agent_token_usage",
                Help:    "Token消耗分布",
                Buckets: prometheus.ExponentialBuckets(100, 2, 12),
            },
            []string{"agent", "model"},
        ),
        taskComplete: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "agent_tasks_completed_total",
                Help: "完成任务总数",
            },
            []string{"agent", "task_type"},
        ),
        safetyHits: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "agent_safety_hits_total",
                Help: "安全拦截次数",
            },
            []string{"agent", "type"},
        ),
    }
}

// RecordToolCall 记录工具调用
func (o *Observability) RecordToolCall(ctx context.Context, agent, tool string, duration time.Duration, err error) {
    o.toolCalls.WithLabelValues(agent, tool).Inc()
    if err != nil {
        o.errorsTotal.WithLabelValues(agent, "tool_error").Inc()
    }
    o.duration.WithLabelValues(agent, "tool_call").Observe(duration.Seconds())
}

// RecordTaskComplete 记录任务完成
func (o *Observability) RecordTaskComplete(agent, taskType string, success bool) {
    if success {
        o.taskComplete.WithLabelValues(agent, taskType).Inc()
    } else {
        o.errorsTotal.WithLabelValues(agent, "task_failed").Inc()
    }
}
```

---

## 三、自测题

1. **Agent可观测性与传统系统有何不同？**
   - 需要追踪非确定性流程、工具调用、记忆访问

2. **为什么需要分层监控？**
   - 不同层级问题定位速度不同

