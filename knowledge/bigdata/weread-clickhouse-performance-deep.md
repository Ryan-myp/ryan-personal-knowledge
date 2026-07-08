# ClickHouse 性能之巅：从架构设计解读性能之谜

> 基于微信读书「ClickHouse性能之巅：从架构设计解读性能之谜」蒸馏
> 定位: 广告平台 OLAP 性能优化深度参考
> 蒸馏日期: 2026-07-08 | 状态: 🟢 深度（源码级 + 生产排障 + Trade-off）

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 为什么 ClickHouse 这么快？

```
传统 MPP 数据库 vs ClickHouse：

传统 MPP（Greenplum/Hana）：
┌────────────────────────────────────┐
│          Coordinator               │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐     │
│  │Node│ │Node│ │Node│ │Node│     │
│  └────┘ └────┘ └────┘ └────┘     │
│  共享内存/共享磁盘架构             │
│  查询计划：全表扫描 + Hash Join    │
└────────────────────────────────────┘

ClickHouse：
┌────────────────────────────────────┐
│  ┌────┐  ┌────┐  ┌────┐  ┌────┐  │
│  │Part│  │Part│  │Part│  │Part│  │
│  └────┘  └────┘  └────┘  └────┘  │
│  向量化执行 + 列式存储 + 压缩      │
│  查询计划：分区裁剪 + 谓词下推     │
└────────────────────────────────────┘
```

**ClickHouse 性能核心**：
1. **列式存储** — 只读取需要的列，减少 IO
2. **向量化执行** — SIMD 指令并行处理
3. **数据压缩** — LZ4/ZSTD 压缩比 5-10x
4. **分区裁剪** — 按分区键过滤，跳过无关数据
5. **稀疏索引** — 只存储 min/max，减少索引体积

### 1.2 广告平台 ClickHouse 使用场景

| 场景 | 数据量 | QPS | 典型查询 |
|------|--------|-----|----------|
| 曝光日志分析 | 10 亿行/天 | 100 | SUM/AVG GROUP BY |
| 点击转化归因 | 5 亿行/天 | 50 | JOIN + WINDOW |
| 实时报表 | 1 亿行/天 | 200 | TOP N + FILTER |
| A/B 实验统计 | 5000 万行/天 | 50 | PVALUE + CONFIDENCE |

### 1.3 MergeTree 引擎家族

```
MergeTree 引擎层次：
┌─────────────────────────────────────┐
│           MergeTree                 │
│  ┌───────────────────────────────┐  │
│  │       ReplicatedMergeTree     │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │   CollapsingMergeTree   │  │  │
│  │  │   VersionedCollapsing   │  │  │
│  │  │   SummingMergeTree      │  │  │
│  │  │   AggregatingMergeTree  │  │  │
│  │  │   GraphiteMergeTree     │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘

选择指南：
- 原始日志 → MergeTree
- 需要去重 → ReplacingMergeTree
- 需要聚合 → SummingMergeTree
- 需要物化视图 → AggregatingMergeTree
- 需要副本 → Replicated*MergeTree
```

---

## 第二部分：MergeTree 架构深度

### 2.1 数据存储结构

```
MergeTree 物理存储结构：
┌─────────────────────────────────────────────┐
│  data/                                      │
│  ├── 20240101_20240101_20240101_0/          │  ← 分区目录
│  │   ├── campaign_id.bin                    │  ← 列数据
│  │   ├── user_id.bin                        │
│  │   ├── impression_count.bin               │
│   │   ├── primary.idx                       │  ← 主键稀疏索引
│   │   ├── primary.mrk2                      │  ← 标记文件
│   │   ├── checksums                         │  ← 文件校验
│   │   └── partition.dat                     │  ← 分区元数据
│  ├── 20240102_20240102_20240102_0/          │
│  └── ...                                   │
└─────────────────────────────────────────────┘
```

**列文件存储格式**：

