---

## 2. 源码级深度 - 集群协议与通信

### 2.1 CRC16 算法实现

Redis Cluster 使用 CRC16 算法对 key 进行哈希，决定 key 落入哪个槽位。

**C 源码 (`crc16.c`)**:
```c
/* CRC-16 algorithm (CCITT variant) */
static const unsigned short crc16tab[256] = {
    0x0000, 0x1021, 0x2042, 0x3063, ...
};

unsigned int crc16(const char *buf, int len) {
    unsigned short crc = 0;
    while (len--) {
        crc = (crc << 8) ^ crc16tab[((crc >> 8) ^ *buf++) & 0xff];
    }
    return crc;
}
```

**Go 等效实现**:
```go
package redis_cluster

// CRC16 实现 Redis 使用的 CRC-16-CCITT 算法
// 与 C 版本完全等价，用于确定 key 的 hash slot
var crc16Table [256]uint16

func init() {
	for i := uint16(0); i < 256; i++ {
		crc := uint16(0)
		for j := uint8(0); j < 8; j++ {
			if (i>>j)&1 == 1 {
				crc ^= 0x8408 // 生成多项式 x^16+x^12+x^5+1
			}
			if crc&1 != 0 {
				crc = (crc >> 1) ^ 0xA001
			} else {
				crc >>= 1
			}
		}
		crc16Table[i] = crc
	}
}

// HashSlot 计算 key 的 hash slot
func HashSlot(key string) int {
	crc := uint16(0)
	for i := 0; i < len(key); i++ {
		b := key[i]
		crc = (crc << 8) ^ crc16Table[(crc>>8)^b]
	}
	return int(crc % 16384)
}

// Test: CRC16("foo") = 5161
func ExampleCRC16() {
	fmt.Println(HashSlot("foo")) // 5161
	fmt.Println(HashSlot("user:1001"))
}
```

### 2.2 槽位分配与管理

Redis Cluster 将 16384 个槽位动态分配给各 master 节点。

**数据结构 (`cluster.h`)**:
```c
/* 槽位映射表 */
typedef struct clusterState {
    clusterNode *myself;          /* 当前节点 */
    clusterNode *slots[16384];    /* slot -> node 映射 */
    clusterNode *nodes;           /* 所有节点链表 */
    mstime_t slots_migration_barrier; /* 迁移屏障时间 */
    uint64_t configEpoch;         /* 配置纪元 */
    clusterLink *link;            /* 到任意节点的 TCP 连接 */
} clusterState;

/* 节点状态 */
#define NODE_MASTER     1
#define NODE_SLAVE      2
#define NODE_PFAIL      4   /* 疑似失败 */
#define NODE_FAIL       8   /* 确认失败 */
#define NODE_MEET      16   /* 待握手 */
#define NODE_CLUSTER   32   /* 集群模式 */
```

**槽位重新分片流程**:

```
阶段1: 从源节点迁移槽位
  CLUSTER SETSLOT <slot> MIGRATING <source-node-id>
  → 源节点开始接受该槽位的写入

阶段2: 在目标节点绑定槽位
  CLUSTER SETSLOT <slot> IMPORTING <target-node-id>
  → 目标节点准备接收

阶段3: 迁移数据
  MIGRATE host port key 0 ttl [COPY | REPLACE]
  → 逐个 key 迁移

阶段4: 完成槽位分配
  CLUSTER SETSLOT <slot> NODE <target-node-id>
  → 槽位正式归属目标节点
```

### 2.3 Gossip 协议详解

Redis Cluster 使用改良版 Gossip 协议同步集群状态。

