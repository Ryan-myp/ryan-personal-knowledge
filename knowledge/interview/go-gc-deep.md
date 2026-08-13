# Go GC实现 - 资深专家深度实现

## 一、GC三色标记法

### 1.1 核心数据结构

```go
// src/runtime/mgc.go
type gcWork struct {
    buf      [gcwBufSize]uintptr
    bufIndex uint32
    bufLimit uint32
}

// GC工作队列
type gcBgMarkWorker struct {
    g         *g
    pd        *p
    gcw       gcWork
}

// GC状态
type gcPhase int

const (
    gcphaseIdle    gcPhase = 0  // GC未开始
    gcphaseMark    gcPhase = 1  // 标记阶段
    gcphaseMarkTerm gcPhase = 2 // 标记终止
    gcphaseFlush   gcPhase = 3  // 刷新阶段
)
```

### 1.2 三色标记流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      三色标记GC流程                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   阶段1: White (初始状态)                                                │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐                                   │
│   │  White  │ │  White  │ │  White  │   所有对象初始为白色               │
│   │  Object │ │  Object │ │  Object │                                   │
│   └─────────┘ └─────────┘ └─────────┘                                   │
│                                                                         →
│   阶段2: Gray (发现根对象)                                               │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐                                   │
│   │  Black  │ │  Gray   │ │  White  │   根对象标记为黑色                 │
│   └─────────┘ └─────────┘ └─────────┘   其引用对象标记为灰色             │
│                                                                         →
│   阶段3: Black (处理灰色对象)                                            │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐                                   │
│   │  Black  │ │  Black  │ │  White  │   灰色对象处理完变为黑色           │
│   └─────────┘ └─────────┘ └─────────┘   其引用对象标记为灰色             │
│                                                                         →
│   阶段4: Sweep (清理白色对象)                                            │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐                                   │
│   │  Black  │ │  Black  │ │  Sweep  │   白色对象被回收                   │
│   └─────────┘ └─────────┘ └─────────┘                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、GC触发条件

### 2.1 触发逻辑

```go
// src/runtime/mgc.go
func gcStart(trig gcTrigger) {
    // 检查是否已经GC
    if gcphase != gcphaseIdle {
        return
    }
    
    // 检查触发条件
    switch trig.kind {
    case gcTriggerTime:
        // 时间触发
        if nanotime()-memstats.last_gc_nanotime < 60*1000000000 {
            return
        }
    case gcTriggerCycle:
        // 周期触发
        if memstats.numgc >= uint32(gctrigger) {
            return
        }
    case gcTriggerHeap:
        // 堆大小触发
        if memstats.heap_live >= memstats.heap_scan {
            return
        }
    }
    
    // 开始GC
    gcWakeP()
}
```

### 2.2 目标GC比例计算

```go
// 计算目标GC比例
func gcBgMarkReady() {
    // 根据堆大小计算目标内存
    goal := memstats.heap_live * (100 + param.gcpercent) / 100
    
    // 确保不超过限制
    if goal > memstats.max_heap_size {
        goal = memstats.max_heap_size
    }
    
    // 设置新的目标
    memstats.gc_goal_live = goal
}
```

## 三、STW暂停优化

### 3.1 两阶段扫描

```go
// 阶段1: 扫描根对象
func gcMarkRootCount() int32 {
    // 计算需要扫描的根对象数量
    count := int32(0)
    
    // 栈根
    count += scanStackRoots()
    
    // 全局根
    count += scanGlobalRoots()
    
    // P根
    count += scanPRoots()
    
    return count
}

// 阶段2: 并发标记
func gcMarkWorker() {
    for {
        // 从work buffer获取对象
        obj := gcWorkGet()
        if obj == nil {
            break
        }
        
        // 标记对象
        markObject(obj)
        
        // 扫描对象引用
        scanObject(obj)
    }
}
```

### 3.2 写屏障优化

```go
// 写屏障：记录指针变更
func writeBarrierPtr(old, new uintptr) {
    // 如果old不是白对象，需要重新标记new
    if !isWhite(old) {
        // 将new加入gray set
        pushGray(new)
    }
}

// 三种写屏障
const (
    whiteToBlackBarrier = iota  // 白→黑：STW
    blackToWhiteBarrier         // 黑→白：并发
    grayToBlackBarrier          // 灰→黑：并发
)
```

## 四、并发GC实现

### 4.1 P的GC协作

