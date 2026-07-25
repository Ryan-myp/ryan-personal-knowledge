# 微信读书精华：技术未读完书籍蒸馏

> 来源：《Redis设计与实现》《深入理解Go语言》《Kafka权威指南》《Apache Kafka实战》《秒懂设计模式》《Go底层原理与工程化实践》《架构师启示录》《ClickHouse原理解析与应用实践》《Head First Go语言程序设计》《Go语言精进之路》《Elasticsearch源码解析与优化实战》《算法图解》《剑指Offer》《深入剖析Nginx》《Python大数据架构全栈开发与应用》《图数据库原理、架构与应用》《微服务设计》《从Paxos到Zookeeper》《ClickHouse性能之巅》《架构解密》《Go程序开发实战宝典》《大话计算机》《设计模式：可复用面向对象软件的基础》《每天5分钟玩转Docker容器技术》《秒懂算法》《Python极简讲义》《企业应用架构模式》《大数据架构商业之路》《深度探索Go语言》《七周七数据库》《分布式系统架构》《一本书讲透Elasticsearch》《HBase原理与实践》《高效使用Redis》《Go语言学习指南》《架构师应该知道的37件事》《Go语言精进之路2》《我的第一本算法书》《Spark快速大数据分析》《PostgreSQL实战》《大数据技术原理与应用》《大数据技术体系详解》《Elasticsearch实战与原理解析》《Kubernetes快速入门》《千金良方：MySQL性能优化金字塔法则》《Redis开发与运维》《Go编程世界》《MongoDB进阶与实战》《数据库系统内幕》《etcd技术内幕》《凤凰架构》《大数据技术基础》《用Go语言自制解释器》
> 状态：未读完（基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：Go 语言深度

### Go 内存模型

```
Go 内存分配：
┌─────────────────────────────────────────────────────────────────────┐
│ Malloc：堆内存分配器                                                 │
│ • 小对象（<32KB）：MCache（每 P 私有）                              │
│ • 中对象（32KB-1MB）：MSpan（每 M 管理）                             │
│ • 大对象（>1MB）：直接 mmap                                         │
│                                                                     │
│ GC 策略：                                                            │
│ • 三色标记清除                                                       │
│ • 写屏障：阻止对象引用变化                                           │
│ • 混合写屏障：平衡性能和复杂性                                       │
│ • STW：短停顿，<1ms                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Go 并发模型

```
GMP 调度：
┌─────────────────────────────────────────────────────────────────────┐
│ G（Goroutine）：协程，包含栈、状态、调度信息                         │
│ M（Machine）：操作系统线程，执行 G                                   │
│ P（Processor）：处理器，管理本地 G 队列                              │
│                                                                     │
│ 调度策略：                                                           │
│ • 工作窃取：P 之间负载均衡                                          │
│ • 网络轮询：NetPoller 处理 IO                                       │
│ • 系统调用：阻塞时释放 P                                             │
│ • 抢占调度：长时间运行的 G 会被抢占                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：Redis 核心原理

### Redis 数据结构

```
Redis 核心数据结构：
┌────────────────┬────────────┬────────────┬────────────┐
│     类型       │  内存模型  │  适用场景  │  复杂度    │
├────────────────┼────────────┼────────────┼────────────┤
│ String         │ SDS        │ 缓存/计数  │ O(1)      │
│ Hash           │ ZipList    │ 用户对象   │ O(1)      │
│ List           │ QuickList  │ 消息队列   │ O(1)      │
│ Set            │ IntSet/HT  │ 去重/交集  │ O(1)      │
│ Sorted Set     │ SkipList   │ 排行榜     │ O(logN)   │
│ Bitmap         │ 位数组     │ 活性分析   │ O(1)      │
│ HyperLogLog    │ 概率结构   │ 基数统计   │ O(1)      │
│ Geo            │ SortedSet  │ 地理位置   │ O(logN)   │
└────────────────┴────────────┴────────────┴────────────┘

广告场景：
• String：用户画像缓存、计数器
• Hash：广告主信息、创意属性
• List：广告请求队列
• Set：用户兴趣标签
• Sorted Set：广告排名、出价排序
```

