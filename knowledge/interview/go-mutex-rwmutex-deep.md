# Go Mutex与RWMutex源码分析 --- 资深专家深度实现

## 概述

Mutex和RWMutex是Go并发编程中最核心的同步原语。本文深入剖析其实现原理、性能优化和生产环境最佳实践。

## 一、Mutex实现原理

### 1.1 结构体定义

```go
// src/sync/mutex.go

type Mutex struct {
    state int32
    sema  uint32  // 信号量
}

// state字段布局 (32位)
// ┌─────────────────────────────────┐
// │ locked (1bit) | mutexState (2bit) | waiterCount (13bit) | reserved (16bit) |
// └─────────────────────────────────┘
//
// mutexState:
//   0: 正常状态
//   1: 唤醒中 (waking)
//   2: 饥饿状态 (starving)
```

### 1.2 锁获取流程

```go
// 轻量级获取路径 (无竞争)
func (m *Mutex) Lock() {
    // 快速路径：尝试原子获取锁
    if atomic.CompareAndSwap(&m.state, 0, 1) {
        return
    }
    // 慢路径：阻塞等待
    m.lockSlow()
}

// 慢路径实现
func (m *Mutex) lockSlow() {
    var waitStartTime int64
    starving := false
    awoke := false
    iter := 0
    
    for {
        // 1. 尝试获取锁
        old := m.state
        if old&1 == 0 {
            // 锁空闲，尝试获取
            if newVal := old | 1; atomic.CompareAndSwap(&m.state, old, newVal) {
                if starving || old&mutexWaiterShift != 0 {
                    // 转换为饥饿模式
                    m.lockStarving(old, waitStartTime)
                }
                return
            }
        }
        
        // 2. 自旋等待（最多4次）
        if old&(mutexWoken|mutexStarving) == 0 && waitStartTime == 0 {
            iter++
            if iter < 4 {
                runtime_do_yield()
                continue
            }
        }
        
        // 3. 阻塞等待
        if starving {
            // 饥饿模式：直接排队
            m.lockStarving(old, waitStartTime)
        } else {
            // 正常模式：加入等待队列
            m.lockNormal(old, waitStartTime, awoke)
        }
        
        // 4. 重新尝试
        awoke = true
        iter = 0
    }
}
```

### 1.3 两种模式切换

```
┌─────────────────────────────────────────────────────────┐
│                    Mutex状态机                           │
├─────────────────────────────────────────────────────────┤
│  正常模式 (Normal)                                       │
│  ┌──────┐   获取锁   ┌──────┐                            │
│  │ 空闲 │ ───────→ │ 持有  │                            │
│  └──┬───┘          └──┬───┘                            │
│     │ 释放锁          │ 竞争激烈                         │
│     └─────────────────┘                                 │
│                                                        │
│  饥饿模式 (Starving)                                    │
│  ┌──────┐   超时等待   ┌──────┐                        │
│  │ 空闲 │ ────────→ │ 持有  │ (FIFO队列)               │
│  └──┬───┘          └──┬───┘                            │
│     │ 释放锁          │ 成功获取                         │
│     └─────────────────┘                                 │
│                                                        │
│  模式切换条件：                                          │
│  - 正常→饥饿: 等待时间 > 1ms                             │
│  - 饥饿→正常: 当前持锁者是队列头部                         │
└─────────────────────────────────────────────────────────┘
```

## 二、RWMutex实现原理

### 2.1 读写锁结构

```go
type RWMutex struct {
    w           Mutex      // 写锁互斥
    writerSem   uint32    // 写者信号量
    readerSem   uint32    // 读者信号量
    readerCount int32     // 读者数量 (含等待写锁的)
    readerWait  int32     // 等待释放的读者数量
}
```

### 2.2 读锁获取

```go
func (rw *RWMutex) Lock() {
    // 获取写锁前，先自增读者数量
    atomic.AddInt32(&rw.readerCount, 1)
    
    // 等待所有当前读者完成
    rw.readerSem++
    runtime_semasleep(rw.readerSem, 6*60*1e9)
    rw.readerSem--
}

func (rw *RWMutex) RLock() {
    if atomic.AddInt32(&rw.readerCount, 1) < 0 {
        // 有写者等待，阻塞
        runtime_semacquire(&rw.readerSem)
    }
}

func (rw *RWMutex) RUnlock() {
    if r := atomic.AddInt32(&rw.readerCount, -1); r < 0 {
        // 最后一个读者释放，唤醒写者
        runtime_semrelease(&rw.readerSem)
    }
}
```

### 2.3 写锁获取

