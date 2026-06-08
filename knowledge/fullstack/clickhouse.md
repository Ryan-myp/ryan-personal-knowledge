# ClickHouse 原理 — MergeTree、列式存储、OLAP 调优

> 标签: `#ClickHouse` `#MergeTree` `#列式存储` `#OLAP` `#调优`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. ClickHouse 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    ClickHouse 集群                           │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │  CH Node │  │  CH Node │  │  CH Node │                 │
│  │  (Co-ord)│  │          │  │          │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
│       │              │              │                       │
│  ┌────▼──────────────▼──────────────▼─────┐                │
│  │            ZooKeeper (协调层)           │                │
│  │  - 副本元数据                            │                │
│  │  - 分片分配                              │                │
│  │  - 分布式 DDL                           │                │
│  │  - 副本同步状态                          │                │
│  └────────────────────────────────────────┘                │
│                                                             │
│  存储层:                                                   │
│  ┌────────────────────────────────────────┐                │
│  │  MergeTree Engine 家族                  │                │
│  │  - primary key (排序键)                 │                │
│  │  - partition key (分区键)               │                │
│  │  - sampling key (采样键)                │                │
│  │  - data parts (数据片段)                │                │
│  └────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 列式存储

### 2.1 行存 vs 列存

```
行存储 (MySQL/PostgreSQL):
  Row 1: | id=1 | name='Alice' | age=25 | city='BJ' |
  Row 2: | id=2 | name='Bob'   | age=30 | city='SH' |
  Row 3: | id=3 | name='Carol' | age=28 | city='GZ' |
  
  查询 SELECT name, age FROM t WHERE city='BJ':
  → 读取 Row 1, 2, 3 所有列 → 过滤 city → 返回 name, age
  → 浪费: 读入了不必要的 city 列数据

列存储 (ClickHouse):
  id:   | 1 | 2 | 3 |
  name: | Alice | Bob | Carol |
  age:  | 25 | 30 | 28 |
  city: | BJ | SH | GZ |
  
  查询 SELECT name, age FROM t WHERE city='BJ':
  → 只读取 name, age, city 三列
  → city 列通过 Compressed Block 快速过滤
  → 节省 IO: 只读取需要的列

列存优势:
  1. 压缩率高: 同列数据类型相同，压缩效果好（Delta + LZ4/ZSTD）
  2. 扫描速度快: 只读需要的列，减少 IO
  3. 适合 OLAP: 聚合查询涉及少量列的统计
  
列存劣势:
  1. 点查询慢: 查单行需要读所有列
  2. 更新/删除成本高: 数据不可变设计
  3. 不适合事务型场景
```

### 2.2 数据文件组织

```
MergeTree 表的物理存储:

/data/
└── table_name/
    ├── primary.key      ← 主键跳表（.mrk2 文件）
    ├── sk_1.idx         ← 稀疏索引
    ├── sk_2.idx
    ├── count.txt        ← 行数
    ├── columns.bin      ← 列数据（合并存储）
    ├── column_name/column_name.mrk2
    ├── column_name/column_name.bin.gz
    ├── column_name2/column_name2.bin.gz
    ├── ...
    └── minmax_timestamp.idx  ← 分区最小最大值索引
```

---

## 3. MergeTree 引擎家族

### 3.1 MergeTree 核心概念

```
MergeTree 表结构:

┌─────────────────────────────────────────────────────────────┐
│  分区 (Partition)                                          │
│  ├─ 分区 1 (2026-01)                                       │
│  │  ├─ Part 1 (all_1_1_0) → 初始写入的数据                   │
│  │  ├─ Part 2 (all_1_2_0) → 后续写入的增量数据               │
│  │  └─ Part 3 (all_2_3_0)                                 │
│  │     └─ 后台 Merge 线程: Part 1 + Part 2 + Part 3        │
│  │         → all_3_3_0 (合并后的单一 Part)                   │
│  │                                                          │
│  ├─ 分区 2 (2026-02)                                       │
│  │  └─ Part 4 (all_4_4_0)                                 │
│  │     └─ Merge → all_4_4_0                               │
│  └─ ...                                                    │
└─────────────────────────────────────────────────────────────┘

排序键 (ORDER BY):
  - 定义数据在 Part 内部的排序方式
  - 自动构建稀疏索引（每 8192 行一个索引点）
  - 稀疏索引支持: primary key, skip indices, projection

分区键 (PARTITION BY):
  - 物理分区，按分区删除/移动数据
  - 常用: toYYYYMM(date), toStartOfHour(timestamp)
  - 分区不可嵌套，建议分区数 < 1000

主键 (PRIMARY KEY):
  - MergeTree 中 PRIMARY KEY = ORDER BY 的前缀
  - 实际用于构建稀疏索引
  - 稀疏索引: 每 8192 行取一个 (key, offset) 对
```

### 3.2 稀疏索引机制

