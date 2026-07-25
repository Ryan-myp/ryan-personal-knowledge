# 微信读书精华：Go 语言高级开发与实战 + 从程序员到架构师 蒸馏笔记

> 来源：《Go语言高级开发与实战》- 廖显东 + 《从程序员到架构师》- 王伟杰
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：Go 高级特性

### 并发模式

```
Go 并发模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Worker Pool（工作池）                                             │
│    jobs := make(chan Job, 100)                                      │
│    results := make(chan Result, 100)                                │
│    for i := 0; i < numWorkers; i++ {                               │
│        go func() {                                                  │
│            for job := range jobs {                                  │
│                results <- process(job)                              │
│            }                                                        │
│        }()                                                          │
│    }                                                                │
│                                                                     │
│ 2. Fan-Out / Fan-In（扇出扇入）                                      │
│    // 多个 goroutine 并行处理，结果合并                              │
│                                                                     │
│ 3. Pipeline（流水线）                                                │
│    // 多阶段处理：生成 → 处理 → 过滤 → 输出                          │
│                                                                     │
│ 4. Context 传播                                                      │
│    // 取消传播 + 超时控制 + 值传递                                   │
│                                                                     │
│ 5. sync.Pool（对象池）                                               │
│    // 复用对象，减少 GC 压力                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 性能优化

```
Go 性能优化清单：
1. 避免不必要的内存分配
   - 使用 []byte 替代 string（减少拷贝）
   - sync.Pool 复用对象
   - 预切片容量

2. 减少 GC 压力
   - 对象池化
   - 避免大对象（> 32KB 不走 MCache）
   - 减少指针使用

3. 并发优化
   - GOMAXPROCS = CPU 核心数
   - 避免锁竞争（无锁数据结构）
   - 减少上下文切换

4. 数据结构优化
   - 用 map[string]int 替代结构体数组
   - 用 slice 替代链表
   - 用数组替代 map（小数据量）
```

---

## 第二部分：架构设计原则

### 系统设计方法论

```
架构设计三要素：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 需求分析                                                          │
│    • 功能需求：系统要做什么                                           │
│    • 非功能需求：性能/可用性/扩展性                                   │
│    • 约束条件：技术栈/时间/预算                                       │
│                                                                     │
│ 2. 架构设计                                                          │
│    • 分层：接入层 → 业务层 → 数据层                                  │
│    • 模块化：高内聚低耦合                                            │
│    • 可扩展：预留扩展点                                               │
│    • 容错：降级/熔断/重试                                            │
│                                                                     │
│ 3. 落地实施                                                          │
│    • 技术选型：Go/Java/Python                                        │
│    • 数据库：MySQL/Redis/ES                                          │
│    • 中间件：Kafka/RabbitMQ                                          │
│    • 部署：Docker/K8s                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 高并发系统设计

```
高并发设计模式：
1. 缓存层：多级缓存（本地 → Redis → DB）
2. 异步化：消息队列削峰填谷
3. 限流：令牌桶/漏桶
4. 降级：非核心功能关闭
5. 扩容：水平扩展 + 弹性伸缩

广告场景：
• 竞价请求：缓存 + 异步 + 限流
• 数据统计：离线计算 + 预聚合
• 创意上传：CDN + 异步处理
```

### 微服务设计

```
微服务拆分原则：
1. 按业务域拆分（DDD 限界上下文）
2. 服务粒度适中（不大不小）
3. 接口稳定（向后兼容）
4. 数据隔离（每个服务有自己的 DB）
5. 独立部署（CI/CD 流水线）

服务间通信：
• 同步：REST/gRPC
• 异步：消息队列
• 事件：Event Sourcing
```

---

## 第三部分：自测题

### Q1: Go 如何减少 GC 压力？

**A**: sync.Pool 复用对象、避免大对象、减少指针、预分配容量。

### Q2: 高并发系统的关键设计？

**A**: 多级缓存、异步化、限流、降级、扩容。

### Q3: 微服务拆分原则？

**A**: 按业务域、粒度适中、接口稳定、数据隔离、独立部署。

---

## Go 代码实战：高并发架构核心模式

### 1. Worker Pool + Task Queue（生产级）

