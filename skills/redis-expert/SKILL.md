---
name: redis-expert
description: "Redis 专家技能 — 数据结构源码、持久化机制、集群架构、性能调优"
version: 1.0.0
author: ryan
tags: [redis, cache, persistence, cluster, performance, expert]
---

# Redis 专家技能

> 从 SDS 字符串到 Cluster 集群，掌握 Redis 源码级知识

## 核心能力

### 1. 数据结构源码
- **SDS**：简单动态字符串，二进制安全
- **List**：quicklist（ziplist + linkedlist）
- **Hash**：ziplist + hashtable 双结构
- **Set**：intset + hashtable
- **ZSet**：skiplist + hashtable 双结构
- **Stream**：迭代器 + 消息链表

### 2. 持久化机制
- **RDB**：快照复制，fork + COW
- **AOF**：追加日志，rewrite 优化
- **混合持久化**：RDB + AOF 结合
- **恢复策略**：加载顺序、数据一致性

### 3. 集群架构
- **主从复制**：全量 + 增量同步
- **Sentinel**：主从切换、监控告警
- **Cluster**：分片、槽位、节点通信
- **一致性哈希**：虚拟节点、负载均衡

### 4. 性能调优
- **内存优化**：压缩、过期策略、淘汰策略
- **网络优化**：IO 多路复用、零拷贝
- **命令优化**：Pipeline、Lua 脚本
- **监控调优**：Keyspace、Slowlog、Info

## 知识库引用

| 主题 | 文档 |
|------|------|
| Redis 源码 | `knowledge/redis/redis-source.md` |
| Redis 深度 | `knowledge/redis/redis-deep.md` |
| 内核深入 | `knowledge/redis/redis-kernel-deep.md` |
| 集群架构 | `knowledge/redis/redis-cluster-src.md` |
| 内存模型 | `knowledge/redis/redis-memory-model-deep.md` |
| 生产排障 | `knowledge/redis/redis-production-troubleshooting.md` |
| 高并发 | `knowledge/redis/redis-high-concurrency-deep.md` |

## 使用场景

### 场景 1: 数据结构选型
1. 了解各数据结构源码实现
2. 根据使用场景选择合适结构
3. 注意内存占用和性能权衡
4. 使用 memory 命令分析实际占用

### 场景 2: 持久化方案选择
1. 评估数据重要性（可丢失 vs 不可丢失）
2. 评估 RTO/RPO 要求
3. 选择合适的持久化组合
4. 定期测试恢复流程

### 场景 3: 性能问题排查
1. 使用 slowlog 查看慢命令
2. 分析 Keyspace 命中率
3. 检查内存碎片率
4. 优化大 Key 和热点 Key

## 数据结构对比

| 结构 | 底层实现 | 适用场景 | 内存效率 |
|------|---------|---------|---------|
| String | SDS | 缓存、计数器 | ⭐⭐⭐ |
| Hash | ziplist+hashtable | 对象存储 | ⭐⭐⭐⭐ |
| List | quicklist | 消息队列 | ⭐⭐⭐ |
| Set | intset+hashtable | 标签、去重 | ⭐⭐⭐ |
| ZSet | skiplist+hashtable | 排行榜 | ⭐⭐ |
| Stream | 链表 | 消息队列 | ⭐⭐⭐ |

## 自测题

<details>
<summary>Q1: Redis 的 SDS 相比 C 字符串有什么优势？</summary>

**答案**：
1. **常数时间获取长度**：len 字段 O(1)，C 字符串需要 O(n) 遍历
2. **二进制安全**：可以存储任意二进制数据
3. **避免缓冲区溢出**：自动扩容，不会溢出
4. **减少内存重分配**：预分配空间，减少 realloc 次数
5. **兼容 C 字符串**：末尾有 \0，可直接用 C 函数处理

</details>

<details>
<summary>Q2: Redis Cluster 是如何分片的？</summary>

**答案**：
1. **哈希槽 (Hash Slot)**：16384 个槽位
2. **键到槽的映射**：CRC16(key) % 16384
3. **槽位分配**：每个节点负责一部分槽位
4. **迁移机制**：cluster migration，支持在线迁移
5. **客户端路由**：MOVED/ASK 重定向

</details>

<details>
<summary>Q3: Redis 的 AOF 重写 (Rewrite) 原理是什么？</summary>

**答案**：
1. **触发条件**：AOF 文件超过阈值，或手动触发
2. **子进程执行**：fork 子进程，避免阻塞主进程
3. **遍历内存**：子进程遍历所有 key，生成 SET 命令
4. **写日志**：新 AOF 文件只包含最终状态
5. **替换原文件**：原子性替换，保证数据一致性

</details>
