# 系统设计面试深度解析

> 深入系统设计面试核心：缓存、消息队列、数据库分片、分布式ID、限流等经典问题。
> 包含真实的系统设计思考和权衡分析。
> 适用对象：准备高级工程师面试的开发者、系统设计师

---

## 1. URL 短链系统设计

### 1.1 需求分析

```
功能需求：
1. 长链接 → 短链接
2. 短链接 → 重定向到原链接
3. 支持自定义短码
4. 支持链接过期
5. 支持点击统计

非功能需求：
- 读写比 10000:1
- P99 延迟 < 50ms
- 可用性 99.99%
- 数据存储 10 年
```

### 1.2 方案一：哈希取模

```python
# 方案一：简单哈希
import hashlib
import base64

def short_url_hash(long_url: str, length: int = 6) -> str:
    """基于哈希的短链生成"""
    # MD5 取前 N 位
    md5 = hashlib.md5(long_url.encode()).hexdigest()
    # base62 编码
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    num = int(md5[:16], 16)
    result = []
    for _ in range(length):
        result.append(chars[num % 62])
        num //= 62
    return ''.join(result)
```

**问题**：冲突率高，需要处理冲突

### 1.3 方案二：数据库自增 ID

```sql
-- 表结构
CREATE TABLE short_urls (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    long_url VARCHAR(2048) NOT NULL,
    short_code CHAR(6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    click_count INT DEFAULT 0,
    UNIQUE KEY uk_short_code (short_code)
);

-- 短码生成
def generate_short_code(id: int) -> str:
    """将 ID 转换为 6 位短码"""
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    result = []
    while id > 0:
        result.append(chars[id % 62])
        id //= 62
    # 补齐 6 位
    while len(result) < 6:
        result.append('0')
    return ''.join(reversed(result))
```

**优点**：无冲突，简单可靠
**缺点**：单点瓶颈，需要分库分表

### 1.4 方案三：分布式 ID

```python
# Twitter Snowflake 改进版
import time
import random

class SnowflakeID:
    def __init__(self, worker_id: int, datacenter_id: int):
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1
    
    def generate(self) -> int:
        timestamp = self._current_millis()
        
        if timestamp < self.last_timestamp:
            raise Exception("Clock moved backwards")
        
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & 0xFFF
            if self.sequence == 0:
                timestamp = self._wait_next_ms()
        else:
            self.sequence = random.randint(0, 0xFFF)
        
        self.last_timestamp = timestamp
        
        # 组合 ID
        return ((timestamp - self.EPOCH) << 22) | \
               (self.datacenter_id << 17) | \
               (self.worker_id << 12) | \
               self.sequence
    
    def _current_millis(self) -> int:
        return int(time.time() * 1000)
    
    def _wait_next_ms(self):
        while self.last_timestamp >= self._current_millis():
            pass
        return self._current_millis()
```

### 1.5 完整架构

```
┌─────────────────────────────────────────────────────────────┐
│                      短链系统架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ Client  │    │  API    │    │  Redis  │                │
│  └────┬────┘    └────┬────┘    └────┬────┘                │
│       │              │              │                      │
│       └──────────────┼──────────────┘                      │
│                      ▼                                     │
│              ┌─────────────────┐                           │
│              │  短链服务集群    │                           │
│              │  (Nginx + Go)   │                           │
│              └────────┬────────┘                           │
│                       │                                    │
│         ┌─────────────┼─────────────┐                     │
│         ▼             ▼             ▼                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │  写服务   │  │  读服务   │  │  统计服务 │                │
│  │ (创建短链)│  │ (重定向)  │  │ (点击统计)│                │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                │
│       │             │             │                       │
│       └─────────────┼─────────────┘                       │
│                     ▼                                     │
│            ┌─────────────────┐                            │
│            │   MySQL 集群     │                            │
│            │   (分库分表)     │                            │
│            └─────────────────┘                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 分布式锁设计

### 2.1 基于 Redis 的实现

```go
// redis_lock.go

type Redlock struct {
    clients []*redis.Client
    nonce   []byte
}

func NewRedlock(addrs []string) *Redlock {
    clients := make([]*redis.Client, len(addrs))
    for i, addr := range addrs {
        clients[i] = redis.NewClient(&redis.Options{
            Addr: addr,
        })
    }
    return &Redlock{
        clients: clients,
        nonce:   generateNonce(16),
    }
}

func (m *Redlock) Lock(key string, ttl time.Duration) (bool, error) {
    // 1. 尝试在所有节点上设置锁
    n := 0
    startTime := time.Now()
    var errors []error
    
    for _, client := range m.clients {
        ok, err := client.SetNX(key, m.nonce, ttl).Result()
        if err != nil {
            errors = append(errors, err)
            continue
        }
        if ok {
            n++
        }
    }
    
    // 2. 检查是否获得多数派
    quorum := len(m.clients)/2 + 1
    if n < quorum {
        // 释放已获取的锁
        m.Unlock(key)
        return false, nil
    }
    
    // 3. 计算 TTL（防止时钟漂移）
    elapsed := time.Since(startTime)
    effectiveTTL := ttl - elapsed
    
    // 4. 启动续期协程
    go m.renewLock(key, effectiveTTL)
    
    return true, nil
}

