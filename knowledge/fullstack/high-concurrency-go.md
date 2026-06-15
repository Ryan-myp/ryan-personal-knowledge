# Go 高并发编程核心原理

> 无锁数据结构/CAS原子操作/协程池/Channel 优化/sync.Pool 实战

---

## 第一部分：入门引导（5 分钟速览）

### 高并发编程为什么重要？

广告平台是典型的高并发场景：
- **实时竞价**：峰值 QPS 100万+
- **预算扣减**：并发更新，需保证原子性
- **用户计数**：实时统计 PV/Click，高并发写入

### Go 并发模型

```
Goroutine（微线程，2KB 栈）
    ↓
M (OS Thread)
    ↓
P (Processor, 调度器核心)
    ↓
Sched (GMP 调度器)
```

---

## 第二部分：无锁数据结构

### 2.1 CAS 原子操作

```go
package atomic

import (
    "sync/atomic"
)

// LockFreeCounter 无锁计数器
type LockFreeCounter struct {
    count int64
}

func (lc *LockFreeCounter) Increment() int64 {
    // CAS 循环：compare-and-swap
    for {
        old := atomic.LoadInt64(&lc.count)
        if atomic.CompareAndSwapInt64(&lc.count, old, old+1) {
            return old + 1
        }
        // CAS 失败，重试
    }
}

func (lc *LockFreeCounter) Decrement() int64 {
    for {
        old := atomic.LoadInt64(&lc.count)
        if atomic.CompareAndSwapInt64(&lc.count, old, old-1) {
            return old - 1
        }
    }
}

func (lc *LockFreeCounter) Get() int64 {
    return atomic.LoadInt64(&lc.count)
}
```

### 2.2 无锁队列

```go
type LockFreeQueue struct {
    head *node
    tail *node
}

type node struct {
    value interface{}
    next  unsafe.Pointer
}

func NewLockFreeQueue() *LockFreeQueue {
    dummy := &node{}
    return &LockFreeQueue{
        head: dummy,
        tail: dummy,
    }
}

func (q *LockFreeQueue) Enqueue(value interface{}) {
    n := &node{value: value}
    
    for {
        tail := q.tail
        next := (*node)(atomic.LoadPointer(&tail.next))
        
        if tail == q.tail {
            if next == nil {
                // 尝试将新节点链接到尾部
                if atomic.CompareAndSwapPointer(&tail.next, nil, unsafe.Pointer(n)) {
                    // 推进 tail
                    atomic.CompareAndSwapPointer(&q.tail, unsafe.Pointer(tail), unsafe.Pointer(n))
                    return
                }
            } else {
                // 尾部落后，帮忙推进
                atomic.CompareAndSwapPointer(&q.tail, unsafe.Pointer(tail), unsafe.Pointer(next))
            }
        }
    }
}

func (q *LockFreeQueue) Dequeue() (interface{}, bool) {
    for {
        head := q.head
        tail := q.tail
        next := (*node)(atomic.LoadPointer(&head.next))
        
        if head == q.head {
            if head == tail {
                if next == nil {
                    return nil, false // 空队列
                }
                // 帮忙推进 tail
                atomic.CompareAndSwapPointer(&q.tail, unsafe.Pointer(tail), unsafe.Pointer(next))
            } else {
                // 读取值，然后推进 head
                value := next.value
                if atomic.CompareAndSwapPointer(&q.head, unsafe.Pointer(head), unsafe.Pointer(next)) {
                    return value, true
                }
            }
        }
    }
}
```

### 2.3 分段锁

```go
type ShardedLock struct {
    shards []shard
    mask   uint64
}

type shard struct {
    mu   sync.Mutex
    data map[string]interface{}
}

func NewShardedLock(shardCount int) *ShardedLock {
    shards := make([]shard, shardCount)
    for i := 0; i < shardCount; i++ {
        shards[i].data = make(map[string]interface{})
    }
    
    return &ShardedLock{
        shards: shards,
        mask:   uint64(shardCount - 1),
    }
}

func (sl *ShardedLock) getShard(key string) *shard {
    hash := crc32.ChecksumIEEE([]byte(key))
    idx := hash & sl.mask
    return &sl.shards[idx]
}

func (sl *ShardedLock) Get(key string) (interface{}, bool) {
    s := sl.getShard(key)
    s.mu.Lock()
    defer s.mu.Unlock()
    
    val, ok := s.data[key]
    return val, ok
}

func (sl *ShardedLock) Set(key string, value interface{}) {
    s := sl.getShard(key)
    s.mu.Lock()
    defer s.mu.Unlock()
    
    s.data[key] = value
}
```

---

## 第三部分：协程池

### 3.1 固定大小协程池

