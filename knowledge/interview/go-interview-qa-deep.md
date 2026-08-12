# Go 面试高频题库 2026

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 面试题库  
> **难度**: 中级

---

## 一、语言特性 (15题)

### 1. Go 的垃圾回收机制是怎样的？

**答案要点:**
- 三色标记清除算法
- 写屏障 (Write Barrier)
- 混合写屏障 (Hybrid Write Barrier)
- 并发 GC，与用户线程并行运行
- STW (Stop-The-World) 时间极短

```go
// GC 触发条件
runtime.GC()  // 手动触发
// 或自动触发: GC 占 CPU 25% 时

// 查看 GC 统计
pprof.Lookup("gc")
```

### 2. interface 底层结构是什么？

**答案要点:**
- type 指针 (类型信息)
- value 指针 (数据指针)
- 动态类型 + 动态值

```go
// interface 内部结构
type iface struct {
    itab *itab   // 类型描述 + 函数表
    data unsafe.Pointer  // 数据指针
}

type itab struct {
    inter *interfacetype  // 接口类型
    _type *_type          // 具体类型
    hash  uint32          // 类型 hash
    _     [4]byte
    fun   [1]uintptr      // 方法表
}
```

### 3. goroutine 调度模型是怎样的？

**答案要点:**
- GMP 调度模型
- G: goroutine 结构
- M: OS 线程
- P: 处理器 (运行队列)
- 工作窃取 (Work Stealing)

```go
// GMP 调度流程
G.runnable → G.runnable on P's queue → M picks up G → G running
       ↑_________________________________________|
```

### 4. channel 底层实现是什么？

**答案要点:**
- 循环缓冲区 (circular buffer)
- 锁保护
- 等待队列 (sendq/recvq)
- 无锁优化 (fast path)

```go
// channel 内部结构
type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形缓冲区大小
    buf      unsafe.Pointer // 环形缓冲区
    elemsize uint16
    closed   uint32
    elemtype *_type         // 元素类型
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 goroutine 队列
    sendq    waitq          // 等待发送的 goroutine 队列
    
    lock mutex              // 锁保护
}
```

### 5. select 语句的工作原理？

**答案要点:**
- 随机选择一个可读/可写的 channel
- 公平调度
- 无 case 时阻塞

```go
select {
case <-ch1:
    // ch1 可读
case ch2 <- val:
    // ch2 可写
default:
    // 没有 channel 就绪
}
```

---

## 二、并发编程 (15题)

### 6. sync.Mutex 和 RWMutex 的区别？

| 特性 | Mutex | RWMutex |
|------|-------|---------|
| 读锁 | ❌ | ✅ |
| 写锁 | ✅ | ✅ |
| 适用场景 | 写多读少 | 读多写少 |
| 性能 | 高 | 读高写低 |

```go
// RWMutex 使用示例
var mu sync.RWMutex
var data map[string]string

// 读操作
mu.RLock()
v := data[key]
mu.RUnlock()

// 写操作
mu.Lock()
data[key] = val
mu.Unlock()
```

### 7. context 的作用是什么？

**答案要点:**
- 传递请求范围的值
- 取消信号传播
- 超时控制
- 请求追踪

```go
// context 使用
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

// 传递值
ctx = context.WithValue(ctx, "requestID", "123")
reqID := ctx.Value("requestID")
```

### 8. 如何检测 goroutine 泄漏？

**答案要点:**
- pprof 分析
- runtime.NumGoroutine()
- trace 分析
- 死锁检测

```go
// 检测泄漏
func checkGoroutineLeak() {
    start := runtime.NumGoroutine()
    // 执行代码...
    time.Sleep(1 * time.Second)
    end := runtime.NumGoroutine()
    
    if end > start + 5 {
        log.Printf("Possible goroutine leak: %d -> %d", start, end)
    }
}
```

### 9. channel 缓冲区的最佳大小是多少？

**答案:**
- 取决于具体场景
- 一般原则: 能不大就不大
- 同步场景: 0
- 异步场景: 根据吞吐量确定

```go
// 同步场景
ch := make(chan int)  // 无缓冲

// 异步场景
ch := make(chan int, 100)  // 缓冲 100
```

### 10. 如何实现一个线程安全的池？