func (m *Redlock) Unlock(key string) error {
    // Lua 脚本原子删除
    script := `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        end
        return 0
    `
    
    var wg sync.WaitGroup
    var errors []error
    
    for _, client := range m.clients {
        wg.Add(1)
        go func(c *redis.Client) {
            defer wg.Done()
            _, err := c.Eval(script, []string{key}, m.nonce).Result()
            if err != nil {
                errors = append(errors, err)
            }
        }(client)
    }
    
    wg.Wait()
    return nil
}
```

### 2.2 基于 ZooKeeper 的实现

```java
// zk_lock.java

public class ZooKeeperLock {
    private final ZooKeeper zk;
    private final String lockPath;
    private final String nodeId;
    
    public ZooKeeperLock(ZooKeeper zk, String lockPath) {
        this.zk = zk;
        this.lockPath = lockPath;
        this.nodeId = UUID.randomUUID().toString();
    }
    
    public boolean lock() throws Exception {
        // 1. 创建临时顺序节点
        String nodeName = zk.create(
            lockPath + "/lock-",
            nodeId.getBytes(),
            ZooDefs.Ids.OPEN_ACL_UNSAFE,
            CreateMode.EPHEMERAL_SEQUENTIAL
        );
        
        // 2. 获取所有子节点
        List<String> children = zk.getChildren(lockPath, false);
        Collections.sort(children);
        
        // 3. 判断是否是第一个
        int index = children.indexOf(nodeName.split("/")[1]);
        if (index == 0) {
            // 获得锁
            return true;
        }
        
        // 4. 监听前一个节点
        String prevNode = children.get(index - 1);
        CountDownLatch latch = new CountDownLatch(1);
        
        zk.exists(lockPath + "/" + prevNode, event -> {
            if (event.getType() == WatchType.NODE_DELETED) {
                latch.countDown();
            }
        });
        
        // 5. 等待锁
        latch.await();
        return true;
    }
    
    public void unlock() throws Exception {
        String nodeName = lockPath + "/" + 
            zk.getChildren(lockPath, false)
                .stream()
                .filter(n -> n.contains(nodeId))
                .findFirst()
                .orElse("");
        zk.delete(nodeName, -1);
    }
}
```

---

## 3. 分布式 ID 设计

### 3.1 Snowflake 算法

```go
// snowflake.go

type Snowflake struct {
    workerID     int64
    datacenterID int64
    sequence     int64
    lastTime     int64
}

const (
    epoch        = 1288834974657  // Twitter 时间戳
    workerBits   = 5
    datacenterBits = 5
    sequenceBits = 12
    
    maxWorkerID    = -1 ^ (-1 << workerBits)
    maxDatacenterID = -1 ^ (-1 << datacenterBits)
    
    workerShift    = sequenceBits
    datacenterShift = sequenceBits + workerBits
    timestampShift = sequenceBits + workerBits + datacenterBits
)

func NewSnowflake(workerID, datacenterID int64) *Snowflake {
    if workerID > maxWorkerID {
        panic(fmt.Sprintf("worker ID can't be greater than %d", maxWorkerID))
    }
    if datacenterID > maxDatacenterID {
        panic(fmt.Sprintf("datacenter ID can't be greater than %d", maxDatacenterID))
    }
    return &Snowflake{
        workerID:     workerID,
        datacenterID: datacenterID,
    }
}