```go
type p struct {
    gcBuffer      [gcBufferLen]gcWork
    gcBufferIndex uint32
    gcScanWork    int64
    gcRescanWork  int64
}

// P协助GC
func (p *p) helpGC() {
    // 获取gcWork
    work := &p.gcBuffer[p.gcBufferIndex]
    p.gcBufferIndex = (p.gcBufferIndex + 1) % gcBufferLen
    
    // 处理缓冲区的对象
    for work.bufIndex < work.bufLimit {
        obj := work.buf[work.bufIndex]
        work.bufIndex++
        
        // 标记和扫描
        markObject(obj)
        scanObject(obj)
    }
}
```

### 4.2 混合写屏障

```go
// 混合写屏障实现
type hybridWriteBarrier struct {
    enabled bool
}

func (h *hybridWriteBarrier) store(p unsafe.Pointer, new uintptr) {
    if !h.enabled {
        return
    }
    
    old := * (*uintptr)(p)
    
    // 记录变更
    if old != 0 {
        // old是灰对象，需要重新标记
        gcWorkPush(old)
    }
    
    // 写入新值
    * (*uintptr)(p) = new
    
    // new是白对象，标记为灰
    if isWhite(new) {
        gcWorkPush(new)
    }
}
```

## 五、内存回收

### 5.1 分代回收

```go
type generation struct {
    objects    []*Object
    capacity   int
    threshold  int
}

// 分代GC策略
func (g *generation) collect() {
    // 年轻代：复制回收
    if g.isYoungGen() {
        g.copyCollect()
    } else {
        // 老年代：标记-压缩
        g.markSweepCompact()
    }
}

// 复制回收
func (g *generation) copyCollect() {
    from := g.active
    to := g.other
    
    // 复制存活对象
    for _, obj := range from.objects {
        if isAlive(obj) {
            copyObject(obj, to)
        }
    }
    
    // 交换
    g.swap()
}
```

### 5.2 压缩算法

```go
// 标记-压缩算法
func markSweepCompact() {
    // 1. 标记存活对象
    markObjects()
    
    // 2. 压缩内存
    compact()
    
    // 3. 更新指针
    updatePointers()
}

// 压缩实现
func compact() {
    // 计算新地址
    var newAddr uintptr
    for _, obj := range allObjects {
        if isAlive(obj) {
            obj.newAddr = newAddr
            newAddr += obj.size
        }
    }
    
    // 移动对象
    for _, obj := range allObjects {
        if obj.newAddr != 0 {
            moveObject(obj, obj.newAddr)
        }
    }
}
```

## 六、生产环境调优

### 6.1 GC参数调整

```go
// GC参数配置
type GCConfig struct {
    GCPercent      int           // 目标GC比例
    GCLifetime     time.Duration // GC最大生命周期
    GCThreshold    int64         // GC触发阈值
    GCPreemption   bool          // 是否允许抢占
}

// 运行时调整
func init() {
    runtime/debug.SetGCPercent(100)   // 默认值
    runtime/debug.SetGCBackgroundRate(1) // 后台GC比例
}
```

### 6.2 常见问题排查

```go
// GC问题排查工具
type GCDiagnostics struct {
    gcCPUFraction float64   // GC占用CPU比例
    gcPauseTime   int64     // GC暂停时间
    gcFrequency   int64     // GC频率
}

func (d *GCDiagnostics) analyze() {
    // 收集GC统计
    stats := &runtime.MemStats{}
    runtime.ReadMemStats(stats)
    
    // 分析GC占用
    d.gcCPUFraction = float64(stats.PauseTotalNs) / 
        float64(stats.TotalAlloc)
    
    // 判断是否异常
    if d.gcCPUFraction > 0.25 {
        log.Warn("GC CPU占用过高")
    }
    
    if stats.NumGC > 100 {
        log.Warn("GC频率过高")
    }
}
```

## 七、面试高频题

### Q1: Go GC为什么快？

```
A:
1. 三色标记法：并发标记
2. 混合写屏障：减少STW
3. 分代收集：年轻代优先
4. P协作：分布式标记
```

### Q2: 如何减少GC暂停？

```
A:
1. 减少对象分配
2. 复用对象（sync.Pool）
3. 避免大对象分配
4. 调整GCPercent
```

### Q3: Write Barrier的作用？

```
A:
1. 记录指针变更
2. 保证标记一致性
3. 支持并发GC
4. 减少STW时间
```

## 八、自测题

1. 解释三色标记法原理
2. 如何减少GC暂停？
3. Write Barrier有哪些类型？

---

## 参考文档

- [Go GC源码](https://github.com/golang/go/blob/master/src/runtime/mgc.go)
- [Go GC设计文档](https://go.dev/doc/gc-guide)
