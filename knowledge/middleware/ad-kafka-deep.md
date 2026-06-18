# Kafka 深度：Replication/Consumer Group/Controller 源码级

> 逐行解析 Kafka 核心组件源码

---

## 第一部分：Replication 源码深度

### Replication 架构

```
Kafka 副本架构：
┌─────────────────────────────────────────────────────────────────────┐
│ Controller Broker                                                    │
│ (负责分区 leader/follower 选举、ISR 管理)                              │
│                                                                     │
│ ┌────────┐  ┌────────┐  ┌────────┐                                 │
│ │Broker 1│  │Broker 2│  │Broker 3│                                 │
│ │Topic:A │  │Topic:A │  │Topic:A │                                 │
│ │Part:0  │  │0,1,2  │  │0,1,2  │                                   │
│ │Leader✓ │  │Follower│  │Follower│                                 │
│ │ISR✓   │  │ISR ✓  │  │ISR ✓  │                                   │
│ └────────┘  └────────┘  └────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘

ISR (In-Sync Replicas):
- 与 leader 保持同步的副本集合
- 只有 ISR 中的副本才能选举为 leader
- 副本落后 leader 超过阈值 → 移出 ISR
```

### ReplicaManager.appendRecords 源码逐行解析

```scala
// Kafka 源码：kafka.server.ReplicaManager.appendRecords
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
  if (isFromClient)
    asynchronousReplicaAlterDirThreads.execute(() =>
      alterReplicaLogDir(tp, isFuture = false))
}
```

### Partition.updateISR 源码逐行解析

```scala
// Kafka 源码：kafka.cluster.Partition.updateISR
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

### handleControllerFailover 源码逐行解析

```scala
// Kafka 源码：kafka.controller.KafkaController.handleControllerFailover
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

---

## 第三部分：Consumer Group 源码深度

### Consumer Group 架构

```
Consumer Group 模型：
┌─────────────────────────────────────────────────────────────────────┐
│ Consumer Group: "order-service"                                      │
│                                                                      │
│ Consumer 1 (C1)    Consumer 2 (C2)                                  │
│ Partition 0, 1     Partition 2, 3                                  │
│ ┌────────┐         ┌────────┐                                       │
│ │ P0-Leader│        │ P2-Leader│                                     │
│ └────────┘         └────────┘                                       │
│ ┌────────┐         ┌────────┐                                       │
│ │ P1-Leader│        │ P3-Leader│                                     │
│ └────────┘         └────────┘                                       │
└─────────────────────────────────────────────────────────────────────┘

核心原则：
- 每个 Partition 只能被 Group 中的一个 Consumer 消费
- Consumer 数量 ≤ Partition 数量（否则有闲置 Consumer）
- rebalance 时暂停所有 Consumer 的消费
```

### CooperativeStickyAssignor 源码逐行解析

```java
// Kafka 源码：org.apache.kafka.clients.consumer.internals.CooperativeStickyAssignor
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
    for (String memberId : subscriptions.keySet())
        newAssignment.put(memberId, new HashSet<>());
    
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

---

## 第四部分：Rebalance 源码深度

### ensureActiveGroup 源码逐行解析

```java
// Kafka 源码：org.apache.kafka.clients.consumer.internals.ConsumerCoordinator
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

### Q3: 如何避免 Rebalance 导致的消费停顿？

**A**:
1. 使用 Cooperative Sticky Assignor（增量 rebalance）
2. 增加 session.timeout.ms（但会增加故障检测时间）
3. 增加 max.poll.interval.ms（允许更长处理时间）
4. 使用静态成员加入（static.member.enable=true）
5. 分区数设计合理（Consumer 数 ≤ Partition 数）

---

## 第六部分：生产实践

### 1. ISR 频繁缩容

```bash
# 检查 ISR 状态
kafka-topics.sh --describe --topic my-topic --bootstrap-server broker:9092

# 常见问题：
# 1. 网络延迟高 → 增加 replica.lag.time.max.ms
# 2. 磁盘 IO 瓶颈 → 使用 SSD
# 3. 消息太大 → 减小 max.message.bytes
# 4. 副本数太多 → 减少 replicas 数量
```

### 2. Consumer 反复 Rebalance

```bash
# 检查 Consumer Group 状态
kafka-consumer-groups.sh --describe --group my-group --bootstrap-server broker:9092

# 常见问题：
# 1. 处理时间过长 → 增加 max.poll.interval.ms
# 2. 心跳超时 → 增加 session.timeout.ms
# 3. GC 停顿 → 调整 JVM 参数
# 4. 网络不稳定 → 检查网络延迟
```

### 3. Controller 频繁切换

```bash
# 检查 Controller 状态
kafka-metadata.sh --snapshot /var/kafka-logs/meta.properties --command "controller"

# 常见问题：
# 1. ZK 会话超时 → 增加 zookeeper.session.timeout.ms
# 2. Broker 频繁上下线 → 检查服务器稳定性
# 3. 网络分区 → 检查网络拓扑
```
