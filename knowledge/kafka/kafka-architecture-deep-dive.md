# Kafka 核心架构深度蒸馏

> 来源：Apache Kafka 官方源码
> 蒸馏日期：2026-01-15
> 核心价值：生产级消息队列 + 消费者组设计

---

## 一、Kafka Consumer 架构

### 1.1 Consumer Group 设计

**源码摘录**（`KafkaConsumer.java`）：
```java
/**
 * Kafka uses the concept of consumer groups to allow a pool of processes 
 * to divide the work of consuming and processing records.
 * 
 * All consumer instances sharing the same group.id will be part of 
 * the same consumer group.
 * 
 * Each partition is assigned to exactly one consumer in the group.
 */
public class KafkaConsumer<K, V> implements Consumer<K, V> {
    
    private final ConsumerDelegate<K, V> delegate;
    private final SubscriptionState subscriptions;
    private final Coordinator coordinator;
    
    /**
     * Consumer liveness detection:
     * - Heartbeat to broker
     * - max.poll.interval.ms: proactively leave group if no progress
     */
}
```

**设计意图**：
```
问题：如何实现水平扩展的消费者？

方案：
1. Consumer Group 概念
   - 同一 group.id 的成员共享负载
   - 每个 partition 只分配给一个 consumer
   
2. 自动 Rebalancing
   - 成员加入/离开时自动重新分配
   - 使用 RebalanceListener 处理业务逻辑
   
3. Liveness 检测
   - Heartbeat 机制
   - max.poll.interval.ms 防止 livelock
```

**实战配置**：
```properties
# consumer.properties
group.id=ad-bidding-consumers
max.poll.interval.ms=300000  # 5分钟
session.timeout.ms=30000     # 30秒心跳超时
heartbeat.interval.ms=10000  # 10秒心跳间隔
max.poll.records=500         # 每次拉取记录数
```

### 1.2 Offset 管理

```java
/**
 * Two notions of position:
 * 
 * 1. position() - offset of next record to receive
 *    - Automatically advances on poll()
 *    - Not persisted
 * 
 * 2. committed position - last offset stored securely
 *    - Persists across restarts
 *    - Can commit manually or automatically
 */
public class KafkaConsumer<K, V> {
    
    public ConsumerRecord<K, V> poll(Duration timeout) {
        // Fetch records from broker
        // Advance position automatically
    }
    
    public void commitSync() {
        // Synchronous commit
    }
    
    public void commitAsync(OffsetCommitCallback callback) {
        // Asynchronous commit
    }
}
```

**实战经验**：
```go
// Go 消费者实现
func (c *Consumer) processRecords(records []*sarama.ConsumerMessage) {
    for _, record := range records {
        // 1. 处理消息
        result := c.handler(record)
        
        // 2. 手动提交 offset
        c.session.MarkMessage(record, "")
    }
    
    // 3. 批量提交
    c.session.Commit()
}

// 注意：避免在 poll 回调中做耗时操作
// 应该异步处理，然后提交 offset
```

---

## 二、Kafka Producer 架构

### 2.1 生产者核心设计

**源码摘录**：
```java
/**
 * The producer is thread-safe and sharing a single producer instance 
 * across threads will generally be faster than having multiple instances.
 * 
 * The send() method is asynchronous. It adds the record to a buffer 
 * of pending record sends and immediately returns.
 */
public class KafkaProducer<K, V> implements Producer<K, V> {
    
    private final RecordAccumulator accumulator;  // 缓冲池
    private final Sender sender;                   // 发送线程
    private final ProducerMetadata metadata;       // 元数据
    private final BufferPool bufferPool;          // 内存池
    
    public Future<RecordMetadata> send(ProducerRecord<K, V> record, 
                                        Callback callback) {
        // 1. 序列化和分区
        // 2. 添加到 accumulator
        // 3. 立即返回 Future
    }
}
```

**关键配置**：
```properties
# producer.properties
bootstrap.servers=localhost:9092
acks=all                    # 最强一致性
retries=Int.MAX_VALUE       # 无限重试
batch.size=16384            # 16KB 批处理
linger.ms=5                 # 等待 5ms 凑批
buffer.memory=33554432      # 32MB 缓冲
compression.type=lz4        # LZ4 压缩
```

