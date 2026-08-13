# Go Context传播机制 --- 资深专家深度实现

## 概述

Context是Go 1.7引入的并发控制机制，用于在goroutine间传递请求范围的值、取消信号和超时控制。本文深入剖析Context的实现原理和使用最佳实践。

## 一、Context接口设计

### 1.1 核心接口

```go
// src/context/context.go

type Context interface {
    // 返回key对应的值，不存在返回nil和false
    Value(key interface{}) interface{}
    
    // 返回一个channel，当Context被取消时会关闭
    Done() <-chan struct{}
    
    // 返回取消的原因，如果未取消返回nil
    Err() error
    
    // 内部方法，不在公开API中
    deadline() (deadline time.Time, ok bool)
    scheduleCancelFunc(context.Context, func())
}

// 空Context，不可取消
var Background = newBackground()
var TODO = newBackground()

func newBackground() context {
    return backgroundCtx
}

// background是空的不可取消的context
var background = context{}

// context结构体
type context struct {
    done chan struct{}  // 关闭通知channel
    err  error         // 取消原因
    mu   sync.Mutex    // 保护以下字段
    values map[key]*value  // key-value对
}
```

### 1.2 四种Context类型

```
┌─────────────────────────────────────────────────────────┐
│                  Context类型层次                         │
├─────────────────────────────────────────────────────────┤
│  Background/TOD (顶层)                                  │
│  ├── WithCancel (可取消)                                │
│  │   └── WithValue (带值)                               │
│  ├── WithTimeout (超时)                                 │
│  │   └── WithValue                                    │
│  └── WithDeadline (截止时间)                            │
│      └── WithValue                                    │
└─────────────────────────────────────────────────────────┘
```

## 二、WithCancel实现

### 2.1 取消机制

```go
// 创建可取消的Context
func WithCancel(parent Context) (ctx Context, cancel CancelFunc) {
    return withCancel(parent)
}

func withCancel(parent Context) (*cancelCtx, func()) {
    if parent == nil {
        panic("cannot create context from nil parent")
    }
    
    c := &cancelCtx {
        Context: parent,
        done: make(chan struct{}),
    }
    
    // 继承父Context的取消
    if pc, ok := parent.(*cancelCtx); ok {
        pc.children = make(map[*cancelCtx]bool)
        pc.children[c] = true
        c.cancelErr = pc.cancelErr
        c.closed = pc.closed
    }
    
    return c, func() { c.cancel(nil) }
}

// cancelCtx结构
type cancelCtx struct {
    Context
    mu       sync.Mutex
    done     chan struct{}     // 取消通知channel
    children map[*cancelCtx]bool  // 子Context
    err      error             // 取消原因
    closed   bool              // 是否已关闭
}
```

### 2.2 取消流程

```go
// 取消Context
func (c *cancelCtx) cancel(removeFromParent bool, err error) {
    if err == nil {
        panic("context: internal error: missing cancel error")
    }
    
    c.mu.Lock()
    if c.closed {
        c.mu.Unlock()
        return
    }
    c.closed = true
    c.err = err
    
    // 关闭done channel
    if c.done == nil {
        c.done = make(chan struct{})
    }
    close(c.done)
    
    // 递归取消所有子Context
    for child := range c.children {
        child.cancel(false, err)
    }
    c.children = nil
    c.mu.Unlock()
    
    if removeFromParent {
        // 从父Context中移除
        removeChild(c.Context, c)
    }
}

// 实现Context接口
func (c *cancelCtx) Done() <-chan struct{} {
    return c.done
}

func (c *cancelCtx) Err() error {
    return c.err
}
```

## 三、WithValue实现

### 3.1 值传递机制

```go
// 创建带值的Context
func WithValue(parent Context, key, val interface{}) Context {
    if parent == nil {
        panic("cannot create context from nil parent")
    }
    return &valueCtx {
        Context: parent,
        key:     key,
        val:     val,
    }
}

// valueCtx结构
type valueCtx struct {
    Context
    key, val interface{}
}

// 查找值 - 沿着链向上查找
func (c *valueCtx) Value(key interface{}) interface{} {
    if c.key == key {
        return c.val
    }
    return c.Context.Value(key)
}
```

### 3.2 链式结构

```
┌─────────────────────────────────────────────────┐
│  valueCtx { key: "req_id", val: "123" }         │
│    └── valueCtx { key: "user", val: User{...} } │
│         └── cancelCtx (Background)              │
└─────────────────────────────────────────────────┘
```

## 四、WithTimeout/WithDeadline

### 4.1 超时控制

