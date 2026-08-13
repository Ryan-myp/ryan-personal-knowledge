# ClickHouse 分布式表深度蒸馏

> 来源：ClickHouse 官方源码 `StorageDistributed.cpp`
> 蒸馏日期：2026-01-15
> 核心价值：生产级分布式架构 + 实战调优经验

---

## 一、分布式表架构设计

### 1.1 核心数据结构
```cpp
// StorageDistributed.h 核心字段
class StorageDistributed : public IStorage {
    String cluster_name;          // 集群名称
    String shard_name;            // 当前分片名称
    String database;              // 数据库名
    String table;                 // 表名
    
    /// 远程服务器地址池
    ClusterPtr cluster;
    
    /// 写入策略
    enum WriteMode {
        ON_CLUSTER,         // 直接写入集群
        LOCAL,             // 本地写入
        INDETERMINISTIC    // 不确定模式
    };
};
```

### 1.2 查询路由机制
```cpp
// 查询如何在分片间分发
std::unique_ptr<QueryPlan> StorageDistributed::read(
    const Names &,
    const MetadataSnapshot &,
    SelectQueryInfo &query_info,
    ContextPtr context,
    QueryProcessingStage::Enum processed_stage,
    ...) {
    
    // 1. 决定查询目标（本地 or 远程）
    auto target_shards = getTargetShards();
    
    // 2. 构建远程查询
    for (auto &shard : target_shards) {
        auto query_per_shard = buildQueryForShard(shard);
        pipelines.push_back(executeQuery(query_per_shard));
    }
    
    // 3. 合并结果
    return createUnionPipeline(pipelines);
}
```

---

## 二、关键优化策略

### 2.1 Skip Unused Shards（跳过不需要的分片）
```cpp
// 核心逻辑
const UInt64 FORCE_OPTIMIZE_SKIP_UNUSED_SHARDS_HAS_SHARDING_KEY = 1;
const UInt64 FORCE_OPTIMIZE_SKIP_UNUSED_SHARDS_ALWAYS           = 2;

// 配置示例
<clickhouse>
    <distributed>
        <optimize_skip_unused_shards>1</optimize_skip_unused_shards>
        <force_optimize_skip_unused_shards>1</force_optimize_skip_unused_shards>
    </distributed>
</clickhouse>
```

**实战效果**：
```
场景：查询特定 campaign_id 的广告数据
原始：扫描所有 10 个分片
优化：只扫描包含该 campaign 的 2 个分片
效果：查询速度提升 5x
```

### 2.2 Parallel Distributed Insert（并行分布式插入）
```cpp
const UInt64 PARALLEL_DISTRIBUTED_INSERT_SELECT_ALL = 2;

// 配置
<clickhouse>
    <distributed>
        <parallel_distributed_insert_select>2</parallel_distributed_insert_select>
    </distributed>
</clickhouse>
```

**工作原理**：
```
1. 客户端执行 SELECT
2. 同时并行向所有分片 INSERT
3. 本地服务器收集结果并返回

优点：充分利用集群带宽
注意：需要保证 SELECT 和 INSERT 的数据一致性
```

### 2.3 Background Insert（后台批量插入）
```cpp
// 后台插入配置
<distributed>
    <background_insert_batch>1</background_insert_batch>
    <background_insert_max_sleep_time_ms>100</background_insert_max_sleep_time_ms>
    <background_insert_split_batch_on_failure>1</background_insert_split_batch_on_failure>
</distributed>
```

**适用场景**：
```
✅ 高吞吐写入场景（日志、埋点）
✅ 可以容忍轻微延迟
❌ 实时性要求高的场景

示例：
INSERT INTO distributed_table VALUES (...);
-- 实际执行：
-- 1. 写入本地 buffer
-- 2. 后台合并后写入远程分片
```

---

## 三、分片策略实战

### 3.1 分片键选择
```sql
-- 方案 1：按时间分片（适合时序数据）
CREATE TABLE ads_events ON CLUSTER default_cluster
(
    event_time DateTime,
    campaign_id UInt32,
    ...
)
ENGINE = Distributed(default_cluster, default, ads_events_local, 
    toUInt32(toUnixTimestamp(event_time) / 86400));  -- 按天分片

-- 方案 2：按业务键分片（适合查询优化）
CREATE TABLE ads_events ON CLUSTER default_cluster
(
    campaign_id UInt32,
    ...
)
ENGINE = Distributed(default_cluster, default, ads_events_local, 
    hash(campaign_id));  -- 相同 campaign 在同一分片
```

