# Go运行时调度器 - 资深专家深度实现

## 一、GMP模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Go Runtime调度器                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   G (Goroutine)         M (Machine/Thread)      P (Processor)           │
│   ┌──────────┐          ┌──────────┐          ┌──────────┐            │
│   │  local Q │◄────────►│  sysmon  │◄────────►│  runQ    │            │
│   │  本地队列 │          │  (系统监控)│          │  运行队列 │            │
│   └──────────┘          └──────────┘          └────┬─────┘            │
│         ▲                                          │                 │
│         │                    global Q ◄────────────┘                 │
│         └────────────────────────────────────────────────            │
│                     steal from other Ps                               │
│                                                                         │
│   调度流程:                                                             │
│   1. G → runnable → P.runQ                                            │
│   2. P调度G到M执行                                                      │
│   3. G阻塞 → 放入 global Q 或 其他P的runQ                              │
│   4. P空闲 → 从global Q或偷取                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、调度器实现

```go
package runtime

type schedt struct {
    nprocs      uint32      // 逻辑处理器数量
    nmidle      uint32      // 空闲M数量
    nmsys       uint32      // 系统M数量
    nmuintptr   uintptr     // M总数
    
    g0      *g            // 调度goroutine
    m0      *m            // 主m
    allgs   **g           // 所有g
    allm     *m            // 所有m (环形链表)
    allp     **p           // 所有p
    
    lock mutex
    
    schedTick    uint64
    schedWhen    int64
    
    // 全局队列
    runqsize   int32
    runq       *g
    runqsize   int32
}

type p struct {
    lock mutex
    
    status       uint32
    id           int32
    schedTick    uint32
    
    // 本地运行队列
    runqhead   *g
    runqtail   *g
    runqsize   int32
    
    // 外部队列 (用于steal)
    deferpool    []*defer
    deferpoolp   *p
}

type g struct {
    stack       stack
    sched       uintptr
    spawnq      *g
    
    // 调度状态
    status      uint32
    atomicstatus guint32
    
    // 绑定关系
    m           *m       // 当前绑定的m
    p           *p       // 绑定的p
    
    // 队列链
    allgnext    *g
    schedlink   guintptr
}
```

## 三、工作窃取

```go
func (p *p) stealWork() *g {
    // 随机选择另一个P
    start := fastrand() % allp.len()
    for i := 0; i < allp.len(); i++ {
        next := (start + i) % allp.len()
        if next == p.id {
            continue
        }
        
        otherP := allp[next]
        if otherP.runqsize > otherP.runqsize/2 {
            // 偷取一半
            n := otherP.runqsize / 2
            g := otherP.runq
            otherP.runq = g.schedlink.ptr()
            otherP.runqsize -= n
            
            // 放入本地队列
            for i := 0; i < n; i++ {
                // ...
            }
            return g
        }
    }
    return nil
}
```

## 四、面试高频题

### Q1: Go调度器有什么优势？

```
A:
1. O(1)调度
2. 工作窃取负载均衡
3. 系统调用不阻塞其他G
4. 协程切换轻量
```

### Q2: 什么是golang的Sysmon？

```
A:
• 系统监控goroutine
• 每10ms执行一次
• 检查长时间运行的G
• 强制抢占调度
• 重置idle M的P
```

## 五、自测题

1. 解释GMP调度模型
2. 如何实现工作窃取？
3. 协程切换开销多大？

---

## 参考文档

- [Go源码sched.go](https://github.com/golang/go/blob/master/src/runtime/proc.go)
- [Go调度器论文](https://go.dev/sched)
