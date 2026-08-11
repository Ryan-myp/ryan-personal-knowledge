# Redis 内存模型深度解析

> 深入 Redis 内存模型：数据结构、内存分配、持久化、内存管理。
> 源码级分析，包含生产环境优化。
> 适用对象：后端工程师、DBA、系统架构师

---

## 1. 数据结构

### 1.1 核心对象

```
┌─────────────────────────────────────────────────────────────┐
│                  Redis 核心数据结构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SDS (Simple Dynamic String)                                 │
│  ───────────────────────────                                 │
│  struct sdshdr {                                             │
│      uint32_t len;        // 已使用长度                       │
│      uint32_t free;       // 剩余空间                         │
│      char buf[];        // 数据缓冲区                         │
│  };                                                          │
│                                                             │
│  list                                                          │
│  ───────────────────────────                                 │
│  struct list {                                                │
│      listNode *head;                                          │
│      listNode *tail;                                          │
│      void *(*dup)(void *ptr);                                │
│      void (*free)(void *ptr);                                │
│      int (*match)(void *ptr, void *key);                     │
│      unsigned long len;                                       │
│  };                                                          │
│                                                             │
│  dict (哈希表)                                               │
│  ───────────────────────────                                 │
│  struct dict {                                                │
│      dictType *type;                                          │
│      void *privdata;                                          │
│      dictht ht[2];   // 双哈希表，用于 rehash                 │
│      long rehashidx;  // rehash 进度                          │
│      unsigned long iterators;                                 │
│  };                                                          │
│                                                             │
│  zset (跳表 + 哈希表)                                        │
│  ───────────────────────────                                 │
│  struct zset {                                                │
│      dict *dict;       // 成员 -> 分数的映射                   │
│      zskiplist *zsl;   // 跳跃表，按分数排序                   │
│  };                                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 对象类型

```c
// redis.h (简化)

typedef struct redisObject {
    unsigned type:4;       // 对象类型
    unsigned encoding:4;   // 编码方式
    unsigned lru:22;       // LRU 时间
    int refcount;          // 引用计数
    void *ptr;             // 指向实际数据
} robj;

// 对象类型
#define OBJ_STRING 0
#define OBJ_LIST 1
#define OBJ_SET 2
#define OBJ_ZSET 3
#define OBJ_HASH 4
#define OBJ_STREAM 5

// 编码方式
#define OBJ_ENCODING_RAW 0      // 原始字符串
#define OBJ_ENCODING_INT 1      // 整数
#define OBJ_ENCODING_HT 2       // 哈希表
#define OBJ_ENCODING_ZIPMAP 3   // zipmap
#define OBJ_ENCODING_LINKEDLIST 4 // 链表
#define OBJ_ENCODING_ZIPLIST 5  // 压缩列表
#define OBJ_ENCODING_INTSET 6   // 整数集合
#define OBJ_ENCODING_SKIPLIST 7 // 跳跃表
#define OBJ_ENCODING_EMBSTR 8   // 短字符串
#define OBJ_ENCODING_QUICKLIST 9 // 快速列表
```

---

## 2. 内存分配

### 2.1 jemalloc  allocator

```
Redis 使用 jemalloc 作为内存分配器

优势：
- 减少内存碎片
- 多线程友好
- 更好的性能

配置：
make MALLOC=jemalloc
```

### 2.2 内存碎片

```
内存碎片率计算：

碎 片 率 = (used_memory - used_memory_rss) / used_memory_rss * 100%

优化方案：
1. 调整 maxmemory 策略
2. 定期重启服务
3. 使用内存复用
```

---

## 3. 持久化

### 3.1 RDB 快照

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

### 3.2 AOF 追加

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

## 4. 内存管理

### 4.1 淘汰策略

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

### 4.2 Go 实现内存管理

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
| 数据结构 | SDS/Hash/SkipList |
| 内存分配 | jemalloc |
| 持久化 | RDB+AOF |
| 淘汰策略 | LRU/LFU |

### 8.2 最佳实践

- [ ] 合理配置内存淘汰策略
- [ ] 使用 Pipeline 批量操作
- [ ] 避免大 Key
- [ ] 监控关键指标
- [ ] 定期备份数据

---

*最后更新：2026-08-11*
*作者：Ryan*
