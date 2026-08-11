# Redis 缓存架构深度解析

> 深入 Redis 缓存架构：集群模式、持久化、内存管理、高可用。
> 包含生产环境调优和故障排查。
> 适用对象：后端工程师、DBA、系统架构师

---

## 1. Redis 集群架构

### 1.1 集群模式对比

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis 集群模式                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  主从复制 (Master-Slave)                                     │
│  ──────────────────────────                                  │
│  ├── 单主多从架构                                            │
│  ├── 读写分离                                                │
│  └── 故障自动转移 (Redis Sentinel)                           │
│                                                             │
│  Redis Cluster (官方集群)                                    │
│  ──────────────────────────                                  │
│  ├── 去中心化架构                                            │
│  ├── 16384 个哈希槽                                          │
│  ├── 支持水平扩展                                            │
│  └── 数据自动分片                                            │
│                                                             │
│  Codis (第三方集群)                                          │
│  ──────────────────────────                                  │
│  ├── proxy 架构                                              │
│  ├── 支持动态扩容                                            │
│  └── 兼容 redis-cli                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Redis Cluster 架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Redis Cluster 架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌──────────┐                             │
│                    │ Master 0 │                             │
│                    └────┬─────┘                             │
│                         │                                   │
│          ┌──────────────┼──────────────┐                    │
│          ▼              ▼              ▼                    │
│    ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│    │ Slave 0  │   │ Master 1 │   │ Slave 1  │              │
│    └──────────┘   └────┬─────┘   └────┬─────┘              │
│                        │              │                     │
│          ┌─────────────┼──────────────┘                     │
│          ▼              ▼                                    │
│    ┌──────────┐   ┌──────────┐                              │
│    │ Master 2 │   │ Slave 2  │                              │
│    └──────────┘   └──────────┘                              │
│                                                             │
│  哈希槽：0-16383                                             │
│  每个 Master 负责一部分槽位                                  │
│  故障自动故障转移                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 持久化机制

### 2.1 RDB 快照

```
RDB 生成过程：

1. 客户端发送 BGSAVE 命令
2. 主进程 fork 子进程
3. 子进程写入临时 RDB 文件
4. 子进程完成后替换旧 RDB 文件

优点：
- 文件紧凑，适合备份
- 恢复速度快

缺点：
- 可能丢失最后一次快照后的数据
- fork 时内存拷贝开销大
```

### 2.2 AOF 追加

```c
// aof.c (简化)

typedef struct {
    char *buf;           // 缓冲区
    size_t buf_len;      // 缓冲区长度
    int fd;              // 文件描述符
    long long written;   // 已写入字节数
    int dirty;           // 是否有未同步数据
} aofState;

// AOF 重写
int rewriteAppendOnlyFile(char *filename) {
    // 1. 创建临时文件
    // 2. 遍历内存数据
    // 3. 生成 AOF 命令
    // 4. 原子替换
}
```

### 2.3 混合持久化

```conf
# redis.conf

# 开启 AOF
appendonly yes

# 混合持久化（Redis 4.0+）
aof-use-rdb-preamble yes

# AOF 重写策略
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB 持久化
save 900 1
save 300 10
save 60 10000
```

---

## 3. 内存管理

### 3.1 内存淘汰策略

```conf
# maxmemory-policy 配置

# 1. noeviction - 不淘汰，返回错误
maxmemory-policy noeviction

# 2. allkeys-lru - 所有键 LRU 淘汰
maxmemory-policy allkeys-lru

# 3. volatile-lru - 有过期时间的键 LRU 淘汰
maxmemory-policy volatile-lru

# 4. allkeys-random - 所有键随机淘汰
maxmemory-policy allkeys-random

# 5. volatile-random - 有过期时间的键随机淘汰
maxmemory-policy volatile-random

# 6. volatile-ttl - 按 TTL 淘汰
maxmemory-policy volatile-ttl
```

### 3.2 内存模型

```go
// memory_model.go

package redis

import (
    "sync"
    "time"
)

type MemoryManager struct {
    maxMemory    int64
    usedMemory   int64
    mu           sync.RWMutex
    evictions    int64
}

func (m *MemoryManager) CheckMemory(keySize, valueSize int64) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    required := keySize + valueSize
    if m.usedMemory+required > m.maxMemory {
        // 需要淘汰
        err := m.evict(required)
        if err != nil {
            return err
        }
    }
    
    m.usedMemory += required
    return nil
}

func (m *MemoryManager) evict(required int64) error {
    // LRU 淘汰算法
    // ...
    return nil
}
```

---

## 4. 高可用架构

### 4.1 Sentinel 架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Redis Sentinel 架构                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Sentinel 1  │    │ Sentinel 2  │    │ Sentinel 3  │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                     ┌──────▼──────┐                         │
│                     │  主观下线    │                         │
│                     │  客观下线    │                         │
│                     └──────┬──────┘                         │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │   故障转移     │                        │
│                    └───────┬───────┘                        │
│                            │                                │
│              ┌─────────────┼─────────────┐                  │
│              ▼             ▼             ▼                  │
│        ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│        │ Master  │   │ Slave 1 │   │ Slave 2 │             │
│        └─────────┘   └─────────┘   └─────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go Sentinel 客户端

