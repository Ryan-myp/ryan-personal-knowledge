# 高并发编程深度：无锁数据结构/协程池/原子操作

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解无锁编程

```
传统锁 = 会议室门上的锁
  → 一个人进去开会，其他人等
  → 开门/关门有开销
  → 可能死锁（钥匙丢了）

无锁编程 = 共享白板
  → 多人可以同时看白板
  → 用原子操作更新（CAS）
  → 不会死锁，但需要处理冲突
```

### 为什么需要无锁编程？

```
锁的开销：
1. 上下文切换：100-1000ns
2. 缓存失效：L1/L2/L3 cache 失效
3. 内存屏障：阻止 CPU 重排序
4. 死锁风险：嵌套锁可能死锁

无锁的优势：
1. 无上下文切换：用户态完成
2. 缓存友好：减少 cache miss
3. 无死锁：不会出现
4. 高吞吐：适合高并发场景
```

---

## 第二部分：CAS 原子操作深度

### 2.1 CAS 原理

```
CAS (Compare-And-Swap)：
1. 读取当前值
2. 比较是否等于预期值
3. 如果相等，更新为新值
4. 如果不相等，重试

伪代码：
bool CAS(pointer, expected, new_value) {
    if *pointer == expected {
        *pointer = new_value
        return true
    }
    return false
}
```

### 2.2 Go 实现无锁计数器

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
    // 方式 1：使用 atomic.AddInt64
    return atomic.AddInt64(&lc.count, 1)
}

func (lc *LockFreeCounter) Decrement() int64 {
    return atomic.AddInt64(&lc.count, -1)
}

func (lc *LockFreeCounter) Get() int64 {
    return atomic.LoadInt64(&lc.count)
}

// 方式 2：手动实现 CAS 循环
func (lc *LockFreeCounter) IncrementManual() int64 {
    for {
        // 1. 读取当前值
        old := atomic.LoadInt64(&lc.count)
        
        // 2. 计算新值
        new := old + 1
        
        // 3. CAS 尝试更新
        if atomic.CompareAndSwapInt64(&lc.count, old, new) {
            return new
        }
        
        // 4. CAS 失败，重试
    }
}

// 关键：为什么需要循环？
// 1. 多个 goroutine 可能同时读取相同的 old 值
// 2. 只有一个能成功 CAS
// 3. 失败的 goroutine 需要重新读取并重试
// 4. 这就是乐观锁的思想
```

### 2.3 ABA 问题

```
ABA 问题：
1. 线程 1 读取值为 A
2. 线程 2 将值改为 B
3. 线程 2 将值改回 A
4. 线程 1 CAS 成功（认为值没变）

解决方案：
1. 使用版本号（带版本的 CAS）
2. 使用指针 + 版本号
3. 使用 hazard pointer
```

```go
// 带版本号的 CAS
type VersionedCounter struct {
    value   int64
    version uint64
}

func (vc *VersionedCounter) Increment() {
    for {
        // 1. 读取当前值和版本号
        oldValue := atomic.LoadInt64(&vc.value)
        oldVersion := atomic.LoadUint64(&vc.version)
        
        // 2. 计算新值
        newValue := oldValue + 1
        newVersion := oldVersion + 1
        
        // 3. CAS 更新（使用双字 CAS）
        if atomic.CompareAndSwapUint64(
            (*uint64)(unsafe.Pointer(&vc.version)),
            oldVersion,
            newVersion,
        ) {
            atomic.StoreInt64(&vc.value, newValue)
            return
        }
        // 4. 失败重试
    }
}
```

---

## 第三部分：无锁队列

### 3.1 Michael-Scott 队列

```
MS 队列是最经典的无锁队列实现。

核心思想：
1. 使用 dummy 节点作为头尾
2. 尾节点指向下一个节点
3. CAS 操作保证原子性
```

```go
package lockfree

import (
    "sync/atomic"
    "unsafe"
)

// Node 队列节点
type Node struct {
    value interface{}
    next  unsafe.Pointer // 使用 unsafe.Pointer 实现原子更新
}