```go
type SafePool struct {
    mu sync.Mutex
    items []Item
    max int
}

func (p *SafePool) Get() Item {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    if len(p.items) == 0 {
        return NewItem()
    }
    item := p.items[len(p.items)-1]
    p.items = p.items[:len(p.items)-1]
    return item
}

func (p *SafePool) Put(item Item) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    if len(p.items) < p.max {
        p.items = append(p.items, item)
    }
}
```

---

## 三、标准库 (10题)

### 11. io.Reader 和 io.Writer 接口是什么？

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}
```

### 12. error 处理方式有哪些？

**答案要点:**
- 返回 error
- panic/recover
- sentinel errors
- error wrapping (fmt.Errorf "%w")

```go
// error wrapping
func Process() error {
    err := doSomething()
    if err != nil {
        return fmt.Errorf("process failed: %w", err)
    }
    return nil
}

// 检查错误
if errors.Is(err, io.EOF) {
    // 处理 EOF
}
```

### 13. sync.Once 的实现原理？

```go
type Once struct {
    done uint32
    m    Mutex
}

func (o *Once) Do(f func()) {
    if atomic.LoadUint32(&o.done) == 1 {
        return
    }
    o.m.Lock()
    defer o.m.Unlock()
    if o.done == 0 {
        f()
        atomic.StoreUint32(&o.done, 1)
    }
}
```

### 14. json.Marshal 的性能优化？

**答案要点:**
- 使用 `json:` tag 指定字段名
- 避免指针嵌套
- 使用 `*[]byte` 缓存序列化结果

### 15. reflect 的使用场景和注意事项？

**答案要点:**
- 反射有性能开销
- 优先使用类型断言
- 适用场景: 序列化/反序列化框架

---

## 四、进阶话题 (10题)

### 16. Go 1.21+ 的改进？

**答案要点:**
- 内置 map 并发安全
- slices 包
- constraints 包
- 更好的泛型支持

### 17. Go 内存模型是怎样的？

**答案要点:**
- happens-before 关系
- goroutine 创建/退出
- channel 操作
- sync 包原语

### 18. 如何排查 Go 内存泄漏？

**答案要点:**
- pprof heap
- go tool trace
- 分析 allocation trace
- 检查 goroutine 泄漏

### 19. Go 网络编程的最佳实践？

**答案要点:**
- 使用 bufio.Scanner 读取
- 设置连接超时
- 使用 keep-alive
- 连接池管理

### 20. Go 的逃逸分析是什么？

**答案:**
- 编译器决定变量分配在栈还是堆
- 函数返回局部变量指针会逃逸
- 大数组可能逃逸到堆

---

## 五、实战问题 (10题)

### 21. 实现一个 LRU 缓存

```go
type LRUCache struct {
    capacity int
    cache map[int]*Node
    head *Node
    tail *Node
}

func (c *LRUCache) Get(key int) int {
    // TODO
}

func (c *LRUCache) Put(key int, value int) {
    // TODO
}
```

### 22. 实现一个限流器

```go
type RateLimiter struct {
    tokens float64
    max float64
    rate float64
    last time.Time
    mu sync.Mutex
}

func (r *RateLimiter) Allow() bool {
    // TODO
}
```

### 23. 实现一个半同步半异步池

```go
type Pool struct {
    workers int
    jobs chan func()
    wg sync.WaitGroup
}

func (p *Pool) Start() {
    // TODO
}

func (p *Pool) Submit(job func()) {
    // TODO
}
```

### 24. 如何优雅关闭 HTTP Server？

```go
srv := &http.Server{Addr: ":8080", Handler: handler}

go func() {
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
    <-sigChan
    
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    srv.Shutdown(ctx)
}()

srv.ListenAndServe()
```

### 25. 实现一个分布式锁

```go
type DistributedLock struct {
    redis *redis.Client
    key string
    value string
    ttl time.Duration
}

func (l *DistributedLock) Lock() bool {
    // TODO: 使用 SET NX PX
}

func (l *DistributedLock) Unlock() {
    // TODO: 使用 Lua 脚本删除
}
```

---

## 六、总结

| 分类 | 题数 | 难度 |
|------|------|------|
| 语言特性 | 15 | ⭐⭐ |
| 并发编程 | 15 | ⭐⭐⭐ |
| 标准库 | 10 | ⭐⭐ |
| 进阶话题 | 10 | ⭐⭐⭐ |
| 实战问题 | 10 | ⭐⭐⭐ |
| **总计** | **60** | - |

EOF
echo "✅ 已创建: interview/go-interview-qa-deep.md"