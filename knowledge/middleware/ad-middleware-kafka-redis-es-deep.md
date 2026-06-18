# 广告中间件实践：Kafka 事件流/Redis 实时特征/ES 搜索

> 从广告系统视角，深度解析中间件的实际应用

---

## 第一部分：Kafka 在广告系统中的应用

### 广告事件流架构

```
Kafka 在广告系统中的角色：
┌─────────────────────────────────────────────────────────────────────┐
│ 事件流架构：                                                         │
│                                                                     │
│  生产者（Producers）：                                               │
│  • Bidder Service → bid_events                                      │
│  • Tracker Service → impression_events, click_events, conversion_events │
│  • Campaign Service → campaign_events                               │
│  • Creative Service → creative_events                               │
│                                                                     │
│  Topic 设计：                                                        │
│  • ad.impressions.{platform}（曝光事件）                             │
│  • ad.clicks.{platform}（点击事件）                                  │
│  • ad.conversions.{platform}（转化事件）                             │
│  • ad.bids.{platform}（竞价事件）                                    │
│  • ad.campaigns（广告系列事件）                                      │
│  • ad.creatives（创意事件）                                          │
│                                                                     │
│  消费者（Consumers）：                                               │
│  • Real-time Aggregation → Redis（实时聚合）                         │
│  • Fraud Detection → Flink（反欺诈）                                 │
│  • Offline Processing → HDFS/S3（离线处理）                          │
│  • ClickHouse → 数仓（分析）                                         │
│  • Elasticsearch → 日志搜索                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Kafka 配置优化

```yaml
# Kafka Broker 配置（广告场景）
broker.id: 1
num.network.threads: 8
num.io.threads: 16
socket.send.buffer.bytes: 102400
socket.receive.buffer.bytes: 102400
socket.request.max.bytes: 104857600

# 日志配置
log.dirs: /var/kafka-logs
num.partitions: 16
default.replication.factor: 3
min.insync.replicas: 2

# 分区策略（按 campaign_id 哈希）
partitioner.class: org.apache.kafka.clients.producer.RoundRobinPartitioner
# 自定义：按 campaign_id 哈希，保证同一 campaign 的消息在同一分区
# 这样消费时可以并行处理不同 campaign

# 消息保留策略
retention.hours: 168  # 7 天
retention.bytes: -1
segment.bytes: 1073741824  # 1GB

# 压缩
compression.type: lz4
```

### Go 生产者实现

```go
package kafka

import (
	"context"
	"encoding/json"
	"github.com/segmentio/kafka-go"
)

