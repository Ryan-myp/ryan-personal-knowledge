# Go内存管理 - 资深专家深度实现

## 一、内存分配器

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Go内存分配架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   heap                                                                 │
│   ├── spans[0..n]                                                      │
│   │   ├── span[0]  (small objects: < 32KB)                             │
│   │   ├── span[1]  (large objects: >= 32KB)                            │
│   │   └── span[n]                                                      │
│   │                                                                       │
│   ├── mcache (per-P cache)                                             │
│   │   ├── tinyobj                                                      │
│   │   ├── small[n]                                                     │
│   │   └── large                                                        │
│   │                                                                       │
│   └── mheap (global heap)                                              │
│       ├── central[n]                                                   │
│       └── free                                                         │
│                                                                         │
│   特点:                                                                   │
│   • 多级缓存                                                             │
│   • 无锁分配                                                             │
│   • 自动垃圾回收                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、分配器实现

```go
// src/runtime/malloc.go
type mcache struct {
    sweepgen   uint32
    tiny       uintptr
    tinyoffset uintptr
    
    // small size classes
    small [numSpanClasses]struct {
        alloc [8]freelist
    }
    
    // large objects
    large *[maxLargeSize]*mspan
}

func (c *mcache) mallocx(size uintptr, flags uint8) unsafe.Pointer {
    if size <= maxSmallSize {
        if size < maxTinySize {
            return c.tinyalloc(size)
        }
        return c.allocklass(size, class_to_size[class])
    }
    return c.malloclarge(size, flags)
}
```

## 三、垃圾回收

```go
// 三色标记法
func gcMark() {
    // 白色: 未访问
    // 灰色: 已访问，子对象未扫描
    // 黑色: 已访问，子对象已扫描
    
    for _, root := range roots {
        if isRoot(root) {
            mark(root)
        }
    }
}

func mark(obj *Object) {
    obj.color = GRAY
    for _, child := range obj.children {
        if child.color == WHITE {
            mark(child)
        }
    }
    obj.color = BLACK
}
```

## 四、面试高频题

### Q1: Go内存分配如何避免碎片？

```
A:
1. 大小类划分
2. 边界对齐
3. 分代回收
```

### Q2: GC如何工作？

```
A:
1. 三色标记
2. 写屏障
3. 并发回收
```

## 五、自测题

1. 解释内存分配器架构
2. 如何实现无锁分配？
3. 如何优化GC性能？

---

## 参考文档

- [Go内存管理源码](https://github.com/golang/go/blob/master/src/runtime/malloc.go)
- [Go GC白皮书](https://go.dev/doc/gc-guide)
