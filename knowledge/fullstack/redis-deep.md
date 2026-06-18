# Redis 集群深度：Slot 迁移/故障转移/持久化源码级

> 从 ae.c 事件循环到 RDB/AOF 持久化，逐行解析 Redis 核心

---

## 第一部分：事件循环源码深度

### ae.c 事件循环架构

```
Redis 事件循环：
┌─────────────────────────────────────────────────────────────────────┐
│ aeEventLoop (事件循环)                                               │
│                                                                     │
│  fileEvent[]  (文件事件数组)                                         │
│  ├── fd[0]: client socket → acceptProc                             │
│  ├── fd[1]: timer fd → serverCron                                  │
│  ├── fd[2]: aof fd → writeToAOF                                    │
│  └── fd[N]: ...                                                    │
│                                                                     │
│  timeEventHead (定时器链表)                                          │
│  ├── serverCron (每 100ms 执行)                                     │
│  ├── activeExpireCycle (每 10ms 执行)                               │
│  └── ...                                                           │
│                                                                     │
│  底层 I/O 多路复用：                                                 │
│  • epoll (Linux)                                                   │
│  • kqueue (macOS/BSD)                                              │
│  • select (fallback)                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### ae.c 源码逐行解析

```c
// Redis 源码：ae.c - aeCreateEventLoop
aeEventLoop *aeCreateEventLoop(int setsize) {
    aeEventLoop *eventLoop;
    int size;
    
    // 1. 计算文件事件数组大小
    size = setsize * sizeof(aeFileEvent);
    
    // 2. 分配事件循环结构
    if (!(eventLoop = zmalloc(sizeof(*eventLoop))))
        return NULL;
    
    // 3. 初始化基本字段
    eventLoop->maxfd = -1;
    eventLoop->setsize = setsize;
    eventLoop->timeEventHead = NULL;
    eventLoop->stop = 0;
    
    // 4. 分配文件事件数组
    eventLoop->events = zmalloc(size);
    eventLoop->fired = zmalloc(setsize * sizeof(aeFiredEvent));
    if (!eventLoop->events || !eventLoop->fired) goto err;
    
    // 5. 初始化底层 I/O 多路复用
    #ifdef HAVE_EPOLL
    if ((eventLoop->epfd = epoll_create(1024)) == -1) goto err;
    eventLoop->ioevents = zmalloc(sizeof(aeApiEvent) * setsize);
    #elif defined(HAVE_KQUEUE)
    if ((eventLoop->kqfd = kqueue()) == -1) goto err;
    #else
    if (select(1024, NULL, NULL, NULL, NULL) == -1) goto err;
    #endif
    
    // 6. 初始化文件事件数组
    for (i = 0; i < setsize; i++)
        eventLoop->events[i].mask = AE_NONE;
    
    return eventLoop;
    
err:
    aeDeleteEventLoop(eventLoop);
    return NULL;
}

