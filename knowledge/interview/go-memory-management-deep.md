# Go内存管理 - 资深专家深度实现

## 一、内存分配器

```c
// src/runtime/malloc.c
typedef struct {
    mspan   *free;      /* list of free spans */
    mspan   *all;       /* list of all spans */
    int32_t   queues[NP] /* ngowersize classes */
} mheap_t;

// 分配器层级:
// • Thread cache (mcache): per-P缓存
// • Central cache (mcentral): per-sizeclass缓存
// • Heap (mheap): 全局堆
void*
malloc(size_t size) {
    if (size < tinySize) {
        return allocateSmall(size);
    }
    if (size <= maxSmallSize) {
        return allocateCentral(size);
    }
    return allocateLarge(size);
}
```

## 二、GC标记清除

```go
package gc

type GC struct {
    state    gcPhase
    workers  int
    helpRate float64
}

type gcPhase int

const (
    _gc_reset gcPhase = iota
    gc_mark_start
    gc_mark
    gc_mark_stop
    gc_cleanup
)

func (g *GC) start() {
    // 1. STW: 标记根集
    g.stopTheWorld()
    
    // 2. 并发标记
    g.concurrentMark()
    
    // 3. 标记终止
    g.markTermination()
    
    // 4. 扫尾
    g.cleanup()
    
    // 5. 重启世界
    g.startTheWorld()
}

func (g *GC) concurrentMark() {
    // 辅助GC
    for assistWork < 0 {
        g.gcWork.put(obj)
    }
    
    // 后台GC
    go g.bgMark()
}
```

## 三、内存对齐

```go
package memory

import "unsafe"

// 内存对齐规则
type AlignedStruct struct {
    a byte    // 1字节，偏移0
    b int32   // 4字节，需要4对齐 → 填充3字节
    c int64   // 8字节，需要8对齐 → 从8开始
    d byte    // 1字节，偏移16
} // 总大小: 24字节 (1+3+4+8+1+6填充)

func alignSize(size int, alignment int) int {
    return (size + alignment - 1) &^ (alignment - 1)
}
```

## 四、面试高频题

### Q1: Go的GC为什么快？

```
A:
1. 三色标记法
2. 写屏障
3. 并发标记
4. 混合写屏障
```

### Q2: 如何优化内存分配？

```
A:
1. 对象池 (sync.Pool)
2. 内存对齐
3. 避免逃逸
```

## 五、自测题

1. 解释Go内存分配器架构
2. 如何实现零开销GC？
3. 如何优化内存使用？

---

## 参考文档

- [Go源码](https://github.com/golang/go/tree/master/src/runtime)
- [Go内存管理白皮书](https://go.dev/doc/gc-guide)
