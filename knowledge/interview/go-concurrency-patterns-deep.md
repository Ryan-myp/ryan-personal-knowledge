# Go并发模式 - 资深专家深度实现

## 一、Worker Pool模式

```go
package workerpool

import (
    "sync"
)

type Job struct {
    ID      int
    Data    []byte
    Result  chan []byte
}

type WorkerPool struct {
    workers int
    jobs    chan *Job
    wg      sync.WaitGroup
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    return &WorkerPool{
        workers: workers,
        jobs:    make(chan *Job, queueSize),
    }
}

func (wp *WorkerPool) Start() {
    // 启动worker
    for i := 0; i < wp.workers; i++ {
        wp.wg.Add(1)
        go wp.worker(i)
    }
}

func (wp *WorkerPool) worker(id int) {
    defer wp.wg.Done()
    for job := range wp.jobs {
        // 处理任务
        result := process(job.Data)
        job.Result <- result
    }
}

func (wp *WorkerPool) Submit(job *Job) {
    wp.jobs <- job
}

func (wp *WorkerPool) Stop() {
    close(wp.jobs)
    wp.wg.Wait()
}
```

## 二、Fan-Out/Fan-In模式

```go
package fanout

import (
    "sync"
)

func FanOut(in <-chan int, workers int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    
    // 启动多个worker
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for v := range in {
                out <- v * 2
            }
        }()
    }
    
    // 等待所有worker完成，关闭输出channel
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}

func FanIn(channels ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int)
    
    // 合并多个输入channel
    output := func(c <-chan int) {
        defer wg.Done()
        for v := range c {
            out <- v
        }
    }
    
    wg.Add(len(channels))
    for _, c := range channels {
        go output(c)
    }
    
    // 等待所有输入完成
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}
```

## 三、Context取消模式

```go
package context

import (
    "context"
    "time"
)

func WithTimeout(parent context.Context, timeout time.Duration) (context.Context, context.CancelFunc) {
    return context.WithTimeout(parent, timeout)
}

func ProcessWithTimeout(ctx context.Context, data []byte) ([]byte, error) {
    // 检查是否已取消
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }
    
    // 处理数据
    result := process(data)
    
    // 定期检查取消状态
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }
    
    return result, nil
}
```

## 四、面试高频题

### Q1: 如何避免goroutine泄漏？

```
A:
1. 确保channel能被关闭
2. 使用context控制生命周期
3. 避免无条件阻塞在channel操作
```

### Q2: Channel vs Mutex如何选择？

```
A:
• Channel: 数据传递，协程通信
• Mutex: 共享状态保护
• 原则: "不要通过共享内存来通信，要通过通信来共享内存"
```

## 五、自测题

1. 解释Worker Pool模式
2. 如何实现并发限制？
3. 如何处理goroutine panic？

---

## 参考文档

- [Go Concurrency Patterns](https://go.dev/talks/2012/concurrency.slide)
- [Effective Go](https://go.dev/doc/effective_go)