```go
// sentinel_client.go

package redis

import (
    "github.com/go-redis/redis/v8"
)

type SentinelClient struct {
    masterName string
    addrs      []string
    client     *redis.Client
}

func NewSentinelClient(masterName string, addrs []string) *SentinelClient {
    opt := &redis.FailoverOptions{
        MasterName:       masterName,
        SentinelAddrs:    addrs,
        RetryTimes:       3,
        DialTimeout:      5 * time.Second,
        ReadTimeout:      3 * time.Second,
        WriteTimeout:     3 * time.Second,
    }
    
    return &SentinelClient{
        masterName: masterName,
        addrs:      addrs,
        client:     redis.NewFailoverClient(opt),
    }
}

func (c *SentinelClient) Get(key string) (string, error) {
    return c.client.Get(key).Result()
}

func (c *SentinelClient) Set(key, value string, exp time.Duration) error {
    return c.client.Set(key, value, exp).Err()
}
```

---

## 5. 性能优化

### 5.1 连接池配置

```go
// pool_config.go

package redis

import (
    "github.com/go-redis/redis/v8"
)

func NewOptimizedClient(addr string) *redis.Client {
    return redis.NewClient(&redis.Options{
        Addr:         addr,
        Password:     "",
        DB:           0,
        
        // 连接池
        PoolSize:     50,
        MinIdleConns: 10,
        MaxConnAge:   time.Hour,
        PoolTimeout:  time.Second * 4,
        IdleTimeout:  time.Minute * 5,
        
        // 重试
        MaxRetries:   3,
        RetryDelay:   time.Millisecond * 100,
        
        // 超时
        ReadTimeout:  time.Second * 3,
        WriteTimeout: time.Second * 3,
        
        // Pipeline
        PipelineSize: 100,
    })
}
```

### 5.2 Pipeline 批量操作

```go
// pipeline.go

package redis

import (
    "context"
    "github.com/go-redis/redis/v8"
)

func PipelineSet(client *redis.Client, data map[string]string) error {
    pipe := client.Pipeline()
    
    for key, value := range data {
        pipe.Set(key, value, 0)
    }
    
    _, err := pipe.Exec(context.Background())
    return err
}

func PipelineGet(client *redis.Client, keys []string) (map[string]string, error) {
    pipe := client.Pipeline()
    
    cmds := make([]*redis.StringCmd, len(keys))
    for i, key := range keys {
        cmds[i] = pipe.Get(key)
    }
    
    _, err := pipe.Exec(context.Background())
    if err != nil {
        return nil, err
    }
    
    result := make(map[string]string)
    for i, cmd := range cmds {
        val, _ := cmd.Result()
        result[keys[i]] = val
    }
    
    return result, nil
}
```

---

## 6. 监控告警

### 6.1 关键指标

```go
// metrics.go

package redis

import "github.com/prometheus/client_golang/prometheus"

type RedisMetrics struct {
    opsTotal      prometheus.Counter
    opsLatency    prometheus.Histogram
    connected     prometheus.Gauge
    memoryUsed    prometheus.Gauge
    keysTotal     prometheus.Gauge
    hitRate       prometheus.Gauge
}

func NewRedisMetrics() *RedisMetrics {
    return &RedisMetrics{
        opsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_ops_total",
            Help: "Total redis operations",
        }),
        opsLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "redis_ops_latency_seconds",
            Help:    "Operation latency",
            Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5},
        }),
        connected: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_connected_clients",
            Help: "Connected clients",
        }),
        memoryUsed: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_memory_used_bytes",
            Help: "Memory used",
        }),
        keysTotal: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_keys_total",
            Help: "Total keys",
        }),
        hitRate: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_hit_rate",
            Help: "Cache hit rate",
        }),
    }
}
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| OOM | 写入失败 | `MEMORY DOCTOR` | 调整淘汰策略 |
| 慢查询 | 响应慢 | `SLOWLOG GET` | 优化key设计 |
| 大key | 阻塞 | `MEMORY USAGE` | 拆分大key |
| 网络 | 连接超时 | `CLIENT LIST` | 调整超时配置 |

### 7.2 调试命令

```bash
# 查看慢查询
redis-cli SLOWLOG GET 10

# 查看内存
redis-cli MEMORY DOCTOR
redis-cli INFO memory

# 查看 Keyspace
redis-cli INFO keyspace

# 监控连接
redis-cli CLIENT LIST

# 检查大Key
redis-cli --bigkeys
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 集群 | 哈希槽分片 |
| 持久化 | RDB + AOF |
| 高可用 | Sentinel 故障转移 |
| 性能 | 连接池 + Pipeline |

### 8.2 最佳实践

- [ ] 合理配置内存淘汰策略
- [ ] 使用 Pipeline 批量操作
- [ ] 避免大 Key
- [ ] 监控关键指标
- [ ] 定期备份数据

---

*最后更新：2026-08-11*
*作者：Ryan*
