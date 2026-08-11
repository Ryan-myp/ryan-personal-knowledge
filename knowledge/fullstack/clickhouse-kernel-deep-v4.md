# ClickHouse 内核深度解析

> 深入 ClickHouse 核心：存储引擎、查询执行、数据压缩、分布式架构。
> 源码级分析，包含性能优化和故障排查。
> 适用对象：数据工程师、DBA、后端工程师

---

## 1. MergeTree 引擎

### 1.1 数据结构

```
┌─────────────────────────────────────────────────────────────┐
│                  MergeTree 数据结构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Part (数据片段)                                             │
│  ├── 0000001_1_1_0/                                         │
│  │   ├── counters.txt                                      │
│  │   ├── primary.idx                                       │
│  │   ├── Skips.txt                                         │
│  │   ├── columns.txt                                       │
│  │   └── *.bin (数据文件)                                   │
│  │       ├── timestamp.bin                                 │
│  │       ├── event_type.bin                                │
│  │       └── user_id.bin                                   │
│  │                                                          │
│  └── 各列独立存储                                             │
│                                                             │
│  列存储特点：                                                  │
│  ├── 同类型数据连续存储                                       │
│  ├── 高效压缩                                                 │
│  └── 向量化执行                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据写入流程

```
写入流程：

1. 接收写入请求
   └── 写入到临时 part

2. 内存中排序
   └── 使用 QuickSort/BlockSort

3. 写入磁盘
   └── 按列存储，每列独立文件

4. 定期合并
   └── BackgroundMergeScheduler 异步合并
```

---

## 2. 查询执行

### 2.1 查询管道

```
查询执行管道 (Query Pipeline):

┌─────────────────────────────────────────────────────────────┐
│                    查询执行流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 解析阶段                                                  │
│     ├── SQL 解析                                              │
│     └── AST 构建                                             │
│                                                             │
│  2. 优化阶段                                                  │
│     ├── 谓词下推                                             │
│     ├── 列裁剪                                              │
│     └── 分区裁剪                                             │
│                                                             │
│  3. 执行阶段                                                  │
│     ├── 读取数据 (DataPartsReader)                           │
│     ├── 过滤 (FilterBlockInputStream)                       │
│     ├── 聚合 (AggregateBlockInputStream)                     │
│     └── 排序 (SortingBlockInputStream)                       │
│                                                             │
│  4. 结果返回                                                  │
│     └── 流式返回                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 向量化执行

```cpp
// 简化版向量化执行
class VectorizedBlockInputStream {
public:
    Block read() {
        // 一次读取一整列
        for (auto &column : columns_) {
            column->readBatch(size_);
        }
        return block_;
    }
    
private:
    std::vector<IColumn *> columns_;
    size_t size_;
};
```

---

## 3. 数据压缩

### 3.1 压缩算法

```
ClickHouse 压缩算法：

1. 无压缩 (NO)
   └── 原始数据

2. LZ4
   ├── 快速压缩/解压
   ├── CPU 友好
   └── 默认算法

3. ZSTD
   ├── 高压缩比
   ├── 适合长期存储
   └── 可配置级别

4. Delta + ZSTD
   ├── 先差值编码
   └── 再压缩，效果更好
```

### 3.2 压缩效果

```
压缩效果对比：

数据量      原始大小    LZ4压缩    ZSTD压缩
─────────────────────────────────────────
1亿行       100 GB     25 GB      15 GB
```

---

## 4. 分布式架构

### 4.1 分布式表

```sql
-- 本地表
CREATE TABLE orders_local ON CLUSTER default {
    order_id UInt64,
    user_id UInt32,
    amount Decimal(10,2),
    created_at DateTime
} ENGINE = MergeTree()
ORDER BY (order_id);

-- 分布式表
CREATE TABLE orders_distributed ON CLUSTER default AS orders_local
ENGINE = Distributed(default, default, orders_local, order_id);
```

### 4.2 查询路由

```
分布式查询流程：

1. 客户端请求 → 分布式表
2. 解析分片键 → 确定目标分片
3. 并行执行查询
4. 合并结果返回

┌─────────────────────────────────────────────────────────────┐
│                    分布式查询                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Client → Distributed Table                                  │
│           │                                                   │
│           ├──► Shard 1 (本地查询)                             │
│           ├──► Shard 2 (本地查询)                             │
│           └──► Shard 3 (本地查询)                             │
│                       │                                       │
│                       └──► Merge Result                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 性能优化

### 5.1 表设计

```sql
-- 1. 选择合适的分区键
PARTITION BY toYYYYMM(created_at)

-- 2. 合理的排序键
ORDER BY (user_id, created_at)

-- 3. 采样表达式
SAMPLE BY user_id

-- 4. 数据TTL
TTL created_at + INTERVAL 90 DAY DELETE
```

### 5.2 查询优化

```sql
-- 1. 使用 PREWHERE 代替 WHERE
SELECT * FROM orders PREWHERE user_id = 100 WHERE amount > 100;

-- 2. 使用 IN 代替 JOIN
SELECT * FROM orders WHERE user_id IN (SELECT id FROM users);

-- 3. 使用最终一致性
SET allow_experimental_lightweight_delete = 1;
```

---

## 6. 监控告警

### 6.1 关键指标

```
监控指标：
- 查询延迟分布
- 内存使用率
- 磁盘使用率
- 插入速率
- 合并频率
```

### 6.2 监控查询

```sql
-- 查询当前运行查询
SELECT 
    query_id,
    query,
    elapsed,
    read_rows,
    written_rows
FROM system.processes;

-- 查询慢查询
SELECT 
    query_duration_ms,
    query
FROM system.query_log
WHERE type = 'QueryFinish'
AND query_duration_ms > 1000
ORDER BY query_duration_ms DESC;
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 存储 | MergeTree + 列存储 |
| 查询 | 管道 + 向量化 |
| 压缩 | LZ4/ZSTD + Delta |
| 分布式 | 分片 + 并行 |

### 7.2 最佳实践

- [ ] 合理分区键设计
- [ ] 选择合适的排序键
- [ ] 使用 PREWHERE 优化
- [ ] 监控合并延迟
- [ ] 定期清理过期数据

---

*最后更新：2026-08-11*
*作者：Ryan*
