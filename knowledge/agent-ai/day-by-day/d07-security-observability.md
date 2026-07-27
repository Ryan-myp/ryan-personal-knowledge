---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

### Agent 安全和可观测性的 Go 实现

```go
package observability

import (
	"fmt"
	"sync"
	"time"
)

type Trace struct {
	TraceID   string
	SpanID    string
	Operation string
	Duration  time.Duration
	Timestamp time.Time
	Children  []*Span
}

type Span struct {
	TraceID   string
	SpanID    string
	Operation string
	Start     time.Time
	End       time.Time
	Labels    map[string]string
}

func (s *Span) EndSpan() {
	s.End = time.Now()
}

type Tracer struct {
	traces map[string]*Trace
	spanID int
	mu     sync.Mutex
}

func NewTracer() *Tracer {
	return &Tracer{traces: make(map[string]*Trace), spanID: 1}
}

func (t *Tracer) StartSpan(operation string) *Span {
	t.mu.Lock()
	defer t.mu.Unlock()
	id := t.spanID
	t.spanID++
	span := &Span{
		TraceID:   fmt.Sprintf("trace_%d", id/100),
		SpanID:    fmt.Sprintf("span_%d", id),
		Operation: operation,
		Start:     time.Now(),
		Labels:    make(map[string]string),
	}
	traceID := fmt.Sprintf("trace_%d", id/100)
	if _, ok := t.traces[traceID]; !ok {
		t.traces[traceID] = &Trace{TraceID: traceID, Operation: operation}
	}
	return span
}

func (t *Tracer) GetTraces() map[string]*Trace {
	t.mu.Lock()
	defer t.mu.Unlock()
	result := make(map[string]*Trace)
	for k, v := range t.traces {
		result[k] = v
	}
	return result
}

type Logger struct {
	entries []LogEntry
	mu      sync.Mutex
}

type LogEntry struct {
	Timestamp time.Time
	Level     string
	Message   string
}

func NewLogger() *Logger { return &Logger{entries: make([]LogEntry, 0)} }

func (l *Logger) Info(msg string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.entries = append(l.entries, LogEntry{time.Now(), "INFO", msg})
}

func (l *Logger) Error(msg string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.entries = append(l.entries, LogEntry{time.Now(), "ERROR", msg})
}

func main() {
	tracer := NewTracer()
	span := tracer.StartSpan("rag_query")
	time.Sleep(10 * time.Millisecond)
	span.EndSpan()
	fmt.Printf("Span %s: %s (%v)\n", span.SpanID, span.Operation, span.End.Sub(span.Start))

	logger := NewLogger()
	logger.Info("Query processed")
	logger.Error("Connection timeout")
	fmt.Printf("Log entries: %d\n", len(logger.entries))
}
```

---

## 自测题

### 问题 1
Agent 的可观测性为什么需要 Tracer + Logger 两套系统？

<details>
<summary>查看答案</summary>

1. **Tracer**：关注调用链和性能，记录每个 Span 的耗时
2. **Logger**：关注事件和异常，记录 INFO/ERROR 级别日志
3. Tracer 用于性能分析和瓶颈定位
4. Logger 用于故障排查和安全审计

</details>

### 问题 2
Go 的 pprof 和自定义 Tracer 在 Agent 监控中各有什么作用？

<details>
<summary>查看答案</summary>

1. **pprof**：系统级监控，goroutine/内存/CPU 使用
2. **自定义 Tracer**：业务级监控，每个 Agent step 的耗时和状态
3. pprof 适合排查性能问题（慢查询、内存泄漏）
4. Tracer 适合排查业务问题（哪个 step 卡住了、哪个 tool 失败了）

</details>
### 问题 3
Agent 执行过程中的敏感信息如何脱敏？

<details>
<summary>查看答案</summary>

1. **红队测试**：定期用潜在有毒 query 测试 Agent，检查是否输出 PII（个人身份信息）或敏感数据
2. **输出过滤**：正则表达式匹配 credit card number、phone number、email 等模式，发现即替换为 [REDACTED]
3. **输入过滤**：user input 中包含敏感字段时提前拦截或标记为 high risk 需要 review
4. **审计日志**：所有 input/output 记录到 immutable audit log，支持事后追溯和责任认定
5. **权限隔离**：不同 role 的 Agent 可见不同数据范围，service account 遵循 least privilege 原则
</details>
