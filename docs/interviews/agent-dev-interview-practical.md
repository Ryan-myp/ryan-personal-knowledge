# Agent 开发工程师 - 一面面试题（实战版）

> 版本: v2.0  
> 时长: 45-60 分钟  
> 形式: 系统设计 + 中间件选型 + 场景分析 + 代码实现

---

## ⏱️ 时间分配

| 环节 | 时长 | 内容 |
|------|------|------|
| 自我介绍 | 3min | 候选人简述背景 |
| 中间件选型与设计 | 15min | 3-4 道场景题 |
| 系统设计 | 15min | 1-2 道架构题 |
| 代码实现 | 10min | 1 道简单编码题 |
| 项目追问 | 10min | 深挖简历项目 |
| Q&A | 5min | 候选人提问 |

---

## 📋 第一部分：中间件选型与设计（15min）

### Q1: Redis 选型（5min）

**场景**: 你要设计一个广告平台的实时竞价系统，需要支持：
- 高频读写（每秒 10 万+ QPS）
- 延迟敏感（< 10ms）
- 需要分布式锁（防止重复出价）

**问题**: 
1. 你会选择 Redis 的哪种数据结构？为什么？
2. 如何实现分布式锁？有哪些注意事项？
3. 如果 Redis 宕机了怎么办？

**期望回答**:

| 需求 | 选型 | 原因 |
|------|------|------|
| 高频读写 | Redis String/Hash | 内存存储，O(1) 复杂度 |
| 分布式锁 | Redis + SET NX PX | 原子操作，带过期时间防死锁 |
| 高可用 | Redis Cluster/Sentinel | 主从复制，自动故障转移 |

```java
// Redis 分布式锁示例
public class RedisLock {
    private final RedisTemplate<String, String> redisTemplate;
    private static final String LOCK_PREFIX = "lock:";
    
    public boolean tryLock(String key, String value, long expireMs) {
        String lockKey = LOCK_PREFIX + key;
        // SET key value NX EX seconds
        Boolean result = redisTemplate.opsForValue()
            .setIfAbsent(lockKey, value, expireMs, TimeUnit.MILLISECONDS);
        return Boolean.TRUE.equals(result);
    }
    
    public boolean releaseLock(String key, String value) {
        String lockKey = LOCK_PREFIX + key;
        // 使用 Lua 脚本保证原子性
        String script = "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                       "return redis.call('del', KEYS[1]) else return 0 end";
        Long result = redisTemplate.execute(new DefaultRedisScript<>(script, Long.class),
            Collections.singletonList(lockKey), value);
        return result != null && result > 0;
    }
}
```

**加分项**:
- 提到 Redis 持久化策略（RDB vs AOF）
- 提到缓存穿透/击穿/雪崩的解决方案
- 提到 Redlock 算法（多节点分布式锁）

---

### Q2: Kafka 选型（5min）

**场景**: 广告平台需要处理海量曝光日志，要求：
- 高吞吐（每秒百万级消息）
- 消息顺序性（同一广告主的曝光顺序）
- 消息可靠性（不丢失）
- 消费回溯能力（历史数据重新处理）

**问题**:
1. 为什么选择 Kafka 而不是 RocketMQ/RabbitMQ？
2. 如何保证消息不丢失？
3. 如何保证消息顺序性？

**期望回答**:

| 特性 | Kafka 实现 |
|------|-----------|
| 高吞吐 | 顺序写磁盘 + Page Cache + Zero Copy |
| 消息不丢失 | Producer acks=all + Replication + ISR |
| 顺序性 | 同一 Partition 内有序（key 哈希路由） |
| 消费回溯 | 消息保留策略（log.retention.hours） |

```java
// Kafka Producer 配置
Properties props = new Properties();
props.put("bootstrap.servers", "kafka:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");

// 可靠性配置
props.put("acks", "all");  // 所有副本都写入才确认
props.put("retries", Integer.MAX_VALUE);
props.put("batch.size", 16384);
props.put("linger.ms", 10);

KafkaProducer<String, String> producer = new KafkaProducer<>(props);

// 保证顺序：同一广告主的消息发送到同一 Partition
producer.send(new ProducerRecord<>("ad-exposure", 
    String.valueOf(advertiserId),  // key 保证顺序
    JSON.toJSONString(exposureEvent)));
```

