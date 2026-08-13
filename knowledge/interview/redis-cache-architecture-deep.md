# Redis缓存架构 --- 资深专家深度实现

## 概述

Redis作为高性能缓存和分布式锁的核心组件，在生产环境中需要深入理解其架构设计、持久化机制和集群方案。

## 一、Redis数据结构

### 1.1 核心数据结构

```
┌─────────────────────────────────────────────────────────┐
│                  Redis数据结构                           │
├──────────┬──────────────────────────────────────────────┤
│ String   │ 字符串，最简单类型                            │
│ Hash     │ 键值对集合，适合对象存储                      │
│ List     │ 双向链表，支持两端操作                        │
│ Set      │ 无序集合，支持交集/并集/差集                  │
│ ZSet     │ 有序集合，按score排序                         │
│ Stream   │ 日志型数据结构，支持消息队列                  │
│ Bitmap   │ 位数组，适合统计                              │
│ HyperLog │ 基数统计，适合UV计算                          │
└──────────┴──────────────────────────────────────────────┘
```

### 1.2 内存模型

```c
// Redis对象结构
typedef struct redisObject {
    unsigned type:4;      // 对象类型
    unsigned encoding:4;  // 编码方式
    unsigned lru:22;      // 淘汰策略
    int refcount;         // 引用计数
    void *ptr;            // 指向底层数据结构
} robj;

// 编码方式
// SDS: Simple Dynamic String (String)
// ziplist: 压缩列表 (Hash/List/ZSet小数据)
// hashtable: 哈希表 (Hash大数据)
// skiplist: 跳跃表 (ZSet大数据)
// listpack: 列表包 (Redis 7.0+)
```

## 二、持久化机制

### 2.1 RDB快照

```conf
# redis.conf配置
save 900 1      # 15分钟至少1个key变化
save 300 10     # 5分钟至少10个key变化
save 60 10000   # 1分钟至少10000个key变化

# 手动触发
SAVE      # 阻塞主进程
BGSAVE    # 后台 fork子进程

# 启动时加载
# Redis会自动加载最近的RDB文件
```

```c
// RDB生成流程
void backgroundSave() {
    pid_t pid = fork();
    if (pid == 0) {
        // 子进程
        rdbSave(filename);
        _exit(0);
    } else {
        // 父进程
        server.lastbgsave_try = time(NULL);
    }
}
```

### 2.2 AOF重写

```conf
# AOF配置
appendonly yes
appendfsync everysec       # 每秒同步
# no: 操作系统控制
# always: 每次写操作同步

# AOF重写
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# 手动触发
BGREWRITEAOF
```

```
┌─────────────────────────────────────────────────────┐
│                    AOF重写流程                        │
├─────────────────────────────────────────────────────┤
│  1. 父进程fork子进程                                │
│  2. 子进程遍历内存，生成新AOF文件                    │
│  3. 父进程将新写入命令追加到新AOF缓冲区              │
│  4. 子进程写完新AOF后，父进程将缓冲区内容追加        │
│  5. 替换旧AOF文件                                   │
└─────────────────────────────────────────────────────┘
```

## 三、缓存模式

### 3.1 Cache-Aside

```go
// Go实现Cache-Aside模式
func GetProduct(ctx context.Context, productID int64) (*Product, error) {
    // 1. 查缓存
    cacheKey := fmt.Sprintf("product:%d", productID)
    cached, err := redis.Get(ctx, cacheKey).Bytes()
    if err == nil && len(cached) > 0 {
        var product Product
        json.Unmarshal(cached, &product)
        return &product, nil
    }
    
    // 2. 查数据库
    var product Product
    err = db.Where("id = ?", productID).First(&product).Error
    if err != nil {
        return nil, err
    }
    
    // 3. 写入缓存
    data, _ := json.Marshal(product)
    redis.Set(ctx, cacheKey, data, 5*time.Minute)
    
    return &product, nil
}

func UpdateProduct(ctx context.Context, product *Product) error {
    // 1. 更新数据库
    err := db.Save(product).Error
    if err != nil {
        return err
    }
    
    // 2. 删除缓存
    cacheKey := fmt.Sprintf("product:%d", product.ID)
    redis.Del(ctx, cacheKey)
    
    return nil
}
```

### 3.2 Write-Through

```go
// Write-Through：先写缓存，再写数据库
func SetProduct(ctx context.Context, product *Product) error {
    // 1. 写入缓存（同步）
    cacheKey := fmt.Sprintf("product:%d", product.ID)
    data, _ := json.Marshal(product)
    redis.Set(ctx, cacheKey, data, 0) // 永不过期
    
    // 2. 写入数据库（异步）
    go func() {
        db.Save(product)
    }()
    
    return nil
}
```

### 3.3 缓存一致性