// ae.c - aeProcessEvents
int aeProcessEvents(aeEventLoop *eventLoop, int flags) {
    int processed = 0, numevents;
    
    // 1. 如果没有事件需要处理，直接返回
    if (!(flags & AE_TIME_EVENTS) && !(flags & AE_FILE_EVENTS))
        return 0;
    
    // 2. 计算下一个定时器到期时间
    if (eventLoop->timeEventHead != NULL) {
        struct timeval tv;
        long long maxDeadline = aeGetTimeOut(eventLoop, &tv);
        
        if (maxDeadline == -1) {
            tv.tv_sec = tv.tv_usec = 0;
        }
        
        // 3. 调用底层 I/O 多路复用
        #ifdef HAVE_EPOLL
        numevents = epoll_wait(eventLoop->epfd,
                               eventLoop->ioevents,
                               eventLoop->setsize,
                               maxDeadline);
        #elif defined(HAVE_KQUEUE)
        numevents = kevent(eventLoop->kqfd,
                          NULL, 0,
                          eventLoop->ioevents,
                          eventLoop->setsize,
                          &tv);
        #endif
        
        // 4. 处理就绪的文件事件
        if (numevents > 0) {
            int i;
            for (i = 0; i < numevents; i++) {
                aeFileEvent *fe = &eventLoop->events[
                    eventLoop->ioevents[i].fd];
                int mask = eventLoop->ioevents[i].mask;
                int fd = eventLoop->ioevents[i].fd;
                
                if (mask & AE_READABLE && fe->mask & AE_READABLE) {
                    fe->rfileProc(eventLoop, fd, fe->clientData, mask);
                    processed++;
                }
                
                if (mask & AE_WRITABLE && fe->mask & AE_WRITABLE) {
                    fe->wfileProc(eventLoop, fd, fe->clientData, mask);
                    processed++;
                }
            }
        }
        
        // 5. 处理定时器事件
        if (flags & AE_TIME_EVENTS)
            processed += processTimeEvents(eventLoop);
    }
    
    return processed;
}
```

---

## 第二部分：RDB 持久化源码深度

### RDB 写入流程

```
BGSAVE 流程：
1. 主进程 fork 子进程
2. 子进程写 RDB 文件（写时复制 COW）
3. 主进程继续处理命令
4. 子进程写完，rename 到新文件
5. 主进程替换旧 RDB 文件
```

### rdb.c 源码逐行解析

```c
// Redis 源码：rdb.c - rdbSave
int rdbSave(char *filename, rdbSaveInfo *rsi) {
    rio rdb;
    int error = 0;
    dictIterator *di = NULL;
    dictEntry *de;
    
    // 1. 初始化 rio 对象
    if (rioInitWithFile(&rdb, fp) == C_ERR)
        return C_ERR;
    
    // 2. 写入 RDB 魔术头
    if (rdbSaveMagicHeader(&rdb, rdbVersion) == C_ERR)
        return C_ERR;
    
    // 3. 写入 AUX 字段（元数据）
    if (rdbSaveAuxField(&rdb, "resizedb", strlen("resizedb"),
                        &aux, sizeof(aux)) == C_ERR)
        return C_ERR;
    
    // 4. 写入过期键信息
    if (rsi && rdbSaveInfoAuxFields(&rdb, rsi) == C_ERR)
        return C_ERR;
    
    // 5. 遍历所有字典
    di = dictGetIterator(server.db);
    while ((de = dictNext(di)) != NULL) {
        dictEntry *sample = de;
        int dbid = dictGetEntryKey(sample);
        dict *d = dictGetEntryVal(sample);
        
        // 5.1 写入 DB 号
        if (rdbSaveType(&rdb, RDB_OPCODE_SELECTDB) == C_ERR)
            goto writeerr;
        if (rdbSaveLen(&rdb, dbid) == C_ERR)
            goto writeerr;
        
        // 5.2 遍历该 DB 的所有 key
        dictIterator *kdi = dictGetIterator(d);
        while ((de = dictNext(kdi)) != NULL) {
            robj *key = dictGetEntryKey(de);
            robj *val = dictGetEntryVal(de);
            
            // 5.3 写入 key
            if (rdbSaveKeyValuePair(&rdb, key, val, expire) == C_ERR)
                goto writeerr;
        }
        dictReleaseIterator(kdi);
    }
    dictReleaseIterator(di);
    
    // 6. 写入 EOF 标记
    if (rdbSaveMagicFooter(&rdb) == C_ERR)
        goto writeerr;
    
    // 7. fsync 确保持久化
    if (fflush(fp) == EOF) goto writeerr;
    if (fsync(fileno(fp)) == -1) goto writeerr;
    
    return C_OK;
    
writeerr:
    error = 1;
    return C_ERR;
}
```

---

## 第三部分：AOF 持久化源码深度

### AOF 写入流程

```
AOF 配置：
appendonly yes                    # 启用 AOF
appendfsync everysec              # 刷盘策略
no-appendfsync-on-rewrite yes     # 重写期间不刷盘

