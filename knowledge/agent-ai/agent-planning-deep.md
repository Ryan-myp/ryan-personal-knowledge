# Agent 规划系统深度实现 - 从ReAct到Plan-and-Execute

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/规划  
> **代码密度**: 30%

---

## 一、规划模式对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 规划模式对比                                │
│                                                                     │
│  Mode 1: ReAct (反应式)                                             │
│  ─────────────────────────────────                                 │
│  Thought → Action → Observation → Thought → Action → ...           │
│  • 优点: 简单灵活                                                   │
│  • 缺点: 缺乏全局规划                                               │
│                                                                     │
│  Mode 2: Plan-and-Execute (计划执行)                                 │
│  ─────────────────────────────────                                 │
│  Plan: [step1, step2, step3]                                        │
│  Execute: step1 → step2 → step3                                   │
│  • 优点: 有全局视角                                                 │
│  • 缺点: 计划僵化，难以调整                                         │
│                                                                     │
│  Mode 3: Tree-of-Thoughts (树搜索)                                   │
│  ─────────────────────────────────                                 │
│  生成多个可能路径，评估选择最优                                       │
│  • 优点: 探索性强                                                   │
│  • 缺点: Token消耗大                                                │
│                                                                     │
│  Mode 4: Graph-of-Thoughts (图搜索)                                  │
│  ─────────────────────────────────                                 │
│  有向无环图表示依赖关系                                              │
│  • 优点: 支持并行和依赖                                              │
│  • 缺点: 实现复杂                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Plan-and-Execute 实现

```go
// agent/planning.go
package agent

import (
    "context"
    "fmt"
)

// PlanStep 计划步骤
type PlanStep struct {
    ID          string
    Description string
    Tool        string
    Args        map[string]interface{}
    DependsOn   []string
    Status      PlanStatus
}

type PlanStatus int

const (
    PlanPending PlanStatus = iota
    PlanRunning
    PlanDone
    PlanFailed
)

// Planner 规划器
type Planner struct {
    llm        LLMClient
    maxRetries int
}

// GeneratePlan 生成计划
func (p *Planner) GeneratePlan(ctx context.Context, goal string) (*Plan, error) {
    prompt := fmt.Sprintf(`
Create a step-by-step plan to achieve: %s

Return JSON format:
{
  "steps": [
    {"id": "1", "description": "...", "tool": "...", "args": {...}}
  ]
}
`, goal)
    
    response, err := p.llm.Generate(ctx, prompt)
    if err != nil {
        return nil, err
    }
    
    plan := parsePlan(response)
    return plan, nil
}

// ExecutePlan 执行计划
func (p *Planner) ExecutePlan(ctx context.Context, plan *Plan) (*PlanResult, error) {
    result := &PlanResult{Steps: make([]*StepResult, 0)}
    
    for _, step := range plan.Steps {
        // 检查依赖
        if !p.checkDependencies(step, result) {
            continue
        }
        
        // 执行步骤
        stepResult := p.executeStep(ctx, step)
        result.Steps = append(result.Steps, stepResult)
        
        // 失败处理
        if stepResult.Error != nil && stepResult.Error != ErrRetry {
            if p.shouldRetry(stepResult); p.maxRetries > 0 {
                stepResult = p.retryStep(ctx, step)
            }
        }
    }
    
    return result, nil
}
```

---

## 三、自测题

1. **为什么需要Plan-and-Execute而不是纯ReAct？**
   - 复杂任务需要全局视角，避免局部最优

2. **如何处理执行过程中的异常？**
   - 依赖检查 + 重试机制 + 动态调整计划

