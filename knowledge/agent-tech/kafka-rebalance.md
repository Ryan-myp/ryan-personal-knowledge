# Kafka Rebalance 流程

> 标签: `#Kafka` `#消费者组` `#重平衡`
> 创建日期: 2026-06-08
> 作者: Ryan

---

## 1. 什么是 Rebalance？

Rebalance（重平衡）是 Kafka 消费者组（Consumer Group）中分区分配方案重新计算和更新的过程。当消费者组中消费者数量发生变化时，Kafka 会自动触发 Rebalance。

**核心概念**：

```
Consumer Group A:  [Consumer-1] [Consumer-2] [Consumer-3]
                      ↓          ↓          ↓
Topic "orders":    [P0] [P1] [P2] [P3] [P4] [P5]

Consumer-1 负责: P0, P1
Consumer-2 负责: P2, P3
Consumer-3 负责: P4, P5

↓ 当 Consumer-2 下线后触发 Rebalance ↓

Consumer Group A:  [Consumer-1]           [Consumer-3]
                      ↓                    ↓
Topic "orders":    [P0] [P1] [P2] [P3] [P4] [P5]

Consumer-1 负责: P0, P1, P2, P3
Consumer-3 负责: P4, P5
```

## 2. Rebalance 的触发条件

- **新消费者加入组**
- **消费者离开组**（正常关闭或故障）
- **Topic 分区数发生变化**
- **消费者订阅的 Topic 发生变化**

## 3. Rebalance 的核心流程

### 流程图

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Consumer   │────▶│ Group Coordinator│────▶│   Group Leader  │
│  (消费者)    │     │   (协调器)       │     │   (领导者)       │
└─────────────┘     └──────────────────┘     └─────────────────┘
       │                     │                       │
       │  JoinGroup          │  等待所有消费者        │  收集消费者信息
       │────────────────────▶│                       │
       │                     │                       │
       │  (非 Leader)        │  选举 Leader          │  计算分区分配
       │                     │                       │
       │                     │  SyncGroup            │  SyncGroup
       │  接收分配方案◀──────│◀──────────────────────│
       │                     │                       │
       │  更新分区分配        │                       │
       │  开始消费            │                       │
```

### 详细流程（8 步）

```
步骤 1: Consumer 启动，向任意 Broker 发送 FindCoordinatorRequest
         ↓
步骤 2: Broker 返回 Group Coordinator（某个 Broker）
         ↓
步骤 3: Consumer 向 Coordinator 发送 JoinGroupRequest
         ↓
步骤 4: Coordinator 等待所有 Consumer 发送 JoinGroupRequest
         等待时间由 group.initial.rebalance.delay.ms 控制
         ↓
步骤 5: 第一个发送的 Consumer 成为 Group Leader
         Leader 收集所有 Consumer 的元数据（订阅的 Topic、消费能力等）
         ↓
步骤 6: Leader 根据分区分配策略计算方案
         常用策略: RangeAssignor / RoundRobinAssignor / StickyAssignor
         ↓
步骤 7: Leader 发送 SyncGroupRequest（携带分配方案）
         Coordinator 将方案分发给所有 Consumer
         ↓
步骤 8: 每个 Consumer 更新本地分区分配
         取消不再分配的分区，开始消费新分配的分区
```

### 各步骤详解

#### 步骤 1-2: 选择 Group Coordinator

每个 Consumer 启动时，向 Kafka 集群中的任意 Broker 发送 `FindCoordinatorRequest`，返回负责该消费者组的 Coordinator Broker。后续所有消费者组相关操作都向该 Coordinator 发送。

**Coordinator 的选择规则**：对消费者组 ID 做 hash，取模后映射到某个 Broker。

#### 步骤 3: 发送 JoinGroup 请求

Consumer 向 Coordinator 发送 `JoinGroupRequest`，包含：
- 消费者组 ID
- 消费者 ID
- 订阅的 Topic 列表
- 协议类型和协议版本

**⚠️ 关键点**：第一个发送 JoinGroupRequest 的 Consumer 成为 Group Leader。

#### 步骤 4-5: 选举 Group Leader

Coordinator 等待所有 Consumer 发送 JoinGroupRequest。等待时间由 `group.initial.rebalance.delay.ms` 控制（默认 0）。第一个发送请求的 Consumer 成为 Group Leader，负责后续分区分配计算。

#### 步骤 6: 计算分区分配方案

Group Leader 收集所有消费者的信息后，根据分区分配策略计算方案：

| 分配策略 | 原理 | 适用场景 |
|---------|------|---------|
| RangeAssignor | 按 Topic 分区范围分配 | 分区数少，消费者数少 |
| RoundRobinAssignor | 轮询分配 | 所有 Topic 分区数相同 |
| StickyAssignor | 粘性分配，最小化分区迁移 | Kafka 0.11.0+ 推荐 |

**StickyAssignor 优势**：尽量保持上一次分配方案不变，只在必要时移动少量分区，减少 Rebalance 时的消费者暂停时间。

#### 步骤 7: 发送 SyncGroup 请求

每个 Consumer 向 Coordinator 发送 `SyncGroupRequest`。Group Leader 携带计算好的分配方案。Coordinator 将方案分发给所有 Consumer。

#### 步骤 8: 更新分区分配

Consumer 收到分配方案后：
1. 取消不再分配的分区订阅
2. 提交当前分区的偏移量（如果有）
3. 开始消费新分配的分区

## 4. Rebalance 的影响和优化

### Rebalance 的影响

```
正常消费:  │──Consuming──│──Consuming──│──Consuming──│
           │              │              │