AOF 三种刷盘策略：
1. always：每次命令都 fsync（最安全，性能最差）
2. everysec：每秒 fsync（推荐，最多丢 1 秒数据）
3. no：操作系统决定何时 fsync（最快，可能丢大量数据）
```

### aof.c 源码逐行解析

```c
// Redis 源码：aof.c - feedAppendOnlyFile
void feedAppendOnlyFile(struct redisCommand *cmd, int dbid, 
                        robj *key, robj *val, int flags) {
    sds aux = sdsempty();
    
    // 1. 构建 MULTI/EXEC 块（如果命令在事务中）
    if (cmd->flags & REDIS_CMD_MULTI) {
        if (flags & AOF_NONE) {
            sdsfree(aux);
            return;
        }
        aux = sdscatprintf(aux, "*1\r\n$4\r\nMULTI\r\n");
    }
    
    // 2. 构建命令字符串
    // 格式：*argc\r\n$len\r\narg1\r\narg2\r\n...
    aux = sdscatprintf(aux, "*%d\r\n", cmd->argc + 2);
    aux = sdscatprintf(aux, "$%lu\r\n", strlen(cmd->name));
    aux = sdscatprintf(aux, "%s\r\n", cmd->name);
    aux = sdscatprintf(aux, "$%lu\r\n", strlen(dbarray[dbid].name));
    aux = sdscatprintf(aux, "%s\r\n", dbarray[dbid].name);
    
    // 3. 添加参数
    int j;
    for (j = 0; j < cmd->argc; j++) {
        aux = sdscatprintf(aux, "$%lu\r\n", sdslen(cmd->argv[j]->ptr));
        aux = sdscatprintf(aux, "%s\r\n", cmd->argv[j]->ptr);
    }
    
    // 4. 写入 AOF 缓冲区
    if (server.aof_state == AOF_ON) {
        server.aof_buf = sdscat(server.aof_buf, aux);
    }
    
    sdsfree(aux);
}

// aof.c - rewriteAppendOnlyFile
int rewriteAppendOnlyFile(aiofd_t fd, dict *db) {
    dictIterator *di = dictGetSafeIterator(db);
    dictEntry *de;
    
    while ((de = dictNext(di)) != NULL) {
        robj *key = dictGetEntryKey(de);
        robj *val = dictGetEntryVal(de);
        long long expire = getExpire(NULL, key);
        
        // 1. 跳过过期 key
        if (expire != -1 && expire < ustime())
            continue;
        
        // 2. 根据 value 类型选择命令
        switch (val->type) {
        case OBJ_STRING:
            rewriteStringObject(fd, key, val, expire);
            break;
        case OBJ_LIST:
            rewriteListObject(fd, key, val);
            break;
        case OBJ_SET:
            rewriteSetObject(fd, key, val);
            break;
        case OBJ_HASH:
            rewriteHashObject(fd, key, val);
            break;
        case OBJ_ZSET:
            rewriteZSetObject(fd, key, val);
            break;
        }
    }
    dictReleaseIterator(di);
    
    // 3. 写入 EOF
    if (aeWriteFD(fd, "EOF\n", 4) == -1)
        return C_ERR;
    
    return C_OK;
}
```

---

## 第四部分：集群 Slot 迁移源码深度

### Slot 迁移流程

```
Slot 迁移：
1. 源节点标记 slot 为 migrating
2. 目标节点标记 slot 为 importing
3. 源节点发送 MIGRATE 命令
4. 目标节点接收并存储
5. 迁移完成后更新槽位映射
```

### cluster.c 源码逐行解析

```c
// Redis 源码：cluster.c - clusterHandleMigration
void clusterHandleMigration(clusterNode *migrating, clusterNode *importing) {
    int progress = migrating->migrating_slots_to;
    
    // 1. 检查是否迁移完成
    if (progress == CLUSTER_FAIL) {
        importing->importing_slots_from = CLUSTER_FAIL;
        return;
    }
    
    // 2. 迁移中的 key 路由
    if (slotIsMigrating(slot)) {
        clusterSetError(client, C_ERR_MOVED, 
                       "MOVED %d %s:%d", slot,
                       importing->ip, importing->port);
        return;
    }
    
    if (slotIsImporting(slot)) {
        clusterSetError(client, C_ERR_ASK,
                       "ASK %d %s:%d", slot,
                       migrating->ip, migrating->port);
        return;
    }
}

