## 第三部分：源码级深度

### 3.1 设计模式源码

（以下内容基于 Go 源码分析，展示设计模式的实际落地）

```go
// Observer Pattern - Go 的 channel 实现
type EventPublisher struct {
    subscribers map[string][]chan interface{}
}

func (ep *EventPublisher) Subscribe(eventType string) chan interface{} {
    ch := make(chan interface{}, 100)
    ep.subscribers[eventType] = append(ep.subscribers[eventType], ch)
    return ch
}

func (ep *EventPublisher) Publish(eventType string, data interface{}) {
    for _, ch := range ep.subscribers[eventType] {
        go func(c chan interface{}) {
            c <- data
        }(ch)
    }
}

// Strategy Pattern - Go 的接口实现
type SortStrategy interface {
    Sort(data []int) []int
}

type QuickSort struct{}

func (qs *QuickSort) Sort(data []int) []int {
    if len(data) <= 1 {
        return data
    }
    // 快速排序实现
    return data
}

// Decorator Pattern - Go 的中间件实现
func LoggingMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        next.ServeHTTP(w, r)
        log.Printf("Request: %s %s %v", r.Method, r.URL.Path, time.Since(start))
    })
}

func AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if !validateToken(token) {
            http.Error(w, "Unauthorized", http.StatusUnauthorized)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

---

## 第四部分：实战排障

### 4.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| N+1 查询 | 循环中每次查数据库 | 批量查询 + 内存关联 |
| 死锁 | 多线程锁顺序不一致 | 固定锁顺序 + timeout |
| 缓存穿透 | 查询不存在的数据 | 布隆过滤器 + 空值缓存 |
| 缓存击穿 | 热点 key 过期 | 逻辑过期 + 互斥锁 |

### 4.2 排查方法论

```
问题排查流程:
1. 复现问题 → 最小化 demo
2. 定位范围 → 二分法缩小
3. 分析原因 → 看源码 / 日志 / 指标
4. 验证修复 → 单元测试 + 压测
5. 预防复发 → 加监控 + 告警
```

---

## 第五部分：自测题

### 问题 1
设计模式中的"依赖倒置"在 Go 的 interface 中如何体现？

<details>
<summary>查看答案</summary>

1. **高层模块不依赖低层模块**：都依赖抽象（interface）
2. **抽象不依赖细节**：interface 定义行为，struct 实现
3. Go 的 interface 是隐式实现，天然支持依赖倒置
4. 对比 Java 的显式 implements，Go 的鸭子类型更灵活

</details>

### 问题 2
Go 的 interface 空接口 interface{} 作为函数参数有什么代价？

<details>
<summary>查看答案</summary>

1. **类型擦除**：编译期无法检查类型正确性
2. **运行时断言**：需要 type switch 或 type assertion 还原
3. **性能开销**：interface{} 包含 type pointer + data pointer
4. **优化方案**：Go 1.18+ 的泛型可以替代 interface{} 的使用

</details>

### 问题 3
"组合优于继承"在 Go 的 struct embedding 中如何体现？

<details>
<summary>查看答案</summary>

1. **组合是 has-a**：Embedding 让结构体"拥有"另一个结构体的方法
2. **继承是 is-a**：Go 没有继承概念，避免类层次爆炸
3. **嵌入的局限性**：不能重写父结构体的方法，只能 override
4. **推荐做法**：用组合 + 接口实现多态，而不是嵌入实现继承

</details>