// LockFreeQueue 无锁队列
type LockFreeQueue struct {
    head *Node
    tail *Node
}

func NewLockFreeQueue() *LockFreeQueue {
    dummy := &Node{}
    return &LockFreeQueue{
        head: dummy,
        tail: dummy,
    }
}

// Enqueue 入队
func (q *LockFreeQueue) Enqueue(value interface{}) {
    node := &Node{value: value}
    
    for {
        // 1. 读取当前 tail
        tail := q.tail
        
        // 2. 读取 tail 的 next
        next := (*Node)(atomic.LoadPointer(&tail.next))
        
        // 3. 检查 tail 是否还在原位
        if tail == q.tail {
            if next == nil {
                // 4. 尝试将新节点链接到尾部
                if atomic.CompareAndSwapPointer(
                    &tail.next,
                    nil,
                    unsafe.Pointer(node),
                ) {
                    // 5. 成功，推进 tail
                    atomic.CompareAndSwapPointer(
                        &q.tail,
                        unsafe.Pointer(tail),
                        unsafe.Pointer(node),
                    )
                    return
                }
            } else {
                // 6. tail 落后了，帮忙推进
                atomic.CompareAndSwapPointer(
                    &q.tail,
                    unsafe.Pointer(tail),
                    unsafe.Pointer(next),
                )
            }
        }
    }
}

// Dequeue 出队
func (q *LockFreeQueue) Dequeue() (interface{}, bool) {
    for {
        // 1. 读取 head 和 tail
        head := q.head
        tail := q.tail
        
        // 2. 读取 head 的 next
        next := (*Node)(atomic.LoadPointer(&head.next))
        
        // 3. 检查 head 是否还在原位
        if head == q.head {
            if head == tail {
                if next == nil {
                    // 空队列
                    return nil, false
                }
                // tail 落后了，帮忙推进
                atomic.CompareAndSwapPointer(
                    &q.tail,
                    unsafe.Pointer(tail),
                    unsafe.Pointer(next),
                )
            } else {
                // 读取值
                value := next.value
                
                // CAS 推进 head
                if atomic.CompareAndSwapPointer(
                    &q.head,
                    unsafe.Pointer(head),
                    unsafe.Pointer(next),
                ) {
                    return value, true
                }
            }
        }
    }
}

// 关键：为什么需要 help 推进 tail？
// 1. 如果 Dequeue 线程失败了，tail 可能还指向旧节点
// 2. Enqueue 线程需要知道真实的 tail
// 3. 帮助推进 tail 可以避免 tail 落后太多
```

### 3.2 无锁栈

```go
// LockFreeStack 无锁栈
type LockFreeStack struct {
    head unsafe.Pointer
}

func NewLockFreeStack() *LockFreeStack {
    return &LockFreeStack{}
}

// Push 入栈
func (s *LockFreeStack) Push(value interface{}) {
    newNode := &Node{value: value}
    
    for {
        oldHead := atomic.LoadPointer(&s.head)
        newNode.next = oldHead
        
        if atomic.CompareAndSwapPointer(
            &s.head,
            oldHead,
            unsafe.Pointer(newNode),
        ) {
            return
        }
    }
}

// Pop 出栈
func (s *LockFreeStack) Pop() (interface{}, bool) {
    for {
        oldHead := atomic.LoadPointer(&s.head)
        if oldHead == nil {
            return nil, false
        }
        
        next := (*Node)(oldHead).next
        
        if atomic.CompareAndSwapPointer(
            &s.head,
            oldHead,
            unsafe.Pointer(next),
        ) {
            return (*Node)(oldHead).value, true
        }
    }
}
```

---

## 第四部分：协程池

### 4.1 固定大小协程池

```go
package pool

import (
    "context"
    "fmt"
    "sync"
    "sync/atomic"
)

