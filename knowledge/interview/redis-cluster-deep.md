# Redis集群架构 - 资深专家深度实现

## 一、Cluster架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Redis Cluster架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │  Master 0   │    │  Master 1   │    │  Master 2   │               │
│   │  (slots 0-5460)◄────────────────────────────────►(slots 10923-16383)│
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│          │                  │                  │                       │
│   ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐               │
│   │  Slave 0    │    │  Slave 1    │    │  Slave 2    │               │
│   └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                         │
│   槽位数量: 16384                                                       │
│   节点通信: Gossip协议                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Go客户端实现

```go
package rediscluster

import (
    "hash/crc16"
    "sync"
)

type ClusterClient struct {
    nodes     []*Node
    slots     [16384]*Node
    mu        sync.RWMutex
}

type Node struct {
    addr     string
    master   bool
    replicas []string
}

// 计算slot
func (c *ClusterClient) getSlot(key string) int {
    return int(crc16.Checksum([]byte(key), crc16.MakeTable(crc16.ECMAC)) & 16383)
}

// 获取节点
func (c *ClusterClient) getNode(key string) *Node {
    slot := c.getSlot(key)
    return c.slots[slot]
}

// 重定向
func (c *ClusterClient) redirectIfNeeded(err error, key string) (*Node, error) {
    // MOVED slot node:port
    // ASK slot node:port
    // ...
    return nil, nil
}
```

## 三、故障转移

```go
package failover

import (
    "time"
)

type FailoverManager struct {
    cluster *Cluster
}

func (f *FailoverManager) detectFailure(node *Node) {
    // 连续3次ping失败认为宕机
    for i := 0; i < 3; i++ {
        if !f.ping(node) {
            time.Sleep(100 * time.Millisecond)
        }
    }
    
    // 触发故障转移
    f.triggerFailover(node)
}

func (f *FailoverManager) triggerFailover(failedNode *Node) {
    // 1. 选择一个从节点提升为主节点
    replica := f.selectReplica(failedNode)
    
    // 2. 执行SLAVEOF NO ONE
    replica.execute("SLAVEOF NO ONE")
    
    // 3. 其他节点更新槽位映射
    f.updateSlotMapping(replica, failedNode.slots)
    
    // 4. 同步数据
    f.syncData(replica, failedNode)
}
```

## 四、面试高频题

### Q1: Redis Cluster如何解决数据一致性？

```
A:
• 主从复制（异步）
• 哨兵机制
• 客户端重试
```

### Q2: 如何处理热点key？

```
A:
1. 本地缓存
2. 多级缓存
3. 读写分离
```

## 五、自测题

1. 解释Redis Cluster架构
2. 如何实现故障转移？
3. 如何处理数据迁移？

---

## 参考文档

- [Redis官方文档](https://redis.io/docs/)
- [Redis Cluster规范](https://redis.io/docs/refs/spec/cluster-spec/)
