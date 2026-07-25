// 5. 使用 GOGC 调整 GC 频率: GOGC=50（更频繁 GC）/ GOGC=200（更少 GC）
// 6. 使用 GOMEMLIMIT 限制内存: 防止 OOM
// 7. 避免频繁字符串拼接: 用 strings.Builder
// 8. 避免接口逃逸: 接口参数会触发 heap 分配
```

## Go 实现：GMP 调度器核心

```go
package runtime

import (
	"sync"
	"sync/atomic"
)

// P 逻辑处理器
type P struct {
	id          int32
	status      uint32 // _Pidle, _Prunning, _Psystem, _Pgc
	runq        runQueue   // 本地运行队列
	runnext     *g         // 下一个要执行的 goroutine
	pendrunq    gQueue     // 等待运行的 goroutine 队列
	gcx         gcContext  // GC 上下文
	m           *m         // 绑定的 M
	mcount      int32      // P 创建数
	mfreecount  int32      // P 释放数
	// ... 更多字段
}

// M OS 线程
type m struct {
	g0      *g       // 系统 goroutine，用于调度
	curg    *g       // 当前执行的 goroutine
	p       puintptr // 绑定的 P
	nextp   puintptr // 下一次要绑定的 P
	stack   stack    // 当前栈
	// ... 更多字段
}

// g Goroutine
type g struct {
	stack       stack    // 栈 [stack.lo, stack.hi]
	stackguard0 uintptr  // 栈检查阈值 (goroutine 用户代码)
	stackguard1 uintptr  // 栈检查阈值 (runtime 内部)
	p           puintptr
	m            *m
	sched        context  // 调度上下文（保存/恢复）
	atomicstatus uint32   // Grunning, Grunnable, Grunnable, etc.
	goroutineID  int64
	// ... 更多字段
}

// runQueue 双端队列 - Work-Stealing 的核心数据结构
type runQueue struct {
	head uint32
	tail uint32
	buf  [256]*g // 环形缓冲区
}

func (q *runQueue) push(g *g) {
	// 从尾部入队
	idx := atomic.AddUint32(&q.tail, 1) - 1
	q.buf[idx%uint32(len(q.buf))] = g
}

func (q *runQueue) pop() *g {
	// 从头部出队
	for {
		head := q.head
		tail := q.tail
		if head >= tail {
			return nil // 空队列
		}
		if atomic.CompareAndSwapUint32(&q.head, head, head+1) {
			g := q.buf[head%uint32(len(q.buf))]
			q.buf[head%uint32(len(q.buf))] = nil // 避免内存泄漏
			return g
		}
	}
}

// stealWork 从其他 P 偷取工作 - Work-Stealing 算法
func (myP *P) stealWork() *g {
	// 随机选择一个其他 P
	for i := 0; i < 4; i++ { // 最多尝试 4 次
		targetP := pickRandomP(myP.id)
		if targetP == nil {
			break
		}
		// 从目标 P 的尾部偷取（与 pop 不同端，减少竞争）
		g := targetP.stealFromTail()
		if g != nil {
			return g
		}
	}
	return nil
}

func (q *runQueue) stealFromTail() *g {
	for {
		tail := q.tail
		head := q.head
		if head >= tail {
			return nil
		}
		// 从尾部偷取
		if atomic.CompareAndSwapUint32(&q.tail, tail, tail-1) {
			g := q.buf[(tail-1)%uint32(len(q.buf))]
			q.buf[(tail-1)%uint32(len(q.buf))] = nil
			return g
		}
	}
}
```

## 动手验证

```bash
# 查看当前 GOMAXPROCS
go env GOMAXPROCS

# 运行 GMP 调度模拟测试
go test -v ./runtime/... -run TestWorkStealing

# 压测 goroutine 并发
go run examples/gmp_bench/main.go --procs=8 --goroutines=100000
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