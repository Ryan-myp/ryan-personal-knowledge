# Go 并发模式深度解析

> 深入 Go 并发模式：Worker Pool、Pipeline、Fan-out/Fan-in、Context。
> 源码级分析，包含高性能并发实践。
> 适用对象：Go 工程师、后端工程师

---

## 1. Worker Pool 模式

### 1.1 基础实现

```
Worker Pool 架构：

┌─────────────────────────────────────────────────────────────┐
│                  Worker Pool 模式                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Job Queue (任务队列)                                        │
│  └── 等待处理的任务                                           │
│                                                             │
│  Worker Pool (工作池)                                        │
│  ├── Worker 1                                                │
│  ├── Worker 2                                                │
│  ├── Worker 3                                                │
│  └── ... (N 个 Worker)                                      │
│                                                             │
│  Result Channel (结果通道)                                    │
│  └── 处理结果                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现

```go
// worker_pool.go

package concurrency

import (
    "context"
    "sync"
)

type Job struct {
    ID      int
    Data    []byte
    Result  chan<- int
}

type WorkerPool struct {
    numWorkers int
    jobs       chan Job
    results    chan int
}

func NewWorkerPool(numWorkers, queueSize int) *WorkerPool {
    return &WorkerPool{
        numWorkers: numWorkers,
        jobs:       make(chan Job, queueSize),
        results:    make(chan int, queueSize),
    }
}

func (wp *WorkerPool) Start(ctx context.Context) {
    var wg sync.WaitGroup
    
    // 启动 Worker
    for i := 0; i < wp.numWorkers; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            wp.worker(ctx, id)
        }(i)
    }
    
    // 等待完成
    go func() {
        wg.Wait()
        close(wp.results)
    }()
}

func (wp *WorkerPool) worker(ctx context.Context, id int) {
    for {
        select {
        case <-ctx.Done():
            return
        case job, ok := <-wp.jobs:
            if !ok {
                return
            }
            result := wp.process(job)
            if job.Result != nil {
                job.Result <- result
            }
        }
    }
}

func (wp *WorkerPool) process(job Job) int {
    // 模拟处理
    return len(job.Data) * 2
}
```

---

## 2. Pipeline 模式

### 2.1 三阶段流水线

```
Pipeline 架构：

Producer → [Stage 1] → [Stage 2] → [Stage 3] → Consumer

┌─────────────────────────────────────────────────────────────┐
│                    Pipeline 模式                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stage 1: 数据清洗                                            │
│  └── 过滤无效数据，格式化                                      │
│                                                             │
│  Stage 2: 数据处理                                            │
│  └── 业务逻辑处理                                              │
│                                                             │
│  Stage 3: 结果聚合                                             │
│  └── 汇总统计，生成报告                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
// pipeline.go

package concurrency

type Pipeline struct {
    stages []func(<-chan int) <-chan int
}

func NewPipeline(stages ...func(<-chan int) <-chan int) *Pipeline {
    return &Pipeline{stages: stages}
}

func (p *Pipeline) Run(input <-chan int) <-chan int {
    out := input
    for _, stage := range p.stages {
        out = stage(out)
    }
    return out
}

// 示例：清洗阶段
func cleanStage(input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for v := range input {
            if v > 0 {  // 过滤负数
                out <- v
            }
        }
    }()
    return out
}

// 示例：处理阶段
func processStage(input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for v := range input {
            out <- v * 2  // 简单处理
        }
    }()
    return out
}
```

---

## 3. Fan-out / Fan-in 模式

### 3.1 模式说明

```
Fan-out / Fan-in 模式：

Fan-out:
  ┌─────┐
  │ Main │ ──► [Task 1]
  └─────┘ ──► [Task 2]
          ──► [Task 3]
          ──► [Task N]

Fan-in:
  [Task 1] ──┐
  [Task 2] ──┼──► [Main]
  [Task 3] ──┤
  [Task N] ──┘
```

### 3.2 Go 实现

```go
// fanout_fanin.go

package concurrency

import (
    "context"
    "sync"
)

func FanOut(ctx context.Context, tasks []func(context.Context) ([]int, error)) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    
    for _, task := range tasks {
        wg.Add(1)
        go func(t func(context.Context) ([]int, error)) {
            defer wg.Done()
            results, err := t(ctx)
            if err != nil {
                return
            }
            for _, r := range results {
                select {
                case out <- r:
                case <-ctx.Done():
                    return
                }
            }
        }(task)
    }
    
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}

