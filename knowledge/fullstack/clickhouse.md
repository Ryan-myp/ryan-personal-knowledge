# ClickHouse 原理 — MergeTree 引擎源码级、列式存储、OLAP 调优

> 标签: `#ClickHouse` `#MergeTree` `#列式存储` `#OLAP` `#调优`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. MergeTree 引擎 — 核心架构

### 1.1 MergeTree 结构

```c
// MergeTree 表结构:
┌─────────────────────────────────────────────────────┐
│                    MergeTree Table                    │
├─────────────────────────────────────────────────────┤
│  Part 1: data.bin, data.mrk2, index...              │
│  Part 2: data.bin, data.mrk2, index...              │
│  Part 3: data.bin, data.mrk2, index...              │
│  Part 4: data.bin, data.mrk2, index...              │
├─────────────────────────────────────────────────────┤
│  merge_tree → merge_parts() → Part 5: merged        │
└─────────────────────────────────────────────────────┘

// MergeTree 数据目录:
// parts/
│   ├── all_1_1_0/          // 0: 表示所有分区
│   │   ├── data.bin        // 压缩后的数据
│   │   ├── data.mrk2       // 数据标记（用于定位）
│   │   ├── index.bin       // 主键索引
│   │   ├── count.txt       // 行数
│   │   └── checksums.txt   // 文件校验和
│   ├── all_2_2_0/
│   │   ├── data.bin
│   │   └── ...
│   └── ...
├─────────────────────────────────────────────────────┤
│  columns.bin.gz           // 列数据（压缩）
│  primary_key.mrk2         // 主键标记
│  primary_key.idx          // 主键索引
└─────────────────────────────────────────────────────┘

// Part 命名规则:
// {partition_id}_{min_block}_{max_block}_{level}
// all_1_1_0: partition=all, min_block=1, max_block=1, level=0
// all_2_2_0: partition=all, min_block=2, max_block=2, level=0
// 合并后 level 增加
```

### 1.2 列存储格式

```c
// ClickHouse 的列存储方式:
// 每列独立存储，按压缩块（compression codec）压缩

// 列文件格式（data.bin）:
// ┌─────────────────────────────────────────────────────────┐
│ Block Header (compressed)                                  │
│   - columns_count: uint32                                  │
│   - rows_count: uint32                                     │
│   - column_names: string[]                                 │
│   - column_types: string[]                                 │
├─────────────────────────────────────────────────────────┤
│ Column Data (每列独立压缩)                                  │
│   Column 1:                                                │
│     - compression_header: uint32 (codec)                   │
│     - compressed_data: bytes                               │
│   Column 2:                                                │
│     - compression_header: uint32 (codec)                   │
│     - compressed_data: bytes                               │
│   ...                                                      │
│ Column N:                                                  │
│     - compression_header: uint32 (codec)                   │
│     - compressed_data: bytes                               │
├─────────────────────────────────────────────────────────┤
│ Index Data                                                  │
│   - primary_key_mrk: uint64[]                              │
│   - granularity: uint32                                    │
│   - index_type: string (minmax, set, ngram, ...)          │
└─────────────────────────────────────────────────────────┘

// 压缩编解码器（Codec）:
// 1. Delta + DoubleDelta: 差分压缩 + 二阶差分（适合时间序列）
// 2. LZ4: 快速压缩/解压，压缩率低
// 3. ZSTD: 高压缩率，压缩/解压较慢
// 4. Gorilla: 适合浮点数（金融/时序数据）
// 5. Delta + LZ4: 差分 + LZ4
// 6. Delta + ZSTD: 差分 + ZSTD

// 列数据组织（Column 实现）:
// 1. ColumnVector: 固定大小类型（UInt64, Int32, Float64）
//    - 按列存储: [v1, v2, v3, v4, v5, ...]
// 2. ColumnFixedString: 固定长度字符串
// 3. ColumnString: 可变长度字符串（data.bin + offsets.bin）
//    - data.bin: 字符串内容
//    - offsets.bin: 字符串偏移量
// 4. ColumnArray: 数组类型
//    - data.bin: 数组元素
//    - offsets.bin: 数组偏移量
// 5. ColumnMap: Map 类型
// 6. ColumnTuple: 元组类型
// 7. ColumnNullable: 可空类型
```

