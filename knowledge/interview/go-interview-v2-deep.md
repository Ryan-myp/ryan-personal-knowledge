# Go 面试题库深度实现V2 - 扩展题库

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: 面试/Go  
> **代码密度**: 28%

---

## 新增面试题

### Q26. 如何实现一个线程安全的缓存？

```go
// 带过期时间的线程安全缓存
type TTLCache struct {
    mu       sync.RWMutex
    items    map[string]*item
    ttl      time.Duration
}

type item struct {
    value      interface{}
    expiresAt  time.Time
}

func (c *TTLCache) Get(key string) (interface{}, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    
    it, ok := c.items[key]
    if !ok || time.Now().After(it.expiresAt) {
        return nil, false
    }
    return it.value, true
}

func (c *TTLCache) Set(key string, value interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    c.items[key] = &item{
        value:     value,
        expiresAt: time.Now().Add(c.ttl),
    }
}
```

### Q27. Go 1.21+ 的调度器优化？

```go
// Go 1.21优化点:
// 1. GOMAXPROCS默认值调整
// 2. 网络轮询器改进
// 3. GC暂停时间优化
// 4. stack growth优化
```

### Q28. 如何实现一个轻量级Web框架？

```go
// 极简Web框架
type Router struct {
    routes map[string]map[string]Handler
}

func (r *Router) Handle(method, path string, handler Handler) {
    if r.routes[method] == nil {
        r.routes[method] = make(map[string]Handler)
    }
    r.routes[method][path] = handler
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
    handler, ok := r.routes[req.Method][req.URL.Path]
    if !ok {
        http.NotFound(w, req)
        return
    }
    handler(w, req)
}
```

### Q29. Context 的三种取消方式？

```go
// 1. WithCancel
ctx, cancel := context.WithCancel(parent)
cancel() // 手动取消

// 2. WithTimeout
ctx, cancel := context.WithTimeout(parent, 5*time.Second)
// 自动取消

// 3. WithDeadline
ctx, cancel := context.WithDeadline(parent, time.Now().Add(10*time.Second))
// 截止时间取消
```

### Q30. Go的内存对齐规则？

```go
// 内存对齐规则:
// 1. 结构体首地址对齐
// 2. 每个字段对齐到自身大小
// 3. 结构体总大小对齐到最大字段

type Struct struct {
    a bool    // 1 byte + 7 padding
    b int64   // 8 bytes
    c int32   // 4 bytes
    d bool    // 1 byte + 3 padding
} // 总共 24 bytes (优化后)

// 优化布局:
type Optimized struct {
    b int64   // 8 bytes
    c int32   // 4 bytes
    a bool    // 1 byte
    d bool    // 1 byte
    _  [4]byte // padding
} // 总共 24 bytes
```

---

## 自测题

1. **TTLCache如何清理过期数据？**
   - 惰性删除 + 定期清理

2. **Go 1.21调度器主要优化了什么？**
   - 网络轮询器、GC暂停、stack growth

3. **Context取消会释放资源吗？**
   - 不会自动释放，需要配合goroutine cleanup

