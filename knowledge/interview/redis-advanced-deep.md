# Redis高级特性 - 资深专家深度实现

## 一、持久化机制

### 1.1 RDB (快照)

```
触发时机:
1. 手动触发: SAVE (阻塞), BGSAVE (后台)
2. 自动触发: redis.conf配置
   save 900 1      # 900秒内有1个key变更
   save 300 10     # 300秒内有10个key变更
   save 60 10000   # 60秒内有10000个key变更

优缺点:
优点: 文件紧凑，恢复快，适合备份
缺点: 可能丢失最后一次快照的数据
```

### 1.2 AOF (追加日志)

```yaml
# redis.conf 配置
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec  # 每秒同步

# 三种策略:
# always: 每次写操作都同步 (最慢，最安全)
# everysec: 每秒同步一次 (推荐)
# no: 操作系统决定何时同步
```

### 1.3 混合持久化 (Redis 4.0+)

```
AOF重写时的优化:
┌─────────────────────────────────────────────────────┐
│  旧AOF    │  RDB快照 │  新AOF                        │
│  (文本)   │ (二进制) │ (文本)                        │
└─────────────────────────────────────────────────────┘
```

```go
// Go客户端配置
import redis "github.com/go-redis/redis/v8"

rdb := redis.NewClient(&redis.Options{
    Addr:     "localhost:6379",
    Password: "",
    DB:       0,
    
    // AOF相关配置
    TCP: "tcp",
})
```

## 二、内存优化

### 2.1 数据类型选择

```
内存使用对比 (存储100万个int):
┌──────────────┬──────────┬──────────┐
│ 数据类型     │ 内存使用 │ 效率     │
├──────────────┼──────────┼──────────┤
│ String       │ 50MB     │ 低       │
│ Hash         │ 30MB     │ 中       │
│ ZSet         │ 40MB     │ 中       │
│ List         │ 35MB     │ 中       │
└──────────────┴──────────┴──────────┘
```

### 2.2 对象编码

```c
// Redis对象结构
typedef struct redisObject {
    unsigned type:4;      // 对象类型
    unsigned encoding:4;  // 编码方式
    unsigned lru:22;      // 空闲时间
    int refcount;         // 引用计数
    void *ptr;            // 指向实际数据
} robj;

// Hash对象编码:
// - ziplist: 元素少且短
// - hashtable: 元素多或长
```

### 2.3 内存淘汰策略

```yaml
# maxmemory-policy
# noeviction: 不淘汰，返回错误
# allkeys-lru: 所有key使用LRU淘汰
# volatile-lru: 有过期时间的key使用LRU
# allkeys-random: 随机淘汰
# volatile-random: 随机淘汰过期key
# volatile-ttl: 淘汰即将过期的key
```

## 三、集群架构

### 3.1 主从复制

```
复制流程:
1. 从库连接主库，发送SYNC命令
2. 主库启动后台保存，生成RDB文件
3. 主库将RDB文件发送给从库
4. 主库将缓冲的写命令发送给从库
5. 从库加载RDB并应用写命令
```

### 3.2 Sentinel高可用

```yaml
# sentinel.conf
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1
```

### 3.3 Cluster分片

```
16384个哈希槽:
┌──────────────────────────────────────────────────────┐
│  Node A              │  Node B              │  Node C  │
│  Slots: 0-5460       │  Slots: 5461-10922   │  10923-  │
│                      │                      │  16383   │
└──────────────────────────────────────────────────────┘

哈希算法: hashSlot(key) = CRC16(key) % 16384
```

## 四、常见问题解决

### 4.1 缓存穿透

```go
// 方案: 布隆过滤器 + 空值缓存
type Cache struct {
    bloom *bloom.BloomFilter
    store *redis.Client
}

func (c *Cache) Get(key string) (string, error) {
    // 1. 布隆过滤器检查
    if !c.bloom.Test([]byte(key)) {
        return "", nil // 肯定不存在
    }
    
    // 2. 查询缓存
    val, err := c.store.Get(key).Result()
    if err == redis.Nil {
        // 3. 缓存空值
        c.store.Set(key, "", 60*time.Second)
        return "", nil
    }
    return val, nil
}
```

### 4.2 缓存击穿

```go
// 方案: 互斥锁
func (c *Cache) GetWithMutex(key string) (string, error) {
    val, err := c.store.Get(key).Result()
    if err == nil {
        return val, nil
    }
    
    // 获取分布式锁
    lockKey := "lock:" + key
    locked, err := c.store.SetNX(lockKey, "1", 10*time.Second).Result()
    if err != nil || !locked {
        time.Sleep(50 * time.Millisecond)
        return c.GetWithMutex(key) // 重试
    }
    
    defer c.store.Del(lockKey)
    
    // 双重检查
    val, err = c.store.Get(key).Result()
    if err == nil {
        return val, nil
    }
    
    // 查询DB并写入缓存
    val = c.queryDB(key)
    c.store.Set(key, val, time.Hour)
    return val, nil
}
```

## 五、面试高频题

### Q1: Redis为什么这么快？

```
A:
1. 纯内存操作
2. 单线程模型 (避免上下文切换和竞争)
3. 高效的数据结构 (SDS、跳表等)
4. IO多路复用 (epoll)
```

### Q2: Redis持久化如何选择？

```
A:
- 对数据安全要求高: AOF + RDB混合
- 对性能要求高: RDB
- 折中方案: AOF everysec
```

### Q3: 如何解决缓存穿透？

```
A:
1. 布隆过滤器预处理
2. 缓存空值
3. 校验参数合法性
```

## 六、自测题

1. 解释Redis持久化的三种方式
2. 如何实现Redis分布式锁？
3. 缓存击穿、穿透、雪崩的区别和解决方案？

---

## 参考文档

- [Redis官方文档](https://redis.io/docs/)
- [Redis深度历险](https://redis.io/topics/internals)
