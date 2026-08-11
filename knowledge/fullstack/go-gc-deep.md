# Go 垃圾回收深度解析

> 深入 Go GC 机制：三色标记法、写屏障、并发标记、混合写屏障。
> 源码级分析 runtime.mgcstack.go，包含 GC 调优。
> 适用对象：Go 工程师、性能优化工程师、系统程序员

---

## 1. GC 发展历程

### 1.1 Go 版本演进

```
┌─────────────────────────────────────────────────────────────┐
│                  Go GC 版本演进                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Go 1.1 - 1.4: 串行 GC                                       │
│  ──────────────────────────────                              │
│  ├── Stop-the-world                                         │
│  ├── 标记阶段阻塞所有 goroutine                              │
│  └── GC 停顿时间：几十到几百毫秒                              │
│                                                             │
│  Go 1.5: 并发 GC 引入                                        │
│  ──────────────────────────────                              │
│  ├── 三色标记法                                             │
│  ├── 混合写屏障                                             │
│  └── GC 停顿时间：几毫秒                                     │
│                                                             │
│  Go 1.8: 并行标记                                            │
│  ──────────────────────────────                              │
│  ├── 多个 P 并行标记                                         │
│  └── 进一步提升标记速度                                      │
│                                                             │
│  Go 1.12: 改进的混合写屏障                                   │
│  ──────────────────────────────                              │
│  ├── 减少 STW 时间                                          │
│  └── 优化内存释放                                            │
│                                                             │
│  Go 1.15: 抢占式调度优化                                     │
│  ──────────────────────────────                              │
│  ├── 减少 GC 对调度器的影响                                   │
│  └── 降低 P 阻塞时间                                         │
│                                                             │
│  Go 1.18: 更低的 P99 延迟                                    │
│  ──────────────────────────────                              │
│  ├── 改进的 STW 阶段                                         │
│  └── 优化标记 termination                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 三色标记法

### 2.1 原理

```
白、灰、黑三色标记：

白 (White): 未扫描的对象（可能被回收）
灰 (Gray): 已扫描但子对象未全部扫描
黑 (Black): 已扫描且子对象全部扫描

标记过程：
1. 从根对象开始，标记为灰色
2. 从灰色对象集合中取出一个对象，扫描其引用
3. 将引用对象标记为灰色（如果为白色）
4. 将当前对象标记为黑色
5. 重复步骤2-4直到灰色集合为空
```

### 2.2 一致性约束

```
一致性约束：
- 黑色对象不能直接指向白色对象（否则白色对象会存活）
- 灰色对象可以指向任何颜色的对象
- 白色对象只能被灰色或黑色对象指向

扫描规则：
- 扫描灰色对象时，将其引用设为黑色
- 如果引用的是白色对象，将其设为灰色
- 扫描完成后，灰色对象变为黑色
```

### 2.3 Go 实现

```go
// gc.go (简化)

package runtime

type gcPhase int

const (
    _gc_off gcPhase = iota  // GC 关闭
    gcmark                    // 标记阶段
    _gcmarktermination        // 标记终止
    gcdrain                   // 排水阶段
    _gcstoptheworld           // STW
)

type_gcWork struct {
    wbuf      wbBuf        // 工作缓冲
    remaining uint32       // 剩余工作
}

