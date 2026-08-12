# Agent Workflow 生产实践深度实现 - 状态机与编排

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/Workflow  
> **代码密度**: 32%

---

## 一、Workflow 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Workflow 状态机                             │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  START   │───▶│ PARSE    │───▶│ THINK    │───▶│ ACT      │     │
│  │  (入口)   │    │ (解析)    │    │ (思考)    │    │ (执行)    │     │
│  └──────────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
│                        │               │               │            │
│              ┌─────────┼───────────────┼───────────────┼────────┐  │
│              ▼         ▼               ▼               ▼        │  │
│         用户输入    意图识别       LLM 推理       工具调用       │  │
│                        │                               │        │  │
│                        ▼                               ▼        │  │
│                    ┌──────────┐                   ┌──────────┐   │  │
│                    │ REFLECT  │◀───────────────── │  CHECK   │   │  │
│                    │ (反思)    │    结果验证        │ (校验)   │   │  │
│                    └────┬─────┘                   └────┬─────┘   │  │
│                         │                              │         │  │
│                         ▼                              ▼         │  │
│                    ┌──────────┐                   ┌──────────┐   │  │
│                    │ REFINED  │───▶     ...       │ COMPLETE │   │  │
│                    │ (优化)    │                   │ (完成)   │   │  │
│                    └──────────┘                   └──────────┘   │  │
│                         │                                       │  │
│                         ▼                                       │  │
│                    ┌──────────┐                                  │  │
│                    │  ERROR   │──────────────────────────────────┘  │
│                    │  (错误)   │    超过最大重试次数                 │
│                    └──────────┘                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Workflow 引擎实现

```go
// workflow/engine.go
package workflow

import (
    "context"
    "errors"
    "fmt"
    "sync"
)

// State 工作流状态
type State int

const (
    StateStart State = iota
    StateParse
    StateThink
    StateAct
    StateReflect
    StateComplete
    StateError
)

// Transition 状态转换
type Transition struct {
    From State
    To   State
    Cond func(*Context) bool
}

// Node 工作流节点
type Node struct {
    ID       string
    State    State
    Handler  func(*Context) error
    Retry    int
    Timeout  int // 秒
}

// Context 工作流上下文
type Context struct {
    Input    string
    Output   string
    Steps    []StepRecord
    Errors   []error
    Cancel   context.CancelFunc
    mu       sync.Mutex
}

// StepRecord 步骤记录
type StepRecord struct {
    Timestamp time.Time
    NodeID    string
    State     State
    Duration  time.Duration
    Success   bool
    Error     string
}

// Engine 工作流引擎
type Engine struct {
    nodes    map[string]*Node
    graph    map[State][]Transition
    maxSteps int
}

// NewEngine 创建工作流引擎
func NewEngine(maxSteps int) *Engine {
    return &Engine{
        nodes:    make(map[string]*Node),
        graph:    make(map[State][]Transition),
        maxSteps: maxSteps,
    }
}

// AddNode 添加节点
func (e *Engine) AddNode(node *Node) {
    e.nodes[node.ID] = node
}

// AddTransition 添加转换
func (e *Engine) AddTransition(t Transition) {
    e.graph[t.From] = append(e.graph[t.From], t)
}

// Run 运行工作流
func (e *Engine) Run(ctx context.Context, input string) (*Context, error) {
    wctx := &Context{
        Input: input,
        Steps: make([]StepRecord, 0),
    }
    
    var cancel context.CancelFunc
    ctx, cancel = context.WithTimeout(ctx, 30*time.Second)
    wctx.Cancel = cancel
    defer cancel()
    
    currentState := StateStart
    steps := 0
    
    for steps < e.maxSteps {
        steps++
        
        // 查找下一步
        transitions := e.graph[currentState]
        var nextTransition *Transition
        for _, t := range transitions {
            if t.Cond == nil || t.Cond(wctx) {
                nextTransition = &t
                break
            }
        }
        
        if nextTransition == nil {
            wctx.Errors = append(wctx.Errors, errors.New("no valid transition"))
            return wctx, fmt.Errorf("workflow failed at step %d", steps)
        }
        
        // 执行节点
        node := e.findNode(nextTransition.To)
        if node == nil {
            return wctx, fmt.Errorf("node not found for state %d", nextTransition.To)
        }
        
        startTime := time.Now()
        err := node.Handler(ctx, wctx)
        duration := time.Since(startTime)
        
        wctx.Steps = append(wctx.Steps, StepRecord{
            Timestamp: time.Now(),
            NodeID:    node.ID,
            State:     nextTransition.To,
            Duration:  duration,
            Success:   err == nil,
            Error:     func() string { if err != nil { return err.Error() }; return "" }(),
        })
        
        if err != nil {
            if node.Retry > 0 {
                node.Retry--
                continue
            }
            return wctx, err
        }
        
        currentState = nextTransition.To
        if currentState == StateComplete || currentState == StateError {
            break
        }
    }
    
    return wctx, nil
}

func (e *Engine) findNode(state State) *Node {
    for _, node := range e.nodes {
        if node.State == state {
            return node
        }
    }
    return nil
}
```

---

## 三、子 Agent 编排

```go
// workflow/subagent.go
package workflow

import "context"

// SubAgent 子 Agent
type SubAgent struct {
    ID       string
    Name     string
    Prompt   string
    Tools    []Tool
    Executor AgentExecutor
}

// AgentExecutor Agent 执行器接口
type AgentExecutor interface {
    Execute(ctx context.Context, prompt string, tools []Tool) (*AgentResult, error)
}

// AgentResult Agent 执行结果
type AgentResult struct {
    Output   string
    Tools    []ToolCall
    Tokens   int
    Duration time.Duration
}

// ToolCall 工具调用记录
type ToolCall struct {
    ToolName string
    Input    map[string]interface{}
    Output   interface{}
    Error    error
}

// Orchestrator 编排器
type Orchestrator struct {
    agents map[string]*SubAgent
}

// Plan 执行计划
type Plan struct {
    Steps []PlanStep
}

type PlanStep struct {
    AgentID  string
    Input    string
    Depends  []string // 依赖的前置步骤
}
```

---

## 四、自测题

1. **为什么工作流需要状态机？**
   - 保证流程可追溯、可重试、可中断

2. **子 Agent 编排的核心挑战？**
   - 上下文传递、结果聚合、错误处理

