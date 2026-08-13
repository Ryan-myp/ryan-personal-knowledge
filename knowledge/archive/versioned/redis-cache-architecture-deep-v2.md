# Redis 缓存架构深度解析

> 深入 Redis 缓存架构：集群模式、持久化、内存管理、高可用。
> 包含生产环境调优和故障排查。
> 适用对象：后端工程师、DBA、系统架构师

---

## 1. Redis 集群架构

### 1.1 集群模式对比

```
┌─────────────────────────────────────────────────────────────┐
│                  Redis 集群模式对比                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Sentinel (哨兵模式)                                       │
│     ├── 主从复制 + 故障转移                                 │
│     ├── 单 Master，多 Slave                                 │
│     └── 适合小规模部署                                      │
│                                                             │
│  2. Cluster (集群模式)                                       │
│     ├── 分片存储 (16384 个 hash slot)                       │
│     ├── 多 Master，多 Slave                                 │
│     └── 适合大规模部署                                      │
│                                                             │
│  3. Twemproxy (代理模式)                                     │
│     ├── 客户端分片                                          │
│     └── 需要客户端支持                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Redis Cluster 原理

```
Redis Cluster 架构：

┌─────────────────────────────────────────────────────────────┐
│                    Redis Cluster                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Master 1 │◄──►│ Master 2 │◄──►│ Master 3 │              │
│  │ (0-5460) │    │ (5461-   │    │ (10922-  │              │
│  │          │    │  10921)  │    │  16383)  │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                      │
│       ▼               ▼               ▼                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Slave 1  │    │ Slave 2  │    │ Slave 3  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
│  数据分片：                                                   │
│  ├── 16384 个 hash slot                                      │
│  ├── 每个 Master 负责一部分 slot                             │
│  └── Key → CRC16 → slot → Master                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 持久化

### 2.1 RDB 快照

```
RDB 生成过程：

1. 主进程 fork 子进程
2. 子进程写入临时 RDB 文件
3. 子进程完成后原子替换

优点：
- 文件紧凑，适合备份
- 恢复速度快

缺点：
- 可能丢失最后一次快照后的数据
- fork 时内存拷贝开销大
```

### 2.2 AOF 追加

```
AOF 重写：

1. 子进程遍历内存数据
2. 生成新的 AOF 文件
3. 原子替换旧文件

配置：
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

---

## 3. 内存管理

### 3.1 淘汰策略

```conf
# maxmemory-policy

noeviction         # 不淘汰，返回错误
allkeys-lru        # 所有键 LRU 淘汰
volatile-lru       # 有过期时间的键 LRU 淘汰
allkeys-random     # 所有键随机淘汰
volatile-random    # 有过期时间的键随机淘汰
volatile-ttl       # 按 TTL 淘汰
volatile-lfu       # 低频访问淘汰
allkeys-lfu        # 全局低频访问淘汰
```

### 3.2 Go 实现内存管理

```go
// memory_manager.go

package redis

import (
    "sync"
    "time"
)

type MemoryManager struct {
    maxMemory int64
    usedMemory int64
    mu       sync.RWMutex
    evictions int64
}

func (m *MemoryManager) CheckMemory(keySize, valueSize int64) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    required := keySize + valueSize
    if m.usedMemory+required > m.maxMemory {
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

## 4. 高可用

### 4.1 Sentinel 架构

```
Sentinel 集群：

┌─────────────────────────────────────────────────────────────┐
│                  Sentinel 架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Sentinel │    │ Sentinel │    │ Sentinel │              │
│  │   1      │    │   2      │    │   3      │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                      │
│       └───────────────┼───────────────┘                      │
│                       │                                      │
│                       ▼                                      │
│              ┌──────────────┐                                │
│              │  Master      │                                │
│              │  (主节点)     │                                │
│              └──────┬───────┘                                │
│                     │                                       │
│            ┌────────┴────────┐                              │
│            ▼                 ▼                              │
│      ┌──────────┐      ┌──────────┐                        │
│      │ Slave 1  │      │ Slave 2  │                        │
│      └──────────┘      └──────────┘                        │
│                                                             │
│  故障转移流程：                                               │
│  1. Sentinel 检测 Master 故障                               │
│  2. Sentinel 投票确认故障                                   │
│  3. 选择一个 Slave 提升为 Master                            │
│  4. 其他 Slave 复制新 Master                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现 Sentinel 客户端

```go
// sentinel_client.go

package redis

import (
    "github.com/go-redis/redis/v8"
)

type SentinelClient struct {
    masterName string
    client     *redis.Client
}

func NewSentinelClient(masterName string) *SentinelClient {
    return &SentinelClient{
        masterName: masterName,
    }
}

func (c *SentinelClient) GetMasterAddr() (string, error) {
    // 从 Sentinel 获取 Master 地址
    return "127.0.0.1:6379", nil
}
```

---

## 5. 性能优化

### 5.1 大 Key 问题

```
大 Key 问题：

1. 内存占用大
2. 网络传输慢
3. 阻塞主线程
4. 删除困难

解决方案：
- 拆分大 Key
- 使用 Hash 类型
- 定期清理
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
```

---

## 6. 监控告警

### 6.1 关键指标

```
监控指标：
- 内存使用率
- 连接数
- QPS
- 命中率
- 慢查询
- 持久化状态
```

### 6.2 Go 实现监控

```go
// metrics.go

package redis

import "github.com/prometheus/client_golang/prometheus"

type RedisMetrics struct {
    memoryUsed    prometheus.Gauge
    connections   prometheus.Gauge
    opsTotal      prometheus.Counter
    hitRate       prometheus.Gauge
    slowQueries   prometheus.Counter
}

func NewRedisMetrics() *RedisMetrics {
    return &RedisMetrics{
        memoryUsed: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_memory_used_bytes",
            Help: "Memory used",
        }),
        connections: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_connected_clients",
            Help: "Connected clients",
        }),
        opsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_ops_total",
            Help: "Total operations",
        }),
        hitRate: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_hit_rate",
            Help: "Cache hit rate",
        }),
        slowQueries: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_slow_queries_total",
            Help: "Slow queries",
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
# 查看内存
redis-cli INFO memory

# 查看慢查询
redis-cli SLOWLOG GET 10

# 查看 Keyspace
redis-cli INFO keyspace

# 检查大Key
redis-cli --bigkeys
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 集群 | 分片存储 + 多 Master |
| 持久化 | RDB + AOF |
| 高可用 | Sentinel 故障转移 |
| 内存管理 | LRU/LFU 淘汰 |

### 8.2 最佳实践

- [ ] 合理配置内存淘汰策略
- [ ] 使用 Pipeline 批量操作
- [ ] 避免大 Key
- [ ] 监控关键指标
- [ ] 定期备份数据

---

*最后更新：2026-08-11*
*作者：Ryan*