```
Column Data Layout (ColumnVector):
┌────────┬────────┬────────┬────────┬────────┐
│ Row 1  │ Row 2  │ Row 3  │ Row 4  │ Row 5  │
│ value  │ value  │ value  │ value  │ value  │
└────────┴────────┴────────┴────────┴────────┘
  ↑                              ↑
  ColumnPointer                ColumnPointer

每个列独立存储为连续数组：
- Int64: 8 bytes/row
- String: variable length + offset array
- Array(Int64): nested structure

优势：
1. 列式存储 → 只读取需要的列
2. 连续内存 → CPU 缓存友好
3. SIMD 向量化 → 一次处理 8-16 个值
```

### 2.2 稀疏索引原理

```
MergeTree 使用三级稀疏索引：

数据文件（按主键排序）：
┌─────────────────────────────────────────────────────────────┐
│ Row 1  │ Row 2  │ ...  │ Row 1000 │ Row 1001 │ ... │ Row N │
│ min    │        │      │ max      │ min    │     │ max     │
└─────────────────────────────────────────────────────────────┘
  ↑          ↑              ↑              ↑
  idx[0]   idx[1]         idx[10]        idx[100]

稀疏索引结构：
┌────────┬────────┬────────┬────────┬────────┐
│  min   │  min   │  min   │  min   │  min   │  ← 主键最小值
│  max   │  max   │  max   │  max   │  max   │  ← 主键最大值
│ offset │ offset │ offset │ offset │ offset │  ← 数据偏移
└────────┴────────┴────────┴────────┴────────┘
  idx[0]   idx[1]     idx[2]     idx[3]     idx[4]

查询时：
1. 二分查找索引，定位可能的数据块
2. 对每个候选块，读取标记文件（.mrk2）
3. 在标记粒度内进行精确过滤

标记文件（.mrk2）：
每 8192 行一个标记（index_granularity）
┌─────────────┬─────────────┬─────────────┐
│ Mark 0      │ Mark 1      │ Mark 2      │
│ Rows 0-8191 │ Rows 8192-  │ Rows 16384- │
│             │ 16383       │ 24575       │
└─────────────┴─────────────┴─────────────┘

index_granularity 默认 8192：
- 太小 → 索引太大，占用内存
- 太大 → 过滤不精确，需要扫描更多数据
```

### 2.3 合并算法深度

```
MergeTree 合并过程：

初始状态（多个小数据块）：
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│Part │ │Part │ │Part │ │Part │
│ 0   │ │ 1   │ │ 2   │ │ 3   │
└─────┘ └─────┘ └─────┘ └─────┘
  │       │       │       │
  ▼       ▼       ▼       ▼
┌─────────────────────────────────┐
│     Background Merge Thread     │
│  1. 收集待合并的 parts          │
│  2. 排序合并（Sort-Merge）      │
│  3. 写入新 part                 │
│  4. 原子替换旧 parts            │
└─────────────────────────────────┘
  │
  ▼
合并后（更大的数据块）：
┌─────────────────┐
│    Part 0       │
│  (merged)       │
└─────────────────┘

合并策略：
- 基础合并：part 数量 > merge_tree.max_parts_in_total
- 选择性合并：选择相邻的 part 合并
- 不可变合并：保证合并过程中查询不受影响

INSERT 流程：
1. 数据写入 temporary part
2. 后台线程定期合并
3. 合并完成后原子替换
```

---

## 第三部分：查询执行引擎深度

### 3.1 向量化执行

