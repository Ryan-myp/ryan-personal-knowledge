# Redis缓存模式深度实现 --- 资深专家深度实现

## 概述

Redis缓存模式是分布式系统的核心组件。本文深入剖析常见缓存模式、一致性策略和生产环境最佳实践。

## 一、缓存模式分类

### 1.1 Cache-Aside (旁路缓存)

```go
// 最常用模式：先查缓存，未命中查DB，再写入缓存
func GetProduct(ctx context.Context, productID int64) (*Product, error) {
    cacheKey := fmt.Sprintf("product:%d", productID)
    
    // 1. 查缓存
    cached, err := redis.Get(ctx, cacheKey).Bytes()
    if err == nil && len(cached) > 0 {
        var product Product
        json.Unmarshal(cached, &product)
        return &product, nil
    }
    
    // 2. 查数据库
    var product Product
    if err := db.Where("id = ?", productID).First(&product).Error; err != nil {
        return nil, err
    }
    
    // 3. 写入缓存
    data, _ := json.Marshal(product)
    redis.Set(ctx, cacheKey, data, 5*time.Minute)
    
    return &product, nil
}

func UpdateProduct(ctx context.Context, product *Product) error {
    // 1. 更新数据库
    if err := db.Save(product).Error; err != nil {
        return err
    }
    
    // 2. 删除缓存 (不是更新!)
    cacheKey := fmt.Sprintf("product:%d", product.ID)
    redis.Del(ctx, cacheKey)
    
    return nil
}
```

### 1.2 Read-Through (读穿透)

```go
// 缓存层封装数据库访问
type CacheDB struct {
    redis *redis.Client
    db    *gorm.DB
}

func (c *CacheDB) Get(ctx context.Context, key string) ([]byte, error) {
    // 缓存层统一处理
    cached, err := c.redis.Get(ctx, key).Bytes()
    if err == nil && len(cached) > 0 {
        return cached, nil
    }
    
    // 查DB
    var item Item
    if err := c.db.Where("key = ?", key).First(&item).Error; err != nil {
        return nil, err
    }
    
    // 写入缓存
    data, _ := json.Marshal(item)
    c.redis.Set(ctx, key, data, 10*time.Minute)
    
    return data, nil
}
```

### 1.3 Write-Through (写穿透)

```go
func (c *CacheDB) Set(ctx context.Context, key string, value []byte) error {
    // 1. 同时写入缓存和数据库
    c.redis.Set(ctx, key, value, 0) // 永不过期
    
    // 2. 异步写DB
    go func() {
        var item Item
        json.Unmarshal(value, &item)
        c.db.Save(&item)
    }()
    
    return nil
}
```

### 1.4 Write-Behind (写回)

```go
type WriteBehindCache struct {
    redis  *redis.Client
    db     *gorm.DB
    buffer map[string][]byte  // 写缓冲
    timer  *time.Timer
}

func (c *WriteBehindCache) Set(ctx context.Context, key string, value []byte) {
    // 1. 写入缓存
    c.redis.Set(ctx, key, value, 0)
    
    // 2. 加入缓冲
    c.buffer[key] = value
    
    // 3. 延迟批量写DB
    c.timer = time.AfterFunc(1*time.Second, c.flushBuffer)
}

func (c *WriteBehindCache) flushBuffer() {
    // 批量写入数据库
    for key, value := range c.buffer {
        var item Item
        json.Unmarshal(value, &item)
        c.db.Save(&item)
        delete(c.buffer, key)
    }
}
```

## 二、缓存一致性

### 2.1 延迟双删

```go
// 应对并发更新的缓存一致性方案
func DeleteCacheWithDelay(ctx context.Context, key string) error {
    // 1. 删除缓存
    redis.Del(ctx, key)
    
    // 2. 更新数据库
    
    // 3. 延迟再次删除 (应对并发更新)
    time.Sleep(500 * time.Millisecond)
    redis.Del(ctx, key)
    
    return nil
}
```

### 2.2 Canal监听Binlog

```go
// 使用Canal订阅MySQL Binlog异步更新Redis
func main() {
    client := canal.NewCanal(canalConfig)
    
    client.RegisterEventHandler(&canalEventHandler{
        onUpdate: func(event *canal.Event) {
            // 解析Binlog事件
            row := event.Rows[0]
            key := fmt.Sprintf("user:%s", row["id"])
            
            // 删除或更新缓存
            redis.Del(context.Background(), key)
        },
    })
    
    client.Start()
}
```

### 2.3 分布式锁

```go
// 使用Redis分布式锁保证缓存更新原子性
func UpdateWithLock(ctx context.Context, key string, updateFn func() error) error {
    lockKey := "lock:" + key
    lockValue := uuid.New().String()
    
    // 尝试获取锁
    acquired, err := redis.SetNX(ctx, lockKey, lockValue, 10*time.Second).Result()
    if err != nil || !acquired {
        return errors.New("获取锁失败")
    }
    
    defer redis.Del(ctx, lockKey)
    
    // 执行更新
    if err := updateFn(); err != nil {
        return err
    }
    
    // 删除缓存
    redis.Del(ctx, key)
    
    return nil
}
```