```go
func (rw *RWMutex) Lock() {
    // 1. 获取写者互斥锁
    rw.w.Lock()
    
    // 2. 等待所有读者释放
    atomic.AddInt32(&rw.readerWait, 1)
    
    // 3. 等待当前读者全部完成
    sem := rw.readerSem
    for {
        rc := atomic.LoadInt32(&rw.readerCount)
        if rc <= atomic.LoadInt32(&rw.readerWait) {
            break
        }
        runtime_semasleep(sem, 10*60*1e9)
    }
    
    // 4. 关闭新读者进入
    atomic.AddInt32(&rw.readerCount, -1<<rw.readerShift)
    atomic.AddInt32(&rw.readerWait, -1)
}

func (rw *RWMutex) Unlock() {
    // 1. 允许新读者进入
    atomic.AddInt32(&rw.readerCount, 1<<rw.readerShift)
    
    // 2. 唤醒等待的写者
    rw.w.Unlock()
    runtime_semrelease(&rw.writerSem)
}
```

## 三、性能优化

### 3.1 锁粒度控制

```go
// ❌ 大粒度锁
type Cache struct {
    mu sync.Mutex
    data map[string]interface{}
}

func (c *Cache) Get(key string) interface{} {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.data[key]
}

// ✅ 细粒度锁 (分片)
type ShardedCache struct {
    shards [16]struct {
        mu     sync.Mutex
        data   map[string]interface{}
    }
}

func (c *ShardedCache) Get(key string) interface{} {
    shard := &c.shards[keyHash(key)%16]
    shard.mu.Lock()
    defer shard.mu.Unlock()
    return shard.data[key]
}
```

### 3.2 读写锁优化

```go
// 读多写少场景使用RWMutex
type PageCache struct {
    mu     sync.RWMutex
    pages  map[string][]byte
}

func (c *PageCache) Read(pageID string) []byte {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.pages[pageID]
}

func (c *PageCache) Write(pageID string, data []byte) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.pages[pageID] = data
}
```

### 3.3 避免锁竞争

```go
// 使用sync.Pool减少分配
var bufPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 4096)
    },
}

func Process(data []byte) []byte {
    buf := bufPool.Get().([]byte)
    defer bufPool.Put(buf)
    
    // 处理数据...
    return buf
}
```

## 四、常见陷阱

### 4.1 死锁

```go
// 错误示例：嵌套锁导致死锁
func transfer(from, to *Account, amount int) {
    // 可能死锁：两个goroutine以不同顺序获取锁
    from.mu.Lock()
    to.mu.Lock()
    defer to.mu.Unlock()
    defer from.mu.Unlock()
    
    if from.Balance >= amount {
        from.Balance -= amount
        to.Balance += amount
    }
}

// 正确：固定锁顺序
func transferSafe(from, to *Account, amount int) {
    first, second := from, to
    if from.ID > to.ID {
        first, second = second, first
    }
    
    first.mu.Lock()
    defer first.mu.Unlock()
    second.mu.Lock()
    defer second.mu.Unlock()
    
    if first.Balance >= amount {
        first.Balance -= amount
        second.Balance += amount
    }
}
```

### 4.2 锁升级

```go
// 错误：读锁升级为写锁可能死锁
func unsafeUpgrade(rw *sync.RWMutex) {
    rw.RLock()
    // ... 读取数据 ...
    
    // 此时其他读者可能还在持有读锁
    // 升级到写锁会死锁
    rw.RUnlock()
    rw.Lock()
}

// 正确：使用写锁保护整个操作
func safeUpgrade(rw *sync.RWMutex) {
    rw.Lock()
    defer rw.Unlock()
    // 直接加写锁
}
```

## 五、面试高频题

### 5.1 高频问题

**Q1: Mutex和RWMutex有什么区别？**

A:
- Mutex: 互斥锁，同时只有一个goroutine能持有
- RWMutex: 读写锁，允许多个读者同时读，但写者独占

**Q2: Mutex的饥饿模式是什么？**

A:
- 当goroutine等待时间超过1ms时进入饥饿模式
- 饥饿模式下，锁直接从等待队列传递给下一个goroutine
- 防止长时间等待的goroutine被饿死

**Q3: 如何避免死锁？**

A:
- 固定锁获取顺序
- 使用defer确保锁释放
- 避免嵌套锁
- 使用trylock超时机制

### 5.2 自测题

1. 画出Mutex的状态机图
2. 解释RWMutex的读者计数原理
3. 实现一个线程安全的缓存
4. 分析死锁产生的条件
5. 比较Mutex和RWMutex的性能差异

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / Go并发编程
**关键词**: mutex, rwmutex, lock, deadlock, concurrency
