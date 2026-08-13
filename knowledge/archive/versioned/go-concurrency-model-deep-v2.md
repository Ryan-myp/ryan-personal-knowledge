# Go 并发模型深度解析

> 深入 Go 并发模型：GMP调度器、Channel、锁机制、并发模式。
> 源码级分析 runtime.g 包，包含高性能并发实践。
> 适用对象：Go 工程师、并发编程学习者、系统程序员

---

## 1. Goroutine 模型

### 1.1 M:P:G 调度模型

```
┌─────────────────────────────────────────────────────────────┐
│                    GMP 调度模型                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  M (Machine) - 操作系统线程                                   │
│  ├── 真正的执行单元                                           │
│  ├── 绑定到 P 才能执行 G                                      │
│  └── 数量 = numcpu (默认)                                    │
│                                                             │
│  P (Processor) - 逻辑处理器                                   │
│  ├── 管理 G 队列                                             │
│  ├── 数量 = numcpu (默认，最大 256)                           │
│  └── 持有 local work queue                                   │
│                                                             │
│  G (Goroutine) - 协程                                       │
│  ├── 轻量级线程 (2KB 栈)                                     │
│  ├── 可抢占式调度                                            │
│  └── 等待系统调用时让出 P                                     │
│                                                             │
│  调度关系：                                                    │
│  ┌─────┐    ┌─────┐    ┌─────┐                              │
│  │  G1 │───►│  P1 │◄───│  M1 │                              │
│  │  G2 │    │     │    │     │                              │
│  │  G3 │    └─────┘    └─────┘                              │
│  └─────┘                                                     │
│                                                             │
│  全局队列：全局 work queue (所有 P 共享)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 调度流程

```
Goroutine 调度流程：

1. 创建 Goroutine
   └── runtime.newproc() → 放入当前 P 的 local queue

2. 执行 Goroutine
   └── P 从 local queue 取出 G 执行

3. 系统调用阻塞
   └── G 阻塞 → M 阻塞 → P 找到新 M 绑定

4. 系统调用返回
   └── G 放入 global queue → M 阻塞 → 等待调度

5. 被抢占
   └── 调度器检查 preempt 标志 → 保存状态 → 放入 queue
```

---

## 2. Channel 实现

### 2.1 数据结构

```go
// chann.go (简化版)

type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列大小
    buf      unsafe.Pointer // 环形队列指针
    elemsize uint16         // 元素大小
    closed   uint32         // 是否关闭
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 G 队列
    sendq    waitq          // 等待发送的 G 队列
    
    lock mutex        // 互斥锁
}

type waitq struct {
    first *g
    last  *g
}
```

### 2.2 发送操作

```go
func chanSend(c *hchan, elem unsafe.Pointer, block bool, callerpc uintptr) bool {
    // 1. 检查是否关闭
    if c.closed != 0 {
        panic("send on closed channel")
    }
    
    // 2. 尝试直接发送
    if c.qcount < c.dataqsiz {
        // 环形队列有空间，直接发送
        setRecv(c, elem)
        return true
    }
    
    // 3. 尝试唤醒接收者
    if sg := c.recvq.dequeue(); sg != nil {
        send(c, sg, elem, true)
        return true
    }
    
    // 4. 阻塞等待
    if !block {
        return false
    }
    
    gp := getg()
    mg := gp.m
    sg := acquireSudog()
    sg.releasetime = 0
    sg.G = gp
    sg.ch = c
    c.sendq.enqueue(sg)
    
    // 挂起当前 goroutine
    goreseet()
    schedule(mg, gp, true)
    
    return true
}
```

### 2.3 接收操作

```go
func chanrecv(c *hchan, elem unsafe.Pointer, block bool) (selected, received bool) {
    // 1. 检查是否关闭且有数据
    if c.closed != 0 && c.qcount == 0 {
        if recv(c, nil) {
            return true, false
        }
        return true, false
    }
    
    // 2. 尝试从队列接收
    if c.qcount > 0 {
        received = recv(c, elem)
        return true, received
    }
    
    // 3. 尝试唤醒发送者
    if sg := c.sendq.dequeue(); sg != nil {
        recv(c, elem, sg, true)
        return true, true
    }
    
    // 4. 阻塞等待
    if !block {
        return false, false
    }
    
    gp := getg()
    mg := gp.m
    sg := acquireSudog()
    sg.G = gp
    sg.ch = c
    c.recvq.enqueue(sg)
    
    // 挂起当前 goroutine
    goreseet()
    schedule(mg, gp, true)
    
    return true, true
}
```

---

## 3. 锁机制

### 3.1 Mutex 实现

```go
// mutex.go (简化版)

type Mutex struct {
    state int32
    sema  uint32
}

const (
    mutexLocked = 1 << iota // 锁已持有
    mutexWoken
    mutexStarving
    mutexWaitShift = iota
)

