# Go GC垃圾回收 - 资深专家深度实现

## 一、GC算法演进

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Go GC算法演进                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Go 1.5: 标记清除 (Mark-Sweep)                                         │
│   Go 1.8: 三色标记法                                                    │
│   Go 1.9: 混合屏障 (Mixed Barrier)                                      │
│   Go 1.12: 斯塔福德算法 (Stafford Algorithm)                             │
│   Go 1.15: 写屏障优化                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、三色标记法

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        三色标记法原理                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   白色: 未扫描的对象（可能存活，可能被GC）                                │
│   灰色: 已扫描但子对象未扫描完                                            │
│   黑色: 已扫描且子对象已扫描完（确定存活）                                 │
│                                                                         │
│   规则:                                                                   │
│   1. 从Root出发，标记所有直接引用为灰色                                     │
│   2. 从灰色对象中选取一个，扫描其所有引用                                   │
│   3. 将被引用的白色对象标记为灰色                                         │
│   4. 当前对象标记为黑色                                                   │
│   5. 重复直到没有灰色对象                                                 │
│                                                                         │
│   写屏障: 防止对象被错误回收                                               │
│   - 白→黑: 正常                                                           │
│   - 灰→白: 可能触发问题，需要屏障处理                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 三、写屏障实现

```go
// src/runtime/mgc.go

// writeBarrier 写屏障
func writeBarrier(obj, ptr unsafe.Pointer) {
    if gcphase == _GCmark {
        // 在标记阶段，需要将新写入的指针加入mark stack
        markObject(ptr)
    }
}

// mixedWriteBarrier 混合写屏障
func mixedWriteBarrier(old, new unsafe.Pointer) {
    if gcphase == _GCmark {
        // 老对象已标记为黑色，新对象如果是白色需要标记为灰色
        if isWhite(new) {
            markObject(new)
        }
    }
}

// STW标记开始
func startMarkStack() {
    // 1. STW: 停止所有用户goroutine
    // 2. 建立P和M的关联
    // 3. 启动标记worker
    // 4. 启用写屏障
}

// 并发标记
func concurrentMark() {
    for _, p := range allp {
        go func() {
            for {
                // 从mark queue获取对象
                obj := grabFromMarkQueue(p)
                if obj == nil {
                    break
                }
                markObject(obj)
            }
        }()
    }
}
```

## 四、内存预算控制

```go
// src/runtime/mgc.go

const (
    minHeapSize    = 4 * 1024 * 1024      // 4MB
    maxHeapSize    = <<30                   // 1GB
    heapGoalRatio  = 2                      // 堆增长目标比率
)

type gcController struct {
    goalHeapSize  uint64    // 目标堆大小
    mem_alloc     uint64    // 已分配内存
    gc_trigger    uint64    // GC触发阈值
}

func (c *gcController) adjustGoal() {
    // 根据实际GC时间和heap size调整目标
    if gc totalTime > targetPauseTime {
        c.goalHeapSize *= 2
    } else if gc totalTime < targetPauseTime / 2 {
        c.goalHeapSize /= 2
    }
}

func (c *gcController) triggerGC() {
    if c.mem_alloc >= c.gc_trigger {
        startGC()
    }
}
```

## 五、调优参数

```go
package tuning

import "runtime"

// 查看GC统计
func printGCStats() {
    stats := runtime.MemStats{}
    runtime.ReadMemStats(&stats)
    
    println("HeapAlloc:", stats.HeapAlloc)
    println("HeapSys:", stats.HeapSys)
    println("NumGC:", stats.NumGC)
    println("GCCPUFraction:", stats.GCCPUFraction)
    println("PauseTotalNs:", stats.PauseTotalNs)
}

// 调整GC参数
func tuneGC() {
    // GOGC: GC触发阈值百分比 (默认100)
    // 降低可以减少内存占用但增加CPU开销
    runtime.GOGC = 50
    
    // GOMAXPROCS: 并发GC的P数量
    runtime.GOMAXPROCS(4)
}

// GC压力测试
func benchmarkGC() {
    var m runtime.MemStats
    
    // 分配内存
    data := make([]byte, 100*1024*1024) // 100MB
    _ = data
    
    runtime.GC()
    runtime.ReadMemStats(&m)
    
    println("After GC:")
    println("HeapAlloc:", m.HeapAlloc)
}
```

## 六、面试高频题

### Q1: Go GC为什么快？

```
A:
1. 三色标记法 + 写屏障
2. 并发标记，STW时间短
3. 斯塔福德算法避免全量扫描
4. 内存预算控制，按需GC
```

### Q2: 如何优化GC性能？

```
A:
• 减少分配：对象复用、对象池
• 避免大对象：大对象单独分配
• 调整GOGC：根据场景调整
• 使用sync.Pool缓存临时对象
```

## 七、自测题

1. 解释三色标记法的工作原理
2. 写屏障的作用是什么？
3. 如何分析GC导致的性能问题？

---

## 参考文档

- [Go GC论文](https://go.dev/doc/gc-guide)
- [Go运行时源码](https://github.com/golang/go/tree/master/src/runtime)
