# Agent 工作流引擎深度实现 - 状态机到SubAgent编排

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/工作流  
> **代码密度**: 32%

---

## 一、状态机架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 状态机流程                                  │
│                                                                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │  START  │───►│  PLAN   │───►│  EXEC   │───►│  VERIFY │         │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘         │
│       │               │               │               │            │
│       └───────────────┴───────────────┴───────────────┘            │
│                           │                                         │
│                           ▼                                         │
│                      ┌─────────┐                                     │
│                      │  FINISH │                                     │
│                      └─────────┘                                     │
│                                                                     │
│  状态转换规则:                                                       │
│  • PLAN → EXEC: 计划生成成功                                        │
│  • EXEC → VERIFY: 执行完成                                          │
│  • VERIFY → PLAN: 验证失败，重新规划                                  │
│  • EXEC → PLAN: 执行超时/失败，回退重规划                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go实现

```go
// agent/workflow.go
package agent

import (
    "context"
    "fmt"
)

// State 工作流状态
type State int

const (
    StateStart State = iota
    StatePlan
    StateExec
    StateVerify
    StateFinish
    StateError
)

// WorkflowEngine 工作流引擎
type WorkflowEngine struct {
    states map[State]*StateHandler
    logger *Logger
}

// StateHandler 状态处理器
type StateHandler struct {
    state    State
    enter    func(ctx context.Context, input interface{}) (interface{}, error)
    exit     func(ctx context.Context, result interface{})
    transitions map[string]State
}

// Execute 执行工作流
func (e *WorkflowEngine) Execute(ctx context.Context, input interface{}) (interface{}, error) {
    currentState := StateStart
    var result interface{}
    
    for currentState != StateFinish && currentState != StateError {
        handler, ok := e.states[currentState]
        if !ok {
            return nil, fmt.Errorf("unknown state: %d", currentState)
        }
        
        // 进入状态
        result, err := handler.enter(ctx, result)
        if err != nil {
            e.logger.Error("state enter failed", err)
            currentState = StateError
            continue
        }
        
        // 状态转换
        nextState, err := e.decideNextState(handler, result)
        if err != nil {
            currentState = StateError
            break
        }
        currentState = nextState
    }
    
    return result, nil
}

// decideNextState 决策下一步状态
func (e *WorkflowEngine) decideNextState(handler *StateHandler, result interface{}) (State, error) {
    // 基于结果和当前状态决策
    if result == nil {
        return StatePlan, nil // 重新规划
    }
    // 检查验证逻辑
    if e.verify(result) {
        return StateFinish, nil
    }
    return StatePlan, nil // 验证失败，重新规划
}
```

---

## 三、自测题

1. **为什么工作流需要状态机而不是简单的顺序执行？**
   - 支持重试、回退、并行分支等复杂流程

2. **SubAgent的触发条件是什么？**
   - 任务复杂度超过阈值 / 需要专业技能 / 并行处理

