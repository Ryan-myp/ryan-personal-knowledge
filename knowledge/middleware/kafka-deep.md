# Kafka 核心源码深度 — 分区日志、生产者、消费者、控制器、零拷贝、Raft/KRaft

> 标签: `#Kafka` `#Broker` `#分区日志` `#生产者` `#消费者` `#控制器` `#Raft` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. Broker 架构 — 源码级

### 1.1 核心类层次

```java
// Kafka 源码结构（kafka.server 包）
// 
// KafkaServer → KafkaRaftServer (KRaft 模式)
//
// 关键类:
// 
// KafkaServer (kafka.server.KafkaServer):
//   - 继承自 KafkaBroker
//   - 包含所有 Broker 组件:
//     val logManager = LogManager(...)    // 分区日志管理
//     val controller = Option.empty[Controller]  // 控制器（ZK 模式）
//     val metadataCache = metadataCache      // 元数据缓存
//     val partitionReplicaManager = replicaManager  // 副本管理器
//     val producerStateManager = producerStateManager  // 生产者状态
//     val groupCoordinator = groupCoordinator   // 消费者组协调器
//     val transactionCoordinator = transactionCoordinator  // 事务协调器
//     val api = api          // API 处理
//
// KafkaBroker (kafka.server.KafkaBroker):
//   - 管理 Broker 生命周期:
//     val socketServer = new SocketServer(config)
//     val requestHandlerPool = new KafkaRequestHandlerPool(...)
//     val scheduledExecutor = scheduler
//     val metrics = new Metrics(config.metric...)
//
// 请求处理路径:
// Client → SocketServer (NIO) → RequestChannel → RequestHandlerPool
//   → KafkaApis (处理每个请求) → ReplicationManager → LogManager
//
// 代码路径:
// KafkaRequestHandler.run() {
//   val request = requestChannel.receiveRequest(blockingTimeout)
//   val apis = new KafkaApis(requestChannel, replicaManager, ...)
//   apis.handle(request)
// }
```

### 1.2 分区日志（Log/Segment）

```java
// 分区日志结构（kafka.log 包）:
// 
// Log (kafka.log.Log):
//   - 管理一个分区的所有 Segment
//   - 核心字段:
//     val segments = new ConcurrentSkipListMap[Long, LogSegment]()
//       // 按 baseOffset 排序的 Segment 映射
//     val logStartOffset: Long  // 日志起始偏移量
//     val logEndOffset: Long    // 日志末尾偏移量
//     val activeSegment: LogSegment  // 当前活跃 Segment
//     val producerStateManager: ProducerStateManager  // 生产者状态管理
//
// LogSegment (kafka.log.LogSegment):
//   - 文件: .index, .timeindex, .log, .partition.index
//   - 核心字段:
//     val baseOffset: Long          // 基础偏移量
//     val index: Index              // 偏移量索引
//     val timeIndex: TimeIndex      // 时间戳索引
//     val logFile: File             // 日志文件
//     val maxIndexSize: Int         // 最大索引大小
//     val lazyDelegate: TransactionDelegate  // 事务委托
//     val transactionIndex: TransactionIndex   // 事务索引
//
// 物理存储格式:
// 
// .log 文件（消息日志）:
// ┌──────────────────────────────────────────────────────┐
// │ MessageSet (按 offset 顺序排列)                       │
// │                                                      │
// │ Message 1:                                           │
// │   - size: int32 (4B)                                  │
// │   - attributes: int8 (1B)                            │
// │     - top 3 bits: magic (消息格式版本)                 │
// │     - bit 4: compress (是否压缩)                      │
// │     - bit 5: timestamp (是否有时间戳)                  │
// │   - timestamp: int64 (如果 magic >= 1)                │
// │   - key: bytes (可以为 null)                          │
// │   - value: bytes                                      │
// │   - headers: list of (key, value) pairs               │
// │                                                      │
// │ Message 2:                                           │
// │   - size: int32                                       │
// │   - attributes: int8                                  │
// │   - timestamp: int64                                  │
// │   - key: bytes                                        │
// │   - value: bytes                                      │
// │   - ...                                               │
// │                                                      │
// │ ...                                                   │
// └──────────────────────────────────────────────────────┘
// 
// .index 文件（偏移量索引）:
// ┌──────────────────────────────────────────────────────┐
// │ Index Entry (每个 8 字节):                            │
// │   - relativeOffset: int32 (相对 baseOffset 的偏移)    │
// │   - position: int32 (在 .log 文件中的位置)            │
// │                                                      │
// │ Entry 1: (0, 0)       // 对应 offset = baseOffset     │
// │ Entry 2: (100, 12345) // 对应 offset = baseOffset+100 │
// │ Entry 3: (200, 25678) // 对应 offset = baseOffset+200 │
// │ ...                                                   │
// └──────────────────────────────────────────────────────┘
// 
// .timeindex 文件（时间戳索引）:
// ┌──────────────────────────────────────────────────────┐
// │ TimeIndex Entry (每个 12 字节):                       │
// │   - timestamp: int64                                  │
// │   - relativeOffset: int32                             │
// │                                                      │
// │ Entry 1: (1700000000000, 0)    // 时间戳 ~ offset 0   │
// │ Entry 2: (1700000060000, 100)  // 时间戳 ~ offset 100 │
// │ ...                                                   │
// └──────────────────────────────────────────────────────┘

// 索引查找过程:
// 1. 给定 offset → 在 .index 文件中二分查找
// 2. 得到 relativeOffset → 计算 position = baseOffset + relativeOffset
// 3. 在 .log 文件中 position 位置读取消息
// 4. 如果 .index 文件过期（segment rollover）→ 查找下一个 Segment

// Segment 滚动条件:
// 1. 按大小: max.segment.bytes (默认 1GB)
// 2. 按时间: log.segment.ms (默认 7天)
// 3. 按消息数: 无（Kafka 基于 offset 滚动）
```

