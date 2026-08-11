# Redis 内核源码级深度解析

> 深入 Redis 核心：内存模型、数据结构、持久化、集群、性能优化。
> 源码级分析 Redis 4.0/6.0 关键实现，包含调优实战。
> 适用对象：后端工程师、DBA、系统架构师

---

## 1. Redis 架构概览

### 1.1 单线程模型

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Redis 单线程架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Client 1    │    │  Client 2    │    │  Client N    │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             ▼                                       │
│                    ┌─────────────────────┐                          │
│                    │   Connection Pool   │                          │
│                    │   (aeEventLoop)     │                          │
│                    └──────────┬──────────┘                          │
│                               │                                     │
│                               ▼                                     │
│                    ┌─────────────────────┐                          │
│                    │   Command Processor │                          │
│                    │   (单线程处理)       │                          │
│                    └──────────┬──────────┘                          │
│                               │                                     │
│         ┌─────────────────────┼─────────────────────┐               │
│         ▼                     ▼                     ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Key Space   │    │  Eviction    │    │  Pub/Sub     │          │
│  │  (字典)      │    │  (淘汰)      │    │  (发布订阅)   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  AOF Rewrite │    │  RDB Snapshot│    │  Replication │          │
│  │  (异步)      │    │  (异步)      │    │  (异步)      │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 事件驱动模型

```c
// server.c

typedef struct aeEventLoop {
    int maxfd;               /* highest file descriptor *currently* registered */
    int setsize;             /* max number of file descriptors tracked */
    long long timeLimitMicroseconds;
    int timeLoopFlag;
    int finished;            /* when a handle has been signaled finished or the server is requesting a shutdown */
    void *user;              /* custom user data passed to aeProcessEvents */
    
    // 文件事件
    aeFileEvent *events;     /* registered file events */
    aeFiredEvent *fired;     /* fired events */
    
    // 时间事件
    aeTimeEvent *timeEventHead;
    
    int stop;
    void *apidata;           /* this is used for logging */
    
    aeBeforeSleepProc *beforesleep;
    aeBeforeSleepProc *aftersleep;
} aeEventLoop;
```

---

## 2. 数据结构源码解析

### 2.1 字典 (dict)

```c
// dict.h

typedef struct dict {
    dictType *type;
    void *privdata;
    
    dictht ht[2];
    long rehashidx; /* rehashing not in progress if rehashidx == -1 */
    
    int iterators; /* number of iterators currently running */
} dict;

/* If safe is set to 1 this is a safe iterator, that means, you can call
 * dictAdd, dictFind, and other functions against the dictionary even while
 * iterating. Otherwise it is not safe to call any other function than the
 * iterator, the behavior is undefined. */
typedef struct dictIterator {
    dict *d;
    long index;
    int table, safe;
    dictEntry *entry, *nextEntry;
    
    /* unsafe iterator fingerprint for misuse detection. */
    long long fingerprint;
} dictIterator;

typedef struct dictht {
    dictEntry **table;
    unsigned long size;
    unsigned long sizemask;
    unsigned long used;
} dictht;

typedef struct dictEntry {
    void *key;
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next;
} dictEntry;
```

### 2.2 跳表 (skiplist)

```c
// t_zset.h

typedef struct zskiplistNode {
    sds ele;
    double score;
    struct zskiplistNode *backward;
    struct zskiplistLevel {
        struct zskiplistNode *forward;
        unsigned int span;
    } level[];
} zskiplistNode;

typedef struct zskiplist {
    struct zskiplistNode *header, *tail;
    unsigned long length;
    int level;
} zskiplist;
```

### 2.3 快速字符串 (sdshdr)

```c
// sdshdr.h

struct sdshdr8 {
    uint8_t len; /* used */
    uint8_t alloc; /* excluding the header and null terminator */
    unsigned char flags; /* 3 lsb of type, 5 unused bits */
    char buf[];
};

struct sdshdr16 {
    uint16_t len; /* used */
    uint16_t alloc; /* excluding the header and null terminator */
    unsigned char flags; /* 3 lsb of type, 5 unused bits */
    char buf[];
};

struct sdshdr32 {
    uint32_t len; /* used */
    uint32_t alloc; /* excluding the header and null terminator */
    unsigned char flags; /* 3 lsb of type, 5 unused bits */
    char buf[];
};

struct sdshdr64 {
    uint64_t len; /* used */
    uint64_t alloc; /* excluding the header and null terminator */
    unsigned char flags; /* 3 lsb of type, 5 unused bits */
    char buf[];
};
```

---

## 3. 内存管理

### 3.1 内存分配器

