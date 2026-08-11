# ClickHouse 深度解析

> 本文档深入解析 ClickHouse 的列式存储、MergeTree 引擎、向量化执行和分布式架构。
> 适用对象：数据分析工程师、DBA、大数据工程师

---

## 1. ClickHouse 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ClickHouse 架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ClickHouse Server                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  Query      │  │  Mutation   │  │  Replication│         │   │
│  │  │  Handler    │  │  Handler    │  │  Handler    │         │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │   │
│  │         └─────────────────┼─────────────────┘                │   │
│  │                          │                                   │   │
│  │                   ┌──────▼──────┐                           │   │
│  │                   │  Storage    │                           │   │
│  │                   │  Layer      │                           │   │
│  │                   └──────┬──────┘                           │   │
│  │                          │                                   │   │
│  │         ┌────────────────┼────────────────┐                 │   │
│  │         │                │                │                 │   │
│  │  ┌──────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐          │   │
│  │  │  Column     │  │  Part     │  │  Merge      │          │   │
│  │  │  Stores     │  │  Manager  │  │  Scheduler  │          │   │
│  │  └─────────────┘  └───────────┘  └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                      │
│         │                 │                 │                       │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                 │
│  │  Replica 1  │  │  Replica 2  │  │  Replica N  │                 │
│  │  (ZK 协调)  │  │  (ZK 协调)  │  │  (ZK 协调)  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键特性

| 特性 | 说明 |
|------|------|
| **列式存储** | 按列存储，IO 效率高 |
| **向量化执行** | SIMD 指令优化 |
| **数据压缩** | LZ4/ZSTD，压缩比 3-10x |
| **主键稀疏索引** | 跳过无关数据 |
| **物化视图** | 预计算，加速查询 |
| **分布式查询** | 跨节点并行执行 |

---

## 2. MergeTree 引擎

### 2.1 表结构设计

```sql
CREATE TABLE orders (
    order_id UInt64,
    user_id UInt64,
    amount Decimal(12,2),
    created_at DateTime,
    INDEX idx_amount amount TYPE minmax GRANULARITY 8192
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (user_id, order_id)
SETTINGS index_granularity = 8192;
```

### 2.2 数据部分结构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Part 结构                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  primary_key │  │  skip_index  │  │   columns    │            │
│  │   .mrk       │  │   .mrk       │  │   .bin/.cz   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  checksums   │  │   count      │  │  partition   │            │
│  │   .txt       │  │   .txt       │  │   .txt       │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  mark 文件 (.mrk):                                                  │
│  - 每 8192 行一个 mark                                              │
│  - 记录该行的偏移量 (offset)                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 合并策略

```go
type MergeScheduler struct {
    merges      chan MergeTask
    maxBytesToMerge  int64  // 最大合并字节数
    minBytesForWideMerge int64  // 宽合并阈值
}

type MergeTask struct {
    table      string
    parts      []string
    destination string
}

// 合并触发条件
func (s *MergeScheduler) ShouldMerge(part Part) bool {
    // 1. 活跃部分数量超过阈值
    if part.activeParts >= 100 {
        return true
    }
    
    // 2. 部分大小超过阈值
    if part.size > s.maxBytesToMerge {
        return true
    }
    
    // 3. 达到后台合并时间窗口
    if time.Since(part.lastMerge) > 5*time.Minute {
        return true
    }
    
    return false
}
```

---

## 3. 向量化执行引擎

### 3.1 Block 处理

```go
type Block struct {
    columns []*Column  // 列数据
    rows    int        // 行数
}

type Column struct {
    data     []byte    // 原始数据
    compression Compression  // 压缩方式
}

// 向量化执行
func (q *QueryExecutor) Execute(block *Block) *Block {
    // 1. 函数向量化
    result := applyVectorizedFunc(block, q.funcs)
    
    // 2. 列式过滤
    result = applyVectorizedFilter(result, q.filters)
    
    // 3. 聚合向量化
    if q.isAggregate {
        result = applyVectorizedAggregate(result, q.aggs)
    }
    
    return result
}
```

### 3.2 SIMD 优化

```go
// SIMD 向量加法
func vectorAddSIMD(a, b []float64) []float64 {
    result := make([]float64, len(a))
    
    // 使用 AVX2/AVX512 指令集
    // 每次处理 4 个 double (32 bytes)
    for i := 0; i < len(a); i += 4 {
        // 伪代码：SIMD 指令
        // __m256d va = _mm256_load_pd(&a[i])
        // __m256d vb = _mm256_load_pd(&b[i])
        // __m256d vr = _mm256_add_pd(va, vb)
        // _mm256_store_pd(&result[i], vr)
    }
    
    return result
}
```

---

## 4. 查询优化

### 4.1 主键索引

```sql
-- 主键稀疏索引
ORDER BY (user_id, order_id)
INDEX idx_amount amount TYPE minmax GRANULARITY 8192

-- 查询优化
SELECT * FROM orders 
WHERE user_id = 12345 
AND amount > 100;
-- 利用主键跳过无关数据
-- 利用 skip index 跳过列无关数据
```

