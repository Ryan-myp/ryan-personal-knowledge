# Go GC垃圾回收 - 资深专家深度实现

## 一、GC算法

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Go GC工作流程                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Phase 1: STW Mark Init (短暂)                                        │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  • 标记根对象                                                    │   │
│   │  • 准备三色标记                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                      │
│                    ▼                                                      │
│   Phase 2: Concurrent Mark (并发标记)                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  • 标记所有可达对象                                              │   │
│   │  • 写屏障记录内存变更                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                      │
│                    ▼                                                      │
│   Phase 3: STW Mark Termination (短暂终止)                               │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  • 完成剩余标记                                                  │   │
│   │  • 扫描G stack                                                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                      │
│                    ▼                                                      │
│   Phase 4: Concurrent Sweep (并发回收)                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  • 回收未标记对象                                                │   │
│   │  • 释放内存到scavenge队列                                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、写屏障

```go
// Go 3色标记法
type Color int

const (
    White Color = iota
    Gray
    Black
)

// 混合写屏障
func writeBarrier(ptr unsafe.Pointer, newval uintptr) {
    // 新写入的值标记为灰色
    markObject(newval, Gray)
    
    // 旧值如果为灰色，需要重新标记
    oldVal := readPointer(ptr)
    if isGray(oldVal) {
        reMarkObject(oldVal)
    }
}
```

## 三、内存管理

```c
// src/runtime/mgc.go
type mheap struct {
    spans           **span
    free            [np]mSpanList  // 每sizeclass一个空闲列表
    allspans        **span
    spanset         [pageSize / spanBytes]byte
}

type mcentral struct {
    locks    mutex
    spans    mSpanList      // 有空闲对象的span
    full     mSpanList      // 已满的span
    nonempty mSpanList      // 有垃圾的span
}

type mcache struct {
    free            [np]mspan        // 每sizeclass一个span
    alloc           [np]uintptr      // 每个sizeclass的已分配数
}
```

## 四、面试高频题

### Q1: Go GC为什么快？

```
A:
1. 三色标记法
2. 写屏障技术
3. 并发标记
4. 混合写屏障 (Go 1.8+)
```

### Q2: 如何调优GC？

```
A:
1. GOGC环境变量 (默认100)
2. GOMEMLIMIT (Go 1.19+)
3. 减少对象分配
4. 使用对象池 sync.Pool
```

## 五、自测题

1. 解释三色标记法原理
2. 如何实现并发回收？
3. GC触发条件是什么？

---

## 参考文档

- [Go源码mgc.go](https://github.com/golang/go/blob/master/src/runtime/mgc.go)
- [Go GC白皮书](https://go.dev/doc/gc-guide)