**Gossip 消息类型**:
```
┌──────────────────────────────────────────────┐
│              Gossip Message Header             │
├──────────────────────────────────────────────┤
│  Type: MEET/PONG/FAIL/PING/META/PING+META     │
│  Version: 协议版本                            │
│  Timestamp: 消息时间戳                         │
│  ConfigEpoch: 配置纪元                         │
│  Sender: 发送者 node-id                        │
│  Count: 后续节点条目数量                        │
│  ───────────────────────────────────────────  │
│  Node Entry[n]:                                │
│    flags, node-id, ping-sent, pong-received,  │
│    ip, port, config-epoch, link-state,         │
│    slot-count, slots[]                         │
└──────────────────────────────────────────────┘
```

**PING 消息处理流程**:
```c
// server.c - 接收 PING 消息
void clusterHandleMessage(void *buf, int len) {
    clusterMsg *msg = (clusterMsg*)buf;
    
    switch(msg->type) {
        case CLUSTERMSG_TYPE_PING:
            // 处理 PING: 更新节点状态、同步槽位信息
            clusterProcessPing(msg);
            // 回复 PONG
            clusterSendPing(link, CLUSTERMSG_TYPE_PONG);
            break;
            
        case CLUSTERMSG_TYPE_PONG:
            // PONG 确认了之前的 PING
            clusterProcessPong(msg);
            break;
            
        case CLUSTERMSG_TYPE_FAIL:
            // 节点标记为 FAIL
            clusterProcessFail(msg->data.ping.node.name);
            break;
            
        case CLUSTERMSG_TYPE_MEET:
            // 新节点加入，发起握手
            clusterSendMeet(msg);
            break;
    }
}
```

**Gossip 周期**:
- 每个节点每秒发送 10 次 PING (每 100ms)
- PING 消息携带 1/10 的已知节点列表
- 最终所有节点看到一致的集群视图

### 2.4 客户端 -MOVED/-ASK 重定向

当客户端请求到达错误的节点时，服务器返回重定向错误：

```
-MOVED <slot> <host:port>   → 永久重定向 (槽位已迁移)
-ASK <slot> <host:port>     → 临时重定向 (迁移中)
```

**Go 客户端自动处理**:
```go
package redis_cluster

import (
	"context"
	"fmt"
	"github.com/redis/go-redis/v9"
)

// 演示 MOVED/ASK 重定向的处理
func RedirectDemo(rdb *redis.ClusterClient, ctx context.Context) {
	// go-redis 自动处理 MOVED/ASK 重定向
	// 你不需要手动解析错误
	
	// 假设 key "foo" 现在在另一个节点上
	err := rdb.Set(ctx, "foo", "bar", 0).Err()
	if err != nil {
		// go-redis 内部已经重试过了
		fmt.Printf("final error: %v\n", err)
	}
	
	// 查看内部重定向统计
	stats := rdb.PoolStats()
	fmt.Printf("connections: in-use=%d total=%d\n", 
		stats.InUse, stats.Total)
}
```

### 2.5 一致性模型

Redis Cluster 提供**最终一致性**，而非强一致性：

| 特性 | 说明 |
|-----|------|
| 同步复制 | 主从之间是异步复制 |
| 写传播 | 写入主节点即返回成功 |
| 故障转移 | 哨兵触发时可能丢失未同步的数据 |
| 跨槽操作 | 不支持 MULTI/EXEC 跨多个槽 |
| 键空间 | 不支持 KEYS、FLUSHALL 等全局操作 |

```go
// 注意：Cluster 模式下不能跨槽位使用 MULTI
// 以下代码会报错: CROSSSLOT Keys in request don't hash to the same slot
func CrossSlotError(rdb *redis.ClusterClient, ctx context.Context) {
	_, err := rdb.Watch(ctx, func(tx *redis.Tx) error {
		// user:1001 和 user:2002 可能在不同的 master 节点
		_, err := tx.Get(ctx, "user:1001").Result()
		if err != nil {
			return err
		}
		_, err = tx.Get(ctx, "user:2002").Result()
		return err
	}, "user:1001", "user:2002")
	// err = CROSSSLOT error
	fmt.Println("CROSSSLOT:", err)
}
```
