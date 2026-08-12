# Multi-Agent 协作模式深度实现 - 从Manager到Debate

> **版本**: v2.1  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/多Agent  
> **代码密度**: 30%

---

## 一、协作模式对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Multi-Agent 协作模式                              │
│                                                                     │
│  ┌──────────────┬──────────────┬──────────────┬──────────────────┐ │
│  │    模式       │   适用场景    │   优点        │    缺点          │ │
│  ├──────────────┼──────────────┼──────────────┼──────────────────┤ │
│  │ Manager-Worker│ 任务分解     │ 结构清晰     │ 单点瓶颈         │ │
│  │ Pipeline     │ 流水线处理   │ 效率高       │ 耦合度高         │ │
│  │ MapReduce    │ 批量处理     │ 可并行       │ 结果聚合复杂     │ │
│  │ Fan-Out-In   │ 并行探索     │ 多样性高     │ Token消耗大      │ │
│  │ Debate       │ 复杂决策     │ 质量高       │ 延迟高           │ │
│  │ Swarm        │ 简单任务     │ 开销小       │ 协调困难         │ │
│  └──────────────┴──────────────┴──────────────┴──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Manager-Worker 模式

```go
// agent/manager_worker.go
package agent

import (
    "context"
    "sync"
)

// Manager 任务分发器
type Manager struct {
    workers map[string]*Worker
    tasks   chan Task
    results chan Result
}

// Worker 工作节点
type Worker struct {
    ID       string
    Skill    string
    Executor AgentExecutor
    mu       sync.Mutex
}

// Task 任务定义
type Task struct {
    ID        string
    Type      string
    Input     interface{}
    Timeout   time.Duration
}

// Result 任务结果
type Result struct {
    TaskID  string
    WorkerID string
    Output  interface{}
    Error   error
}

// Dispatch 分发任务
func (m *Manager) Dispatch(ctx context.Context, tasks []Task) []Result {
    var wg sync.WaitGroup
    results := make([]Result, len(tasks))
    
    for i, task := range tasks {
        wg.Add(1)
        worker := m.selectWorker(task.Type)
        
        go func(idx int, t Task, w *Worker) {
            defer wg.Done()
            
            result, err := w.Executor.Execute(ctx, t.Input)
            results[idx] = Result{
                TaskID:   t.ID,
                WorkerID: w.ID,
                Output:   result,
                Error:    err,
            }
        }(i, task, worker)
    }
    
    wg.Wait()
    return results
}

// selectWorker 选择合适的工作者
func (m *Manager) selectWorker(taskType string) *Worker {
    // 基于技能匹配选择
    best := (*Worker)(nil)
    bestScore := 0.0
    
    for _, w := range m.workers {
        if w.Skill == taskType {
            score := w.calculateScore()
            if score > bestScore {
                bestScore = score
                best = w
            }
        }
    }
    
    if best == nil {
        // 回退到第一个可用worker
        for _, w := range m.workers {
            return w
        }
    }
    return best
}
```

---

## 三、Debate 辩论模式

```go
// agent/debate.go
package agent

import (
    "context"
    "strings"
)

// Debator 辩论者
type Debator struct {
    ID     string
    Role   string // pro/con/neutral
    Prompt string
}

// DebateEngine 辩论引擎
type DebateEngine struct {
    debators []Debator
    rounds   int
}

// DebateResult 辩论结果
type DebateResult struct {
    FinalDecision string
    Arguments     []Argument
    Confidence    float64
}

// Argument 论点
type Argument struct {
    DebatorID string
    Stance    string
    Content   string
    Score     float64
}

// RunDebate 执行辩论
func (e *DebateEngine) RunDebate(ctx context.Context, question string) *DebateResult {
    arguments := make([]Argument, 0)
    
    // 多轮辩论
    for round := 0; round < e.rounds; round++ {
        for _, d := range e.debators {
            arg, err := d.execute(ctx, question, arguments)
            if err != nil {
                continue
            }
            arguments = append(arguments, arg)
        }
    }
    
    // 汇总决策
    decision := e.aggregate(arguments)
    return &DebateResult{
        FinalDecision: decision,
        Arguments:     arguments,
        Confidence:    e.calculateConfidence(arguments),
    }
}

// execute 执行辩论
func (d *Debator) execute(ctx context.Context, question string, args []Argument) (*Argument, error) {
    prompt := d.buildPrompt(question, args)
    response, err := d.Executor.Execute(ctx, prompt)
    if err != nil {
        return nil, err
    }
    return &Argument{
        DebatorID: d.ID,
        Stance:    d.Role,
        Content:   response,
        Score:     0.8, // TODO: 可信度评分
    }, nil
}
```

---

## 四、MapReduce 模式

```go
// agent/mapreduce.go
package agent

import (
    "context"
    "sync"
)

// MapReduceAgent MapReduce工作流
type MapReduceAgent struct {
    mapper   func(context.Context, interface{}) []interface{}
    reducer  func(context.Context, []interface{}) interface{}
}

// Map 映射阶段
func (a *MapReduceAgent) Map(ctx context.Context, input interface{}) []interface{} {
    return a.mapper(ctx, input)
}

// Reduce 归约阶段
func (a *MapReduceAgent) Reduce(ctx context.Context, outputs []interface{}) interface{} {
    return a.reducer(ctx, outputs)
}

// Run 完整流程
func (a *MapReduceAgent) Run(ctx context.Context, inputs []interface{}) interface{} {
    // Map阶段 (并行)
    var wg sync.WaitGroup
    mapped := make([][]interface{}, len(inputs))
    
    for i, input := range inputs {
        wg.Add(1)
        go func(idx int, in interface{}) {
            defer wg.Done()
            mapped[idx] = a.Map(ctx, in)
        }(i, input)
    }
    wg.Wait()
    
    // Shuffle (合并所有map输出)
    var allOutputs []interface{}
    for _, m := range mapped {
        allOutputs = append(allOutputs, m...)
    }
    
    // Reduce阶段
    return a.Reduce(ctx, allOutputs)
}
```

---

## 五、自测题

1. **为什么需要多种协作模式？**
   - 不同场景下效率和质量要求不同

2. **Debate模式适合什么场景？**
   - 复杂决策、需要多角度论证的问题