Rebalance: │\_________/│  (暂停消费，Consumer 元数据交换)
           │              │              │
```

- **暂停消费**：Rebalance 期间消费者暂停消息处理
- **延迟增加**：可能导致消息处理延迟
- **性能下降**：频繁的 Rebalance 会影响系统性能

### 优化措施

#### 1. 使用 StickyAssignor（推荐）

```properties
partition.assignment.strategy=org.apache.kafka.clients.consumer.StickyAssignor
```

#### 2. 合理设置超时参数

```properties
# 会话超时时间：Consumer 多久没发心跳被认为死亡
session.timeout.ms=45000

# 心跳间隔：每隔多久发一次心跳（应小于 session.timeout.ms 的 1/3）
heartbeat.interval.ms=15000

# 最大轮询间隔：两次 poll() 之间的最大间隔
max.poll.interval.ms=300000
max.poll.records=500  # 每次 poll 最多返回 500 条，避免处理超时
```

**关键原则**：`session.timeout.ms > heartbeat.interval.ms * 3`，且 `max.poll.interval.ms` 要大于实际处理一批消息的最大时间。

#### 3. 避免不必要的 Rebalance

- 使用长连接，避免 Consumer 频繁加入/离开
- 消费者下线前先 `consumer.close()` 优雅退出
- 合理设置 `group.initial.rebalance.delay.ms`（初始 Rebalance 延迟）

## 5. 常见 Rebalance 问题排查

### 问题 1: Rebalance 频繁触发

**症状**：日志中频繁出现 `Revoking previous partitions` / `RevokePartitions`

**原因**：
- `session.timeout.ms` 设置过小，Consumer 网络波动被误判死亡
- `max.poll.interval.ms` 设置过小，处理消息超时
- Consumer 处理消息太慢，来不及调用 `poll()`

**排查**：
```bash
# 查看 Consumer 日志中的 Rebalance 记录
grep -i "rebalance" consumer.log

# 检查 Consumer 的 poll 间隔
# 在代码中埋点记录 poll() 调用间隔
```

### 问题 2: Consumer 无法加入 Consumer Group

**症状**：Consumer 一直在 `JoinGroup` 状态，无法进入 `AssignPartitions`

**原因**：
- Coordinator 不可用
- 网络问题导致 JoinGroupRequest 超时
- 版本不兼容

### 问题 3: 分区分配不均

**症状**：某些 Consumer 负责的分区多，某些少

**原因**：
- 使用 RangeAssignor，且 Topic 分区数与 Consumer 数量不匹配
- 不同 Consumer 订阅的 Topic 列表不同

**解决**：使用 StickyAssignor 或 RoundRobinAssignor

## 6. 配置参数速查

| 参数 | 默认值 | 说明 | 推荐值 |
|------|--------|------|--------|
| `session.timeout.ms` | 10000 | 会话超时时间 | 45000 |
| `heartbeat.interval.ms` | 3000 | 心跳间隔 | 15000 |
| `max.poll.interval.ms` | 300000 | 最大轮询间隔 | 300000 |
| `max.poll.records` | 500 | 每次 poll 最大返回条数 | 500 |
| `group.initial.rebalance.delay.ms` | 0 | 初始重平衡延迟 | 3000 |
| `partition.assignment.strategy` | RangeAssignor | 分区分配策略 | StickyAssignor |

---

*本文档基于微信读书《Kafka权威指南》及相关技术文档整理*