func (s *Snowflake) NextID() int64 {
    mu.Lock()
    defer mu.Unlock()
    
    timestamp := time.Now().UnixNano() / 1e6
    
    if timestamp < s.lastTime {
        panic("clock moved backwards")
    }
    
    if timestamp == s.lastTime {
        s.sequence = (s.sequence + 1) & ((1 << sequenceBits) - 1)
        if s.sequence == 0 {
            timestamp = s.waitNextMillis()
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTime = timestamp
    
    return ((timestamp - epoch) << timestampShift) |
        (s.datacenterID << datacenterShift) |
        (s.workerID << workerShift) |
        s.sequence
}
```

### 3.2 数据库方案

```sql
-- 号段模式
CREATE TABLE id_generator (
    biz_type VARCHAR(32) PRIMARY KEY,
    current_max_id BIGINT NOT NULL,
    step INT NOT NULL DEFAULT 100,
    version INT DEFAULT 0
);

-- 获取 ID 的存储过程
DELIMITER //
CREATE PROCEDURE get_id(IN p_biz_type VARCHAR(32), OUT p_id BIGINT)
BEGIN
    DECLARE v_current_max_id BIGINT;
    DECLARE v_step INT;
    
    SELECT current_max_id, step INTO v_current_max_id, v_step
    FROM id_generator
    WHERE biz_type = p_biz_type
    FOR UPDATE;
    
    SET p_id = v_current_max_id;
    
    UPDATE id_generator 
    SET current_max_id = current_max_id + step,
        version = version + 1
    WHERE biz_type = p_biz_type;
END //
DELIMITER ;
```

---

## 4. 缓存设计

### 4.1 缓存穿透

```python
# 布隆过滤器方案
import pybloom_live

class CacheProtection:
    def __init__(self, capacity: int, error_rate: float = 0.001):
        self.bloom = pybloom_live.BloomFilter(capacity, error_rate)
        self.cache = {}
        self.lock = threading.Lock()
    
    def get(self, key: str):
        # 1. 布隆过滤器判断
        if key not in self.bloom:
            return None  # 肯定不存在
        
        # 2. 查缓存
        if key in self.cache:
            return self.cache[key]
        
        # 3. 查数据库
        value = self.db.get(key)
        if value:
            self.cache[key] = value
            self.bloom.add(key)
        else:
            # 缓存空值
            self.cache[key] = None
        return value
```

### 4.2 缓存雪崩

```python
# TTL 随机化
import random

def set_cache(key: str, value: any, base_ttl: int = 3600):
    # 添加随机抖动
    jitter = random.randint(0, base_ttl // 4)
    ttl = base_ttl + jitter
    redis.setex(key, ttl, value)
```

### 4.3 缓存击穿

```python
# 互斥锁方案
import threading

class CacheWithMutex:
    def __init__(self):
        self.cache = {}
        self.locks = {}
        self.lock = threading.Lock()
    
    def get(self, key: str, loader: callable):
        # 1. 查缓存
        if key in self.cache:
            return self.cache[key]
        
        # 2. 获取锁
        with self.lock:
            if key not in self.locks:
                self.locks[key] = threading.Lock()
        
        mutex = self.locks[key]
        
        # 3. 双重检查
        if key in self.cache:
            return self.cache[key]
        
        # 4. 加锁查询
        with mutex:
            if key not in self.cache:
                value = loader(key)
                self.cache[key] = value
        
        return self.cache[key]
```

---

## 5. 限流设计

### 5.1 令牌桶

```go
// 令牌桶实现
type TokenBucket struct {
    tokens     float64
    maxTokens  float64
    rate       float64 // 每秒补充
    lastTime   time.Time
    mu         sync.Mutex
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    tb.tokens += rate * now.Sub(tb.lastTime).Seconds()
    if tb.tokens > tb.maxTokens {
        tb.tokens = tb.maxTokens
    }
    tb.lastTime = now
    
    if tb.tokens >= 1 {
        tb.tokens -= 1
        return true
    }
    return false
}
```

### 5.2 滑动窗口

```go
// 滑动窗口实现
type SlidingWindow struct {
    windowSize time.Duration
    maxRequests int
    records []Record
    mu sync.Mutex
}

type Record struct {
    timestamp time.Time
    count int
}

func (sw *SlidingWindow) Allow() bool {
    sw.mu.Lock()
    defer sw.mu.Unlock()
    
    now := time.Now()
    cutoff := now.Add(-sw.windowSize)
    
    // 清理过期记录
    valid := make([]Record, 0)
    total := 0
    for _, r := range sw.records {
        if r.timestamp.After(cutoff) {
            valid = append(valid, r)
            total += r.count
        }
    }
    sw.records = valid
    
    if total >= sw.maxRequests {
        return false
    }
    
    sw.records = append(sw.records, Record{now, 1})
    return true
}
```

---

## 6. 消息队列设计

### 6.1 保证消息不丢失

```go
// 生产者确认
func (p *Producer) Send(msg Message) error {
    // 1. 发送消息
    err := p.client.Publish(msg)
    if err != nil {
        return err
    }
    
    // 2. 等待确认
    confirm := <-p.confirmCh
    
    if !confirm.Ack {
        return fmt.Errorf("message not confirmed")
    }
    
    // 3. 持久化到本地
    p.persist(msg)
    
    return nil
}
```

### 6.2 顺序消息

```go
// 基于分区的顺序消息
func (p *Producer) SendOrdered(msg Message, shardKey string) error {
    // 1. 根据 key 计算分区
    partition := hash(shardKey) % numPartitions
    
    // 2. 发送到指定分区
    return p.client.SendToPartition(msg, partition)
}

// 消费者保证顺序消费
func (c *Consumer) Process(partition int, messages []Message) {
    // 同一分区内的消息按序处理
    for _, msg := range messages {
        c.handle(msg)
    }
}
```

---

## 7. 总结

### 7.1 设计权衡总结

| 场景 | 方案 | 权衡 |
|------|------|------|
| 短链生成 | 哈希 vs ID | 冲突率 vs 简单性 |
| 分布式锁 | Redis vs ZK | 性能 vs 强一致性 |
| 分布式 ID | Snowflake vs DB | 性能 vs 可靠 |
| 缓存防护 | 布隆 vs 空值 | 复杂度 vs 准确性 |
| 限流算法 | 令牌桶 vs 滑动窗口 | 平滑 vs 精确 |

### 7.2 面试要点

1. **需求澄清**：明确功能需求和非功能需求
2. **方案设计**：给出多种方案并分析优劣
3. **深入细节**：展示对核心问题的理解
4. **权衡分析**：说明为什么选择这个方案
5. **扩展思考**：讨论优化和可能的改进

---

*最后更新：2026-08-11*
*作者：Ryan*
