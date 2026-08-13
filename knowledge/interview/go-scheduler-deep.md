# Go调度器实现 - 资深专家深度实现

## 一、调度器架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Go调度器架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   P (Processor)                                                          │
│   ├── M (Machine) - 线程                                                │
│   ├── G (Goroutine) - 协程                                              │
│   └── Local Queue - 本地队列                                            │
│                                                                         │
│   Global Queue                                                           │
│   ├── Work Stealing                                                      │
│   └── Hand-off                                                           │
│                                                                         │
│   特点:                                                                   │
│   • M:N调度模型                                                          │
│   • 工作窃取                                                              │
│   • 协作式抢占                                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、GMP模型

```go
// src/runtime/proc.go
type p struct {
    lock      mutex
    id        int32
    status    uint32
    runqhead  uint32
    runqtail  uint32
    runq      [256]guintptr
    runnext   guintptr
    goidbase  uint64
    schedtick uint32
    sysmonlock unlock
    flags     uint32
    
    // 本地队列
    deferpool    [5]*_defer
    deferpoolbuf [5]*_defer
}

type m struct {
    g0      *g        // 拥有栈空间的goroutine
    curg    *g        // 当前运行的goroutine
    p       pptr     // 绑定的p
    nextp   pptr
    id      int32
    mcache  *mcache
    lockedg guintptr
}

type g struct {
    stack       stack      // 栈信息
    sched       gstruct    // 调度信息
    params      unsafe.Pointer
    atomicstatus uint32    // 状态
    goid        int64     // goroutine id
}
```

## 三、工作窃取

```go
// src/runtime/proc.go
func stealWork(batch []*g) int {
    for _, _p_ := range allp {
        if _p_ == myp || _p_.runnext != 0 {
            continue
        }
        
        n := readyFromRunQueue(_p_, &batch[len(batch):cap(batch)])
        if n > 0 {
            return len(batch)
        }
    }
    return 0
}

func readyFromRunQueue(_p_ *p, batch *[]*g) int {
    n := 0
    for n < cap(*batch) && _p_.runqhead != _p_.runqtail {
        g := _p_.runq[_p_.runqtail%uint32(len(_p_.runq))]
        _p_.runqtail++
        *batch = append(*batch, g)
        n++
    }
    return n
}
```

## 四、面试高频题

### Q1: Go调度器如何解决GIL问题？

```
A:
1. M:N调度模型
2. 多P并行执行
3. 工作窃取
```

### Q2: 如何实现抢占式调度？

```
A:
1. 系统调用时检测
2. 信号量中断
3. 栈空间不足
```

## 五、自测题

1. 解释GMP模型
2. 如何实现工作窃取？
3. 如何避免死锁？

---

## 参考文档

- [Go调度器源码](https://github.com/golang/go/blob/master/src/runtime/proc.go)
- [Go运行时](https://github.com/golang/go/wiki/Goroutines)
