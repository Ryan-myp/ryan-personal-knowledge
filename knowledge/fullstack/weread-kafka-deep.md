
---

## Go 代码实战：Kafka 消费者组实现

### 1. 消费者组协调器

```go
package kafka

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// ConsumerGroup 消费者组
type ConsumerGroup struct {
	groupID    string
	members    sync.Map
	brokers    []*Broker
	partitions map[string][]int32 // topic -> partitions
	mu         sync.Mutex
}

// Consumer 消费者实例
type Consumer struct {
	ID         string
	Topic      string
	Partition  int32
	Offset     int64
	handler    func(*Message) error
	stopped    chan struct{}
}

func (c *Consumer) Start(ctx context.Context) error {
	c.stopped = make(chan struct{})
	
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			msgs, err := c.fetchMessages(ctx)
			if err != nil {
				return err
			}
			
			for _, msg := range msgs {
				if err := c.handler(msg); err != nil {
					// 处理失败，offset 不回移
					fmt.Printf("handler error: %v\n", err)
					continue
				}
				c.Offset = msg.Offset + 1
			}
			
		case <-ctx.Done():
			return ctx.Err()
		case <-c.stopped:
			return nil
		}
	}
}

func (c *Consumer) fetchMessages(ctx context.Context) ([]*Message, error) {
	// 从 Kafka broker 拉取消息
	req := &FetchRequest{
		Topic:     c.Topic,
		Partition: c.Partition,
		Offset:    c.Offset,
		MaxBytes:  1048576, // 1MB
	}
	
	broker := c.getBrokerForPartition(c.Partition)
	resp, err := broker.Fetch(ctx, req)
	if err != nil {
		return nil, err
	}
	
	return resp.Messages, nil
}

func (c *Consumer) Stop() {
	close(c.stopped)
}
```

### 2. 精确一次语义（At-Least-Once）

```go
package kafka

import (
	"context"
	"sync"
)

// OffsetManager 偏移量管理器
type OffsetManager struct {
	mu        sync.Mutex
	offsets   map[string]int64 // "topic:partition" -> offset
	dirty     map[string]bool  // 标记哪些需要持久化
}

func NewOffsetManager() *OffsetManager {
	return &OffsetManager{
		offsets: make(map[string]int64),
		dirty:   make(map[string]bool),
	}
}

func (om *OffsetManager) Commit(topic string, partition int32, offset int64) {
	om.mu.Lock()
	defer om.mu.Unlock()
	
	key := fmt.Sprintf("%s:%d", topic, partition)
	om.offsets[key] = offset
	om.dirty[key] = true
}

func (om *OffsetManager) Flush(ctx context.Context) error {
	om.mu.Lock()
	defer om.mu.Unlock()
	
	for key, dirty := range om.dirty {
		if !dirty {
			continue
		}
		
		// 提交到 Kafka
		offset := om.offsets[key]
		parts := strings.Split(key, ":")
		topic := parts[0]
		partition := parseInt32(parts[1])
		
		if err := commitOffset(ctx, topic, partition, offset); err != nil {
			return err
		}
		
		delete(om.dirty, key)
	}
	
	return nil
}

func (om *OffsetManager) GetOffset(topic string, partition int32) int64 {
	om.mu.Lock()
	defer om.mu.Unlock()
	return om.offsets[fmt.Sprintf("%s:%d", topic, partition)]
}
```

### 自测题

<details>
<summary>Q1: Consumer 的 fetchMessages 为什么用 100ms ticker 而不是连续拉取？</summary>

**答案**：

**原因**：
1. 避免空轮询（busy wait）消耗 CPU
2. 给 broker 时间积累消息
3. 控制拉取频率，防止网络拥塞

**Trade-off**：
- 100ms → 延迟和吞吐量的平衡点
- 太短 → CPU 浪费
- 太长 → 消息延迟增加

广告平台推荐 50-100ms。

</details>

<details>
<summary>Q2: At-Least-Once 语义下，如果 handler 执行成功但 offset 没提交，会发生什么？</summary>

**答案**：

**重复消费**——这是 At-Least-Once 的核心特征。

**解决方案**：
1. **幂等性**：handler 必须幂等（相同消息多次处理结果一致）
2. **先提交后处理**：先写 offset 再处理（可能丢消息）
3. **事务性写入**：Kafka 2.4+ 支持事务，保证 exactly-once

广告计费场景必须幂等——同一曝光日志处理两次不能收两份钱。

</details>

<details>
<summary>Q3: OffsetManager 的 dirty map 设计有什么优缺点？</summary>

**答案**：

**优点**：
- 批量提交：只提交 dirty 的 offset，减少 RPC
- 内存高效：不需要持久化所有 offset

**缺点**：
- 崩溃时 dirty 但未提交的 offset 丢失
- 需要定期 flush（如每秒）

生产环境用 Kafka 内置的 offset topic 管理，自己实现的 dirty map 适合轻量级场景。

</details>
