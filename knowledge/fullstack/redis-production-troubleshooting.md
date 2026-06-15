# Redis 生产排障实战

> 内存溢出/持久化失败/集群故障/主从延迟/热点 Key 排查

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台 Redis 常见问题

| 问题 | 现象 | 根因 |
|------|------|------|
| 内存溢出 | OOM/Killed | 数据量超内存 |
| 持久化失败 | AOF 损坏 | 磁盘满 |
| 集群故障 | 节点 Down | 网络/磁盘 IO |
| 主从延迟 | 数据不一致 | 复制链路慢 |
| 热点 Key | 单节点被打爆 | 大 Key/热 Key |

---

## 第二部分：内存溢出排查

### 2.1 内存监控

```bash
# 查看内存使用
redis-cli INFO memory

# 关键字段
# used_memory: 已使用内存
# used_memory_peak: 峰值内存
# mem_fragmentation_ratio: 内存碎片率
# evicted_keys: 被驱逐的 key 数

# 查看大 Key
redis-cli --bigkeys

# 查看内存分布
redis-cli MEMORY DOCTOR
redis-cli MEMORY STATS

# 监控内存趋势
redis-cli INFO memory | grep used_memory_human
```

### 2.2 内存优化

```bash
# 设置最大内存
maxmemory 8gb

# 设置淘汰策略
maxmemory-policy allkeys-lru

# 可选策略:
# volatile-lru: 有过期时间的 key 使用 LRU
# allkeys-lru: 所有 key 使用 LRU
# volatile-ttl: 优先删除 TTL 短的
# noeviction: 不删除，返回错误

# 查看淘汰统计
redis-cli INFO stats | grep evicted_keys

# 查看某个 key 的内存使用
redis-cli MEMORY USAGE mykey
redis-cli MEMORY USAGE mykey SAMPLES 5
```

### 2.3 大 Key 优化

```go
package redis

import (
    "context"
    "fmt"
)

// 大 Key 拆分
type BigKeySplitter struct {
    client *redis.Client
}

// 拆分 Hash
func (s *BigKeySplitter) SplitHash(key string, batchSize int) error {
    cursor := uint64(0)
    batch := make([]string, 0, batchSize)
    
    for {
        keys, newCursor, err := s.client.HScan(context.Background(), key, cursor, "*", batchSize).Result()
        if err != nil {
            return err
        }
        
        for i, k := range keys {
            v := keys[i+1]
            // 拆分到子 key
            subKey := fmt.Sprintf("%s:%s", key, k)
            s.client.Set(context.Background(), subKey, v, 0)
            batch = append(batch, k)
        }
        
        cursor = newCursor
        if cursor == 0 {
            break
        }
    }
    
    // 删除原 key
    s.client.Del(context.Background(), key)
    return nil
}

// 热 Key 检测
func (s *BigKeySplitter) DetectHotKeys() ([]string, error) {
    // 使用 redis-cli --hotkeys
    // 或使用 Redis 4.0+ 的 LATENCY DOCTOR
    return []string{}, nil
}
```

---

## 第三部分：持久化失败排查

### 3.1 RDB 排查

```bash
# 查看 RDB 状态
redis-cli INFO persistence

# 关键字段
# rdb_last_bgsave_status: 最后一次 BGSAVE 状态
# rdb_last_bgsave_time_sec: BGSAVE 耗时
# rdb_last_save_time: 最后保存时间

# 手动触发 BGSAVE
redis-cli BGSAVE

# 查看 RDB 文件
redis-cli DEBUG SLEEP 0
ls -lh /var/lib/redis/dump.rdb

# RDB 损坏恢复
redis-check-rdb dump.rdb
```

### 3.2 AOF 排查

```bash
# 查看 AOF 状态
redis-cli INFO persistence

# 关键字段
# aof_enabled: 是否启用
# aof_rewrite_in_progress: 是否在重写
# aof_last_rewrite_time_sec: 上次重写耗时
# aof_current_size: 当前 AOF 大小

# 手动触发 AOF 重写
redis-cli BGREWRITEAOF

# AOF 修复
redis-check-aof /var/lib/redis/aof.aof
redis-check-aof --fix /var/lib/redis/aof.aof

# AOF 配置优化
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

### 3.3 持久化性能优化

```
AOF 重写优化:
1. 使用 no-appendfsync-on-rewrite: yes
2. 限制 BGSAVE 频率
3. 监控 AOF 文件大小

RDB 优化:
1. 设置合适的 save 间隔
2. 监控 BGSAVE 耗时
3. 使用 SSD 存储 RDB
```

---

## 第四部分：集群故障排查

### 4.1 集群状态检查

```bash
# 查看集群状态
redis-cli CLUSTER INFO
redis-cli CLUSTER NODES

# 关键字段
# cluster_state: ok/degraded/fail
# cluster_known_nodes: 已知节点数
# cluster_size: 集群大小

# 检查节点健康
redis-cli -c ping
redis-cli -c cluster nodes

# 查看节点日志
tail -f /var/log/redis/redis-server.log
```

### 4.2 节点故障恢复

```bash
# 节点 Down 后的恢复步骤:
# 1. 确认故障节点
redis-cli CLUSTER NODES | grep fail

# 2. 尝试重启故障节点
systemctl restart redis-server

# 3. 如果数据丢失，从主节点复制
redis-cli CLUSTER FAILOVER

# 4. 重新加入集群
redis-cli CLUSTER MEET <ip> <port>

# 5. 重新分配 slot
redis-cli CLUSTER ADDSLOTS <slot1> <slot2> ...
```

### 4.3 脑裂预防

```
脑裂预防策略:
1. 设置 min-replicas-to-write 3
2. 设置 min-replicas-max-lag 10
3. 使用哨兵自动故障切换
4. 监控主从延迟

哨兵配置:
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1
```

---

## 第五部分：自测题

### 问题 1
Redis 内存溢出怎么排查？

<details>
<summary>查看答案</summary>

1. redis-cli INFO memory 查看内存使用
2. redis-cli --bigkeys 查找大 Key
3. 检查 maxmemory 和淘汰策略
4. 监控内存碎片率
5. 优化：拆分大 Key，设置 TTL

</details>

### 问题 2
AOF 和 RDB 怎么选？

<details>
<summary>查看答案</summary>

1. RDB: 快照，恢复快，可能丢数据
2. AOF: 追加写，数据完整，文件大
3. 生产推荐: 两者都开
4. AOF 重写: BGREWRITEAOF
5. 恢复: RDB 快，AOF 完整

</details>

### 问题 3
Redis 集群脑裂怎么预防？

<details>
<summary>查看答案</summary>

1. min-replicas-to-write: 3
2. min-replicas-max-lag: 10
3. 哨兵自动故障切换
4. 监控主从延迟
5. 使用云 Redis 托管服务

</details>

---

*本文档基于 Redis 生产排障经验整理。*