func (m *Mutex) Lock() {
    // 快速路径：尝试获取锁
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
        
        wait++
        
        // 饥饿模式：直接等待
        if m.state&mutexStarving != 0 {
            // 加入等待队列
            atomic.OrInt32(&m.state, mutexWoken)
            semaphoreSemacreate()
            return
        }
        
        // 正常模式：让出 CPU
        if wait > 1000 {
            // 转为饥饿模式
            atomic.OrInt32(&m.state, mutexStarving)
        }
        
        runtime_sched()
    }
}
```

### 3.2 RWMutex 实现

```go
type RWMutex struct {
    w           Mutex    // 写锁
    writerSem   uint32   // 写者信号量
    readerSem   uint32   // 读者信号量
    readerCount int32    // 读者数量
    readerWait  int32    // 等待释放的读者数量
}

func (rw *RWMutex) RLock() {
    atomic.AddInt32(&rw.readerCount, 1)
    semaphoreSemacreate()
}

func (rw *RWMutex) RUnlock() {
    if atomic.AddInt32(&rw.readerCount, -1) == 0 {
        // 最后一个读者释放，唤醒写者
        semaphoreSemav()
        return
    }
    if atomic.AddInt32(&rw.readerWait, -1) == 0 {
        // 所有读者释放完毕，唤醒写者
        semaphoreSemav()
    }
}
```

---

## 4. 并发模式

### 4.1 Worker Pool

```go
// worker_pool.go

type WorkerPool struct {
    jobs    chan func()
    results chan []byte
    workers int
}

func NewWorkerPool(workers, queueSize int) *WorkerPool {
    return &WorkerPool{
        jobs:    make(chan func(), queueSize),
        results: make(chan []byte, queueSize),
        workers: workers,
    }
}

func (wp *WorkerPool) Start() {
    for i := 0; i < wp.workers; i++ {
        go wp.worker(i)
    }
}

func (wp *WorkerPool) worker(id int) {
    for job := range wp.jobs {
        result := job()
        wp.results <- result
    }
}

func (wp *WorkerPool) Submit(job func() []byte) {
    wp.jobs <- job
}

func (wp *WorkerPool) Collect(n int) []byte {
    return <-wp.results
}
```

### 4.2 Fan-out/Fan-in

```go
// fan_out_in.go

func fanOut(in <-chan int, workers int) []<-chan int {
    outs := make([]<-chan int, workers)
    for i := 0; i < workers; i++ {
        outs[i] = worker(in, i)
    }
    return outs
}

func worker(in <-chan int, id int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for v := range in {
            out <- v * 2 // 处理逻辑
        }
    }()
    return out
}

func fanIn(channels ...<-chan int) <-chan int {
    var wg sync.WaitGroup
    out := make(chan int)
    
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
    
    go func() {
        wg.Wait()
        close(out)
    }()
    
    return out
}
```

---

## 5. 性能优化

### 5.1 减少锁竞争

```go
// 优化前：全局锁
var counter int
var mu sync.Mutex

func increment() {
    mu.Lock()
    counter++
    mu.Unlock()
}

// 优化后：per-Goroutine 计数
type LocalCounter struct {
    count int
}

func (lc *LocalCounter) increment() {
    lc.count++
}

func collect(counters []*LocalCounter) int {
    total := 0
    for _, lc := range counters {
        total += lc.count
    }
    return total
}
```

### 5.2 Channel 优化

```go
// 优化前：阻塞 Channel
func process(ch chan int) {
    for v := range ch {
        // 处理
    }
}

// 优化后：带 buffer 的 Channel
func process(ch chan int) {
    for v := range ch {
        // 处理
    }
}

// 创建时指定 buffer
ch := make(chan int, 1000)
```

---

## 6. 调试工具

### 6.1 pprof

```bash
# CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile

# Goroutine dump
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Mutex contention
go tool pprof http://localhost:6060/debug/pprof/mutex

# Block profile
go tool pprof http://localhost:6060/debug/pprof/block
```

### 6.2 常见并发问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| Goroutine 泄漏 | 内存持续增长 | `pprof goroutine` | 修复泄漏点 |
| 死锁 | 程序卡住 | `pprof block` | 优化锁顺序 |
| 锁竞争 | CPU 高 | `pprof mutex` | 减少锁粒度 |
| Channel 阻塞 | 请求超时 | trace分析 | 增加 buffer |

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| GMP调度 | 工作窃取 + 全局队列 |
| Channel | 环形队列 + 等待队列 |
| Mutex | 自旋 + 饥饿模式 |
| 并发模式 | Worker Pool / Fan-out |

### 7.2 最佳实践

- [ ] 合理设置 Channel buffer
- [ ] 减少锁粒度
- [ ] 使用 context 控制生命周期
- [ ] 定期 pprof 分析
- [ ] 避免 Goroutine 泄漏

---

*最后更新：2026-08-11*
*作者：Ryan*