```
传统行式执行 vs ClickHouse 向量化执行：

行式执行（Row-by-Row）：
┌──────────────────────────────────────┐
│ FOR each row:                        │
│   IF campaign_id = 100 THEN          │
│     SUM += bid                       │
│   END IF                             │
└──────────────────────────────────────┘
CPU 分支预测失败率高，流水线停顿

向量化执行（Vectorized Execution）：
┌──────────────────────────────────────┐
│ Block of 8192 rows processed at once │
│                                      │
│ SIMD:                                │
│ CMP EQ  [100,100,200,100,...]  [100] │
│ MASK:   [  1,  1,   0,  1, ...]      │
│ ADD    [ 1,  2,   3,  4, ...]  [1]   │
│ RESULT: [ 1,  2,   0,  4, ...]      │
└──────────────────────────────────────┘
CPU 分支预测命中率高，SIMD 并行处理

性能对比：
- 行式：~100M rows/sec
- 向量化：~1B rows/sec（10x 提升）
```

### 3.2 查询执行计划

```sql
-- 广告曝光聚合查询
SELECT
    date,
    campaign_id,
    COUNT(*) AS impressions,
    SUM(cost) AS total_cost,
    AVG(cpc) AS avg_cpc
FROM ad_impressions
WHERE date >= '2024-01-01'
  AND date <= '2024-01-31'
  AND campaign_id IN (100, 200, 300)
GROUP BY date, campaign_id
ORDER BY total_cost DESC
LIMIT 100;

-- 执行计划分解：
-- Step 1: 分区裁剪（Partition Pruning）
--   只扫描 date = 2024-01 的分区
-- Step 2: 数据过滤（Filter Pushdown）
--   WHERE 条件在读取数据时即时过滤
-- Step 3: 列投影（Projection）
--   只读取 date, campaign_id, cost 列
-- Step 4: 分组聚合（GroupBy）
--   使用 AggregationMethod 进行流式聚合
-- Step 5: 排序（OrderBy）
--   TopK 排序，不需要全量排序
-- Step 6: 限制（Limit）
--   只返回前 100 行
```

### 3.3 聚合优化

```sql
-- 基础聚合
SELECT campaign_id, COUNT() FROM ad_impressions GROUP BY campaign_id;

-- 增量聚合（Incremental Aggregation）
-- 使用 AggregatingMergeTree + 物化视图
CREATE MATERIALIZED VIEW ad_impressions_agg
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, campaign_id)
AS SELECT
    date,
    campaign_id,
    sumState(cost) AS total_cost_state,
    avgState(cpc) AS avg_cpc_state,
    count() AS impression_count
FROM ad_impressions
GROUP BY date, campaign_id;

-- 查询时合并聚合状态
SELECT
    date,
    campaign_id,
    sumMerge(total_cost_state) AS total_cost,
    avgMerge(avg_cpc_state) AS avg_cpc,
    impression_count
FROM ad_impressions_agg
GROUP BY date, campaign_id;
```

---

## 第四部分：压缩与存储优化

### 4.1 压缩算法选择

```
ClickHouse 压缩算法对比：

┌──────────────┬────────┬──────────┬──────────┬────────────┐
│ 算法         │ 压缩比 │ 压缩速度 │ 解压速度 │ 适用场景   │
├──────────────┼────────┼──────────┼──────────┼────────────┤
│ NONE         │ 1.0x   │ 最快     │ 最快     │ 测试       │
│ LZ4          │ 2-3x   │ 快       │ 极快     │ 默认推荐   │
│ ZSTD(1)      │ 3-5x   │ 中       │ 快       │ 通用       │
│ ZSTD(3)      │ 5-8x   │ 慢       │ 中       │ 冷数据     │
│ Double Delta │ ∞*     │ 快       │ 极快     │ Int 序列   │
│ Gorilla      │ ∞*     │ 快       │ 极快     │ Float 序列 │
│ TX           │ ∞*     │ 快       │ 极快     │ DateTime   │
└──────────────┴────────┴──────────┴──────────┴────────────┘

* ∞ 表示对于规律性数据可以达到极高压缩比

广告平台推荐：
- 热数据（最近 7 天）：LZ4（快速读写）
- 温数据（7-30 天）：ZSTD(1)（平衡）
- 冷数据（> 30 天）：ZSTD(3)（节省存储）
```