// 三色标记主循环
func gcDrain(w *gcWork, flags uint32) {
    for w.remaining > 0 {
        // 从标记队列中取出对象
        obj := markone(w.pop())
        
        // 扫描对象，标记子对象
        scanobject(obj)
        
        w.remaining--
        
        // 检查是否需要触发后台 GC
        if gcBgMarkPrepare() {
            break
        }
    }
}
```

---

## 3. 写屏障

### 3.1 写屏障类型

```
┌─────────────────────────────────────────────────────────────┐
│                    写屏障类型                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  预写屏障 (Pre-write Barrier)                                │
│  ──────────────────────────                                  │
│  ├── 在指针更新前执行                                         │
│  ├── 确保新值被正确标记                                       │
│  └── 优点：标记简单                                           │
│  └── 缺点：需要暂停写操作                                     │
│                                                             │
│  后写屏障 (Post-write Barrier)                               │
│  ──────────────────────────                                  │
│  ├── 在指针更新后执行                                         │
│  ├── 确保旧值被正确标记                                       │
│  └── 优点：不影响写性能                                       │
│  └── 缺点：标记复杂                                           │
│                                                             │
│  混合写屏障 (Mixed-write Barrier)                            │
│  ──────────────────────────                                  │
│  ├── 结合预写和后写屏障                                       │
│  ├── Go 1.8+ 使用                                             │
│  └── 在标记开始时写指针为黑色，之后写指针为白色               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 混合写屏障

```
混合写屏障过程：

1. 标记开始时：
   - 所有新写的指针都标记为黑色
   - 确保不会出现白色对象指向黑色对象的情况

2. 标记过程中：
   - 扫描黑色对象，标记其引用
   - 如果引用是白色，标记为灰色

3. 标记结束时：
   - 所有灰色对象变为黑色
   - 剩余的白色对象被回收
```

### 3.3 Go 实现

```go
// writebarrier.go (简化)

package runtime

// 写屏障内联函数
func writeBarrierPtr(oldptr, newptr unsafe.Pointer) {
    if writeBarrierEnabled {
        // 混合写屏障实现
        if gcphase == _gcmark {
            // 标记阶段：将新值标记
            if isWhite(newptr) {
                markroot(newptr, _RootKind)
            }
        }
    }
    
    // 实际写入
    *(*unsafe.Pointer)(oldptr) = newptr
}

// 编译期间插入写屏障
//go:nosplit
func wbBufFlush() {
    // 刷新写屏障缓冲区
}
```

---

## 4. GC 阶段

### 4.1 完整流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Go GC 完整流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. STW Mark Termination                                    │
│  ──────────────────────────                                  │
│  ├── 暂停所有 goroutine                                      │
│  ├── 完成最后的标记工作                                       │
│  └── 设置写屏障                                              │
│                                                             │
│  2. Concurrent Mark                                          │
│  ──────────────────────────                                  │
│  ├── 并发标记存活对象                                         │
│  ├── 多个 P 并行标记                                          │
│  └── 使用三色标记法                                           │
│                                                             │
│  3. STW Sweep Termination                                   │
│  ──────────────────────────                                  │
│  ├── 暂停所有 goroutine                                      │
│  ├── 完成最后的清理工作                                       │
│  └── 切换标记状态                                            │
│                                                             │
│  4. Concurrent Sweep                                         │
│  ──────────────────────────                                  │
│  ├── 并发回收未使用内存                                       │
│  ├── 多个 P 并行扫描                                          │
│  └── 归还内存给操作系统                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 源码实现

```go
// mgc.go (简化)

package runtime

func gcStart(trigger gcTrigger) {
    // 检查是否需要启动 GC
    if !gcBlackenEnabled {
        return
    }
    
    // 启动后台 GC 标记
    if trigger.kind == gcTriggerTime {
        gcBgMarkStartWorkers()
    }
    
    // STW 标记终止
    gcMarkDone()
    
    // 并发标记
    gcDrainAll()
    
    // STW 清理终止
    gcSweepDone()
    
    // 并发清理
    gcSweep()
}

// 后台标记工作
func gcBgMarkStartWorkers() {
    // 启动标记工作者
    for i := 0; i < gomaxprocs; i++ {
        gf := gfget()
        gf.runfn = gcBgMarkWorker
        gfrun(gf)
    }
}
```

---

## 5. GC 调优

### 5.1 GOGC 环境变量

```bash
# 调整 GC 目标百分比
export GOGC=100    # 默认值，堆增长100%时触发GC
export GOGC=50     # 更激进的GC，减少内存使用
export GOGC=200    # 更保守的GC，减少CPU开销

# 查看当前设置
go tool trace trace.out
```

