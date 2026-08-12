# Multi-Agent 协作模式深度实现

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 28%

---

## 一、协作模式总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Multi-Agent 协作模式                               │
│                                                                     │
│  1. Manager-Worker          2. MapReduce                            │
│     ┌──────┐                 ┌──────┐                              │
│     │ Manager│ ──任务分发──▶ │Worker1│                             │
│     │       │ ──结果收集──◀ │Worker2│                             │
│     └──────┘                 └──────┘                              │
│                                                                     │
│  3. Pipeline            4. Debate                                  │
│     ┌───┐  ┌───┐  ┌───┐          ┌──────┐     ┌──────┐           │
│     │A  │──▶│B  │──▶│C  │          │Agent1│ ──争论──▶│Agent2│           │
│     └───┘  └───┘  └───┘          └──────┘     └──────┘           │
│                                                                     │
│  5. Fan-Out/Fan-In    6. Hierarchical                              │
│     ┌──────┐                    ┌──────┐                          │
│     │ Input│──┬──▶┬──▶┬──▶ Output │    │ Supervisor               │
│     └──────┘  │  │  │             └──────┘     │                   │
│              ┌▼──▼──▼┐                       ┌─▼──▼──▼┐            │
│              │Workers │                       │ SubAgents │            │
│              └────────┘                       └─────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Manager-Worker 模式实现

```go
// agent/manager_worker.go
package agent

import (
    "context"
    "sync"
)

// Task 任务定义
type Task struct {
    ID        string
    Input     string
    WorkerID  string
}

// Result 结果定义
type Result struct {
    TaskID   string
    Output   string
    Error    error
}

// Manager 管理器
type Manager struct {
    workers  map[string]Worker
    taskCh   chan Task
    resultCh chan Result
}

// Worker 工作者接口
type Worker interface {
    Process(ctx context.Context, input string) (string, error)
}

// NewManager 创建管理器
func NewManager(workers map[string]Worker) *Manager {
    return &Manager{
        workers:  workers,
        taskCh:   make(chan Task, 100),
        resultCh: make(chan Result, 100),
    }
}

// Execute 执行任务
func (m *Manager) Execute(ctx context.Context, tasks []Task) ([]Result, error) {
    var wg sync.WaitGroup
    results := make([]Result, len(tasks))
    
    // 启动 worker goroutines
    for id, worker := range m.workers {
        wg.Add(1)
        go func(workerID string, w Worker) {
            defer wg.Done()
            for task := range m.taskCh {
                output, err := w.Process(ctx, task.Input)
                m.resultCh <- Result{
                    TaskID: task.ID,
                    Output: output,
                    Error:  err,
                }
            }
        }(id, worker)
    }
    
    // 分发任务
    go func() {
        for i, task := range tasks {
            task.WorkerID = m.selectWorker(task)
            m.taskCh <- task
            results[i] = <-m.resultCh // 等待结果
        }
        close(m.taskCh)
    }()
    
    wg.Wait()
    close(m.resultCh)
    
    return results, nil
}

// selectWorker 选择 worker (轮询)
func (m *Manager) selectWorker(task Task) string {
    // 简单轮询
    ids := make([]string, 0, len(m.workers))
    for id := range m.workers {
        ids = append(ids, id)
    }
    return ids[task.ID%len(ids)]
}
```

---

## 三、Pipeline 模式实现

```go
// agent/pipeline.go
package agent

import "context"

// Stage 处理阶段
type Stage struct {
    Name     string
    Process  func(ctx context.Context, input string) (string, error)
}

// Pipeline 流水线
type Pipeline struct {
    stages []Stage
}

// NewPipeline 创建流水线
func NewPipeline(stages ...Stage) *Pipeline {
    return &Pipeline{stages: stages}
}

// Execute 执行流水线
func (p *Pipeline) Execute(ctx context.Context, input string) (string, error) {
    current := input
    for _, stage := range p.stages {
        select {
        case <-ctx.Done():
            return "", ctx.Err()
        default:
        }
        
        var err error
        current, err = stage.Process(ctx, current)
        if err != nil {
            return "", err
        }
    }
    return current, nil
}

// 示例：代码审查流水线
func examplePipeline() {
    pipeline := NewPipeline(
        Stage{
            Name: "lint",
            Process: func(ctx context.Context, code string) (string, error) {
                // Lint 检查
                return lint(code), nil
            },
        },
        Stage{
            Name: "format",
            Process: func(ctx context.Context, code string) (string, error) {
                // 格式化处理
                return format(code), nil
            },
        },
        Stage{
            Name: "review",
            Process: func(ctx context.Context, code string) (string, error) {
                // AI 代码审查
                return aiReview(code), nil
            },
        },
    )
    
    result, err := pipeline.Execute(context.Background(), sourceCode)
}
```

