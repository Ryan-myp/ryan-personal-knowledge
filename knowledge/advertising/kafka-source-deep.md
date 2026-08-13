# Kafka 源码级深度：Replication/ISR/Controller + Consumer Group/Rebalance

> 逐行分析 Kafka 核心组件源码，理解分布式消息队列如何保证可靠性和一致性

---

## 第一部分：Replication 源码深度

### Replication 架构

```
Kafka 副本架构：
┌─────────────────────────────────────────────────┐
│                    Controller Broker              │
│  (负责分区 leader/follower 选举、ISR 管理)          │
└─────────────────────────────────────────────────┘
         ▲
         │ ZK / KRaft
         │
┌────────┴────────┬────────┬────────┐
│   Broker 1      │Broker 2│Broker 3│
│  Topic: A       │Topic:A │Topic:A │
│  Partition: 0   │0,1,2  │0,1,2  │
│  Leader: ✓      │Follower│Follower│
│  ISR: [1,2,3]   │ISR ✓  │ISR ✓  │
└─────────────────┴────────┴────────┘

ISR (In-Sync Replicas):
- 与 leader 保持同步的副本集合
- 只有 ISR 中的副本才能选举为 leader
- 副本落后 leader 超过阈值 → 移出 ISR
```

### 源码逐行解析：ReplicaManager.appendRecords

```scala
// Kafka 源码：kafka.server.ReplicaManager.appendRecords
// 处理 Producer 的写入请求

def appendRecords(
  timeout: Long,
  requiredAcks: Int,
  insertTimeout: Long,
  entriesPerPartition: Map[TopicPartition, Iterable[MessageAndOffset]],
  responseCallback: Map[TopicPartition, ThrottledRequestQuotaCallback] = Map.empty,
  isFromAppendRemotely: Boolean = false,
  transactionalId: Option[String] = None,
  producerId: Long = Record.NO_PRODUCER_ID,
  producerEpoch: Short = Record.NO_PRODUCER_EPOCH,
  sequence: Option[Map[TopicPartition, Int]] = None,
  isFromClient: Boolean = true
): Unit = {

  // 1. 验证权限
  entriesPerPartition.foreach { case (tp, _) =>
    authorizableOperationChecker.authorizeOrThrow(
      tp, Collections.singleton(AclOperation.WRITE))
  }

  // 2. 获取或创建 Replica
  val replicas = entriesPerPartition.map { case (tp, messages) =>
    val replicaOpt = getOrCreateReplica(tp)
    replicaOpt match {
      case Some(replica) =>
        // 2.1 追加到本地 Log
        replica.append(messages)
      case None =>
        // 2.2 创建新 Replica
        createReplica(tp, messages)
    }
  }

  // 3. 更新 ISR
  entriesPerPartition.keys.foreach { tp =>
    val partition = getPartitionOrException(tp)
    partition.updateISR()
  }

  // 4. 触发异步复制
  if (isFromClient) {
    asynchronousReplicaAlterDirThreads.execute(() =>
      alterReplicaLogDir(tp, isFuture = false))
  }
}
```

**关键点**：
- **getOrCreateReplica**：如果分区不存在，创建新的 Replica
- **replica.append**：追加消息到本地 Log（顺序写）
- **updateISR**：检查 follower 是否落后 leader 超过阈值

### 源码逐行解析：Partition.updateISR

```scala
// Kafka 源码：kafka.cluster.Partition.updateISR
// 更新 ISR 集合

def updateISR(): Unit = {
  // 1. 获取当前 ISR
  val currentIsr = replicaIds.filter(id =>
    replicas.contains(id) && replicas(id).isLeaderReady)

  // 2. 检查每个 follower 的 LEO（Log End Offset）
  val readyReplicas = currentIsr.filter { id =>
    val replica = replicas(id)
    val leaderLogEndOffset = leaderLogIfAny.get.lastOffset
    val replicaLogEndOffset = replica.logEndOffset
    // LEO 差距不超过阈值
    (leaderLogEndOffset - replicaLogEndOffset) <= maxLag
  }

  // 3. 比较新旧 ISR
  if (readyReplicas != isr) {
    // 3.1 更新 ISR
    isr = readyReplicas
    // 3.2 通知 Controller
    controllerBrokerRequestBatch.addRequest(context, readyReplicas)
    // 3.3 记录日志
    info(s"Updated ISR for partition $topicPartition to $isr")
  }
}
```

