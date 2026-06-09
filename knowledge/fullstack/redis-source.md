# Redis 源码级深度 — dict/sds/skiplist、RDB/AOF、cluster gossip、一致性协议

> 标签: `#Redis` `#数据结构` `#持久化` `#cluster` `#一致性` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 对象系统 & SDS — 源码级

### 1.1 robj 与类型编码

```c
// server.h — 对象系统
typedef struct redisObject {
    unsigned type:4;           // 对象类型
    unsigned encoding:4;       // 编码方式
    unsigned lru:LRU_BITS;     // LRU 时钟（24 bits）
    int refcount;              // 引用计数（-1 表示共享，共享对象池）
    void *ptr;                 // 指向实际数据的指针
} robj;

// 类型枚举:
#define OBJ_STRING 0
#define OBJ_LIST 1
#define OBJ_SET 2
#define OBJ_ZSET 3
#define OBJ_HASH 4
#define OBJ_STREAM 5

// 编码枚举:
#define OBJ_ENCODING_RAW 0        // 简单动态字符串（SDS）
#define OBJ_ENCODING_INT 1        // 整数（long）
#define OBJ_ENCODING_HT 2         // 哈希表（dict）
#define OBJ_ENCODING_ZIPLIST 3    // 压缩列表
#define OBJ_ENCODING_LISTPACK 4   // 列表包（Redis 7.0+，替代 ziplist）
#define OBJ_ENCODING_LINKEDLIST 5 // 链表
#define OBJ_ENCODING_QUICKLIST 6  // 快速链表（Redis 4.0+）
#define OBJ_ENCODING_SKIPLIST 7   // 跳表
#define OBJ_ENCODING_INTSET 8     // 整数集合
#define OBJ_ENCODING_STREAM 9     // Stream 数据结构
#define OBJ_ENCODING_STREAM_LISTPACKS 10 // Stream 内部编码

// 自动编码切换逻辑:
// String:
//   - 值是 long 类型 → OBJ_ENCODING_INT
//   - 值 <= 44 字节 → OBJ_ENCODING_RAW (SDS)
//   - 值 > 44 字节 → OBJ_ENCODING Embstr（embstr 是 SDS 和 robj 连续分配的优化）
// List:
//   - 数据量少 + 元素短 → OBJ_ENCODING_ZIPLIST
//   - 数据量大 → OBJ_ENCODING_QUICKLIST
// Hash:
//   - 数据量少 + key/value 短 → OBJ_ENCODING_ZIPLIST
//   - 数据量大 → OBJ_ENCODING_HT
// Set:
//   - 全是整数且数量少 → OBJ_ENCODING_INTSET
//   - 其他 → OBJ_ENCODING_HT
// ZSet:
//   - 数据量少 + 元素短 → OBJ_ENCODING_ZIPLIST
//   - 数据量大 → OBJ_ENCODING_SKIPLIST + HT
```

### 1.2 SDS — Simple Dynamic String 源码

```c
// sds.h — SDS 结构（Redis 4.0+ 变长头部）
struct sdshdr8 {
    uint8_t len;        // 已用字节数（低 7 bits）
    uint8_t free;       // 剩余字节数（低 7 bits）
    uint8_t alloc;      // 总分配字节数（低 7 bits）
    unsigned char flags; // 3 bits type + 5 bits unused
    char buf[];         // 数据数组
};

// SDS 分配:
// SDS_TYPE_5: flags=00, 不分配 buf（仅用于短字符串，len < 32）
// SDS_TYPE_8: flags=01, 头部 3 bytes
// SDS_TYPE_16: flags=10, 头部 5 bytes
// SDS_TYPE_32: flags=110, 头部 9 bytes
// SDS_TYPE_64: flags=111, 头部 17 bytes

// 空间预分配策略:
// 1. SDS 不为空时: len < 1MB → 分配 len * 2（翻倍）
//                  len >= 1MB → 分配 len + 1MB（只加 1MB）
// 2. SDS 为空时: 分配 1 byte（最小分配）
// 3. 惰性空间释放: sdsrange/sdslen 缩小时，不 free，free 字段增加

// SDS API:
sds sdsnewlen(const void *init, size_t initlen);
sds sdscatlen(sds s, const void *t, size_t len);
sds sdscatfmt(sds s, const char *fmt, ...);  // 格式化追加
void sdsfree(sds s);
size_t sdslen(const sds s);
size_t sdsavail(const sds s);

// SDS vs C 字符串:
// C 字符串: strlen() O(N), 必须 \0 结尾, 不能存二进制
// SDS: len() O(1), 不依赖 \0, 二进制安全
```