```go
// 延迟双删
func DeleteCacheWithDelay(ctx context.Context, key string) error {
    // 1. 删除缓存
    redis.Del(ctx, key)
    
    // 2. 更新数据库
    
    // 3. 延迟删除（应对并发更新）
    time.Sleep(500 * time.Millisecond)
    redis.Del(ctx, key)
    
    return nil
}

// Canal监听Binlog
// 使用Canal订阅MySQL Binlog，异步更新Redis
```

## 四、集群架构

### 4.1 Redis Cluster

```
┌─────────────────────────────────────────────────────────┐
│                   Redis Cluster架构                     │
├─────────────────────────────────────────────────────────┤
│  16384个槽位(shards)                                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │ Master1 │  │ Master2 │  │ Master3 │                 │
│  │  Slave  │  │  Slave  │  │  Slave  │                 │
│  └─────────┘  └─────────┘  └─────────┘                 │
│  slot 0-5460     5461-10922   10923-16383               │
└─────────────────────────────────────────────────────────┘
```

```bash
# 启动集群
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 \
  127.0.0.1:7002 127.0.0.1:7003 \
  127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1

# 查看集群状态
redis-cli -c cluster info
redis-cli -c cluster nodes
```

### 4.2 一致性哈希

```go
// 一致性哈希实现
type ConsistentHash struct {
    hash     func([]byte) uint32
    keys     []uint32
    circle   map[uint32]string
}

func NewConsistentHash(items []string) *ConsistentHash {
    ch := &ConsistentHash{
        hash:   crc32.ChecksumIEEE,
        circle: make(map[uint32]string),
    }
    for _, item := range items {
        for i := 0; i < 150; i++ {  // 虚拟节点
            key := ch.hash([]byte(item + strconv.Itoa(i)))
            ch.keys = append(ch.keys, key)
            ch.circle[key] = item
        }
    }
    sort.Slice(ch.keys, func(i, j int) bool {
        return ch.keys[i] < ch.keys[j]
    })
    return ch
}

func (ch *ConsistentHash) Get(key string) string {
    if len(ch.keys) == 0 {
        return ""
    }
    h := ch.hash([]byte(key))
    idx := sort.Search(len(ch.keys), func(i int) bool {
        return ch.keys[i] >= h
    })
    if idx == len(ch.keys) {
        idx = 0
    }
    return ch.circle[ch.keys[idx]]
}
```

## 五、性能优化

### 5.1 大Key问题

```go
// 大Key检测
redis-cli --bigkeys

// 大Hash优化
// 分批删除
SCAN 0 MATCH user:large:* COUNT 100
// 分批删除field

// 使用Redis 7.0的HSCAN迭代
HSCAN key 0 MATCH pattern COUNT 100
```

### 5.2 热点Key

```go
// 本地缓存 + Redis
type HotKeyCache struct {
    local  sync.Map    // 本地缓存
    remote *redis.Client
}

func (c *HotKeyCache) Get(key string) ([]byte, error) {
    // 1. 查本地缓存
    if v, ok := c.local.Load(key); ok {
        return v.([]byte), nil
    }
    
    // 2. 查Redis
    data, err := c.remote.Get(context.Background(), key).Bytes()
    if err != nil {
        return nil, err
    }
    
    // 3. 写入本地缓存
    c.local.Store(key, data)
    return data, nil
}
```

### 5.3 连接池

```go
import "github.com/go-redis/redis/v8"

func NewRedisPool() *redis.Client {
    rdb := redis.NewClient(&redis.Options{
        Addr:         "localhost:6379",
        Password:     "",
        DB:           0,
        PoolSize:     100,           // 连接池大小
        MinIdleConns: 10,            // 最小空闲连接
        MaxConnAge:   time.Hour,     // 连接最大生命周期
        PoolTimeout:  time.Second,   // 获取连接超时
        IdleTimeout:  time.Minute,   // 空闲连接超时
    })
    return rdb
}
```

## 六、面试高频题

### 6.1 高频问题

**Q1: Redis为什么这么快？**

A:
- 纯内存操作
- 单线程模型，避免上下文切换
- IO多路复用（epoll）
- 高效的数据结构实现

**Q2: Redis持久化方案如何选择？**

A:
- RDB：适合备份恢复，定期快照
- AOF：适合数据完整性，记录每次写操作
- 混合模式：RDB+AOF组合

**Q3: 如何解决缓存穿透/击穿/雪崩？**

A:
- 穿透：布隆过滤器/缓存空值
- 击穿：互斥锁/永不过期
- 雪崩：随机TTL/多级缓存

### 6.2 自测题

1. 画出Redis内存模型图
2. 解释RDB和AOF的区别
3. 实现一个简单的本地缓存
4. 分析热点Key的解决方案
5. 设计一个分布式锁方案

---

**创建时间**: 2026-10-16
**作者**: Ryan
**领域**: Interview / 缓存
**关键词**: redis, cache, persistence, cluster, hotkey
