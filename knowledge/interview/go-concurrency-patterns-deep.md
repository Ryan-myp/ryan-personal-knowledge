# Go并发模式实战 - 资深专家深度实现

## 一、并发模式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Go 并发模式                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模式              | 适用场景           | 实现方式                    │
│   ──────────────────┼───────────────────┼─────────────────────────────│
│   Worker Pool       | 批量任务处理        | 固定数量worker+任务队列        │
│   Fan-Out/Fan-In    | 并行计算聚合       | 多goroutine+channel聚合       │
│   Pipeline          | 流式处理           | 多级管道+数据流动             │
│   Context           | 超时控制           | context.WithTimeout           │
│   Select            | 多路复用           | select+case                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Worker Pool实现

```go
package workerpool

import (
    "context"
    "sync"
)

// WorkerPool 工作池
type WorkerPool struct {
    jobs    chan Job
    results chan Result
    wg      sync.WaitGroup
}

type Job struct {
    ID      int
    Payload interface{}
}

type Result struct {
    JobID int
    Value interface{}
    Err   error
}

// NewWorkerPool 创建工作池
func NewWorkerPool(numWorkers int, queueSize int) *WorkerPool {
    return &WorkerPool{
        jobs:    make(chan Job, queueSize),
        results: make(chan Result, queueSize),
    }
}

// Start 启动worker
func (wp *WorkerPool) Start(ctx context.Context, numWorkers int) {
    for i := 0; i < numWorkers; i++ {
        wp.wg.Add(1)
        go func(id int) {
            defer wp.wg.Done()
            for job := range wp.jobs {
                result := wp.process(ctx, job)
                wp.results <- result
            }
        }(i)
    }
}

// process 处理任务
func (wp *WorkerPool) process(ctx context.Context, job Job) Result {
    select {
    case <-ctx.Done():
        return Result{JobID: job.ID, Err: ctx.Err()}
    default:
        // 模拟处理
        value := job.Payload.(string) + "-processed"
        return Result{JobID: job.ID, Value: value}
    }
}

// Submit 提交任务
func (wp *WorkerPool) Submit(jobs []Job) {
    for _, job := range jobs {
        wp.jobs <- job
    }
    close(wp.jobs)
}

// Results 获取结果
func (wp *WorkerPool) Results() <-chan Result {
    go func() {
        wp.wg.Wait()
        close(wp.results)
    }()
    return wp.results
}
```

## 三、面试高频题

### Q1: 如何避免Goroutine泄漏？

```
A:
1. 使用context控制退出
2. 确保channel关闭
3. 避免死锁
```

### Q2: 如何实现并行计算？

```
A:
1. Fan-Out分发任务
2. Fan-In聚合结果
3. 使用sync.WaitGroup等待
```

## 四、自测题

1. 解释Worker Pool模式
2. 如何实现Fan-Out/Fan-In？
3. 如何避免Goroutine泄漏？

---

## 参考文档

- [Go Concurrency Patterns](https://go.dev/blog/pipelines)
- [Go Wiki Concurrency](https://go.dev/wiki/ConcurrentPatterns)
