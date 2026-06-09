# Kafka Rebalance 源码级深度 — ConsumerCoordinator、Rebalance 协议、StickyAssignor

> 标签: `#Kafka` `#消费者组` `#重平衡` `#源码级`
> 创建日期: 2026-06-08
> 作者: Ryan
>
> ---

## 1. 消费者组协调器架构

### 1.1 分布式协调器架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     Kafka Cluster (KRaft / ZK)                   │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │  │ Broker N │        │
│  │          │  │          │  │          │  │          │        │
│  │ GroupCoord│ │ GroupC.  │ │ Grp.C.   │ │          │        │
│  │ Coordinator│ │ oordinator│ │ oator   │ │          │        │
│  │ (for GID=) │ │ (for GID=)│ │ (for GID=)│ │          │        │
│  │ A, C     │ │ B, D     │ │ E, F     │ │ A, C     │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│       ▲              │              │                ▲           │
│       │              │              │                │           │
│       │  _consumer_metadata ─────────────────────    │           │
│       │       topic metadata                     _consumer_offsets │
│       │              │              │                │           │
│       │              │              │                │           │
│  ┌────┴────┐   ┌────┴────┐  ┌─────┴─────┐  ┌──────┴─────┐      │
│  │Consumer1│   │Consumer2│  │Consumer3  │  │Consumer4   │      │
│  │GID=A    │   │GID=B    │  │GID=A      │  │GID=C      │      │
│  └─────────┘   └─────────┘  └───────────┘  └────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

Coordinator 选择规则（ZK 模式）：

```java
// GroupMetadataManager.scala
// Group coordinator 选择：hash(groupId) % numPartitions(_offsetsTopicPartitions)
private def selectCoordinator(groupId: String): Int =
  MathUtils.abs(groupId.hashCode) % _offsetsTopicPartitions

// KRaft 模式（KIP-595）：通过 _metadata 主题中的 Controller 路由
// Coordinator 选举不再依赖 ZK，改为 Raft 日志中的 GroupMetadataManager
```

### 1.2 消费者启动流程源码

```java
// org.apache.kafka.clients.consumer.KafkaConsumer 构造流程
public KafkaConsumer(Map<String, Object> configs) {
    // 1. 序列化器配置
    this.serializer = config.serializer;
    this.deserializer = config.deserializer;
    
    // 2. 初始化网络层
    this.consumerClient = new ConsumerNetworkClient(
        metadata,          // 集群元数据缓存
        selector,          // KafkaClient (NIO Selector)
        coordinator,       // ConsumerCoordinator
        logContext,
        maxPollIntervalMs, // 300000ms
        sessionTimeoutMs,  // 10000ms
        heartbeatIntervalMs, // 3000ms
        requestTimeoutMs,
        retryBackoffMs,
        deliveryTimeoutMs,
        metrics,
        time
    );
    
    // 3. 协调器初始化（延迟初始化）
    coordinator = new ConsumerCoordinator<>(
        apiVersions,
        clientId,
        sessionTimeoutMs,
        rebalanceTimeoutMs,
        maxPollIntervalMs,
        autoCommitEnabled,
        new OffsetCommitCallback() {},
        consumerClient,
        metadata,
        subscriber,    // SubscriptionState
        receiver,      // NetworkThread
        sender,        // Sender 线程
        metrics,
        this,
        groupInstanceId,  // 固定 consumer.id (幂等 rejoin)
        partitionAssignors, // [StickyAssignor]
        logContext
    );
}

// KafkaConsumer#poll() 中的协调器交互循环
public ConsumerRecords<K, V> poll(Duration timeout) {
    // 确保订阅已设置
    ensureSubscription();
    
    // 协调器子轮询循环（处理 coordinator 相关请求）
    ConsumerCoordinator.GroupCoordinatorResponseMetadata coordinatorMetadata =
        coordinator.poll(time, timeout);  // 核心：可能触发 JoinGroup/SyncGroup
    
    // 网络层处理：发送 PendingRequest + 接收 Response
    client.poll(metadataTimeout, now, fetcher);
    
    // 拉取消息
    List<ConsumerRecord<K, V>> records = fetcher.fetchedRecords();
    
    return new ConsumerRecords<>(records);
}
```

