# Kafka Rebalance 流程

> 标签: `#Kafka` `#消费者组` `#重平衡`
> 创建日期: 2026-06-08
> 作者: Ryan

---

## 1. 什么是 Rebalance？

Rebalance（重平衡）是 Kafka 消费者组（Consumer Group）中分区分配方案重新计算和更新的过程。当消费者组中消费者数量发生变化时，Kafka 会自动触发 Rebalance。

## 2. Rebalance 的触发条件

- **新消费者加入组**
- **消费者离开组**（正常关闭或故障）
- **Topic 分区数发生变化**
- **消费者订阅的 Topic 发生变化**

## 3. Rebalance 的核心流程

### 流程步骤

1. **消费者启动** — 消费者实例启动
2. **选择 Group Coordinator** — 选择负责管理该消费者组的协调器
3. **发送 JoinGroup 请求** — 消费者向 Coordinator 发送加入请求
4. **选举 Group Leader** — 第一个发送请求的消费者成为 Leader
5. **收集消费者信息** — Leader 收集所有消费者的元数据
6. **计算分区分配方案** — Leader 根据算法计算分配方案
7. **发送 SyncGroup 请求** — Leader 将方案发送给 Coordinator
8. **Coordinator 分发方案** — Coordinator 将方案分发给所有消费者
9. **更新分区分配** — 消费者更新本地分区归属关系
10. **开始消费消息** — 消费者正式开始消费

### 详细流程

#### 步骤 1: 选择 Group Coordinator
- 每个 Consumer 启动时，向 Kafka 集群中的任意 Broker 发送 `FindCoordinatorRequest`
- 返回负责该消费者组的 Coordinator Broker
- 后续所有消费者组相关操作都向该 Coordinator 发送

#### 步骤 2: 发送 JoinGroup 请求
- 消费者向 Coordinator 发送 `JoinGroupRequest`
- 包含消费者组 ID、消费者 ID、订阅的 Topic 列表等
- 第一个发送 JoinGroup 请求的消费者成为 Group Leader

#### 步骤 3: 选举 Group Leader
- Coordinator 等待所有消费者发送 JoinGroup 请求
- 等待时间由 `group.initial.rebalance.delay.ms` 控制
- 第一个发送请求的消费者成为 Group Leader
- Leader 负责计算分区分配方案

#### 步骤 4: 计算分区分配方案
- Group Leader 收集所有消费者的信息
- 根据分区分配策略计算方案
- 常用的分配策略：
  - **RangeAssignor**：按 Topic 分区范围分配
  - **RoundRobinAssignor**：轮询分配
  - **StickyAssignor**：粘性分配（Kafka 0.11.0+）

#### 步骤 5: 发送 SyncGroup 请求
- 每个消费者向 Coordinator 发送 `SyncGroupRequest`
- Group Leader 携带计算好的分配方案
- Coordinator 将分配方案分发给所有消费者

#### 步骤 6: 更新分区分配
- 消费者收到分配方案后，更新本地分区分配
- 取消不再分配的分区订阅
- 开始消费新分配的分区

## 4. Rebalance 的影响和优化

### Rebalance 的影响
- **暂停消费**：Rebalance 期间消费者暂停消息处理
- **延迟增加**：可能导致消息处理延迟
- **性能下降**：频繁的 Rebalance 会影响系统性能

### 优化措施
- **增加 `group.initial.rebalance.delay.ms`**：延迟触发 Rebalance
- **使用 StickyAssignor**：减少分区移动
- **合理设置 `session.timeout.ms`**：避免误判消费者故障
- **使用 `max.poll.interval.ms`**：控制消费者处理超时

## 5. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `session.timeout.ms` | 10000 | 会话超时时间 |
| `heartbeat.interval.ms` | 3000 | 心跳间隔 |
| `max.poll.interval.ms` | 300000 | 最大轮询间隔 |
| `group.initial.rebalance.delay.ms` | 0 | 初始重平衡延迟 |
| `partition.assignment.strategy` | RangeAssignor | 分区分配策略 |

---

*本文档基于微信读书《Kafka权威指南》及相关技术文档整理*