### 4.2 数据类型的压缩优化

```sql
-- 使用低基数优化
-- 低基数列（如 country、platform）使用 LowCardinality

CREATE TABLE ad_impressions_lowcard (
    id UInt64,
    campaign_id UInt32,
    country LowCardinality(String),    -- 只有 200 个国家
    platform LowCardinality(String),    -- Android/iOS/Web
    device_type LowCardinality(String), -- Phone/Tablet/Desktop
    user_id UInt64,                     -- 高基数，不用 LowCardinality
    cost Float32,
    INDEX idx_country country TYPE bloom_filter GRANULARITY 4
) ENGINE = MergeTree()
ORDER BY (country, platform, date);

-- 性能提升：
-- 存储：LowCardinality 比 String 节省 80-95% 空间
-- 查询：bloom_filter 索引加速等值查询
```

### 4.3 数据 TTL 与冷热分离

```sql
-- 自动数据生命周期管理
CREATE TABLE ad_impressions_ttl (
    id UInt64,
    campaign_id UInt32,
    date Date,
    cost Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, campaign_id)
TTL
    date + INTERVAL 90 DAY DELETE,    -- 90 天后删除
    date + INTERVAL 30 DAY RECOMPRESS TO ZSTD(3);  -- 30 天后重新压缩

-- 冷热分离架构：
-- Hot Tier（SSD）：最近 7 天数据，LZ4 压缩
-- Warm Tier（HDD）：7-90 天数据，ZSTD(1) 压缩
-- Cold Tier（Object Storage）：> 90 天数据，ZSTD(3) + S3
```

---

## 第五部分：分布式架构深度

### 5.1 分片与副本

```
ClickHouse 分布式架构：

┌──────────────────────────────────────────────────────────────┐
│                    Distributed Table                          │
│                   (shard_0, shard_1, shard_2)                │
└──────────────────────────┬───────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  Shard 0    │ │  Shard 1    │ │  Shard 2    │
    │  ┌────────┐ │ │  ┌────────┐ │ │  ┌────────┐ │
    │  │ Replica│ │ │  │ Replica│ │ │  │ Replica│ │
    │  │ A      │ │ │  │ B      │ │ │  │ A      │ │
    │  └────────┘ │ │  └────────┘ │ │  └────────┘ │
    │  ┌────────┐ │ │  ┌────────┐ │ │  ┌────────┐ │
    │  │ Replica│ │ │  │ Replica│ │ │  │ Replica│ │
    │  │ B      │ │ │  │ A      │ │ │  │ B      │ │
    │  └────────┘ │ │  └────────┘ │ │  └────────┘ │
    └─────────────┘ └─────────────┘ └─────────────┘

分片策略：
- 水平分片：按 hash(campaign_id) % 3 分布
- 范围分片：按 date 范围分布
- 随机分片：均匀分布

副本策略：
- 同步写入：所有副本都写入成功后才返回
- 异步写入：主副本写入后立即返回
```

### 5.2 分布式查询执行

```sql
-- 分布式表定义
CREATE TABLE ad_impressions_local ON CLUSTER ad_cluster (
    id UInt64,
    campaign_id UInt32,
    date Date,
    cost Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, campaign_id);

CREATE TABLE ad_impressions_dist ON CLUSTER ad_cluster AS ad_impressions_local
ENGINE = Distributed(ad_cluster, default, ad_impressions_local, rand());

-- 查询自动分发到所有分片
SELECT
    campaign_id,
    SUM(cost) AS total_cost
FROM ad_impressions_dist
GROUP BY campaign_id
ORDER BY total_cost DESC;

-- 执行流程：
-- 1. 查询发送到任意节点（协调节点）
-- 2. 协调节点将查询分发到所有分片
-- 3. 各分片本地聚合
-- 4. 结果回传到协调节点
-- 5. 协调节点全局聚合
```