### 1.3 页缓存（PageCache）优化

```c
// Kafka 零拷贝实现:
// Kafka 不自己实现缓冲和拷贝，而是依赖操作系统的页缓存（PageCache）
//
// 写路径:
// 1. 生产者发送消息 → Kafka 直接写入 pagecache
// 2. background thread 调用 fsync → 刷到磁盘
// 3. 不需要在 JVM heap 中拷贝数据
//
// 读路径:
// 1. Consumer 发送读取请求 → Kafka 使用 FileChannel.transferTo()
// 2. transferTo 使用 sendfile/system call → 零拷贝
// 3. 数据直接从 pagecache → NIC 网卡，不经过用户态
//
// Java 实现:
// FileChannel.transferTo(long position, long count, WritableByteChannel target)
//   → native 方法调用 sendfile()
//
// 性能优势:
// 1. 减少 CPU 拷贝: 从 4 次拷贝降为 2 次
// 2. 减少上下文切换: 不需要用户态 ↔ 内核态切换
// 3. 利用 DMA: 直接内存到网卡传输
//
// sendfile 调用栈:
// user app (FileChannel.transferTo) → kernel (sendfile) → NIC
//   CPU: 用户态 → 内核态（1次） → NIC DMA
//   传统拷贝: 用户态 → 内核态 → 用户态 → 内核态 → NIC
//             CPU: 用户态 ↔ 内核态（4次）
```

---

## 2. 生产者 — 源码级

### 2.1 Producer 核心架构