---

## 2. Rebalance 协议 — 源码级流程

### 2.1 JoinGroup 协议（KIP-345）

```
Consumer A (Member-A)        GroupCoordinator           Consumer B (Member-B)
      │                            │                           │
      │   JoinGroupRequest(v6)     │                           │
      │───>────────────────────────│                           │
      │                            │   Forward to Leader       │
      │                            │◀──────────────────────────│
      │                            │   JoinGroupRequest(v6)    │
      │                            │───>───────────────────────│
      │   (等待其他成员加入)         │                           │
      │                            │                           │
      │     协调器发现自己是 leader │                           │
      │   或 elected leader 是 A   │                           │
      │                            │                           │
      │   JoinGroupResponse        │                           │
      │   (leader=A, protocol=    │                           │
      │    StickyAssignor,        │                           │
      │    member=A)              │                           │
      │<───────────────────────────│                           │
      │                            │                           │
      │                            │   SyncGroupResponse       │
      │                            │   (assignment=topic-p-0:  │
      │                            │    A; topic-p-1: B)      │
      │   SyncGroupResponse        │                           │
      │◀───────────────────────────│                           │
      │                            │                           │
      │  本地更新: assign([p0])    │                           │
      │                            │  本地更新: assign([p1])   │
```

### 2.2 JoinGroupRequest 协议结构

```protobuf
// src/clients/src/main/resources/protocol/message/JointGroupRequest.json
JoinGroupRequest => GroupId SessionId MemberId MemberGroupInstanceId
                     ProtocolType ProtocolName Metadata
  => ErrorCode LeaderId Assignment

GroupId:           STRING(0-255)
SessionId:         INT32
MemberId:          STRING(0-2147483647)  // "" 表示新加入
MemberGroupInstanceId: STRING(0-2147483647)  // null 表示动态加入
ProtocolType:      STRING(0-255)         // "consumer"
ProtocolName:      STRING(0-2147483647)  // "range-sticky"
Metadata:          BYTES               // 序列化后的订阅信息

// ConsumerCoordinator 构造 Metadata:
private def subscriptionsMetadata(
    consumerSessionTimeoutMs: Long,
    rebalanceTimeoutMs: Long,
    maxPollIntervalMs: Long
): Array[Byte] = {
  val builder = ConsumerProtocol.Metadata.builder()
    .setSessionTimeoutMs(consumerSessionTimeoutMs)
    .setRebalanceTimeoutMs(rebalanceTimeoutMs)
    .setMaxPollIntervalMs(maxPollIntervalMs)
    .addAllTopics(subscription.allTopics())  // 订阅的 Topic 集合
    .build()
  ConsumerProtocol.toByteArray(builder)  // Protobuf 编码
}
```

### 2.3 Coordinator 端 JoinGroup 处理