```go
type WorkerPool struct {
    jobs    chan func()
    wg      sync.WaitGroup
    running int64
}

func NewWorkerPool(workerCount, queueSize int) *WorkerPool {
    wp := &WorkerPool{
        jobs: make(chan func(), queueSize),
    }
    
    // 启动 worker
    for i := 0; i < workerCount; i++ {
        wp.wg.Add(1)
        go wp.worker()
    }
    
    return wp
}

func (wp *WorkerPool) worker() {
    defer wp.wg.Done()
    
    for job := range wp.jobs {
        atomic.AddInt64(&wp.running, 1)
        
        func() {
            defer func() {
                atomic.AddInt64(&wp.running, -1)
                if r := recover(); r != nil {
                    log.Printf("worker panic: %v", r)
                }
            }()
            job()
        }()
    }
}

func (wp *WorkerPool) Submit(job func()) error {
    if atomic.LoadInt64(&wp.running) == 0 {
        return fmt.Errorf("pool is shutting down")
    }
    
    select {
    case wp.jobs <- job:
        return nil
    default:
        return fmt.Errorf("queue is full")
    }
}

func (wp *WorkerPool) Stop() {
    close(wp.jobs)
    wp.wg.Wait()
}
```

### 3.2 动态协程池

```go
type DynamicPool struct {
    jobs     chan func()
    minWorkers int
    maxWorkers int
    currentWorkers int64
    mu sync.Mutex
    wg sync.WaitGroup
}

func (dp *DynamicPool) Submit(job func()) error {
    select {
    case dp.jobs <- job:
        return nil
    default:
        // 队列满，创建新 worker
        dp.mu.Lock()
        if dp.currentWorkers < int64(dp.maxWorkers) {
            dp.currentWorkers++
            dp.wg.Add(1)
            go dp.runWorker()
        }
        dp.mu.Unlock()
        return fmt.Errorf("pool is full")
    }
}

func (dp *DynamicPool) runWorker() {
    defer dp.wg.Done()
    
    timer := time.NewTimer(30 * time.Second)
    defer timer.Stop()
    
    for {
        select {
        case job, ok := <-dp.jobs:
            if !ok {
                return
            }
            job()
            // 重置定时器
            if !timer.Stop() {
                select {
                case <-timer.C:
                default:
                }
            }
            timer.Reset(30 * time.Second)
        case <-timer.C:
            // 超时后减少 worker
            dp.mu.Lock()
            if dp.currentWorkers > int64(dp.minWorkers) {
                dp.currentWorkers--
            }
            dp.mu.Unlock()
            return
        }
    }
}
```

---

## 第四部分：sync.Pool 实战

### 4.1 连接池复用

```go
var connPool = sync.Pool{
    New: func() interface{} {
        return &Connection{
            buf: make([]byte, 1024),
        }
    },
}

type Connection struct {
    buf []byte
    netConn net.Conn
}

func GetConnection() *Connection {
    return connPool.Get().(*Connection)
}

func PutConnection(conn *Connection) {
    conn.buf = conn.buf[:0]
    conn.netConn = nil
    connPool.Put(conn)
}

// 使用示例
func ProcessRequest(req *Request) ([]byte, error) {
    conn := GetConnection()
    defer PutConnection(conn)
    
    // 使用 conn.buf 处理请求
    err := conn.writeRequest(req)
    if err != nil {
        return nil, err
    }
    
    return conn.readResponse()
}
```

### 4.2 广告竞价对象池

```go
var bidReqPool = sync.Pool{
    New: func() interface{} {
        return &BidRequest{
            impressions: make([]Impression, 0, 10),
        }
    },
}

type BidRequest struct {
    impressions []Impression
    userId      string
    budget      float64
}

func GetBidRequest() *BidRequest {
    return bidReqPool.Get().(*BidRequest)
}

func PutBidRequest(req *BidRequest) {
    req.impressions = req.impressions[:0]
    req.userId = ""
    req.budget = 0
    bidReqPool.Put(req)
}
```

---

## 第五部分：自测题

### 问题 1
CAS 操作为什么比互斥锁快？

<details>
<summary>查看答案</summary>

1. **无锁竞争**：CAS 在用户态完成，不需要操作系统介入
2. **避免上下文切换**：不需要线程阻塞/唤醒
3. **硬件支持**：现代 CPU 提供 CAS 指令（CMPXCHG）
4. **适用场景**：简单计数器、标志位
5. **ABA 问题**：需要用带版本号的 CAS 解决

</details>

### 问题 2
sync.Pool 适合什么场景？不适合什么场景？

<details>
<summary>查看答案</summary>

1. **适合**：临时对象复用（Connection、Buffer、BidRequest）
2. **不适合**：需要持久化状态的对象
3. **不适合**：线程安全要求高的场景
4. **特点**：GC 时会被清空，不保证对象存活
5. **最佳实践**：存放可重新初始化的对象

</details>

### 问题 3
协程池相比直接启动协程有什么优势？

<details>
<summary>查看答案</summary>

1. **资源控制**：限制并发数量，防止 OOM
2. **性能稳定**：避免频繁创建/销毁协程的开销
3. **队列管理**：任务排队，防止突发流量打垮系统
4. **优雅退出**：可以优雅停止所有 worker
5. **Go 实现**：使用固定大小或动态协程池

</details>

---

*本文档基于 Go 高并发编程原理整理。*