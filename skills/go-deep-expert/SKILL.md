---
name: go-deep-expert
description: "Go 语言专家技能 — GMP 调度器、GC、网络轮询器、内存分配器源码级深入"
version: 1.0.0
author: ryan
tags: [go, performance, runtime, concurrency, expert]
---

# Go 语言专家技能

> 从 runtime 源码到生产调优，掌握 Go 语言底层原理

## 核心能力

### 1. GMP 调度器
- **G (Goroutine)**：调度单元，包含栈、状态、等待队列
- **M (Machine)**：OS 线程，执行 G 的实际载体
- **P (Processor)**：逻辑处理器，维护 local queue 和 global queue
- **工作窃取 (Work Stealing)**：P 之间平衡负载

### 2. 垃圾回收 (GC)
- **三色标记法**：白/灰/黑三色标记算法
- **混合屏障**：写屏障 + 读屏障
- **GC 触发条件**：内存增长率、时间间隔
- **GC 调优**：GOGC、GOMAXPROCS、gc CPU 占比

### 3. 网络轮询器 (Netpoller)
- **epoll/kqueue**：I/O 多路复用
- **Event Poller**：后台线程监听事件
- **G 阻塞与唤醒**：netpollblock / netpollgready

### 4. 内存分配器
- **mcache**：每 P 私有缓存，避免锁竞争
- **mcentral**：中等大小对象管理
- **mspan**：内存块管理单元
- **tcmalloc 风格**：size class 分级管理

### 5. 性能剖析
- **pprof**：CPU/内存/阻塞/锁 profile
- **trace**：运行时事件追踪
- **bench**：基准测试
- **trace flag**：运行时追踪标志

## 知识库引用

| 主题 | 文档 |
|------|------|
| GMP 调度器 | `knowledge/fullstack/go-gmp-scheduler-deep.md` |
| GC 原理 | `knowledge/fullstack/go-gc-deep.md` |
| 内存模型 | `knowledge/fullstack/go-memory-model-deep.md` |
| 网络轮询器 | `knowledge/fullstack/go-netpoller-deep.md` |
| 内存分配 | `knowledge/fullstack/go-memory-allocator-deep.md` |
| 并发模型 | `knowledge/fullstack/go-concurrency-model-deep.md` |
| 并发模式 | `knowledge/fullstack/go-concurrency-patterns-deep.md` |
| 性能优化 | `knowledge/fullstack/backend-performance-optimization-deep.md` |

## 使用场景

### 场景 1: Go 性能优化
1. 使用 `pprof` 定位瓶颈
2. 分析 CPU profile 找到热点函数
3. 分析 memory profile 检查 GC 压力
4. 参考对应文档应用优化策略

### 场景 2: 并发编程
1. 理解 GMP 调度原理
2. 合理设置 GOMAXPROCS
3. 选择合适的并发模式
4. 避免常见陷阱（goroutine 泄漏、死锁）

### 场景 3: GC 调优
1. 监控 GC 频率和耗时
2. 调整 GOGC 参数
3. 减少 allocations（object pooling）
4. 使用 `sync.Pool` 优化

## 关键代码模式

### sync.Pool 使用
```go
var bufferPool = sync.Pool{
    New: func() interface{} {
        buf := make([]byte, 32*1024)
        return &buf
    },
}

func processData() {
    buf := bufferPool.Get().(*[]byte)
    defer bufferPool.Put(buf)
    // 使用 buf...
}
```

### Goroutine Pool
```go
type WorkerPool struct {
    workers int
    jobs    chan func()
    wg      sync.WaitGroup
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    wp := &WorkerPool{
        workers: workers,
        jobs:    make(chan func(), queueSize),
    }
    for i := 0; i < workers; i++ {
        go wp.worker()
    }
    return wp
}
```

## 自测题

<details>
<summary>Q1: GOMAXPROCS 应该设多少？</summary>

**答案**：
1. **CPU 密集型**：等于 CPU 核数
2. **IO 密集型**：可以大于核数（因为 G 会阻塞等待 IO）
3. **混合负载**：根据实际情况调整，通常 2-4 倍核数
4. **默认值**：Go 1.5+ 默认为 CPU 核数
5. **注意**：过大不会提升性能，反而增加调度开销

</details>

<details>
<summary>Q2: 如何避免 Goroutine 泄漏？</summary>

**答案**：
1. **Context 超时**：使用 context.WithTimeout 控制生命周期
2. **Channel 关闭**：确保发送方正确关闭 channel
3. **Select 默认**：使用 select 配合 default 避免阻塞
4. **pprof 检测**：使用 `go tool pprof` 检查 goroutine 数量
5. **测试覆盖**：在测试中验证 goroutine 是否正常退出

</details>

<details>
<summary>Q3: GC 触发条件是什么？如何调优？</summary>

**答案**：
1. **触发条件**：
   - 内存增长达到阈值（GOGC 控制，默认 100%）
   - 时间间隔达到 gcPauseMaxDuration
   - GC 标记阶段抢占式扫描
   
2. **调优方法**：
   - 降低 GOGC（如 50）减少内存占用但增加 CPU
   - 提高 GOGC（如 200）减少 GC 频率但增加内存
   - 使用 `GODEBUG=gctrace=1` 查看详细日志
   - 减少 allocations（复用对象、预分配容量）

</details>
