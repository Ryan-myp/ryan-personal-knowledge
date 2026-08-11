# Go 并发模式深度解析

> 深入 Go 并发模式：Worker Pool、Fan-out/Fan-in、Pipeline、并发安全集合。
> 包含真实生产环境实现。
> 适用对象：Go 工程师、并发编程学习者

---

## 1. Worker Pool 模式

### 1.1 基础实现

```go
// worker_pool.go

package concurrent

import (
    "sync"
)

type WorkerPool struct {
    jobs    chan func()
    results chan result
    workers int
    wg      sync.WaitGroup
}

type result struct {
    value interface{}
    err   error
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    return &WorkerPool{
        jobs:    make(chan func(), queueSize),
        results: make(chan result, queueSize),
        workers: workers,
    }
}

func (p *WorkerPool) Start() {
    for i := 0; i < p.workers; i++ {
        p.wg.Add(1)
        go p.worker(i)
    }
}

func (p *WorkerPool) worker(id int) {
    defer p.wg.Done()
    for job := range p.jobs {
        result := job()
        p.results <- result{value: result}
    }
}

func (p *WorkerPool) Submit(job func() interface{}) <-chan interface{} {
    ch := make(chan interface{}, 1)
    go func() {
        p.jobs <- func() interface{} {
            return job()
        }
        <-ch
    }()
    return ch
}

func (p *WorkerPool) Wait() {
    p.wg.Wait()
    close(p.results)
}
```

### 1.2 带限流的 Worker Pool

```go
// bounded_worker_pool.go

package concurrent

import (
    "context"
    "sync"
    "sync/atomic"
)

type BoundedWorkerPool struct {
    jobs    chan func()
    sem     chan struct{}
    results chan interface{}
    workers int
    limit   int
    done    int32
}

func NewBoundedWorkerPool(workers, limit int) *BoundedWorkerPool {
    return &BoundedWorkerPool{
        jobs:    make(chan func()),
        sem:     make(chan struct{}, limit),
        results: make(chan interface{}, limit),
        workers: workers,
        limit:   limit,
    }
}

func (p *BoundedWorkerPool) Start(ctx context.Context) {
    var wg sync.WaitGroup
    for i := 0; i < p.workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for {
                select {
                case <-ctx.Done():
                    return
                case job := range p.jobs:
                    p.sem <- struct{}{}
                    result := job()
                    <-p.sem
                    p.results <- result
                }
            }
        }()
    }
    go func() {
        wg.Wait()
        close(p.results)
    }()
}
```

---

## 2. Fan-out / Fan-in 模式

### 2.1 Fan-out 实现

```go
// fanout.go

package concurrent

import "context"

func FanOut(ctx context.Context, tasks []func(context.Context) interface{}) []chan interface{} {
    channels := make([]chan interface{}, len(tasks))
    
    for i, task := range tasks {
        ch := make(chan interface{}, 1)
        go func(t func(context.Context) interface{}, c chan interface{}) {
            defer close(c)
            c <- t(ctx)
        }(task, ch)
        channels[i] = ch
    }
    
    return channels
}
```

### 2.2 Fan-in 实现

```go
// fanin.go

package concurrent

import "context"

func FanIn(ctx context.Context, channels ...<-chan interface{}) <-chan interface{} {
    out := make(chan interface{})
    
    var wg sync.WaitGroup
    for _, ch := range channels {
        wg.Add(1)
        go func(c <-chan interface{}) {
            defer wg.Done()
            for v := range c {
                select {
                case out <- v:
                case <-ctx.Done():
                    return
                }
            }
        }(ch)
    }
    
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}
```

---

## 3. Pipeline 模式

### 3.1 多级流水线

```go
// pipeline.go

package concurrent

// Stage 流水线阶段
type Stage func(<-chan int) <-chan int

// Pipeline 流水线
type Pipeline struct {
    stages []Stage
}

func NewPipeline() *Pipeline {
    return &Pipeline{}
}

func (p *Pipeline) AddStage(stage Stage) *Pipeline {
    p.stages = append(p.stages, stage)
    return p
}

func (p *Pipeline) Run(input <-chan int) <-chan int {
    out := input
    for _, stage := range p.stages {
        out = stage(out)
    }
    return out
}
```

### 3.2 实际案例