```c
// zmalloc.h

#ifdef HAVE_MALLOC_SIZE
#define zmalloc_size(p) malloc_size(p)
#else
#define zmalloc_size(p) (zmalloc_thread_safe_malloc_size(p))
#endif

#define zmalloc_used_memory() zmalloc_thread_safe_used_memory()
#define set_zmalloc_used_memory-hook(x) zmalloc_thread_safe_set_used_memory_hook(x)

void *zmalloc(size_t size);
void *zcalloc(size_t size);
void *zrealloc(void *ptr, size_t size);
void zfree(void *ptr);
char *zstrdup(const char *s);
size_t zmalloc_used_memory(void);
void zmalloc_set_oom_handler(void (*oom_handler)(size_t));
size_t zmalloc_get_rss(void);
int zmalloc_get_allocator_info(size_t *allocated, size_t *active, size_t *resident);
size_t zmalloc_get_allocator_active(void);
size_t zmalloc_get_allocator_resident(void);
size_t zmalloc_get_allocator_allocated(void);
void zmalloc_statistics(char *buf, size_t len);
size_t zmalloc_get_smap_bytes_by_file(char *filename, size_t *anon, size_t *mapped);
size_t zmalloc_get_private_dirty(void);
size_t zmalloc_get_pmap_bytes_by_file(char *filename, size_t *rss, size_t *pss);
size_t zmalloc_get_usable_size(size_t size);
void zmalloc_set_purge_enabled(int enabled);
int zmalloc_get_purge_enabled(void);
int zmalloc_get_defrag_stats(size_t *defrag_runs, size_t *defrag_misses);
int zmalloc_get_fragmentation_ratio(size_t *rss, size_t *alloc);
int zmalloc_get_lazy_free(void);
void zmalloc_set_maxmemory_size(size_t size);
size_t zmalloc_get_maxmemory_size(void);
```

### 3.2 内存淘汰策略

```c
// eviction.c

typedef enum {
    EVICT_NONE = -1,
    EVICT_LRU = 0,
    EVICT_LFU = 1,
    EVICT_RANDOM = 2,
    EVICT_TTL = 3
} evict_policy_t;

int getEvictionPolicy(void) {
    if (server.maxmemory_policy == MAXMEMORY_ALLKEYS_LRU)
        return EVICT_LRU;
    else if (server.maxmemory_policy == MAXMEMORY_ALLKEYS_LFU)
        return EVICT_LFU;
    else if (server.maxmemory_policy == MAXMEMORY_ALLKEYS_RANDOM)
        return EVICT_RANDOM;
    else if (server.maxmemory_policy == MAXMEMORY_VOLATILE_LRU)
        return EVICT_LRU;
    else if (server.maxmemory_policy == MAXMEMORY_VOLATILE_LFU)
        return EVICT_LFU;
    else if (server.maxmemory_policy == MAXMEMORY_VOLATILE_RANDOM)
        return EVICT_RANDOM;
    else if (server.maxmemory_policy == MAXMEMORY_VOLATILE_TTL)
        return EVICT_TTL;
    else
        return EVICT_NONE;
}

int prepareForEviction(void) {
    // 计算可用内存
    size_t mem_fragmentation = zmalloc_get_fragmentation_ratio(NULL, NULL);
    size_t mem_allocator_active = zmalloc_get_allocator_active();
    
    // 设置淘汰阈值
    if (server.maxmemory != 0) {
        size_t available = server.maxmemory - mem_allocator_active;
        if (available < server.maxmemory / 10) {
            // 触发淘汰
            return 1;
        }
    }
    return 0;
}
```

---

## 4. 持久化机制

### 4.1 RDB 实现

```c
// rdb.c

int rdbSave(char *filename) {
    dict *d = server.db[0].dict;
    dictIterator *iter = dictCreate(&rdbDictIteratorType, NULL);
    dictEntry *de;
    
    // 打开文件
    FILE *fp = fopen(filename, "w");
    if (!fp) {
        serverLog(LL_WARNING, "Failed opening %s for RDB save: %s", 
                  filename, strerror(errno));
        return C_ERR;
    }
    
    // 写魔数
    if (rdbSaveMagicHeader(fp) != C_OK) {
        fclose(fp);
        return C_ERR;
    }
    
    // 遍历所有键
    dictRewind(d);
    while ((de = dictNext(d)) != NULL) {
        sds key = dictGetKey(de);
        robj *val = dictGetVal(de);
        
        // 保存键值对
        if (rdbSaveKey(fp, key, val) != C_OK) {
            fclose(fp);
            return C_ERR;
        }
    }
    
    // 写检查点
    if (rdbSaveCheckPoint(fp) != C_OK) {
        fclose(fp);
        return C_ERR;
    }
    
    fclose(fp);
    return C_OK;
}
```

### 4.2 AOF 实现