```java
// GroupCoordinator.scala — 核心调度逻辑
class GroupCoordinator(
    val groupIdMetadataCache: GroupMetadataCache,
    val groupMetadataCache: GroupMetadataCache,  // ZooKeeper/LogDir 持久化
    val groupTopicPartitionSchema: OffsetCommitRequestData
) extends Logging {
    
    // 核心方法：处理 JoinGroupRequest
    def handleJoinGroup(
        request: JoinGroupRequest.Builder,
        sessionTimeout: Int,
        rebalanceTimeout: Int,
        maxPollInterval: Long,
        memberMetadata: ByteBuffer,
        memberAssignments: util.Map[String, ByteBuffer]
    ): JoinGroupResponse = {
        
        val groupId = request.groupId
        val memberId = request.memberId
        
        // 1. 获取或创建 GroupMetadata
        val group = getOrCreateGroup(groupId)
        
        if (memberId.isEmpty || memberId == GroupMetadata.UNKNOWN_MEMBER_ID) {
            // 新成员：使用 sessionId 做冲突检测
            // 如果同一 sessionId 已有成员且不同 memberId → 旧成员已被踢出
            group.handleJoinGroup(
                request.requestId,
                request.sessionId,
                memberId,  // ""
                request.memberGroupInstanceId,
                request.protocolType,
                request.protocolName,
                memberMetadata,
                sessionTimeout,
                rebalanceTimeout,
                maxPollInterval
            )
        } else {
            // 已知成员 rejoin
            group.handleRejoinGroup(...)
        }
    }
}

// GroupMetadata.scala — Group 内部状态机
case class GroupMetadata(
    groupId: String,
    state: GroupState,           // Empty/PreparingRebalance/PreparingRebalance/CompletingRebalance/Dead
    generationId: Int,           // 当前 generation
    protocolType: String,        // "consumer"
    protocolName: String,        // "range-sticky"
    leaderId: String,            // 当前 leader 成员 ID
    protocolMetadata: Map[String, ByteBuffer], // 每个成员的 metadata
    members: Map[String, GroupMemberMetadata]
) {
    
    def handleJoinGroup(
        requestId: Int,
        sessionId: Int,
        memberId: String,
        groupInstanceId: String,
        protocolType: String,
        protocolName: String,
        memberMetadata: ByteBuffer,
        sessionTimeoutMs: Int,
        rebalanceTimeoutMs: Int,
        maxPollIntervalMs: Long
    ): JoinGroupResponseData = {
        
        if (state == GroupState.Empty) {
            // 第一成员加入 → 直接成为 leader
            setState(GroupState.PreparingRebalance)
            leaderId = memberId
        } else if (state == GroupState.PreparingRebalance) {
            // 等待其他成员
        } else if (state == GroupState.CompletingRebalance) {
            // 有成员在 sync 阶段超时 → 踢出，重新 PreparingRebalance
        }
        
        // 存储成员元数据
        memberMetadata = GroupMemberMetadata(
            memberId,
            groupInstanceId,
            sessionId,
            sessionTimeoutMs,
            memberMetadata,
            maxPollIntervalMs
        )
        
        // 所有成员已加入？→ 开始计算分配
        if (areAllMembersJoined()) {
            val leaderMember = members(leaderId)
            val allMetadata = members.map { case (id, m) => id -> m.metadata }.toMap
            val assignment = assignor.assign(group, allMetadata)
            
            // 发送 SyncGroup 给 leader
            sendSyncGroupToLeader(leaderId, assignment)
            
            // 通知其他成员等待
            for ((mid, _) <- members if mid != leaderId) {
                sendJoinGroupResponse(mid, ...)
            }
        }
    }
}
```

---

## 3. StickyAssignor 源码级分析

### 3.1 设计原理

StickyAssignor 的核心思想：**最小化 Rebalance 时的分区迁移**，从而减少消费者暂停时间。

```
之前：RangeAssignor
  5 consumers → Rebalance → 所有分区重新分配
  所有 consumer 暂停消费
  
之后：StickyAssignor  
  5 consumers → Rebalance → 只迁移必要的分区
  大部分 consumer 继续消费
```

### 3.2 源码实现

