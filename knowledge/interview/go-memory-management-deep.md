# Go内存管理深入 - 资深专家深度实现

## 一、内存层次

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Go内存层次结构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Stack (栈)                                                           │
│   ├── 每个Goroutine独立                                                 │
│   ├── 初始2KB，动态扩展                                                 │
│   └── 线程本地存储(TLS)                                                  │
│                                                                         →
│   Heap (堆)                                                            │
│   ├── Arena: 64MB大内存块                                                │
│   ├── mcache: Per-P缓存，避免竞争                                        │
│   └── mcentral: 中等大小对象                                              │
│                                                                         →
│   Span (跨度)                                                          │
│   ├── 连续内存单元                                                       │
│   ├── class: 对象大小类别                                                │
│   └── free list: 空闲对象链                                               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Arena分配

```go
// arena.go
type Arena struct {
    base unsafe.Pointer
    size uintptr
    busy *busyAlloc
}

func (a *Arena) alloc(n uintptr, align uintptr) unsafe.Pointer {
    // 对齐分配
    end := a.base + a.size
    cur := ptrmaskptr(a.base)
    
    // 找合适空间
    for cur + n <= end {
        if !busyAlloc.isBusy(cur, n) {
            busyAlloc.mark(cur, n)
            return unsafe.Pointer(cur)
        }
        cur += PageSize
    }
    
    // 分配新span
    return a.grow(n, align)
}
```

## 三、面试高频题

### Q1: 栈和堆如何选择？

```
A:
1. 栈: 生命周期明确的局部变量
2. 堆: 逃逸变量/闭包捕获
3. 逃逸分析决定
```

### Q2: 如何优化内存？

```
A:
1. 对象池复用
2. 避免分配热点路径
3. 使用[]byte替代string
```

## 四、自测题

1. 解释内存层次
2. 如何实现Arena分配？
3. 如何处理内存碎片？

---

## 参考文档

- [Go内存分配器](https://github.com/golang/go/blob/master/src/runtime/mheap.go)
- [Go运行时源码](https://github.com/golang/go/tree/master/src/runtime)
