
---

## Go 代码实战：Redis + Kafka + Go 集成架构

### 1. 实时竞价数据管道

```go
package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/IBM/sarama"
	"github.com/go-redis/redis/v8"
)

// BidEvent 竞价事件
type BidEvent struct {
	Timestamp  time.Time `json:"ts"`
	UserID     string    `json:"user_id"`
	CampaignID string    `json:"campaign_id"`
	BidPrice   float64   `json:"bid_price"`
	AdID       string    `json:"ad_id"`
	Win        bool      `json:"win"`
}

// DataPipeline 数据管道
type DataPipeline struct {
	producer sarama.AsyncProducer
	rdb      *redis.Client
	streamCh chan *BidEvent
}

func NewDataPipeline(brokers []string, redisAddr string) (*DataPipeline, error) {
	config := sarama.NewConfig()
	config.Producer.Return.Errors = true
	
	producer, err := sarama.NewAsyncProducer(brokers, config)
	if err != nil {
		return nil, err
	}
	
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})
	
	return &DataPipeline{
		producer: producer,
		rdb:      rdb,
		streamCh: make(chan *BidEvent, 10000),
	}, nil
}

func (p *DataPipeline) Start(ctx context.Context) error {
	// 启动消费者 goroutine
	go p.consumeEvents(ctx)
	
	// 启动 Redis 写入 goroutine
	go p.flushToRedis(ctx)
	
	return nil
}

func (p *DataPipeline) Submit(event *BidEvent) {
	p.streamCh <- event
}

func (p *DataPipeline) consumeEvents(ctx context.Context) {
	for {
		select {
		case event, ok := <-p.streamCh:
			if !ok {
				return
			}
			p.processEvent(ctx, event)
			
		case <-ctx.Done():
			return
		}
	}
}

func (p *DataPipeline) processEvent(ctx context.Context, event *BidEvent) {
	// 1. 发送到 Kafka（实时流）
	payload, _ := json.Marshal(event)
	p.producer.Input() <- &sarama.ProducerMessage{
		Topic: "bid-events",
		Value: sarama.StringEncoder(payload),
	}
	
	// 2. 更新 Redis（实时统计）
	key := fmt.Sprintf("campaign:%s:stats", event.CampaignID)
	p.rdb.IncrByFloat(ctx, key+":impressions", 1)
	if event.Win {
		p.rdb.IncrByFloat(ctx, key+":wins", 1)
		p.rdb.IncrByFloat(ctx, key+":spend", event.BidPrice)
	}
	
	// 3. 写入用户画像缓存
	p.rdb.HSet(ctx, fmt.Sprintf("user:%s:bids", event.UserID), event.AdID, event.BidPrice)
}

func (p *DataPipeline) flushToRedis(ctx context.Context) {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			// 批量刷新到 Redis（减少网络 RTT）
			// ... batch flush logic
		case <-ctx.Done():
			return
		}
	}
}
```

### 2. 布隆过滤器（广告去重）

```go
package bloom

import (
	"math"
	"sync"
)

// BloomFilter 布隆过滤器
type BloomFilter struct {
	bits     []bool
	size     int
	hashFuncs []func([]byte) uint64
	mu       sync.RWMutex
}

func NewBloomFilter(expectedItems int, falsePositiveRate float64) *BloomFilter {
	bitSize := int(math.Ceil(-float64(expectedItems) * math.Log(falsePositiveRate) / (math.Ln2 * math.Ln2)))
	hashCount := int(math.Ceil(float64(bitSize) / float64(expectedItems) * math.Ln2))
	
	filter := &BloomFilter{
		bits:      make([]bool, bitSize),
		size:      bitSize,
		hashFuncs: make([]func([]byte) uint64, hashCount),
	}
	
	// 初始化哈希函数
	for i := 0; i < hashCount; i++ {
		a := uint64(i+1) * 0x9e3779b97f4a7c15 // Golden ratio
		b := uint64(i+1) * 0x243f6a8885a308d3
		filter.hashFuncs[i] = func(data []byte) uint64 {
			h := a
			for _, b := range data {
				h ^= uint64(b)
				h = h*a + b
			}
			return h
		}
	}
	
	return filter
}

func (bf *BloomFilter) Add(item []byte) {
	bf.mu.Lock()
	defer bf.mu.Unlock()
	
	for _, hf := range bf.hashFuncs {
		idx := int(hf(item) % uint64(bf.size))
		bf.bits[idx] = true
	}
}

func (bf *BloomFilter) MightContain(item []byte) bool {
	bf.mu.RLock()
	defer bf.mu.RUnlock()
	
	for _, hf := range bf.hashFuncs {
		idx := int(hf(item) % uint64(bf.size))
		if !bf.bits[idx] {
			return false
		}
	}
	return true
}
```

### 自测题

<details>
<summary>Q1: DataPipeline 的 streamCh buffer 为什么设 10000？</summary>

**答案**：

**Trade-off**：
| Buffer Size | 优点 | 缺点 |
|------------|------|------|
| 0（无缓冲） | 零内存 | 提交阻塞，吞吐低 |
| 1000 | 平衡 | 突发时可能满 |
| **10000** | 吸收突发 | 内存 ~几十MB |
| 100000+ | 完全异步 | OOM风险 |

广告竞价场景 QPS 可达 10万+/秒，10000 可以吸收约 0.1 秒的突发。配合 backpressure（channel 满时拒绝新请求）使用。

</details>

<details>
<summary>Q2: BloomFilter 的 false positive rate 设多少合适？为什么不能设太低？</summary>

**答案**：

**典型值**：0.01（1% 误判率）

**原因**：
- 误判率低 → 需要更多 bits → 内存占用大
- bitSize = -n × ln(p) / (ln2)²
- 100万元素 @ 0.01 FPR ≈ 9.6M bits ≈ 1.2MB
- 100万元素 @ 0.001 FPR ≈ 14.4M bits ≈ 1.8MB（贵50%）

广告去重场景 1% 误判完全可以接受——多处理一条重复曝光的成本远低于多用 50% 内存。

</details>

<details>
<summary>Q3: Redis HSet 写用户画像和 Kafka 写事件日志，哪个更快？为什么架构中两个都要？</summary>

**答案**：

| 操作 | 延迟 | 持久性 | 用途 |
|------|------|--------|------|
| Redis HSet | <1ms | RAM（可配持久化） | **实时查询**（用户画像、频次控制） |
| Kafka Write | <5ms | 磁盘（持久化） | **离线分析**（计费、报表、归因） |

**两个都要的原因**：
1. Redis 提供亚毫秒读取——竞价引擎必须快
2. Kafka 提供持久化审计——计费对账不能丢数据
3. 两者互补：Redis 是"现在"，Kafka 是"历史"

</details>
