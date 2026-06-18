# Go 并发编程深度：sync/atomic/channel 源码级

> 从 runtime 源码逐行解析 Go 并发原语

---

## 第一部分：sync/atomic 源码深度

### atomic 底层实现

```
atomic 操作映射到 CPU 指令：
┌─────────────────────────────────────────────────────────────────────┐
│ Load (LoadInt32/LoadInt64/LoadPointer)                              │
│   MOV [addr], eax/x86_64                                           │
│   LDR x0, [x1] (ARM)                                               │
│                                                                     │
│ Store (StoreInt32/StoreInt64/StorePointer)                          │
│   MOV eax/x86_64, [addr]                                           │
│   STR x0, [x1] (ARM)                                               │
│                                                                     │
│ CAS (CompareAndSwap)                                                │
│   CMPXCHG eax, [addr] (x86)                                        │
│   LDREX/STREX (ARM)                                                │
│                                                                     │
│ Add (AddInt32/AddInt64)                                             │
│   LOCK XADD (x86)                                                  │
│   LDREX+ADD+STREX (ARM)                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### sync/atomic/value.go 源码逐行解析

```go
// Go 源码：sync/atomic/value.go
type Value struct {
    v interface{}
}

// Store 原子存储
func (v *Value) Store(val interface{}) {
    // 1. 禁止存储 nil
    if val == nil {
        panic("sync/atomic: store of nil value into Value")
    }
    
    // 2. 存储时加锁（防止并发读写）
    for {
        // 3. CAS 循环：直到成功
        if v.cas(nil, val) {
            return
        }
    }
}

// Load 原子加载
func (v *Value) Load() (val interface{}) {
    // 1. 自旋等待直到稳定
    for {
        val = v.v
        if val != nil {
            return val
        }
        // 2. 短暂 yield，避免忙等待
        runtime_do_yield()
    }
}

// cas 比较并交换
func (v *Value) cas(old, new interface{}) bool {
    // 使用 atomic.Pointer 实现 CAS
    return atomic.CompareAndSwapPointer(
        (*unsafe.Pointer)(unsafe.Pointer(&v.v)),
        unsafe.Pointer(old),
        unsafe.Pointer(new),
    )
}
```

### atomic/int.go 源码逐行解析

```go
// Go 源码：sync/atomic/int.go
type Int32 int32

func (x *Int32) Add(delta int32) int32 {
    // 1. 调用 runtime 级别的 atomic add
    return runtime_atomic_addInt32((*int32)(x), delta)
}

func (x *Int32) Load() int32 {
    // 2. 调用 runtime 级别的 atomic load
    return runtime_atomic_loadInt32((*int32)(x))
}

func (x *Int32) Store(val int32) {
    // 3. 调用 runtime 级别的 atomic store
    runtime_atomic_storeInt32((*int32)(x), val)
}

func (x *Int32) Swap(new int32) (old int32) {
    // 4. 调用 runtime 级别的 atomic swap
    return runtime_atomic_swapInt32((*int32)(x), new)
}

