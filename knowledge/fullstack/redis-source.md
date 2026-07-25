	store.SetEx("session", "abc123", 30*time.Minute)
	if v, ok := store.Get("name"); ok { fmt.Printf("name=%s\n", v) }

	ps := NewPubSub()
	ch := ps.Subscribe("news")
	ps.Publish("news", "Hello")
	fmt.Printf("Received: %s\n", <-ch)
}

---

## 自测题

### 问题 1
Redis 的 RDB 和 AOF 持久化各有什么优缺点？

<details>
<summary>查看答案</summary>

1. **RDB**: 定时快照，恢复快，数据可能丢失（最后一次快照到崩溃）
2. **AOF**: 每命令追加，数据更安全，文件更大，恢复更慢
3. **混合持久化**: RDB 快照 + AOF 增量，兼顾速度和安全性
4. **实际生产**: 推荐 AOF+混合持久化，RDB 仅做冷备

</details>

### 问题 2
Redis 的过期策略为什么用惰性删除+定期删除？

<details>
<summary>查看答案</summary>

1. **惰性删除**: 访问键时检查过期，延迟释放内存，但可能大量过期键堆积
2. **定期删除**: 周期性抽查 key space，逐步清理过期键
3. **组合策略**: 惰性删除保证实时性，定期删除防止堆积
4. **内存淘汰**: 如果内存满了，触发 LRU/LFU 淘汰策略

</details>
---

## Go 代码实战：Redis 核心概念 Go 实现

### 1. LRU Cache（模拟 Redis 淘汰策略）

```go
package cache

import (
	"sync"
	"time"
)

// LRUEntry 缓存条目
type LRUEntry struct {
	Key      string
	Value    interface{}
	Expires  time.Time
	Priority int // LFU 优先级
}

// LRUCache 基于双向链表 + hash map 的 LRU 缓存
type LRUCache struct {
	mu       sync.Mutex
	capacity int
	items    map[string]*listNode
	head     *listNode
	tail     *listNode
}

type listNode struct {
	key   string
	entry *LRUEntry
	prev  *listNode
	next  *listNode
}

func NewLRUCache(capacity int) *LRUCache {
	return &LRUCache{
		capacity: capacity,
		items:    make(map[string]*listNode),
	}
}

func (c *LRUCache) Get(key string) (*LRUEntry, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	node, ok := c.items[key]
	if !ok {
		return nil, false
	}
	
	// 检查过期
	if time.Now().After(node.entry.Expires) {
		c.removeNode(node)
		delete(c.items, key)
		return nil, false
	}
	
	// 移到头部（最近使用）
	c.moveToHead(node)
	return node.entry, true
}

func (c *LRUCache) Set(key string, value interface{}, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	// 更新已有
	if node, ok := c.items[key]; ok {
		node.entry.Value = value
		node.entry.Expires = time.Now().Add(ttl)
		c.moveToHead(node)
		return
	}
	
	// 容量不足，淘汰尾部
	if len(c.items) >= c.capacity {
		c.evict()
	}
	
	// 新建节点放头部
	entry := &LRUEntry{Key: key, Value: value, Expires: time.Now().Add(ttl)}
	node := &listNode{key: key, entry: entry}
	c.items[key] = node
	c.addToHead(node)
}

func (c *LRUCache) evict() {
	if c.tail != nil {
		delete(c.items, c.tail.key)
		c.removeNode(c.tail)
	}
}

func (c *LRUCache) addToHead(n *listNode) {
	n.next = c.head
	n.prev = nil
	if c.head != nil {
		c.head.prev = n
	}
	c.head = n
	if c.tail == nil {
		c.tail = n
	}
}

func (c *LRUCache) moveToHead(n *listNode) {
	if n == c.head {
		return
	}
	c.removeNode(n)
	c.addToHead(n)
}

func (c *LRUCache) removeNode(n *listNode) {
	if n.prev != nil {
		n.prev.next = n.next
	} else {
		c.head = n.next
	}
	if n.next != nil {
		n.next.prev = n.prev
	} else {
		c.tail = n.prev
	}
}
```

