// 5. 使用 GOGC 调整 GC 频率: GOGC=50（更频繁 GC）/ GOGC=200（更少 GC）
// 6. 使用 GOMEMLIMIT 限制内存: 防止 OOM
// 7. 避免频繁字符串拼接: 用 strings.Builder
// 8. 避免接口逃逸: 接口参数会触发 heap 分配
```

---

## 自测题

### 问题 1
Go 的 GMP 模型中，M 和 P 的关系是什么？

<details>
<summary>查看答案</summary>

1. **M (Machine)**: 真正的操作系统线程，执行 goroutine 的代码
2. **P (Processor)**: 逻辑处理器，管理本地 runqueue 和全局 runqueue
3. **G (Goroutine)**: 轻量级线程，包含执行栈和状态
4. **关系**: 每个 P 关联一个 M 执行工作，每个 M 可以执行多个 G
5. **调度**: G → P 的本地队列 → M 执行，P 本地队列为空时从全局队列或其他 P 偷取
6. **GOMAXPROCS**: 控制 P 的数量，默认等于 CPU 核心数

</details>

### 问题 2
Go 的 Work-Stealing 调度算法为什么比 FIFO 更好？

<details>
<summary>查看答案</summary>

1. **负载均衡**: P 本地队列空时从其他 P 偷取 G，避免负载不均衡
2. **减少锁竞争**: 优先从本地队列取 G，减少锁竞争
3. **减少停顿**: 偷取时使用双端队列，偷取和入队不同端，减少冲突
4. **缓存友好**: G 在 P 本地队列中执行，减少缓存失效
5. **公平性**: 每个 P 都有机会执行工作，避免饿死

</details>

### 问题 3
Go 的 GC 为什么采用三色标记+写屏障？

<details>
<summary>查看答案</summary>

1. **三色标记**: 白（未扫描）、灰（待扫描）、黑（已扫描）
2. **写屏障**: 记录黑→白的指针写操作，避免漏标
3. **STW**: 只有标记开始和结束时需要 STW，停顿时间极短
4. **增量式**: GC 过程中用户 goroutine 可以继续执行
5. **GOGC**: 控制触发 GC 的堆增长比例，默认 100%

</details>