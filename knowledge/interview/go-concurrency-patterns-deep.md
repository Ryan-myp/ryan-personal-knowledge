# Go并发模式 - 资深专家深度实现

## 一、Worker Pool

```go
package concurrency

type WorkerPool struct {
    jobs    chan Job
    results chan Result
    workers int
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    return &WorkerPool{
        jobs:    make(chan Job, queueSize),
        results: make(chan Result, queueSize),
        workers: workers,
    }
}

func (wp *WorkerPool) Start() {
    for i := 0; i < wp.workers; i++ {
        go func(id int) {
            for job := range wp.jobs {
                result := wp.process(job)
                wp.results <- result
            }
        }(i)
    }
}

func (wp *WorkerPool) process(job Job) Result {
    // 实际处理逻辑
    return Result{
        JobID: job.ID,
        Data:  job.Data,
    }
}
```

## 二、Fan-out/Fan-in

```go
func fanOut(in <-chan int, numWorkers int) <-chan int {
    out := make(chan int)
    for i := 0; i < numWorkers; i++ {
        go func() {
            for v := range in {
                out <- v * 2
            }
        }()
    }
    return out
}

func fanIn(channels ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    
    for _, ch := range channels {
        wg.Add(1)
        go func(c <-chan int) {
            defer wg.Done()
            for v := range c {
                out <- v
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

## 三、Context传播

```go
package context

import "context"

func WithTimeout(parent context.Context, timeout time.Duration) (context.Context, context.CancelFunc)

func WithCancel(parent context.Context) (context.Context, context.CancelFunc)

func WithValue(parent context.Context, key, val any) context.Context

// 请求级上下文链
func HandleRequest(ctx context.Context, req *Request) (*Response, error) {
    // 创建子上下文
    childCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    // 传递值
    ctx = context.WithValue(childCtx, "requestID", req.ID)
    
    // 执行处理
    return process(ctx, req)
}
```

## 四、面试高频题

### Q1: Goroutine泄漏如何检测？

```
A:
1. pprof goroutine分析
2. 监控goroutine数量
3. 检查channel未关闭
```

### Q2: 如何选择缓冲/无缓冲channel？

```
A:
• 无缓冲: 同步通信，强依赖
• 有缓冲: 异步通信，流量控制
```

## 五、自测题

1. 解释Worker Pool模式
2. 如何实现Fan-out/Fan-in？
3. Context如何传播取消信号？

---

## 参考文档

- [Go并发模式官方指南](https://go.dev/doc/effective_go#concurrency)
- [Go并发编程书籍](https://github.com/golang/go/wiki/Concurrency)