// WorkerPool 工作池
type WorkerPool struct {
    jobs    chan func()
    wg      sync.WaitGroup
    running int64
    stopped int32
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
                    fmt.Printf("worker panic: %v\n", r)
                }
            }()
            job()
        }()
    }
}

func (wp *WorkerPool) Submit(job func()) error {
    if atomic.LoadInt32(&wp.stopped) == 1 {
        return fmt.Errorf("pool is stopped")
    }
    
    select {
    case wp.jobs <- job:
        return nil
    default:
        return fmt.Errorf("queue is full")
    }
}

func (wp *WorkerPool) Stop() {
    atomic.StoreInt32(&wp.stopped, 1)
    close(wp.jobs)
    wp.wg.Wait()
}

func (wp *WorkerPool) Running() int64 {
    return atomic.LoadInt64(&wp.running)
}
```

### 4.2 动态协程池

```go
// DynamicPool 动态协程池
type DynamicPool struct {
    jobs         chan func()
    minWorkers   int
    maxWorkers   int
    currentWorkers int64
    idleTimeout  time.Duration
    mu           sync.Mutex
    wg           sync.WaitGroup
}

func NewDynamicPool(minWorkers, maxWorkers int, idleTimeout time.Duration) *DynamicPool {
    dp := &DynamicPool{
        jobs:         make(chan func(), 1000),
        minWorkers:   minWorkers,
        maxWorkers:   maxWorkers,
        idleTimeout:  idleTimeout,
    }
    
    // 启动最小 worker 数
    for i := 0; i < minWorkers; i++ {
        dp.wg.Add(1)
        go dp.worker()
    }
    
    return dp
}

func (dp *DynamicPool) worker() {
    defer dp.wg.Done()
    
    timer := time.NewTimer(dp.idleTimeout)
    defer timer.Stop()
    
    for {
        select {
        case job, ok := <-dp.jobs:
            if !ok {
                return
            }
            
            // 重置定时器
            if !timer.Stop() {
                select {
                case <-timer.C:
                default:
                }
            }
            timer.Reset(dp.idleTimeout)
            
            // 执行 job
            func() {
                defer func() {
                    if r := recover(); r != nil {
                        fmt.Printf("worker panic: %v\n", r)
                    }
                }()
                job()
            }()
            
        case <-timer.C:
            // 超时，减少 worker
            dp.mu.Lock()
            if dp.currentWorkers > int64(dp.minWorkers) {
                dp.currentWorkers--
            }
            dp.mu.Unlock()
            return
        }
    }
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
            go dp.worker()
        }
        dp.mu.Unlock()
        return fmt.Errorf("pool is full")
    }
}
```

---

## 第五部分：sync.Pool 深度

### 5.1 sync.Pool 原理

```
sync.Pool 是 Go 的对象池，用于复用临时对象。

核心特点：
1. 线程安全：每个 P 有自己的 poolLocal
2. GC 友好：GC 时会清空所有 pool
3. 按需创建：New 函数在获取空池时调用
4. 不保证存活：对象可能被 GC 回收

适用场景：
1. 临时对象复用（Request/Response）
2. 减少 GC 压力
3. 避免频繁内存分配
```

### 5.2 Go 实现 sync.Pool

```go
// 使用 sync.Pool 优化竞价服务
var bidReqPool = sync.Pool{
    New: func() interface{} {
        return &BidRequest{
            Impressions: make([]Impression, 0, 10),
        }
    },
}

type BidRequest struct {
    Impressions []Impression
    UserID      string
    Budget      float64
}

type Impression struct {
    AdSlotID string
    Width    int
    Height   int
}

// 获取对象
func GetBidRequest() *BidRequest {
    return bidReqPool.Get().(*BidRequest)
}

// 归还对象
func PutBidRequest(req *BidRequest) {
    // 重置状态
    req.Impressions = req.Impressions[:0]
    req.UserID = ""
    req.Budget = 0
    
    // 放回池子
    bidReqPool.Put(req)
}