---

## 2. dict 哈希表 — 源码级

### 2.1 dict 结构

```c
// dict.h — 哈希表结构
typedef struct dict {
    dictType *type;         // 类型相关函数
    void *privdata;         // 私有数据
    
    dictht ht[2];           // 双哈希表（rehash 用）
    long rehashidx;         // rehash 进度（-1 = 不在 rehash）
    int iterators;          // 活跃迭代器数量
    unsigned long size;     // 总槽数（ht[0].size + ht[1].size）
    unsigned long sizemask; // 掩码（size - 1）
    unsigned long used;     // 已有节点数
} dict;

// dictht — 哈希表
typedef struct dictht {
    dictEntry **table;      // 哈希表数组（指针数组）
    unsigned long size;     // 数组大小（2 的幂）
    unsigned long sizemask; // size - 1
    unsigned long used;     // 节点数
} dictht;

// dictEntry — 哈希表节点
typedef struct dictEntry {
    void *key;              // 键
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;                    // 值
    struct dictEntry *next; // 链表（冲突解决）
} dictEntry;

// dictType — 类型相关函数（多态）
typedef struct dictType {
    uint64_t (*hashFunction)(const void *key);  // 哈希函数
    void *(*keyDup)(void *privdata, const void *key);  // 键复制
    void *(*valDup)(void *privdata, const void *obj);  // 值复制
    int (*keyCompare)(void *privdata, const void *key1, const void *key2);  // 键比较
    void (*keyDestructor)(void *privdata, void *key);  // 键析构
    void (*valDestructor)(void *privdata, void *obj);  // 值析构
} dictType;
```

### 2.2 rehash（渐进式扩容）

```c
// rehash 触发条件:
// 1. 负载因子 >= 1 且没有 BGSAVE 在进行 → 立即扩容（负载因子 = used / size）
// 2. 负载因子 >= 5 且没有 BGSAVE → 立即扩容（强制触发）
// 3. 负载因子 >= 1 且有 BGSAVE → 延迟扩容（渐进式）

// rehash 过程:
void dictRehash(dict *d, int steps) {
    // 每次只迁移 steps 个 bucket（渐进式，不阻塞）
    while (d->rehashidx != -1 && steps > 0) {
        // 找到下一个非空 bucket
        while (d->ht[0].table[d->rehashidx] == NULL) {
            d->rehashidx++;
        }
        
        // 迁移一个 bucket 的所有节点到 ht[1]
        dictEntry *de = d->ht[0].table[d->rehashidx];
        while (de) {
            // 计算在新哈希表中的位置
            unsigned long hash = dictHash(d, de->key);
            unsigned long index = hash & d->ht[1].sizemask;
            
            // 插入到 ht[1]
            de->next = d->ht[1].table[index];
            d->ht[1].table[index] = de;
            d->ht[1].used++;
            
            // 移动到下一个节点
            de = de->next;
        }
        
        d->ht[0].table[d->rehashidx] = NULL;
        d->rehashidx++;
        steps--;
    }
}

// 渐进式 rehash 的关键:
// 1. ht[0] 和 ht[1] 同时存在
// 2. 新写入/查找/删除操作同时在两个表上进行
// 3. 迁移完成后释放 ht[0]

// 时间复杂度:
// 单次 rehash: O(1)（每次迁移一个 bucket）
// 总时间: O(N)（N = 旧表大小）
// 空间复杂度: O(N)（双表共存）
```

### 2.3 冲突解决