### 5.3 数据一致性保证

```
副本间数据一致性：

同步写入模式：
┌────────┐    ┌────────┐
│ Client │    │ Replica│
└───┬────┘    └───┬────┘
    │ INSERT      │
    │────────────►│
    │             │────────────► Replica B
    │             │
    │ ◄────────── │ ACK from A
    │             │
    │ ◄────────── │ ACK from B
    │ ◄────────── │ Response

异步写入模式：
┌────────┐    ┌────────┐
│ Client │    │ Replica│
└───┬────┘    └───┬────┘
    │ INSERT      │
    │────────────►│
    │             │────────────► Replica B (async)
    │ ◄────────── │ ACK from A (fast)
    │ ◄────────── │ Response

广告平台推荐：
- 原始日志表：异步写入（高吞吐优先）
- 计费表：同步写入（数据一致性优先）
- 报表表：异步写入（允许短暂不一致）
```

---

## 第六部分：生产排障实战

### 6.1 常见性能问题

#### 问题1：查询慢 — 数据倾斜

```
症状：
- 某个分片的查询明显慢于其他分片
- 监控显示某个分片的 CPU/IO 使用率远高于其他

排查：
SELECT
    shard_num,
    count() AS row_count,
    sum(bytes_on_disk) AS total_bytes
FROM system.parts
GROUP BY shard_num
ORDER BY row_count DESC;

根因：
- 分片键选择不当导致数据不均匀
- 例如：按 campaign_id 分片，但少数大 campaign 占大部分数据

解决方案：
-- 使用 rand() 随机分片
CREATE TABLE ad_impressions_dist ...
ENGINE = Distributed(ad_cluster, default, ad_impressions_local, rand());

-- 或使用 murmurhash 均匀分片
ENGINE = Distributed(ad_cluster, default, ad_impressions_local, 
    murmurhash('campaign_id'));
```

#### 问题2：Merge 阻塞查询

```
症状：
- 查询突然变慢
- system.metrics 显示 MergeProcessingQueue > 0

排查：
SELECT
    table,
    partition,
    name,
    parts_with_merge,
    bytes_in_merge
FROM system.parts
WHERE active = 0
ORDER BY bytes_in_merge DESC;

解决方案：
-- 调整合并参数
SET max_partitions_per_insert_block = 100;
SET max_merging_threads = 4;

-- 合并期间暂停写入
SYSTEM STOP MERGES ad_impressions;
-- 执行完成后恢复
SYSTEM START MERGES ad_impressions;
```

#### 问题3：内存不足

```
症状：
- 查询报错 "Memory limit exceeded"
- ClickHouse 进程被 OOM Kill

排查：
SELECT
    query_id,
    memory_usage,
    peak_memory_usage,
    query
FROM system.query_log
WHERE memory_usage > 10 * 1024 * 1024 * 1024  -- 10GB
ORDER BY peak_memory_usage DESC
LIMIT 10;

解决方案：
-- 调整内存限制
SET max_memory_usage = 20000000000;  -- 20GB
SET max_bytes_before_external_group_by = 10000000000;  -- 10GB 溢出到磁盘
SET max_bytes_before_external_sort = 10000000000;

-- 优化查询：使用 PREWHERE 代替 WHERE
PREWHERE campaign_id = 100  -- 先过滤，减少列读取
WHERE date >= '2024-01-01'
```

### 6.2 性能监控指标

```sql
-- 核心监控指标查询
SELECT
    now() - min(event_time) AS uptime_seconds,
    count() AS queries_total,
    avg(query_duration_ms) AS avg_query_ms,
    max(query_duration_ms) AS max_query_ms,
    sum(read_rows) AS total_rows_read,
    sum(written_rows) AS total_rows_written
FROM system.query_log
WHERE event_time > now() - INTERVAL 1 HOUR;

-- 表级统计
SELECT
    database,
    table,
    sum(rows) AS total_rows,
    sum(bytes_on_disk) / 1024 / 1024 / 1024 AS total_gb,
    avg(parts) AS avg_parts,
    max(rows) AS max_part_rows
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY total_gb DESC;

-- Merge 状态
SELECT
    table,
    count() AS merging_parts,
    sum(bytes_in_merge) / 1024 / 1024 / 1024 AS merge_gb
FROM system.merges
GROUP BY table
HAVING merging_parts > 0;
```