### Redis 持久化

```
持久化策略：
┌────────────────┬────────────┬────────────┬────────────┐
│     类型       │  安全性    │  性能      │  文件大小  │
├────────────────┼────────────┼────────────┼────────────┤
│ RDB            │ 中        │ 高        │ 小        │
│ AOF            │ 高        │ 中        │ 大        │
│ AOF+RDB        │ 最高      │ 中        │ 中        │
└────────────────┴────────────┴────────────┴────────────┘

推荐配置：
• 缓存：RDB（性能优先）
• 会话：AOF（安全优先）
• 重要数据：AOF+RDB（兼顾）
```

---

## 第三部分：Kafka 高级特性

### Kafka 高级配置

```
生产环境配置：
┌─────────────────────────────────────────────────────────────────────┐
│ Broker 配置：                                                        │
│ • num.partitions：默认分区数                                        │
│ • replication.factor：默认副本数                                    │
│ • min.insync.replicas：最小同步副本数                               │
│ • log.retention.hours：日志保留时间                                 │
│ • log.segment.bytes：段文件大小                                     │
│                                                                     │
│ Producer 配置：                                                      │
│ • acks：确认级别（0/1/all）                                         │
│ • retries：重试次数                                                 │
│ • batch.size：批量大小                                              │
│ • linger.ms：等待时间                                               │
│ • compression.type：压缩算法                                        │
│                                                                     │
│ Consumer 配置：                                                      │
│ • auto.offset.reset：偏移量策略                                    │
│ • enable.auto.commit：自动提交                                     │
│ • max.poll.records：每次拉取记录数                                 │
│ • session.timeout.ms：会话超时时间                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Kafka 监控

```
关键指标：
┌─────────────────────────────────────────────────────────────────────┐
│ Broker 指标：                                                        │
│ • Under Replicated Partitions：未同步分区数                         │
│ • Offline Partitions Count：离线分区数                              │
│ • Bytes In/Out：吞吐量                                             │
│ • Requests Per Second：QPS                                         │
│                                                                     │
│ Consumer 指标：                                                      │
│ • Lag：消费延迟                                                     │
│ • Commit Rate：提交速率                                             │
│ • Poll Rate：拉取速率                                               │
│ • Rebalance Rate：重平衡频率                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: Go 内存分配的三级策略？

**A**: 小对象（MCache）、中对象（MSpan）、大对象（mmap）。

### Q2: Redis 五种核心数据结构？

**A**: String、Hash、List、Set、Sorted Set。

### Q3: Kafka 生产环境关键配置？

**A**: acks=all、retries=3、compression=lz4、min.insync.replicas=2。

---

## Go 代码实战：技术基础核心模块

### 1. 连接池（通用）

```go
package pool

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// PooledObject 池化对象
type PooledObject struct {
	ID        int
	CreatedAt time.Time
	LastUsed  time.Time
	InUse     bool
}

// ObjectPool 对象池（通用连接池）
type ObjectPool struct {
	factory     func() (interface{}, error)
	destroy     func(interface{})
	maxSize     int
	idleTimeout time.Duration
	mu          sync.Mutex
	available   []interface{}
	inUse       map[int]interface{}
	nextID      int
	stats       PoolStats
}

type PoolStats struct {
	Created    int
	Destroyed  int
	WaitCount  int64
	WaitTime   time.Duration
}

func NewObjectPool(factory func() (interface{}, error), maxSize int, idleTimeout time.Duration) *ObjectPool {
	return &ObjectPool{
		factory:     factory,
		maxSize:     maxSize,
		idleTimeout: idleTimeout,
		inUse:       make(map[int]interface{}),
	}
}

func (p *ObjectPool) Acquire(ctx context.Context) (interface{}, int, error) {
	start := time.Now()
	
	p.mu.Lock()
	defer p.mu.Unlock()
	
	// 从空闲池取
	if len(p.available) > 0 {
		obj := p.available[len(p.available)-1]
		p.available = p.available[:len(p.available)-1]
		p.inUse[p.nextID] = obj
		id := p.nextID
		p.nextID++
		return obj, id, nil
	}
	
	// 创建新对象（未达上限）
	if len(p.inUse)+len(p.available) < p.maxSize {
		obj, err := p.factory()
		if err != nil {
			return nil, 0, err
		}
		p.inUse[p.nextID] = obj
		id := p.nextID
		p.nextID++
		p.stats.Created++
		return obj, id, nil
	}
	
	// 池满，等待
	select {
	case <-time.After(5 * time.Second):
		return nil, 0, fmt.Errorf("pool acquire timeout")
	case <-ctx.Done():
		return nil, 0, ctx.Err()
	}
}

func (p *ObjectPool) Release(id int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	obj, ok := p.inUse[id]
	if !ok {
		return
	}
	delete(p.inUse, id)
	p.available = append(p.available, obj)
}

func (p *ObjectPool) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	for _, obj := range p.available {
		if p.destroy != nil {
			p.destroy(obj)
			p.stats.Destroyed++
		}
	}
	for _, obj := range p.inUse {
		if p.destroy != nil {
			p.destroy(obj)
			p.stats.Destroyed++
		}
	}
	p.available = nil
	p.inUse = make(map[int]interface{})
}
```

