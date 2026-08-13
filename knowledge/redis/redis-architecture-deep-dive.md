# Redis 核心架构深度蒸馏

> 来源：Redis 官方源码（GitHub）
> 蒸馏日期：2026-01-15
> 核心价值：生产级缓存架构 + 内存优化实战

---

## 一、Redis 内存分配器

### 1.1 线程安全的内存统计

**源码摘录**（`zmalloc.c`）：
```c
/* Per-thread memory accounting slots */
#define DEDICATED_ENTRIES 8
#define SHARED_ENTRIES 8

typedef struct used_memory_entry {
    redisAtomic long long used_memory;
    redisAtomic long long last_peak_check;
    char padding[CACHE_LINE_SIZE - sizeof(long long) - sizeof(long long)];
} used_memory_entry;

static __attribute__((aligned(CACHE_LINE_SIZE))) 
    used_memory_entry used_memory[MAX_ENTRIES];
static redisAtomic size_t num_active_threads = 0;
```

**设计意图**：
```
问题：多线程环境下如何高效统计内存使用？

方案：
1. 前 8 个线程使用专属槽位（原子操作）
2. 后续线程共享哈希槽（CAS 操作）
3. 对齐到 cache line，避免 false sharing
```

**实战应用**：
```go
// 在广告系统中监控 Redis 内存使用
func monitorRedisMemory() {
    // 获取内存统计
    info, _ := redisClient.Info("memory").Result()
    
    // 关键指标
    usedMemory := parseUsedMemory(info)
    peakMemory := parsePeakMemory(info)
    
    // 告警阈值
    if usedMemory > peakMemory * 0.8 {
        log.Warn("Redis memory approaching peak")
    }
}
```

### 1.2 内存分配策略

```c
/* Compile-time jemalloc tuning */
const char *je_malloc_conf =
    "lg_tcache_nslots_mul:3,tcache_nslots_small_max:1000";

/* When using the libc allocator, use a minimum allocation size */
#define MALLOC_MIN_SIZE(x) ((x) > 0 ? (x) : sizeof(long))
```

**我的理解**：
```
jemalloc 配置：
- lg_tcache_nslots_mul:3 → tcache 大小翻倍（8x）
- tcache_nslots_small_max:1000 → 小对象桶上限提升

效果：减少大对象 spill 到 arena，提升性能
```

---

## 二、Redis Object 系统

### 2.1 Object 结构体

**源码摘录**（`object.c`）：
```c
kvobj *kvobjCreate(int type, const sds key, void *ptr, uint32_t keyMetaBits) {
    /* Calculate metadata size */
    uint32_t sizeMetas = getNumMeta(keyMetaBits) * sizeof(uint64_t);
    
    /* Calculate key size */
    size_t key_sds_size = sdsReqSize(key_sds_len, key_sds_type);
    
    /* Compute base object size */
    size_t min_size = sizeof(robj);
    min_size += sizeMetas;
    min_size += 1 + key_sds_size;
    
    /* Allocate memory */
    char *alloc = zmalloc(min_size);
    kvobj *kv = (kvobj *) (alloc + sizeMetas);
    
    return kv;
}
```

**设计洞察**：
```
优化策略：
1. 将 key 嵌入对象内部，减少内存碎片
2. 使用 metadata bits 控制分配的元数据
3. key > 128 字节时自动包含 expire 空间
```

### 2.2 LRU/LFU 实现

**源码摘录**：
```c
void initObjectLRUOrLFU(robj *o) {
    if (o->refcount == OBJ_SHARED_REFCOUNT)
        return;
    
    if (server.maxmemory_policy & MAXMEMORY_FLAG_LFU) {
        o->lru = (LFUGetTimeInMinutes() << 8) | LFU_INIT_VAL;
    } else {
        o->lru = LRU_CLOCK();
    }
}
```

**实战应用**：
```sql
-- 广告系统中的缓存策略
-- 场景：用户画像缓存，需要高频访问

SELECT 
    key,
    lru_score,
    lfu_counter
FROM user_profiles
ORDER BY lfu_counter DESC
LIMIT 1000;

-- 配置
maxmemory-policy allkeys-lfu  -- 基于访问频率淘汰
maxmemory 8gb                 -- 限制内存使用
```