```c
// Redis 哈希表使用链地址法解决冲突
// 冲突链的尾部插入策略:
// dictAdd → dictGenericAdd → dictAddRaw
// dictAddRaw 总是将新节点插入到桶的头部（O(1)）

// 哈希函数:
// 对于字符串键: dictGenHashFunction → djb2 哈希
// djb2: hash = ((hash << 5) + hash) + string[i]
// 对于整数键: 直接使用整数值

// 为什么用 djb2？
// 1. 速度快：位运算
// 2. 分散性好：低字节影响高字节
```

---

## 3. 跳表（skiplist）— ZSet 底层实现

### 3.1 zskiplist 结构

```c
// zskiplist.h — 跳表结构
typedef struct zskiplist {
    struct zskiplistNode *header, *tail;  // 头尾节点
    unsigned long length;                  // 节点数
    int level;                             // 最大层数
} zskiplist;

// zskiplistNode — 跳表节点
typedef struct zskiplistNode {
    sds ele;                  // 元素（字符串）
    double score;             // 分数
    struct zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward; // 前向指针
        unsigned long span;            // 跨度（到下一个节点的距离）
    } level[];  // 变长数组，最多 32 层
} zskiplistNode;

// 跳跃节点层级概率:
// level 1: P = 1/4
// level 2: P = 1/16
// level 3: P = 1/64
// ...
// level N: P = (1/4)^N

// 平均层数: 1 / (1 - 1/4) = 4/3 ≈ 1.33
// 最大层数: 32（硬编码上限）
```

### 3.2 跳表插入/删除

```c
// 插入 O(log N):
void zslInsert(zskiplist *zsl, double score, sds ele) {
    // 1. 找到插入位置（从高层向下逐层查找）
    zskiplistNode *update[MAXLEVEL]; // 记录每层的前驱
    unsigned int rank[MAXLEVEL];     // 记录每层的排名
    
    zskiplistNode *x = zsl->header;
    for (int i = zsl->level - 1; i >= 0; i--) {
        rank[i] = (i == zsl->level - 1) ? 0 : rank[i + 1];
        while (x->level[i].forward && 
               (x->level[i].forward->score < score ||
                (x->level[i].forward->score == score && sdscmp(x->level[i].forward->ele, ele) < 0))) {
            rank[i] += x->level[i].span;
            x = x->level[i].forward;
        }
        update[i] = x; // 记录前驱
    }
    
    // 2. 生成随机层级
    int level = zslRandomLevel();
    
    // 3. 创建新节点
    zskiplistNode *newNode = zslCreateNode(level, score, ele);
    
    // 4. 更新指针
    for (int i = 0; i < level; i++) {
        newNode->level[i].forward = update[i]->level[i].forward;
        update[i]->level[i].forward = newNode;
        newNode->level[i].span = update[i]->level[i].span - (rank[0] - rank[i]);
        update[i]->level[i].span += (rank[0] - rank[i]);
    }
    
    // 5. 更新高层的跨度
    for (int i = level; i < zsl->level; i++) {
        update[i]->level[i].span++;
    }
    
    // 6. 更新 head 的跨度
    if (x->level[0].forward) {
        x->level[0].span++;
    }
    
    // 7. 处理并列分数: 按 lexicographical order 排序
    // (Redis 5.0+ 引入字典序排序)
}
```

---

## 4. 持久化 — RDB/AOF 源码级

### 4.1 RDB（Redis Database）

