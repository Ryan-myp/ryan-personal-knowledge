# Kafka 源码/Controller/Consumer Group 深度

> Kafka Controller 选举 / Consumer Group 协调 / Rebalance 策略 / 事务消息 / 零拷贝

---

## 第一部分：入门引导（5 分钟速览）

### Kafka 为什么快？

1. **顺序写磁盘**：利用文件系统缓存，顺序写比随机写快 10 倍
2. **零拷贝**：sendfile 系统调用，减少 CPU 拷贝
3. **分区并行**：每个分区独立处理
4. **批量发送**：Producer 批量发送减少网络开销

### Kafka 架构

```
Producer → Broker 1 (Leader) → Broker 2 (Follower)
                ↓
Broker 3 (Leader) → Broker 4 (Follower)
                ↓
Consumer Group → Partition 0 → Partition 1
```

---

## 第二部分：Controller 选举

### 2.1 Controller 职责

```
Controller 负责：
1. Topic 创建/删除
2. Partition Leader 选举
3. ISR 管理
4. 配置变更
```

### 2.2 Go 实现 Controller 选举

```go
package kafka

import (
    "time"
)

type Controller struct {
    brokers      map[string]*Broker
    controllerId int
    epoch        int
    zkClient     *ZKClient
}

type Broker struct {
    Id       int
    Host     string
    Port     int
    IsLeader bool
}

func (c *Controller) ElectController() error {
    // 1. 在 ZooKeeper 创建临时节点
    zkPath := "/controller"
    data := fmt.Sprintf(`{"version":1,"broker":%d,"timestamp":"%d"}`,
        c.controllerId, time.Now().Unix()*1000)
    
    err := c.zkClient.createEphemeral(zkPath, data)
    if err != nil {
        return err
    }
    
    // 2. 监听 Controller 变更
    c.zkClient.watch(zkPath, func(event zk.Event) {
        if event.Type == zk.EventNodeDeleted {
            // Controller 失效，重新选举
            c.tryElect()
        }
    })
    
    return nil
}

func (c *Controller) tryElect() {
    // 1. 获取所有 Broker 列表
    brokers, err := c.zkClient.getChildren("/brokers/ids")
    if err != nil {
        return
    }
    
    // 2. 选择最低 ID 的 Broker 作为 Controller
    minId := -1
    for _, broker := range c.brokers {
        if broker.Id < minId || minId == -1 {
            minId = broker.Id
        }
    }
    
    c.controllerId = minId
    c.ElectController()
}
```

### 2.3 Leader Election

```go
type PartitionManager struct {
    controller *Controller
    isr        map[string][]string // partition → ISR
}

func (pm *PartitionManager) ElectLeader(partition string) error {
    isr := pm.isr[partition]
    if len(isr) == 0 {
        return fmt.Errorf("no ISR for partition %s", partition)
    }
    
    // 选择 ISR 中第一个 Broker 作为 Leader
    leader := isr[0]
    
    // 更新 ZooKeeper
    zkPath := fmt.Sprintf("/brokers/topics/%s/partitions/%s/state",
        pm.topic, partition)
    data := fmt.Sprintf(`{"version":1,"partition":%d,"leader":%d,"leader_epoch":%d}`,
        partition, leader, pm.epoch)
    
    err := pm.controller.zkClient.setData(zkPath, data)
    if err != nil {
        return err
    }
    
    return nil
}
```

---

## 第三部分：Consumer Group 协调

### 3.1 Consumer Group 架构

```
Consumer Group:
├── Consumer 0 → Partition 0, 1
├── Consumer 1 → Partition 2, 3
└── Consumer 2 → Partition 4, 5

Group Coordinator 负责：
1. 成员管理
2. Rebalance
3. Offset 管理
```

### 3.2 Go 实现 Consumer Group

```go
type ConsumerGroup struct {
    groupId    string
    members    map[string]*Consumer
    partitions []int
    coordinator *GroupCoordinator
}

type Consumer struct {
    id        string
    host      string
    assigned  []int
    committed map[int]int64 // partition → offset
}

func (cg *ConsumerGroup) Join(consumer *Consumer) error {
    // 1. 添加消费者到组
    cg.members[consumer.id] = consumer
    
    // 2. 触发 Rebalance
    err := cg.rebalance()
    if err != nil {
        return err
    }
    
    return nil
}

func (cg *ConsumerGroup) Leave(consumerId string) error {
    delete(cg.members, consumerId)
    return cg.rebalance()
}
```