## 三、缓存问题解决方案

### 3.1 缓存穿透

```go
// 方案1: 布隆过滤器
type BloomFilter struct {
    bits   []uint64
    size   int
    hashFn func(string) uint64
}

func (bf *BloomFilter) Add(item string) {
    h := bf.hashFn(item)
    bf.bits[h%uint64(len(bf.bits)*64)] |= 1 << (h % 64)
}

func (bf *BloomFilter) MightContain(item string) bool {
    h := bf.hashFn(item)
    return (bf.bits[h%uint64(len(bf.bits)*64)] >> (h % 64)) & 1 == 1
}

// 方案2: 缓存空值
func GetWithEmptyCache(ctx context.Context, key string) ([]byte, error) {
    cached, err := redis.Get(ctx, key).Bytes()
    if err == redis.Nil {
        // 缓存空值，设置短TTL
        redis.Set(ctx, key, []byte{}, 60*time.Second)
        return nil, errors.New("not found")
    }
    return cached, err
}
```

### 3.2 缓存击穿

```go
// 方案1: 互斥锁
func GetWithMutex(ctx context.Context, key string) ([]byte, error) {
    cached, err := redis.Get(ctx, key).Bytes()
    if err == nil {
        return cached, nil
    }
    
    // 获取锁
    mutexKey := "mutex:" + key
    acquired, _ := redis.SetNX(ctx, mutexKey, "1", 10*time.Second).Result()
    if !acquired {
        // 等待后再试
        time.Sleep(100 * time.Millisecond)
        return redis.Get(ctx, key).Bytes()
    }
    
    defer redis.Del(ctx, mutexKey)
    
    // 双重检查
    cached, err = redis.Get(ctx, key).Bytes()
    if err == nil {
        return cached, nil
    }
    
    // 查询DB并写入缓存
    data := queryDB(key)
    redis.Set(ctx, key, data, 5*time.Minute)
    
    return data, nil
}

// 方案2: 永不过期
redis.Set(ctx, key, data, 0) // 永不过期
```

### 3.3 缓存雪崩

```go
// 方案1: 随机TTL
ttl := 5*time.Minute + time.Duration(rand.Intn(60))*time.Second
redis.Set(ctx, key, data, ttl)

// 方案2: 多级缓存
// L1: 本地缓存 (sync.Map)
// L2: Redis集群

var localCache sync.Map

func GetMultiLevel(ctx context.Context, key string) ([]byte, error) {
    // 1. 查本地缓存
    if v, ok := localCache.Load(key); ok {
        return v.([]byte), nil
    }
    
    // 2. 查Redis
    data, err := redis.Get(ctx, key).Bytes()
    if err == nil {
        localCache.Store(key, data)
        return data, nil
    }
    
    // 3. 查DB
    data = queryDB(key)
    redis.Set(ctx, key, data, 5*time.Minute)
    localCache.Store(key, data)
    
    return data, nil
}
```

## 四、性能优化

### 4.1 Pipeline批量操作

```go
// 批量查询
pipe := redis.Pipeline()
for _, key := range keys {
    pipe.Get(ctx, key)
}
results, err := pipe.Exec()

// 批量写入
pipe = redis.Pipeline()
for key, value := range data {
    pipe.Set(ctx, key, value, ttl)
}
pipe.Exec()
```

### 4.2 连接池配置

```go
rdb := redis.NewClient(&redis.Options{
    Addr:         "localhost:6379",
    Password:     "",
    DB:           0,
    PoolSize:     100,
    MinIdleConns: 10,
    MaxConnAge:   time.Hour,
    PoolTimeout:  time.Second,
    IdleTimeout:  time.Minute,
})
```

### 4.3 序列化优化

```go
// 使用msgpack替代json
import "github.com/vmihailenco/msgpack/v5"

data, _ := msgpack.Marshal(product)
redis.Set(ctx, key, data, ttl)

// 反序列化
var product Product
msgpack.Unmarshal(data, &product)
```

## 五、面试高频题

### 5.1 高频问题

**Q1: Cache-Aside和Read-Through有什么区别？**

A:
- Cache-Aside: 应用层管理缓存，先查缓存再查DB
- Read-Through: 缓存层封装DB，应用只访问缓存

**Q2: 如何解决缓存穿透？**

A:
- 布隆过滤器预判
- 缓存空值
- 参数校验

**Q3: 缓存一致性如何保证？**

A:
- 延迟双删
- Canal监听Binlog
- 分布式锁

### 5.2 自测题

1. 画出四种缓存模式的流程图
2. 分析缓存击穿和缓存雪崩的区别
3. 实现一个带过期时间的缓存
4. 设计多级缓存架构
5. 解释布隆过滤器的原理

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 缓存
**关键词**: redis, cache, consistency, penetration, breakdown