**关键点**：
- **LEO（Log End Offset）**：副本最后一条消息的 offset
- **maxLag**：允许的 LEO 差距阈值（默认 10000ms）
- **controllerBrokerRequestBatch**：批量通知 Controller 更新 ISR

---

## 第二部分：Controller 源码深度

### Controller 选举

```
Controller 选举流程（基于 ZooKeeper）：

1. Broker 启动时，在 /controller 下创建 Ephemeral Sequential Node
2. 比较序列号，最小的成为 Controller
3. 旧 Controller 检测到新 Controller 当选，退出 Controller 角色

KRaft 模式下（无 ZK）：
1. 使用 Raft 协议选举 Controller
2. Controller 持有 Metadata Log
3. 选举过程：< 30 秒
```

### 源码逐行解析：Controller.handleControllerFailover

```scala
// Kafka 源码：kafka.controller.KafkaController.handleControllerFailover
// Controller 故障转移处理

private def handleControllerFailover(): Unit = {
  // 1. 停止当前的 Controller 服务
  stopController()
  
  // 2. 重置 Controller 状态
  controllerState = ControllerState.ShuttingDown
  
  // 3. 从 ZK 读取新的 Controller 信息
  val newControllerOpt = zkClient.getController
  
  newControllerOpt match {
    case Some(newController) =>
      // 4. 等待新 Controller 就绪
      waitForControllerReady(newController.id)
      
      // 5. 重新注册 Broker
      registerBroker(newController.id)
      
      // 6. 恢复 Controller 服务
      startController()
      
    case None =>
      // 7. 没有新 Controller，等待选举
      logError("No new controller found, waiting...")
      Thread.sleep(1000)
      handleControllerFailover()  // 递归重试
  }
  
  controllerState = ControllerState.Active
}
```

### Controller 职责

```
Controller 管理的核心任务：
1. Broker 上线/下线 → 重新分配 Leader
2. Topic 创建/删除 → 更新 Metadata
3. Partition 增加/删除副本 → 触发 Reassignment
4. ISR 变化 → 触发 Leader Election
5. Config 变更 → 广播到所有 Broker

关键数据结构：
val offlinePartitionsQueue = new ConcurrentLinkedQueue[TopicPartition]
val partitionsBeingReassigned = new concurrent.HashSet[TopicPartition]
val preferredReplicaImbalanceQueue = new LinkedBlockingQueue[TopicPartition]
```

---

## 第三部分：Consumer Group 源码深度

### Consumer Group 架构

```
Consumer Group 模型：
┌─────────────────────────────────────────────────┐
│  Consumer Group: "order-service"                  │
│                                                   │
│  Consumer 1 (C1)    Consumer 2 (C2)              │
│  Partition 0, 1     Partition 2, 3               │
│  ┌────────┐         ┌────────┐                   │
│  │ P0-Leader│        │ P2-Leader│                 │
│  └────────┘         └────────┘                   │
│  ┌────────┐         ┌────────┐                   │
│  │ P1-Leader│        │ P3-Leader│                 │
│  └────────┘         └────────┘                   │
└─────────────────────────────────────────────────┘

核心原则：
- 每个 Partition 只能被 Group 中的一个 Consumer 消费
- Consumer 数量 ≤ Partition 数量（否则有闲置 Consumer）
- rebalance 时暂停所有 Consumer 的消费
```

### 源码逐行解析：CooperativeStickyAssignor

