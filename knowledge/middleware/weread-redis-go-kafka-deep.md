# 微信读书精华：Redis设计与实现 + 深入理解Go语言 + Kafka权威指南 蒸馏笔记

> 来源：《Redis设计与实现》- 黄健宏
>       《深入理解Go语言》- 刘丹冰
>       《Kafka权威指南（第2版）》- 格温·沙皮拉 等
> 状态：未读完（高价值，基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：Redis 核心原理

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

## 第二部分：Go 语言核心

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

### Q1: Redis 五种核心数据结构？

**A**: String、Hash、List、Set、Sorted Set。

### Q2: Go 内存分配的三级策略？

**A**: 小对象（MCache）、中对象（MSpan）、大对象（mmap）。

### Q3: Kafka 生产环境关键配置？

**A**: acks=all、retries=3、compression=lz4、min.insync.replicas=2。

---

## Go 代码实战：Redis + Kafka + Go 集成模式

### 1. CQRS 事件溯源（Command Query Responsibility Segregation）

```go
package cqrs

import (
	"context"
	"encoding/json"
	"sync"
	"time"
)

// Event 领域事件
type Event struct {
	ID        string    `json:"id"`
	Type      string    `json:"type"`
	Timestamp time.Time `json:"timestamp"`
	Payload   []byte    `json:"payload"`
	Version   int       `json:"version"`
}

// Aggregate 聚合根
type Aggregate struct {
	ID        string
	Version   int
	State     map[string]interface{}
	events    []Event
	mu        sync.Mutex
}

func NewAggregate(id string) *Aggregate {
	return &Aggregate{
		ID:    id,
		State: make(map[string]interface{}),
	}
}

func (a *Aggregate) Apply(eventType string, payload interface{}) {
	a.mu.Lock()
	defer a.mu.Unlock()
	
	data, _ := json.Marshal(payload)
	event := Event{
		ID:        generateID(),
		Type:      eventType,
		Timestamp: time.Now(),
		Payload:   data,
		Version:   a.Version + 1,
	}
	
	a.events = append(a.events, event)
	a.Version++
	
	// 应用事件到状态
	a.applyEvent(&event)
}

func (a *Aggregate) applyEvent(e *Event) {
	switch e.Type {
	case "campaign_created":
		var payload struct {
			Name     string  `json:"name"`
			Budget   float64 `json:"budget"`
			TargetID string  `json:"target_id"`
		}
		json.Unmarshal(e.Payload, &payload)
		a.State["name"] = payload.Name
		a.State["budget"] = payload.Budget
		a.State["target_id"] = payload.TargetID
		a.State["status"] = "active"
		
	case "budget_updated":
		var payload struct {
			NewBudget float64 `json:"new_budget"`
		}
		json.Unmarshal(e.Payload, &payload)
		a.State["budget"] = payload.NewBudget
		
	case "campaign_paused":
		a.State["status"] = "paused"
	}
}

// EventStore 事件存储
type EventStore struct {
	mu       sync.Mutex
	events   []Event
	handlers map[string][]func(*Event)
}

func NewEventStore() *EventStore {
	return &EventStore{
		handlers: make(map[string][]func(*Event)),
	}
}

func (s *EventStore) Append(event *Event) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.events = append(s.events, *event)
	
	// 通知处理器
	for _, handler := range s.handlers[event.Type] {
		handler(event)
	}
	return nil
}

func (s *EventStore) RegisterHandler(eventType string, handler func(*Event)) {
	s.handlers[eventType] = append(s.handlers[eventType], handler)
}

func (s *EventStore) GetEvents(aggregateID string) []Event {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	var result []Event
	for _, e := range s.events {
		if strings.Contains(string(e.Payload), aggregateID) || 
		   strings.Contains(e.Type, aggregateID) {
			result = append(result, e)
		}
	}
	return result
}
```

### 2. 读写分离路由

