# Redis 源码级理解 — 数据结构、持久化、集群

> 标签: `#Redis` `#数据结构` `#持久化` `#集群` `#源码分析`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 数据结构源码分析

### 1.1 Redis 对象系统

```c
// Redis 对象结构（src/object.h）
typedef struct redisObject {
    unsigned type:4;       // 对象类型: OBJ_STRING/OBJ_LIST/OBJ_HASH/OBJ_ZSET/OBJ_SET
    unsigned encoding:4;   // 编码方式: OBJ_ENCODING_INT/SDS/HASHMAP/ZIPLIST/LISTPACK/SKIPLIST/INTSET
    unsigned lru:REDIS_LRU_BITS;  // LRU 时钟（24 bits）
    int refcount;           // 引用计数
    void *ptr;              // 指向实际数据的指针
} robj;
```

**核心设计**：所有数据都封装在 `robj` 中，同一逻辑类型可以有不同编码，根据数据量自动切换。

### 1.2 SDS（简单动态字符串）

```c
// SDS 结构（src/sds.h）
struct sdshdr {
    // 变长头部，根据 buf 长度选择不同结构:
    // struct sdshdr8:  uint8_t len; uint8_t free; uint8_t buf[];
    // struct sdshdr16: uint16_t len; uint16_t free; uint8_t buf[];
    // struct sdshdr32: uint32_t len; uint32_t free; uint8_t buf[];
    // struct sdshdr64: uint64_t len; uint64_t free; uint8_t buf[];
    
    uint64_t len;      // 已用字节数
    uint64_t free;     // 剩余字节数
    char buf[];        // 数据数组
};

// 特点:
// 1. O(1) 获取字符串长度（len 字段）
// 2. 空间预分配：连续操作时 free > 1MB 则增加 50%，否则增加 100%
// 3. 惰性空间释放：缩短字符串时不立即 free，保留到下次写入
// 4. 二进制安全：不依赖 \0 作为结束标志
```

### 1.3 哈希表（Dict）

```c
// 双哈希表实现（src/dict.h）
typedef struct dict {
    dictType *type;           // 类型相关回调
    void *privdata;           // 私有数据
    dictht ht[2];            // 两张哈希表
    long rehashidx;          // rehash 进度，-1 表示不在 rehash
    int iterators;           // 迭代器数量
} dict;

typedef struct dictht {
    dictEntry **table;       // 哈希表数组（桶）
    unsigned long size;      // 表大小（2 的幂）
    unsigned long sizemask;  // size - 1，用于位运算取模
    unsigned long used;      // 已用节点数
} dictht;

typedef struct dictEntry {
    void *key;               // 键
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next;  // 解决哈希冲突（链地址法）
} dictEntry;

// rehash 流程（渐进式）:
// 1. 给 ht[1] 分配空间: size = used * 2（扩容）或 used / 2（缩容）
// 2. 开始 rehash: dictRehash() 每次移动 100 个桶
// 3. 期间读写操作: ht[0] 为主，如果 key 不在 ht[0] 则查 ht[1]
// 4. rehash 完成后: 释放 ht[0]，ht[1] 改为 ht[0]，新建空 ht[1]
```

**触发 rehash 条件**：
```
扩容: dict.size <= dict.used && dict.size < 1048576
扩容: dict.size <= dict.used * 10（允许扩容到 10 倍，节省空间）
扩容: dict.size <= dict.used * 5（Redis 4.0+，Redis 集群模式）
缩容: dict.size > dict.used * 0.1 且 dict.size > 16
```

### 1.4 跳表（SkipList）

```c
// Redis 跳表实现（src/t_zset.c）
typedef struct zskiplistNode {
    sds ele;                   // 成员值
    double score;              // 分数
    struct zskiplistNode *backward;  // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward;  // 前进指针
        unsigned int span;               // 跨度
    } level[];                      // 变长数组，最大 32 层
} zskiplistNode;

typedef struct zskiplist {
    struct zskiplistNode *header, *tail;
    unsigned long length;
    int level;  // 最高层数
} zskiplist;

// 节点层数选择（随机算法）:
// P(layer >= N) = 1/4^N
// N = 1: 概率 100%
// N = 2: 概率 25%
// N = 3: 概率 6.25%
// ...
// N = 32: 概率 ~0.00002%

// 平均 O(log N)，最坏 O(N)（概率极低）
// 相比平衡树: 实现简单，内存占用少
```

**为什么 ZSet 用跳表不用红黑树？**
1. 范围查询友好（中序遍历 vs 跳表前进指针）
2. 实现简单，维护成本低
3. 内存占用少（不需要 parent/左右子指针/color 标记）

### 1.5 IntSet（整数集合）

```c
// 紧凑的整数存储
typedef struct intset {
    uint32_t encoding;  // INTSET_ENC_INT16 / INTSET_ENC_INT32 / INTSET_ENC_INT64
    uint32_t length;    // 元素个数
    int8_t contents[];  // 连续内存存储
} intset;

// 升级策略（只升不降）:
// 新元素 > 当前最大编码 → 升级整个集合
// 例如: [1, 2, 3] (int16) → 加入 65537 → 全部升级 int32 → [1, 2, 3, 65537]
```