### 4.2 物化视图

```sql
-- 创建物化视图
CREATE MATERIALIZED VIEW orders_mv
ENGINE = SummingMergeTree()
ORDER BY (user_id, toDate(created_at))
AS SELECT 
    user_id,
    toDate(created_at) as date,
    sum(amount) as total_amount
FROM orders
GROUP BY user_id, date;

-- 查询自动路由
SELECT * FROM orders_mv
WHERE date >= '2024-01-01';
```

### 4.3 分区裁剪

```sql
-- 分区键
PARTITION BY toYYYYMM(created_at)

-- 查询时自动裁剪分区
SELECT count() FROM orders
WHERE created_at >= '2024-01-01'
AND created_at < '2024-02-01';
-- 只扫描 2024-01 分区
```

---

## 5. 分布式架构

### 5.1 分片策略

```sql
-- 分布式表
CREATE TABLE orders_distributed ON CLUSTER my_cluster (
    order_id UInt64,
    user_id UInt64,
    amount Decimal(12,2),
    created_at DateTime
) ENGINE = Distributed(my_cluster, default, orders, rand());

-- 分片键
-- rand(): 随机分片
-- hashCode(order_id): 哈希分片
-- toInt64(order_id): 范围分片
```

### 5.2 查询执行

```
┌─────────────────────────────────────────────────────────────────────┐
│                    分布式查询执行                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                    ┌──────────────┐                                │
│                    │  Local Node  │                                │
│                    └──────┬───────┘                                │
│                           │                                        │
│         ┌─────────────────┼─────────────────┐                     │
│         │                 │                 │                       │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                │
│  │  Shard 1    │  │  Shard 2    │  │  Shard 3    │                │
│  │  (本地执行)  │  │  (本地执行)  │  │  (本地执行)  │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼──────┐                                 │
│                    │  Merge 结果  │                                 │
│                    └─────────────┘                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. 性能优化

### 6.1 写入优化

```sql
-- 批量写入
INSERT INTO orders VALUES (...), (...), (...);  -- 每次 > 1000 行

-- 设置合并参数
ALTER TABLE orders SETTINGS 
    max_bytes_to_merge = 10GB,
    number_of_free_entries_to_merge = 16;

-- 禁用后台合并（写入高峰期）
SET mutations_sync = 0;
```

### 6.2 查询优化

```sql
-- 使用最适合的引擎
ENGINE = AggregatingMergeTree()  -- 聚合查询
ENGINE = SummingMergeTree()       -- 求和查询
ENGINE = CollapsingMergeTree()    -- 状态变更

-- 预聚合
CREATE MATERIALIZED VIEW ...
ENGINE = SummingMergeTree()
ORDER BY ...

-- 限制扫描量
SELECT ... LIMIT 10000;
```

### 6.3 配置优化

```xml
<!-- config.xml -->
<clickhouse>
    <max_threads>16</max_threads>
    <max_block_size>65536</max_block_size>
    <max_download_threads>4</max_download_threads>
    <background_pool_size>16</background_pool_size>
    <merge_tree>
        <max_suspicious_broken_parts>5</max_suspicious_broken_parts>
        <parts_to_throw_insert>100</parts_to_throw_insert>
    </merge_tree>
</clickhouse>
```

---

## 7. 常见问题

### 7.1 数据跳过索引

```sql
-- 创建数据跳过索引
ALTER TABLE orders 
ADD INDEX idx_amount amount TYPE granular_bloom_filter(1024) GRANULARITY 16;

-- 使用索引
SELECT * FROM orders WHERE amount > 1000;
```

### 7.2 稀疏索引设计

```
主键: (user_id, order_id)
granularity: 8192

查询: WHERE user_id = 123
     ┌─────────────────────────────────┐
     │ Part 1 │ Part 2 │ Part 3 │... │
     │ min=1  │ min=5  │ min=10 │... │
     │ max=4  │ max=9  │ max=15 │... │
     └─────────────────────────────────┘
           ↑
     跳过 Part 1, 只扫描 Part 2
```

---

## 8. 总结

### 8.1 核心原理回顾

| 特性 | 作用 | 优化点 |
|------|------|--------|
| 列式存储 | IO 效率 | 合理选择压缩算法 |
| MergeTree | 持久化 | 控制合并频率 |
| 稀疏索引 | 数据跳过 | 选择合适的 granularity |
| 物化视图 | 预计算 | 选择合适的聚合引擎 |
| 向量化执行 | 查询加速 | 合理设置 max_block_size |

### 8.2 性能优化 Checklist

- [ ] 使用合适的 MergeTree 变体
- [ ] 设置合理的 max_block_size
- [ ] 使用物化视图预聚合
- [ ] 合理设置分区键
- [ ] 使用数据跳过索引
- [ ] 批量写入（>1000行/次）
- [ ] 监控 merge 状态

---

*最后更新：2026-08-11*
*作者：Ryan*