**追问**:
- "Kafka 如何保证消息不重复消费？" → 幂等性设计（业务层去重）
- "消费 lag 怎么处理？" → 扩容 Consumer Group

---

### Q3: 搜索引擎选型（5min）

**场景**: 广告平台需要支持：
- 亿级素材库检索
- 模糊搜索（素材标题、标签）
- 多维度筛选（行业、地域、预算）
- 实时索引更新

**问题**:
1. 选择 Elasticsearch 还是 MySQL 全文检索？为什么？
2. 如何设计 Mapping 以支持高性能检索？
3. 如何处理实时性要求？

**期望回答**:

| 方案 | 适用场景 | 原因 |
|------|---------|------|
| Elasticsearch | 亿级数据、复杂查询、模糊搜索 | 倒排索引、分布式、接近实时 |
| MySQL 全文索引 | 万级数据、简单查询 | 简单、ACID 强一致 |

**ES 设计要点**:
- **Mapping**: 合理设置 field type（text vs keyword）
- **分片策略**: 数据量/分片大小（建议 30-50GB/分片）
- **刷新间隔**: `refresh_interval=30s` 平衡实时性与性能
- **Near Realtime**: 默认 1s refresh

```json
{
  "mappings": {
    "properties": {
      "ad_id": { "type": "keyword" },
      "title": { "type": "text", "analyzer": "ik_smart" },
      "tags": { "type": "keyword", "multi_field": { "text": { "type": "text" } } },
      "budget": { "type": "long" },
      "create_time": { "type": "date" }
    }
  },
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  }
}
```

---

### Q4: 消息队列选型对比（5min）

**问题**: 请对比 RabbitMQ、Kafka、RocketMQ 的适用场景

| 特性 | RabbitMQ | Kafka | RocketMQ |
|------|----------|-------|----------|
| **吞吐量** | 万级 | 百万级 | 十万级 |
| **延迟** | 微秒级 | 毫秒级 | 毫秒级 |
| **可靠性** | 高 | 高 | 极高 |
| **消息顺序** | Partition 内有序 | Partition 内有序 | Topic 内有序 |
| **消息堆积** | 不擅长 | 擅长 | 擅长 |
| **适用场景** | 复杂路由、小消息量 | 日志采集、流处理 | 交易订单、金融场景 |

**选型建议**:
- **广告曝光日志**: Kafka（高吞吐、大数据处理）
- **订单状态流转**: RocketMQ（事务消息、高可靠）
- **即时通知**: RabbitMQ（低延迟、复杂路由）

---

## 🔧 第二部分：系统设计（15min）

### 题目 1: 设计一个广告竞价系统（10min）

**需求**:
- 实时竞价（RTB），延迟 < 100ms
- 支持多种出价策略（oCPM、oCPC、CPC）
- 防作弊（同一用户多次曝光去重）
- 预算控制（日预算、总预算）

**问题**:
1. 画出系统架构图
2. 关键组件如何设计？
3. 如何应对突发流量？

**期望架构**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   广告请求   │────▶│  预处理层    │────▶│  竞价引擎    │
│  (SDK/WebView)│     │ (限流/鉴权)  │     │ (Bidding)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
              ┌─────▼─────┐              ┌─────▼─────┐              ┌─────▼─────┐
              │  用户画像  │              │  广告库存  │              │  出价策略  │
              │  (Redis)  │              │  (Redis)  │              │  (本地)   │
              └───────────┘              └───────────┘              └───────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
              ┌─────▼─────┐              ┌─────▼─────┐              ┌─────▼─────┐
              │  预算服务  │              │  实时计费  │              │  日志服务  │
              │  (Redis)  │              │  (Kafka)  │              │  (Kafka)  │
              └───────────┘              └───────────┘              └───────────┘