### 1.6 ZipList（压缩列表）

```c
// 连续内存块存储多个 entry
// 结构: <zlbytes> <zltail> <zllen> <entry1> <entry2> ... <entryN> <zleof>

// 每个 entry 结构:
// prevlen_bytes (变长，1 byte 或 5 bytes) | encoding | data

// prevlen: 前一个 entry 的长度（用于反向遍历）
//   如果 < 254: 1 字节
//   如果 >= 254: 1 字节标记 (254) + 4 字节实际长度

// encoding:
//   < 60 字节: 直接存储（前 2 字节表示长度和类型）
//   60-16383 字节: 2 字节前缀 + 数据
//   16384+ 字节: 2 字节前缀(01) + 4 字节长度 + 数据

// 触发条件:
// list-max-zipmap-entries 默认 128 个元素
// list-max-zipmap-value 默认 64 字节
// 超过任一条件 → 转为 HashMap
```

---

## 2. 持久化机制

### 2.1 RDB（快照）

```c
// 触发条件:
// 1. SAVE: 同步快照（阻塞所有命令）
// 2. BGSAVE: 后台快照（fork 子进程）
// 3. 自动触发（redis.conf）:
//    save 900 1      // 900 秒内至少 1 次 key 变更
//    save 300 10     // 300 秒内至少 10 次
//    save 60 10000   // 60 秒内至少 10000 次

// BGSAVE 流程:
// 1. 主进程 fork 子进程
// 2. 子进程写入 RDB 文件到临时文件 (.rdb.tmp)
// 3. 写完后 mv 覆盖旧 RDB 文件
// 4. 主进程更新 stats

// RDB 文件格式:
// [REDIS0011]  // 版本号
// [DB0]        // 数据库编号
// [SELECTDB 0] // SELECTDB 指令
// [key1 value1 type1]  // key-value 对（带类型）
// [key2 value2 type2]
// ...
// [checksum]   // CRC64 校验
```

**RDB vs AOF 对比**：

| 维度 | RDB | AOF |
|------|-----|-----|
| 文件大小 | 小（压缩） | 大（追加写） |
| 恢复速度 | 快 | 慢（需重放） |
| 数据安全性 | 可能丢失最后 N 秒 | 可配置（每秒/每次） |
| CPU 占用 | 低（fork 一次） | 高（持续写磁盘） |
| 适用场景 | 灾难恢复 | 数据一致性要求高 |

### 2.2 AOF（追加日志）

```c
// appendonly.conf 配置:
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec  // always/everysec/no
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100  // AOF 增长 100% 时触发重写
auto-aof-rewrite-min-size 64mb   // AOF 最小 64MB 才触发重写

// AOF 重写（BGREWRITEAOF）:
// 1. 主进程 fork 子进程
// 2. 子进程遍历所有 key，用最小命令重建（SET/HMSET/LPUSH 等）
// 3. 同时接收主进程的新写入，写入 AOF 重写缓冲区
// 4. 重写完成后，将缓冲区写入新 AOF 文件
// 5. 原子替换旧 AOF

// 写入命令格式:
*3\r\n$3\r\nSET\r\n$4\r\nkey1\r\n$5\r\nvalue\r\n
// 格式: *argvlen\r\n$arg1len\r\narg1\r\n$arg2len\r\narg2\r\n...
```

### 2.3 混合持久化（Redis 4.0+）

```c
// AOF 重写时:
// 前半部分: RDB 格式（快照）
// 后半部分: AOF 格式（增量）

// 优势: 恢复速度接近 RDB，数据安全性接近 AOF

// AOF 结构:
// [RDB 快照数据]
// [AOF 增量命令]

// 加载时:
// 1. 先加载 RDB 部分 → 快速恢复大部分数据
// 2. 再重放 AOF 增量命令 → 保证数据完整
```

---

## 3. 内存淘汰策略

```c
// 触发内存淘汰: maxmemory-policy 配置
// 1. noeviction: 不淘汰，返回错误（默认）
// 2. allkeys-lru: 所有 key 中淘汰最近最少使用
// 3. allkeys-lfu: 所有 key 中淘汰最不经常使用
// 4. allkeys-random: 随机淘汰
// 5. volatile-lru: 有过期时间的 key 中淘汰 LRU
// 6. volatile-lfu: 有过期时间的 key 中淘汰 LFU
// 7. volatile-ttl: 有过期时间的 key 中淘汰 TTL 最小的
// 8. volatile-random: 有过期时间的 key 中随机淘汰

// LRU 近似算法（Redis 不用严格 LRU）:
// 1. 随机采样 5 个 key（config: maxmemory-samples）
// 2. 淘汰样本中 LRU 的 key
// 3. O(k) 复杂度，k = 5（默认）

// LFU 算法（Redis 4.0+）:
// struct redisObject {
//     ...
//     unsigned lru:28;  // 低 16 位: 28 bits 用于 LFU counter
//                     // 高 16 位: LRU 时间
// };
// LFU counter 采用对数计数器（logcount）:
//   counter 初始 0
//   访问时以概率 p = 1/(1+exp((min-counter - counter)/slope)) 递增
//   饱和到 255
//   避免新 key 永远不被淘汰
```

