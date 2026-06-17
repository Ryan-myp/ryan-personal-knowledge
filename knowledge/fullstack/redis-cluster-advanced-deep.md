# Redis 源码级深度：集群 Slot 迁移 + 高级特性

> 逐行分析 Redis Cluster 槽位迁移/故障转移 + 内存淘汰/发布订阅/慢查询

---

## 第一部分：Cluster Slot 迁移源码深度

### Redis Cluster 架构

```
Redis Cluster 架构：
┌─────────────────────────────────────────────────┐
│  16384 个槽位（0-16383）                         │
│                                                  │
│  Master 1 (192.168.1.1:6379)                    │
│  Slots: 0-5460                                 │
│  Replica: 192.168.1.2:6379                      │
│                                                  │
│  Master 2 (192.168.1.3:6379)                    │
│  Slots: 5461-10922                              │
│  Replica: 192.168.1.4:6379                      │
│                                                  │
│  Master 3 (192.168.1.5:6379)                    │
│  Slots: 10923-16383                             │
│  Replica: 192.168.1.6:6379                      │
└─────────────────────────────────────────────────┘

槽位分配：
- 16384 = 2^14，CRC16(key) % 16384
- 每个 master 分配一段连续的槽位
- 槽位迁移：从源 master → 目标 master
```

### 源码逐行解析：clusterHandleMigration

```c
// Redis 源码：cluster.c - clusterHandleMigration
// 处理槽位迁移

void clusterHandleMigration(clusterNode *migrating, clusterNode *importing) {
    // 1. 获取迁移进度
    int progress = migrating->migrating_slots_to;
    
    // 2. 检查是否迁移完成
    if (progress == CLUSTER_FAIL) {
        // 迁移取消
        importing->importing_slots_from = CLUSTER_FAIL;
        return;
    }
    
    // 3. 迁移中的 key 路由
    // 客户端请求 key → CRC16(key) % 16384 → 找到对应 slot
    // 如果 slot 在迁移中：
    //   - 源 master 返回 MOVED 错误，告诉客户端去目标 master
    //   - 目标 master 返回 ASK 错误，告诉客户端先去源 master 拿
    
    // 4. 处理 MOVED 错误
    if (slotIsMigrating(slot)) {
        clusterSetError(client, C_ERR_MOVED, 
                       "MOVED %d %s:%d", slot,
                       importing->ip, importing->port);
        return;
    }
    
    // 5. 处理 ASK 错误
    if (slotIsImporting(slot)) {
        clusterSetError(client, C_ERR_ASK,
                       "ASK %d %s:%d", slot,
                       migrating->ip, migrating->port);
        return;
    }
}
```

**关键点**：
- **MOVED**：key 已完全迁移到目标 master，客户端应重定向
- **ASK**：key 正在迁移中，客户端应先向源 master 请求
- **迁移状态**：每个 slot 有三种状态：本地/迁移中/导入中

### 源码逐行解析：clusterDoBasicMigration

```c
// Redis 源码：cluster.c - clusterDoBasicMigration
// 执行基本的槽位迁移

int clusterDoBasicMigration(int slot, clusterNode *target) {
    // 1. 检查目标节点是否同意接收
    if (clusterNodeIsMySlot(target, slot)) {
        return C_ERR; // 目标节点已经拥有该 slot
    }
    
    // 2. 标记 slot 为迁移中
    server.cluster->slots[slot] = target->node;
    
    // 3. 发送 MIGRATE 命令到目标节点
    char cmd[256];
    snprintf(cmd, sizeof(cmd), 
            "MIGRATE %s %d \"%s\" %d 0",
            target->ip, target->port, "", 0);
    
    // 4. 迁移该 slot 下的所有 key
    dictIterator *di = dictGetIterator(server.db->dict);
    dictEntry *de;
    while ((de = dictNext(di)) != NULL) {
        robj *key = dictGetEntryKey(de);
        int hashslot = keyHashSlot(key->ptr);
        
        if (hashslot == slot) {
            // 4.1 获取 key 的 TTL
            long long ttl = getExpire(NULL, key);
            
            // 4.2 序列化 key
            robj *serialized = serializeObject(dictGetEntryVal(de));
            
            // 4.3 发送到目标节点
            clusterSendMigrate(slot, serialized, ttl, target);
            
            // 4.4 删除本地 key
            dictDelete(server.db->dict, key);
        }
    }
    dictReleaseIterator(di);
    
    return C_OK;
}
```

---

## 第二部分：故障转移源码深度

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

### 源码逐行解析：clusterFailoverReplaceYourMaster

```c
// Redis 源码：cluster.c - clusterFailoverReplaceYourMaster
// 故障转移：Replica 晋升为 Master

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
        if (clusterNodeIsMySlot(oldmaster, slot)) {
            clusterSetSlotNode(slot, myself);
        }
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

**关键点**：
- **槽位转移**：原 master 的槽位全部转移到新 master
- **节点标记**：更新 CLUSTER_NODE_MASTER/SLAVE 标志
- **广播 Ping**：通知集群其他节点拓扑变更

---

## 第三部分：内存淘汰源码深度

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
- 精确控制：volatile-lru（给每个 key 设 TTL）
- 生产推荐：allkeys-lru
```

### 源码逐行解析：freeMemoryAndCheckEvents