```go
// 创建超时Context
func WithTimeout(parent Context, timeout time.Duration) (Context, CancelFunc) {
    return WithDeadline(parent, time.Now().Add(timeout))
}

// 创建截止时间Context
func WithDeadline(parent Context, d time.Time) (Context, CancelFunc) {
    if parent == nil {
        panic("context: cannot nil parent")
    }
    
    // 如果已经是deadline context，优化处理
    if dc, ok := parent.(*cancelCtx); ok && dc.deadline >= d {
        return withCancel(dc)
    }
    
    c := &timerCtx {
        cancelCtx: &cancelCtx {
            Context: parent,
        },
        deadline: d,
    }
    
    // 计算延迟时间
    t := time.Until(d)
    if t <= 0 {
        c.cancel(true, DeadlineExceeded)
        return c, func() { c.cancel(true, Canceled) }
    }
    
    // 设置定时器
    c.timer = time.AfterFunc(t, func() {
        c.cancel(true, DeadlineExceeded)
    })
    
    return c, func() { c.cancel(true, Canceled) }
}

// timerCtx结构
type timerCtx struct {
    *cancelCtx
    timer *time.Timer  // 定时器
    deadline time.Time  // 截止时间
}
```

### 4.2 超时取消流程

```go
func (c *timerCtx) cancel(removeFromParent bool, err error) {
    // 1. 先取消父Context
    c.cancelCtx.cancel(removeFromParent, err)
    
    if removeFromParent {
        // 2. 移除父Context
        removeChild(c.cancelCtx.Context, c.cancelCtx)
    }
    
    // 3. 停止定时器
    if c.timer != nil {
        c.timer.Stop()
        c.timer = nil
    }
}
```

## 五、使用最佳实践

### 5.1 正确用法

```go
// 1. 作为函数第一个参数
func HandleRequest(ctx context.Context, req *Request) error {
    // 使用ctx传递请求上下文
    select {
    case result := <-doWork(ctx):
        return result
    case <-ctx.Done():
        return ctx.Err()
    }
}

// 2. 及时取消
func processBatch(ctx context.Context, items []Item) error {
    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
            if err := process(ctx, item); err != nil {
                return err
            }
        }
    }
    return nil
}

// 3. 使用defer取消
func fetchData(ctx context.Context, url string) ([]byte, error) {
    childCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    // 使用childCtx...
    return http.Get(childCtx, url)
}
```

### 5.2 常见错误

```go
// 错误1: 忘记取消
func badCancel() {
    ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    // 忘记调用cancel()，导致资源泄漏
}

// 错误2: 在多个goroutine中共享
func badShare() {
    ctx, cancel := context.WithCancel(context.Background())
    
    go worker1(ctx)
    go worker2(ctx)
    
    cancel() // 这会取消所有goroutine
    // 可能导致意外的提前取消
}

// 错误3: 传递非context类型
func badType() {
    type ctxKey string
    const key ctxKey = "request_id"
    
    // 不要这样
    ctx := context.WithValue(context.Background(), "request_id", "123")
    
    // 要这样
    ctx := context.WithValue(context.Background(), key, "123")
}
```

## 六、性能分析

### 6.1 Context开销

```go
func benchmarkContext(b *testing.B) {
    // 创建Context开销
    b.Run("Create", func(b *testing.B) {
        for i := 0; i < b.N; i++ {
            ctx, cancel := context.WithTimeout(context.Background(), time.Second)
            cancel()
        }
    })
    
    // Value查找开销
    b.Run("ValueLookup", func(b *testing.B) {
        ctx := context.WithValue(
            context.WithValue(context.Background(), "a", 1),
            "b", 2,
        )
        for i := 0; i < b.N; i++ {
            _ = ctx.Value("a")
            _ = ctx.Value("b")
        }
    })
}

// 典型数据:
// Create: ~50ns/op
// ValueLookup: ~10ns/op
```

### 6.2 优化建议

```go
// 1. 避免过长的Context链
// 最多2-3层WithValue

// 2. 使用context.Key类型避免冲突
type ctxKey string

const requestIDKey ctxKey = "request_id"
const userIDKey ctxKey = "user_id"

// 3. 及时取消
defer cancel()

// 4. 不要将Context存储在结构中
type Handler struct {
    ctx context.Context  // ❌ 不要这样做
}
```

## 七、面试高频题

### 7.1 高频问题

**Q1: Context是如何实现级联取消的？**

A: 通过树状结构和递归：
- cancelCtx维护children map
- cancel()时递归调用所有子Context的cancel()
- 通过done channel通知所有监听者

**Q2: WithValue的查找过程是怎样的？**

A: 链式查找：
- valueCtx存储一个key-value对
- Value()时先检查自身，再递归调用父Context
- 时间复杂度O(n)，n为链长度

**Q3: Context能传递什么类型的值？**

A: 
- 只传只读数据（请求ID、用户信息）
- 不传指针或可变对象
- key使用自定义类型避免冲突

### 7.2 自测题

1. 画出cancelCtx的树状结构图
2. 实现一个带超时的HTTP请求
3. 解释Context链式查找的性能开销
4. 分析Context内存泄漏的原因
5. 比较WithCancel和WithTimeout的实现差异

---

**创建时间**: 2026-10-16
**作者**: Ryan
**领域**: Interview / Go并发编程
**关键词**: context, cancel, timeout, withvalue, goroutine
