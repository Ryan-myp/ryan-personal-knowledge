# Redis 源码级深度：事件循环 + RDB/AOF 持久化

> 逐行解析 Redis ae.c 事件循环 + rdb.c/aof.c 持久化源码

---

## 第一部分：事件循环源码深度

### Redis 事件循环架构

```
Redis 单线程模型：
┌─────────────────────────────────────────────────┐
│                 Redis Server                     │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │         aeEventLoop (事件循环)             │   │
│  │                                           │   │
│  │  ┌─────────────┐  ┌──────────────────┐   │   │
│  │  │  timeEvent    │  │  fileEvent       │   │   │
│  │  │  (定时器)     │  │  (文件描述符)    │   │   │
│  │  │             │  │                  │   │   │
│  │  │ - 过期键清理 │  │ - ACCEPT 事件    │   │   │
│  │  │ - 超时命令   │  │ - READ 事件      │   │   │
│  │  │ - 后台任务   │  │ - WRITE 事件     │   │   │
│  │  └─────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  底层 I/O 多路复用：                              │
│  - epoll (Linux)                                 │
│  - kqueue (macOS/BSD)                            │
│  - select (fallback)                             │
└─────────────────────────────────────────────────┘
```

### 源码逐行解析：aeCreateEventLoop

```c
// Redis 源码：ae.c - aeCreateEventLoop
// 创建事件循环

aeEventLoop *aeCreateEventLoop(int setsize) {
    aeEventLoop *eventLoop;
    int size;
    int i;
    
    // 1. 计算文件事件数组大小
    // setsize: 最大文件描述符数量 + 1
    size = setsize * sizeof(aeFileEvent);
    
    // 2. 分配事件循环结构
    if (!(eventLoop = zmalloc(sizeof(aeEventLoop))))
        return NULL;
    
    // 3. 初始化基本字段
    eventLoop->maxfd = -1;       // 最大 fd
    eventLoop->setsize = setsize; // 数组大小
    eventLoop->timeEventHead = NULL; // 定时器链表头
    eventLoop->stop = 0;         // 是否停止循环
    
    // 4. 初始化文件事件数组
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
    for (i = 0; i < setsize; i++) {
        eventLoop->events[i].mask = AE_NONE;
    }
    
    return eventLoop;
    
err:
    aeDeleteEventLoop(eventLoop);
    return NULL;
}
```

**关键点**：
- **setsize**：默认 1024，可容纳的文件描述符数量
- **ioevents**：epoll/kqueue 的 events 数组，用于 epoll_wait/kqueue 返回
- **HAVE_EPOLL**：Linux 优先用 epoll，macOS 用 kqueue

### 源码逐行解析：aeProcessEvents

```c
// Redis 源码：ae.c - aeProcessEvents
// 处理一次事件循环

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
            // 没有定时器，无限等待
            tv.tv_sec = tv.tv_usec = 0;
        } else {
            // 有定时器，等待到下一个定时器到期
            // 注意：这里会调整 tv 为相对时间
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
        #else
        // select 的 timeout 已经是绝对时间
        // 需要转换为相对时间
        #endif
        
        // 4. 处理就绪的文件事件
        if (numevents > 0) {
            int i;
            for (i = 0; i < numevents; i++) {
                aeFileEvent *fe = &eventLoop->events[
                    eventLoop->ioevents[i].fd];
                int mask = eventLoop->ioevents[i].mask;
                int fd = eventLoop->ioevents[i].fd;
                
                // 4.1 检查可读事件
                if (mask & AE_READABLE && fe->mask & AE_READABLE) {
                    fe->rfileProc(eventLoop, fd, fe->clientData, mask);
                    processed++;
                }
                
                // 4.2 检查可写事件
                if (mask & AE_WRITABLE && fe->mask & AE_WRITABLE) {
                    fe->wfileProc(eventLoop, fd, fe->clientData, mask);
                    processed++;
                }
            }
        }
        
        // 5. 处理定时器事件
        if (flags & AE_TIME_EVENTS) {
            processed += processTimeEvents(eventLoop);
        }
    }
    
    return processed;
}
```

**关键点**：
- **flags**：AE_FILE_EVENTS（文件事件）+ AE_TIME_EVENTS（定时器事件）
- **epoll_wait**：阻塞等待，超时时间由下一个定时器决定
- **rfileProc/wfileProc**：回调函数，处理具体的读写事件

### 文件事件注册：aeCreateFileEvent