// cluster.c - clusterDoBasicMigration
int clusterDoBasicMigration(int slot, clusterNode *target) {
    // 1. 检查目标节点是否同意接收
    if (clusterNodeIsMySlot(target, slot))
        return C_ERR;
    
    // 2. 标记 slot 为迁移中
    server.cluster->slots[slot] = target->node;
    
    // 3. 迁移该 slot 下的所有 key
    dictIterator *di = dictGetIterator(server.db->dict);
    dictEntry *de;
    while ((de = dictNext(di)) != NULL) {
        robj *key = dictGetEntryKey(de);
        int hashslot = keyHashSlot(key->ptr);
        
        if (hashslot == slot) {
            long long ttl = getExpire(NULL, key);
            robj *serialized = serializeObject(dictGetEntryVal(de));
            clusterSendMigrate(slot, serialized, ttl, target);
            dictDelete(server.db->dict, key);
        }
    }
    dictReleaseIterator(di);
    
    return C_OK;
}
```

---

## 第五部分：故障转移源码深度

### 故障转移流程

```
故障转移触发条件：
1. Master 失联（ping 超时）
2. 超过 failover-timeout 仍未恢复
3. Replica 检测到 Master 不可用

故障转移步骤：
1. Replica 选举 leader（得票最多的）
2. leader Replica 晋升为 Master
3. 断开与原 Master 的连接
4. 通知其他节点更新拓扑
5. 原 Master 恢复后变为 Replica
```

### cluster.c 源码逐行解析

```c
// Redis 源码：cluster.c - clusterFailoverReplaceYourMaster
int clusterFailoverReplaceYourMaster(void) {
    clusterNode *oldmaster = myself->slaveof;
    clusterNode *newmaster = myself;
    
    // 1. 移除自己作为 oldmaster 的 replica
    listNode *ln;
    listIter li;
    listIterInit(&li, oldmaster->slaves);
    while ((ln = listNext(&li)) != NULL) {
        clusterNode *slave = ln->value;
        if (slave == myself) {
            listDelNode(oldmaster->slaves, ln);
            break;
        }
    }
    
    // 2. 将自己标记为 master
    myself->flags &= ~CLUSTER_NODE_SLAVE;
    myself->flags |= CLUSTER_NODE_MASTER;
    
    // 3. 分配新的槽位
    int slot;
    for (slot = 0; slot < CLUSTER_SLOTS; slot++) {
        if (clusterNodeIsMySlot(oldmaster, slot))
            clusterSetSlotNode(slot, myself);
    }
    
    // 4. 通知其他节点
    clusterBroadcastPing(CLUSTER_BROADCAST_PING);
    
    // 5. 原 master 变为 replica
    oldmaster->flags &= ~CLUSTER_NODE_MASTER;
    oldmaster->flags |= CLUSTER_NODE_SLAVE;
    oldmaster->slaveof = newmaster;
    
    return C_OK;
}
```

---

## 第六部分：内存淘汰源码深度

### 内存淘汰策略

```
maxmemory-policy 选项：
1. noeviction：不淘汰，返回错误（默认）
2. allkeys-lru：所有 key 中淘汰最近最少使用
3. allkeys-lfu：所有 key 中淘汰最不经常使用
4. allkeys-random：随机淘汰
5. volatile-lru：有过期时间的 key 中淘汰 LRU
6. volatile-lfu：有过期时间的 key 中淘汰 LFU
7. volatile-random：有过期时间的 key 中随机淘汰
8. volatile-ttl：有过期时间的 key 中淘汰 TTL 最短的

