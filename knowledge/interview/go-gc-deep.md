# Go GC垃圾回收机制 --- 资深专家深度实现

## 概述

Go的垃圾回收器采用三色标记-清除算法配合写屏障，实现低延迟的高并发GC。本文深入剖析其工作原理和优化方法。

## 一、GC算法概述

### 1.1 算法选择

```
┌─────────────────────────────────────────────────────────┐
│                  Go GC演进历史                           │
├─────────────────────────────────────────────────────────┤
│  Go 1.5: 并发标记 + 并发清除                             │
│  Go 1.8: 引入混合写屏障 (Hybrid Write Barrier)          │
│  Go 1.9: 改进STW阶段                                      │
│  Go 1.12: 引入P (Processor) 概念，进一步降低延迟         │
│  Go 1.19: 引入Stw trigger，进一步优化                   │
│  Go 1.22: 实验性并发清除 (Concurrent Deletion)           │
└─────────────────────────────────────────────────────────┘
```

### 1.2 三色标记法

```
┌─────────────────────────────────────────────────────────┐
│                    三色标记原理                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   白色 (White): 未访问的存活对象                           │
│   灰色 (Gray):  已访问，但子对象未扫描                      │
│   黑色 (Black): 已访问，且子对象已扫描                      │
│                                                          │
│   ┌──────────┐                                          │
│   │  RootSet │ ───标记──→ ┌──────────┐                  │
│   └──────────┘            │ 灰色对象 │                  │
│                           └────┬─────┘                  │
│                                │ 扫描                    │
│                           ┌────▼─────┐                  │
│                           │ 黑色对象 │                  │
│                           └──────────┘                  │
│                                                          │
│   不变式:                                                │
│   1. 黑对象指向白对象 → 必须经过写屏障标记                │
│   2. 灰对象不会变黑直到所有子对象处理完毕                 │
└─────────────────────────────────────────────────────────┘
```

## 二、GC工作流程

### 2.1 标记阶段

```go
// GC标记过程
func gcMark() {
    // 1. 标记根对象
    for _, p := range allp {
        markroot(p, markrootFunctions[i])
    }
    
    // 2. 从灰色队列驱逐对象
    for len(gcMarkWork.markrootBlocks) > 0 || 
        atomic.Loaduint64(&gcBgMarkWorker.work.bytesmark) < goal {
        
        // 并发标记
        work := draindwork(&gcBgMarkWorker.work)
        if work != nil {
            drainbheap(&work.remains, markobject)
        }
    }
}

// 标记对象
func markobject(b unsafe.Pointer) {
    // 1. 将对象标记为灰色
    scanstate := blacktogray(obj)
    
    // 2. 扫描对象内容
    switch obj.kind {
    case kindDirectIface:
        // 接口类型，标记指向的对象
        markptr(scanstate, *(*uintptr)(b))
    case kindIndir:
        // 间接类型
        markptr(scanstate, *(*uintptr)(b))
    }
}
```

### 2.2 写屏障

```go
// 混合写屏障
func writeBarrier(buf unsafe.Pointer, ptr unsafe.Pointer) {
    if gcphase == _GCmark {
        // 标记阶段：将旧值标记为灰色
        old := *(*unsafe.Pointer)(buf)
        if old != nil {
            grayobject(old)
        }
        // 设置新值
        *(*unsafe.Pointer)(buf) = ptr
    } else {
        // 非标记阶段：直接设置
        *(*unsafe.Pointer)(buf) = ptr
    }
}

// 写屏障类型
// 1. 白色写屏障: 只在新值上工作
// 2. 黑色写屏障: 只在旧值上工作  
// 3. 混合写屏障: 新旧值都处理 (Go默认)
```

### 2.3 清除阶段

```go
// GC清除过程
func gcSweep() {
    for _, m := range memstats.allheap {
        // 遍历堆页面
        for _, span := range m.spans {
            if span.needsScavenging {
                // 物理内存回收
                sysFree(unsafe.Pointer(span.base()), span.allocsize)
            }
        }
    }
}
```

## 三、GC参数调优