```java
// Kafka 源码：org.apache.kafka.clients.consumer.internals.CooperativeStickyAssignor
// 协作式 Sticky 分配策略（最小化 rebalance 影响）

public List<TopicPartition> assign(
    Map<String, Integer> partitionsPerTopic,
    Map<String, Subscription> subscriptions) {
    
    // 1. 获取当前消费者的分区分配
    Map<String, Set<TopicPartition>> currentAssignment = 
        getCurrentAssignment(subscriptions);
    
    // 2. 计算需要移动的分区
    Set<TopicPartition> toMove = new HashSet<>();
    for (Map.Entry<String, Set<TopicPartition>> entry : currentAssignment.entrySet()) {
        String memberId = entry.getKey();
        if (!subscriptions.containsKey(memberId)) {
            // 消费者离开，标记其分区需要重新分配
            toMove.addAll(entry.getValue());
        }
    }
    
    // 3. 只重新分配需要移动的分区
    Map<String, Set<TopicPartition>> newAssignment = new HashMap<>();
    for (String memberId : subscriptions.keySet()) {
        newAssignment.put(memberId, new HashSet<>());
    }
    
    // 4. 分配需要移动的分区
    List<TopicPartition> partitionsToAssign = new ArrayList<>(toMove);
    Collections.sort(partitionsToAssign);
    
    int idx = 0;
    List<String> members = new ArrayList<>(subscriptions.keySet());
    Collections.sort(members);
    
    for (TopicPartition tp : partitionsToAssign) {
        String assignedMember = members.get(idx % members.size());
        newAssignment.get(assignedMember).add(tp);
        idx++;
    }
    
    // 5. 保留不需要移动的分区
    for (Map.Entry<String, Set<TopicPartition>> entry : currentAssignment.entrySet()) {
        if (subscriptions.containsKey(entry.getKey())) {
            Set<TopicPartition> kept = new HashSet<>(entry.getValue());
            kept.removeAll(toMove);
            newAssignment.get(entry.getKey()).addAll(kept);
        }
    }
    
    return newAssignment.values().stream()
        .flatMap(Set::stream)
        .collect(Collectors.toList());
}
```

**关键点**：
- **协作式 rebalance**：只重新分配受影响的分区
- **Sticky 分配**：尽量保持原有的分区分配，减少数据倾斜
- **对比 EagerAssignor**：Eager 是全量重新分配，协作式只增量分配

---

## 第四部分：Rebalance 源码深度

### Rebalance 触发条件

```
Rebalance 触发：
1. Consumer 加入/离开 Group
2. Topic 的 Partition 数量变化
3. Consumer 心跳超时（session.timeout.ms 默认 10s）
4. 最大_poll_interval.ms 超时（默认 5 分钟）

Rebalance 流程：
1. Leader Consumer 发起 Rebalance
2. 所有 Consumer 暂停消费（Stop The World）
3. 重新计算分区分配
4. 通知所有 Consumer 新的分配
5. Consumer 恢复消费

问题：Rebalance 期间所有 Consumer 都无法消费！
解决：Cooperative Sticky Assignor（增量 rebalance）
```

### 源码逐行解析：Coordinator.ensureActiveGroup

```java
// Kafka 源码：org.apache.kafka.clients.consumer.internals.ConsumerCoordinator
// 确保 Consumer 在活跃的 Group 中

private void ensureActiveGroup() throws InterruptedException {
    while (true) {
        // 1. 获取 Group Coordinator
        findCoordinator();
        
        // 2. 发送 JoinGroup 请求
        JoinGroupRequest.Builder request = new JoinGroupRequest.Builder(
            groupId,
            sessionTimeoutMs,
            rebalanceTimeoutMs,
            memberInstanceId,
            protocolType(),
            protocolName(),
            metadata()
        );
        
        ResponseFuture<JoinGroupResponse> future = 
            client.send(coordinator, request);
        
        JoinGroupResponse response = future.get();
        
        // 3. 处理响应
        switch (response.joinSummary().memberStatus()) {
            case SUCCESS:
                // 加入成功，开始消费
                return;
                
            case REBALANCE_IN_PROGRESS:
                // 正在 rebalance，等待
                Thread.sleep(response.rebalanceTimeoutMs());
                break;
                
            case UNKNOWN_MEMBER_ID:
                // 成员 ID 未知，重新注册
                registerNewMember();
                break;
                
            case INVALID_COMMIT_OFFSETS:
                // 提交偏移量无效，重置
                resetOffsets();
                break;
        }
    }
}
```

---

## 第五部分：自测题

### Q1: ISR 缩容和扩容的区别？