```
数据行:
  row 1:  (age=20, name='A', ...)
  row 2:  (age=21, name='B', ...)
  ...
  row 8192: (age=25, name='V', ...)
  row 8193: (age=25, name='W', ...)
  ...
  row 16384: (age=28, name='AA', ...)

稀疏索引 (每 8192 行):
  (20, offset=0)     → Part 中第 0 行
  (25, offset=8192)  → Part 中第 8192 行
  (28, offset=16384) → Part 中第 16384 行

查询 age = 25:
  1. 二分查找稀疏索引 → 定位到 offset=8192
  2. 从 offset=8192 开始逐行扫描 → 找到所有 age=25 的行
  3. 精确匹配 age=25 的记录

查询 age BETWEEN 21 AND 27:
  1. 二分查找 sparse index → age=21, age=25
  2. 扫描 offset=0 ~ offset=16384 之间的数据
  3. 过滤 age BETWEEN 21 AND 27

粒度 (index_granularity):
  - 默认 8192 个行标记（marks）
  - 可调整，但不建议改（太小索引大，太大扫描慢）
```

### 3.3 MergeTree 引擎家族

```
MergeTree 系列:
  - MergeTree: 基础引擎，支持分区、排序、稀疏索引
  - ReplacingMergeTree: 去重（按 ORDER BY 保留最新版本）
  - CollapsingMergeTree: 状态维护（SIGN=+1/-1 抵消）
  - SummingMergeTree: 聚合（按 ORDER BY 求和）
  - VersionedCollapsingMergeTree: 带版本的 Collapsing
  - GraphiteMergeTree: 时序数据聚合
  
分布式:
  - Distributed: 分布式表（不存数据，仅路由）
  - 数据实际存储在分片的 MergeTree 表中
  
高可用:
  - ReplicatedMergeTree: ZooKeeper 协调的副本
  - 副本间自动同步数据
```

### 3.4 ReplacingMergeTree 实战

```sql
-- 订单表，同一订单可能多次更新
CREATE TABLE orders (
    order_id UInt64,
    user_id UInt64,
    status String,
    updated_at DateTime
) ENGINE = ReplacingMergeTree()
ORDER BY (order_id, user_id)
PARTITION BY toYYYYMM(updated_at);

-- 插入同订单的多次更新:
INSERT INTO orders VALUES
  (1, 100, 'pending', '2026-01-01 10:00:00'),
  (1, 100, 'paid', '2026-01-02 10:00:00'),
  (1, 100, 'shipped', '2026-01-03 10:00:00');

-- 后台 Merge 后，每个 order_id 只保留 updated_at 最大的行
-- 但 Merge 可能未完成，查询时指定 FINAL 强制合并:
SELECT * FROM orders FINAL WHERE order_id = 1;
-- 返回: (1, 100, 'shipped', '2026-01-03 10:00:00')

-- 缺点: FINAL 扫描整个表，性能差
-- 建议: 在 WHERE 中加入分区键限制范围
SELECT * FROM orders FINAL 
WHERE order_id = 1 AND updated_at >= '2026-01-01';
```

---

## 4. 写入机制

### 4.1 写入流程

```
1. Client 发送 INSERT 请求
2. Server 分配到对应分片
3. 数据写入内存中的 MergeTree 块（每 100K 行或 10MB flush）
4. Flush 到磁盘，生成临时 Part（_tmp_x_x_x）
5. 后台 Merge 线程将临时 Part 合并到正式 Part
6. 返回写入成功

写入优化:
  - 批量写入: 每次 INSERT 10K-1M 行
  - 避免小批量写入: 每次 INSERT < 1000 行会产生大量小 Part
  - INSERT 间隔 > 10 分钟: 后台 Merge 来不及合并
  
  强制合并:
  OPTIMIZE TABLE orders FINAL;  -- 合并所有 Part
  -- 生产环境慎用，锁表
```

### 4.2 异步写入

```sql
-- 异步写入（提升吞吐，可能丢数据）
INSERT INTO orders SELECT * FROM source ASYNC;

-- 设置写入参数
SET async_insert = 1;           -- 开启异步写入
SET async_insert_delay_timeout = 3000;  -- 等待 3s 攒批
SET async_insert_max_data_size = 1000000;  -- 攒到 1M 行
```

---

## 5. 查询优化

### 5.1 查询执行流程

```
1. 解析 SQL → 生成 AST
2. 查询优化:
   - WHERE 下推: 过滤条件尽量下推到存储层
   - 分区裁剪: 只扫描涉及的分区
   - 索引跳跃: 利用稀疏索引快速定位
3. 数据读取:
   - 读取需要的列（列存优势）
   - 并行读取多个 Part
4. 数据处理:
   - 聚合（GROUP BY）
   - 排序（ORDER BY）
   - 过滤（WHERE/HAVING）
5. 结果返回
```

### 5.2 查询优化策略

