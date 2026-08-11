# ClickHouse 查询优化深度解析

> 深入 ClickHouse 查询优化：分区裁剪、谓词下推、物化视图、并行查询。
> 源码级分析，包含生产环境优化案例。
> 适用对象：数据工程师、DBA、后端工程师

---

## 1. 查询执行模型

### 1.1 查询流程

```
┌─────────────────────────────────────────────────────────────┐
│                  ClickHouse 查询流程                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 查询解析 (Parser)                                       │
│     ├── 解析 SQL 语句                                       │
│     └── 生成 AST                                            │
│                                                             │
│  2. 查询优化 (Optimizer)                                    │
│     ├── 谓词下推                                           │
│     ├── 常量折叠                                           │
│     ├── 子查询优化                                          │
│     └── 分区裁剪                                           │
│                                                             │
│  3. 查询执行 (Executor)                                     │
│     ├── 读取数据                                           │
│     ├── 过滤数据                                           │
│     ├── 聚合计算                                           │
│     └── 返回结果                                           │
│                                                             │
│  4. 结果序列化 (Serializer)                                 │
│     └── 将结果格式化为响应                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 分区裁剪

```sql
-- 假设表按日期分区
CREATE TABLE orders (
    order_id UInt64,
    order_date Date,
    amount Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(order_date)
ORDER BY (order_date, order_id);

-- ✅ 分区裁剪：只扫描指定分区
SELECT * FROM orders 
WHERE order_date >= '2024-01-01' 
  AND order_date < '2024-02-01';

-- ❌ 无分区裁剪：扫描所有分区
SELECT * FROM orders 
WHERE toDate(order_date) >= '2024-01-01';
```

---

## 2. 谓词下推

### 2.1 谓词下推原理

```
传统数据库：
┌─────────┐    ┌─────────┐    ┌─────────┐
│  SELECT │───►│  FILTER │───►│  TABLE  │
└─────────┘    └─────────┘    └─────────┘

ClickHouse 谓词下推：
┌─────────┐    ┌─────────┐    ┌─────────┐
│  SELECT │───►│  TABLE  │───►│  FILTER │
└─────────┘    └─────────┘    └─────────┘
                （先过滤，后选择）
```

### 2.2 Go 实现查询优化器

```go
// optimizer.go

package query

import "strings"

type Optimizer struct {
    rules []Rule
}

type Rule interface {
    Apply(plan *Plan) *Plan
}

// 谓词下推规则
type PredicatePushdownRule struct{}

func (r *PredicatePushdownRule) Apply(plan *Plan) *Plan {
    // 将 WHERE 条件推下到表扫描层
    for _, node := range plan.Nodes {
        if node.Type == "TableScan" {
            node.Filter = plan.Where
        }
    }
    return plan
}

// 分区裁剪规则
type PartitionPruningRule struct{}

func (r *PartitionPruningRule) Apply(plan *Plan) *Plan {
    // 根据分区键裁剪分区
    for _, node := range plan.Nodes {
        if node.Type == "TableScan" {
            node.Partitions = r.prunePartitions(node, plan.Where)
        }
    }
    return plan
}

func (r *PartitionPruningRule) prunePartitions(node *Node, where string) []string {
    // 解析 WHERE 条件中的分区键
    // 返回需要扫描的分区列表
    return []string{"2024-01", "2024-02"}
}
```

---

## 3. 物化视图

### 3.1 物化视图原理

```
物化视图 = 预计算 + 持久化存储

优势：
- 加速聚合查询
- 减少重复计算
- 自动更新（INSERT 时）

适用场景：
- 固定维度的聚合查询
- 高频查询的预计算
- 报表生成
```

### 3.2 ClickHouse 物化视图

```sql
-- 创建物化视图
CREATE MATERIALIZED VIEW orders_summary_mv
ENGINE = SummingMergeTree()
ORDER BY (date, product_id)
AS SELECT
    toDate(order_date) AS date,
    product_id,
    sum(amount) AS total_amount,
    count() AS order_count
FROM orders
GROUP BY date, product_id;

-- 查询物化视图
SELECT date, product_id, total_amount
FROM orders_summary_mv
WHERE date >= '2024-01-01';
```

### 3.3 Go 实现物化视图

```go
// materialized_view.go

package query

import (
    "sync"
    "time"
)

type MaterializedView struct {
    name      string
    source    string
    query     string
    data      sync.Map
    lastSync  time.Time
    interval  time.Duration
}

func NewMaterializedView(name, source, query string, interval time.Duration) *MaterializedView {
    return &MaterializedView{
        name:     name,
        source:   source,
        query:    query,
        interval: interval,
    }
}

func (mv *MaterializedView) Sync() error {
    // 从源表读取数据
    data := mv.querySource()
    
    // 更新物化视图
    mv.data.Range(func(k, v interface{}) bool {
        mv.data.Delete(k)
        return true
    })
    
    for k, v := range data {
        mv.data.Store(k, v)
    }
    
    mv.lastSync = time.Now()
    return nil
}

func (mv *MaterializedView) Get(key string) (interface{}, bool) {
    return mv.data.Load(key)
}
```

---

## 4. 并行查询

### 4.1 并行查询原理

```
单线程查询：
┌─────────────────────────────────────────────────────────────┐
│  Thread 1: |=====READ=====|=====FILTER=====|=====AGG=====|   │
└─────────────────────────────────────────────────────────────┘

多线程并行查询：
┌─────────────────────────────────────────────────────────────┐
│  Thread 1: |=====READ=====|=====FILTER=====|=====AGG=====|   │
│  Thread 2: |=====READ=====|=====FILTER=====|=====AGG=====|   │
│  Thread 3: |=====READ=====|=====FILTER=====|=====AGG=====|   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现并行查询

```go
// parallel_query.go

package query

import (
    "context"
    "sync"
)

type ParallelQuery struct {
    threads int
}

func NewParallelQuery(threads int) *ParallelQuery {
    return &ParallelQuery{threads: threads}
}

func (pq *ParallelQuery) Execute(ctx context.Context, chunks [][]byte) []Result {
    var wg sync.WaitGroup
    results := make([]Result, len(chunks))
    
    for i := 0; i < len(chunks); i++ {
        wg.Add(1)
        go func(idx int, chunk []byte) {
            defer wg.Done()
            results[idx] = pq.processChunk(ctx, chunk)
        }(i, chunks[i])
    }
    
    wg.Wait()
    return results
}

func (pq *ParallelQuery) processChunk(ctx context.Context, chunk []byte) Result {
    // 处理数据块
    return Result{}
}
```

---

## 5. 性能优化

### 5.1 查询优化策略

```
ClickHouse 查询优化策略：

1. 选择合适的引擎
   ├── MergeTree: 通用场景
   ├── SummingMergeTree: 聚合场景
   └── CollapsingMergeTree: 变更历史

2. 优化查询语句
   ├── 使用 IN 代替 JOIN
   ├── 预过滤数据
   └── 避免高基数聚合

3. 合理设计表
   ├── 选择合适的分区键
   ├── 选择合适的排序键
   └── 使用 TTL 管理数据
```

### 5.2 监控指标

```sql
-- 查看查询性能
SELECT 
    query_id,
    query_duration_ms / 1000 AS duration_sec,
    read_rows,
    read_bytes,
    written_rows,
    memory_usage
FROM system.query_log
ORDER BY event_time DESC
LIMIT 10;

-- 查看慢查询
SELECT 
    query,
    query_duration_ms / 1000 AS duration_sec,
    read_rows
FROM system.query_log
WHERE query_duration_ms > 1000
ORDER BY query_duration_ms DESC
LIMIT 10;
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 分区裁剪 | 按分区键过滤 |
| 谓词下推 | 先过滤后选择 |
| 物化视图 | 预计算聚合 |
| 并行查询 | 多线程处理 |

### 6.2 最佳实践

- [ ] 合理设计分区键
- [ ] 使用物化视图加速
- [ ] 选择合适的引擎
- [ ] 监控查询性能
- [ ] 定期分析慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