### 5.2 监控 GC

```go
// gc_monitor.go

package main

import (
    "runtime"
    "time"
)

func main() {
    var stats runtime.MemStats
    
    // 定期收集 GC 统计
    go func() {
        for {
            runtime.ReadMemStats(&stats)
            
            println("HeapAlloc:", stats.HeapAlloc)
            println("HeapSys:", stats.HeapSys)
            println("HeapIdle:", stats.HeapIdle)
            println("HeapInuse:", stats.HeapInuse)
            println("GCNext:", stats.NextGC)
            println("GCCycle:", stats.NumGC)
            println("PauseTotalNs:", stats.PauseTotalNs)
            
            time.Sleep(time.Second)
        }
    }()
    
    // 业务逻辑...
}
```

### 5.3 pprof 分析

```bash
# 获取 GC 信息
go tool pprof http://localhost:6060/debug/pprof/heap

# 查看 GC 时间分布
go tool pprof -alloc_space http://localhost:6060/debug/pprof/heap

# 查看 GC 停顿
pprof> list runtime.gcbarrier
```

---

## 6. 实战案例

### 6.1 GC 停顿过长

**症状**: 应用响应延迟突增

**排查**:
```go
// 开启 GC 追踪
go tool trace trace.out

# 分析 trace
go tool trace -http=:8080 trace.out
```

**解决方案**:
```go
// 1. 调整 GOGC
runtime.SetGCPercent(50)

// 2. 减少分配
// - 使用对象池
pool := sync.Pool{
    New: func() interface{} {
        return &Buffer{}
    },
}

// - 减少临时对象
buf := make([]byte, 0, 1024)  // 预分配

// 3. 使用内存映射文件
```

### 6.2 内存泄漏

**症状**: 内存持续增长，GC 无法回收

**排查**:
```bash
# 查看 goroutine 泄漏
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 查看堆分配
go tool pprof -alloc_objects http://localhost:6060/debug/pprof/heap
```

**解决方案**:
```go
// 1. 检查闭包捕获
// ❌ 错误：捕获大量数据
go func() {
    data := make([]byte, 10*1024*1024)
    // ...
}()

// ✅ 正确：只捕获必要数据
go func(x int) {
    // ...
}(x)

// 2. 使用 weak reference
import "runtime/cgocall"
```

---

## 7. GC 内部结构

### 7.1 内存管理结构

```go
// mcache.go (简化)

type mcache struct {
    spanclass spanClass
    free      *mspan    // 空闲 span
    full      *mspan    // 满的 span
    large     uintptr   // 大对象分配器
}

type mcentral struct {
    spans   [1 << spanShift]*mspan  // span 数组
    nonempty mSpanList              // 非空列表
    empty   mSpanList              // 空列表
}
```

### 7.2 Span 管理

```
Span 结构：

┌─────────────────────────────────────────────────────────────┐
│                    mspan 结构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  spanClass: 类                                              │
│  flags: 标志                                                │
│  refillGen: 填充代                                           │
│  refillAlloc: 填充分配                                        │
│  nelems: 元素数量                                            │
│  allocBits: 分配位图                                         │
│  gcBits: GC 位图                                            │
│  busy: 忙碌指针                                              │
│  limit: 限制指针                                             │
│  array: 元素数组                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 总结

### 8.1 核心原理回顾

| 概念 | 说明 |
|------|------|
| 三色标记 | 白/灰/黑标记存活对象 |
| 写屏障 | 保证标记一致性 |
| 并发 GC | 标记和清理与业务并发 |
| GOGC | 控制 GC 触发时机 |

### 8.2 调优建议

- [ ] 监控 GC 停顿时间
- [ ] 合理设置 GOGC
- [ ] 减少临时对象分配
- [ ] 使用对象池复用
- [ ] 分析 pprof 热点

---

*最后更新：2026-08-11*
*作者：Ryan*