```java
// org.apache.kafka.clients.consumer.internals.StickyAssignor
public class StickyAssignor extends AbstractStickyAssignor implements PartitionAssignor {
    
    @Override
    public Map<String, List<TopicPartition>> assign(
        Map<String, Integer> partitionsPerTopic,  // topic → partition count
        Map<String, Subscription> subscriptions    // memberId → subscription
    ) {
        // 1. 从订阅信息中提取：成员列表、订阅 topic 集合、最大轮询间隔
        Set<String> allMembers = subscriptions.keySet();
        Map<String, Set<String>> allSubscriptions = new HashMap<>();
        
        for (Map.Entry<String, Subscription> entry : subscriptions.entrySet()) {
            allSubscriptions.put(entry.getKey(), entry.getValue().topics());
        }
        
        // 2. 获取上一次的分配方案（从 _consumer_offsets 中读取）
        //    如果存在稳定分配，则在此基础上做增量调整
        Map<TopicPartition, String> currentAssignment = getCurrentAssignment();
        
        // 3. 如果分配方案处于"稳定状态"，只处理变化的成员
        if (isStable(currentAssignment, allMembers, allSubscriptions)) {
            // 只需要将新成员的分区从现有分配中"剥离"
            return incrementalAssign(currentAssignment, allMembers, allSubscriptions);
        }
        
        // 4. 否则执行全量分配
        return assignAll(currentAssignment, partitionsPerTopic, allSubscriptions, allMembers);
    }
    
    // ========== 核心：最小化迁移的分配算法 ==========
    
    // 目标：最小化 |newAssignment \ currentAssignment|
    // 即：新分配中不属于旧分配的分区数最少
    private Map<String, Set<TopicPartition>> assignAll(
        Map<TopicPartition, String> currentAssignment,
        Map<String, Integer> partitionsPerTopic,
        Map<String, Set<String>> allSubscriptions,
        Set<String> allMembers
    ) {
        // 步骤1: 将 topic → partition 映射到每个订阅者
        Map<String, Set<TopicPartition>> possibleAssignments = new HashMap<>();
        for (Map.Entry<String, Set<String>> entry : allSubscriptions.entrySet()) {
            String memberId = entry.getKey();
            Set<String> topics = entry.getValue();
            Set<TopicPartition> partitions = new HashSet<>();
            
            for (String topic : topics) {
                Integer numPartitions = partitionsPerTopic.get(topic);
                for (int p = 0; p < numPartitions; p++) {
                    partitions.add(new TopicPartition(topic, p));
                }
            }
            possibleAssignments.put(memberId, partitions);
        }
        
        // 步骤2: 如果当前有稳定分配，尝试保持
        if (currentAssignment != null && currentAssignment.isEmpty()) {
            return assign(currentAssignment, partitionsPerTopic, allSubscriptions, allMembers);
        }
        
        // 步骤3: 核心贪心分配
        // 按 member 的 possible assignment 集合大小排序（先处理选择少的）
        // 然后尝试保持现有分配
        Map<String, Set<TopicPartition>> assigned = new HashMap<>();
        Set<TopicPartition> unassigned = new HashSet<>(possibleAssignments.values());
        
        for (String memberId : allMembers) {
            Set<TopicPartition> memberPossible = possibleAssignments.get(memberId);
            Set<TopicPartition> toAssign = new HashSet<>(memberPossible);
            
            // 尽量保留旧的分配
            if (currentAssignment != null) {
                Set<TopicPartition> oldForMember = currentAssignment.entrySet().stream()
                    .filter(e -> e.getValue().equals(memberId))
                    .map(Map.Entry::getKey)
                    .collect(Collectors.toSet());
                toAssign.retainAll(memberPossible);
            }
            
            assigned.put(memberId, toAssign);
            unassigned.removeAll(toAssign);
        }
        
        // 步骤4: 分配未分配的分区（贪心：分配给拥有该分区的成员中 partition count 最少的）
        while (!unassigned.isEmpty()) {
            TopicPartition tp = unassigned.iterator().next();
            String topic = tp.topic();
            int partition = tp.partition();
            
            // 找出可以消费这个 partition 的成员
            List<String> candidates = allMembers.stream()
                .filter(m -> allSubscriptions.get(m).contains(topic))
                .sorted(Comparator.comparingInt(m -> assigned.get(m).size()))
                .collect(Collectors.toList());
            
            if (!candidates.isEmpty()) {
                String chosen = candidates.get(0);
                assigned.get(chosen).add(tp);
                unassigned.remove(tp);
            }
        }
        
        return assigned;
    }
}

// AbstractStickyAssignor — 稳定判断和增量调整
abstract class AbstractStickyAssignor implements PartitionAssignor {
    
    // 判断当前分配是否"稳定"
    // 稳定条件：
    //  1. 当前分配非 null 且非空
    //  2. 没有成员订阅了新的 topic
    //  3. 没有成员删除了之前订阅的 topic
    //  4. 新加入的成员数量为 0（或只有新成员，无老成员离开）
    boolean isStable(
        Map<TopicPartition, String> currentAssignment,
        Set<String> allSubscribedMembers,
        Map<String, Set<String>> allSubscriptions
    ) {
        if (currentAssignment == null || currentAssignment.isEmpty()) {
            return false;
        }
        
        // 检查是否只有新成员加入
        Set<String> currentGroupMembers = currentAssignment.values().stream()
            .collect(Collectors.toSet());
        
        boolean onlyNewMembers = allSubscribedMembers.stream()
            .allMatch(m -> !currentGroupMembers.contains(m));
        
        // 检查是否没有成员新增/删除 topic
        boolean noTopicChange = allSubscriptions.entrySet().stream()
            .allMatch(entry -> {
                String memberId = entry.getKey();
                Set<String> oldTopics = getOldTopics(memberId);
                return oldTopics == null || oldTopics.equals(entry.getValue());
            });
        
        return onlyNewMembers || noTopicChange;
    }
}
```