---

## 三、Redis Cluster 架构

### 3.1 Slot 计算

**源码摘录**（`cluster.c`）：
```c
int patternHashSlot(char *pattern, int length) {
    int s = -1;
    
    for (int i = 0; i < length; i++) {
        if (pattern[i] == '*') return -1;  // Wildcard
        
        if (pattern[i] == '{') {
            s = i;  // Found tag
        } else if (pattern[i] == '}' && s >= 0) {
            // Hash the tag content
            return crc16(pattern + s + 1, i - s - 1) & 0x3FFF;
        }
    }
    
    // Hash entire key
    return crc16(pattern, length) & 0x3FFF;
}
```

**设计意图**：
```
问题：如何确定 key 在哪个节点？

方案：
1. CRC16 计算，结果 & 0x3FFF → 0-16383
2. 支持 hash tag：{user123}profile → 只 hash "user123"
3. Wildcard 返回 -1，需要 broadcast
```

**实战配置**：
```bash
# 广告系统中的分片键设计
redis-cli CLUSTER SLOTS

# 推荐的分片键格式
"user:{campaign_id}:profile"  # hash tag 优化
"ad:{ad_id}:stats"           # 按广告 ID 分片
"req:{request_id}"           # 按请求 ID 分片
```

### 3.2 DUMP/RESTORE 机制

```c
/* Generates a DUMP-format representation */
void createDumpPayload(rio *payload, robj *o, robj *key, int dbid, 
                       int flags, size_t size_hint) {
    unsigned char buf[2];
    uint64_t crc = 0;
    
    /* Serialize in RDB-like format */
    sds buffer = sdsnewlen(SDS_NOINIT, size_hint);
    
    // 序列化对象类型 + 数据
    // 添加 CRC 校验
}
```

**应用**：跨集群数据迁移
```bash
# 迁移脚本
for key in $(redis-cli -h source SCAN 0 MATCH "*"); do
    dump=$(redis-cli -h source DUMP "$key")
    redis-cli -h target RESTORE "$key" 0 "$dump" REPLACE
done
```

---

## 四、生产级调优

### 4.1 内存配置

```xml
<!-- redis.conf -->
maxmemory 8gb
maxmemory-policy allkeys-lfu
maxmemory-samples 5

# 碎片率控制
activedefrag yes
activerehashing yes
```

### 4.2 连接池配置

```go
// Go 客户端连接池
import "github.com/go-redis/redis/v8"

rdb := redis.NewClient(&redis.Options{
    Addr:         "localhost:6379",
    Password:     "",
    DB:           0,
    PoolSize:     50,                    // 连接池大小
    MinIdleConns: 10,                    // 最小空闲连接
    MaxConnAge:   time.Hour,             // 连接最大寿命
    PoolTimeout:  time.Second * 4,       // 获取连接超时
    IdleTimeout:  time.Minute * 10,      // 空闲连接超时
})
```

### 4.3 监控指标

```bash
# 关键监控指标
INFO memory          # 内存使用
INFO stats           # 命中率和命令统计
INFO client          # 客户端连接数
CLUSTER INFO         # 集群状态

# 告警规则
used_memory > 80% * maxmemory
rejected_connections > 0
instantaneous_ops_per_sec > 10000
```

---

## 五、核心洞察总结

```
1. 内存管理
   - Per-thread atomic counters 避免锁竞争
   - jemalloc 调优提升小对象分配性能
   - Cache line 对齐减少 false sharing

2. Object 设计
   - Key 嵌入对象减少碎片
   - Metadata bits 灵活控制元数据
   - LRU/LFU 双策略支持

3. Cluster 架构
   - CRC16 + hash tag 优化
   - DUMP/RESTORE 支持迁移
   - 16384 slots 标准化设计
```

---

**核心价值**：Redis 的优雅在于"简单但高效"——线程安全计数、缓存对齐、分片算法，每个设计都经过生产环境验证。
EOF
echo "✅ Redis 深度文档已创建"