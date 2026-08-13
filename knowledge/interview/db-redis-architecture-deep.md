# Redis缓存架构 - 资深专家深度实现

## 一、Redis架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Redis集群架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        Sentinel/Cluster                          │   │
│   └───────────────────────┬─────────────────────────────────────────┘   │
│                           │                                              │
│        ┌──────────────────┼──────────────────┐                          │
│        ▼                  ▼                  ▼                          │
│   ┌─────────┐       ┌─────────┐       ┌─────────┐                     │
│   │ Master  │◄─────▶│ Master  │◄─────▶│ Master  │                     │
│   │  Node1  │       │  Node2  │       │  Node3  │                     │
│   └────┬────┘       └────┬────┘       └────┬────┘                     │
│        │                 │                 │                            │
│   ┌────┴────┐       ┌────┴────┐       ┌────┴────┐                     │
│   │ Replica │       │ Replica │       │ Replica │                     │
│   │  Node1  │       │  Node2  │       │  Node3  │                     │
│   └─────────┘       └─────────┘       └─────────┘                     │
│                                                                         │
│   分片策略:                                                              │
│   • Hash Slot: 16384个槽位                                               │
│   • 每个Master管理部分槽位                                                 │
│   • 数据自动分片                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、内存模型

### 2.1 数据结构实现

```go
// dict.h - 字典实现
typedef struct dict {
    dictType *type;           // 字典类型
    void *privdata;           // 私有数据
    dictht ht[2];            // 两个哈希表（用于rehash）
    long rehashidx;          // rehash进度
    unsigned long iterators; // 迭代器数量
} dict;

typedef struct dictht {
    dictEntry **table;       // 哈希表数组
    unsigned long size;      // 哈希表大小
    unsigned long sizemask;  // 掩码
    unsigned long used;      // 已使用节点数
} dictht;

typedef struct dictEntry {
    void *key;               // 键
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next;  // 链地址法解决冲突
} dictEntry;
```

### 2.2 内存编码

```c
// object.c - 对象编码
#define OBJ_STRING 0  // 字符串对象
#define OBJ_LIST 1    // 列表对象
#define OBJ_SET 2     // 集合对象
#define OBJ_ZSET 3    // 有序集合
#define OBJ_HASH 4    // 哈希对象

// 字符串对象的编码
typedef struct sdshdr {
    uint32_t len;      // 已使用长度
    uint32_t free;     // 剩余空间
    char buf[];        // 数据
} sdshdr;

// 不同长度使用不同编码
// < 44 bytes: 直接存储在sdshdr
// >= 44 bytes: 使用ziplist/hashtable
```

## 三、持久化机制

### 3.1 RDB快照

```bash
# 触发RDB快照
SAVE      # 阻塞主进程
BGSAVE    # 后台fork子进程

# 配置
save 900 1     # 900秒内至少1个key变化
save 300 10    # 300秒内至少10个key变化
save 60 10000  # 60秒内至少10000个key变化
```

### 3.2 AOF重写

```bash
# AOF配置
appendonly yes
appendfsync everysec          # 每秒同步
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# 手动触发重写
BGREWRITEAOF
```

```go
// AOF重写流程
func rewriteAOF() {
    // 1. fork子进程
    pid := syscall.Fork()
    if pid == 0 {
        // 子进程：重写AOF
        rewriteAOFChild()
    } else {
        // 父进程：继续处理命令，同时记录到aof_rewrite_buf
        startAOFBGRewrite()
    }
}
```

## 四、缓存问题与解决方案

### 4.1 缓存穿透

```go
package cache

import "github.com/go-redis/redis/v8"

type BloomFilter struct {
    client *redis.Client
    keys   []string
}

func (b *BloomFilter) Add(key string) {
    for _, k := range b.keys {
        b.client.BitOpAnd(context.Background(), k, k, k)
        b.client.SetBit(context.Background(), k, hash(key)%256, 1)
    }
}

func (b *BloomFilter) Contains(key string) bool {
    for _, k := range b.keys {
        if b.client.GetBit(context.Background(), k, hash(key)%256).Val() == 0 {
            return false
        }
    }
    return true
}

// 缓存穿透保护
func (c *Cache) GetWithBloom(ctx context.Context, key string) (string, error) {
    // 1. 布隆过滤器检查
    if !bloom.Contains(key) {
        return "", nil // 肯定不存在
    }
    
    // 2. 缓存检查
    val, err := c.redis.Get(ctx, key).Result()
    if err == nil {
        return val, nil
    }
    
    // 3. 数据库查询
    val, err = c.db.Get(ctx, key)
    if err != nil {
        // 写入空值防止穿透
        c.redis.Set(ctx, key, "", 5*time.Minute)
        return "", err
    }
    
    c.redis.Set(ctx, key, val, 30*time.Minute)
    return val, nil
}
```

### 4.2 缓存击穿

```go
// 互斥锁防止击穿
func (c *Cache) GetWithMutex(ctx context.Context, key string) (string, error) {
    // 1. 缓存读取
    val, err := c.redis.Get(ctx, key).Result()
    if err == nil {
        return val, nil
    }
    
    // 2. 尝试获取锁
    lockKey := "lock:" + key
    locked := c.redis.SetNX(ctx, lockKey, "1", 10*time.Second).Val()
    
    if locked {
        // 3. 重新读取缓存
        val, err = c.redis.Get(ctx, key).Result()
        if err != nil {
            // 4. 从数据库加载
            val, err = c.loadFromDB(ctx, key)
            c.redis.Set(ctx, key, val, 30*time.Minute)
        }
        c.redis.Del(ctx, lockKey)
        return val, err
    }
    
    // 5. 等待后重试
    time.Sleep(10 * time.Millisecond)
    return c.GetWithMutex(ctx, key)
}
```

### 4.3 缓存雪崩

```go
// 随机TTL防止雪崩
func (c *Cache) SetWithJitter(ctx context.Context, key, val string, baseTTL time.Duration) {
    // 添加随机抖动
    jitter := time.Duration(rand.Int63n(int64(baseTTL) / 4))
    ttl := baseTTL + jitter
    c.redis.Set(ctx, key, val, ttl)
}

// 多级缓存架构
type MultiLevelCache struct {
    local  *LocalCache   // L1: 本地缓存
    redis  *redis.Client // L2: Redis缓存
    db     *Database     // L3: 数据库
}
```

## 五、面试高频题

### Q1: Redis为什么快？

```
A:
1. 纯内存操作
2. 单线程模型（避免上下文切换和竞争）
3. 高效的数据结构（SDS/跳表/哈希）
4. IO多路复用（epoll/kqueue）
5. 零拷贝技术
```

### Q2: Redis持久化方案如何选择？

```
A:
• RDB: 适合备份恢复，文件小，恢复快
• AOF: 适合数据安全性，记录每条写命令
• 混合: RDB+AOF，兼顾性能和安全性
```

### Q3: 如何解决缓存穿透/击穿/雪崩？

```
A:
• 穿透: 布隆过滤器 + 空值缓存
• 击穿: 互斥锁 + 永不过期
• 雪崩: 随机TTL + 多级缓存 + 限流降级
```

## 六、自测题

1. Redis的内存回收策略有哪些？
2. Redis集群如何实现数据分片？
3. 如何设计一个高可用的Redis缓存系统？

---

## 参考文档

- [Redis源码](https://github.com/redis/redis)
- [Redis官方文档](https://redis.io/docs/)