// AdEvent 广告事件
type AdEvent struct {
	Type        string                 `json:"type"`         // impression/click/conversion
	CampaignID  string                 `json:"campaign_id"`
	Platform    string                 `json:"platform"`
	UserID      string                 `json:"user_id,omitempty"`
	DeviceID    string                 `json:"device_id"`
	IP          string                 `json:"ip"`
	Timestamp   int64                  `json:"timestamp"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// Producer 广告事件生产者
type Producer struct {
	writer *kafka.Writer
}

// NewProducer 创建生产者
func NewProducer(brokers []string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:         kafka.TCP(brokers...),
			Topic:        "ad-events",
			Balancer:     &kafka.LeastBytes{},
			Compression:  kafka.LZ4,
			Async:        false,
			RequiredAcks: kafka.RequireAll, // 确保数据不丢
			Timeout:      10 * time.Second,
		},
	}
}

// Publish 发布事件
func (p *Producer) Publish(ctx context.Context, event *AdEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		return err
	}

	msg := kafka.Message{
		Key:   []byte(event.CampaignID), // 按 campaign_id 分区
		Value: data,
		Time:  time.Unix(event.Timestamp, 0),
	}

	return p.writer.WriteMessages(ctx, msg)
}

// PublishBatch 批量发布（提高吞吐）
func (p *Producer) PublishBatch(ctx context.Context, events []*AdEvent) error {
	messages := make([]kafka.Message, len(events))
	for i, event := range events {
		data, _ := json.Marshal(event)
		messages[i] = kafka.Message{
			Key:   []byte(event.CampaignID),
			Value: data,
			Time:  time.Unix(event.Timestamp, 0),
		}
	}
	return p.writer.WriteMessages(ctx, messages...)
}
```

---

## 第二部分：Redis 在广告系统中的应用

### 实时特征存储

```
Redis 在广告系统中的角色：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 实时特征存储                                                      │
│    • user:{user_id}:features → HSET（用户特征）                      │
│    • campaign:{campaign_id}:stats → HSET（广告系列统计）              │
│    • creative:{creative_id}:metrics → HSET（创意指标）                │
│                                                                     │
│ 2. 计数器（曝光/点击/转化）                                          │
│    • counters:impressions:{campaign_id}:{date} → INCR               │
│    • counters:clicks:{campaign_id}:{date} → INCR                    │
│    • counters:conversions:{campaign_id}:{date} → INCR               │
│                                                                     │
│ 3. 排行榜（热门广告/热门创意）                                       │
│    • leaderboards:impressions:{date} → ZADD                         │
│    • leaderboards:clicks:{date} → ZADD                              │
│                                                                     │
│ 4. 预算扣减（原子操作）                                              │
│    • budgets:{campaign_id}:spent → INCRBY                           │
│    • Lua 脚本保证原子性                                              │
│                                                                     │
│ 5. 缓存（广告列表/用户信息）                                         │
│    • ads:{user_id}:{page} → JSON（广告列表缓存）                     │
│    • users:{user_id} → JSON（用户信息缓存）                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Redis Lua 脚本（预算扣减）

```lua
-- deduct_budget.lua
-- 参数：KEYS[1] = budget_key, ARGV[1] = amount

local budget_key = KEYS[1]
local amount = tonumber(ARGV[1])

-- 1. 获取当前花费
local spent = tonumber(redis.call('GET', budget_key) or '0')

-- 2. 获取预算上限
local limit_key = budget_key .. ':limit'
local limit = tonumber(redis.call('GET', limit_key) or '0')

-- 3. 检查是否超限
if spent + amount > limit then
    return -1  -- 预算不足
end

-- 4. 扣减预算
redis.call('INCRBY', budget_key, amount)

-- 5. 设置过期时间（每日重置）
local expire_key = budget_key .. ':expire'
if redis.call('EXISTS', expire_key) == 0 then
    -- 获取当天结束时间
    local today = os.date('%Y-%m-%d')
    local tomorrow = os.date('%Y-%m-%d', os.time({year=os.date('%Y'), month=os.date('%m'), day=os.date('%d')}+86400))
    redis.call('EXPIREAT', budget_key, os.time({year=tomorrow:sub(1,4), month=tomorrow:sub(6,7), day=tomorrow:sub(9,10)}))
end

return 1  -- 扣减成功
```

### Go 调用 Redis Lua 脚本

```go
package redis

import (
	"context"
	"fmt"
	"github.com/go-redis/redis/v8"
)

var deductBudgetScript = redis.NewScript(`
local budget_key = KEYS[1]
local amount = tonumber(ARGV[1])
local spent = tonumber(redis.call('GET', budget_key) or '0')
local limit_key = budget_key .. ':limit'
local limit = tonumber(redis.call('GET', limit_key) or '0')
if spent + amount > limit then
    return -1
end
redis.call('INCRBY', budget_key, amount)
return 1
`)

// DeductBudget 扣减预算
func DeductBudget(ctx context.Context, rdb *redis.Client, campaignID string, amount float64) error {
	budgetKey := fmt.Sprintf("budgets:%s:spent", campaignID)
	limitKey := fmt.Sprintf("budgets:%s:limit", campaignID)
	
	// 设置预算上限（如果不存在）
	rdb.Set(ctx, limitKey, 1000.0, 0) // 假设预算上限 $1000
	
	// 执行 Lua 脚本
	result, err := deductBudgetScript.Run(ctx, rdb, []string{budgetKey}, amount).Int()
	if err != nil {
		return err
	}
	
	if result == -1 {
		return fmt.Errorf("budget exhausted for campaign %s", campaignID)
	}
	
	return nil
}
```

---

## 第三部分：Elasticsearch 在广告系统中的应用

### ES 应用场景

```
Elasticsearch 在广告系统中的角色：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 广告素材搜索                                                      │
│    • 广告主搜索历史素材                                                │
│    • 创意推荐（基于相似性）                                           │
│                                                                     │
│ 2. 日志搜索                                                        │
│    • 广告事件日志（曝光/点击/转化）                                    │
│    • 系统日志（错误/警告）                                            │
│                                                                     │
│ 3. 实时仪表盘                                                       │
│    • 广告表现实时查询                                                │
│    • 多维度聚合（按平台/按campaign/按创意）                           │
│                                                                     │
│ 4. 全文检索                                                        │
│    • 广告标题/描述搜索                                               │
│    • 用户评论搜索                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### ES Mapping 设计

```json
{
  "mappings": {
    "properties": {
      "campaign_id": { "type": "keyword" },
      "platform": { "type": "keyword" },
      "creative_id": { "type": "keyword" },
      "user_id": { "type": "keyword" },
      "device_id": { "type": "keyword" },
      "event_type": { "type": "keyword" },
      "timestamp": { "type": "date" },
      "amount": { "type": "float" },
      "ctr": { "type": "float" },
      "cpc": { "type": "float" },
      "cpa": { "type": "float" },
      "roas": { "type": "float" },
      "ip_address": { "type": "ip" },
      "geo": {
        "type": "geo_point"
      },
      "user_agent": {
        "type": "text",
        "analyzer": "standard"
      },
      "creative_title": {
        "type": "text",
        "analyzer": "ik_max_word"
      },
      "creative_description": {
        "type": "text",
        "analyzer": "ik_max_word"
      }
    }
  },
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.refresh_interval": "5s"
  }
}
```

### Go 查询 ES

```go
package es

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/elastic/go-elasticsearch/v8"
)

// SearchCampaignStats 搜索广告系列统计
func SearchCampaignStats(ctx context.Context, es *elasticsearch.Client, campaignID string) (*CampaignStats, error) {
	// 构建查询
	query := map[string]interface{}{
		"query": map[string]interface{}{
			"term": map[string]interface{}{
				"campaign_id": campaignID,
			},
		},
		"aggs": map[string]interface{}{
			"total_impressions": map[string]interface{}{
				"sum": map[string]interface{}{
					"field": "impressions",
				},
			},
			"total_clicks": map[string]interface{}{
				"sum": map[string]interface{}{
					"field": "clicks",
				},
			},
			"total_spend": map[string]interface{}{
				"sum": map[string]interface{}{
					"field": "amount",
				},
			},
			"avg_ctr": map[string]interface{}{
				"avg": map[string]interface{}{
					"field": "ctr",
				},
			},
		},
	}

	body, _ := json.Marshal(query)
	
	// 执行查询
	res, err := es.Search(
		es.Search.WithContext(ctx),
		es.Search.WithIndex("ad-events"),
		es.Search.WithBody(bytes.NewReader(body)),
	)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	
	// 解析结果
	var result map[string]interface{}
	json.NewDecoder(res.Body).Decode(&result)
	
	stats := &CampaignStats{}
	// 解析聚合结果...
	
	return stats, nil
}
```

---

## 第四部分：中间件选型对比

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   场景       │   推荐方案   │   备选方案   │   原因       │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ 事件流       │ Kafka        │ Pulsar       │ 生态成熟     │
│ 实时特征     │ Redis        │ Memcached    │ 数据结构丰富 │
│ 搜索         │ Elasticsearch│ Meilisearch  │ 全文检索     │
│ 数仓         │ ClickHouse   │ Druid        │ 列式存储     │
│ 向量检索     │ FAISS        │ Milvus       │ 轻量级       │
│ 消息队列     │ Kafka        │ RabbitMQ     │ 高吞吐       │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 第五部分：自测题

### Q1: 为什么广告事件流用 Kafka 而不是 RabbitMQ？

**A**:
- Kafka 高吞吐（百万级消息/秒），RabbitMQ 适合低延迟场景
- Kafka 持久化，支持回溯消费
- Kafka 分区并行，适合大规模数据处理

### Q2: Redis Lua 脚本为什么能保证原子性？

**A**: Lua 脚本在 Redis 中是原子执行的，不会被其他命令打断。这对于预算扣减等需要原子操作的场景至关重要。

### Q3: ES 和 ClickHouse 在广告系统中的分工？

**A**:
- **ES**: 日志搜索、全文检索、实时仪表盘
- **ClickHouse**: 大规模数据分析、归因分析、BI 报表
- ES 适合 OLTP 场景，ClickHouse 适合 OLAP 场景

---

## 第六部分：生产实践

### 1. Kafka 运维

```
Kafka 运维要点：
1. 监控：broker lag、producer throughput、consumer lag
2. 扩容：增加 partition 提升吞吐
3. 备份：定期备份 topic 元数据
4. 清理：设置合理的 retention 策略
```

### 2. Redis 运维

```
Redis 运维要点：
1. 监控：memory usage、hit rate、latency
2. 持久化：RDB + AOF
3. 集群：Redis Cluster 自动分片
4. 淘汰策略：allkeys-lru
```

### 3. ES 运维

```
ES 运维要点：
1. 监控：cluster health、indexing rate、search latency
2. 分片：合理设置 shard 数量
3. 索引生命周期：ILM 自动滚动
4. 压缩：启用 gzip 压缩减少存储
```
