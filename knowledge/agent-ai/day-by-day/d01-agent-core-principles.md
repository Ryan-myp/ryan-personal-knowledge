3. 工具返回了什么？
4. LLM 怎么组合信息给出答案？
---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

### Agent 核心原理的 Go 实现

```go
package agentcore

import (
	"context"
	"fmt"
	"sync"
)

type Tool interface {
	Name() string
	Execute(ctx context.Context, input string) (string, error)
}

type Agent struct {
	name     string
	tools    map[string]Tool
	memory   []string
	maxSteps int
	mu       sync.Mutex
}

func NewAgent(name string, tools []Tool) *Agent {
	a := &Agent{name: name, tools: make(map[string]Tool), maxSteps: 10}
	for _, t := range tools {
		a.tools[t.Name()] = t
	}
	return a
}

func (a *Agent) Run(ctx context.Context, query string) (string, error) {
	a.mu.Lock()
	a.memory = append(a.memory, "Q: "+query)
	a.mu.Unlock()

	for i := 0; i < a.maxSteps; i++ {
		action := a.planAction(query, i)
		tool, ok := a.tools[action]
		if !ok {
			return fmt.Sprintf("Final answer: %s", query), nil
		}
		obs, err := tool.Execute(ctx, query)
		if err != nil {
			return "", err
		}
		a.mu.Lock()
		a.memory = append(a.memory, fmt.Sprintf("Step %d: obs=%s", i, obs))
		a.mu.Unlock()
	}
	return "Max steps", nil
}

func (a *Agent) planAction(query string, step int) string {
	if step == 0 {
		return "search"
	}
	return "finalize"
}

func (a *Agent) GetMemory() []string {
	a.mu.Lock()
	defer a.mu.Unlock()
	return append([]string{}, a.memory...)
}

func main() {
	agent := NewAgent("researcher", []Tool{&mock{}})
	result, _ := agent.Run(context.Background(), "What is RAG?")
	fmt.Printf("Result: %s\n", result)
	fmt.Printf("Memory: %d steps\n", len(agent.GetMemory()))
}

type mock struct{}

func (t *mock) Name() string          { return "search" }
func (t *mock) Execute(ctx context.Context, input string) (string, error) {
	return "RAG = Retrieval Augmented Generation", nil
}
```

---

## 自测题

### 问题 1
Go 的 goroutine 泄漏怎么排查？

<details>
<summary>查看答案</summary>

1. 用 pprof 分析 goroutine 数量
2. `runtime.NumGoroutine()` 持续监控
3. 检查 channel 是否有人接收
4. 检查 context 是否正确传递和取消
5. 常见泄漏场景：goroutine 阻塞在 channel 上

</details>

### 问题 2
Agent 主循环中 `planAction` 返回 "finalize" 代表什么？

<details>
<summary>查看答案</summary>

1. Agent 已经收集了足够信息
2. 不再需要调用工具，直接输出最终答案
3. 避免不必要的 API 调用，节省 token
4. 这是 ReAct 模式的终止条件之一

</details>
### 问题 3
Agent 系统的可观测性监控指标应该包括哪些？

<details>
<summary>查看答案</summary>

1. **吞吐率**：每秒处理的 request 数（QPS），反映系统承载能力
2. **延迟分布**：P50/P90/P99 响应时间，定位慢请求和瓶颈
3. **错误率**：failure / total ratio，异常比例过高需及时告警
4. **tool 利用率**：各个 tool 被调用的频次，发现 hot paths 优化热点
5. **memory 使用量**：Agent 会话占用的内存，防止泄漏和 OOM
6. **token 用量**：每个 request 消耗的前向/后向 token，监控 cost 趋势
7. **react 循环深度**：平均 step 数，过深可能表示 plan 困难或 tool 不够好
</details>