---

## 4. 集群架构

### 4.1 数据分片（Hash Slot）

```c
// Redis Cluster 使用 16384 个 hash slot
// hash slot = CRC16(key) % 16384

// 3 主 3 从集群:
// Master 0: slot [0-5460]   + Replica: Slave 0
// Master 1: slot [5461-10922] + Replica: Slave 1
// Master 2: slot [10923-16383] + Replica: Slave 2

// 客户端命令路由:
// 1. 客户端计算 slot = CRC16(key) % 16384
// 2. 查找 slot 映射表 → 找到对应 Master
// 3. 如果当前节点不是该 slot 的 Master → 返回 MOVED 重定向
// 4. 客户端重定向到新节点

// 多 key 操作（MGET/DEL）:
// - 所有 key 必须在同一个 slot → 使用 hash tag {key1} {key1}
// - 不同 slot → 返回 CROSSSLOT 错误
// - Redis 7.0+ 支持跨 slot 操作（通过 CLUSTER SLOTS 命令）
```

### 4.2 Gossip 协议

```c
// 节点间通信协议:
// PING/PONG: 节点发现、心跳检测
// MEET: 主动邀请新节点加入集群
// FAIL: 标记节点为 FAIL
// PFAIL: 标记节点为 PFAIL（可能失败）
// INFO: 节点信息交换（slots、nodes）

// 故障检测（PFail → Fail）:
// 1. 节点 A 检测到节点 B 心跳超时
// 2. A 标记 B 为 PFAIL，并广播给其他节点
// 3. 当超过半数节点标记 B 为 PFAIL → B 升级为 FAIL
// 4. 标记为 FAIL 的节点被移除集群

// 主观故障 vs 客观故障:
// 主观（PFail）: 单个节点认为某节点故障
// 客观（Fail）: 多数节点确认某节点故障
```

### 4.3 主从复制

```c
// 复制流程:
// 1. 从节点发送 PSYNC <runid> <offset> 到主节点
//    runid: 主节点的 runid（首次为空，之后用主节点的）
//    offset: 上次同步的偏移量

// 主节点响应:
// FULLRESYNC <runid> <offset>  → 触发全量复制
// SYNC_WITH_MASTER <offset>    → 触发增量复制

// 全量复制:
// 1. 主节点执行 BGSAVE 生成 RDB
// 2. 主节点将 RDB 写入 backlog buffer（接收复制期间的写命令）
// 3. 主节点发送 RDB 文件给从节点
// 4. 从节点加载 RDB
// 5. 主节点发送 backlog buffer 中的命令给从节点

// 增量复制（PSYNC）:
// 主节点维护 replication backrep buffer
// 从节点通过 offset 定位断点，只同步增量部分
// backrep buffer 大小: repl-backlog-size（默认 1MB）
```

### 4.4 事务机制

```c
// MULTI → EXEC 事务:
// 1. MULTI: 进入事务状态，后续命令入队到事务队列
// 2. 命令入队时不执行（仅检查语法）
// 3. EXEC: 一次性执行所有命令
// 4. 如果任何命令语法错误 → 整个事务不执行
// 5. 如果命令运行时错误 → 该命令失败，继续执行后续命令

// WATCH: 乐观锁
// WATCH key1 key2  // 监控 key
// MULTI
//   GET key1
//   SET key1 newval
// EXEC  // 如果 key1 被其他客户端修改 → 返回 nil（事务失败）

// Lua 脚本（原子操作）:
// EVAL "return redis.call('set', KEYS[1], ARGV[1])" 1 mykey myval
// 整个 Lua 脚本原子执行，不可打断
```

---

## 5. 性能优化

### 5.1 大 Key 治理

```c
// 大 Key 定义:
// String > 10KB
// Hash/List/Set/ZSet > 5000 个元素

// 问题:
// 1. 网络开销大
// 2. 阻塞 Redis（删除大 Key 时 O(N)）
// 3. 主从复制延迟
// 4. 内存碎片

// 解决方案:
// 1. 拆分: 一个大 Key 拆成多个小 Key
//    例如: user:123:tags → user:123:tag:1, user:123:tag:2, ...
// 2. SCAN 替代 KEYS（非阻塞扫描）
// 3. 延迟删除: 分批删除大 Key
// 4. MEMORY USAGE key 监控大 Key
```

### 5.2 慢查询日志

```c
// 配置:
slowlog-log-slower-than 10000  // 超过 10ms 记录
slowlog-max-len 128            // 保留 128 条

// 查询:
SLOWLOG GET 10       // 最近 10 条慢查询
SLOWLOG LEN          // 慢查询总数
SLOWLOG RESET        // 清空慢查询日志

// 常见慢命令:
// KEYS * → 用 SCAN 替代
// FLUSHALL → 用 FLUSHDB 或异步删除
// DEL bigkey → 用 UNLINK（异步删除）
// SORT → 避免
```

---

*本文档基于 Redis 7.0+ 源码整理*