### 3.3 增量分配 vs 全量分配

```java
// Incremental 模式下，Kafka 0.11.0+ 引入了增量订阅/分配

// 协议：JoinGroupRequest v6 + SyncGroupRequest v4
// 成员可以携带 subcriptionType=INCREMENTAL_STATIC 标记

// 增量分配的核心逻辑：
//  当只有新成员加入时：
//    1. 不重新分配所有分区
//    2. 只将新成员需要消费的分区从现有成员的分配中移除
//    3. 被移除分区的成员不需要停止消费（sticky 的关键）

// 示例：
//  初始: C1->[p0,p1], C2->[p2,p3], C3->[p4,p5]
//  加入 C4 后（增量）:
//    C1->[p0,p1]  ← 不变
//    C2->[p2,p3]  ← 不变
//    C3->[p4,p5]  ← 不变
//    C4->[p0]     ← 从 C1 拿走 p0
//  C1 继续消费 p1，C4 开始消费 p0 → 零中断
```

### 3.4 Rebalance 期间消费者状态机

```java
// ConsumerCoordinator.GroupRebalanceConfig
// 状态流转:

//         ┌──────────┐
//         │  Started │
//          └────┬─────┘
//               │
//               ▼
//     ┌──────────────────┐
//     │  Unsubscribed    │  (未订阅任何 topic)
//     └──────────────────┘
//               │
//               │ subscribe(topics)
//               ▼
//     ┌──────────────────┐    ┌──────────────────┐
//     │  Subscribed      │───▶│  Assigning       │  (rebalance 中)
//     └──────────────────┘    └────────┬─────────┘
//                                     │
//                      ┌──────────────┼──────────────┐
//                      │              │              │
//                     ▼              ▼              ▼
//              ┌──────────────┐ ┌──────────┐ ┌────────────┐
//              │  RevokePartitions  │ │ AssignPartitions │ │ CommitOffsets │
//              │  (撤销旧分区)    │ │ (分配新分区)    │ │ (提交偏移)     │
//              └──────────────┘ └──────────┘ └────────────┘
//                      │              │              │
//                      └──────────────┼──────────────┘
//                                     │
//                                     ▼
//                             ┌──────────────┐
//                             │  Polling     │  (正常消费)
//                             └──────────────┘
//                                     │
//                                  close() / timeout
//                                     │
//                                     ▼
//                             ┌──────────────┐
//                             │  Dead        │
//                             └──────────────┘
```

---

## 4. 服务端 GroupCoordinator 源码

### 4.1 GroupCoordinator 核心类