```java
// 生产者架构（kafka.producer 包）:
// 
// KafkaProducer:
//   - 核心组件:
//     val accumulator: RecordAccumulator   // 消息累加器（batch 缓存）
//     val sender: Sender                   // 发送线程（后台）
//     val metadata: Metadata               // 元数据管理
//     val interceptors: ProducerInterceptors  // 拦截器链
//     val serializer: Serializer           // 序列化器
//     val partitioner: Partitioner         // 分区器
//
// RecordAccumulator (BoundedDeque):
//   - 核心字段:
//     val batches: ConcurrentMap[TopicPartition, Deque[RecordBatch]]
//       // 每个分区对应一个 Deque
//     val batchMemory: AtomicLong        // 已用内存
//     val batchExpirationMs: Long        // 批超时时间
//     val maxMemory: Long                // 最大内存
//     val lingerMs: Long                 //  linger 时间
//
// RecordBatch:
//   - 核心字段:
//     val baseOffset: Long               // 基础偏移量
//     val producerId: Long               // 生产者 ID
//     val producerEpoch: Short           // 生产者纪元
//     val sequenceNumber: Int            // 序列号
//     val records: MutableRecordBatch    // 消息记录
//     val callbacks: List[Callback]      // 回调函数
//     val isBatchFull: Boolean           // 批是否已满
//     val lock: Object                   // 线程锁
//
// 发送流程:
// producer.send(record, callback) {
//   // 1. 序列化
//   serializedKey = keySerializer.serialize(topic, key)
//   serializedValue = valueSerializer.serialize(topic, value)
//
//   // 2. 选择分区
//   partition = partitioner.partition(topic, key, serializedKey, 
//                                    serializedValue, partitionList)
//
//   // 3. 等待元数据更新
//   metadata.awaitUpdate(producerId, timeoutMs)
//
//   // 4. 创建批
//   batch = accumulator.append(topicPartition, timestamp, 
//                              serializedKey, serializedValue, 
//                              headers, callback, maxTimeMs)
//
//   // 5. 唤醒 Sender 线程
//   accumulator.hasBatchReady() || accumulator.hasNonReady() ? 
//     sender.wakeup() : 
//     noop
// }
//
// Sender 线程运行:
// while (!stopped) {
//   // 1. 从 accumulator 获取准备发送的批
//   List<RecordBatch> batches = accumulator.drain(...)
//
//   // 2. 构建 RequestHeader + ProduceRequest
//   ProduceRequest request = new ProduceRequest(batches, requiredAcks)
//
//   // 3. 发送到对应的 broker
//   ClientResponse response = client.send(broker, request)
//
//   // 4. 处理响应
//   for (RecordBatch batch : batches) {
//     if (response.hasError()) {
//       batch.completeExceptionally(response.error())
//     } else {
//       batch.complete()
//     }
//   }
//
//   // 5. 等待 lingerMs 或 batchFull
//   Thread.sleep(lingerMs)
// }
```

### 2.2 幂等生产者（Idempotent Producer）

```java
// 幂等生产者实现（KIP-98）:
// 
// 原理: 每个生产者分配唯一 PID + Epoch，每条消息有 sequence number
// 
// 初始化:
// 1. 生产者启动时，向 Controller 申请 PID
//    InitProducerIdRequest → InitProducerIdResponse
// 2. 响应: {producerId: 12345, producerEpoch: 0}
// 3. 后续所有消息携带 PID 和 sequence number
//
// 幂等保证:
// 1. Producer 消息格式:
//    magic = 2
//    attributes |= (1 << 5)  // IDENTITY flag
//    headers:
//      - key: "kafka.producer.id"
//      - value: producerId
//      - key: "kafka.producer.epoch"
//      - value: producerEpoch
//      - key: "kafka.producer.sequence"
//      - value: sequenceNumber
//
// 2. Broker 端检查:
//    ProducerStateManager.track(transactionId, producerId, epoch)
//    if (sequenceNumber < lastSeen) {
//      return DuplicateError  // 重复消息，丢弃
//    }
//    if (sequenceNumber > lastSeen + 1) {
//      return InvalidSequenceNumberError  // 跳号，拒绝
//    }
//    lastSeen = sequenceNumber
//
// 3. 故障转移:
//    - 生产者崩溃 → 新生产者使用相同 PID 但 epoch+1
//    - Broker 丢弃旧 epoch 的所有消息
//    - 新 epoch 从 sequenceNumber 0 开始
//
// 事务生产者（KIP-166）:
// 1. beginTransaction()
// 2. send(record) → 标记事务
// 3. commitTransaction()
//    → TransactionCoordinator → 两阶段提交
//
// 事务协议:
// 1. InitProducerId → 获取 PID
// 2. AddPartitionsToTxn → 标记分区参与事务
// 3. AddOffsetsToTxn → 标记消费偏移参与事务
// 4. SendMessages → 发送消息（带事务标记）
// 5. PrepareCommit / PrepareAbort → 准备提交/回滚
// 6. CommitTransaction / AbortTransaction → 提交/回滚
```