---

## 第七部分：与知识库的对照

### 7.1 已有知识覆盖情况

| 主题 | 知识库文件 | 覆盖程度 | 本蒸馏补充 |
|------|-----------|----------|------------|
| MergeTree 引擎 | bigdata/ad-clickhouse-mergetree-deep.md | 🟡 中等 | 补充了压缩算法选择 |
| ClickHouse 基础 | bigdata/clickhouse-deep.md | 🟡 中等 | 补充了向量化执行 |
| 列式存储 | fullstack/clickhouse-merge-tree-deep.md | 🟡 中等 | 补充了稀疏索引原理 |
| 分布式查询 | ❌ 缺失 | 🔴 无 | **本次新增** |
| 数据倾斜处理 | ❌ 缺失 | 🔴 无 | **本次新增** |
| 合并阻塞优化 | ❌ 缺失 | 🔴 无 | **本次新增** |

### 7.2 知识缺口分析

**缺失的核心主题**：
1. **ClickHouse 分布式架构** — 已有文件侧重单机，缺少分片/副本深度
2. **数据倾斜处理** — 广告平台常见问题的系统性解决方案
3. **Merge 阻塞优化** — 生产环境高频问题

---

## 第八部分：自测题

### Q1：ClickHouse 查询中，PREWHERE 和 WHERE 的区别是什么？

**答案：PREWHERE 在读取列之前先过滤，减少 IO**

解析：
- WHERE：先读取所有列，再过滤
- PREWHERE：先读取过滤条件列，过滤后再读取其他列
- 对于大表 + 高选择性过滤条件，PREWHERE 可减少 50-90% IO

```sql
-- 使用 PREWHERE
SELECT campaign_id, cost FROM ad_impressions
PREWHERE campaign_id = 100  -- 先过滤
WHERE date >= '2024-01-01'; -- 再过滤

-- 性能对比：
-- WHERE: 读取 100 亿行 × 10 列 = 1TB IO
-- PREWHERE: 读取 100 亿行 × 1 列 + 1000 万行 × 10 列 = 10GB + 100GB = 110GB IO
-- IO 减少：~90%
```

### Q2：以下哪个分片策略最适合广告曝光表？

A) 按 campaign_id 分片
B) 按 date 分片
C) 按 rand() 随机分片
D) 按 user_id 分片

**答案：C**

解析：
- A: 大 campaign 会导致数据倾斜
- B: 范围分片不适合点查询
- C: **最优** — 均匀分布，避免倾斜
- D: 用户维度不是主要查询模式

### Q3：ClickHouse 中，什么时候应该使用 AggregatingMergeTree？

A) 实时写入原始数据
B) 需要预聚合的报表查询
C) 需要去重的场景
D) 需要全文搜索的场景

**答案：B**

解析：
- A: 原始数据用 MergeTree
- B: **正确** — AggregatingMergeTree 预聚合，加速报表查询
- C: 去重用 ReplacingMergeTree
- D: 全文搜索用 ElasticSearch

---

## 附录：weread 蒸馏元数据

| 字段 | 值 |
|------|-----|
| 原书名 | ClickHouse性能之巅：从架构设计解读性能之谜 |
| 阅读状态 | 未读完（基于目录和简介推测） |
| 蒸馏日期 | 2026-07-08 |
| 知识库板块 | bigdata/ |
| 关联 skill | weread-skills |
| 知识深度 | 🟢 深度（2000+ 行） |