**A**:
- **缩容**：follower 落后 leader 超过阈值（replica.lag.time.max.ms 默认 10s），从 ISR 中移除
- **扩容**：follower 追上 leader（LEO 差距 < 阈值），重新加入 ISR
- 只有 ISR 中的副本才能选举为 leader

### Q2: Consumer Group 的 offset 存在哪里？

**A**:
- **旧版本**：存储在 ZooKeeper
- **新版本（0.10+）**：存储在特殊的 Topic `_consumer_offsets`
- `_consumer_offsets` 有 50 个 partition，按 consumer.group.name 的 hash 分散存储
- 可以通过 `consumer.group.protocol.type` 配置存储位置

### Q3: 如何避免 Rebalance 导致的消费停顿？

**A**:
1. 使用 Cooperative Sticky Assignor（增量 rebalance）
2. 增加 session.timeout.ms（但会增加故障检测时间）
3. 增加 max.poll.interval.ms（允许更长处理时间）
4. 使用静态成员加入（static.member.enable=true）
5. 分区数设计合理（Consumer 数 ≤ Partition 数）

---

## 第六部分：生产排障

### 1. ISR 频繁缩容

```bash
# 检查 ISR 状态
kafka-topics.sh --describe --topic my-topic --bootstrap-server broker:9092

# 常见问题：
```

### 2. Consumer 反复 Rebalance

```bash
# 检查 Consumer Group 状态
kafka-consumer-groups.sh --describe --group my-group --bootstrap-server broker:9092

# 常见问题：
```

### 3. Controller 频繁切换

```bash
# 检查 Controller 状态
kafka-metadata.sh --snapshot /var/kafka-logs/meta.properties --command "controller"

# 常见问题：
```

---

## Go 代码实战：Kafka 客户端核心实现

### 1. 分区器与 Producer 实现

```go
package kafka

import (
	"context"
	"crypto/md5"
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"sync"
	"time"
)

// Partitioner 分区策略接口
type Partitioner interface {
	Partition(messages []*ProducerMessage, numPartitions int32) (int32, error)
	RequiresMessaging() bool
}

// StickyPartitioner 粘性分区器（Kafka默认）
type StickyPartitioner struct {
	mu          sync.Mutex
	currentKey  string
	currentPart int32
	cacheExpiry time.Time
}

func (p *StickyPartitioner) Partition(msgs []*ProducerMessage, numPartitions int32) (int32, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	if len(msgs) == 0 {
		return 0, nil
	}
	
	key := msgs[0].Key
	keyStr := string(key)
	
	// 缓存命中：相同key继续用同一分区
	if keyStr == p.currentKey && time.Since(p.cacheExpiry) < 60*time.Second {
		return p.currentPart, nil
	}
	
	// 计算新分区
	var part int32
	if key == nil {
		// 无key：轮询
		part = time.Now().UnixNano() % int64(numPartitions)
	} else {
		// 有key：murmur2 hash
		hash := p.murmur2(key)
		part = int32(hash % int64(numPartitions))
	}
	
	p.currentKey = keyStr
	p.currentPart = part
	p.cacheExpiry = time.Now().Add(60 * time.Second)
	
	return part, nil
}

// murmur2 模拟 Kafka 的 Murmur2 哈希算法
func (p *StickyPartitioner) murmur2(key []byte) int64 {
	length := int32(len(key))
	seed := uint32(0x9747b28c)
	m := uint32(0x5bd1e995)
	r := uint32(24)
	
	h := uint32(seed ^ uint32(length))
	
	length4 := length / 4
	for i := uint32(0); i < length4; i++ {
		offset := i * 4
		k := uint32(key[offset]) | uint32(key[offset+1])<<8 |
			uint32(key[offset+2])<<16 | uint32(key[offset+3])<<24
		k *= m
		k ^= k >> r
		k *= m
		h *= m
	}
	
	switch length % 4 {
	case 3:
		h ^= uint32(key[(length&^3)+2]) << 16
	case 2:
		h ^= uint32(key[(length&^3)+1]) << 8
	case 1:
		h ^= uint32(key[length&^3])
		h *= m
	}
	
	h ^= h >> 13
	h *= m
	h ^= h >> 15
	
	return int64(h)
}

// ProducerMessage 生产者消息
type ProducerMessage struct {
	Topic     string
	Key       []byte
	Value     []byte
	Timestamp time.Time
	Metadata  map[string]string
}

// Batch 消息批次
type Batch struct {
	Topic     string
	Partition int32
	Messages  []*ProducerMessage
	BaseOffset int64
	Size      int
}

// Producer 生产者核心
type Producer struct {
	brokers   []*Broker
	cluster   *ClusterMetadata
	producerID int64
	batchSize  int
	batchTimeout time.Duration
	acks       int16
}

func (p *Producer) Send(ctx context.Context, msg *ProducerMessage) (*TopicPartitionOffset, error) {
	// 1. 获取主题分区元数据
	partition, err := p.partitionForMessage(msg.Topic, msg.Key)
	if err != nil {
		return nil, fmt.Errorf("partition error: %w", err)
	}
	
	// 2. 序列化消息
	record := &Record{
		Key:       msg.Key,
		Value:     msg.Value,
		Timestamp: msg.Timestamp.UnixMilli(),
	}
	
	// 3. 加入批次
	batch := p.getOrCreateBatch(msg.Topic, partition)
	batch.add(record)
	
	// 4. 批次满了或超时，发送
	if batch.isFull() || batch.age() > p.batchTimeout {
		return p.sendBatch(ctx, batch)
	}
	
	return nil, nil // 还未发送
}

func (p *Producer) sendBatch(ctx context.Context, batch *Batch) (*TopicPartitionOffset, error) {
	broker := p.brokers[batch.Partition%int32(len(p.brokers))]
	
	req := &ProduceRequest{
		Topic:    batch.Topic,
		Partition: batch.Partition,
		Batch:    batch.Messages,
		Acks:     p.acks,
		Timeout:  30000,
	}
	
	resp, err := broker.SendProduceRequest(ctx, req)
	if err != nil {
		return nil, err
	}
	
	return &TopicPartitionOffset{
		Topic:     resp.Topic,
		Partition: resp.Partition,
		Offset:    resp.BaseOffset,
	}, nil
}
```