### 2.3 分区策略

```java
// 分区策略:
// 
// 1. StickyPartitioner（默认）:
//    - 尽可能将消息发送到同一个分区
//    - 直到 batchFull 或 lingerMs 超时 → 切换到新分区
//    - 减少 partitioner 开销和 broker 负载均衡
//
// 2. RoundRobinPartitioner:
//    - 轮询所有分区
//    - 不考虑 key
//
// 3. CustomPartitioner:
//    class CustomPartitioner implements Partitioner {
//      public int partition(String topic, Object key, 
//                           byte[] keyBytes, Object value, 
//                           byte[] valueBytes, Cluster cluster) {
//        // 自定义逻辑: 按 key 哈希
//        int hash = key.hashCode() & 0x7fffffff
//        return hash % cluster.partitionsForTopic(topic).size()
//      }
//    }
//
// 4. 分区选择流程:
//    a. 如果 key 非空 → 按 key 哈希选择分区
//    b. 如果 key 为空 → 使用 StickyPartitioner
//       - 如果当前批满了 → 切换到随机分区
//       - 否则 → 发送到当前分区
//
// 性能优化:
// 1. StickyPartitioner 减少分区切换次数
// 2. 自定义分区器按业务语义分组（如 user_id → 同一分区）
// 3. 避免使用 round-robin（增加 broker 负载）
```

---

## 3. 消费者 — 源码级

### 3.1 Consumer 核心架构

```java
// 消费者架构（kafka.consumer 包）:
// 
// KafkaConsumer:
//   - 核心组件:
//     val coordinator: ConsumerCoordinator  // 消费者组协调器
//     val fetcher: ConsumerFetcher          // 拉取器
//     val subscriptions: SubscriptionState  // 订阅状态
//     val metrics: Metrics                  // 指标
//     val interceptor: ConsumerInterceptors // 拦截器
//     val deserializer: Deserializer        // 反序列化器
//
// ConsumerCoordinator:
//   - 核心职责:
//     - 注册/注销消费者
//     - 管理成员列表
//     - 触发 rejoin 流程
//     - 协调 offset 提交
//
// SubscriptionState:
//   - 核心字段:
//     val assignments: mutable.Map[TopicPartition, OffsetAndMetadata]
//     val subscribedTopics: Set[String]
//     val groupInstanceId: Option[String]
//     val autoCommit: Boolean
//     val autoCommitInterval: Duration
//
// 拉取流程:
// consumer.poll(timeoutMs) {
//   // 1. 更新元数据
//   metadata.update(cluster, now)
//
//   // 2. 处理协调器请求
//   coordinator.poll(now)
//
//   // 3. 拉取数据
//   List<ConsumerRecord> records = fetcher.fetchedRecords()
//
//   // 4. 反序列化
//   for (Record record : records) {
//     record.key = keyDeserializer.deserialize(topic, record.key)
//     record.value = valueDeserializer.deserialize(topic, record.value)
//   }
//
//   // 5. 拦截
//   for (ConsumerInterceptor interceptor : interceptors) {
//     records = interceptor.onConsume(records)
//   }
//
//   // 6. 返回
//   return records
// }
```

### 3.2 消费者组协议（GroupCoordinator）