```c
// Redis 源码：ae.c - aeCreateFileEvent
// 注册文件事件

int aeCreateFileEvent(aeEventLoop *eventLoop, int fd, int mask,
                      aeFileProc *proc, void *clientData) {
    // 1. 检查 fd 是否超出范围
    if (fd >= eventLoop->setsize) {
        errno = ERANGE;
        return AE_ERR;
    }
    
    aeFileEvent *fileEvent = &eventLoop->events[fd];
    
    // 2. 如果已注册，先删除旧的
    if (fileEvent->mask & mask) {
        return AE_ERR; // 不允许重复注册相同事件
    }
    
    // 3. 设置回调函数
    fileEvent->rfileProc = (mask & AE_READABLE) ? proc : NULL;
    fileEvent->wfileProc = (mask & AE_WRITABLE) ? proc : NULL;
    fileEvent->clientData = clientData;
    
    // 4. 更新 mask
    fileEvent->mask |= mask;
    
    // 5. 更新 epoll/kqueue
    #ifdef HAVE_EPOLL
    epoll_event ee;
    ee.events = 0;
    if (fileEvent->mask & AE_READABLE) ee.events |= EPOLLIN;
    if (fileEvent->mask & AE_WRITABLE) ee.events |= EPOLLOUT;
    ee.data.fd = fd;
    epoll_ctl(eventLoop->epfd, EPOLL_CTL_MOD, fd, &ee);
    #endif
    
    return AE_OK;
}
```

**关键点**：
- **mask**：AE_READABLE（可读）+ AE_WRITABLE（可写）
- **EPOLLIN/EPOLLOUT**：epoll 的事件类型
- **clientData**：用户数据指针，通常是 client 结构体

---

## 第二部分：RDB 持久化源码深度

### RDB 写入流程

```
RDB 触发条件：
1. SAVE 命令（阻塞，不推荐）
2. BGSAVE（后台 fork，推荐）
3. 自动触发：
   - save 900 1（900 秒内至少 1 次变更）
   - save 300 10（300 秒内至少 10 次变更）
   - save 60 10000（60 秒内至少 10000 次变更）

BGSAVE 流程：
1. 主进程 fork 子进程
2. 子进程写 RDB 文件（写时复制 COW）
3. 主进程继续处理命令
4. 子进程写完，rename 到新文件
5. 主进程替换旧 RDB 文件
```

### 源码逐行解析：rdbSave

```c
// Redis 源码：rdb.c - rdbSave
// 保存 RDB 文件

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
    if (server.rdb_save_diskless) {
        // diskless: 直接发送到 replica
        rioDisklessWrite(&rdb);
    } else {
        // disk-based: fsync
        if (fflush(fp) == EOF) goto writeerr;
        if (fsync(fileno(fp)) == -1) goto writeerr;
    }
    
    return C_OK;
    
writeerr:
    error = 1;
    return C_ERR;
}
```

**关键点**：
- **rio 对象**：Redis 的抽象 IO 层，支持文件和网络
- **rdbSaveKeyValuePair**：序列化单个 key-value
- **diskless**：直接发送给 replica，不经过磁盘（Redis 4.0+）

### RDB 压缩算法

```
RDB 使用的压缩算法：
1. LZF：轻量级压缩，速度快，压缩率低
2. LZ4：速度更快，压缩率中等（Redis 5.0+）
3. ZSTD：压缩率最高，速度较慢（Redis 6.2+）

配置：
save-rdb-compress yes      # 是否启用压缩
rdbcompression lzf|lz4|zstd # 选择算法

选择建议：
- 内存紧张：zstd（压缩率高）
- CPU 紧张：lzf（速度快）
- 平衡：lz4（推荐）
```

---

## 第三部分：AOF 持久化源码深度

### AOF 写入流程

```
AOF 配置：
appendonly yes                    # 启用 AOF
appendfsync everysec              # 刷盘策略
no-appendfsync-on-rewrite yes     # 重写期间不刷盘
auto-aof-rewrite-percentage 100   # 增长率阈值
auto-aof-rewrite-min-size 64mb    # 最小文件大小

AOF 三种刷盘策略：
1. always：每次命令都 fsync（最安全，性能最差）
2. everysec：每秒 fsync（推荐，最多丢 1 秒数据）
3. no：操作系统决定何时 fsync（最快，可能丢大量数据）
```

### 源码逐行解析：feedAppendOnlyFile

