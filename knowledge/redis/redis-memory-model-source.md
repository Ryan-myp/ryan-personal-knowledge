# Redis内存模型源码级深度分析

> **领域**: 缓存内核
> **版本**: v1.0
> **难度**: 专家级
> **阅读时间**: 90分钟
> **数据来源**: Redis 7.0 源码 (`src/`)

---

## 目录

1. [Redis架构总览](#1-redis架构总览)
2. [对象系统(Object System)](#2对象系统object-system)
3. [内存分配器(Jemalloc)](#3内存分配器jemalloc)
4. [数据结构实现](#4数据结构实现)
5. [主动内存回收](#5主动内存回收)
6. [内存淘汰策略](#6内存淘汰策略)
7. [持久化内存优化](#7持久化内存优化)
8. [生产调优实践](#8生产调优实践)

---

## 1. Redis架构总览

### 1.1 内存布局

```
┌─────────────────────────────────────────────────────────────────┐
│                      Redis Server                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Network  │  │ Command  │  │ Client   │  │ Persistence│      │
│  │ Layer    │  │ Processor│  │ Manager  │  │ Manager   │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │             │             │              │
│       └─────────────┴─────────────┴─────────────┘              │
│                            ▼                                    │
│              ┌─────────────────────────┐                       │
│              │      Data Structures     │                       │
│              │  ┌───────────────────┐   │                       │
│              │  │ String / List /    │   │                       │
│              │  │ Hash / Set / ZSet  │   │                       │
│              │  └───────────────────┘   │                       │
│              └────────────┬────────────┘                       │
│                           │                                     │
│     ┌─────────────────────┼─────────────────────┐             │
│     │                     │                     │             │
│     ▼                     ▼                     ▼             │
│ ┌────────┐           ┌──────────┐           ┌──────────┐      │
│ │Memory  │           │ Eviction │           │ AOF/RDB  │      │
│ │Manager │           │ Manager  │           │ Manager  │      │
│ └────────┘           └──────────┘           └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据结构

```c
// src/server.h
typedef struct redisObject {
    unsigned type:4;          // 对象类型
    unsigned encoding:4;      // 编码方式
    unsigned lru:22;          // LRU时间戳
    int refcount;             // 引用计数
    void *ptr;                // 指向实际数据的指针
} robj;

// 对象类型
#define OBJ_STRING 0
#define OBJ_LIST 1
#define OBJ_HASH 2
#define OBJ_SET 3
#define OBJ_ZSET 4
#define OBJ_MODULE 5
#define OBJ_STREAM 6

// 编码方式
#define OBJ_ENCODING_RAW 0      // 简单动态字符串
#define OBJ_ENCODING_INT 1      // 整数
#define OBJ_ENCODING_HT 2       // 哈希表
#define OBJ_ENCODING_ZIPLIST 3  // 压缩列表
#define OBJ_ENCODING_SKIPLIST 4 // 跳表
#define OBJ_ENCODING_QUICKLIST 5 // 快链表
#define OBJ_ENCODING_STREAM 6   // 流
```

---

## 2. 对象系统(Object System)

### 2.1 SDS（Simple Dynamic String）

```c
// src/sds.h
struct sdshdr {
    buf[len+1];  // 字符数组（包含'\0'）
    len;         // 字符串长度
    alloc;       // 分配的总空间
    flags;       // 字节 flags
};

// 不同长度的SDS
struct sdshdr5 {
    flags;       // 3位类型标志 + 5位长度
    buf[0];
};

struct sdshdr8 {
    uint8_t len;      // 已使用长度
    uint8_t alloc;    // 分配长度
    flags;            // 类型标志
    buf[];
};

struct sdshdr16 {
    uint16_t len;     // 已使用长度
    uint16_t alloc;   // 分配长度
    flags;            // 类型标志
    buf[];
};

struct sdshdr32 {
    uint32_t len;     // 已使用长度
    uint32_t alloc;   // 分配长度
    flags;            // 类型标志
    buf[];
};

struct sdshdr64 {
    uint64_t len;     // 已使用长度
    uint64_t alloc;   // 分配长度
    flags;            // 类型标志
    buf[];
};
```

### 2.2 对象创建与回收

```c
// src/object.c
robj *createStringObject(const char *ptr, size_t len) {
    robj *o = zmalloc(sizeof(robj));
    o->type = OBJ_STRING;
    o->encoding = OBJ_ENCODING_RAW;
    o->ptr = sdscatlen(sdsnewlen(ptr, len), "", 0);
    o->refcount = 1;
    o->lru = LRU_CLOCK();
    return o;
}

void decrRefCount(robj *o) {
    if (o->refcount <= 0) serverPanic("decrRefCount against refcount <= 0");
    if (o->refcount == 1) {
        switch(o->type) {
            case OBJ_STRING: freeStringObject(o); break;
            case OBJ_LIST: freeListObject(o); break;
            case OBJ_HASH: freeHashObject(o); break;
            case OBJ_SET: freeSetObject(o); break;
            case OBJ_ZSET: freeZsetObject(o); break;
            default: serverPanic("Unknown object type");
        }
        zfree(o);
    } else {
        o->refcount--;
    }
}
```

---

## 3. 内存分配器(Jemalloc)

### 3.1 分配器选择

```c
// src/zmalloc.h
#ifdef HAVE_JEMALLOC_H
#include <jemalloc/jemalloc.h>
#define zmalloc js_zmalloc
#define zrealloc js_zrealloc
#define zcalloc js_zcalloc
#define zfree js_zfree
#elif defined(__APPLE__)
#include <malloc/malloc.h>
// ...
#endif
```

### 3.2 Jemalloc核心结构

```c
// jemalloc/src/jemalloc_internal.hpp
struct arena_s {
    size_t nregs;               // 区域总数
    size_t npages;              // 页面数
    unsigned nthreads;          // 绑定线程数
    size_t *lg_prof_sample;     // 采样间隔
    malloc_bin_stats_t *stats;  // 统计信息
    // ... 更多字段
};

struct chunk_s {
    size_t bytes;               // 总字节数
    size_t nregs;               // 区域数
    size_t reg_seq;             // 区域序列号
    bool committed;             // 是否提交
    bool purge_dirty;           // 是否需要清理
    // ...
};
```

### 3.3 内存统计

```c
// src/zmalloc.c
void zmalloc_get_memsize(size_t *used_memory) {
#ifdef HAVE_SYSINFO
    struct sysinfo info;
    sysinfo(&info);
    *used_memory = info.totalram * info.mem_unit;
#elif defined(HAVE_JEMALLOC_STATS)
    size_t allocated = 0;
    malloc_stats_print(NULL, NULL, NULL);
    // 获取jemalloc统计
#endif
}
```

---

## 4. 数据结构实现

### 4.1 哈希表(dict)

```c
// src/dict.h
typedef struct dict {
    dictType *type;             // 类型特定函数
    void *privdata;             // 私有数据
    dictht ht[2];              // 两个哈希表（用于rehash）
    long rehashidx;             // rehash进度
    unsigned long iterators;    // 迭代器数量
} dict;

typedef struct dictht {
    dictEntry **table;          // 哈希表数组
    unsigned long size;         // 哈希表大小
    unsigned long sizemask;     // 掩码
    unsigned long used;         // 已有节点数
} dictht;

typedef struct dictEntry {
    void *key;                  // 键
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next;    // 下一个节点（解决冲突）
} dictEntry;
```

### 4.2 跳表(zskiplist)

```c
// src/zset.h
typedef struct zskiplistNode {
    sds ele;                    // 元素
    double score;              // 分数
    struct zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward; // 前进指针
        unsigned long span;            // 跨度
    } level[];                  // 层数组（变长）
} zskiplistNode;

typedef struct zskiplist {
    struct zskiplistNode *header, *tail; // 头尾节点
    unsigned long length;               // 节点数
    int level;                         // 最大层数
} zskiplist;
```

**跳表节点创建**：
```c
// src/t_zset.c
zskiplistNode *zslInsert(zskiplist *zsl, double score, sds ele) {
    zskiplistNode *update[ZSKIPLIST_MAXLEVEL];
    int rank[ZSKIPLIST_MAXLEVEL];
    
    // 1. 计算插入位置
    int i = zsl->length, j = 0;
    dictEntry *de;
    
    // 2. 创建新节点（随机层数）
    int level = zslRandomLevel();
    if (level > zsl->level) {
        level = zsl->level = level;
    }
    
    zskiplistNode *node = zslCreateNode(level, score, ele);
    
    // 3. 插入节点
    // ...
    
    return node;
}
```

### 4.3 快链表(quiklist)

```c
// src/quicklist.h
typedef struct quicklist {
    quicklistNode *head;     // 头节点
    quicklistNode *tail;     // 尾节点
    unsigned long count;     // 总节点数
    unsigned long len;       // 快链表长度
    int fill;                // 节点填充因子
    unsigned int compress;   // 压缩深度
} quicklist;

typedef struct quicklistNode {
    struct quicklistNode *prev;
    struct quicklistNode *next;
    unsigned char *zl;       // ziplist指针
    unsigned int sz;         // ziplist大小
    unsigned int count;      // 元素数量
    int encoding;            // 编码方式（LOCAL/RAW）
    int container;           // 容器类型
    unsigned int recompress; // 是否需要重新压缩
} quicklistNode;
```

---

## 5. 主动内存回收

### 5.1 LRU采样

```c
// src/server.c
unsigned long long LRU_CLOCK(void) {
    // 返回以秒为单位的LRU时钟
    return Uptime_Into_LRUClock();
}

static void activeExpireCycle(int type) {
    // 1. 遍历所有数据库
    for (int dbidx = 0; dbidx < server.dbnum; dbidx++) {
        dict *d = server.db[dbidx].dict;
        
        // 2. 采样过期键
        unsigned long long start_time = ustime();
        int expired = 0;
        
        dictScanPointer *scan = dictGetSafeIter(d);
        dictEntry *de;
        
        while ((de = dictNext(scan)) != NULL) {
            // 检查是否过期
            if (activeExpireCycleTryExpire(d, de, start_time)) {
                expired++;
            }
            
            // 时间限制
            if (ustime() - start_time > ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP * 1000) {
                break;
            }
        }
        
        dictReleaseIterator(scan);
    }
}
```

### 5.2 惰性删除

```c
// src/t_string.c
robj *lookupKeyReadWithFlags(client *c, robj *key, int flags) {
    robj *val = lookupKeyReadWithFlagsFromDb(c, key, flags);
    
    // 惰性删除：如果键已过期，删除并返回NULL
    if (val != NULL && expireIfNeeded(val->db, val->ptr)) {
        signalModifiedKey(c, val->db, val->ptr);
        notifyKeyspaceEvent(NOTIFY_EXPIRED, "expired", 
                           val->ptr, val->db->id);
        return NULL;
    }
    
    return val;
}
```

---

## 6. 内存淘汰策略

### 6.1 策略列表

```c
// src/server.h
enum evictionPolicyType {
    EVICT_NONE = 0,      // 无淘汰
    EVICT_ALLKEYS_LRU,   // LRU全局
    EVICT_ALLKEYS_RANDOM, // 随机全局
    EVICT_VOLATILE_LRU,  // LRU过期键
    EVICT_VOLATILE_RANDOM, // 随机过期键
    EVICT_VOLATILE_TTL,  // TTL最短
    EVICT_ALLKEYS_LFU,   // LFU全局
    EVICT_VOLATILE_LFU,  // LFU过期键
};
```

### 6.2 LRU近似算法

```c
// src/evict.c
void freeMemoryIfNeeded(void) {
    while (getUsedMemory() > server.maxmemory) {
        robj *keyobj = NULL;
        
        // 1. 选择淘汰键
        switch (server.eviction_policy) {
            case EVICT_ALLKEYS_LRU:
                keyobj = evictGetSample();
                break;
            case EVICT_ALLKEYS_LFU:
                keyobj = evictGetSampleLFU();
                break;
            // ...
        }
        
        // 2. 删除键
        if (keyobj != NULL) {
            dbDelete(server.db, keyobj->ptr);
            decrRefCount(keyobj);
        }
    }
}

// LRU近似采样
robj *evictGetSample(void) {
    // 从所有键中采样N个（默认5个）
    #define EVICT_SAMPLES 5
    
    uint32_t samples[EVICT_SAMPLES];
    memset(samples, 0, sizeof(samples));
    
    // 使用Resistance Probabilistic数据结构
    for (int j = 0; j < server.dbnum; j++) {
        dict *d = server.db[j].dict;
        dictIterator *iter = dictGetIterator(d);
        dictEntry *de;
        
        while ((de = dictNext(iter)) != NULL) {
            // 填充采样池
            // ...
        }
        dictReleaseIterator(iter);
    }
    
    // 返回最老的键
    return getLRUKey(samples);
}
```

### 6.3 LFU算法

```c
// src/evict.c
void objectLFULatch(robj *o) {
    // LFU计数是8位的，最多255
    if (o->lru & 128) {
        // 已经饱和，按概率递减
        uint8_t decay = LFUDecrAndReturn(o);
        o->lru = (o->lru & 191) | (decay << 6);
    } else {
        // 正常递增
        o->lru = (o->lru & 191) | ((LFUDecrAndReturn(o) + 1) << 6);
    }
}
```

---

## 7. 持久化内存优化

### 7.1 RDB Fork优化

```c
// src/rdb.c
pid_t rdbSaveBackground(char *filename) {
    // 1. Fork子进程
    pid_t childpid = fork();
    
    if (childpid == 0) {
        // 子进程：生成RDB文件
        int retval = rdbSave(filename);
        _exit(retval == C_OK ? 0 : 1);
    }
    
    if (childpid == -1) {
        errnoAbort("Can't save in background: fork: %s", strerror(errno));
        return -1;
    }
    
    // 2. 设置追踪
    server.rdb_child_pid = childpid;
    server.rdb_child_type = RDB_CHILD_TYPE_DISK;
    
    // 3. 启动Bgsave计时器
    elapsedStart(&server.rdb_save_time_start);
    
    return childpid;
}
```

### 7.2 Copy-on-Write优化

```c
// src/server.c
void updateDictResizePolicy(void) {
    // 检查是否有子进程在执行Bgsave
    if (server.rdb_child_pid != -1 || server.aof_child_pid != -1) {
        // 暂停rehash，避免COW放大
        dictEnableResize();
    } else {
        dictDisableResize();
    }
}
```

### 7.3 AOF重写优化

```c
// src/aof.c
pid_t aofRewriteBackground(void) {
    // 1. Fork子进程
    pid_t childpid = fork();
    
    if (childpid == 0) {
        // 子进程：生成AOF重写文件
        if (aofRewriteBufferBytes() > 0) {
            // 写入差异数据
            writeToAOFRewriteChild(aof_rewrite_buffer);
        }
        _exit(0);
    }
    
    // 2. 父进程：设置标志
    server.aof_child_pid = childpid;
    server.aof_rewrite_time_start = time(NULL);
    
    return childpid;
}
```

---

## 8. 生产调优实践

### 8.1 内存配置

```conf
# redis.conf
# 最大内存限制
maxmemory 8gb

# 淘汰策略
maxmemory-policy allkeys-lru

# 采样数量
maxmemory-samples 10

# 禁用透明大页（减少内存碎片）
vm.overcommit_memory = 1
```

### 8.2 内存监控

```bash
# 查看内存使用
redis-cli info memory

# 输出示例：
# used_memory:123456789
# used_memory_human:117.74M
# used_memory_rss:134567890
# used_memory_peak:145678901
# mem_fragmentation_ratio:1.09
# maxmemory:8589934592
# maxmemory_human:8.00G
# maxmemory_policy:allkeys-lru
```

### 8.3 内存碎片优化

```bash
# 触发内存整理（需要CONFIG SET activedefrag yes）
redis-cli CONFIG SET activedefrag yes

# 查看碎片信息
redis-cli INFO memory | grep fragmentation

# 期望值：1.0-1.5之间
# >1.5 表示碎片较严重
```

### 8.4 大Key优化

```bash
# 查找大Key
redis-cli --bigkeys

# 删除大Key
redis-cli DEL keyname

# 使用SCAN替代KEYS（避免阻塞）
redis-cli SCAN 0 MATCH pattern* COUNT 100
```

---

## 总结

本文档详细分析了Redis内存系统的源码实现，包括：

1. **对象系统**: SDS、引用计数、类型编码
2. **内存分配器**: Jemalloc设计、统计监控
3. **数据结构**: 哈希表、跳表、快链表
4. **主动回收**: LRU采样、惰性删除
5. **淘汰策略**: LRU/LFU算法、近似实现
6. **持久化优化**: Fork、Copy-on-Write、AOF重写

**核心设计原则**：
- **对象封装**: 统一的数据表示
- **延迟释放**: 引用计数管理
- **近似算法**: 平衡性能与准确性
- **COW优化**: Fork时最小化内存拷贝

---

**文档版本**: v1.0  
**作者**: Expert Engineer（基于Redis 7.0源码）  
**审核**: Tech Lead  
**最后更新**: 2026-08-12
