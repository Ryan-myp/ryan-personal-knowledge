# Agent 架构深度：Multi-Agent/ReAct/Planning 实战

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Agent 架构

```
单 Agent = 一个全能助手
  → 什么都会，但什么都不精
  → 上下文窗口有限
  → 容易出错

Multi-Agent = 一个专家团队
  → 每个 Agent 专注一个领域
  → 可以并行工作
  → 互相协作完成任务
```

### 为什么需要 Multi-Agent？

| 维度 | 单 Agent | Multi-Agent |
|------|---------|-------------|
| **上下文窗口** | 有限（32K-128K） | 每个 Agent 独立 |
| **专业能力** | 通用 | 专业化 |
| **并行性** | 串行执行 | 并行执行 |
| **容错性** | 一个失败全失败 | 部分失败可恢复 |
| **扩展性** | 难扩展 | 轻松添加新 Agent |

---

## 第二部分：ReAct 模式深度

### 2.1 ReAct 原理

```
ReAct = Reasoning + Acting

核心思想：
1. 思考（Thought）：分析当前情况
2. 行动（Action）：调用工具
3. 观察（Observation）：获取结果
4. 重复直到得出结论

示例：
Thought: 我需要查询用户的广告历史
Action: search_ad_history(user_id=123)
Observation: 用户最近点击了 3 个运动品牌广告
Thought: 用户可能对运动品牌感兴趣
Action: generate_creative(category=sports)
Observation: 生成了 3 条运动品牌创意
Thought: 创意生成完成
Final Answer: 推荐运动品牌创意
```

### 2.2 Go 实现 ReAct Agent

