# Redis 集群生产实践深度实现 - 从原理到排障

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/Redis  
> **代码密度**: 30%

---

## 一、Redis Cluster 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Redis Cluster 架构                                │
│                                                                     │
│                    ┌─────────────┐                                  │
│                    │   Client    │                                  │
│                    └──────┬──────┘                                  │
│                           │                                        │
│              ┌────────────┼────────────┐                          │
│              ▼            ▼            ▼                          │
│     ┌───────────┐ ┌───────────┐ ┌───────────┐                    │
│     │ Node 0    │ │ Node 1    │ │ Node 2    │    ...              │
│     │ (Master)  │ │ (Master)  │ │ (Master)  │                    │
│     ├───────────┤ ├───────────┤ ├───────────┤                    │
│     │ Slave     │ │ Slave     │ │ Slave     │                    │
│     └───────────┘ └───────────┘ └───────────┘                    │
│                                                                     │
│  16384 个哈希槽 (hash slot)                                         │
│  • 每个 key → CRC16(key) mod 16384 → 槽位                          │
│  • 每个 Master 负责一部分槽位                                       │
│  • 故障转移:  slave → master 自动晋升                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go Redis 客户端

```go
// redis/client.go
package redis

import (
    "context"
    "github.com/redis/go-redis/v9"
    "time"
)

// RedisCluster Redis 集群客户端
type RedisCluster struct {
    rdb *redis.ClusterClient
}

// NewRedisCluster 创建集群客户端
func NewRedisCluster(nodes []string, password string) *RedisCluster {
    rdb := redis.NewClusterClient(&redis.ClusterOptions{
        Addrs:        nodes,
        Password:     password,
        MaxRetries:   3,
        PoolSize:     50,
        MinIdleConns: 10,
        PoolTimeout:  5 * time.Second,
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,
        DialTimeout:  5 * time.Second,
    })
    return &RedisCluster{rdb: rdb}
}

// Get 获取值
func (r *RedisCluster) Get(ctx context.Context, key string) (string, error) {
    return r.rdb.Get(ctx, key).Result()
}

// Set 设置值
func (r *RedisCluster) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
    return r.rdb.Set(ctx, key, value, ttl).Err()
}

// Del 删除
func (r *RedisCluster) Del(ctx context.Context, keys ...string) error {
    return r.rdb.Del(ctx, keys...).Err()
}

// Pipeline 管道操作
func (r *RedisCluster) Pipeline(ctx context.Context, fn func(redis.Pipeliner) error) ([]redis.Cmder, error) {
    pipe := r.rdb.Pipeline()
    if err := fn(pipe); err != nil {
        return nil, err
    }
    return pipe.Exec(ctx)
}

// Eval 执行 Lua 脚本
func (r *RedisCluster) Eval(ctx context.Context, script string, keys []string, args ...interface{}) interface{} {
    return r.rdb.Eval(ctx, script, keys, args...).Val()
}
```

---

## 三、Lua 原子操作

```go
// redis/lua_scripts.go
package redis

// INCR_IF_EXISTS 如果 key 存在则自增
const IncrIfExistsScript = `
if redis.call('EXISTS', KEYS[1]) == 1 then
    return redis.call('INCR', KEYS[1])
else
    return 0
end
`

// SET_IF_NOT_EXISTS 不存在则设置
const SetNXScript = `
if redis.call('EXISTS', KEYS[1]) == 0 then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', tonumber(ARGV[2]))
    return 1
else
    return 0
end
`

// DEL_IF_VALUE 条件删除
const DelIfValueScript = `
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
`
```

---

## 四、哨兵模式

```go
// redis/sentinel.go
package redis

import (
    "github.com/redis/go-redis/v9"
)

// SentinelClient 哨兵客户端
type SentinelClient struct {
    rdb *redis.Client
}

// NewSentinelClient 创建哨兵客户端
func NewSentinelClient(masterName string, sentinels []string) *SentinelClient {
    rdb := redis.NewClient(&redis.Options{
        MasterName:    masterName,
        SentinelAddrs: sentinels,
    })
    return &SentinelClient{rdb: rdb}
}

// Get 通过哨兵获取主节点
func (s *SentinelClient) Get(ctx context.Context, key string) (string, error) {
    return s.rdb.Get(ctx, key).Result()
}
```

---

## 五、生产排障

| 问题 | 现象 | 排查命令 | 解决方案 |
|------|------|---------|---------|
| OOM | 写入失败 | `INFO memory` | 增加 maxmemory，设置淘汰策略 |
| 慢查询 | 延迟飙升 | `SLOWLOG GET 10` | 优化命令，添加索引 |
| 主从延迟 | 数据不一致 | `INFO replication` | 检查网络，减少写压力 |
| 连接数满 | 无法连接 | `INFO clients` | 增加 maxclients，连接池复用 |
| 热点 Key | 单节点负载高 | `KEYS *` 扫描 | 本地缓存，key 分散 |

---

## 六、自测题

1. **Redis Cluster 的 16384 槽位是什么？**
   - 哈希槽，用于数据分片

2. **哨兵模式如何故障转移？**
   - 投票机制，多数派判定主节点宕机后推举新主

3. **如何解决热点 Key 问题？**
   - 本地缓存 + 读写分离 + key 重命名分散