### 1.3 稀疏索引（Primary Key + Mark）

```c
// ClickHouse 的稀疏索引设计:
// 每个 Part 的粒度（granularity）= 8192 行
// 即每 8192 行创建一个索引条目

// 主键索引结构:
// 主键可以是多列的，按字典序排序
// 索引条目: (min, max) 对，表示该粒度范围内主键的最小值和最大值

// 示例:
// 假设主键是 (user_id, event_date, event_type)
// 数据按主键排序:
// user_id | event_date | event_type | value
// 1       | 2024-01-01 | click      | 10
// 1       | 2024-01-01 | view       | 20
// 1       | 2024-01-02 | click      | 30
// 1       | 2024-01-02 | view       | 40
// ... (8192 行)
// 2       | 2024-01-01 | click      | 50
// ...

// 索引条目（每 8192 行）:
// Entry 0: (1, 2024-01-01, click) ~ (1, 2024-03-01, view)   // 标记 0
// Entry 1: (1, 2024-03-02, click) ~ (2, 2024-01-01, view)   // 标记 1
// Entry 2: (2, 2024-01-02, click) ~ (2, 2024-02-01, view)   // 标记 2
// ...

// 查询优化:
// WHERE user_id = 1 AND event_date = '2024-01-01'
// 1. 在索引中二分查找满足条件的第一条条目
// 2. 跳过不匹配的条目（跳过整个 granule）
// 3. 从匹配的 granule 开始扫描数据
// 4. 遇到不匹配的 granule 后停止

// 标记文件（.mrk2）:
// 标记文件记录了每个 granule 在 data.bin 中的偏移量
// 格式: binary file, 每个标记 6 bytes (mark number + offset)
```

---

## 2. Merge 机制 — 后台合并

### 2.1 Merge 流程

```c
// MergeTree 的合并流程（mutation + merge）:
// 1. 写入: INSERT → 创建 Part（level=0）
// 2. 后台线程: merge_tree → scheduleMerge()
// 3. 合并条件:
//    - 同一 Part 的多个小 Part 合并
//    - 合并比例: level × 3 + 1（level=0: 需要 1 个, level=1: 需要 4 个）
// 4. 合并结果: 生成新的 Part（level+1）

// 合并过程:
// 1. 选择待合并的 Parts（MergeTreeBackgroundExecutor）
// 2. 对 Parts 按主键排序（如果尚未排序）
// 3. 逐列读取并合并（列式合并）
// 4. 写入新的 Part 文件
// 5. 原子替换旧 Part

// MergeTree 后台线程:
// 1. MergeTreeBackgroundExecutor: 调度合并任务
// 2. MergeTreeData::merger: 执行合并
// 3. MutationInterpreter: 执行 ALTER 操作
// 4. GCThread: 清理过期 Parts

// 合并配置:
// merge_tree.max_bytes_to_merge_at_max_space_in_pool: 最大合并大小
// merge_tree.num_threads_for_merge: 合并线程数
// merge_tree.min_bytes_for_wide_part: 宽 Part 的最小大小
// merge_tree.min_rows_for_wide_part: 宽 Part 的最小行数
```

### 2.2 写入与事务

```c
// ClickHouse 的写入模型:
// 1. INSERT → 临时 Part（pending）
// 2. 后台 merge 合并 Part
// 3. 合并完成后，旧 Part 被删除

// 事务支持（从 22.8 开始）:
// 1. 支持 ACID 事务
// 2. 使用 MVCC 实现
// 3. 写入时创建新版本
// 4. 查询时读取特定版本
// 5. 事务回滚: 删除新版本，回退到旧版本

// 异步插入:
// 1. INSERT → 放入 buffer
// 2. 每 100ms 或 10000 条 → 触发合并
// 3. 异步合并 → 不阻塞主线程

// 最终一致性:
// 1. 写入后可能不立即可见（等待 merge）
// 2. 配置 wait_for_async_insert=1 确保立即可见
```

---

## 3. 分布式架构

### 3.1 Distributed 引擎