// 使用示例
func ProcessBid(userID string, budget float64) (*BidResponse, error) {
    // 1. 从池中获取
    req := GetBidRequest()
    defer PutBidRequest(req) // 确保归还
    
    // 2. 设置参数
    req.UserID = userID
    req.Budget = budget
    
    // 3. 执行竞价
    result, err := executeBid(req)
    if err != nil {
        return nil, err
    }
    
    return result, nil
}
```

---

## 第六部分：生产排障案例

### 6.1 高并发下的数据竞争

```
现象：偶尔出现数据不一致

排查：
1. go test -race 检测数据竞争
2. pprof 分析热点
3. 检查锁的使用

根因：多个 goroutine 同时写 map

解决方案：
1. 使用 sync.Map
2. 使用 RWMutex
3. 使用分片锁
```

```go
// 错误的做法：并发写 map
var cache = make(map[string]string)

func Set(key, value string) {
    cache[key] = value // 数据竞争！
}

func Get(key string) string {
    return cache[key] // 数据竞争！
}

// 正确的做法 1：使用 sync.Map
var safeCache sync.Map

func SetSafe(key, value string) {
    safeCache.Store(key, value)
}

func GetSafe(key string) (string, bool) {
    return safeCache.Load(key)
}

// 正确的做法 2：使用 RWMutex
var rwCache struct {
    mu   sync.RWMutex
    data map[string]string
}

func SetRW(key, value string) {
    rwCache.mu.Lock()
    defer rwCache.mu.Unlock()
    rwCache.data[key] = value
}

func GetRW(key string) string {
    rwCache.mu.RLock()
    defer rwCache.mu.RUnlock()
    return rwCache.data[key]
}

// 正确的做法 3：分片锁
type ShardedMap struct {
    shards []shard
    mask   uint64
}

type shard struct {
    mu   sync.Mutex
    data map[string]string
}

func (sm *ShardedMap) Set(key, value string) {
    idx := uint64(hash(key)) & sm.mask
    sm.shards[idx].mu.Lock()
    defer sm.shards[idx].mu.Unlock()
    sm.shards[idx].data[key] = value
}

func (sm *ShardedMap) Get(key string) (string, bool) {
    idx := uint64(hash(key)) & sm.mask
    sm.shards[idx].mu.Lock()
    defer sm.shards[idx].mu.Unlock()
    val, ok := sm.shards[idx].data[key]
    return val, ok
}
```

### 6.2 协程池饥饿

```
现象：协程池 CPU 使用率 100%，但吞吐量上不去

排查：
1. pprof goroutine 分析
2. 检查是否有 goroutine 泄漏
3. 检查是否有死锁

根因：协程池大小设置不合理

解决方案：
1. 调整 worker 数量
2. 使用动态协程池
3. 添加背压机制
```

---

## 第七部分：自测题

### 问题 1
CAS 相比互斥锁有什么优势？

<details>
<summary>查看答案</summary>

1. **无锁竞争**：用户态完成，无需内核介入
2. **避免上下文切换**：不需要线程阻塞/唤醒
3. **硬件支持**：现代 CPU 提供 CAS 指令
4. **适用场景**：简单计数器、标志位
5. **ABA 问题**：需要用带版本号的 CAS 解决

</details>

### 问题 2
sync.Pool 适合什么场景？

<details>
<summary>查看答案</summary>

1. **临时对象复用**：Request/Response
2. **减少 GC 压力**：避免频繁分配/释放
3. **不适合**：需要持久化状态的对象
4. **特点**：GC 时会被清空
5. **最佳实践**：存放可重新初始化的对象

</details>

### 问题 3
协程池相比直接启动 goroutine 有什么优势？

<details>
<summary>查看答案</summary>

1. **资源控制**：限制并发数量，防止 OOM
2. **性能稳定**：避免频繁创建/销毁 goroutine
3. **队列管理**：任务排队，防止突发流量
4. **优雅退出**：可以优雅停止所有 worker
5. **Go 实现**：WorkerPool/DynamicPool

</details>

---

*本文档基于高并发编程原理和生产实战整理。*