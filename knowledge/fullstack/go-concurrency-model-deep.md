# Go 并发模型深度解析

> 深入 Go 并发模型：Goroutine、Channel、锁机制、并发模式。
> 源码级分析 runtime.g 包，包含高性能并发实践。
> 适用对象：Go 工程师、并发编程学习者、系统程序员

---

## 1. Goroutine 模型

### 1.1 M:P:G 调度模型

```
┌─────────────────────────────────────────────────────────────┐
│                  Go 调度器架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  G (Goroutine)                                              │
│  ├── 用户代码执行的协程                                       │
│  ├── 栈大小动态扩展（2KB 起步）                               │
│  └── 内核无关，完全由 Go 运行时管理                            │
│                                                             │
│  M (Machine)                                                │
│  ├── 操作系统线程                                              │
│  ├── 执行 G 的代码                                           │
│  └── 数量由 GOMAXPROCS 控制                                  │
│                                                             │
│  P (Processor)                                              │
│  ├── 本地运行队列                                            │
│  ├── 管理 G 的执行                                           │
│  └── 数量默认等于 CPU 核数                                    │
│                                                             │
│  调度流程：                                                   │
│  1. G 创建 → 放入 P 的本地队列                               │
│  2. P 调度 G 到 M 执行                                       │
│  3. G 阻塞 → 放入全局队列或网络队列                          │
│  4. P 从全局队列窃取 G                                       │
│  5. 工作窃取（Work Stealing）实现负载均衡                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 调度器源码结构

```go
// runtime/proc.go (简化)

// P 结构
type p struct {
    lock mutex
    
    runq     gQueue      // 本地运行队列
    runnext  g           // 下一个运行的 G
    
    sudoglock  mutex
    sudogcache []*sudog    // sudog 缓存
    
    pollUntil  uint64      // 下一轮 poll 时间
    
    // 全局队列统计
    pcount     int32
    maxpcount  int32
    
    // 工作窃取
    stealord  uint32      // 窃取顺序
}

// M 结构
type m struct {
    g0      *g          // 操作系统线程的栈
    curg    *g          // 当前运行的 G
    p       puintptr    // 绑定的 P
    locks   int32       // 锁计数
}

// G 结构
type g struct {
    stack       stack      // 栈信息
    stackguard0 uintptr    // 栈保护（防溢出）
    stackguard1 uintptr    // 栈保护（另一种方式）
    sched       gobuf      // 执行现场
    
    params      unsafe.Pointer  // 参数
    atomicstatus uint32         // 状态
}
```

---

## 2. Channel 实现

### 2.1 Channel 数据结构

```go
// runtime/chan.go

type hchan struct {
    mu *lock     // 互斥锁
    
    elemtype *_type    // 元素类型
    
    elemsize uint16    // 元素大小
    
    closed uint16      // 是否关闭
    
    elem *_type    // 元素指针
    
    // 队列
    qcount   uint        // 队列中的元素数量
    dataqsiz uint        // 环形队列容量
    
    buf      unsafe.Pointer  // 环形队列缓冲区
    
    elemsize uint16      // 每个元素大小
    
    elemtype *_type      // 元素类型
    
    // 等待队列
    sendq    waitq       // 等待发送的 G 队列
    recvq    waitq       // 等待接收的 G 队列
    
    // 锁
    lock mutex
}

// waitq 等待队列
type waitq struct {
    first *g
    last  *g
}
```

### 2.2 Channel 操作原理

```
发送操作：
1. 检查 Channel 是否关闭
2. 尝试直接发送给等待的接收者
3. 将数据放入缓冲区
4. 如果没有空间，阻塞等待

接收操作：
1. 检查 Channel 是否关闭
2. 尝试直接从缓冲区或等待的发送者获取
3. 如果没有数据，阻塞等待
```

### 2.3 Go 实现 Channel

```go
// channel.go

package concurrent

import "sync"

type Channel struct {
    mu       sync.Mutex
    buf      []interface{}
    maxBuf   int
    closed   bool
    sendWait sync.Cond
    recvWait sync.Cond
}

func NewChannel(size int) *Channel {
    c := &Channel{
        buf:    make([]interface{}, 0, size),
        maxBuf: size,
    }
    c.sendWait = *sync.NewCond(&c.mu)
    c.recvWait = *sync.NewCond(&c.mu)
    return c
}

func (c *Channel) Send(v interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    // 如果缓冲区满，等待
    for len(c.buf) >= c.maxBuf && !c.closed {
        c.sendWait.Wait()
    }
    
    if c.closed {
        panic("send on closed channel")
    }
    
    c.buf = append(c.buf, v)
    c.recvWait.Signal()
}

func (c *Channel) Receive() (interface{}, bool) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    // 如果缓冲区空，等待
    for len(c.buf) == 0 && !c.closed {
        c.recvWait.Wait()
    }
    
    if len(c.buf) == 0 {
        return nil, false
    }
    
    v := c.buf[0]
    c.buf = c.buf[1:]
    c.sendWait.Signal()
    return v, true
}

func (c *Channel) Close() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.closed = true
    c.sendWait.Broadcast()
    c.recvWait.Broadcast()
}
```

---

## 3. 锁机制

### 3.1 sync.Mutex

```
Mutex 实现原理：

1. 自旋锁（自旋等待）
   - 在多核 CPU 上，短时间自旋等待
   - 避免上下文切换开销

2. 系统调用
   - 如果自旋失败，进入内核等待
   - 通过 futex 系统调用实现

3. 公平性
   - 先到先得，避免饥饿
```

### 3.2 Go 实现 Mutex

```go
// mutex.go

package concurrent

import (
    "sync"
    "sync/atomic"
)

type Mutex struct {
    state int32
    sema  uint32
}