func (x *Int32) CompareAndSwap(old, new int32) bool {
    // 5. 调用 runtime 级别的 atomic cas
    return runtime_atomic_casInt32((*int32)(x), old, new)
}
```

---

## 第二部分：Channel 源码深度

### channel 数据结构

```
channel 内部结构：
┌─────────────────────────────────────────────────────────────────────┐
│ type hchan struct {                                                 │
│     qcount   uint           // 队列中元素个数                        │
│     dataqsiz uint           // 环形缓冲区大小                        │
│     buf      unsafe.Pointer // 环形缓冲区                           │
│     elemsize uint16         // 元素大小                              │
│     closed   uint16         // 是否关闭                              │
│     elemtype *_type     // 元素类型                                  │
│     sendx    uint         // 发送索引                                │
│     recvx    uint         // 接收索引                                │
│     recvq    waitq      // 等待接收的 goroutine 队列                 │
│     sendq    waitq      // 等待发送的 goroutine 队列                 │
│     lock   mutex        // 互斥锁                                    │
│ }                                                                    │
│                                                                     │
│ 操作流程：                                                           │
│ 1. 有缓冲 channel:                                                 │
│    - 发送：buf[sendx] = val, sendx++, notify receiver                │
│    - 接收：val = buf[recvx], recvx++, notify sender                  │
│                                                                     │
│ 2. 无缓冲 channel:                                                 │
│    - 发送：直接传递给接收者，阻塞直到对方接收                          │
│    - 接收：直接从发送者获取，阻塞直到有发送者                          │
└─────────────────────────────────────────────────────────────────────┘
```

### chansend 源码逐行解析

```c
// Go 源码：src/runtime/chan.go - chansend
func chansend(c *hchan, ep unsafe.Pointer, block bool, sender unsafe.Pointer) bool {
    // 1. 检查 channel 是否关闭
    if c.closed != 0 {
        panic("send on closed channel")
    }
    
    // 2. 获取锁
    lock(&c.lock)
    
    // 3. 有缓冲 channel
    if c.dataqsiz > 0 {
        // 3.1 缓冲区有空间
        if c.qcount < c.dataqsiz {
            // 3.2 拷贝数据到缓冲区
            qp := chanbuf(c, c.sendx)
            typedmemmove(c.elemtype, qp, ep)
            c.sendx++
            if c.sendx == c.dataqsiz {
                c.sendx = 0
            }
            c.qcount++
            
            // 3.3 唤醒等待接收的 goroutine
            unlock(&c.lock)
            goready(c.recvq.dequeue(), 0)
            return true
        }
    }
    
    // 4. 无缓冲 channel 或有缓冲但满了
    if sg := c.recvq.dequeue(); sg != nil {
        // 4.1 直接传递数据
        send(c, sg, ep, func() { unlock(&c.lock) }, 3)
        return true
    }
    
    // 5. 阻塞等待
    if !block {
        unlock(&c.lock)
        return false
    }
    
    // 5.1 创建 sender goroutine
    gp := getg()
    ms := acquireSudog()
    ms.G = gp
    ms.elem = ep
    ms.releasetime = 0
    
    // 5.2 加入发送队列
    c.sendq.enqueue(ms)
    
    // 5.3 释放锁并挂起
    unlock(&c.lock)
    goready(gp, 0)
    
    // 5.4 被唤醒后释放 sudog
    releasems(ms)
    return true
}
```

### chanrecv 源码逐行解析

```c
// Go 源码：src/runtime/chan.go - chanrecv
func chanrecv(c *hchan, ep unsafe.Pointer, block bool) (selected, received bool) {
    // 1. 检查 channel 是否关闭且有数据
    if c.closed != 0 && c.qcount == 0 {
        if receivemode != 0 {
            panic("receive of closed channel")
        }
        return true, false
    }
    
    // 2. 获取锁
    lock(&c.lock)
    
    // 3. 有缓冲 channel
    if c.qcount > 0 {
        // 3.1 从缓冲区取出数据
        qp := chanbuf(c, c.recvx)
        if ep != nil {
            typedmemmove(c.elemtype, ep, qp)
        }
        typedmemclr(c.elemtype, qp)
        c.recvx++
        if c.recvx == c.dataqsiz {
            c.recvx = 0
        }
        c.qcount--
        
        // 3.2 唤醒等待发送的 goroutine
        unlock(&c.lock)
        goready(c.sendq.dequeue(), 0)
        return true, true
    }
    
    // 4. 无缓冲 channel 或缓冲区为空
    if sg := c.sendq.dequeue(); sg != nil {
        // 4.1 直接接收数据
        recv(c, sg, ep, func() { unlock(&c.lock) }, 3)
        return true, true
    }
    
    // 5. 阻塞等待
    if !block {
        unlock(&c.lock)
        return false, false
    }
    
    // 5.1 创建 receiver goroutine
    gp := getg()
    rg := acquireSudog()
    rg.G = gp
    rg.elem = ep
    rg.releasetime = 0
    
    // 5.2 加入接收队列
    c.recvq.enqueue(rg)
    
    // 5.3 释放锁并挂起
    unlock(&c.lock)
    goready(gp, 0)
    
    // 5.4 被唤醒后释放 sudog
    releasems(rg)
    return true, true
}
```

---

## 第三部分：sync 包源码深度

### Mutex 源码逐行解析

```go
// Go 源码：sync/mutex.go
type Mutex struct {
    state int32
    sema  uint32
}

// 状态位定义
const (
    mutexLocked = 1 << iota // 锁标记
    mutexWakeup             // 唤醒标记
    mutexStarving           // 饥饿模式标记
    mutexWaiterShift = iota // 等待者数量偏移
)