```go
package agent

import (
    "context"
    "fmt"
    "strings"
)

// ReActAgent ReAct 模式的 Agent
type ReActAgent struct {
    llm        *LLMClient
    tools      []Tool
    maxSteps   int
    history    []ReActStep
}

// Tool 工具定义
type Tool struct {
    Name        string
    Description string
    Parameters  map[string]ParameterSchema
    Execute     func(context.Context, map[string]interface{}) (interface{}, error)
}

// ParameterSchema 参数定义
type ParameterSchema struct {
    Type        string `json:"type"`
    Description string `json:"description"`
    Required    bool   `json:"required"`
}

// ReActStep ReAct 步骤
type ReActStep struct {
    Thought     string      `json:"thought"`
    Action      string      `json:"action"`
    ActionInput interface{} `json:"action_input"`
    Observation interface{} `json:"observation"`
}

// Run 运行 ReAct Agent
func (a *ReActAgent) Run(ctx context.Context, query string) (string, error) {
    a.history = make([]ReActStep, 0)
    
    for i := 0; i < a.maxSteps; i++ {
        // 1. 构建 ReAct prompt
        prompt := a.buildReActPrompt(query, a.history)
        
        // 2. LLM 生成下一步
        response, err := a.llm.Generate(ctx, prompt)
        if err != nil {
            return "", err
        }
        
        // 3. 解析响应
        step, err := a.parseStep(response)
        if err != nil {
            return "", err
        }
        
        a.history = append(a.history, *step)
        
        // 4. 检查是否是最终答案
        if step.Action == "Final Answer" {
            return step.Observation.(string), nil
        }
        
        // 5. 执行工具
        result, err := a.executeTool(step.Action, step.ActionInput)
        if err != nil {
            step.Observation = fmt.Sprintf("Error: %v", err)
        } else {
            step.Observation = result
        }
    }
    
    return "", fmt.Errorf("max steps reached")
}

// buildReActPrompt 构建 ReAct prompt
func (a *ReActAgent) buildReActPrompt(query string, history []ReActStep) string {
    sb := strings.Builder{}
    
    // 系统提示
    sb.WriteString("You are a helpful assistant. Use the following tools to answer the question.\n\n")
    
    // 工具定义
    sb.WriteString("Tools:\n")
    for _, tool := range a.tools {
        sb.WriteString(fmt.Sprintf("- %s: %s\n", tool.Name, tool.Description))
        sb.WriteString(fmt.Sprintf("  Parameters: %v\n", tool.Parameters))
    }
    
    // 示例
    sb.WriteString("\nExamples:\n")
    sb.WriteString("Thought: I need to search for the user's ad history\n")
    sb.WriteString("Action: search_ad_history\n")
    sb.WriteString("Action Input: {\"user_id\": \"123\"}\n")
    sb.WriteString("Observation: User clicked 3 sports brand ads\n")
    sb.WriteString("Thought: User is interested in sports\n")
    sb.WriteString("Final Answer: Recommended sports brand creatives\n\n")
    
    // 当前问题
    sb.WriteString("Question: ")
    sb.WriteString(query)
    sb.WriteString("\n\n")
    
    // 历史记录
    if len(history) > 0 {
        sb.WriteString("Previous steps:\n")
        for _, step := range history {
            sb.WriteString(fmt.Sprintf("Thought: %s\n", step.Thought))
            sb.WriteString(fmt.Sprintf("Action: %s\n", step.Action))
            sb.WriteString(fmt.Sprintf("Action Input: %v\n", step.ActionInput))
            sb.WriteString(fmt.Sprintf("Observation: %v\n", step.Observation))
        }
    }
    
    sb.WriteString("Thought: ")
    
    return sb.String()
}

// parseStep 解析 ReAct 步骤
func (a *ReActAgent) parseStep(response string) (*ReActStep, error) {
    parts := strings.Split(response, "\n")
    step := &ReActStep{}
    
    for _, part := range parts {
        part = strings.TrimSpace(part)
        if strings.HasPrefix(part, "Thought:") {
            step.Thought = strings.TrimSpace(strings.TrimPrefix(part, "Thought:"))
        } else if strings.HasPrefix(part, "Action:") {
            step.Action = strings.TrimSpace(strings.TrimPrefix(part, "Action:"))
        } else if strings.HasPrefix(part, "Action Input:") {
            step.ActionInput = strings.TrimSpace(strings.TrimPrefix(part, "Action Input:"))
        } else if strings.HasPrefix(part, "Observation:") {
            step.Observation = strings.TrimSpace(strings.TrimPrefix(part, "Observation:"))
        }
    }
    
    return step, nil
}

// executeTool 执行工具
func (a *ReActAgent) executeTool(name string, input interface{}) (interface{}, error) {
    for _, tool := range a.tools {
        if tool.Name == name {
            return tool.Execute(context.Background(), input.(map[string]interface{}))
        }
    }
    return nil, fmt.Errorf("tool not found: %s", name)
}
```

---

## 第三部分：Plan-and-Execute 深度

### 3.1 Plan-and-Execute 原理

```
Plan-and-Execute = 先规划，再执行

与传统 ReAct 的区别：
- ReAct: 思考 → 行动 → 观察 → 思考 → 行动（交替进行）
- Plan: 规划所有步骤 → 依次执行（先规划后执行）

优点：
1. 全局视角：可以看到完整计划
2. 错误恢复：某步失败可以重新规划
3. 并行执行：独立步骤可以并行
4. 可解释性：计划清晰可见

缺点：
1. 规划可能不准确
2. 无法适应动态变化
3. 需要更多 LLM 调用
```

### 3.2 Go 实现 Plan-and-Execute

```go
type PlanAndExecuteAgent struct {
    planner   *PlannerAgent
    executor  *ExecutorAgent
    llm       *LLMClient
}

type Plan struct {
    Steps []PlanStep
}

type PlanStep struct {
    Description string
    Tool        string
    Parameters  map[string]interface{}
}

// Run 运行 Plan-and-Execute Agent
func (a *PlanAndExecuteAgent) Run(ctx context.Context, query string) (string, error) {
    // 1. 生成计划
    plan, err := a.planner.GeneratePlan(ctx, query)
    if err != nil {
        return "", err
    }
    
    // 2. 执行计划
    results := make([]string, 0, len(plan.Steps))
    for _, step := range plan.Steps {
        result, err := a.executor.ExecuteStep(ctx, step)
        if err != nil {
            // 错误恢复：重新规划
            plan, err = a.replan(ctx, query, results, err)
            if err != nil {
                return "", err
            }
            continue
        }
        results = append(results, result)
    }
    
    // 3. 汇总结果
    finalAnswer, err := a.llm.Generate(ctx, a.buildSummaryPrompt(query, results))
    if err != nil {
        return "", err
    }
    
    return finalAnswer, nil
}

// PlannerAgent 规划 Agent
type PlannerAgent struct {
    llm *LLMClient
}

func (p *PlannerAgent) GeneratePlan(ctx context.Context, query string) (*Plan, error) {
    prompt := fmt.Sprintf(`You are a planning agent. Break down the following query into executable steps.

