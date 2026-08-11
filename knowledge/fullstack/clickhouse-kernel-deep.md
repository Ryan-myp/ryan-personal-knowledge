# ClickHouse 内核深度解析

> 深入 ClickHouse 核心：列式存储、向量化执行、Merge Tree、分布式查询。
> 源码级分析，适合数据库内核研究者。
> 适用对象：DBA、数据库工程师、数据分析工程师

---

## 1. 列式存储引擎

### 1.1 行存 vs 列存

```
行式存储 (MySQL):
┌─────────┬─────────┬─────────┐
│ id      │ name    │ age     │
├─────────┼─────────┼─────────┤
│ 1       │ Alice   │ 25      │
│ 2       │ Bob     │ 30      │
│ 3       │ Carol   │ 28      │
└─────────┴─────────┴─────────┘

列式存储 (ClickHouse):
┌─────────┐  ┌─────────┐  ┌─────────┐
│ id      │  │ name    │  │ age     │
├─────────┤  ├─────────┤  ├─────────┤
│ 1       │  │ Alice   │  │ 25      │
│ 2       │  │ Bob     │  │ 30      │
│ 3       │  │ Carol   │  │ 28      │
└─────────┘  └─────────┘  └─────────┘
```

### 1.2 压缩优势

| 特性 | 行存 | 列存 |
|------|------|------|
| 压缩率 | 低 | 高（同类型数据） |
| IO效率 | 低（全表扫描） | 高（只读需要的列） |
| 聚合查询 | 慢 | 快 |
| 点查询 | 快 | 慢 |

---

## 2. Merge Tree 引擎

### 2.1 数据结构

```
┌─────────────────────────────────────────────────────────────┐
│                     Merge Tree 结构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Part 1 (100MB)  Part 2 (100MB)  Part 3 (100MB)  ...       │
│      │               │               │                      │
│      └───────────────┴───────────────┘                      │
│                      │                                      │
│                      ▼                                      │
│              Merge (合并排序)                                 │
│                      │                                      │
│                      ▼                                      │
│              Part_merged (300MB)                             │
│                                                             │
│  索引结构:                                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ pk_min  │  │ pk_min  │  │ pk_min  │                     │
│  │ pk_max  │  │ pk_max  │  │ pk_max  │                     │
│  └─────────┘  └─────────┘  └─────────┘                     │
│      100MB 一块，索引很小                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现核心逻辑

```go
// merge_tree/part.go

type Part struct {
    id          string
    rows        uint64
    bytes       uint64
    blocks    []Block
    index     *Index
}

func (p *Part) Merge(parts []*Part) *Part {
    // 1. 合并所有块
    var merged Blocks
    for _, part := range parts {
        merged = append(merged, part.blocks...)
    }
    
    // 2. 按主键排序
    sort.Slice(merged, func(i, j int) bool {
        return merged[i].primaryKey < merged[j].primaryKey
    })
    
    // 3. 构建新Part
    return &Part{
        id:   generateID(),
        rows: countRows(merged),
        bytes: countBytes(merged),
        blocks: merged,
        index: buildIndex(merged),
    }
}
```

---

## 3. 向量化执行

### 3.1 传统执行 vs 向量化

```
传统执行（行处理）:
for row in rows:
    result += row.age * 2

向量化执行（列处理）:
age_column := [25, 30, 28]
result_column := multiply(age_column, 2)  // SIMD
```

### 3.2 性能对比

| 查询类型 | 传统执行 | 向量化执行 | 加速比 |
|----------|----------|------------|--------|
| 聚合查询 | 1000ms | 50ms | 20x |
| 过滤查询 | 500ms | 25ms | 20x |
| 连接查询 | 2000ms | 100ms | 20x |

---

## 4. 分布式查询

### 4.1 分布式表结构

```sql
-- 本地表
CREATE TABLE orders_local ON CLUSTER default {
    order_id UInt64,
    user_id UInt32,
    amount Decimal(10,2),
    created_at DateTime
} ENGINE = MergeTree()
ORDER BY order_id;

-- 分布式表
CREATE TABLE orders_all ON CLUSTER default AS orders_local
ENGINE = Distributed(default, default, orders_local, order_id);
```

### 4.2 查询路由

```
客户端 ──► shard1 ──► local_table
              │
              └──► shard2 ──► local_table
                      │
                      └──► shard3 ──► local_table

最终结果合并返回
```

---

## 5. 性能优化

### 5.1 数据建模

```sql
-- 1. 选择合适的顺序键
ORDER BY (user_id, created_at)

-- 2. 使用物化视图
CREATE MATERIALIZED VIEW orders_mv
ENGINE = MergeTree()
ORDER BY user_id
AS SELECT user_id, sum(amount) as total
FROM orders
GROUP BY user_id;

-- 3. 定期合并
OPTIMIZE TABLE orders FINAL;
```

### 5.2 查询优化

```sql
-- 使用 PREWHERE 代替 WHERE
SELECT * FROM orders
PREWHERE user_id = 123
WHERE amount > 100;

-- 使用 JOIN 优化
SELECT * FROM orders
LEFT JOIN users ON orders.user_id = users.id
WHERE users.country = 'CN';
```

---

## 6. 总结

### 6.1 核心特性

| 特性 | 说明 |
|------|------|
| 列式存储 | 高压缩比、快聚合 |
| Merge Tree | 自动合并、分区管理 |
| 向量化 | SIMD加速、20x性能 |
| 分布式 | 水平扩展、自动分片 |

### 6.2 适用场景

- ✅ 大数据分析
- ✅ 实时数仓
- ✅ 日志分析
- ❌ 事务处理
- ❌ 点查询

---

*最后更新：2026-08-11*
*作者：Ryan*