```scala
// kafka.coordinator.group.GroupCoordinator (Kafka 3.x+)
class GroupCoordinator(
    val config: GroupCoordinatorConfig,
    val time: Time,
    val kafkaScheduler: KafkaScheduler,
    val dynamicConfig: GroupCoordinatorConfigHandler,
    val metrics: Metrics,
    val partitionRegistrator: GroupMetadataManager.PartitionListener,
    val transactionCoordinator: TransactionCoordinator,
    val storage: GroupMetadataManager,  // 负责持久化 GroupMetadata
    val groupMetadataCache: GroupMetadataCache
) extends AbstractCoordinator[GroupMetadata](
    storage,
    metrics,
    time,
    groupMetadataCache,
    config
) {
    
    // ========== 关键方法 ==========
    
    // 处理 JoinGroupRequest
    def handleJoinGroup(
        memberId: String,
        groupId: String,
        sessionTimeout: Int,
        rebalanceTimeout: Int,
        maxPollInterval: Long,
        memberMetadata: ByteBuffer,
        memberAssignments: util.Map[String, ByteBuffer]
    ): JoinGroupResponseData = {
        
        val response = new JoinGroupResponseData()
        
        // 获取或创建 group
        val group = getGroup(groupId)
        
        if (memberId.isEmpty || memberId == GroupMetadata.UNKNOWN_MEMBER_ID) {
            // 新成员
            handleJoinGroupForNewMember(...)
        } else {
            // 已知成员 rejoin
            handleJoinGroupForExistingMember(...)
        }
        
        // 如果自己是 leader，计算分配方案
        if (memberId == group.leaderId) {
            val assignment = partitionAssignor.assign(group, memberAssignments)
            response.setAssignment(assignmentsToByteBuffer(assignment))
        }
        
        response
    }
    
    // 处理 SyncGroupRequest
    def handleSyncGroup(
        memberId: String,
        groupId: String,
        generationId: Int,
        groupInstanceId: String,
        memberAssignment: ByteBuffer
    ): SyncGroupResponseData = {
        
        val group = getGroup(groupId)
        
        if (memberId == group.leaderId) {
            // Leader 发送的是分配方案（已经由 assign 计算好）
            // Coordinator 将其广播给所有成员
            val assignment = ByteBufferToAssignments(memberAssignment)
            group.updateAssignment(generationId, assignment)
            
            // 通知所有成员新的分配方案
            for (member <- group.allMembers) {
                sendSyncGroupResponse(member, generationId, memberAssignment)
            }
            
            // 更新状态
            group.setState(GroupState.Stable)
        } else {
            // 非 leader 接收分配方案
            val assignment = memberAssignment
            // 更新本地分配
            updateLocalMemberAssignment(groupId, generationId, assignment)
        }
    }
    
    // 心跳检测 / 踢出死亡成员
    def handleHeartbeat(
        groupId: String,
        memberId: String,
        generationId: Int,
        groupInstanceId: String
    ): HeartbeatResponseData = {
        
        val group = getGroup(groupId)
        
        if (group == null || !group.isAlive) {
            return new HeartbeatResponseData()
                .setErrorCode(Errors.GROUP_COORDINATOR_NOT_AVAILABLE.code)
        }
        
        if (group.generationId != generationId) {
            // generation 不匹配 → 成员需要重新 JoinGroup
            return new HeartbeatResponseData()
                .setErrorCode(Errors.ILLEGAL_GENERATION.code)
        }
        
        if (group.isMember(memberId)) {
            // 更新心跳时间
            group.updateMemberLastHeartbeat(memberId, time.milliseconds())
            
            // 检查是否有成员超时 → 触发 rebalance
            checkForStaleMembers(group)
            
            new HeartbeatResponseData()
                .setErrorCode(Errors.NONE.code)
        } else {
            new HeartbeatResponseData()
                .setErrorCode(Errors.UNKNOWN_MEMBER_ID.code)
        }
    }
}
```

### 4.2 踢出死亡成员机制

```scala
// GroupCoordinator.scala — 定时任务检测超时成员
// 后台调度器每隔 heartbeat.interval.ms / 3 检查一次
kafkaScheduler.startup()

def checkForStaleMembers(group: GroupMetadata): Unit = {
    val now = time.milliseconds()
    val staleMembers = group.allMembers.filter { member =>
        val timeSinceLastHeartbeat = now - member.lastHeartbeatTime
        val sessionTimeoutMs = config.sessionTimeoutMs
        
        timeSinceLastHeartbeat > sessionTimeoutMs
    }
    
    if (staleMembers.nonEmpty) {
        // 踢出所有超时的成员
        for (staleMember <- staleMembers) {
            group.removeMember(staleMember.memberId)
            // 触发新的 rebalance
            initiateRebalance(group)
        }
    }
}

// 触发 Rebalance
def initiateRebalance(group: GroupMetadata): Unit = {
    // 1. 将 group 状态改为 PreparingRebalance
    group.setState(GroupState.PreparingRebalance)
    
    // 2. 如果是稳定状态下的变化，需要先通知成员撤销分区
    if (group.state == GroupState.Stable) {
        // 发送 OffsetCommitRequest 通知 consumer 提交当前 offset
        notifyAllMembers(group, GroupState.PreparingRebalance)
    }
    
    // 3. 等待 JoinGroup 请求
    //    coordinator 端有一个 pendingJoinGroup 队列
    //    当所有成员到达后 → 计算分配 → 发送 SyncGroup
}
```

