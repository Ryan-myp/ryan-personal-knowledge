# ClickHouse 深度：MergeTree/物化视图/分布式查询源码级

> 逐行解析 ClickHouse 核心存储引擎和查询优化

---

## 第一部分：MergeTree 源码深度

### MergeTree 架构

```
MergeTree 存储引擎：
┌─────────────────────────────────────────────────────────────────────┐
│ 数据文件结构：                                                        │
│                                                                     │
│ data/                                                               │
│ └── table_name/                                                     │
│     ├── primary.idx      # 主键索引                                  │
│     ├── parts/                                                    │
│     │   ├── 20240101_1_1_0/                                    │
│     │   │   ├── count.txt          # 行数                              │
│     │   │   ├── marks/             # 标记文件（8192 行一个 mark）        │
│     │   │   │   ├── 00001.mrk       # mark 0: 行 1-8192              │
│     │   │   │   ├── 00002.mrk       # mark 1: 行 8193-16384          │
│     │   │   │   └── ...                                             │
│     │   │   ├── columns/                                           │
│     │   │   │   ├── date.bin        # 日期列（LZ4 压缩）              │
│     │   │   │   ├── user_id.bin     # 用户 ID 列（LZ4 压缩）          │
│     │   │   │   ├── amount.bin      # 金额列（LZ4 压缩）              │
│     │   │   │   └── ...                                             │
│     │   │   └── checksums.txt      # 文件校验和                      │
│     │   ├── 20240102_2_2_0/                                    │
│     │   └── ...                                                     │
│     └── ...                                                       │
└─────────────────────────────────────────────────────────────────────┘

MergeTree 核心概念：
• Primary Key：主键索引（稀疏索引，每 8192 行一个 mark）
• Partition：分区（按月/天/自定义），物理隔离
• Order By：排序键，决定数据在磁盘上的排列顺序
• Granule：粒度（8192 行），查询的最小单位
```

### 查询执行流程

```
SELECT * FROM orders WHERE date = '2024-01-15' AND user_id = 123;

1. 分区裁剪（Partition Pruning）：
   只扫描 202401 分区，跳过其他分区

2. 主键索引扫描（Primary Key Index Scan）：
   利用稀疏索引定位 user_id = 123 的 granule

3. 数据读取（Data Reading）：
   只读取标记的 granule（约 8192 行）

4. 过滤（Filtering）：
   在 granule 内精确过滤 user_id = 123

5. 聚合/排序（Aggregation/Sorting）：
   如果需要 GROUP BY/ORDER BY
```

---

## 第二部分：物化视图深度

```sql
-- 物化视图（Materialized View）
CREATE MATERIALIZED VIEW orders_daily_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, platform, campaign_id)
AS SELECT
    toDate(date) as date,
    platform,
    campaign_id,
    sumState(impressions) as impressions_sum,
    sumState(clicks) as clicks_sum,
    sumState(spend) as spend_sum,
    uniqState(user_id) as unique_users
FROM orders
GROUP BY date, platform, campaign_id;

-- 查询物化视图
SELECT
    date,
    platform,
    campaign_id,
    sumMerge(impressions_sum) as total_impressions,
    sumMerge(clicks_sum) as total_clicks,
    sumMerge(spend_sum) as total_spend,
    uniqMerge(unique_users) as total_users
FROM orders_daily_mv
WHERE date >= '2024-01-01'
GROUP BY date, platform, campaign_id;
```

---

## 第三部分：分布式查询深度

```sql
-- 分布式表（Distributed Table）
CREATE TABLE orders_dist ON CLUSTER ad_cluster AS orders
ENGINE = Distributed(ad_cluster, default, orders, rand());

-- 查询分布式表（自动路由到各分片）
SELECT platform, sum(impressions) as total_imp
FROM orders_dist
WHERE date = '2024-01-15'
GROUP BY platform;

-- 执行流程：
-- 1. 查询解析：解析 SQL
-- 2. 查询重写：转换为本地查询
-- 3. 分片路由：发送到各分片
-- 4. 并行执行：各分片本地执行
-- 5. 结果合并：合并各分片结果
-- 6. 返回客户端
```

---

## 第四部分：自测题

### Q1: MergeTree 的主键索引为什么是稀疏的？

**A**: 稀疏索引（每 8192 行一个 mark）减少索引大小，查询时用 granule 级别扫描，再在 granule 内精确过滤。

### Q2: 物化视图和普通视图的区别？

**A**: 物化视图物理存储聚合结果，查询快但写入慢；普通视图不存储数据，每次查询实时计算。

### Q3: 分布式查询的执行流程？

**A**: 查询解析 → 重写 → 分片路由 → 并行执行 → 结果合并 → 返回。

---

## 第五部分：生产实践

### 1. 表设计

```
表设计要点：
1. 选择合适的分区键（按月/天）
2. Order By 包含高频查询条件
3. 使用 TTL 自动清理历史数据
4. 合理设置 granularity（默认 8192）
```

### 2. 查询优化

```
查询优化要点：
1. 使用 WHERE 前置条件，减少扫描量
2. 避免 SELECT *，只查需要的列
3. 使用物化视图预聚合
4. 批量插入而非单条插入
```

### 3. 运维监控

```
运维监控要点：
1. 监控 Merge 进度
2. 监控磁盘使用
3. 监控查询延迟
4. 定期 OPTIMIZE TABLE
```