Query: %s

Return a JSON plan with the following format:
{
  "steps": [
    {
      "description": "Step description",
      "tool": "tool_name",
      "parameters": {"param1": "value1"}
    }
  ]
}`, query)
    
    response, err := p.llm.Generate(ctx, prompt)
    if err != nil {
        return nil, err
    }
    
    var plan Plan
    err = json.Unmarshal([]byte(response), &plan)
    return &plan, err
}

// ExecutorAgent 执行 Agent
type ExecutorAgent struct {
    tools []Tool
}

func (e *ExecutorAgent) ExecuteStep(ctx context.Context, step PlanStep) (string, error) {
    for _, tool := range e.tools {
        if tool.Name == step.Tool {
            return tool.Execute(ctx, step.Parameters)
        }
    }
    return "", fmt.Errorf("tool not found: %s", step.Tool)
}

// replan 重新规划
func (a *PlanAndExecuteAgent) replan(ctx context.Context, query string, results []string, err error) (*Plan, error) {
    prompt := fmt.Sprintf(`The previous plan failed with error: %v

Previous steps completed:
%s

Please generate a new plan to complete the task.

Query: %s

Return a JSON plan.`, err, strings.Join(results, "\n"), query)
    
    response, err := a.llm.Generate(ctx, prompt)
    if err != nil {
        return nil, err
    }
    
    var plan Plan
    err = json.Unmarshal([]byte(response), &plan)
    return &plan, err
}
```

---

## 第四部分：Multi-Agent 协作

### 4.1 广告平台 Multi-Agent 架构

```
┌─────────────────────────────────────────────────────┐
│                  Orchestrator Agent                   │
│  (协调者：分配任务、汇总结果)                          │
├──────────────┬──────────────┬──────────────┬────────┤
│ Researcher   │ Creator      │ Analyzer     │ Review │
│ Agent        │ Agent        │ Agent        │ Agent  │
├──────────────┼──────────────┼──────────────┼────────┤
│ 搜索竞品     │ 生成创意     │ 分析数据     │ 审核   │
│ 收集信息     │ 撰写文案     │ 评估效果     │ 优化   │
└──────────────┴──────────────┴──────────────┴────────┘
```

### 4.2 Go 实现 Multi-Agent

```go
type MultiAgentSystem struct {
    orchestrator *OrchestratorAgent
    agents       map[string]Agent
}

type Agent interface {
    Name() string
    Run(ctx context.Context, input string) (string, error)
}

// OrchestratorAgent 编排 Agent
type OrchestratorAgent struct {
    llm      *LLMClient
    agents   map[string]Agent
}

func (o *OrchestratorAgent) Run(ctx context.Context, query string) (string, error) {
    // 1. 分析任务，决定调用哪个 Agent
    agentName, err := o.selectAgent(ctx, query)
    if err != nil {
        return "", err
    }
    
    // 2. 调用对应 Agent
    agent := o.agents[agentName]
    result, err := agent.Run(ctx, query)
    if err != nil {
        return "", err
    }
    
    // 3. 如果有多个 Agent，协调结果
    if o.needsCoordination(query) {
        result, err = o.coordinateResults(ctx, query, result)
        if err != nil {
            return "", err
        }
    }
    
    return result, nil
}

func (o *OrchestratorAgent) selectAgent(ctx context.Context, query string) (string, error) {
    prompt := fmt.Sprintf(`You are an orchestrator. Select the best agent for the following query.