```java
// 消费者组协议（KIP-34）:
// 
// 成员管理:
// 1. JoinGroup 协议:
//    - 消费者加入组时，发送 JoinGroupRequest
//    - GroupCoordinator 选择 leader
//    - Leader 发送 SyncGroupRequest 包含分配方案
//    - 所有消费者收到 SyncGroupResponse
//
// 2. 分配策略:
//    - RangeAssignor: 按范围分配
//    - RoundRobinAssignor: 轮询分配
//    - StickyAssignor: 粘性分配（最小化迁移）
//
// 分配算法源码（RangeAssignor）:
// def rangeAssign(topicPartitionList, consumerIds):
//   // 按 topic 分组
//   topicPartitions = groupByTopic(topicPartitionList)
//   assignments = {}
//   for (topic, partitions) in topicPartitions:
//     consumers = sorted(consumerIds.filter(hasTopic))
//     numPartitions = len(partitions)
//     numConsumers = len(consumers)
//     // 计算每个消费者分配多少 partition
//     baseCount = numPartitions // numConsumers
//     remainder = numPartitions % numConsumers
//     for i in range(numConsumers):
//       count = baseCount + (1 if i < remainder else 0)
//       start = i * baseCount + min(i, remainder)
//       assignments[consumers[i]] = partitions[start:start+count]
//   return assignments
//
// StickyAssignor（粘性分配）:
// 核心思想: 最小化 rebalance 时的分区迁移
// 
// 算法:
// 1. 保留上一次分配中与本次可用的消费者重叠的部分
// 2. 将剩余 partition 按 round-robin 分配
// 3. 目标: 最小化 |迁移的 partition 数|
//
// 优势:
// - 减少 partition 迁移次数
// - 降低 rebalance 时的抖动
// - 特别适合 large groups（> 50 consumers）
//
// Rebalance 触发条件:
// 1. 消费者加入/退出
// 2. Topic 增加/减少 partition
// 3. Consumer 心跳超时（session.timeout.ms）
// 4. Coordinator 故障转移
//
// Rebalance 流程:
// 1. Consumer 发送 LeaveGroupRequest
// 2. GroupCoordinator 移除该消费者
// 3. 触发重新分配
// 4. 所有 consumer 发送 JoinGroupRequest
// 5. GroupCoordinator 选择新 leader
// 6. Leader 计算新分配方案
// 7. SyncGroup 广播分配方案
// 8. 所有 consumer 重新分配 partition
```

### 3.3 Offset 管理

```java
// Offset 提交:
// 1. 自动提交:
//    enable.auto.commit = true
//    auto.commit.interval.ms = 5000
//    → 每 5 秒自动提交所有 partition 的 offset
//    → 代码: CoordinatorClient.maybeAutoCommitOffsetsAsync()
//
// 2. 手动提交:
//    consumer.commitSync()  // 同步提交
//    consumer.commitAsync(callback)  // 异步提交
//    → 精确控制提交时机（处理完成后提交）
//
// Offset 存储位置:
// 1. __consumer_offsets topic（Kafka 0.10+）:
//    - Topic: __consumer_offsets
//    - Partitions: 50（默认）
//    - Key: ConsumerGroup:Topic:Partition
//    - Value: OffsetAndMetadata(offset, metadata, timestamp)
//    - 格式: compacted（只保留最新 offset）
//
// 2. ZooKeeper（Kafka 0.8-0.9）:
//    - 路径: /consumers/{groupId}/offsets/{topic}/{partition}
//    - 已废弃
//
// Offset 管理源码:
// ConsumerCoordinator.commitSync() {
//   // 1. 获取需要提交的 offsets
//   List<TopicPartition> partitions = subscriptions.assignedPartitions()
//   Map<TopicPartition, OffsetAndMetadata> offsets = new HashMap<>()
//   for (TopicPartition partition : partitions) {
//     OffsetAndMetadata offsetAndMetadata = subscriptions
//       .committableOffset(partition)
//     if (offsetAndMetadata != null) {
//       offsets.put(partition, offsetAndMetadata)
//     }
//   }
//
//   // 2. 发送 OffsetCommitRequest
//   OffsetCommitRequest request = new OffsetCommitRequest(
//     groupId, offsets, "manual", null)
//   OffsetCommitResponse response = client.send(groupId, request)
//
//   // 3. 处理响应
//   for (Map.Entry<TopicPartition, OffsetAndMetadata> entry : response.data().asMap().entrySet()) {
//     if (entry.getValue().isError()) {
//       // 处理错误
//     } else {
//       // 提交成功
//     }
//   }
// }
```