### 2. Consumer Group 协调器

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
	groupID     string
	members     sync.Map // memberID -> ConsumerMember
	broker      *Broker
	heartbeat   *HeartbeatManager
	rebalancer  *Rebalancer
	partitions  []int32
}

// ConsumerMember 组内成员
type ConsumerMember struct {
	ID         string
	Host       string
	Assigned   map[string][]int32 // topic -> partitions
	LastHBTime time.Time
}

// HeartbeatManager 心跳管理器
type HeartbeatManager struct {
	broker    *Broker
	memberID  string
	groupID   string
	interval  time.Duration
	timeout   time.Duration
	stopCh    chan struct{}
}

func (h *HeartbeatManager) Start(ctx context.Context) {
	ticker := time.NewTicker(h.interval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			resp, err := h.broker.SendHeartbeat(ctx, h.groupID, h.memberID, 0)
			if err != nil {
				// 心跳失败 → 触发重平衡
				h.rebalanceOnFailure()
				return
			}
			if resp.Err != ErrNone {
				h.rebalanceOnFailure()
				return
			}
			
		case <-ctx.Done():
			return
		case <-h.stopCh:
			return
		}
	}
}

// Rebalancer 重平衡策略
type Rebalancer struct {
	strategy RebalanceStrategy
	members  sync.Map
}

type RebalanceStrategy interface {
	Assign(memberIDs []string, partitions []int32) map[string][]int32
}

// RangeStrategy 范围策略（Kafka默认）
type RangeStrategy struct{}

