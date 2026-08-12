# Agent 调试指南深度实现 - 从日志到分布式追踪

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/调试指南  
> **代码密度**: 30%

---

## 一、调试方法

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 调试方法                                   │
│                                                                     │
│  Method 1: Structured Logging (结构化日志)                           │
│  ─────────────────────────────                                      │
│  • 统一日志格式: timestamp, level, trace_id, agent_id               │
│  • 分层日志: DEBUG/INFO/WARN/ERROR                                 │
│  • 关键节点日志: 输入/输出/工具调用/状态转换                         │
│                                                                     │
│  Method 2: Distributed Tracing (分布式追踪)                          │
│  ─────────────────────────────                                      │
│  • OpenTelemetry集成                                                │
│  • Span层级展示工具调用链                                            │
│  • 延迟分解: 思考/等待/执行                                          │
│                                                                     │
│  Method 3: Replay Debugging (回放调试)                                │
│  ─────────────────────────────                                      │
│  • 记录完整对话历史                                                  │
│  • 重现特定场景                                                     │
│  • 对比不同版本的Agent行为                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、实现示例

```go
// agent/debug.go
package agent

import (
    "context"
    "go.opentelemetry.io/otel/trace"
)

// DebugLogger 调试日志器
type DebugLogger struct {
    tracer trace.Tracer
}

// StartSpan 开始追踪span
func (d *DebugLogger) StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
    return d.tracer.Start(ctx, name)
}

// LogToolCall 记录工具调用
func (d *DebugLogger) LogToolCall(ctx context.Context, tool string, args, result interface{}) {
    span := trace.SpanFromContext(ctx)
    span.SetAttributes(
        attribute.String("tool.name", tool),
        attribute.String("tool.args", fmt.Sprintf("%v", args)),
        attribute.String("tool.result", fmt.Sprintf("%v", result)),
    )
}

// ReplayContext 回放上下文
type ReplayContext struct {
    Messages   []Message
    ToolCalls  []ToolCall
    Decisions  []Decision
}

// Replay 重放对话
func (d *DebugLogger) Replay(ctx context.Context, replay *ReplayContext) error {
    for _, msg := range replay.Messages {
        d.logMessage(ctx, msg)
    }
    for _, call := range replay.ToolCalls {
        d.logToolCall(ctx, call.Tool, call.Args, call.Result)
    }
    return nil
}
```

---

## 三、自测题

1. **为什么需要结构化日志？**
   - 便于检索和分析，支持自动化处理

2. **分布式追踪的核心价值？**
   - 定位性能瓶颈，理解调用链