```c
// rdb.h — RDB 文件格式
// 结构: Header + Entry Sequence + Footer

// Header:
// - RDB 版本号（Magic Number: REDIS0011）
// - 创建时间戳
// - 辅助数据（aof-preamble 等）

// Entry:
// - Type Byte（操作类型）
//   - RDB_OPCODE_EXPIRETIME_MS: 过期时间（毫秒）
//   - RDB_OPCODE_EXPIRETIME: 过期时间（秒）
//   - RDB_OPCODE_SELECTDB: 数据库编号
//   - RDB_OPCODE_EOF: 文件结束
//   - RDB_OPCODE_AUX: 辅助数据
//   - RDB_OPCODE_RESIZEDB: 哈希表大小
//   - 0-127: 短字符串（带类型）
//   - 128-191: 16-bit 长度字符串
//   - 192-254: 32-bit 长度字符串
//   - 255: 特殊操作码
// - Data（字符串值或键值对）

// 压缩:
// - LZF: 用于短字符串
// - ZSTD: Redis 6.2+ 支持
// - 整数编码: 直接存整数，不转字符串

// save 流程:
void rdbSave(int dirfd, rdbSaveInfo *rsi, unsigned flags) {
    // 1. fork 子进程
    pid_t child = fork();
    if (child == 0) {
        // 子进程: 写入 RDB 文件
        rdbSaveRio(rdb, NULL, NULL, flags);
        _exit(0);
    } else {
        // 父进程: 等待子进程完成
        rdbChildBlock childInfo;
        rdbPrepareForSave(&childInfo);
        
        // 触发 BGSAVE 阻塞点
        atomicSetLongLong(&server.rdb_child_start_time, ustime());
        
        // 等待子进程退出
        while (waitpid(child, &stat, WNOHANG) == 0) {
            sleep(1);
        }
    }
}

// copy-on-write 机制:
// fork 后，父进程的内存页变为只读
// 子进程读取时，如果父进程修改了页，操作系统复制该页
// 这样子进程读取的是 fork 时刻的快照
// 代价: 如果父进程写压力大，COW 频繁，内存翻倍
```

### 4.2 AOF（Append Only File）

```c
// aof.h — AOF 文件结构
// 格式: Redis Protocol（RESP）
// 每条记录是一个完整的 Redis 命令
// EX: SET key value
// EX: EXPIRE key timeout
// EX: DEL key

// aofState:
// AOF_OFF    // 关闭
// AOF_ENABLED // 启用
// AOF_WRITE   // 正在写入 RDB 文件

// 写入策略:
// 1. no: 不写入（操作系统决定）
// 2. everysec: 每秒写入（默认，最多丢 1 秒数据）
// 3. always: 每次写入都 fsync（最安全，性能最差）

// aofRewrite — AOF 重写（消除冗余命令）:
void aofRewriteBackground(int flags) {
    // 1. fork 子进程
    pid_t child = fork();
    if (child == 0) {
        // 子进程: 遍历所有 key，生成 SET/EXPIRE 等命令
        // 不读 AOF 文件，直接读内存数据
        aofRewriteBufferWrite();
        _exit(0);
    }
}

// AOF 重写 + 复制（Redis 5.0+ 改进）:
// 1. 子进程开始重写，生成重写缓冲区
// 2. 主进程将新命令同时写入 base AOF + 重写缓冲区
// 3. 子进程完成重写后，发送 base AOF 到从库
// 4. 主进程发送重写缓冲区中的命令到从库
// 5. 从库: 先加载 base AOF，再回放增量命令

// AOF 文件结构:
// Header:
//   - RDB 头（用于快速启动时跳过）
//   - AOF 魔术头（REDIS0011）
// Data:
//   - Redis 协议命令
// Footer:
//   - RDB 尾
//   - AOF 校验和
```

### 4.3 RDB vs AOF 对比

```c
// 选择策略:
// 同时启用 RDB + AOF（推荐）:
// - RDB: 定期全量快照
// - AOF: 每秒追加命令
// 启动时: 先加载 AOF（恢复最新数据），再加载 RDB（如果需要回退到更早快照）

// 恢复速度:
// RDB: 快（加载快照文件）
// AOF: 慢（回放命令）

// 数据完整性:
// RDB: 可能丢最近一次快照的数据
// AOF: 最多丢 1 秒（everysec 策略）

// 文件大小:
// RDB: 小（压缩 + 二进制）
// AOF: 大（文本命令）
```

---

## 5. Cluster 集群 — gossip 协议

### 5.1 cluster 架构

