# Agent 状态机深度实现 - 从有限状态机到分层状态机

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/状态机  
> **代码密度**: 32%

---

## 一、状态机设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 分层状态机                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 1: Workflow State (工作流层)                          │   │
│  │  • Idle: 空闲等待                                           │   │
│  │  • Planning: 规划中                                          │   │
│  │  • Executing: 执行中                                          │   │
│  │  • Reviewing: 审核中                                          │   │
│  │  • Completed: 已完成                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 2: SubAgent State (子Agent层)                         │   │
│  │  • ToolCalling: 工具调用中                                    │   │
│  │  • Reasoning: 推理中                                          │   │
│  │  • Waiting: 等待外部输入                                      │   │
│  │  • Error: 错误状态                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 3: Transition Rules (转换规则)                        │   │
│  │  • Idle → Planning: 接收新任务                               │   │
│  │  • Planning → Executing: 计划生成完成                        │   │
│  │  • Executing → Reviewing: 执行完成                           │   │
│  │  • Reviewing → Completed: 审核通过                           │   │
│  │  • Any → Error: 异常捕获                                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go实现

```go
// agent/statemachine.go
package agent

import (
    "context"
    "fmt"
)

// State 状态类型
type State int

const (
    StateIdle State = iota
    StatePlanning
    StateExecuting
    StateReviewing
    StateCompleted
    StateError
)

// Transition 状态转换
type Transition struct {
    From      State
    To        State
    Condition func(Context) bool
    Action    func(Context) error
}

// StateMachine 状态机
type StateMachine struct {
    currentState State
    transitions  []Transition
    history      []StateEvent
}

// StateEvent 状态事件
type StateEvent struct {
    Timestamp time.Time
    From      State
    To        State
    Reason    string
}

// NewStateMachine 创建状态机
func NewStateMachine() *StateMachine {
    return &StateMachine{
        currentState: StateIdle,
        transitions: []Transition{
            {StateIdle, StatePlanning, alwaysTrue, startPlanning},
            {StatePlanning, StateExecuting, planValid, startExecution},
            {StateExecuting, StateReviewing, executionDone, startReview},
            {StateReviewing, StateCompleted, reviewPassed, completeTask},
            {StateReviewing, StatePlanning, reviewFailed, retryPlanning},
        },
    }
}

// TransitionTo 转换状态
func (sm *StateMachine) TransitionTo(ctx Context, to State) error {
    for _, t := range sm.transitions {
        if t.From == sm.currentState && t.To == to {
            if !t.Condition(ctx) {
                return fmt.Errorf("condition not met")
            }
            if err := t.Action(ctx); err != nil {
                return err
            }
            sm.recordEvent(sm.currentState, to, "manual")
            sm.currentState = to
            return nil
        }
    }
    return fmt.Errorf("invalid transition: %d -> %d", sm.currentState, to)
}
```

---

## 三、自测题

1. **为什么需要分层状态机？**
   - 不同层级关注点不同，解耦更清晰

2. **状态转换的关键是什么？**
   - 条件判断 + 副作用处理 + 历史追踪