Available agents:
- researcher: Search and collect information
- creator: Generate creative content
- analyzer: Analyze data and evaluate results
- reviewer: Review and optimize content

Query: %s

Return only the agent name.`, query)
    
    response, err := o.llm.Generate(ctx, prompt)
    if err != nil {
        return "", err
    }
    
    return strings.TrimSpace(response), nil
}

// ResearcherAgent 研究 Agent
type ResearcherAgent struct {
    llm *LLMClient
}

func (a *ResearcherAgent) Name() string {
    return "researcher"
}

func (a *ResearcherAgent) Run(ctx context.Context, query string) (string, error) {
    prompt := fmt.Sprintf(`Research the following topic and provide a summary.

Topic: %s

Provide:
1. Key findings
2. Competitor analysis
3. Market trends

Topic: %s`, query, query)
    
    return a.llm.Generate(ctx, prompt)
}

// CreatorAgent 创作 Agent
type CreatorAgent struct {
    llm *LLMClient
}

func (a *CreatorAgent) Name() string {
    return "creator"
}

func (a *CreatorAgent) Run(ctx context.Context, query string) (string, error) {
    prompt := fmt.Sprintf(`Create advertising creative based on the following research.

Research: %s

Requirements:
- 3 creative options
- Each with headline and body
- Target audience: 25-35 year old males

Research: %s`, query, query)
    
    return a.llm.Generate(ctx, prompt)
}

// CoordinatorAgent 协调 Agent
type CoordinatorAgent struct {
    llm *LLMClient
}

func (c *CoordinatorAgent) Coordinate(ctx context.Context, query string, results []string) (string, error) {
    prompt := fmt.Sprintf(`Coordinate the following results for the query:

Query: %s

Results:
%s

Provide a coordinated final answer.`, query, strings.Join(results, "\n"))
    
    return c.llm.Generate(ctx, prompt)
}
```

---

## 第五部分：生产排障案例

### 5.1 Agent 循环无限执行

```
现象：Agent 陷入无限循环

排查：
1. 检查 ReAct 步骤数
2. 检查工具返回
3. 检查 LLM 响应

根因：LLM 无法生成 Final Answer

解决方案：
1. 设置最大步骤数
2. 添加超时机制
3. 优化 prompt
```

```go
// 添加超时保护
func (a *ReActAgent) RunWithTimeout(ctx context.Context, query string, timeout time.Duration) (string, error) {
    ctx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()
    
    return a.Run(ctx, query)
}
```

### 5.2 Multi-Agent 协调失败

```
现象：多个 Agent 结果冲突

排查：
1. 检查 Orchestrator 的选择逻辑
2. 检查 Agent 的输出格式
3. 检查协调器的一致性

根因：Agent 输出格式不统一

解决方案：
1. 定义统一的输出 schema
2. 添加结果验证
3. 使用 CoT 提高一致性
```

---

## 第六部分：自测题

### 问题 1
ReAct 相比纯 Prompt 有什么优势？

<details>
<summary>查看答案</summary>

1. **工具调用**：可以调用外部工具
2. **观察反馈**：根据观察调整策略
3. **复杂任务**：适合多步骤任务
4. **广告场景**：创意生成 + 审核
5. **Go 实现**：ReActAgent

</details>

### 问题 2
Plan-and-Execute 相比 ReAct 有什么优势？

<details>
<summary>查看答案</summary>

1. **全局规划**：先看全局再执行
2. **错误恢复**：某步失败可重新规划
3. **并行执行**：独立步骤可并行
4. **可解释性**：计划清晰可见
5. **Limitation**：规划可能不准确

</details>

### 问题 3
Multi-Agent 系统如何协调？

<details>
<summary>查看答案</summary>

1. **Orchestrator**：中央调度器
2. **消息传递**：Agent 间通信
3. **共享状态**：共享上下文
4. **异步执行**：非阻塞调用
5. **Go 实现**：MultiAgentSystem

</details>

---

*本文档基于 Agent 架构原理和生产实战整理。*