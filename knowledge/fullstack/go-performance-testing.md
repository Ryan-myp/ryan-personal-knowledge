# Go 进阶：性能测试/泄漏排查/Benchmark

> Race Detector/Benchmark/PPROF/内存泄漏排查/CPuprofiler

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要性能测试？

广告平台是极致性能敏感的系统：
- **竞价延迟**：RTT < 100ms
- **吞吐量**：QPS 100万+
- **稳定性**：99.99% 可用性
- **成本控制**：降低服务器成本

### Go 性能分析工具链

```
Race Detector → 并发安全
Benchmark → 基准测试
PPROF → CPU/内存/阻塞分析
Tracing → 调用链追踪
```

---

## 第二部分：Race Detector

### 2.1 数据竞争检测

```go
package main

import (
    "fmt"
    "sync"
)

// 有数据竞争的代码
type Counter struct {
    count int
}

func (c *Counter) Incr() {
    c.count++ // 数据竞争！
}

// 修复：使用原子操作
func (c *Counter) IncrAtomic() {
    atomic.AddInt32(&c.count, 1)
}

// 修复：使用互斥锁
type SafeCounter struct {
    mu    sync.Mutex
    count int
}

func (sc *SafeCounter) Incr() {
    sc.mu.Lock()
    defer sc.mu.Unlock()
    sc.count++
}

// 修复：使用 channel
func counterViaChannel() {
    ch := make(chan int)
    
    go func() {
        var count int
        for i := 0; i < 1000; i++ {
            ch <- 1
        }
        close(ch)
    }()
    
    for range ch {
        count++
    }
    fmt.Println(count)
}
```

### 2.2 Race Detector 使用

```bash
# 启用 race detector 运行测试
go test -race ./...

# 启用 race detector 运行程序
go run -race main.go

# 启用 race detector 构建二进制
go build -race -o myapp main.go
```

### 2.3 常见数据竞争场景

```go
// 场景1：map 并发读写
type Cache struct {
    data map[string]string
}

// ❌ 错误：map 并发读写 panic
func (c *Cache) Get(key string) string {
    return c.data[key]
}

func (c *Cache) Set(key, value string) {
    c.data[key] = value
}

// ✅ 正确：使用 sync.Map
type SafeCache struct {
    data sync.Map
}

func (sc *SafeCache) Get(key string) (string, bool) {
    return sc.data.Load(key)
}

func (sc *SafeCache) Set(key, value string) {
    sc.data.Store(key, value)
}

// ✅ 正确：使用读写锁
type RWLockCache struct {
    mu     sync.RWMutex
    data   map[string]string
}

func (rc *RWLockCache) Get(key string) string {
    rc.mu.RLock()
    defer rc.mu.RUnlock()
    return rc.data[key]
}

func (rc *RWLockCache) Set(key, value string) {
    rc.mu.Lock()
    defer rc.mu.Unlock()
    rc.data[key] = value
}
```

---

## 第三部分：Benchmark

### 3.1 基础 Benchmark

```go
package benchmark_test

import (
    "testing"
)

// 字符串拼接性能测试
func BenchmarkStringConcat(b *testing.B) {
    for i := 0; i < b.N; i++ {
        s := ""
        for j := 0; j < 100; j++ {
            s += fmt.Sprintf("item%d,", j)
        }
    }
}

func BenchmarkStringBuilder(b *testing.B) {
    for i := 0; i < b.N; i++ {
        var sb strings.Builder
        for j := 0; j < 100; j++ {
            sb.WriteString(fmt.Sprintf("item%d,", j))
        }
        _ = sb.String()
    }
}

func BenchmarkBytesBuffer(b *testing.B) {
    for i := 0; i < b.N; i++ {
        var buf bytes.Buffer
        for j := 0; j < 100; j++ {
            buf.WriteString(fmt.Sprintf("item%d,", j))
        }
        _ = buf.String()
    }
}

// 运行：go test -bench=. -benchmem
// 结果示例：
// BenchmarkStringConcat-8    1000    1234567 ns/op    123456 B/op    1000 allocs/op
// BenchmarkStringBuilder-8   5000    234567 ns/op     12345 B/op    100 allocs/op
// BenchmarkBytesBuffer-8     5000    123456 ns/op     12345 B/op    100 allocs/op
```

### 3.2 Benchmark 对比

```go
func BenchmarkMapLookup(b *testing.B) {
    data := make(map[string]int)
    for i := 0; i < 10000; i++ {
        data[fmt.Sprintf("key%d", i)] = i
    }
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _ = data["key5000"]
    }
}

func BenchmarkSliceLookup(b *testing.B) {
    type Item struct {
        Key string
        Val int
    }
    data := make([]Item, 10000)
    for i := 0; i < 10000; i++ {
        data[i] = Item{Key: fmt.Sprintf("key%d", i), Val: i}
    }
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        for _, item := range data {
            if item.Key == "key5000" {
                break
            }
        }
    }
}

// 结论：map 查找 O(1)，slice 查找 O(n)
// 大数据量时 map 远快于 slice
```

