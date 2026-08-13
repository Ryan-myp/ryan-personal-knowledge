# Go 内存模型深度解析

> 深入Go内存模型：堆栈分配、逃逸分析、内存对齐、垃圾回收。
> 源码级分析，包含性能调优实践。
> 适用对象：Go工程师、系统工程师

---

## 1. 堆栈分配

### 1.1 分配策略

```
Go 内存分配策略：

┌─────────────────────────────────────────────────────────────┐
│                     内存分配器                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  小对象 (<32KB)                                             │
│  ├── mcache (每P私有)                                       │
│  │   ├── sizeclass 0-51 (8B-256B)                          │
│  │   ├── sizeclass 52-67 (288B-8KB)                        │
│  │   └── sizeclass 68-71 (8KB-32KB)                        │
│  └── mcentral (全局共享)                                     │
│                                                             │
│  大对象 (≥32KB)                                             │
│  └── mheap (直接分配)                                       │
│                                                             │
│  栈分配                                                      │
│  └── Goroutine 栈 (初始2KB，动态扩展)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现内存分配

```go
// memory_allocator.go

package memory

import (
    "unsafe"
)

type mcache struct {
    small [numSpanClasses]*mspan
    large [numSpanClasses]*mspan
}

type mspan struct {
    next      *mspan
    prev      *mspan
    startAddr uintptr
    npages    uintptr
    shape     spanClass
    state     spanState
    allocBits bitvector
}

type mheap struct {
    lock mutex
    pages pagemap
    free [numSpanClasses]freeList
    allocated uint64
}

func (c *mcache) alloc(size uintptr, typ *_type) unsafe.Pointer {
    if size <= maxSmallSize {
        sc := sizeclass(size)
        sp := c.small[sc]
        if sp == nil || sp.base() == 0 {
            sp = c.refill(sc, size)
        }
        return sp.alloc(size)
    }
    return c.largeAlloc(size, typ)
}
```

---

## 2. 逃逸分析

### 2.1 分析规则

```
逃逸分析规则：

├── 栈分配 (不逃逸)
│   ├── 局部变量，生命周期不超过函数
│   ├── 函数返回值，调用者不保存
│   └── 数组元素，数组在栈上
│
└── 堆分配 (逃逸)
    ├── 局部变量，生命周期超过函数
    ├── 函数返回值，调用者保存
    ├── 接口值，动态类型
    └── 大数组，栈空间不足
```

### 2.2 Go 实现逃逸分析

```go
// escape_analysis.go

package memory

type EscapeAnalyzer struct {
    stackDepth int
    heapObjects []*HeapObject
}

type HeapObject struct {
    Type string
    Size uintptr
    StackTrace []uintptr
}

func (ea *EscapeAnalyzer) Analyze(fn func()) []HeapObject {
    // 模拟逃逸分析
    var result []HeapObject
    
    // 分析函数体内的内存分配
    // ...
    
    return result
}

// 逃逸示例
func escapeExample() {
    // 不逃逸 - 栈分配
    a := [100]int{1, 2, 3}
    _ = a
    
    // 逃逸 - 堆分配
    b := make([]int, 100)
    _ = b
    
    // 逃逸 - 堆分配
    c := &struct{ x int }{1}
    _ = c
}
```

---

## 3. 内存对齐

### 3.1 对齐规则

```
内存对齐规则：

├── 基本类型对齐
│   ├── bool: 1 字节
│   ├── int8/uint8: 1 字节
│   ├── int16/uint16: 2 字节
│   ├── int32/uint32/float32: 4 字节
│   ├── int64/uint64/float64: 8 字节
│   └── pointer: 8 字节 (64位)
│
├── 结构体对齐
│   ├── 最大对齐成员决定结构体对齐
│   └── 总大小必须是最大对齐的整数倍
│
└── 数组对齐
    └── 元素对齐决定数组对齐
```

### 3.2 Go 实现对齐优化

```go
// alignment.go

package memory

import "unsafe"

type AlignedStruct struct {
    A bool    // 1 byte
    _ [7]byte // padding
    B int64   // 8 bytes
    C int32   // 4 bytes
    _ [4]byte // padding
}

// 优化前
type BadStruct struct {
    A bool    // 1 byte
    B int64   // 8 bytes (需要8字节对齐)
    C int32   // 4 bytes
}
// 总大小: 24 bytes (含padding)

// 优化后
type GoodStruct struct {
    A bool    // 1 byte
    _ [7]byte // padding
    B int64   // 8 bytes
    C int32   // 4 bytes
    _ [4]byte // padding
}
// 总大小: 24 bytes (相同，但访问更高效)

func checkAlignment() {
    var s GoodStruct
    println(unsafe.Offsetof(s.A)) // 0
    println(unsafe.Offsetof(s.B)) // 8
    println(unsafe.Offsetof(s.C)) // 16
    println(unsafe.Sizeof(s))     // 24
}
```

---

## 4. 垃圾回收

### 4.1 Tri-color Mark-Sweep

```
三色标记清除算法：

┌─────────────────────────────────────────────────────────────┐
│                    GC 工作流程                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  阶段1: 写屏障                                             │
│  └── 记录指针变更                                           │
│                                                             │
│  阶段2: 标记                                               │
│  ├── 白色: 未访问                                          │
│  ├── 灰色: 已访问，子节点未扫描                             │
│  └── 黑色: 已访问，子节点已扫描                             │
│                                                             │
│  阶段3: 扫描                                               │
│  └── 遍历灰色节点，标记子节点                               │
│                                                             │
│  阶段4: 清理                                               │
│  └── 回收白色节点                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现 GC

```go
// gc.go

package memory

import (
    "runtime"
    "sync"
)

type GC struct {
    state    GCState
    mu       sync.Mutex
    rootSet  []unsafe.Pointer
    work     gcWork
}

type GCState int

const (
    GCIdle GCState = iota
    GCRunning
    GCGrabbing
)

type gcWork struct {
    bufs [2]gcBgMarkWork
    wbufp uintptr
}

type gcBgMarkWork struct {
    roots []unsafe.Pointer
    marks []*mspan
}

func (gc *GC) Start() {
    gc.mu.Lock()
    defer gc.mu.Unlock()
    
    if gc.state == GCIdle {
        gc.state = GCRunning
        go gc.markRoots()
        go gc.scanWork()
    }
}

func (gc *GC) markRoots() {
    // 标记根集合
    for _, root := range gc.rootSet {
        gc.mark(root)
    }
}

func (gc *GC) mark(obj unsafe.Pointer) {
    // 三色标记
    // ...
}

func (gc *GC) stopTheWorld() {
    runtime.GCStopTheWorld()
}

func (gc *GC) startTheWorld() {
    runtime.GCStartTheWorld()
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 堆栈分配 | 内存管理 |
| 逃逸分析 | 优化决策 |
| 内存对齐 | 性能优化 |
| GC | 垃圾回收 |

### 5.2 最佳实践

- [ ] 减少堆分配
- [ ] 避免逃逸
- [ ] 合理对齐
- [ ] 监控GC暂停

---

*最后更新：2026-08-12*
*作者：Ryan*