```

**关键设计**:
1. **预加载**: 用户画像、广告库存预热到 Redis
2. **分片**: 按 advertiser_id 分片，并行竞价
3. **降级**: 超时直接返回默认广告
4. **异步**: 计费、日志异步写入

---

### 题目 2: 设计一个分布式 ID 生成服务（5min）

**需求**:
- 全局唯一
- 趋势递增
- 高可用、高性能
- 支持分库分表

**问题**: 你会选择 Snowflake 还是其他方案？如何优化？

**期望回答**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Snowflake** | 高性能、无需中心化 | 时钟回拨问题、依赖时间服务 |
| **UUID** | 简单、全局唯一 | 无序、索引性能差 |
| **DB 自增** | 简单 | 性能瓶颈、单点 |
| **Leaf** | 美团开源、双号段 | 相对复杂 |

**Snowflake 优化**:
```java
public class SnowflakeIdGenerator {
    private long workerId;
    private long datacenterId;
    private long sequence = 0L;
    private long lastTimestamp = -1L;
    
    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();
        
        // 时钟回拨处理
        if (timestamp < lastTimestamp) {
            throw new RuntimeException("时钟回拨");
        }
        
        // 同一毫秒内序列号递增
        if (timestamp == lastTimestamp) {
            sequence = (sequence + 1) & 4095;
            if (sequence == 0) {
                timestamp = waitNextMillis(lastTimestamp);
            }
        } else {
            sequence = new Random().nextLong() & 4095;
        }
        
        lastTimestamp = timestamp;
        
        // 生成 ID: 时间戳(41) + 机器ID(10) + 数据中心(5) + 序列号(12)
        return ((timestamp - START_TIMESTAMP) << 22) | 
               (workerId << 17) | 
               (datacenterId << 12) | 
               sequence;
    }
}
```

**加分项**:
- 提到 Twitter Snowflake 原理
- 提到时钟回拨解决方案（等待、抛异常、预留机器位）
- 提到 Leaf（美团开源的分布式 ID 服务）

---

## 💻 第三部分：代码实现（10min）

### 题目 1: 实现一个简单限流器（5min）

**场景**: 广告接口需要限流，防止恶意刷量

**要求**: 实现滑动窗口限流器

```java
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class SlidingWindowRateLimiter {
    private final int maxRequests;
    private final long windowSizeMs;
    private final ConcurrentHashMap<String, LongAdder> counters;
    
    public SlidingWindowRateLimiter(int maxRequests, long windowSizeMs) {
        this.maxRequests = maxRequests;
        this.windowSizeMs = windowSizeMs;
        this.counters = new ConcurrentHashMap<>();
    }
    
    public boolean tryAcquire(String key) {
        long now = System.currentTimeMillis();
        long windowStart = now - windowSizeMs;
        
        // 清理过期计数
        counters.entrySet().removeIf(e -> e.getKey().compareTo(windowStart) < 0);
        
        // 获取当前窗口计数
        LongAdder counter = counters.computeIfAbsent(now, k -> new LongAdder());
        
        // 滑动窗口逻辑（简化版，实际应使用多个桶）
        return counter.increment() <= maxRequests;
    }
}
```

**追问**: 
- "滑动窗口和固定窗口有什么区别？" → 滑动窗口避免边界突刺
- "如何实现令牌桶？" → Guava RateLimiter

---

### 题目 2: 实现一个布隆过滤器（5min）

**场景**: 广告曝光去重，快速判断广告是否已曝光

```java
import java.util.BitSet;

public class BloomFilter {
    private BitSet bitSet;
    private int size;
    private int hashCount;
    
    public BloomFilter(int expectedInsertions, double fpp) {
        // 计算位数组大小
        this.size = (int) (-expectedInsertions * Math.log(fpp) / (Math.log(2) * Math.log(2)));
        // 计算哈希函数个数
        this.hashCount = (int) (size * Math.log(2) / expectedInsertions);
        this.bitSet = new BitSet(size);
    }
    
    public void add(String value) {
        for (int i = 0; i < hashCount; i++) {
            int hash = hash(value, i);
            bitSet.set(hash % size, true);
        }
    }
    