---

## 4. 控制器与副本管理

### 4.1 控制器选举（KRaft 模式）

```java
// KRaft 模式（KIP-500）:
// 移除 ZooKeeper，使用内置 Raft 实现
// 
// Controller 角色:
// - 管理元数据变更
// - 管理副本分配
// - 处理故障转移
// 
// Raft 协议实现:
// 1. Leader: 处理所有写入请求
// 2. Follower: 复制 Leader 日志
// 3. Candidate: 竞选 Leader
//
// 选举流程:
// 1. 节点启动 → 随机选举超时 → 进入 Candidate 状态
// 2. 发送 RequestVote RPC
// 3. Follower 投票给第一个请求的 Candidate
// 4. 获得多数票 → 成为 Leader
// 5. 发送 heartbeat（AppendEntries RPC）维持领导权
//
// KRaft 实现（kafka.controller 包）:
// KRaftController:
//   - 核心字段:
//     val controllerNode = new ControllerNode(...)
//     val metadataCache = metadataCache
//     val replicaManager = replicaManager
//     val partitionStateMachine = partitionStateMachine
//     val brokerStateMachine = brokerStateMachine
//
// 选举流程:
// 1. ElectionScheduler.run() {
//    // 等待选举超时
//    while (true) {
//      if (state == UNAVAILABLE) {
//        // 开始选举
//        state = CANDIDATE
//        sendRequestVote()
//        wait(forVotes())
//        
//        if (votes > quorumSize) {
//          state = LEADER
//          startHeartbeat()
//        } else {
//          state = UNAVAILABLE
//        }
//      }
//    }
//  }
//
// 元数据管理:
// 1. MetadataManager 管理集群元数据
// 2. 每个元数据变更生成一个新的 MetadataRecord
// 3. 通过 Raft 协议复制到其他节点
// 4. 所有节点维护相同的 MetadataLog
//
// 故障恢复:
// 1. Controller 故障 → 新的 Controller 选举
// 2. 新 Controller 从 MetadataLog 恢复状态
// 3. 重新注册所有 Broker
// 4. 重新分配所有 partition
```

### 4.2 ISR（In-Sync Replicas）

```java
// ISR 管理:
// ISR = In-Sync Replicas
// 
// 核心逻辑:
// 1. Leader 维护 ISR 列表
// 2. 每个 replica 定期发送 Fetch 请求
// 3. 如果 replica 落后 leader 超过 replica.lag.time.max.ms → 移出 ISR
// 4. 如果 replica 跟上 leader → 重新加入 ISR
//
// ISR 配置:
// min.insync.replicas = 1  // 最小同步副本数
// replica.lag.time.max.ms = 10000  // 副本落后超时时间（10秒）
// replica.fetch.max.bytes = 10485760  // 副本最大拉取字节数（10MB）
//
// ISR 影响:
// 1. acks=all: 需要 ISR 中所有副本确认
// 2. min.insync.replicas > 1: 需要至少 N 个副本确认
// 3. 如果 ISR 为空 →  producer 拒绝写入（acks=all 时）
//
// ISR 状态机:
// 
// 初始状态:
// Leader: Broker-1
// ISR: [Broker-1, Broker-2, Broker-3]
// 
// 场景 1: Broker-2 故障
// ISR: [Broker-1, Broker-3]  // Broker-2 移出 ISR
// 
// 场景 2: Broker-2 恢复
// ISR: [Broker-1, Broker-2, Broker-3]  // Broker-2 重新加入 ISR
// 
// 场景 3: Broker-2 落后太多
// ISR: [Broker-1, Broker-3]  // Broker-2 被踢出
// 
// 不可用场景:
// 如果 acks=all 且 min.insync.replicas=2
// ISR 大小为 1 → 写入失败
```