```c
// cluster.h — 集群配置
typedef struct clusterState {
    clusterNode *myself;         // 当前节点
    clusterNode **slots_to_node; // 槽位 → 节点映射
    clusterNode **migrating;     // 正在迁移的槽位
    clusterNode **importing;     // 正在导入的槽位
    
    int slot_end;                // 槽位范围结束
    int slot_start;              // 槽位范围开始
    
    clusterNode *failover_auth_node; // 故障转移候选节点
    long long failover_auth_request; // 故障转移请求
    long long failover_auth_sent;     // 故障转移已发送
    
    uint64_t configEpoch;      // 配置纪元
    int slots_sub_slots;       // 已分配的槽位数
    
    clusterLink **links;       // 与所有节点的链接
    int links_count;           // 链接数量
    
    // 节点信息
    clusterNode **nodes;       // 所有节点列表
    int cluster_size;          // 集群大小
    unsigned long long cluster_size_slots;  // 集群槽位总数
    
    // 节点发现
    int failover_recovery;     // 故障恢复标志
    int cluster_stats_messages_sent; // 发送消息数
    int cluster_stats_messages_received; // 接收消息数
    
    // 槽位分配
    unsigned long cluster_known_nodes; // 已知节点数
    unsigned long cluster_size;       // 集群大小
    unsigned long long cluster_stats_messages_examined;
    
    // 节点
    struct clusterNode {
        char name[CLUSTER_NAMELEN];   // 节点名称（40 hex 字符）
        int flags;                    // 节点标志
        int numslots;                 // 槽位数
        int numsubslots;              // 子槽位数
        struct clusterNode *slaveof;  // 主节点（如果是从节点）
        mstime_t ping_sent;           // 最后 ping 时间
        mstime_t pong_received;       // 最后 pong 时间
        mstime_t fail_time;           // 失败时间
        mstime_t voted_time;          // 投票时间
        mstime_t repl_offset_time;    // 复制偏移量时间
        mstime_t orphaned_time;       // 孤立时间
        double ping_lag;              // ping 延迟
        long long repl_offset;        // 复制偏移量
        int fail_time_ms;             // 失败时间戳
        int config_epoch;             // 配置纪元
        int numreplicas;              // 从节点数
        int slots[16384];             // 槽位分配
        int *slots_array;             // 槽位数组
        int *subslots;                // 子槽位
        int slot_start, slot_end;     // 槽位范围
        int slot_count;               // 槽位数量
    };
} clusterState;
```

### 5.2 gossip 协议

```c
// cluster.c — gossip 协议实现

// 消息类型:
// PING: 发现/心跳
// PONG: PING 的响应
// MEET: 主动发现
// FAILOVER_AUTH_REQUEST: 故障转移请求
// FAILOVER_AUTH_ACK: 故障转移确认
// FAIL: 故障通知
// BUSY: 集群忙碌

// gossip 协议:
// 1. 每个节点定期（1 秒）向随机 N 个节点发送 PING
// 2. PING 包含:
//    - 自己的信息（名称、标志、槽位分配、配置纪元）
//    - 其他 N 个节点的信息
// 3. 收到 PING 后回复 PONG
// 4. PONG 包含:
//    - 接收到的 PING 的内容
//    - 自己的信息

// 节点发现:
// 新节点 JOIN:
// 1. 节点 A 发送 MEET 消息给集群中的某个节点
// 2. 该节点将 A 加入自己的节点列表
// 3. A 节点通过 gossip 了解到所有节点
// 4. A 节点获取槽位分配信息
// 5. A 节点开始处理自己的槽位

// 故障检测:
// 1. 节点 A 定期检查节点 B 的 pong_received
// 2. 如果 pong_received 超过 cluster-node-timeout（默认 15 秒），标记为 PFAIL（可能失败）
// 3. 如果有超过半数的主节点标记 B 为 PFAIL，升级为 FAIL
// 4. FAIL 的节点的主从切换流程:
//    a. 从节点发现主节点 FAIL
//    b. 从节点发起故障转移请求
//    c. 集群中其他主节点投票
//    d. 获得多数票的从节点提升为主节点
//    e. 新主节点接管槽位
//    f. 旧主节点恢复后变为从节点
```

---

## 6. 一致性协议 — 主从复制

### 6.1 复制状态机

