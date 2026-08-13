# Go内存管理 - 资深专家深度实现

## 一、内存模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Go内存管理模型                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   内存区域              | 大小               | 用途                      │
│   ─────────────────────┼───────────────────┼──────────────────────────│
│   Stack (每goroutine)  | 2KB-2MB            | 局部变量、函数参数        │
│   Heap                 | 动态分配            | 逃逸对象、大型数据结构    │
│   GC Heap              | 可变大小            | GC管理的堆内存           │
│   MCache (per P)       | 约8MB              | 对象缓存                   │
│   MSpan                | 可变大小            | 内存块管理                 │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、分配器实现

```go
package allocator

import (
    "unsafe"
)

// MCache 每P的内存缓存
type MCache struct {
    spans [36]*MSpan  // 不同大小class的span
}

// MSpan 内存块管理
type MSpan struct {
    baseAddr uintptr  // 起始地址
    npages   uint32   // 页数
    allocBits gcBits  // 分配位图
    freelist *mcache  // 空闲链表
}

// 对象分配
func (c *MCache) allocate(size uintptr) unsafe.Pointer {
    class := size_to_class(size)
    span := c.spans[class]
    
    if span.nelem == 0 {
        span = c.refill(class)
    }
    
    obj := span.alloc()
    span.nelem--
    return obj
}

// 分配class表
var class_to_size = [...]uintptr{
    0, 8, 16, 24, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208,
    224, 240, 256, 288, 320, 352, 384, 416, 448, 480, 512, 576, 640, 704,
    768, 1024, 1280, 1536, 2048, 3072, 4096,
}
```

## 三、面试高频题

### Q1: Go内存如何管理？

```
A:
1. MCache per-P
2. MSpan管理内存块
3. GC标记清除
```

### Q2: 如何减少GC压力？

```
A:
1. 对象池复用
2. 避免逃逸
3. 预分配大对象
```

## 四、自测题

1. 解释Go内存模型
2. 如何实现分配器？
3. 如何减少GC压力？

---

## 参考文档

- [Go Memory Model](https://go.dev/doc/gc-guide)
- [Go Runtime](https://github.com/golang/go/src/runtime/mheap.go)