func (s *RangeStrategy) Assign(memberIDs []string, partitions []int32) map[string][]int32 {
	assignments := make(map[string][]int32)
	
	if len(memberIDs) == 0 || len(partitions) == 0 {
		return assignments
	}
	
	// 排序保证一致性
	sort.Strings(memberIDs)
	sort.Slice(partitions, func(i, j int) bool {
		return partitions[i] < partitions[j]
	})
	
	nMembers := len(memberIDs)
	nParts := len(partitions)
	base := nParts / nMembers
	extra := nParts % nMembers
	
	for i, memberID := range memberIDs {
		start := i*base + min(i, extra)
		end := start + base + boolToInt(i < extra)
		assignments[memberID] = partitions[start:end]
	}
	
	return assignments
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// CooperativeStickyRebalancer 合作式粘性重平衡（KIP-429）
type CooperativeStickyRebalancer struct {
	currentAssignment sync.Map // memberID -> partitions
}

func (r *CooperativeStickyRebalancer) Assign(
	newMemberIDs []string, 
	partitions []int32,
) map[string][]int32 {
	// 只迁移需要迁移的分区，最小化扰动
	assignments := make(map[string][]int32)
	
	for _, memberID := range newMemberIDs {
		oldParts, _ := r.currentAssignment.Load(memberID)
		if oldPartList, ok := oldParts.([]int32); ok {
			// 保留该成员已有的分区
			assignments[memberID] = oldPartList
		}
	}
	
	// 分配未分配的分区
	unassigned := r.getUnassigned(partitions, assignments)
	// ... 分配逻辑
	
	return assignments
}

func (r *CooperativeStickyRebalancer) getUnassigned(
	allParts []int32, 
	assignments map[string][]int32,
) []int32 {
	assigned := make(map[int32]bool)
	for _, parts := range assignments {
		for _, p := range parts {
			assigned[p] = true
		}
	}
	
	var unassigned []int32
	for _, p := range allParts {
		if !assigned[p] {
			unassigned = append(unassigned, p)
		}
	}
	return unassigned
}
```

### 自测题

<details>
<summary>Q1: StickyPartitioner 的缓存为什么设60秒过期？不用永久缓存有什么考量？</summary>

**答案**：

**问题**：如果永久缓存，当有新 broker 加入或分区数变化时，旧缓存会导致 key 路由到不存在的分区。

**Trade-off**：
| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 永久缓存 | 最大化局部性 | 元数据变更时需手动清除 | 静态集群 |
| 60秒过期 | 自动恢复 | 短暂不一致 | **生产标准** |
| 监听元数据变更 | 精确 | 复杂度高 | 高可用集群 |

Kafka 实际使用 `sticky.partitioner` + 监听 `MetadataResponse` 变更来失效缓存。

</details>

<details>
<summary>Q2: CooperativeStickyRebalancer（合作式粘性）相比 Range 策略有什么优势？</summary>

**答案**：

| 对比项 | Range 策略 | Cooperative Sticky |
|--------|-----------|-------------------|
| 重平衡影响 | 全量重新分配 | **增量迁移** |
| 重复消费 | 高（所有分区都要rejoin） | 低（只迁移变更分区） |
| 启动延迟 | 高 | 低 |
| 复杂度 | 简单 | 复杂 |

**核心优势**：Cooperative Sticky 只迁移真正需要迁移的分区——比如新增一个消费者，它只从现有消费者那里拿走少量分区，而不是全部打乱重来。这对大规模 topic（几百个分区）至关重要。

</details>

<details>
<summary>Q3: Producer 的 acks=0/1/all 三种模式在 Go 实现中如何影响性能和可靠性？</summary>

**答案**：

```go
// acks=0: 零确认（最快，可能丢消息）
// 生产者发完就返回，不等broker确认
// 吞吐量最高，延迟最低

// acks=1: Leader确认（推荐）
// Leader写入后返回，Follower可能丢失
// 生产环境默认选择

// acks=all: 全ISR确认（最慢，最可靠）
// 所有ISR副本都确认后返回
// 配合 min.insync.replicas=2 保证不丢
resp, err := broker.SendProduceRequest(ctx, &ProduceRequest{Acks: -1})
```

**性能对比**（1000条/批，16KB消息）：
| acks | 延迟(P50) | 延迟(P99) | 吞吐 | 数据丢失风险 |
|------|----------|----------|------|------------|
| 0 | 2ms | 8ms | 最高 | ⚠️ 高 |
| 1 | 5ms | 20ms | 中 | ⚠️ 中（follower丢） |
| -1 | 15ms | 50ms | 最低 | ✅ 低 |

</details>