```c
// aof.c

int aofWrite(int fd, const char *buf, size_t len) {
    if (server.aof_fsync == AOF_FSYNC_ALWAYS) {
        // 每次都 fsync
        ssize_t nwritten = write(fd, buf, len);
        fsync(fd);
        return nwritten;
    } else if (server.aof_fsync == AOF_FSYNC_EVERYSEC) {
        // 每秒 fsync
        if (server.aof_fsync_offset == server.aof_written_size) {
            ssize_t nwritten = write(fd, buf, len);
            server.aof_written_size += nwritten;
            return nwritten;
        } else {
            // 后台 fsync
            ssize_t nwritten = write(fd, buf, len);
            server.aof_written_size += nwritten;
            if (server.aof_fsync_offset < server.aof_written_size - BUF_MAX) {
                aof_background_fsync();
            }
            return nwritten;
        }
    } else {
        // 不 fsync
        return write(fd, buf, len);
    }
}

void aofBackgroundFsync(void) {
    if (server.aof_child_pid == -1) {
        if (forkandwrite(AOF_FORK_BG) == -1) {
            serverLog(LL_WARNING, "Can't save in background: fork failed");
            return;
        }
    }
}
```

---

## 5. 集群架构

### 5.1 数据分片

```c
// cluster.c

#define CLUSTER_SLOTS 16384

int clusterAddSlot(int slot) {
    if (slot < 0 || slot >= CLUSTER_SLOTS) {
        return C_ERR;
    }
    
    clusterNode *node = getNodeBySlot(slot);
    if (!node) {
        // 创建新节点
        node = createClusterNode();
    }
    
    // 添加槽位
    node->slots[slot] = 1;
    node->slots_count++;
    
    // 更新集群状态
    clusterUpdateState();
    
    return C_OK;
}

clusterNode *getNodeBySlot(int slot) {
    for (int i = 0; i < server.cluster->nodes->dict->ht[0].used; i++) {
        dictEntry *de = dictGetEntryByIndex(server.cluster->nodes->dict, i);
        clusterNode *node = dictGetVal(de);
        
        if (node->slots[slot]) {
            return node;
        }
    }
    return NULL;
}
```

### 5.2 故障转移

```c
// cluster.c

int clusterFailover(void) {
    // 1. 检查是否可以故障转移
    if (!clusterCanFailover(CLUSTER_FAILOVER_FORCE)) {
        return C_ERR;
    }
    
    // 2. 请求其他节点投票
    clusterSendFailoverAuthorize();
    
    // 3. 等待投票结果
    if (!clusterWaitFailoverAuthorize()) {
        return C_ERR;
    }
    
    // 4. 执行故障转移
    clusterDoFailover();
    
    return C_OK;
}

void clusterDoFailover(void) {
    // 1. 接管主节点槽位
    clusterAssignSlots(server.master);
    
    // 2. 广播新状态
    clusterBroadcastNewState();
    
    // 3. 更新配置
    clusterUpdateConfig();
}
```

---

## 6. 性能优化实战

### 6.1 配置优化

```conf
# redis.conf 优化建议

# 内存管理
maxmemory 2gb
maxmemory-policy allkeys-lru

# 持久化
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite no

# 网络
tcp-backlog 511
timeout 0
tcp-keepalive 300

# 集群
cluster-node-timeout 5000
cluster-migration-barrier 1

# 线程
io-threads 4
io-threads-do-reads yes
```

### 6.2 监控指标

```bash
# 内存使用
redis-cli info memory

# 连接数
redis-cli info clients

# 命令统计
redis-cli info commandstats

# 键统计
redis-cli info keyspace

# 复制状态
redis-cli info replication

# 集群状态
redis-cli -c cluster info
```

### 6.3 慢查询分析

```sql
-- 开启慢查询日志
redis-cli config set slowlog-log-slower-than 10000
redis-cli config set slowlog-max-len 128

-- 查看慢查询
redis-cli slowlog get 10

-- 重置慢查询
redis-cli slowlog reset
```

---

## 7. 故障排查

### 7.1 内存问题

```bash
# 检查内存碎片
redis-cli info memory | grep used_memory

# 检查大键
redis-cli --bigkeys

# 检查内存分布
redis-cli --stat
```

### 7.2 性能问题

```bash
# 监控实时性能
redis-cli --latency

# 检查网络延迟
redis-cli --latency-history

# 检查命令分布
redis-cli --topkey
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 | 关键优化点 |
|------|----------|-----------|
| 单线程 | 事件驱动 | 避免上下文切换 |
| 数据结构 | SDS/跳表/字典 | 内存复用 |
| 持久化 | RDB+AOF | 异步合并 |
| 集群 | 哈希槽 | 自动分片 |

### 8.2 性能调优 Checklist

- [ ] 设置合适的 maxmemory
- [ ] 选择合适的淘汰策略
- [ ] 启用 AOF 持久化
- [ ] 调整 io-threads
- [ ] 定期监控内存碎片
- [ ] 避免大键

---

*最后更新：2026-08-11*
*作者：Ryan*