```
1. 分区裁剪:
   -- 必须包含分区键，否则全表扫描
   SELECT * FROM orders WHERE dt = '2026-01-01';  ✅
   SELECT * FROM orders WHERE user_id = 123;      ❌ 全表扫描

2. 稀疏索引利用:
   -- PRIMARY KEY 前缀匹配
   SELECT * FROM orders WHERE order_id = 123 AND dt = '2026-01-01';  ✅
   
3. 提前聚合:
   -- 先在数据源聚合，减少网络传输
   SELECT city, COUNT() FROM orders GROUP BY city;
   -- CH 分布式: 每个节点先聚合，再汇总

4. 使用合适的数据类型:
   -- UInt64 > String > DateTime
   -- 用 Enum/LowCardinality 减少存储

5. 投影（Projection，CH 22.8+）:
   CREATE PROJECTION orders_proj (
     SELECT city, COUNT() AS cnt GROUP BY city
   )
   ALTER TABLE orders MATERIALIZE PROJECTION orders_proj;
   -- 自动在查询中利用投影
```

### 5.3 聚合优化

```sql
-- 分布式聚合: 每个分片先聚合，再汇总
SELECT city, sum(spend) FROM distributed_orders GROUP BY city;
-- 执行计划:
-- 1. 各分片本地聚合: GROUP BY city, SUM(spend)
-- 2. Coordinator 汇总所有分片结果

-- 大数据量聚合优化:
-- 使用 aggregate_function_combinators
SELECT city, sumState(spend) FROM orders GROUP BY city;
-- 返回聚合状态，可合并

-- 多步聚合
SELECT city, sumMerge(sumState) FROM orders GROUP BY city;
```

---

## 6. 调优实战

### 6.1 表设计

```sql
-- 最佳实践:
-- 1. ORDER BY 选查询最常用的过滤列 + 高基数列
CREATE TABLE events (
    event_id UInt64,
    user_id UInt64,
    event_type String,
    ts DateTime,
    value UInt64
) ENGINE = MergeTree()
ORDER BY (ts, user_id)  -- ts 高选择性，user_id 作为二级排序
PARTITION BY toYYYYMM(ts);

-- 2. 分区键用按月/天
-- 3. 不用 FINAL，避免性能问题
-- 4. 用 ReplacingMergeTree 代替 FINAL

-- 避免:
-- - 低基数列放 ORDER BY 前面（如 status）
-- - 分区过多（每个分区产生一个 Part）
-- - 不用字符串做主键（用 UInt64/UUID）
```

### 6.2 写入调优

```sql
-- 批量写入:
INSERT INTO events VALUES (...);  -- 单次 10K+ 行

-- 异步写入:
SET async_insert = 1;
SET async_insert_max_data_size = 1000000;

-- 合并节奏:
-- background_pool_size: 后台 Merge 线程数（默认 16）
-- merge_tree_parts_to_delay_insert: 单表 Part 数 > 300 时暂停写入
-- merge_tree_parts_to_throw_insert: Part 数 > 600 时拒绝写入
```

### 6.3 查询调优

```sql
-- 使用 EXPLAIN 分析查询
EXPLAIN PIPELINE SELECT city, sum(spend) FROM orders GROUP BY city;

-- 调整并行度:
SET max_threads = 16;           -- 并行线程数
SET max_block_size = 1048576;   -- 单块行数

-- 避免:
-- - SELECT * 读所有列（列存但仍有 IO 开销）
-- - 无分区键的查询（全表扫描）
-- - GROUP BY 后 ORDER BY 大结果集（内存溢出）
```

### 6.4 集群调优

```sql
-- ZooKeeper 配置:
-- zookeeper.servers 指向 ZK 集群
-- 副本数: 2-3（根据数据重要性）

-- 分布式表:
CREATE TABLE distributed_orders AS orders
ENGINE = Distributed(cluster, default, orders, rand());

-- 写入: INSERT 到 Distributed 表，自动路由到分片
-- 读取: SELECT 从 Distributed 表，聚合各分片结果

-- 监控:
SELECT * FROM system.merges;     -- Merge 状态
SELECT * FROM system.parts;       -- Part 状态
SELECT * FROM system.profiles;    -- 配置
SELECT * FROM system.metrics;     -- 指标
```

---

## 7. 与 ClickHouse 对比

```
ClickHouse vs ClickHouse:
  
ClickHouse 优势:
  1. 列存 + 压缩 → 高压缩比，低 IO
  2. 向量化执行 → CPU 利用率高
  3. 分布式原生 → 水平扩展
  4. 实时写入 + 查询 → OLAP + OLTP 混合

ClickHouse 劣势:
  1. 不适合点查询（单行更新/删除）
  2. 事务支持弱（无 ACID）
  3. 数据模型简单（无 JOIN 优化）

适用场景:
  - 日志分析（10B+ 行/天）
  - 广告 BI 报表
  - 实时监控
  - 用户行为分析
```

---

*本文档基于 ClickHouse 24.x 整理*