### 4.3 _consumer_offsets 主题

```
// 内部主题 _consumer_offsets 的物理布局
__consumer_offsets  (partitions=50, replication.factor=3)

┌──────────────────────────────────────────────────────┐
│ Partition 0                    Partition 49           │
│ ┌────────┐ ┌────────┐ ┌───┐  ┌────────┐ ┌────────┐  │
│ │Seg-0   │ │Seg-1   │ │...│  │Seg-N-1 │ │Seg-N   │  │
│ │records │ │records │ │   │  │records  │ │records │  │
│ └────────┘ └────────┘ └───┘  └────────┘ └────────┘  │
└──────────────────────────────────────────────────────┘

存储的 Record 类型:
  - GROUP_METADATA:  GroupState, GenerationId, LeaderId, ProtocolType, ProtocolName
  - MEMBER_METADATA: MemberId, GroupInstanceId, SessionTimeout, Metadata
  - OFFSET_COMMIT:   Topic, Partition, Offset, Metadata, CommitTimestamp
  -Txn_METADATA:      ProducerId, ProducerEpoch, LastStableOffset

Key 分区策略: Hash(groupId) % 50
```

---

## 5. 消费者端 Rebalance 回调

```java
// org.apache.kafka.clients.consumer.ConsumerRebalanceListener
public interface ConsumerRebalanceListener {
    /**
     * 在分区被撤销前调用（revoke 阶段）
     * 适合在此提交 pending offset
     */
    void onPartitionsRevoked(Collection<TopicPartition> partitions);
    
    /**
     * 在分区分配后调用（assign 阶段）
     * 适合在此恢复消费位置
     */
    void onPartitionsAssigned(Collection<TopicPartition> partitions);
}

// KafkaConsumer 中的内部实现
private class DefaultConsumerRebalanceListener implements ConsumerRebalanceListener {
    @Override
    public void onPartitionsRevoked(Collection<TopicPartition> partitions) {
        // 1. 同步提交偏移量（如果有 auto.commit 的 pending 值）
        if (autoCommitEnabled && subscriptions.hasFetchableOffsets()) {
            coordinator.commitSync(subscriptions.allConsumed());
        }
        
        // 2. 撤销拉取任务
        fetcher.unassign(partitions);
        
        // 3. 唤醒 Sender 线程处理 pending request
        waker.wakeup();
    }
    
    @Override
    public void onPartitionsAssigned(Collection<TopicPartition> partitions) {
        // 1. 确定每个分区的拉取起始位置（seek）
        for (TopicPartition tp : partitions) {
            if (!subscriptions.hasRequestedOffset(tp)) {
                if (subscriptions.isOffsetResetNeeded(tp)) {
                    // 自动重置策略: latest / earliest / none
                    coordinator.resetOffset(tp);
                } else {
                    // 使用已提交的 offset
                    OffsetAndMetadata offsetAndMetadata = subscriptions.committed(tp);
                    client.seek(tp, offsetAndMetadata.offset());
                }
            }
        }
        
        // 2. 唤醒拉取循环
        waker.waker();
    }
}
```

---

## 6. 常见问题与源码级根因

### 6.1 为什么 Rebalance 会触发？

```java
// ConsumerCoordinator 中触发 Rebalance 的所有路径：

// 路径 1: 心跳超时
// GroupCoordinator.checkForStaleMembers() → 成员超时 → initiateRebalance()

// 路径 2: 显式 leave group
// KafkaConsumer#close() → LeaveGroupRequest → GroupCoordinator.removeMember()

// 路径 3: max.poll.interval.ms 超时
// KafkaConsumer.poll() 内部循环:
//   long timeElapsed = time.milliseconds() - lastPollTime;
//   if (timeElapsed > maxPollIntervalMs) {
//       // 主动 leave group，触发 rebalance
//       coordinator.ensureActiveGroup();
//   }

// 路径 4: 订阅的 topic 变化
// KafkaConsumer.subscribe(pattern, listener) → SubscriptionState 变化
//   → coordinator.updatePatternSubscription(pattern) → rebalance

// 路径 5: Consumer 实例化时 group.instance.id 固定
// 如果 group.instance.id 存在但不匹配 → coordinator 拒绝并触发 rebalance
```

