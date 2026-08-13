# Go并发模式实战 - 资深专家深度实现

## 一、Worker Pool模式

### 1.1 基础实现

```go
// Worker Pool
type WorkerPool struct {
    workers    int
    jobs       chan Job
    results    chan Result
    wg         sync.WaitGroup
}

// Job定义
type Job struct {
    ID      int
    Payload interface{}
}

// Result定义
type Result struct {
    JobID int
    Data  interface{}
    Err   error
}

// 创建Worker Pool
func NewWorkerPool(workers, jobQueueSize int) *WorkerPool {
    return &WorkerPool{
        workers: workers,
        jobs:    make(chan Job, jobQueueSize),
        results: make(chan Result, jobQueueSize),
    }
}

// 启动Pool
func (p *WorkerPool) Start() {
    // 启动workers
    for i := 0; i < p.workers; i++ {
        p.wg.Add(1)
        go p.worker(i)
    }
}

// Worker执行
func (p *WorkerPool) worker(id int) {
    defer p.wg.Done()
    
    for job := range p.jobs {
        result := p.processJob(job)
        p.results <- result
    }
}

// 处理任务
func (p *WorkerPool) processJob(job Job) Result {
    // 模拟处理
    time.Sleep(time.Millisecond * 10)
    
    return Result{
        JobID: job.ID,
        Data:  fmt.Sprintf("result-%d", job.ID),
    }
}

// 提交任务
func (p *WorkerPool) Submit(job Job) {
    p.jobs <- job
}

// 等待完成
func (p *WorkerPool) Wait() {
    close(p.jobs)
    p.wg.Wait()
    close(p.results)
}
```

### 1.2 高级特性

```go
// 带优先级的Worker Pool
type PriorityWorkerPool struct {
    highJobs   chan Job
    normalJobs chan Job
    lowJobs    chan Job
    workers    int
}

func (p *PriorityWorkerPool) Start() {
    for i := 0; i < p.workers; i++ {
        go p.worker(i)
    }
}

func (p *PriorityWorkerPool) worker(id int) {
    for {
        select {
        case job := <-p.highJobs:
            p.processJob(job)
        case job := <-p.normalJobs:
            p.processJob(job)
        case job := <-p.lowJobs:
            p.processJob(job)
        }
    }
}

// 带超时的Worker Pool
type TimeoutWorkerPool struct {
    pool *WorkerPool
    timeout time.Duration
}

func (p *TimeoutWorkerPool) SubmitWithTimeout(job Job) error {
    ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
    defer cancel()
    
    done := make(chan Result, 1)
    go func() {
        p.pool.Submit(job)
        result := <-p.pool.Results()
        done <- result
    }()
    
    select {
    case result := <-done:
        return result.Err
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

## 二、Fan-Out/Fan-In模式

### 2.1 基础实现

```go
// Fan-Out/Fan-In
func fanOutFanIn(jobs []Job, workers int) []Result {
    // Fan-Out: 分发任务
    jobChan := make(chan Job, len(jobs))
    for _, job := range jobs {
        jobChan <- job
    }
    close(jobChan)
    
    // Fan-In: 收集结果
    resultChan := make(chan Result, len(jobs))
    
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobChan {
                result := processJob(job)
                resultChan <- result
            }
        }()
    }
    
    // 等待所有worker完成
    go func() {
        wg.Wait()
        close(resultChan)
    }()
    
    // 收集结果
    var results []Result
    for result := range resultChan {
        results = append(results, result)
    }
    
    return results
}