```c
// Redis 源码：memory.c - freeMemoryAndCheckEvents
// 内存淘汰核心函数

int freeMemoryAndCheckEvents(void) {
    // 1. 检查当前内存使用量
    size_t mem_current = zmalloc_used_memory();
    size_t mem_peak = zmalloc_max_mem;
    long long mem_reported = server.stat_mem_clients_norm;
    
    // 2. 如果未达到 maxmemory，直接返回
    if (server.maxmemory == 0 || mem_current <= server.maxmemory) {
        return C_OK;
    }
    
    // 3. 达到 maxmemory，开始淘汰
    int freed = 0;
    int iterations = 0;
    int max_iterations = 10; // 最多迭代 10 次
    
    while (freed < max_iterations && mem_current > server.maxmemory) {
        // 3.1 根据策略选择淘汰 key
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
            return C_ERR; // 不淘汰，返回错误
        }
        
        // 3.2 删除选中的 key
        if (keyobj) {
            dbDelete(server.db, keyobj);
            firedEvents++;
            freed++;
            
            // 3.3 更新内存统计
            mem_current = zmalloc_used_memory();
        }
        
        iterations++;
    }
    
    // 4. 通知客户端
    if (freed > 0) {
        notifyKeyspaceEvent(REDIS_NOTIFY_EVICT, "evicted",
                           NULL, server.db->id);
    }
    
    return freed > 0 ? C_OK : C_ERR;
}
```

---

## 第四部分：发布订阅源码深度

### 发布订阅架构

```
Pub/Sub 模型：
┌─────────────────────────────────────────────────┐
│  Redis Server                                   │
│                                                  │
│  pubsubChannels:                                 │
│  "news" → [client1, client2, client3]           │
│  "updates" → [client2, client4]                 │
│  "orders.*" → [client5] (pattern)               │
│                                                  │
│  发布：PUBLISH news "Hello"                      │
│  订阅：SUBSCRIBE news                            │
│  模式订阅：PSUBSCRIBE news.*                     │
└─────────────────────────────────────────────────┘

特点：
- 实时推送，无持久化
- 发布者不知道谁在订阅
- 订阅者断开后消息丢失
```

### 源码逐行解析：pubsubPublishMessage

```c
// Redis 源码：pubsub.c - pubsubPublishMessage
// 发布消息

int pubsubPublishMessage(sds message, robj *channel) {
    int receivers = 0;
    
    // 1. 精确匹配订阅
    dictEntry *de;
    dictIterator *di = dictGetIterator(server.pubsub_channels);
    while ((de = dictNext(di)) != NULL) {
        sds key = dictGetEntryKey(de);
        if (sdsEquals(key, channel->ptr)) {
            // 1.1 获取订阅该 channel 的客户端列表
            list *clients = dictGetEntryVal(de);
            listNode *ln;
            listIter li;
            listIterInit(&li, clients);
            while ((ln = listNext(&li)) != NULL) {
                client *c = ln->value;
                // 1.2 发送消息给客户端
                addReplyBulk(c, channel);
                addReplyBulk(c, message);
                receivers++;
            }
        }
    }
    dictReleaseIterator(di);
    
    // 2. 模式匹配订阅
    di = dictGetIterator(server.pubsub_patterns);
    while ((de = dictNext(di)) != NULL) {
        pubsubPattern *pat = dictGetEntryVal(de);
        if (stringmatchlen(channel->ptr, sdslen(channel->ptr),
                          pat->pattern, sdslen(pat->pattern), 0)) {
            // 2.1 发送消息给匹配的客户端
            addReplyArray(pat->client, 3);
            addReplyBulk(pat->client, "message");
            addReplyBulk(pat->client, channel);
            addReplyBulk(pat->client, message);
            receivers++;
        }
    }
    dictReleaseIterator(di);
    
    return receivers;
}
```

---

## 第五部分：自测题

### Q1: Redis Cluster 最少需要几个节点？

**A**: 最少 3 个 master 节点（每个 master 可以有 0-N 个 replica）。3 个 master 保证多数派（quorum），2 个 master 无法达成共识。

### Q2: 内存淘汰和过期 key 清理的区别？

**A**:
- **过期清理**：被动 + 主动，key 到期后删除
- **内存淘汰**：主动触发，达到 maxmemory 后按策略删除
- 两者可以同时工作：先过期清理，不够再内存淘汰

### Q3: Pub/Sub 和 Queue 的区别？

**A**:
- **Pub/Sub**：实时推送，无持久化，发布者不知道订阅者
- **Queue**（如 Redis Streams/List）：持久化，支持重播，有消费者组
- 广告系统推荐用 Streams（支持持久化和消费者组）

---

## 第六部分：生产排障

### 1. 槽位迁移卡住

```bash
# 检查迁移状态
redis-cli CLUSTER SLOTS

# 查看迁移进度
redis-cli CLUSTER INFO
# cluster_state:ok
# cluster_slots_assigned:16384
# cluster_slots_ok:16384

# 手动触发迁移
redis-cli CLUSTER SETSLOT <slot> MIGRATING <target-node-id>
```

### 2. 内存淘汰频繁

```bash
# 检查内存使用
redis-cli INFO memory
# used_memory_human: 1.50G
# maxmemory_human: 2.00G

# 优化：
# 1. 增加 maxmemory
# 2. 调整淘汰策略
# 3. 设置合理的 TTL
# 4. 使用 Redis 4.0+ 的 LFU 策略
```

### 3. Pub/Sub 消息丢失

```bash
# 检查订阅者数量
redis-cli PUBSUB NUMSUB channel_name

# 优化：
# 1. 使用 Redis Streams 替代 Pub/Sub
# 2. 增加消费者数量
# 3. 设置合理的超时
```