// Lock 加锁
func (m *Mutex) Lock() {
    // 1. 快速路径：无竞争
    if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
        return
    }
    
    // 2. 慢路径：有竞争
    m.lockSlow()
}

func (m *Mutex) lockSlow() {
    var waitStartTime int64
    starving := false
    awoke := false
    iter := 0
    old := m.state
    
    for {
        // 1. 尝试加锁
        if old&(mutexLocked|mutexStarving) == mutexLocked && runtime_canSpin(iter) {
            // 2. 自旋（多核环境下）
            if !awoke && old&mutexWakeup == 0 {
                atomic.OrInt32(&m.state, mutexWakeup)
                awoke = true
            }
            runtime_do_spin()
            iter++
            old = m.state
            continue
        }
        
        // 3. 尝试获取锁
        var new int32
        if old&mutexStarving == 0 {
            // 非饥饿模式：CAS 加锁
            new = old | mutexLocked
        } else {
            // 饥饿模式：移到队尾
            waitStartTime = runtime_nanotime()
            // ...
        }
        
        // 4. CAS 尝试
        if atomic.CompareAndSwapInt32(&m.state, old, new) {
            if old&mutexStarving == 0 {
                return // 加锁成功
            }
            // 饥饿模式下，唤醒下一个等待者
            runtime_Semrelease(&m.sema, false, 1)
            return
        }
        old = m.state
    }
}
```

### WaitGroup 源码逐行解析

```go
// Go 源码：sync/waitgroup.go
type WaitGroup struct {
    noCopy noCopy
    state1 [3]uint64 // 打包为 3 个 uint64 减少缓存行污染
}

func (wg *WaitGroup) Add(delta int) {
    statep := wg.state()
    
    // 1. 原子加法
    for {
        v := atomic.Load(statep)
        w := uint32(v >> 32)
        if w != 0 && delta > 0 {
            panic("sync: negative WaitGroup counter")
        }
        
        if delta < 0 {
            // 负数：减法
            new := v + uint64(delta)<<32
            if atomic.CompareAndSwap(statep, v, new) {
                if new>>32 == 0 && new&0xffffffff == 0 {
                    // 计数归零，唤醒所有等待者
                    runtime_Semrelease(wg.sem(), false, true)
                }
                return
            }
        } else {
            // 正数：加法
            new := v + uint64(delta)<<32
            if atomic.CompareAndSwap(statep, v, new) {
                return
            }
        }
    }
}

func (wg *WaitGroup) Wait() {
    statep := wg.state()
    
    for {
        v := *statep
        w := uint32(v >> 32)
        if w == 0 {
            return // 计数已归零
        }
        
        // 等待信号
        runtime_Semacquire(wg.sem())
        
        // 重新检查
        if *statep == 0 {
            return
        }
    }
}
```

---

## 第四部分：自测题

### Q1: Go channel 和 queue 的区别？

**A**: Channel 是通信原语（CSP 模型），强调"通过通信共享内存"；queue 是数据结构，强调"共享内存的并发访问"。

### Q2: Mutex 的饥饿模式是什么？

**A**: 当等待时间过长时，Mutex 进入饥饿模式，新来的 goroutine 不能直接获取锁，而是排队等待。这防止了长时间等待的 goroutine 被饿死。

### Q3: atomic.Value 为什么只能存一个值？

**A**: 为了保证原子性，Value 内部用 CAS 循环实现，只能保证整体替换的原子性，不能保证内部字段的原子性。

---

## 第五部分：生产实践

### 1. 并发模式

```
常见并发模式：
1. Worker Pool：固定数量的 worker 处理任务
2. Fan-Out/Fan-In：并行处理 + 合并结果
3. Pipeline：多阶段串行处理
4. Context：取消传播 + 超时控制
```

### 2. 性能调优

```
性能调优要点：
1. 减少锁竞争（无锁数据结构）
2. 使用 sync.Pool 复用对象
3. 避免 false sharing（缓存行对齐）
4. 合理设置 GOMAXPROCS
```

### 3. 调试技巧

```
调试技巧：
1. race detector: go run -race
2. pprof: 性能分析
3. trace: 执行追踪
4. GODEBUG=schedtrace=1000: 调度器追踪
```
