# Agent 架构深度：Multi-Agent/Tool Use/Planning

> ReAct/Plan-and-Execute/Multi-Agent 协作/Function Calling/Agent 记忆系统

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 Multi-Agent？

单 Agent 的局限：
- **上下文窗口有限**：无法处理超长对话
- **能力单一**：一个 Agent 难以胜任所有任务
- **并行性差**：串行执行效率低

Multi-Agent 优势：
- **分工协作**：每个 Agent 专注特定领域
- **并行执行**：多个 Agent 同时工作
- **可扩展**：按需添加新 Agent

---

## 第二部分：ReAct 深度

### 2.1 ReAct 模式详解

```
Thought: 我需要查询这个用户的广告历史
Action: search_ad_history(user_id=123)
Observation: 用户最近点击了 3 个运动品牌广告
Thought: 用户可能对运动品牌感兴趣
Action: generate_creative(category=sports)
Observation: 生成了 3 条运动品牌创意
Thought: 创意生成完成
Final Answer: 推荐运动品牌创意
```

### 2.2 Go 实现 ReAct

```go
package agent

import (
    "context"
    "strings"
)

type ReActAgent struct {
    llm      *LLMClient
    tools    []Tool
    maxSteps int
}

type Tool struct {
    Name        string
    Description string
    Parameters  map[string]ParameterSchema
    Execute     func(context.Context, map[string]interface{}) (interface{}, error)
}

type ParameterSchema struct {
    Type        string `json:"type"`
    Description string `json:"description"`
    Required    bool   `json:"required"`
}

type ReActStep struct {
    Thought     string      `json:"thought"`
    Action      string      `json:"action"`
    ActionInput interface{} `json:"action_input"`
    Observation interface{} `json:"observation"`
}

func (a *ReActAgent) Run(ctx context.Context, query string) (string, error) {
    steps := make([]ReActStep, 0)
    
    for i := 0; i < a.maxSteps; i++ {
        // 构建 ReAct prompt
        prompt := a.buildReActPrompt(query, steps)
        
        // LLM 生成下一步
        response, err := a.llm.Generate(ctx, prompt)
        if err != nil {
            return "", err
        }
        
        // 解析响应
        step, err := a.parseStep(response)
        if err != nil {
            return "", err
        }
        
        steps = append(steps, step)
        
        // 检查是否是最终答案
        if step.Action == "Final Answer" {
            return step.Observation.(string), nil
        }
        
        // 执行工具
        result, err := a.executeTool(step.Action, step.ActionInput)
        if err != nil {
            return "", err
        }
        
        step.Observation = result
    }
    
    return "", fmt.Errorf("max steps reached")
}

func (a *ReActAgent) buildReActPrompt(query string, steps []ReActStep) string {
    sb := strings.Builder{}
    
    sb.WriteString("You are a helpful assistant. Use the following tools to answer the question.\n\n")
    sb.WriteString("Tools:\n")
    for _, tool := range a.tools {
        sb.WriteString(fmt.Sprintf("- %s: %s\n", tool.Name, tool.Description))
    }
    
    sb.WriteString("\nExamples:\n")
    sb.WriteString("Thought: I need to search for the user's ad history\n")
    sb.WriteString("Action: search_ad_history\n")
    sb.WriteString("Action Input: {\"user_id\": \"123\"}\n")
    sb.WriteString("Observation: User clicked 3 sports brand ads\n")
    sb.WriteString("Thought: User is interested in sports\n")
    sb.WriteString("Final Answer: Recommended sports brand creatives\n\n")
    
    sb.WriteString("Question: ")
    sb.WriteString(query)
    sb.WriteString("\n\n")
    
    if len(steps) > 0 {
        sb.WriteString("Previous steps:\n")
        for _, step := range steps {
            sb.WriteString(fmt.Sprintf("Thought: %s\n", step.Thought))
            sb.WriteString(fmt.Sprintf("Action: %s\n", step.Action))
            sb.WriteString(fmt.Sprintf("Action Input: %v\n", step.ActionInput))
            sb.WriteString(fmt.Sprintf("Observation: %v\n", step.Observation))
        }
    }
    
    sb.WriteString("Thought: ")
    
    return sb.String()
}

func (a *ReActAgent) parseStep(response string) (*ReActStep, error) {
    // 解析 Thought/Action/Action Input/Observation
    // 简化实现
    parts := strings.Split(response, "\n")
    
    step := &ReActStep{}
    for _, part := range parts {
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

## 第三部分：Plan-and-Execute

### 3.1 Plan-and-Execute 架构

```
用户请求 → Planner Agent → 生成计划 → Executor Agent → 执行计划 → 结果
```

### 3.2 Go 实现

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
            return "", err
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
```

---

## 第四部分：Multi-Agent 协作

### 4.1 广告平台 Multi-Agent 架构

```
┌─────────────────────────────────────────────────────┐
│                  Orchestrator Agent                   │
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

type OrchestratorAgent struct {
    llm       *LLMClient
    agents    map[string]Agent
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

// Researcher Agent
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

// Creator Agent
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
```

---

## 第五部分：自测题

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

*本文档基于 Agent 架构原理整理。*