```go
package routing

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Router 读写路由器
type Router struct {
	writeDB  *DBConn
	readDBs  []*DBConn
	mu       sync.RWMutex
	stats    RoutingStats
}

type RoutingStats struct {
	ReadCount  int64
	WriteCount int64
	LatencyUS  int64 // 微秒
}

func NewRouter(writeDSN, readDSNs []string) (*Router, error) {
	writeDB, err := openDB(writeDSN)
	if err != nil {
		return nil, err
	}
	
	readDBs := make([]*DBConn, 0, len(readDSNs))
	for _, dsn := range readDSNs {
		db, err := openDB(dsn)
		if err != nil {
			continue
		}
		readDBs = append(readDBs, db)
	}
	
	return &Router{
		writeDB: writeDB,
		readDBs: readDBs,
	}, nil
}

func (r *Router) Read(ctx context.Context, query string, args ...interface{}) (*Rows, error) {
	start := time.Now()
	
	// 轮询选择读节点
	r.mu.RLock()
	db := r.readDBs[len(r.stats.ReadCount)%len(r.readDBs)]
	r.mu.RUnlock()
	
	rows, err := db.QueryContext(ctx, query, args...)
	
	r.mu.Lock()
	r.stats.ReadCount++
	r.stats.LatencyUS += time.Since(start).Microseconds()
	r.mu.Unlock()
	
	return rows, err
}

func (r *Router) Write(ctx context.Context, query string, args ...interface{}) (Result, error) {
	start := time.Now()
	
	result, err := r.writeDB.ExecContext(ctx, query, args...)
	
	r.mu.Lock()
	r.stats.WriteCount++
	r.stats.LatencyUS += time.Since(start).Microseconds()
	r.mu.Unlock()
	
	return result, err
}

// StaleReadDetector 主从延迟检测
type StaleReadDetector struct {
	writeBinlogPos uint64
	readBinlogPos  map[int]uint64
	mu             sync.RWMutex
}

func (d *StaleReadDetector) UpdateWritePos(pos uint64) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.writeBinlogPos = pos
}

func (d *StaleReadDetector) CheckStale(readIdx int) bool {
	d.mu.RLock()
	defer d.mu.RUnlock()
	
	readPos, ok := d.readBinlogPos[readIdx]
	if !ok {
		return true // 未知位置，保守认为滞后
	}
	
	return d.writeBinlogPos - readPos > 1000 // 延迟超过1000binlog
}
```

### 自测题

<details>
<summary>Q1: CQRS 的事件溯源模式相比直接存状态有什么优势？</summary>

**答案**：

| 特性 | 直接存状态 | 事件溯源 |
|------|-----------|---------|
| 审计追踪 | ❌ 需要额外表 | ✅ 天然完整历史 |
| 时间旅行 | ❌ | ✅ 重放事件重建任意时刻状态 |
| 调试 | 困难 | 容易（看事件序列） |
| 复杂度 | 低 | 高 |

广告计费场景：**必须用事件溯源**——每笔消费都是不可变事件，方便对账和审计。

</details>

<details>
<summary>Q2: 读写分离的主从延迟问题如何解决？</summary>

**答案**：

**三级方案**：
1. **StaleReadDetector**：检测 binlog 延迟，延迟大时路由到写库
2. **强制路由**：刚写入后的读取强制走写库（write-then-read）
3. **最终一致性**：接受短暂不一致，业务层容忍

广告平台推荐方案1+3：预算扣减后立即可见用方案2，报表查询用方案3。

</details>

<details>
<summary>Q3: Router 的轮询读节点选择有什么缺点？生产环境用什么？</summary>

**答案**：

**轮询缺点**：不考虑节点负载差异——慢节点和快节点分到同样多的请求。

**生产方案**：
```go
// 方案1: 加权轮询（基于响应时间动态调整权重）
// 方案2: 最少连接（选当前连接数最少的）
// 方案3: 一致性哈希（相同查询路由到同一节点，提高缓存命中率）
```

广告平台推荐方案3：用户画像查询用一致性哈希，相同用户总是路由到同一读节点 → Redis 缓存命中率高。

</details>