### 3.3 广告竞价 Benchmark

```go
func BenchmarkBidCalculation(b *testing.B) {
    req := &BidRequest{
        UserID:  "user123",
        Budget:  1000.0,
        Impression: Impression{
            AdSlotID: "slot456",
        },
    }
    
    engine := NewBidEngine()
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _, err := engine.Bid(context.Background(), req)
        if err != nil {
            b.Fatal(err)
        }
    }
}

func BenchmarkBidParallel(b *testing.B) {
    req := &BidRequest{
        UserID:  "user123",
        Budget:  1000.0,
    }
    
    engine := NewBidEngine()
    
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            _, err := engine.Bid(context.Background(), req)
            if err != nil {
                b.Fatal(err)
            }
        }
    })
}

// 运行：go test -bench=. -benchmem -benchtime=10s
```

---

## 第四部分：PPROF 性能分析

### 4.1 CPU Profile

```go
package main

import (
    "net/http"
    _ "net/http/pprof"
)

func main() {
    // 启用 pprof HTTP 端点
    go func() {
        http.ListenAndServe(":6060", nil)
    }()
    
    // 你的服务...
    http.ListenAndServe(":8080", nil)
}
```

```bash
# 采集 CPU Profile
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30

# 命令行分析
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 查看 top 10 热点函数
top 10

# 查看调用图
web

# 查看某个函数的调用栈
list MyFunction
```

### 4.2 内存 Profile

```bash
# 采集内存 Profile
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/heap

# 查看内存分配最多的函数
top -alloc_space

# 查看对象数量最多的函数
top -alloc_objects

# 比较两次采样的差异
go tool pprof -http=:8081 -base heap1.prof heap2.prof
```

### 4.3 阻塞分析

```bash
# 阻塞分析（需要启用 mutex profile）
go tool pprof -http=:8060 http://localhost:6060/debug/pprof/mutex

# 查看阻塞最严重的锁
top -focus=sync.Mutex

# 阻塞分析（阻塞等待）
go tool pprof -http=:6061 http://localhost:6060/debug/pprof/block
```

---

## 第五部分：内存泄漏排查

### 5.1 常见泄漏场景

```go
// 场景1：闭包持有大对象引用
func processData(data []byte) func() {
    return func() {
        // data 引用一直存在，无法释放
        fmt.Println(len(data))
    }
}

// 场景2：全局 Map 无限增长
var cache = make(map[string]string)

func CacheSet(key, value string) {
    cache[key] = value // 永不过期
}

// 修复：使用带过期时间的缓存
type TTLCache struct {
    data map[string]*entry
    mu   sync.RWMutex
}

type entry struct {
    value     string
    expiresAt time.Time
}

func (tc *TTLCache) Set(key, value string, ttl time.Duration) {
    tc.mu.Lock()
    defer tc.mu.Unlock()
    tc.data[key] = &entry{
        value:     value,
        expiresAt: time.Now().Add(ttl),
    }
}

// 场景3：goroutine 泄漏
func leakyWorker() {
    ch := make(chan int)
    
    go func() {
        for i := range ch {
            fmt.Println(i)
        }
    }()
    
    ch <- 1
    // ch 永远不会被关闭，goroutine 泄漏
}

// 修复：确保 channel 关闭
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
```

### 5.2 内存泄漏检测工具

```bash
# 使用 go tool trace 分析
go tool trace http://localhost:6060/debug/pprof/trace?seconds=10

# 使用 memguard 检测泄漏
go install github.com/awgh/memguard/cmd/memguard@latest
memguard check ./myapp

# 使用 go-delve 调试
dlv exec ./myapp
(dlv) breakpoints
(dlv) continue
```

---

## 第六部分：自测题

### 问题 1
什么时候应该使用 sync.Map 而不是 map + mutex？

<details>
<summary>查看答案</summary>

1. **读多写少**：sync.Map 优化了读操作
2. **键不变**：适合键集合固定的场景
3. **并发读**：sync.Map 内部使用 copy-on-write
4. **写多场景**：普通 map + RWMutex 更快
5. **广告平台**：用户画像缓存适合 sync.Map

</details>

### 问题 2
PPROF 的 heap profile 中 alloc_objects 和 inuse_objects 有什么区别？

<details>
<summary>查看答案</summary>

1. **alloc_objects**：总共分配的对象数
2. **inuse_objects**：当前仍在使用中的对象数
3. **差异**：alloc - inuse = 已释放但未回收的对象
4. **泄漏判断**：inuse_objects 持续增长 = 泄漏
5. **优化**：减少不必要的对象分配

</details>

### 问题 3
如何定位 goroutine 泄漏？

<details>
<summary>查看答案</summary>

1. **goroutine profile**：go tool pprof goroutine
2. **trace 分析**：go tool trace 查看 goroutine 状态
3. **常见原因**：channel 未关闭、context 未取消
4. **修复**：defer close(ch)、defer cancel(ctx)
5. **预防**：代码审查 + 自动化测试

</details>

---

*本文档基于 Go 性能测试原理整理。*