# Go调度器深入 - 资深专家深度实现

## 一、GMP模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      GMP调度模型                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   G (Goroutine)                                                         │
│   ├── 用户态线程                                                          │
│   ├── Stack: 2KB-1MB动态扩展                                              │
│   └── Status: runnable/running/waiting                                   │
│                                                                         →
│   M (Machine)                                                           │
│   ├── OS线程                                                              │
│   ├── P引用                                                               │
│   └── 阻塞时释放P                                                        │
│                                                                         →
│   P (Processor)                                                          │
│   ├── local queue: 256个G                                               │
│   ├── global queue: 所有G共享                                             │
│   └── 网络轮询器                                                          │
│                                                                         →
│   调度流程:                                                              │
│   1. 新G → P的local queue                                               │
│   2. P的queue满 → 推送到global queue或另一P                                │
│   3. M空闲 → 从global queue获取G                                          │
│   4. M阻塞 → 释放P，创建新M                                               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Work Stealing

```go
// worksteal.go
func (p *p) stealWork() *g {
    // 从其他P的queue偷取一半
    for {
        victim := runqsteal(p, randomInt(numP))
        if victim != nil {
            return victim
        }
        // 尝试从全局queue获取
        if g, ok := globrunqget(); ok {
            return g
        }
        // 休眠等待
        startTheWorldWithSema()
    }
}
```

## 三、面试高频题

### Q1: GMP模型优势？

```
A:
1. 工作窃取负载均衡
2. 本地队列减少竞争
3. 非抢占式调度
```

### Q2: 如何避免饥饿？

```
A:
1. 系统G与用户G分离
2. 全局队列优先
3. 抢占机制
```

## 四、自测题

1. 解释GMP模型
2. 如何实现工作窃取？
3. 如何处理死锁？

---

## 参考文档

- [Go运行时调度器](https://github.com/golang/go/blob/master/src/runtime/proc.go)
- [Golang GC实现](https://github.com/golang/go/blob/master/src/runtime/mgc.go)
