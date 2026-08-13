# Go 运行时深度解析

> 深入 Go 运行时：Goroutine 调度器、GC 机制、内存分配、调度优化。
> 适用对象：Go 开发者、性能优化工程师

---

## 1. Goroutine 调度模型

### 1.1 GMP 模型

```
┌─────────────────────────────────────────────────────────────────┐
│                     Go Runtime GMP 调度                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  M (Machine) - 操作系统线程                                      │
│  ├── P (Processor) - 处理器，维护本地 RunQueue                   │
│  │   └── G (Goroutine) - 用户态协程                            │
│  │       ├── stack (2KB-几MB 动态扩容)                          │
│  │       ├── PC (程序计数器)                                    │
│  │       └── state (running/waiting/runnable)                   │
│  │                                                               │
│  全局队列 (Global RunQueue):                                     │
│  ├── 当 P 本地队列满时 (正常: 32, 偷窃: 建议 1)                  │
│  └── 当所有 P 都空闲时，从全局队列获取                          │
│                                                                 │
│  调度流程:                                                       │
│  1. G → P 本地队列 (运行中)                                     │
│  2. P 本地队列满 → 放入全局队列                                 │
│  3. 系统调用阻塞 → P 被阻塞，创建新 M 持有 P                     │
│  4. 网络 I/O 阻塞 → HandOff (移交 P)                           │
│  5. 时间片耗尽 → 主动让出 (yield)                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 工作窃取 (Work Stealing)

```go
// 伪代码
func (p *p) stealWork() *g {
    // 从其他 P 的本地队列偷取一半
    for _, victim := range allPs {
        if g := victim.localq.stealHalf(); g != nil {
            return g
        }
    }
    // 从全局队列获取
    return gloabalRunq.pop()
}
```

---

## 2. GC 机制

### 2.1 Tri-Color Mark-Sweep

```
┌─────────────────────────────────────────────────────────────────┐
│                     三色标记法                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  白色: 未扫描                                                  │
│  黑色: 已扫描，且子对象已扫描                                   │
│  灰色: 已扫描，但子对象未完全扫描                               │
│                                                                 │
│  标记阶段:                                                      │
│  1. 从根对象开始，标记为灰色                                     │
│  2. 从灰色队列取出，标记子对象为灰色，自身变为黑色               │
│  3. 重复直到灰色队列为空                                        │
│                                                                 │
│  写屏障 (Write Barrier):                                       │
│  ├── 预写屏障 (Pre-write): 记录旧值                             │
│  └── 后写屏障 (Post-write): 记录新值                            │
│                                                                 │
│  清扫阶段: 遍历所有 span，回收白色对象                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 并发 GC 优化

```go
// 触发 GC 条件
heapGoal = int64(gcTriggerCountheaptop * 0.5)  // 堆增长 50%
heapGoal = int64(gogc) * memstats.last_gc_size  // gogc 参数控制

// GOGC 默认值: 100 (堆增长 100% 时触发)
// GODEBUG=gctrace=1 开启 GC 日志
```

---

## 3. 内存分配

### 3.1 多级分配器

```
┌─────────────────────────────────────────────────────────────────┐
│                     Go 内存分配器                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  对象大小分类:                                                   │
│  ├── small < 16KB  → MCache (per-P)                           │
│  │   └── 细分: 8B, 16B, 32B, ..., 16KB 共 67 类               │
│  ├── 16KB <= size < 2MB → MSpan (页分配器)                     │
│  └── >= 2MB → 直接 mmap                                       │
│                                                                 │
│  MCache:                                                        │
│  ├── 每个 P 独占，避免锁竞争                                   │
│  ├── 缓存常见大小的对象                                        │
│  └── 定期 flush 到 MCentral                                   │
│                                                                 │
│  MSpan:                                                         │
│  ├── 管理 8KB-2MB 的内存块                                     │
│  ├── 由 MCentral 分配/回收                                     │
│  └── 基于 Buddy System 思想                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 性能优化实践

```go
// 1. 避免不必要的内存分配
var buf bytes.Buffer
buf.Grow(1024) // 预分配

// 2. 复用对象
var pool = sync.Pool{
    New: func() interface{} { return new(bytes.Buffer) },
}
buf := pool.Get().(*bytes.Buffer)
defer pool.Put(buf)

// 3. 减少锁竞争
// 使用 per-Goroutine 缓存
type localStats struct {
    count int64
}
var local = sync.Map{} // 或直接使用 per-P slice

// 4. 栈溢出防护
// 递归深度 > 10000 考虑迭代
```

---

## 5. 实践 Checklist

- [ ] 使用 `go tool trace` 分析调度
- [ ] 监控 GC 暂停时间 (目标 < 100μs)
- [ ] 大对象 (>32KB) 避免频繁分配
- [ ] 复用 buffer 和 channel
- [ ] 避免全局变量 hot path

---

**参考**: Go Runtime 源码、kenai.dev、Dave Cheney 系列文章