```c
// replication.c — 复制状态机

typedef enum {
    REPL_STATE_NONE,         // 无复制
    REPL_STATE_CONNECT,      // 连接中
    REPL_STATE_TRANSFER,     // 传输 RDB 中
    REPL_STATE_ONLINE,       // 在线
    REPL_STATE_SEND_BULK     // 发送增量数据
} replState;

// 复制流程:
// 1. MASTER → SLAVE: SYNC 命令
// 2. MASTER fork 子进程生成 RDB
// 3. MASTER 将 RDB 发送给 SLAVE
// 4. SLAVE 加载 RDB（全量同步）
// 5. MASTER 将同步期间的命令写入 replaybuf
// 6. MASTER 将 replaybuf 发送给 SLAVE
// 7. SLAVE 回放命令（增量同步）
// 8. 之后 Master 持续将新命令发送给 Slave（PSYNC）

// PSYNC（部分重同步）:
// SLAVE → MASTER: PSYNC <replication_id> <offset>
// MASTER 响应:
//   - FULLRESYNC <replication_id> <offset>: 需要全量同步
//   - PARTIAL_OK: 可以部分重同步
//   - PARTIAL_FAIL: 需要全量同步（主库缓冲区清空）

// 复制偏移量:
// master_repl_offset: 主库的复制偏移量
// slave_repl_offset: 从库的复制偏移量
// master_repl_offset - slave_repl_offset = 复制延迟（字节）

// 心跳:
// 每秒发送一次 PING 保持连接
```

### 6.2 一致性保证

```c
// Redis 一致性模型:
// 1. 单线程: 命令原子执行，不会交错
// 2. 主从复制: 异步复制（可能丢数据）
// 3. 集群: 最终一致性（CAP 中的 AP）

// 如何保证强一致?
// 1. 使用 MULTI/EXEC（事务）: 保证命令原子执行
// 2. 使用 WATCH: 乐观锁（CAS）
// 3. 使用 Lua 脚本: 原子执行

// 但 Redis 没有传统 ACID 事务:
// - 没有回滚（rollback）
// - 没有隔离级别
// - 命令执行失败后，后续命令仍然执行
```

---

## 7. 内存管理

### 7.1 内存分配

```c
// zmalloc.h — Redis 内存管理
void *zmalloc(size_t size);
void zfree(void *ptr);
void *zcalloc(size_t size);
void *zrealloc(void *ptr, size_t size);
size_t zmalloc_size(const void *ptr);
size_t zmalloc_used_memory(void);

// Redis 使用的 allocator:
// jemalloc (默认, Linux): 减少内存碎片
// libc malloc (MacOS, Windows): 系统默认
// tcmalloc (Google): 高性能

// 内存限制:
// maxmemory 配置:
//   - noeviction: 不驱逐，直接返回错误
//   - allkeys-lru: 全局 LRU 驱逐
//   - volatile-lru: 只驱逐有过期时间的 key
//   - allkeys-random: 随机驱逐
//   - volatile-random: 随机驱逐有过期时间的 key
//   - volatile-ttl: 驱逐最近过期的 key
//   - allkeys-lfu: LFU 驱逐（Redis 4.0+）
//   - volatile-lfu: LFU 驱逐有过期时间的 key

// LRU 近似算法:
// 采样 N 个 key（默认 5），淘汰最久未使用的
// 不是精确的 LRU，但 O(1) 时间复杂度
```

### 7.2 内存碎片

```c
// 内存碎片原因:
// 1. 频繁分配/释放小对象
// 2. 不同大小的对象交替分配
// 3. allocator 的内存对齐和页边界

// 监控:
// INFO memory 中的:
//   - used_memory: 实际使用
//   - used_memory_rss: 操作系统看到的内存
//   - mem_fragmentation_ratio: used_memory_rss / used_memory
//     - > 1.5: 高碎片
//     - < 1.0: 使用了 overcommit（可能 OOM）

// 解决:
// 1. 重启 Redis（释放碎片）
// 2. 启用 active-defrag:
//    activedefrag yes
//    active-defrag-threshold-lower 10
//    active-defrag-threshold-upper 100
//    active-defrag-cycle-min 5
//    active-defrag-cycle-max 25
```

---

*本文档基于 Redis 7.0 源码整理，覆盖核心数据结构、持久化、集群、一致性*

