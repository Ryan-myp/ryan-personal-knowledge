---
*本文基于微信读书《Agent设计模式》及相关技术文档整理*

---

## 自测题

### 问题 1
React 模式中的 Thought → Action → Observation 循环与传统的 if-then-else 控制流有什么本质区别？

<details>
<summary>查看答案</summary>

**传统 if-then-else 是硬编码逻辑**，而 React 循环是**基于观察的动态决策**：
1. **解耦**：推理和动作分离，思考部分不涉及具体实现
2. **可扩展**：新增工具只需注册，无需修改核心循环
3. **可调试**：每一步 Thought 都可以记录和回放
4. **容错**：某步失败可以 backtracking 重新思考

</details>

### 问题 2
Go 中 `Tool` 接口为什么只用 `Name()` 和 `Execute()` 两个方法而不是更多？

<details>
<summary>查看答案</summary>

**KISS 原则 + 注册表模式**：
1. `Name()` 用于注册表查找和列出所有工具
2. `Execute()` 是唯一的执行入口
3. 如果工具需要元数据（描述、参数 schema），可以单独实现 `Description()` 等方法，但核心接口保持极简
4. 越少的接口方法，实现成本越低，工具链越灵活

</details>

---

### React 架构的 Go 实现

```go
package reactarch

import (
	"context"
	"fmt"
	"sync"
)

type Tool interface {
	Name() string
	Execute(ctx context.Context, input string) (string, error)
}

type Thought struct {
	Reasoning string
	Action    string
	Input     string
}

type Agent struct {
	tools  map[string]Tool
	mu     sync.Mutex
	memo   []string
}

func (a *Agent) Step(ctx context.Context, thought *Thought) (string, error) {
	tool, ok := a.tools[thought.Action]
	if !ok {
		return "", fmt.Errorf("unknown tool: %s", thought.Action)
	}
	return tool.Execute(ctx, thought.Input)
}

func (a *Agent) Run(ctx context.Context, query string, maxSteps int) (string, error) {
	a.mu.Lock()
	a.memo = append(a.memo, query)
	a.mu.Unlock()

	for i := 0; i < maxSteps; i++ {
		thought := &Thought{
			Reasoning: fmt.Sprintf("Step %d: %s", i+1, query),
			Action:    "search",
			Input:     query,
		}
		obs, err := a.Step(ctx, thought)
		if err != nil {
			return "", err
		}
		a.mu.Lock()
		a.memo = append(a.memo, obs)
		a.mu.Unlock()
	}
	return "Done", nil
}

func main() {
	a := &Agent{tools: map[string]Tool{"search": &mock{}}}
	result, _ := a.Run(context.Background(), "What is RAG?", 3)
	fmt.Printf("Result: %s\n", result)
}

type mock struct{}

func (t *mock) Name() string { return "search" }
func (t *mock) Execute(ctx context.Context, input string) (string, error) {
	return "RAG combines retrieval and generation", nil
}
```