### 3.3 Rebalance 策略

```go
type Rebalancer interface {
    Assign(members map[string]*Consumer, partitions []int) map[string][]int
}

type RangeRebalancer struct{}

func (r *RangeRebalancer) Assign(members map[string]*Consumer, partitions []int) map[string][]int {
    assignments := make(map[string][]int)
    
    // 1. 排序
    memberIds := make([]string, 0, len(members))
    for id := range members {
        memberIds = append(memberIds, id)
    }
    sort.Strings(memberIds)
    
    sort.Ints(partitions)
    
    // 2. 范围分配
    nMembers := len(members)
    nPartitions := len(partitions)
    
    for i, memberId := range memberIds {
        start := i * nPartitions / nMembers
        end := (i + 1) * nPartitions / nMembers
        assignments[memberId] = partitions[start:end]
    }
    
    return assignments
}

type RoundRobinRebalancer struct{}

func (r *RoundRobinRebalancer) Assign(members map[string]*Consumer, partitions []int) map[string][]int {
    assignments := make(map[string][]int)
    
    memberIds := make([]string, 0, len(members))
    for id := range members {
        memberIds = append(memberIds, id)
    }
    sort.Strings(memberIds)
    
    for i, partition := range partitions {
        memberId := memberIds[i%len(memberIds)]
        assignments[memberId] = append(assignments[memberId], partition)
    }
    
    return assignments
}
```

---

## 第四部分：事务消息

### 4.1 事务 API

```go
type TransactionalProducer struct {
    producer   *Producer
    txnId      string
    inTransaction bool
}

func (tp *TransactionalProducer) BeginTransaction() error {
    if tp.inTransaction {
        return fmt.Errorf("already in transaction")
    }
    
    // 初始化事务
    err := tp.producer.initTransactions()
    if err != nil {
        return err
    }
    
    // 开始事务
    err = tp.producer.beginTransaction()
    if err != nil {
        return err
    }
    
    tp.inTransaction = true
    return nil
}

func (tp *TransactionalProducer) CommitTransaction() error {
    if !tp.inTransaction {
        return fmt.Errorf("not in transaction")
    }
    
    // 提交事务
    err := tp.producer.commitTransaction()
    if err != nil {
        return err
    }
    
    tp.inTransaction = false
    return nil
}

func (tp *TransactionalProducer) AbortTransaction() error {
    if !tp.inTransaction {
        return fmt.Errorf("not in transaction")
    }
    
    // 中止事务
    err := tp.producer.abortTransaction()
    if err != nil {
        return err
    }
    
    tp.inTransaction = false
    return nil
}
```

### 4.2 Exactly-Once 语义

```go
type ExactlyOnceProcessor struct {
    producer   *TransactionalProducer
    consumer   *Consumer
    txnId      string
}

func (eop *ExactlyOnceProcessor) Process() error {
    // 1. 开启事务
    err := eop.producer.BeginTransaction()
    if err != nil {
        return err
    }
    
    // 2. 消费消息
    messages := eop.consumer.poll()
    
    // 3. 处理消息
    for _, msg := range messages {
        result := eop.processMessage(msg)
        
        // 4. 写入结果
        err := eop.producer.send(result.Topic, result.Key, result.Value)
        if err != nil {
            eop.producer.AbortTransaction()
            return err
        }
    }
    
    // 5. 提交事务
    err = eop.producer.CommitTransaction()
    if err != nil {
        return err
    }
    
    return nil
}
```

---

## 第五部分：自测题

### 问题 1
Kafka 为什么选择顺序写磁盘而不是随机写？

<details>
<summary>查看答案</summary>

1. **顺序写更快**：磁盘顺序写带宽远高于随机写
2. **文件系统缓存**：利用 OS Page Cache
3. **零拷贝优化**：sendfile 系统调用
4. **批量发送**：Producer 批量写入减少 IO 次数
5. **SSD 优势**：SSD 顺序写优势不如 HDD 明显

</details>

### 问题 2
Consumer Group Rebalance 什么时候触发？

<details>