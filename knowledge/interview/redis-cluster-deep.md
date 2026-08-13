# Redis Cluster架构 - 资深专家深度实现

## 一、集群原理

### 1.1 哈希槽分配

```
Redis Cluster使用16384个哈希槽:
- 每个Key通过CRC16计算映射到0-16383
- 每个节点负责一部分槽位
- 槽位可以在节点间迁移

示例:
Node A: 0-5460
Node B: 5461-10922
Node C: 10923-16383
```

### 1.2 Go Cluster客户端

```go
package rediscluster

import (
	"context"
	"github.com/go-redis/redis/v8"
)

func NewClusterClient(nodes []string) *redis.ClusterClient {
	rdb := redis.NewClusterClient(&redis.ClusterOptions{
		Addrs: nodes,
		MaxRetries: 3,
	})
	return rdb
}

func (c *ClusterClient) Get(key string) (string, error) {
	return c.rdb.Get(context.Background(), key).Result()
}

func (c *ClusterClient) Set(key, value string, ttl time.Duration) error {
	return c.rdb.Set(context.Background(), key, value, ttl).Err()
}
```

## 二、数据分片

### 2.1 分片策略

```
一致性哈希:
- 虚拟节点解决数据倾斜
- 节点增减时影响最小化

Ring结构:
┌────────────────────────────────────────┐
│  0 ────── 4369 ────── 8738 ────── 16383 │
│   Node A    Node B      Node C         │
└────────────────────────────────────────┘
```

### 2.2 槽位迁移

```bash
# 手动迁移槽位
redis-cli -c cluster setslot 5000 migrating <node-id>
redis-cli -c cluster getkeysinslot 5000 100

# 自动迁移 (cluster- migrate)
redis-trib.rb reshard <host>:<port>
```

## 三、高可用

### 3.1 主从复制

```
主节点: 处理读写请求
从节点: 故障转移，数据备份

故障转移流程:
1. 主节点不可达
2. 从节点选举新主
3. 客户端重定向
```

### 3.2 哨兵模式

```yaml
# sentinel.conf
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
```

## 四、常见问题

### 4.1 跨节点事务

```
Redis Cluster不支持跨节点事务:
- 多Key操作必须在同一节点
- 使用KEYS标签指定节点
```

### 4.2 热点Key

```go
package hotkey

import (
	"sync"
	"time"
)

type HotKeyProtection struct {
	localCache sync.Map
	ttl        time.Duration
}

func (h *HotKeyProtection) Get(key string) (interface{}, error) {
	// 本地缓存优先
	if v, ok := h.localCache.Load(key); ok {
		return v, nil
	}
	
	// 远程Redis
	v, err := h.remoteGet(key)
	if err != nil {
		return nil, err
	}
	
	// 写入本地缓存
	h.localCache.Store(key, v)
	return v, nil
}
```

## 五、面试高频题

### Q1: Cluster和Sentinel有什么区别？

```
A:
Cluster: 数据分片，水平扩展
Sentinel: 高可用，主从切换
```

### Q2: 如何扩容Cluster？

```
A:
1. 添加新节点
2. 迁移槽位
3. 平衡数据
```

## 六、自测题

1. 解释Redis Cluster的数据分片机制
2. 如何实现热点Key保护？

---

## 参考文档

- [Redis Cluster规范](https://redis.io/docs/reference/cluster-spec/)
