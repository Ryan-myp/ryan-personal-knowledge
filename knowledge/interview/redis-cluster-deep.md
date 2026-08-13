# Redis Cluster架构 - 资深专家深度实现

## 一、集群架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Redis Cluster架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌───────────┐                                   │
│                         │  Client   │                                   │
│                         └─────┬─────┘                                   │
│                               │                                         │
│              ┌────────────────┼────────────────┐                        │
│              │                │                │                        │
│              ▼                ▼                ▼                        │
│      ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│      │   Master    │  │   Master    │  │   Master    │                 │
│      │   (Node 0)  │  │   (Node 1)  │  │   (Node 2)  │                 │
│      └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│             │               │               │                           │
│     ┌───────┴───────┐ ┌─────┴─────┐ ┌───────┴───────┐                   │
│     │    Slave      │ │  Slave    │ │    Slave      │                   │
│     │   (Node 0)    │ │ (Node 1)  │ │   (Node 2)    │                   │
│     └───────────────┘ └───────────┘ └───────────────┘                   │
│                                                                         │
│  特点:                                                                   │
│  • 16384个哈希槽                                                       │
│  • 主从复制                                                             │
│  • 故障自动转移                                                         │
│  • 客户端分片                                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、数据分片

```go
package rediscluster

import (
    "hash/crc32"
    "sort"
)

type Node struct {
    ID       string
    Address  string
    Slots    []int
}

type Cluster struct {
    nodes []*Node
    slots [16384]*Node
}

func (c *Cluster) GetNode(key string) *Node {
    slot := c.getSlot(key)
    return c.slots[slot]
}

func (c *Cluster) getSlot(key string) int {
    // CRC32 hash to slot
    checksum := crc32.ChecksumIEEE([]byte(key))
    return int(checksum % 16384)
}
```

## 三、故障转移

```
故障转移流程:
1. Master失败检测 (Gossip协议)
2. Slave选举新的Master
3. 复制数据
4. 更新集群状态
5. 通知客户端
```

## 四、面试高频题

### Q1: Redis Cluster如何分片？

```
A:
1. 16384个哈希槽
2. CRC32哈希计算
3. 数据均匀分布
```

### Q2: 如何实现故障转移？

```
A:
1. 主从复制
2. 选举机制
3. 状态同步
```

## 五、自测题

1. 解释哈希槽原理
2. 如何实现高可用？
3. 如何扩容缩容？

---

## 参考文档

- [Redis Cluster规范](https://redis.io/docs/reference/cluster-spec/)
- [Redis源码](https://github.com/redis/redis)
