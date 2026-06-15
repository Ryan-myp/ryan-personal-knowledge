# Go 内存泄漏排查实战

> Goroutine 泄漏/闭包引用/缓存无限增长/Channel 未关闭

---

## 第一部分：入门引导（5 分钟速览）

### Go 内存泄漏常见场景

| 场景 | 现象 | 根因 |
|------|------|------|
| Goroutine 泄漏 | 内存持续增长 | Channel 未关闭 |
| 闭包引用 | 大对象无法释放 | 闭包持有引用 |
| 缓存无限增长 | OOM | 无过期时间的 Map |
| 全局变量 | 内存不释放 | 全局引用 |

---

## 第二部分：Goroutine 泄漏排查

### 2.1 泄漏检测

```bash
# 查看 goroutine 数量
go tool pprof -http=:6060 http://localhost:6060/debug/pprof/goroutine

# 命令行查看
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 查看 top 10 goroutine
top 10

# 查看 goroutine 堆栈
list myLeakyFunction
```

### 2.2 常见泄漏模式

```go
// 场景1: Channel 未关闭
func leakyWorker() {
    ch := make(chan int)
    
    go func() {
        for i := range ch {  // ch 永远不会关闭
            fmt.Println(i)
        }
    }()
    
    ch <- 1
    // ch 永远不会被关闭，goroutine 泄漏
}

// 修复: 确保 channel 关闭
func safeWorker() {
    ch := make(chan int)
    
    go func() {
        defer close(ch)
        for i := 0; i < 10; i++ {
            ch <- i
        }
    }()
    
    for v := range ch {
        fmt.Println(v)
    }
}

// 场景2: Context 未取消
func leakyWithContext() {
    ctx, cancel := context.WithCancel(context.Background())
    
    go func() {
        select {
        case <-ctx.Done():  // cancel() 永远不会被调用
            return
        case <-time.After(1 * time.Hour):
        }
    }()
    
    // 缺少 defer cancel()
}

// 修复: 使用 defer cancel()
func safeWithContext() {
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()  // 确保取消
    
    go func() {
        select {
        case <-ctx.Done():
            return
        case <-time.After(1 * time.Hour):
        }
    }()
}

// 场景3: 定时器未停止
func leakyTimer() {
    timer := time.NewTimer(1 * time.Hour)
    // timer.Stop() 永远不会被调用
}

// 修复: 确保停止定时器
func safeTimer() {
    timer := time.NewTimer(1 * time.Hour)
    defer timer.Stop()
}
```

---

## 第三部分：闭包引用泄漏

### 3.1 闭包引用分析

```go
// 场景1: 闭包持有大对象引用
func processData(data []byte) func() {
    return func() {
        // data 引用一直存在，无法释放
        fmt.Println(len(data))
    }
}

// 修复: 使用局部变量
func processDataFixed(data []byte) func() {
    size := len(data)  // 只保留需要的数据
    return func() {
        fmt.Println(size)
    }
}

// 场景2: 全局 Map 无限增长
var cache = make(map[string]string)

func CacheSet(key, value string) {
    cache[key] = value  // 永不过期
}

// 修复: 使用带过期时间的缓存
type TTLCache struct {
    data    map[string]*entry
    mu      sync.RWMutex
    ttl     time.Duration
    cleanup *time.Ticker
}

type entry struct {
    value     string
    expiresAt time.Time
}

func NewTTLCache(ttl time.Duration) *TTLCache {
    tc := &TTLCache{
        data:  make(map[string]*entry),
        ttl:   ttl,
        cleanup: time.NewTicker(1 * time.Minute),
    }
    
    go tc.cleanupLoop()
    return tc
}

func (tc *TTLCache) Set(key, value string) {
    tc.mu.Lock()
    defer tc.mu.Unlock()
    
    tc.data[key] = &entry{
        value:     value,
        expiresAt: time.Now().Add(tc.ttl),
    }
}

func (tc *TTLCache) cleanupLoop() {
    for range tc.cleanup.C {
        tc.mu.Lock()
        now := time.Now()
        for key, entry := range tc.data {
            if now.After(entry.expiresAt) {
                delete(tc.data, key)
            }
        }
        tc.mu.Unlock()
    }
}
```

---

## 第四部分：PPROF 内存分析

### 4.1 Heap Profile 分析

```bash
# 采集内存 Profile
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/heap

# 查看内存分配最多的函数
top -alloc_space

# 查看对象数量最多的函数
top -alloc_objects

# 查看当前驻留内存
top -inuse_space

# 比较两次采样的差异
go tool pprof -http=:8081 -base heap1.prof heap2.prof
```

### 4.2 内存泄漏判断

```
alloc_objects > inuse_objects = 可能存在泄漏
alloc_space > inuse_space = 可能存在泄漏

判断标准:
1. inuse_objects 持续增长 = 泄漏
2. alloc_objects 稳定 = 正常
3. 比较不同时间点的 heap profile

优化策略:
1. 减少不必要的对象分配
2. 使用 sync.Pool 复用对象
3. 及时释放大对象引用
4. 使用 defer 确保资源释放
```

---

## 第五部分：自测题

### 问题 1
如何检测 goroutine 泄漏？

<details>
<summary>查看答案</summary>

1. go tool pprof goroutine
2. 监控 goroutine 数量趋势
3. 检查 channel 是否关闭
4. 检查 context 是否取消
5. 检查定时器是否停止

</details>

### 问题 2
闭包引用导致泄漏怎么解决？

<details>
<summary>查看答案</summary>

1. 只保留需要的数据
2. 使用局部变量替代大对象
3. 及时置 nil 释放引用
4. 使用 sync.Pool 复用对象
5. Go 实现: 闭包只捕获必要字段

</details>

### 问题 3
Heap Profile 中 alloc_objects 和 inuse_objects 有什么区别？

<details>
<summary>查看答案</summary>

1. alloc_objects: 总共分配的对象数
2. inuse_objects: 当前仍在使用中的对象数
3. 差异 = 已释放但未回收的对象
4. inuse_objects 持续增长 = 泄漏
5. 优化: 减少不必要的对象分配

</details>

---

*本文档基于 Go 内存泄漏排查经验整理。*