```go
package workerpool

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
)

// Task 任务定义
type Task struct {
	ID       string
	Payload  []byte
	Deadline time.Time
	Retries  int
}

// Result 任务结果
type Result struct {
	TaskID string
	Output []byte
	Err    error
}

// WorkerPool 工作池
type WorkerPool struct {
	tasks    chan *Task
	results  chan *Result
	workers  int
	wg       sync.WaitGroup
	stopped  atomic.Bool
	ctx      context.Context
	cancel   context.CancelFunc
}

func NewWorkerPool(ctx context.Context, workers, queueSize int) *WorkerPool {
	cctx, cancel := context.WithCancel(ctx)
	return &WorkerPool{
		tasks:   make(chan *Task, queueSize),
		results: make(chan *Result, queueSize),
		workers: workers,
		ctx:     cctx,
		cancel:  cancel,
	}
}

func (wp *WorkerPool) Start() {
	for i := 0; i < wp.workers; i++ {
		wp.wg.Add(1)
		go wp.worker(i)
	}
}

func (wp *WorkerPool) worker(id int) {
	defer wp.wg.Done()
	for {
		select {
		case task, ok := <-wp.tasks:
			if !ok {
				return
			}
			result := wp.process(task)
			wp.results <- result
			
		case <-wp.ctx.Done():
			return
		}
	}
}

func (wp *WorkerPool) process(task *Task) *Result {
	// 模拟处理
	output := doWork(task.Payload)
	return &Result{
		TaskID: task.ID,
		Output: output,
	}
}

func (wp *WorkerPool) Submit(task *Task) error {
	if wp.stopped.Load() {
		return fmt.Errorf("pool stopped")
	}
	
	select {
	case wp.tasks <- task:
		return nil
	case <-wp.ctx.Done():
		return wp.ctx.Err()
	default:
		return fmt.Errorf("task queue full")
	}
}

func (wp *WorkerPool) Results() <-chan *Result {
	return wp.results
}

func (wp *WorkerPool) Stop() {
	wp.stopped.Store(true)
	wp.cancel()
	close(wp.tasks)
	wp.wg.Wait()
	close(wp.results)
}
```

### 2. 优雅关闭（Graceful Shutdown）

```go
package server

import (
	"context"
	"net/http"
	"os/signal"
	"syscall"
	"time"
)

// GracefulServer 支持优雅关闭的服务器
type GracefulServer struct {
	httpServer *http.Server
	workerPool *WorkerPool
}

func (s *GracefulServer) Start(ctx context.Context) error {
	s.workerPool.Start()
	
	// 信号监听
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	
	go func() {
		<-sigCh
		s.shutdown(ctx)
	}()
	
	return s.httpServer.ListenAndServe()
}

func (s *GracefulServer) shutdown(ctx context.Context) {
	// 1. 停止接受新请求
	s.httpServer.Shutdown(ctx)
	
	// 2. 等待现有请求完成
	done := make(chan struct{})
	go func() {
		s.workerPool.Stop()
		close(done)
	}()
	
	select {
	case <-done:
		fmt.Println("shutdown complete")
	case <-time.After(30 * time.Second):
		fmt.Println("shutdown timeout, force exit")
	}
}
```

### 自测题

<details>
<summary>Q1: WorkerPool 的 queueSize 设多少合适？太大和太小的影响？</summary>

**答案**：

| queueSize | 优点 | 缺点 | 适用场景 |
|-----------|------|------|---------|
| 0（无缓冲） | 零内存，天然背压 | 提交阻塞 | 低延迟要求 |
| 100-1000 | 吸收突发 | OOM风险 | **生产标准** |
| 10000+ | 完全异步 | 内存占用大，延迟不可控 | 批量离线任务 |

**选择原则**：queueSize = workers × 平均处理时间 / 目标延迟。例如 100 workers × 10ms / 5ms = 200。

</details>

<details>
<summary>Q2: GracefulShutdown 中为什么先 stop accepting 再 stop workers？顺序反了会怎样？</summary>

**答案**：

**正确顺序**：
1. `httpServer.Shutdown()` → 停止接受新请求，但继续处理已有请求
2. `workerPool.Stop()` → 停止处理新任务，等队列清空

**反序的后果**：如果先停 worker pool，httpServer 还在接受请求 → 请求进来后找不到 worker → panic 或返回错误。

</details>

<details>
<summary>Q3: sync/atomic.Bool 相比 sync.Mutex 保护 bool 变量有什么优势？</summary>

**答案**：

| 特性 | atomic.Bool | sync.Mutex |
|------|-------------|------------|
| 性能 | 无锁，CPU指令级 | 有锁，可能阻塞 |
| 适用场景 | 单变量读写 | 复杂状态 |
| 可组合性 | ❌ 只能保护一个值 | ✅ 可保护任意数据 |

广告平台中 `stopped` 这种简单标志位用 atomic，因为它只需要原子读写，不需要保护复合状态。

</details>