// 锁状态位
const (
    mutexLocked = 1 << iota
    mutexWoken
    mutexStarving
)

func (m *Mutex) Lock() {
    // 快速路径：无竞争
    if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
        return
    }
    
    // 慢路径
    m.lockSlow()
}

func (m *Mutex) lockSlow() {
    var wait int
    for {
        // 尝试获取锁
        if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
            return
        }
        
        // 等待
        wait++
        runtime_sleep(wait)
    }
}
```

### 3.3 RWMutex

```
读锁 vs 写锁：

┌─────────────────────────────────────────────────────────────┐
│                    读写锁对比                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RWMutex                                                     │
│  ├── 读锁：多个 goroutine 可同时获取                         │
│  ├── 写锁：独占，阻塞其他读写                                │
│  ├── 写锁优先：避免写饥饿                                   │
│  └── 适用：读多写少场景                                     │
│                                                             │
│  性能对比：                                                  │
│  ├── Mutex: 100% 序列化                                    │
│  ├── RWMutex (读多): ~N 并发读                             │
│  └── RWMutex (写多): ~Mutex 性能                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 并发模式

### 4.1 Worker Pool

```go
// worker_pool.go

package concurrent

import (
    "sync"
)

type WorkerPool struct {
    tasks   chan func()
    wg      sync.WaitGroup
    workers int
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    return &WorkerPool{
        tasks:   make(chan func(), queueSize),
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
    for task := range p.tasks {
        task()
    }
}

func (p *WorkerPool) Submit(task func()) {
    p.tasks <- task
}

func (p *WorkerPool) Stop() {
    close(p.tasks)
    p.wg.Wait()
}
```

### 4.2 Fan-out/Fan-in

```go
// fan_out_in.go

package concurrent

import "sync"

// Fan-out: 并行处理，Fan-in: 合并结果
func FanOutIn(tasks []func() interface{}) []interface{} {
    var wg sync.WaitGroup
    results := make([]interface{}, len(tasks))
    
    for i, task := range tasks {
        wg.Add(1)
        go func(idx int, t func() interface{}) {
            defer wg.Done()
            results[idx] = t()
        }(i, task)
    }
    
    wg.Wait()
    return results
}
```

### 4.3 Pipeline

```go
// pipeline.go

package concurrent

import "sync"

type Pipeline struct {
    stages []func(<-chan interface{}) <-chan interface{}
}

func (p *Pipeline) Run(input <-chan interface{}) <-chan interface{} {
    out := input
    for _, stage := range p.stages {
        out = stage(out)
    }
    return out
}

func (p *Pipeline) AddStage(stage func(<-chan interface{}) <-chan interface{}) {
    p.stages = append(p.stages, stage)
}
```

---

## 5. 性能优化

### 5.1 常见优化策略

```
并发性能优化：

1. 减少锁竞争
   ├── 缩小临界区
   ├── 使用无锁数据结构
   └── 读写分离

2. 合理选择 Channel 大小
   ├── 无缓冲：同步通信
   ├── 小缓冲：解耦+流量控制
   └── 大缓冲：批量处理

3. 避免 goroutine 泄漏
   ├── 确保所有 goroutine 能退出
   ├── 使用 context 控制生命周期
   └── 监控 goroutine 数量
```

### 5.2 压测工具

```go
// benchmark.go

package concurrent

import (
    "testing"
    "sync"
)

// 测试 Channel 性能
func BenchmarkChannelSend(b *testing.B) {
    ch := make(chan int, 1000)
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        ch <- i
    }
}

// 测试 Mutex 性能
func BenchmarkMutex(b *testing.B) {
    var mu sync.Mutex
    var count int
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        mu.Lock()
        count++
        mu.Unlock()
    }
}

// 测试 WaitGroup 性能
func BenchmarkWaitGroup(b *testing.B) {
    var wg sync.WaitGroup
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        wg.Add(1)
        go func() {
            wg.Done()
        }()
        wg.Wait()
    }
}
```

---

## 6. 监控与调试

### 6.1 pprof 工具

```bash
# 开启 pprof
import _ "net/http/pprof"
import "net/http"
http.ListenAndServe("localhost:6060", nil)

# 查看 goroutine
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 查看阻塞分析
go tool pprof http://localhost:6060/debug/pprof/block

# 查看锁竞争
go tool pprof http://localhost:6060/debug/pprof/mutex
```

### 6.2 监控指标

```go
// metrics.go

package concurrent

import "github.com/prometheus/client_golang/prometheus"

type ConcurrentMetrics struct {
    goroutines    prometheus.Gauge
    channels      prometheus.GaugeVec
    locks         prometheus.GaugeVec
    waitgroups    prometheus.GaugeVec
}

func NewConcurrentMetrics() *ConcurrentMetrics {
    return &ConcurrentMetrics{
        goroutines: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "concurrent_goroutines",
            Help: "Current goroutines",
        }),
        channels: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{Name: "concurrent_channels", Help: "Channel operations"},
            []string{"type", "name"},
        ),
        locks: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{Name: "concurrent_locks", Help: "Lock operations"},
            []string{"type", "name"},
        ),
        waitgroups: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{Name: "concurrent_waitgroups", Help: "WaitGroup operations"},
            []string{"name"},
        ),
    }
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| Goroutine | GMP 调度模型 |
| Channel | 环形缓冲 + 等待队列 |
| 锁 | 自旋 + 系统调用 |
| 并发模式 | Worker Pool / Pipeline |

### 7.2 最佳实践

- [ ] 合理设置 GOMAXPROCS
- [ ] 避免 goroutine 泄漏
- [ ] 使用 context 控制生命周期
- [ ] 监控并发指标
- [ ] 压测验证性能

---

*最后更新：2026-08-11*
*作者：Ryan*