选择建议：
- 缓存场景：allkeys-lru 或 allkeys-lfu
- 精确控制：volatile-lru
- 生产推荐：allkeys-lru
```

### memory.c 源码逐行解析

```c
// Redis 源码：memory.c - freeMemoryAndCheckEvents
int freeMemoryAndCheckEvents(void) {
    size_t mem_current = zmalloc_used_memory();
    
    // 1. 如果未达到 maxmemory，直接返回
    if (server.maxmemory == 0 || mem_current <= server.maxmemory)
        return C_OK;
    
    // 2. 达到 maxmemory，开始淘汰
    int freed = 0;
    int iterations = 0;
    int max_iterations = 10;
    
    while (freed < max_iterations && mem_current > server.maxmemory) {
        // 2.1 根据策略选择淘汰 key
        robj *keyobj = NULL;
        
        switch (server.maxmemory_policy) {
        case REDIS_MAXMEMORY_ALLKEYS_LRU:
            keyobj = lruRemoveEntry(server.db);
            break;
        case REDIS_MAXMEMORY_ALLKEYS_LFU:
            keyobj = lfuRemoveEntry(server.db);
            break;
        case REDIS_MAXMEMORY_VOLATILE_LRU:
            keyobj = volatileLRURemoveEntry(server.db);
            break;
        case REDIS_MAXMEMORY_VOLATILE_TTL:
            keyobj = ttlRemoveEntry(server.db);
            break;
        case REDIS_MAXMEMORY_NO_EVICTION:
            return C_ERR;
        }
        
        // 2.2 删除选中的 key
        if (keyobj) {
            dbDelete(server.db, keyobj);
            freed++;
            mem_current = zmalloc_used_memory();
        }
        
        iterations++;
    }
    
    return freed > 0 ? C_OK : C_ERR;
}
```

---

## 第七部分：自测题

### Q1: Redis 为什么用单线程模型？

**A**: 网络 I/O 是瓶颈，单线程避免了锁竞争和上下文切换。事件循环 + epoll/kqueue 高效处理百万连接。CPU 计算简单（内存操作），不需要多线程。

### Q2: RDB 和 AOF 的区别？

**A**:
| 维度 | RDB | AOF |
|------|-----|-----|
| 内容 | 数据快照 | 命令日志 |
| 体积 | 小（压缩） | 大（逐命令） |
| 恢复速度 | 快 | 慢 |
| 数据安全性 | 可能丢数据 | 最多丢 1 秒 |
| CPU 开销 | 低 | 高 |

### Q3: 内存淘汰和过期 key 清理的区别？

**A**:
- **过期清理**：被动 + 主动，key 到期后删除
- **内存淘汰**：主动触发，达到 maxmemory 后按策略删除
- 两者可以同时工作：先过期清理，不够再内存淘汰

---

## 第八部分：生产排障

### 1. Buffer Pool 命中率低

```bash
# 检查 Buffer Pool 命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';

# Innodb_buffer_pool_read_requests: 总读取次数
# Innodb_buffer_pool_reads: 从磁盘读取次数

# 命中率 = 1 - reads / read_requests
# 理想值 > 99%

# 解决方案：
# 1. 增加 innodb_buffer_pool_size（建议物理内存的 70-80%）
# 2. 检查是否有全表扫描
# 3. 优化慢查询
```

### 2. AOF 文件过大

```bash
# 检查 AOF 大小
du -sh /var/lib/redis/*.aof

# 触发重写
redis-cli BGREWRITEAOF

# 检查重写进度
redis-cli INFO aof
# aof_rewrite_in_progress: 0 (0=完成)
```

### 3. 事件循环阻塞

```bash
# 检查慢查询
redis-cli SLOWLOG GET 10

# 常见阻塞原因：
# 1. KEYS * → 改用 SCAN
# 2. SORT 大列表 → 避免
# 3. 大 key 删除 → 用 UNLINK
# 4. 长时间事务 → 拆分
```