### 2.2 分区策略

```java
/**
 * Partitioning logic:
 * 1. If key is specified → hash(key) % numPartitions
 * 2. If no key → round-robin across partitions
 * 3. Custom partitioner → implement Partitioner interface
 */
public class BuiltInPartitioner implements Partitioner {
    
    public int partition(String topic, Object key, byte[] keyBytes,
                         Object value, byte[] valueBytes, 
                         Cluster cluster) {
        List<PartitionInfo> partitions = cluster.partitionsForTopic(topic);
        int numPartitions = partitions.size();
        
        if (keyBytes == null) {
            // Round-robin
            return stickyKeys.next(numPartitions);
        }
        
        // Hash-based partitioning
        return Utils.toPositive(Utils.murmur2(keyBytes)) % numPartitions;
    }
}
```

**实战应用**：
```go
// 广告系统中的分区策略
// 场景：同一 campaign 的消息需要顺序处理

type CampaignPartitioner struct{}

func (p *CampaignPartitioner) Partition(topic string, key []byte) int {
    // 解析 campaign_id
    campaignID := parseCampaignID(key)
    
    // 确保同一 campaign 的消息在同一分区
    numPartitions := 16
    return int(campaignID % uint32(numPartitions))
}
```

---

## 三、生产级调优

### 3.1 Consumer 调优

```properties
# 消费速度控制
max.poll.records=1000          # 每次拉取记录数
fetch.min.bytes=1              # 最小拉取字节数
fetch.max.wait.ms=100          # 最大等待时间

# 批处理优化
auto.offset.reset=latest       # 从最新开始
enable.auto.commit=false       # 手动提交
```

### 3.2 Producer 调优

```properties
# 吞吐量优化
batch.size=32768               # 32KB 批次
linger.ms=10                   # 等待 10ms
compression.type=zstd          # ZSTD 压缩
max.in.flight.requests.per.connection=5

# 可靠性优化
acks=all
retries=Int.MAX_VALUE
delivery.timeout.ms=120000
```

### 3.3 Topic 设计

```sql
-- 广告系统的 Topic 设计
CREATE TOPIC:

-- 1. 原始事件流（高吞吐）
ads.events.raw           -- 所有广告事件
partitions=48, replicas=3

-- 2. 用户行为流
ads.events.user.behavior -- 用户点击/曝光
partitions=24, replicas=3

-- 3. 聚合结果流
ads.aggregations.hourly  -- 小时级聚合
partitions=12, replicas=3

-- 4. 告警流
ads.alerts.critical      -- 关键告警
partitions=6, replicas=3
```

---

## 四、常见问题排查

### 4.1 Consumer Lag

```bash
# 查看消费延迟
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group ad-bidding-consumers \
  --describe

# 关键指标
GROUP              TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
ad-bidding-        ads.events      0          1000000         1000500         500
```

### 4.2 Rebalance 频繁

```bash
# 检查消费者健康状态
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group ad-bidding-consumers \
  --state

# 常见原因：
# 1. max.poll.interval.ms 设置过小
# 2. 消费者处理消息耗时过长
# 3. 网络不稳定导致心跳超时
```

### 4.3 消息重复

```properties
# 幂等生产者
enable.idempotence=true    # Kafka 0.11+ 默认开启
```

---

## 五、核心洞察总结

```
1. Consumer Group 设计
   - 水平扩展的核心机制
   - Partition 独占保证有序性
   - Rebalancing 透明化处理

2. Offset 管理
   - 双位置设计（当前 vs 已提交）
   - 手动提交保证处理完成后才推进
   - 支持跨会话恢复

3. Producer 设计
   - 异步发送 + 批量压缩
   - 分区策略决定消息分布
   - 幂等性保证 exactly-once
```

---

**核心价值**：Kafka 的核心价值在于"简单但有保证"——Consumer Group 模型解决了分布式消费的难题，Offset 机制保证了消息的可恢复性。
EOF
echo "✅ Kafka 深度文档已创建"