```go
// example.go

package main

import (
    "fmt"
    "concurrent"
)

func main() {
    // 生成 1-100
    numbers := make(chan int)
    go func() {
        for i := 1; i <= 100; i++ {
            numbers <- i
        }
        close(numbers)
    }()
    
    // 构建流水线
    pipeline := concurrent.NewPipeline().
        AddStage(square).      // 平方
        AddStage(filterEven).  // 过滤偶数
        AddStage(add100)       // 加 100
    
    result := pipeline.Run(numbers)
    
    // 消费结果
    for v := range result {
        fmt.Println(v)
    }
}

func square(input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for v := range input {
            out <- v * v
        }
        close(out)
    }()
    return out
}

func filterEven(input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for v := range input {
            if v%2 == 0 {
                out <- v
            }
        }
        close(out)
    }()
    return out
}

func add100(input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for v := range input {
            out <- v + 100
        }
        close(out)
    }()
    return out
}
```

---

## 4. 并发安全集合

### 4.1 并发安全 Map

```go
// safe_map.go

package concurrent

import (
    "sync"
)

type SafeMap struct {
    mu     sync.RWMutex
    data   map[string]interface{}
}

func NewSafeMap() *SafeMap {
    return &SafeMap{
        data: make(map[string]interface{}),
    }
}

func (m *SafeMap) Get(key string) (interface{}, bool) {
    m.mu.RLock()
    defer m.mu.RUnlock()
    val, ok := m.data[key]
    return val, ok
}

func (m *SafeMap) Set(key string, value interface{}) {
    m.mu.Lock()
    defer m.mu.Unlock()
    m.data[key] = value
}

func (m *SafeMap) Delete(key string) {
    m.mu.Lock()
    defer m.mu.Unlock()
    delete(m.data, key)
}

func (m *SafeMap) Len() int {
    m.mu.RLock()
    defer m.mu.RUnlock()
    return len(m.data)
}
```

### 4.2 读写锁

```go
// rw_mutex.go

package concurrent

import "sync"

type RWCache struct {
    mu    sync.RWMutex
    data  map[string]string
}

func (c *RWCache) Get(key string) (string, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    val, ok := c.data[key]
    return val, ok
}

func (c *RWCache) Set(key, value string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.data[key] = value
}
```

---

## 5. Context 控制

### 5.1 超时控制

```go
// context_timeout.go

package concurrent

import (
    "context"
    "time"
)

func WithTimeout(ctx context.Context, timeout time.Duration) (context.Context, func()) {
    return context.WithTimeout(ctx, timeout)
}

func WithCancel(ctx context.Context) (context.Context, func()) {
    return context.WithCancel(ctx)
}
```

---

## 6. 实战案例：并发任务调度器

```go
// task_scheduler.go

package concurrent

import (
    "context"
    "sync"
    "time"
)

type Task struct {
    ID       string
    Execute  func(context.Context) error
    Timeout  time.Duration
    Retry    int
}

type Scheduler struct {
    tasks    []*Task
    maxConc  int
    sem      chan struct{}
    results  chan *TaskResult
}

type TaskResult struct {
    TaskID string
    Error  error
    Duration time.Duration
}

func NewScheduler(maxConcurrency int) *Scheduler {
    return &Scheduler{
        maxConc: maxConcurrency,
        sem:     make(chan struct{}, maxConcurrency),
        results: make(chan *TaskResult),
    }
}

func (s *Scheduler) Submit(task *Task) {
    s.tasks = append(s.tasks, task)
}

func (s *Scheduler) Run(ctx context.Context) <-chan *TaskResult {
    var wg sync.WaitGroup
    
    go func() {
        for _, task := range s.tasks {
            wg.Add(1)
            s.sem <- struct{}{}
            
            go func(t *Task) {
                defer wg.Done()
                defer func() { <-s.sem }()
                
                taskCtx, cancel := context.WithTimeout(ctx, t.Timeout)
                defer cancel()
                
                start := time.Now()
                var err error
                for i := 0; i <= t.Retry; i++ {
                    err = t.Execute(taskCtx)
                    if err == nil {
                        break
                    }
                    time.Sleep(time.Duration(i+1) * 100 * time.Millisecond)
                }
                
                s.results <- &TaskResult{
                    TaskID:   t.ID,
                    Error:    err,
                    Duration: time.Since(start),
                }
            }(task)
        }
        
        wg.Wait()
        close(s.results)
    }()
    
    return s.results
}
```

---

## 7. 总结

### 7.1 核心模式回顾

| 模式 | 用途 |
|------|------|
| Worker Pool | 限制并发数，复用资源 |
| Fan-out/Fan-in | 并行执行，合并结果 |
| Pipeline | 分阶段处理数据流 |
| Context | 控制生命周期 |

### 7.2 最佳实践

- [ ] 合理设置并发度
- [ ] 使用 Context 控制超时
- [ ] 避免 goroutine 泄漏
- [ ] 使用 sync.Pool 复用对象
- [ ] 监控并发性能

---

*最后更新：2026-08-11*
*作者：Ryan*