    public boolean mightContain(String value) {
        for (int i = 0; i < hashCount; i++) {
            int hash = hash(value, i);
            if (!bitSet.get(hash % size)) {
                return false;
            }
        }
        return true;
    }
    
    private int hash(String value, int seed) {
        int result = seed;
        for (int i = 0; i < value.length(); i++) {
            result = (result * 31 + value.charAt(i)) & 0x7fffffff;
        }
        return Math.abs(result);
    }
}
```

**核心要点**:
- 误判率可控制（通常 0.01%）
- 不能删除元素
- 空间效率极高（1000 万数据仅需 ~10MB）

---

## 💼 第四部分：项目追问（10min）

**引导话术**:
> "请介绍一下你负责的项目，重点讲讲技术选型和遇到的挑战"

**追问方向**:

| 维度 | 问题 |
|------|------|
| **技术选型** | "为什么选这个中间件？有没有对比过其他方案？" |
| **性能优化** | "系统瓶颈在哪里？怎么定位和解决的？" |
| **故障处理** | "遇到过什么线上故障？怎么排查的？" |
| **架构演进** | "系统是如何从 V1 演进到 V2 的？" |
| **Agent 相关** | "ReAct 循环怎么实现的？工具调用如何保证可靠性？" |

---

## 📝 评分表

| 维度 | 权重 | 得分 (1-5) | 备注 |
|------|------|-----------|------|
| 中间件选型 | 25% | | Redis/Kafka/ES 场景理解 |
| 系统设计 | 30% | | 架构设计、权衡分析 |
| 代码能力 | 20% | | 代码规范、边界处理 |
| 项目深度 | 15% | | 技术选型、难点解决 |
| 沟通能力 | 10% | | 表达清晰、逻辑严谨 |

**总分**: ___/25

### 录用建议

| 总分 | 建议 |
|------|------|
| 20-25 | ✅ 强烈推荐二面 |
| 15-19 | ✅ 推荐二面 |
| 10-14 | ⚠️ 谨慎考虑 |
| <10 | ❌ 不推荐 |

---

## 🎯 高频考点速查

### 中间件选型速查表

| 场景 | 推荐中间件 | 关键原因 |
|------|-----------|---------|
| 高频缓存 | Redis | 内存存储、O(1) 复杂度 |
| 分布式锁 | Redis SET NX | 原子操作、高性能 |
| 消息队列（高吞吐） | Kafka | 顺序写、零拷贝 |
| 消息队列（可靠性） | RocketMQ | 事务消息、重试机制 |
| 搜索引擎 | Elasticsearch | 倒排索引、分布式 |
| 会话存储 | Redis | 共享状态、过期机制 |
| 配置中心 | Nacos/Apollo | 热更新、服务发现 |

### 系统设计速查表

| 问题 | 解决方案 |
|------|---------|
| 分布式 ID | Snowflake、Leaf、UUID |
| 限流 | 令牌桶、滑动窗口、漏桶 |
| 缓存一致性 | Cache-Aside、Read-Through、Write-Through |
| 消息去重 | 幂等设计、分布式锁、唯一索引 |
| 服务降级 | 熔断器、超时控制、默认值 |
| 数据一致性 | 最终一致性、TCC、Saga |

---

## 💡 面试官技巧

### 好的提问方式
- ✅ "如果让你设计一个 X 系统，你会怎么做？" → 开放设计
- ✅ "为什么选择 A 而不是 B？" → 考察权衡能力
- ✅ "如果流量翻 10 倍，系统会怎样？" → 考察扩展性思维
- ✅ "如果中间件挂了怎么办？" → 考察容错设计

### 避免的提问
- ❌ "请背诵 Redis 的所有命令" → 可查阅
- ❌ "Kafka 的源码是怎么实现的" → 超出范围
- ❌ 过于细节的配置参数 → 不实用

### 鼓励技巧
- 候选人卡住时："可以从架构角度说说思路"
- 部分正确时："这个方向是对的，继续说说其他方面"
- 完全不会时："这道题有点难，我们聊聊你熟悉的项目"

---

**祝面试顺利！** 🎉