---

## 四、MapReduce 模式实现

```go
// agent/map_reduce.go
package agent

import (
    "context"
    "sync"
)

// MapReduce 映射归约
type MapReduce struct {
    mapper   func(ctx context.Context, input string) []string
    reducer  func(ctx context.Context, parts []string) string
    workers  int
}

// NewMapReduce 创建 MapReduce
func NewMapReduce(mapper func(ctx context.Context, input string) []string,
                  reducer func(ctx context.Context, parts []string) string,
                  workers int) *MapReduce {
    return &MapReduce{
        mapper:  mapper,
        reducer: reducer,
        workers: workers,
    }
}

// Execute 执行 MapReduce
func (mr *MapReduce) Execute(ctx context.Context, input string) (string, error) {
    // Map 阶段
    partsChan := make(chan []string, mr.workers)
    var mapWg sync.WaitGroup
    
    for i := 0; i < mr.workers; i++ {
        mapWg.Add(1)
        go func() {
            defer mapWg.Done()
            parts := mr.mapper(ctx, input)
            partsChan <- parts
        }()
    }
    
    go func() {
        mapWg.Wait()
        close(partsChan)
    }()
    
    // 合并 map 结果
    var allParts []string
    for parts := range partsChan {
        allParts = append(allParts, parts...)
    }
    
    // Reduce 阶段
    return mr.reducer(ctx, allParts), nil
}
```

---

## 五、Debate 辩论模式

```go
// agent/debate.go
package agent

import "context"

// Debater 辩论者
type Debater struct {
    ID       string
    Position string // "pro" or "con"
    LLM      LLMClient
}

// Debate 辩论流程
type Debate struct {
    topic    string
    agents   []*Debater
    rounds   int
}

// NewDebate 创建辩论
func NewDebate(topic string, agents []*Debater, rounds int) *Debate {
    return &Debate{
        topic:  topic,
        agents: agents,
        rounds: rounds,
    }
}

// Execute 执行辩论
func (d *Debate) Execute(ctx context.Context) (string, error) {
    arguments := make(map[string][]string)
    
    for round := 0; round < d.rounds; round++ {
        for _, agent := range d.agents {
            // 收集对方观点
            opponentArgs := d.getOpponentArguments(agent, arguments)
            
            // 生成反驳
            response, err := agent.LLM.Generate(ctx, buildDebatePrompt(
                d.topic, opponentArgs, agent.Position,
            ))
            if err != nil {
                return "", err
            }
            
            arguments[agent.ID] = append(arguments[agent.ID], response)
        }
    }
    
    // 总结
    return d.summarize(ctx, arguments)
}

func (d *Debate) getOpponentArguments(agent *Debater, args map[string][]string) []string {
    var opponentArgs []string
    for id, argList := range args {
        if id != agent.ID {
            opponentArgs = append(opponentArgs, argList...)
        }
    }
    return opponentArgs
}
```

---

## 六、模式选择指南

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 任务独立 | MapReduce | 并行度高 |
| 任务依赖 | Pipeline | 顺序执行 |
| 需要协调 | Manager-Worker | 集中控制 |
| 需要创新 | Debate | 多角度思考 |
| 结果验证 | Fan-Out/Fan-In | 多路验证 |

---

## 七、自测题

1. **Manager-Worker 模式的瓶颈是什么？**
   - Manager 单点、结果收集延迟

2. **Pipeline 如何实现错误恢复？**
   - 重试机制 + 降级策略

3. **Debate 模式何时适用？**
   - 需要多角度分析、决策质量高于速度