### 3.2 分片数选择
```
原则：
1. 分片数 = 集群节点数（简单均匀分布）
2. 分片数 = 查询热度 * 副本数（热点优化）
3. 分片数不要过多（增加查询复杂度）

推荐：
- 中小规模：3-5 个分片
- 大规模：10-20 个分片
- 超大规模：按业务分区
```

---

## 四、性能调优配置

### 4.1 查询优化
```xml
<clickhouse>
    <distributed>
        <!-- 跳过不需要的分片 -->
        <optimize_skip_unused_shards>1</optimize_skip_unused_shards>
        <optimize_skip_unused_shards_limit>100</optimize_skip_unused_shards_limit>
        
        <!-- 禁止 GROUP BY 合并（减少网络传输） -->
        <distributed_group_by_no_merge>2</distributed_group_by_no_merge>
        
        <!-- 优先本地副本 -->
        <prefer_localhost_replica>1</prefer_localhost_replica>
    </distributed>
</clickhouse>
```

### 4.2 写入优化
```xml
<clickhouse>
    <distributed>
        <!-- 批量写入阈值 -->
        <bytes_to_delay_insert>1048576</bytes_to_delay_insert>
        <bytes_to_throw_insert>10485760</bytes_to_throw_insert>
        <max_delay_to_insert>1</max_delay_to_insert>
        
        <!-- 失败重试 -->
        <distributed_background_insert_split_batch_on_failure>1</distributed_background_insert_split_batch_on_failure>
    </distributed>
</clickhouse>
```

### 4.3 内存优化
```xml
<clickhouse>
    <distributed>
        <!-- 限制分布式查询内存 -->
        <max_bytes_before_external_group_by>1000000000</max_bytes_before_external_group_by>
        <max_memory_usage>10000000000</max_memory_usage>
    </distributed>
</clickhouse>
```

---

## 五、常见问题排查

### 5.1 查询慢的原因
```sql
-- 检查分片分布
SELECT shard_name, count() 
FROM system.distributed_tables 
GROUP BY shard_name;

-- 查看查询路由
SELECT query, shards, executed_rows 
FROM system.query_log 
WHERE query LIKE '%distributed%';
```

### 5.2 写入延迟
```sql
-- 检查后台写入队列
SELECT * FROM system.distributed_queues;

-- 查看写入延迟
SELECT 
    now() - max(event_time) as max_delay
FROM ads_events;
```

### 5.3 数据不一致
```sql
-- 检查分片数据一致性
SELECT 
    shard_name,
    count() as row_count
FROM ads_events ON CLUSTER default_cluster
GROUP BY shard_name;

-- 修复不一致
ALTER TABLE ads_events ON CLUSTER default_cluster 
DROP PARTITION '20240101';
```

---

## 六、生产级最佳实践

### 6.1 架构模式
```
Layer 1: 接入层（Nginx/HAProxy）
         ↓
Layer 2: 分布式表（路由分发）
         ↓
Layer 3: 本地表（实际存储）
         ↓
Layer 4: 物化视图（预聚合）
```

### 6.2 监控指标
```bash
# 关键监控指标
1. 分片均衡度：每个分片的行数差异 < 20%
2. 查询延迟：p99 < 100ms（本地），< 500ms（分布式）
3. 写入延迟：后台队列堆积 < 1000 条
4. 内存使用：单分片 < 50GB
```

### 6.3 容量规划
```
公式：
单分片大小 = 总数据量 / 分片数
建议：单分片 ≤ 500GB（压缩后）

分片数 = ceil(总数据量 / 500GB) * 副本数
```

---

## 七、核心设计洞察

### 1. 分布式查询的本质
```
查询分解 → 并行执行 → 结果合并
```

### 2. 写入策略的权衡
```
Foreground: 强一致，高延迟
Background: 最终一致，低延迟
```

### 3. 分片键的选择
```
根据查询模式选择：
- 时间范围查询 → 时间分片
- 点查优化 → 业务键分片
- 分析查询 → 哈希分片
```

---

**核心洞察**：ClickHouse 分布式表的精髓在于"简单路由 + 智能优化"——分片键决定数据分布，查询优化器决定执行路径，两者结合实现高性能分布式分析。
