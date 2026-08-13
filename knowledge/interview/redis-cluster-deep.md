# Redis集群架构深度实现 --- 资深专家深度实现

## 概述

Redis Cluster是Redis的分布式解决方案，提供自动分片和故障转移。本文深入剖析其架构原理和生产实践。

## 一、集群架构

### 1.1 节点拓扑

```
┌─────────────────────────────────────────────────────────┐
│                   Redis Cluster架构                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐        │
│   │ Master1 │◄────►│ Master2 │◄────►│ Master3 │        │
│   │  (Slot  │      │  (Slot  │      │  (Slot  │        │
│   │   0-5460│      │ 5461-  │      │10923-16│        │
│   │   )     │      │ 10922)  │      │ 383)   │        │
│   └────┬────┘      └────┬────┘      └────┬────┘        │
│        │                │                │              │
│   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐        │
│   │  Slave  │      │  Slave  │      │  Slave  │        │
│   │  (Replica)│    │ (Replica)│    │ (Replica)│        │
│   └─────────┘      └─────────┘      └─────────┘        │
│                                                          │
│   16384个槽位 (Slots)                                    │
└─────────────────────────────────────────────────────────┘
```

### 1.2 槽位分配

```go
// 槽位计算
const TotalSlots = 16384

func GetSlot(key string) int {
    // CRC16算法
    crc := crc16.Checksum([]byte(key), crc16.MakeTable(crc16.ISO))
    return int(crc % TotalSlots)
}

// 槽位到节点的映射
type SlotMap struct {
    slots [TotalSlots]NodeID
}
```

## 二、通信协议

### 2.1 Gossip协议

```go
// Gossip协议：节点间定期交换信息
type GossipMessage struct {
    MsgType    string    // ping, pong, meet, fail
    SourceNode string    // 发送者
    TargetNode string    // 接收者
    ConfigEpoch uint64   // 配置版本
    Slots      []SlotRange // 槽位范围
}

// 定期发送Ping
func (n *Node) gossipLoop() {
    ticker := time.NewTicker(gossipInterval)
    for range ticker.C {
        target := n.selectTarget()
        msg := n.buildPing()
        n.sendTo(target, msg)
    }
}
```

### 2.2 消息类型

```
┌─────────────────────────────────────────────────────────┐
│                  Gossip消息类型                          │
├─────────────────────────────────────────────────────────┤
│  PING:      节点间探测心跳                              │
│  PONG:      PING的响应                                  │
│  MEET:      邀请新节点加入集群                           │
│  FAIL:      标记节点宕机                                │
│  UPDATE:    节点配置更新                                │
│  CLUSTER_OK: 集群健康状态                               │
└─────────────────────────────────────────────────────────┘
```

## 三、故障转移

### 3.1 主从切换流程

```go
// 故障转移流程
func (slave *Node) failover() error {
    // 1. 标记自己为候选主节点
    slave.configEpoch++
    slave.updateState(FAILOVER_CHANGE)
    
    // 2. 获取其他节点投票
    votes := 1
    required := clusterSize/2 + 1
    for votes < required {
        vote := slave.requestVote()
        if vote {
            votes++
        }
    }
    
    // 3. 提升为主节点
    slave.promoteToMaster()
    
    // 4. 接管槽位
    slave.slaveof(nil, nil)
    
    // 5. 广播新配置
    cluster.broadcastConfig()
    
    return nil
}
```

### 3.2 故障检测

```go
// 节点故障检测
func (n *Node) checkNodeHealth(node *Node) bool {
    // 1. 发送Ping
    start := time.Now()
    err := n.sendPing(node)
    elapsed := time.Since(start)
    
    // 2. 检查超时
    if elapsed > clusterNodeTimeout {
        n.markAsFail(node)
        return false
    }
    
    // 3. 检查响应
    if err != nil {
        n.markAsFail(node)
        return false
    }
    
    return true
}
```

## 四、生产实践

### 4.1 配置优化

```conf
# redis-cluster.conf
port 7000
cluster-enabled yes
cluster-config-file nodes.conf
cluster-node-timeout 5000
cluster-slave-validity-factor 10
cluster-migration-barrier 1
cluster-require-full-coverage yes

# 性能优化
tcp-keepalive 60
timeout 0
```

### 4.2 监控指标

```go
// 关键监控指标
type ClusterMetrics struct {
    ConnectedClients   int      // 连接客户端数
    UsedMemory         int64    // 内存使用
    KeyspaceHits       int64    // 缓存命中
    KeyspaceMisses     int64    // 缓存未命中
    ClusterSize        int      // 集群节点数
    ClusterSlotsOK     int      // 正常槽位数
    ClusterSlotsPfail  int      // 疑似失败槽位
    ClusterSlotsFail   int      // 已失败槽位
}
```

### 4.3 备份恢复

```bash
# 备份所有节点
for port in 7000 7001 7002 7003 7004 7005; do
    redis-cli -p $port BGSAVE
done

# 恢复集群
redis-cli --cluster fix 127.0.0.1:7000

# 重新平衡槽位
redis-cli --cluster rebalance 127.0.0.1:7000
```

## 五、面试高频题

### 5.1 高频问题

**Q1: Redis Cluster为什么是16384个槽位？**

A: 16384 = 2^14，便于位运算，槽位数足够分配且不过大。

**Q2: 故障转移是如何实现的？**

A: 通过Gossip协议检测故障，Slave申请投票提升为主节点，接管故障主节点的槽位。

**Q3: 如何处理跨节点操作？**

A: 客户端需要重定向，或代理层处理多步操作。

### 5.2 自测题

1. 画出Redis Cluster架构图
2. 解释Gossip协议的工作原理
3. 设计一个高可用集群方案
4. 分析槽位迁移的过程
5. 解释Cluster模式与哨兵模式的区别

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 缓存
**关键词**: redis, cluster, gossip, failover, partition