### 2. Pub/Sub 广播系统

```go
package pubsub

import (
	"sync"
)

// Channel 订阅频道
type Channel struct {
	name      string
	subscribers map[int]chan string
	mu        sync.RWMutex
}

// Broadcaster 广播器
type Broadcaster struct {
	channels map[string]*Channel
	mu       sync.RWMutex
	nextID   int
	idMu     sync.Mutex
}

func NewBroadcaster() *Broadcaster {
	return &Broadcaster{
		channels: make(map[string]*Channel),
	}
}

func (b *Broadcaster) Subscribe(channelName string) (int, <-chan string) {
	b.mu.RLock()
	ch, ok := b.channels[channelName]
	b.mu.RUnlock()
	
	if !ok {
		b.mu.Lock()
		ch = &Channel{
			name:        channelName,
			subscribers: make(map[int]chan string),
		}
		b.channels[channelName] = ch
		b.mu.Unlock()
	}
	
	b.idMu.Lock()
	b.nextID++
	subscriberID := b.nextID
	b.idMu.Unlock()
	
	msgChan := make(chan string, 100)
	ch.mu.Lock()
	ch.subscribers[subscriberID] = msgChan
	ch.mu.Unlock()
	
	return subscriberID, msgChan
}

func (b *Broadcaster) Publish(channelName, message string) {
	b.mu.RLock()
	ch, ok := b.channels[channelName]
	b.mu.RUnlock()
	
	if !ok {
		return
	}
	
	ch.mu.RLock()
	for _, sub := range ch.subscribers {
		select {
		case sub <- message:
		default: // 订阅者慢，丢弃消息
		}
	}
	ch.mu.RUnlock()
}

func (b *Broadcaster) Unsubscribe(channelName string, id int) {
	b.mu.RLock()
	ch, ok := b.channels[channelName]
	b.mu.RUnlock()
	
	if !ok {
		return
	}
	
	ch.mu.Lock()
	if sub, exists := ch.subscribers[id]; exists {
		close(sub)
		delete(ch.subscribers, id)
	}
	ch.mu.Unlock()
}
```

### 自测题

<details>
<summary>Q1: LRUCache 的 mutex 粒度太粗，高并发下如何优化？</summary>

**答案**：

**Sharded LRU**：将缓存分成多个分片，每个分片独立锁。
```go
type ShardedLRU struct {
    shards [16]LRUShard  // 16个分片
}
// key % 16 决定分片 → 只锁一个分片
```

Redis 实际用 **single-threaded model**（命令执行单线程），不需要 mutex。Go 实现用 sharding 是最佳实践。

</details>

<details>
<summary>Q2: Pub/Sub 的 channel buffer 设为 100 有什么风险？如何设计背压机制？</summary>

**答案**：

**风险**：buffer 满时 `select default` 会静默丢消息——广告竞价场景下丢一条曝光日志可能影响计费。

**背压方案**：
```go
// 方案1: 阻塞发送（慢消费者拖慢发布者）
case sub <- message:  // 无 default，阻塞

// 方案2: 快速失败 + 降级（推荐）
select {
case sub <- message:
default:
    log.Warn("subscriber slow, dropping", "channel", name)
    metrics.Inc("pubsub.dropped")
}

// 方案3: 环形缓冲区（固定大小覆盖旧消息）
```

</details>

<details>
<summary>Q3: Redis 的惰性删除+定期删除组合策略中，定期删除的频率如何确定？</summary>

**答案**：

Redis 使用 **自适应策略**：每次定期删除后根据耗时调整频率。
- 如果耗时 < 25% 时间预算 → 增加抽查数量
- 如果耗时 > 时间预算 → 减少抽查数量
- 默认每次抽查 20 个 key，每 100ms 执行一次

核心原则：**不让过期清理影响主线程性能**。

</details>