func FanIn(ctx context.Context, channels ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int)
    
    output := func(c <-chan int) {
        defer wg.Done()
        for v := range c {
            select {
            case out <- v:
            case <-ctx.Done():
                return
            }
        }
    }
    
    wg.Add(len(channels))
    for _, c := range channels {
        go output(c)
    }
    
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}
```

---

## 4. Context 模式

### 4.1 Context 树

```
Context 树结构：

ctx (root)
├── child1 (带超时)
│   ├── child1_1
│   └── child1_2
└── child2 (带值)
    ├── child2_1
    └── child2_2

规则：
├── 父 Context 取消 → 所有子 Context 取消
├── 子 Context 不能影响父 Context
└── 值继承，不覆盖
```

### 4.2 Go 实现

```go
// context_pattern.go

package concurrency

import (
    "context"
    "time"
)

func WithTimeoutContext(ctx context.Context, timeout time.Duration) (context.Context, context.CancelFunc) {
    return context.WithTimeout(ctx, timeout)
}

func WithValueContext(ctx context.Context, key, val interface{}) context.Context {
    return context.WithValue(ctx, key, val)
}

func WithCancelContext(ctx context.Context) (context.Context, context.CancelFunc) {
    return context.WithCancel(ctx)
}

// 使用示例
func ProcessWithTimeout(ctx context.Context, data []byte) ([]byte, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    // 带取消的检查
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }
    
    // 业务处理
    return data, nil
}
```

---

## 5. 同步原语

### 5.1 WaitGroup

```go
// waitgroup_pattern.go

package concurrency

import (
    "sync"
)

func UseWaitGroup() {
    var wg sync.WaitGroup
    results := make([]int, 0, 10)
    
    for i := 0; i < 10; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            results = append(results, id*2)
        }(i)
    }
    
    wg.Wait()
    _ = results
}
```

### 5.2 Once

```go
// once_pattern.go

package concurrency

import (
    "sync"
)

func UseOnce() {
    var once sync.Once
    var data string
    
    init := func() {
        data = "initialized"
    }
    
    // 多个 goroutine 安全初始化
    for i := 0; i < 10; i++ {
        go func() {
            once.Do(init)
        }()
    }
    
    _ = data
}
```

### 5.3 Mutex

```go
// mutex_pattern.go

package concurrency

import (
    "sync"
)

func UseMutex() {
    var mu sync.Mutex
    counter := 0
    
    for i := 0; i < 100; i++ {
        go func() {
            mu.Lock()
            counter++
            mu.Unlock()
        }()
    }
    
    // 等待完成
    time.Sleep(100 * time.Millisecond)
    _ = counter
}
```

---

## 6. 性能优化

### 6.1 避免常见陷阱

```
并发陷阱及解决方案：

1. 数据竞争 (Data Race)
   └── 使用 sync.Mutex 或 channel

2. Goroutine 泄漏
   └── 确保所有 goroutine 能退出

3. 死锁 (Deadlock)
   └── 固定加锁顺序

4. 上下文泄漏
   └── 及时取消 context

5. 缓冲通道溢出
   └── 合理设置缓冲大小
```

### 6.2 最佳实践

```go
// best_practices.go

package concurrency

import (
    "context"
    "sync"
)

// 1. 总是传递 Context
func ProcessWithContext(ctx context.Context, data []byte) ([]byte, error) {
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }
    // 处理逻辑
    return data, nil
}

// 2. 使用 Done channel
func ProcessWithDone(ctx context.Context) <-chan struct{} {
    done := make(chan struct{})
    go func() {
        defer close(done)
        // 处理逻辑
    }()
    return done
}

// 3. 限制并发度
func LimitedConcurrency(ctx context.Context, jobs []Job, limit int) {
    var wg sync.WaitGroup
    sem := make(chan struct{}, limit)
    
    for _, job := range jobs {
        wg.Add(1)
        sem <- struct{}{}
        go func(j Job) {
            defer wg.Done()
            defer func() { <-sem }()
            // 处理 job
        }(job)
    }
    wg.Wait()
}
```

---

## 7. 总结

### 7.1 核心模式回顾

| 模式 | 适用场景 | 关键机制 |
|------|----------|----------|
| Worker Pool | 任务处理 | 固定数量 Worker |
| Pipeline | 数据流处理 | 多阶段处理 |
| Fan-out/Fan-in | 并行计算 | 多路复用 |
| Context | 生命周期管理 | 树形传播 |

### 7.2 最佳实践

- [ ] 合理选择并发模式
- [ ] 使用 Context 管理生命周期
- [ ] 避免 Goroutine 泄漏
- [ ] 限制并发度
- [ ] 建立监控告警

---

*最后更新：2026-08-11*
*作者：Ryan*
