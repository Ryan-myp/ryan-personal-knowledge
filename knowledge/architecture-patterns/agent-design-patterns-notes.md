---

## 自测题

### 问题 1
为什么 Agent 设计模式的"反思"（Reflection）机制对生产环境很重要？

<details>
<summary>查看答案</summary>

1. **自我修正**：Agent 可以分析自己的错误输出并调整
2. **质量保障**：减少幻觉和错误决策
3. **学习循环**：通过反思积累经验，越用越好
4. **监控指标**：反思过程本身就是可观测的日志

</details>

### 问题 2
Go 的反射（reflect）和 Agent 的反射（Reflection）有什么本质区别？

<details>
<summary>查看答案</summary>

1. **语言反射**：reflect 包操作运行时类型，是底层机制
2. **Agent 反思**：LLM 自我分析输出，是语义层面的
3. **性能**：reflect 有运行时开销，Agent 反思有 LLM 调用成本
4. **用途**：reflect 用于元编程，Agent 反思用于自我改进

</details>

### 问题 2
Go 的泛型（Generics）在 Agent 工具链中有什么优势？

<details>
<summary>查看答案</summary>

1. **类型安全**：编译期检查工具参数类型
2. **性能**：消除类型断言开销
3. **Go 实现**：
```go
type Tool[T any, R any] interface {
    Execute(ctx context.Context, input T) (R, error)
}

type SearchTool struct{}

func (s *SearchTool) Execute(ctx context.Context, query string) ([]Result, error) {
    // 实现搜索逻辑
    return nil, nil
}

type SummarizeTool struct{}

func (s *SummarizeTool) Execute(ctx context.Context, text string) (string, error) {
    // 实现摘要逻辑
    return "", nil
}
```
4. **适用场景**：不同类型的工具输入/输出类型不同

</details>

### 问题 3
Agent 工具链中如何保证工具调用的幂等性？

<details>
<summary>查看答案</summary>

1. **幂等键**：每个工具调用生成唯一 ID
2. **去重**：通过 ID 判断是否已执行
3. **Go 实现**：
```go
type ToolExecutor struct {
    executed map[string]bool
    mu       sync.Mutex
}

func (te *ToolExecutor) Execute(toolID string, tool Tool) error {
    te.mu.Lock()
    defer te.mu.Unlock()
    
    if te.executed[toolID] {
        return nil  // 幂等：重复调用返回 nil
    }
    
    te.executed[toolID] = true
    _, err := tool.Execute(context.Background(), nil)
    return err
}
```
4. **应用场景**：预算扣减、创意提交等需要保证不重复操作

</details>

---

*本文档基于 Agent 设计模式整理。*

---

## Go 代码示例

### Agent 反思机制

```go
package agent

import (
    "context"
    "fmt"
)

type ReflectionAgent struct {
    llm         *LLMClient
    memory      *MemoryStore
    maxRounds   int
}

type ReflectionResult struct {
    Output     string
    Reflection string
    Valid      bool
}

func (a *ReflectionAgent) Execute(ctx context.Context, task string) (*ReflectionResult, error) {
    for i := 0; i < a.maxRounds; i++ {
        // 第一步：生成输出
        output, err := a.llm.Generate(ctx, task)
        if err != nil {
            return nil, err
        }
        
        // 第二步：反思输出
        reflection := a.reflect(ctx, task, output)
        
        // 第三步：判断是否有效
        if a.isValid(reflection) {
            return &ReflectionResult{
                Output:     output,
                Reflection: reflection,
                Valid:      true,
            }, nil
        }
        
        // 第四步：更新任务，继续反思
        task = a.updateTask(task, reflection)
    }
    
    return &ReflectionResult{
        Output:     "",
        Reflection: "max rounds reached",
        Valid:      false,
    }, nil
}

func (a *ReflectionAgent) reflect(ctx context.Context, task, output string) string {
    prompt := fmt.Sprintf("请反思以下回答的质量：\n\n任务：%s\n回答：%s\n\n请指出回答中的问题和改进建议",
        task, output)
    return a.llm.Generate(ctx, prompt)
}

func (a *ReflectionAgent) isValid(reflection string) bool {
    // 检查反思中是否包含严重错误
    return !containsCriticalError(reflection)
}
```

---

*本文档基于 Agent 设计模式整理。*