```c
// Redis 源码：aof.c - feedAppendOnlyFile
// 将命令写入 AOF 缓冲区

void feedAppendOnlyFile(struct redisCommand *cmd, int dbid, 
                        robj *key, robj *val, int flags) {
    sds aux = sdsempty();
    
    // 1. 构建 MULTI/EXEC 块（如果命令在事务中）
    if (cmd->flags & REDIS_CMD_MULTI) {
        if (flags & AOF_NONE) {
            // 事务命令，不写入 AOF
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
    robj *joined = NULL;
    for (j = 0; j < cmd->argc; j++) {
        if (cmd->argv[j] == key && val != NULL) {
            // 替换为新的 value
            aux = sdscatprintf(aux, "$%lu\r\n", 
                             sdslen(val->ptr));
            aux = sdscatprintf(aux, "%s\r\n", val->ptr);
        } else {
            aux = sdscatprintf(aux, "$%lu\r\n", 
                             sdslen(cmd->argv[j]->ptr));
            aux = sdscatprintf(aux, "%s\r\n", cmd->argv[j]->ptr);
        }
    }
    
    // 4. 写入 AOF 缓冲区
    if (server.aof_state == AOF_ON) {
        server.aof_buf = sdscat(server.aof_buf, aux);
    }
    
    sdsfree(aux);
}
```

**关键点**：
- **sdscatprintf**：Redis 的 SDS 字符串追加
- **AOF 缓冲区**：server.aof_buf，累积命令后批量写入
- **dbid**：数据库编号，每个 key 前写入 SELECT dbid

### AOF 重写（BGREWRITEAOF）

```
AOF 重写流程：
1. 主进程 fork 子进程
2. 子进程遍历所有 key，生成 SET 命令
3. 主进程继续处理命令，写入 aof_rewrite_buf
4. 子进程写完，rename 到新 AOF 文件
5. 主进程将 aof_rewrite_buf 追加到新文件
6. 替换旧 AOF 文件

重写优化：
- 只保留最新状态（SET key value）
- 删除过期 key
- 合并相同 key 的操作
- 压缩 RDB + AOF 混合模式（Redis 4.0+）
```

### 源码逐行解析：rewriteAppendOnlyFile

```c
// Redis 源码：aof.c - rewriteAppendOnlyFile
// AOF 重写核心函数

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
            // SET key value [EX seconds]
            rewriteStringObject(fd, key, val, expire);
            break;
            
        case OBJ_LIST:
            // LPUSH/LSET 命令
            rewriteListObject(fd, key, val);
            break;
            
        case OBJ_SET:
            // SADD 命令
            rewriteSetObject(fd, key, val);
            break;
            
        case OBJ_HASH:
            // HSET 命令
            rewriteHashObject(fd, key, val);
            break;
            
        case OBJ_ZSET:
            // ZADD 命令
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

## 第四部分：自测题

### Q1: Redis 为什么用单线程模型？

**A**: 
- 网络 I/O 是瓶颈，单线程避免了锁竞争和上下文切换
- 事件循环 + epoll/kqueue 高效处理百万连接
- CPU 计算简单（内存操作），不需要多线程
- 但阻塞命令（SORT、KEYS、BGSAVE）会影响性能

### Q2: RDB 和 AOF 的区别？

**A**:
| 维度 | RDB | AOF |
|------|-----|-----|
| **内容** | 数据快照 | 命令日志 |
| **体积** | 小（压缩） | 大（逐命令） |
| **恢复速度** | 快 | 慢 |
| **数据安全性** | 可能丢数据 | 最多丢 1 秒 |
| **CPU 开销** | 低 | 高 |
| **推荐** | 冷备 | 热备 |

### Q3: AOF 重写期间主进程怎么处理新命令？

**A**: 主进程将新命令写入 `aof_rewrite_buf`（内存缓冲区），重写完成后追加到新 AOF 文件。这样既不影响主进程性能，又保证数据不丢失。

---

## 第五部分：生产排障

### 1. AOF 文件过大

```bash
# 检查 AOF 大小
du -sh /var/lib/redis/*.aof

# 触发重写
redis-cli BGREWRITEAOF

# 检查重写进度
redis-cli INFO aof
# aof_rewrite_in_progress: 0 (0=完成)
# aof_rewrite_scheduled: 0
```

### 2. RDB 生成慢

```bash
# 检查 fork 是否成功
redis-cli INFO persistence
# rdb_bgsave_in_progress: 0
# rdb_last_bgsave_status: ok

# 优化：
# 1. 增加内存（减少 COW 拷贝）
# 2. 使用 diskless RDB（直接发给 replica）
# 3. 调整 save 规则，减少触发频率
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