---

## 5. 性能调优

### 5.1 生产者调优

```properties
# 生产者配置:
# 1. 批量处理:
#    batch.size=16384          # 批大小（16KB，默认）
#    linger.ms=5               # 等待时间（毫秒）
#    buffer.memory=33554432    # 缓冲内存（32MB）
#
# 2. 压缩:
#    compression.type=lz4      # lz4/snappy/zstd/gzip
#    推荐: lz4（平衡压缩率/速度）
#
# 3. 可靠性:
#    acks=all                  # 等待所有 ISR 确认
#    retries=2147483647        # 最大重试次数
#    max.in.flight.requests.per.connection=5  # 允许的最大请求数
#
# 4. 幂等:
#    enable.idempotence=true   # 启用幂等生产者
#    自动设置 acks=all + retries=MAX + max.in.flight.requests=5
#
# 性能优化:
# - 增加 batch.size 到 64KB-128KB（减少网络请求）
# - 设置 linger.ms=10-50ms（增加批大小）
# - 使用 lz4 压缩（减少网络传输）
# - 增加 buffer.memory（减少阻塞）
```

### 5.2 消费者调优

```properties
# 消费者配置:
# 1. 拉取:
#    max.poll.records=500      # 每次拉取最大记录数
#    fetch.min.bytes=1048576   # 最小拉取字节数（1MB）
#    fetch.max.wait.ms=500     # 最大等待时间（毫秒）
#
# 2. 会话:
#    session.timeout.ms=10000  # 会话超时（10秒）
#    heartbeat.interval.ms=3000 # 心跳间隔（3秒）
#
# 3. 提交:
#    enable.auto.commit=false  # 关闭自动提交
#    auto.commit.interval.ms=5000
#
# 性能优化:
# - 增加 max.poll.records（批量处理）
# - 增加 fetch.min.bytes（减少请求次数）
# - 手动提交 offset（处理完成后提交）
# - 增加 session.timeout.ms（避免不必要的 rebalance）
```

---

## 6. 与竞品对比

```
┌──────────┬────────────────┬────────────────┬────────────────┐
│          │   Apache Kafka │   Apache Pulsar│    NATS JetStream│
├──────────┼────────────────┼────────────────┼────────────────┤
│ 存储     │ PageCache      │ Apache BookKeeper│ 文件存储       │
│          │ (OS Level)     │ (独立存储层)    │ (NATS 内部)    │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 架构     │ Broker 直接存  │ Broker 无状态  │ Broker 无状态  │
│          │ 数据           │ 数据在 BookKeeper│ 数据在 JetStream│
├──────────┼────────────────┼────────────────┼────────────────┤
│ 扩展性   │ Broker 存储    │ 存储计算分离    │ Broker 存储    │
│          │ 和计算一体     │ 可扩展性好      │ 和计算一体      │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 消息语义 │ At-Least-Once  │ At-Least-Once  │ At-Least-Once  │
│          │ + 幂等         │ + 幂等         │ + 幂等         │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 延迟     │ 微秒级         │ 毫秒级         │ 微秒级         │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 吞吐     │ 百万+ msg/s    │ 百万+ msg/s    │ 十万+ msg/s    │
├──────────┼────────────────┼────────────────┼────────────────┤
│ 适用场景 │ 大数据/日志    │ 消息队列+流处理  │ 微服务/实时    │
└──────────┴────────────────┴────────────────┴────────────────┘

选择建议:
1. 大数据/日志: Kafka
   - 高吞吐、高可靠、生态完善
   - 适合广告平台日志、点击流

2. 消息队列+流处理: Pulsar
   - 存储计算分离，弹性伸缩
   - 适合混合负载

3. 微服务/实时: NATS JetStream
   - 低延迟，简单部署
   - 适合服务间通信
```

---

*本文档基于 Kafka 3.x 源码整理，覆盖 Broker/分区日志/生产者/消费者/控制器/零拷贝*