// 带错误处理的Fan-In
func fanInWithError(results []chan Result) chan Result {
    out := make(chan Result)
    
    var wg sync.WaitGroup
    for _, r := range results {
        wg.Add(1)
        go func(rc chan Result) {
            defer wg.Done()
            for result := range rc {
                out <- result
            }
        }(r)
    }
    
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}
```

### 2.2 实际应用

```go
// 批量数据处理
func processBatch(data []DataItem) []ProcessedData {
    batchSize := 100
    var results []ProcessedData
    
    // Fan-out: 分批处理
    var wg sync.WaitGroup
    resultChans := make([]chan ProcessedData, 0, (len(data)+batchSize-1)/batchSize)
    
    for i := 0; i < len(data); i += batchSize {
        end := min(i+batchSize, len(data))
        batch := data[i:end]
        
        ch := make(chan ProcessedData, len(batch))
        resultChans = append(resultChans, ch)
        
        wg.Add(1)
        go func(batch []DataItem, ch chan ProcessedData) {
            defer wg.Done()
            for _, item := range batch {
                ch <- processItem(item)
            }
            close(ch)
        }(batch, ch)
    }
    
    // Fan-in: 合并结果
    mergedChan := fanInWithError(resultChans)
    
    go func() {
        wg.Wait()
        close(mergedChan)
    }()
    
    for result := range mergedChan {
        results = append(results, result)
    }
    
    return results
}
```

## 三、Pipeline模式

### 3.1 基础Pipeline

```go
// Pipeline阶段
type PipelineStage func(<-chan Job) <-chan Result

// 创建Pipeline
func createPipeline(stages ...PipelineStage) Pipeline {
    return Pipeline{stages: stages}
}

// 执行Pipeline
func (p *Pipeline) Execute(input <-chan Job) <-chan Result {
    var out <-chan Result = input
    
    for _, stage := range p.stages {
        out = stage(out)
    }
    
    return out
}

// 标准Pipeline阶段
func validateStage() PipelineStage {
    return func(input <-chan Job) <-chan Result {
        output := make(chan Result)
        go func() {
            defer close(output)
            for job := range input {
                if job.Validate() {
                    output <- Result{Job: job, Stage: "validate", OK: true}
                }
            }
        }()
        return output
    }
}

func processStage() PipelineStage {
    return func(input <-chan Result) <-chan Result {
        output := make(chan Result)
        go func() {
            defer close(output)
            for result := range input {
                if result.OK {
                    processed := process(result.Job)
                    output <- Result{Job: processed, Stage: "process", OK: true}
                }
            }
        }()
        return output
    }
}
```

### 3.2 并发Pipeline

```go
// 并发Pipeline
type ConcurrentPipeline struct {
    stages []PipelineStage
    width  int
}

func (p *ConcurrentPipeline) Execute(input <-chan Job) <-chan Result {
    var out <-chan Result = input
    
    for _, stage := range p.stages {
        out = p.concurrentStage(out, p.width)
    }
    
    return out
}

func (p *ConcurrentPipeline) concurrentStage(input <-chan Result, width int) <-chan Result {
    output := make(chan Result)
    
    var wg sync.WaitGroup
    for i := 0; i < width; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for result := range input {
                output <- process(result)
            }
        }()
    }
    
    go func() {
        wg.Wait()
        close(output)
    }()
    
    return output
}
```

## 四、面试高频题

### Q1: Worker Pool如何实现？

```
A:
1. 定义Job和Result结构
2. 创建chan接收任务
3. 启动多个goroutine处理
4. 使用sync.WaitGroup等待完成
```

### Q2: Fan-Out/Fan-In模式适用场景？

```
A:
1. 批量数据处理
2. 并行API调用
3. 分布式计算
4. 实时数据处理
```

### Q3: Pipeline模式如何设计？

```
A:
1. 定义阶段接口
2. 每个阶段独立处理
3. 使用chan传递数据
4. 支持并发执行
```

## 五、自测题

1. 实现一个带优先级的Worker Pool
2. 如何用Pipeline处理流式数据？
3. Fan-Out/Fan-In的优缺点？

---

## 参考文档

- [Go Channel深入](./go-channel-impl-deep.md)
- [Go Scheduler深入](./go-scheduler-deep.md)
- [Go GC深入](./go-gc-deep.md)