### 6.2 StickyAssignor 的稳定性保证

```
稳定状态判定 (AbstractStickyAssignor.isStable):

条件 A: currentAssignment 非空且当前所有成员都在 assignment 中
条件 B: 没有成员新增了订阅 topic
条件 C: 没有成员删除了订阅 topic
条件 D: 新加入的成员数量 ≤ 1 或者没有成员离开

满足 A+B+C+D → 增量调整，只移动新成员的分区
不满足 → 全量重新分配

增量调整的迁移成本:
  全量分配: O(N_partitions) 个分区迁移
  增量调整: O(N_new_members * partitions_per_member) 个分区迁移
```

---

## 7. 配置参数源码级说明

```properties
# ===== Consumer 端 =====

# 会话超时: GroupCoordinator 在没有收到心跳多久后认为成员死亡
# 源码: GroupMetadata.SESSION_TIMEOUT_MS_DEFAULT = 45000
# 影响: checkForStaleMembers() 的阈值
group.initial.rebalance.delay.ms=3000
# 初始 rebalance 延迟：等待所有成员到达后再开始计算分配
# 源码: GroupCoordinator.handleJoinGroup() 中的 waitUntilReady()
# 适用: 批量启动 consumer 时减少不必要的 rejoin-rebalance

# 心跳间隔: 发送 HeartbeatRequest 的频率
# 源码: ConsumerNetworkClient.poll() 中检查 heartbeatTimer
heartbeat.interval.ms=3000
# 要求: heartbeat.interval.ms <= session.timeout.ms / 3
# 原因: 确保在会话超时前至少收到 3 次心跳

# 最大轮询间隔: 两次 poll() 之间的最大允许间隔
# 源码: ConsumerCoordinator.poll() → 检查 timeElapsed > maxPollIntervalMs
# 超过则主动 leave group
max.poll.interval.ms=300000
# 关联: max.poll.records=500 (每次 poll 最多返回 500 条)
# 关键: max.poll.interval.ms > 处理 max.poll.records 条消息的时间

# 固定实例 ID (幂等加入组)
# 源码: JoinGroupRequest.groupInstanceId
# 效果: 消费者拥有固定 ID 后，rebalance 时不会更换 memberId
#       因此 GroupCoordinator 知道这是同一个消费者，无需撤销分配
group.instance.id=consumer-1

# ===== 服务端 =====

# offsets.topic.num.partitions=50
# 决定 GroupCoordinator 的分区数和并行度
# 源码: GroupMetadataManager 按 hash(groupId) % numPartitions 路由

# offsets.topic.replication.factor=3
# _consumer_offsets 的副本因子

# group.min.session.timeout.ms / group.max.session.timeout.ms
# 限制消费者可设置的 sessionTimeoutMs 范围
```

---

## 8. Rebalance 与零拷贝的关系（对比理解）

```
Rebalance 影响面:
┌──────────────────────────────────────────────────────────┐
│ 消费者端:                                                │
│  • 分区分配变更 → 重新 seek                             │
│  • 取消旧分区 → fetcher 停止拉取                        │
│  • 新增分区 → fetcher 开始拉取                          │
│  • 暂停时间 = O(分区迁移数 × seek 延迟)                  │
│                                                          │
│  Broker 端（零拷贝无关）:                                │
│  • Rebalance 是控制平面协议，不涉及数据面传输              │
│  • 零拷贝 (sendfile/sendFile) 只在 FetchRequest/          │
│    ReadRequest 数据面生效                                │
└──────────────────────────────────────────────────────────┘
```

---

*本文档聚焦 Kafka Consumer Rebalance 协议的源码级实现，涵盖 ConsumerCoordinator、StickyAssignor、GroupMetadataManager 等核心组件。*