### 3.1 关键环境变量

```bash
# GC目标堆内存占比 (默认100%)
GOGC=100

# 限制最大堆内存
GOMEMLIMIT=1GiB

# GC模式
GOEXPERIMENT=concdelet  # 实验性并发清除

# GC跟踪
GODEBUG=gctrace=1

# GC强制触发
runtime.GC()
```

### 3.2 监控指标

```go
import "runtime"

func printGCStats() {
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    fmt.Printf("HeapAlloc: %d MB\n", stats.HeapAlloc/1024/1024)
    fmt.Printf("HeapSys: %d MB\n", stats.HeapSys/1024/1024)
    fmt.Printf("HeapIdle: %d MB\n", stats.HeapIdle/1024/1024)
    fmt.Printf("HeapReleased: %d MB\n", stats.HeapReleased/1024/1024)
    fmt.Printf("NumGC: %d\n", stats.NumGC)
    fmt.Printf("GCCPUFraction: %.2f\n", stats.GCCPUFraction)
}
```

## 四、内存泄漏检测

### 4.1 使用pprof

```go
import _ "net/http/pprof"

// 启动pprof服务端
go func() {
    http.ListenAndServe("localhost:6060", nil)
}()

// 采样堆内存
go runtime.SetMemoryProfileRate(1 << 20) // 每1MB分配采样一次
```

```bash
# 查看堆内存
go tool pprof http://localhost:6060/debug/pprof/heap

# 查看分配热点
top 10

# 生成调用图
dot -Tpng -o heap.png < heap.pb.gz

# 对比两次快照
go tool pprof -base base.pb.gz new.pb.gz
```

### 4.2 常见泄漏模式

```go
// 泄漏1: 全局map累积
var cache = make(map[string][]byte)

func handler(req *Request) {
    data := process(req)
    cache[req.ID] = data  // 永远不会释放
}

// 修复：使用带TLV的缓存
type LRUCache struct {
    items  map[string]*item
    maxLen int
}

// 泄漏2: Goroutine持有引用
func leaky() {
    ch := make(chan int)
    go func() {
        for v := range ch {
            _ = v
        }
    }()
    // ch永远不会被关闭，goroutine泄漏
}

// 泄漏3: 未取消的Context
func badContext() {
    ctx, cancel := context.WithCancel(context.Background())
    go worker(ctx)
    // 忘记调用cancel()
}
```

## 五、性能优化

### 5.1 减少分配

```go
// 使用对象池
var bufPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 4096)
    },
}

func process(data []byte) []byte {
    buf := bufPool.Get().([]byte)
    defer bufPool.Put(buf)
    
    // 重用缓冲区
    copy(buf, data)
    return buf
}
```

### 5.2 预分配容量

```go
// 预分配map容量
cache := make(map[string]int, 1000)

// 预分配slice容量
items := make([]Item, 0, 1000)
items = append(items, item1, item2, ...)
```

### 5.3 避免大对象

```go
// 大对象 (>32KB) 会直接进入大对象堆，增加GC压力
// 优化：分块处理
const chunkSize = 1024 * 1024  // 1MB

func processLargeData(data []byte) {
    for i := 0; i < len(data); i += chunkSize {
        end := i + chunkSize
        if end > len(data) {
            end = len(data)
        }
        processChunk(data[i:end])
    }
}
```

## 六、面试高频题

### 6.1 高频问题

**Q1: Go GC是什么算法？**

A: 三色标记-清除算法，配合混合写屏障实现并发标记。

**Q2: 什么是写屏障？**

A: 写屏障是在指针赋值时插入的代码，用于在并发GC期间保持内存不变式。

**Q3: 如何调优GC性能？**

A:
- 调整GOGC参数
- 减少内存分配
- 使用对象池
- 预分配容量

### 6.2 自测题

1. 画出三色标记法的工作流程
2. 解释混合写屏障的作用
3. 分析以下代码的GC行为
4. 设计一个高性能的对象池
5. 解释GOMEMLIMIT的作用

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / Go运行时
**关键词**: gc, garbage collection, mark-sweep, write barrier, pprof