```c
// Distributed 表:
// 数据分散在多个 Shard 上，Distributed 表是一个"视图"

// 结构:
┌─────────────────────────────────────────────────────┐
│                    Query Router                       │
│  Distributed Table → Route to Shard(s)               │
├─────────────────────────────────────────────────────┤
│  Shard 1                          Shard 2            │
│  ┌──────────┐                    ┌──────────┐       │
│  │ Local 1  │                    │ Local 2  │       │
│  │ Local 2  │                    │ Local 3  │       │
│  └──────────┘                    └──────────┘       │
└─────────────────────────────────────────────────────┘

// Distributed 引擎:
CREATE TABLE distributed_table AS local_table
ENGINE = Distributed(cluster_name, database, table, sharding_key)

// 分片键:
// 1. rand(): 随机分片
// 2. cityHash64(user_id): 按用户哈希分片
// 3. toInt64Hash(toUInt64(user_id)): 高性能哈希

// 查询路由:
// 1. SELECT * FROM distributed_table → 查询所有 Shard
// 2. SELECT * FROM distributed_table WHERE user_id = 1 → 只路由到 user_id 所在的 Shard
// 3. 本地查询: SELECT * FROM local_table → 只查询本地 Shard
```

### 3.2 ReplicatedMergeTree

```c
// ReplicatedMergeTree:
// 使用 ZooKeeper 实现分布式协调

// 结构:
┌─────────────────────────────────────────────────────┐
│                    ZooKeeper                          │
│  /clickhouse/tables/01/users/                       │
│    ├── shards/01/data/...                            │
│    ├── replicas/replica1/                            │
│    │   ├── logs/log-0000000001                       │
│    │   ├── parts/                                    │
│    │   └── queue/                                    │
│    └── replicas/replica2/                            │
│        ├── logs/log-0000000002                       │
│        ├── parts/                                    │
│        └── queue/                                    │
└─────────────────────────────────────────────────────┘

// ZooKeeper 存储:
// 1. /clickhouse/tables/{shard}/{table}/replicas/replica/
//    - 存储副本信息
// 2. /clickhouse/tables/{shard}/{table}/logs/
//    - 存储操作日志（log entries）
// 3. /clickhouse/tables/{shard}/{table}/parts/
//    - 存储 Part 元数据
// 4. /clickhouse/tables/{shard}/{table}/queue/
//    - 存储合并任务队列

// 副本同步流程:
// 1. 写入 → 创建 Part → 写入 ZooKeeper
// 2. 其他副本从 ZooKeeper 获取 Part 信息
// 3. 其他副本从主副本拉取 Part 数据
// 4. 合并完成后，更新 ZooKeeper 状态

// 故障恢复:
// 1. 副本故障 → ZooKeeper 检测到心跳超时
// 2. 新副本启动 → 从 ZooKeeper 拉取最新 Part
// 3. 合并队列中的任务 → 在新副本上执行
```

---

## 4. 性能调优

### 4.1 索引优化

```sql
-- 选择合适的索引类型:
-- 1. Primary Key: 主键必须选择（用于稀疏索引）
-- 2. Sampling Key: 采样键（用于近似计算）

-- 索引类型:
-- 1. minmax: 最小值/最大值（默认）
-- 2. set: 集合索引（用于 IN 查询）
-- 3. ngram: n-gram 索引（用于模糊匹配）
-- 4. tokenbf: 倒排索引（用于全文搜索）
-- 5. bf: 布隆过滤器（用于精确匹配）

-- 示例:
ALTER TABLE users ADD INDEX idx_email email TYPE set(1000) GRANULARITY 4;
```

### 4.2 数据分布优化

```sql
-- 选择合适的分片键:
-- 1. 均匀分布: cityHash64(user_id)
-- 2. 热点分散: rand()
-- 3. 查询匹配: 按查询条件分片

-- 选择合适的粒度:
-- 1. 默认: 8192 行
-- 2. 大数据量: 增加粒度（减少索引大小）
-- 3. 小数据量: 减小粒度（提高查询精度）

-- 选择合适的压缩编解码器:
-- 1. Delta + DoubleDelta: 时间序列
-- 2. LZ4: 快速压缩/解压
-- 3. ZSTD: 高压缩率
```

---

*本文档基于 ClickHouse 23.x 源码整理，覆盖 MergeTree、列式存储、合并机制、分布式架构*