### 2. 限流器（漏桶算法）

```go
package rate

import (
	"sync"
	"time"
)

// LeakyBucket 漏桶限流器
type LeakyBucket struct {
	mu         sync.Mutex
	capacity   int
	leakRate   time.Duration // 每多少秒漏一滴
	water      int
	lastLeak   time.Time
}

func NewLeakyBucket(capacity int, leakRate time.Duration) *LeakyBucket {
	return &LeakyBucket{
		capacity: capacity,
		leakRate: leakRate,
		lastLeak: time.Now(),
	}
}

func (lb *LeakyBucket) Allow() bool {
	lb.mu.Lock()
	defer lb.mu.Unlock()
	
	// 先漏水
	lb.leak()
	
	// 检查是否满了
	if lb.water >= lb.capacity {
		return false
	}
	
	// 加水
	lb.water++
	return true
}

func (lb *LeakyBucket) leak() {
	now := time.Now()
	elapsed := now.Sub(lb.lastLeak)
	drops := int(elapsed / lb.leakRate)
	
	if drops > 0 {
		lb.water = max(0, lb.water-drops)
		lb.lastLeak = now
	}
}
```

### 自测题

<details>
<summary>Q1: ObjectPool 的 Release 为什么把对象放回 available 而不是直接销毁？</summary>

**答案**：

**复用 vs 新建**：
- 新建对象（DB连接/HTTP客户端）成本高（TCP握手、内存分配）
- 复用可以节省 80%+ 的创建开销
- 但需要定期清理空闲对象（idle timeout）

这是 **对象池模式** 的核心——用空间换时间。Go 标准库 `sync.Pool` 也是这个原理。

</details>

<details>
<summary>Q2: 漏桶算法和令牌桶算法的区别？各适用于什么场景？</summary>

**答案**：

| 特性 | 漏桶 | 令牌桶 |
|------|------|--------|
| 输出速率 | **恒定**（匀速流出） | 可变（桶满时可突发） |
| 突发处理 | ❌ 不允许 | ✅ 允许 |
| 平滑流量 | ✅ | ❌ |
| 适用场景 | CDN带宽控制、API限流 | 消息队列、突发请求 |

广告平台：API调用用令牌桶（允许突发），CDN回源用漏桶（匀速）。

</details>

<details>
<summary>Q3: ObjectPool 的 Acquire 超时为什么设 5 秒而不是更长？</summary>

**答案**：

**设计考量**：
- 5秒太长 → 请求堆积，用户体验差
- 5秒太短 → 短暂波动就失败

实际生产中：
- **HTTP请求**：超时 3-5 秒
- **DB查询**：超时 1-3 秒
- **RPC调用**：超时 100ms-1s

关键：**超时时间必须小于客户端期望延迟**。广告竞价请求要求 <50ms，所以连接池获取必须 <1ms（无等待）。

</details>
