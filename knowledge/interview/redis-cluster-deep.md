# Redis集群架构 - 资深专家深度实现

## 一、Cluster模式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Redis Cluster架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                         │
│   │ Node 0   │    │ Node 1   │    │ Node 2   │                         │
│   │(Master)  │◄──►│(Master)  │◄──►│(Master)  │                         │
│   │  Slots   │    │  Slots   │    │  Slots   │                         │
│   │  0-5460  │    │  5461-   │    │  10923-  │                         │
│   │          │    │  10922   │    │  16383   │                         │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘                         │
│        │               │               │                               │
│   ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐                         │
│   │ Replica  │    │ Replica  │    │ Replica  │                         │
│   │  Node 3  │    │  Node 4  │    │  Node 5  │                         │
│   └──────────┘    └──────────┘    └──────────┘                         │
│                                                                         │
│   • 16384个哈希槽                                                        │
│   • Gossip协议节点通信                                                   │
│   • 自动故障转移                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、数据分片

```go
package cluster

import "hash/crc32"

type Slot struct {
    Start int
    End   int
    Node  string
}

func GetSlot(key string) int {
    // CRC16哈希算法
    c := crc32.ChecksumIEEE([]byte(key))
    return int(c % 16384)
}

func GetNode(slot int) string {
    // 根据槽位获取节点
    for _, s := range slots {
        if slot >= s.Start && slot <= s.End {
            return s.Node
        }
    }
    return ""
}
```

## 三、故障转移

```go
package failover

// Redis Cluster故障转移流程
type Failover struct {
    master *Node
    replica *Node
}

func (f *Failover) Execute() error {
    // 1. Replica发起故障转移
    f.replica.clusterSaveConfig()
    f.replica.clusterSetSlotMissing(slot)
    
    // 2. 选举成为新Master
    f.replica.clusterFailoverReplaceSlots()
    
    // 3. 通知其他节点
    f.replica.broadcastFailoverAnnounce()
    
    // 4. 旧Master降级为Replica
    f.master.clusterSetSlave(f.replica)
    
    return nil
}
```

## 四、面试高频题

### Q1: Redis Cluster如何分片？

```
A:
1. CRC16哈希算法
2. 16384个槽位
3. 槽位映射到节点
```

### Q2: 如何实现高可用？

```
A:
1. 主从复制
2. 自动故障转移
3. Gossip协议
```

## 五、自测题

1. 解释Cluster分片原理
2. 如何实现故障转移？
3. 如何处理跨Slot事务？

---

## 参考文档

- [Redis Cluster规范](https://redis.io/docs/reference/cluster-spec/)
- [Redis源码](https://github.com/redis/redis)
