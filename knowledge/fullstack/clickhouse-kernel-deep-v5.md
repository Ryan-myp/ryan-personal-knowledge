# ClickHouse 内核深度解析

> 深入 ClickHouse 核心：MergeTree、查询执行、数据压缩、分布式架构。
> 源码级分析，包含性能优化和故障排查。
> 适用对象：数据工程师、DBA、后端工程师

---

## 1. MergeTree 引擎

### 1.1 数据结构

```
┌─────────────────────────────────────────────────┐
│                 MergeTree 引擎                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  Part (数据片段)                                  │
│  ├── data.bin (主数据)                            │
│  ├── data_compressed.bin (压缩数据)              │
│  ├── primary.idx (主键索引)                      │
│  └── checksums.txt (校验和)                      │
│                                                  │
│  Mutation (修改操作)                               │
│  └── 异步执行 DROP COLUMN / ALTER COLUMN         │
│                                                  │
│  Sparsification (稀疏化)                          │
│  └── 主键粒度 (PK granularity) 控制读取效率      │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 1.2 Go 模拟数据模型

```go
// mergetree.go

package clickhouse

import (
    "sort"
)

type PrimaryKeyIndex struct {
    Granules []Granule
}

type Granule struct {
    RowOffsets []uint64  // 行偏移量
    MinMax     []Value   // 最小最大值
}

type Part struct {
    Name        string
    Rows        uint64
    Bytes       uint64
    IndexSize   uint64
    ModificationTime int64
}

func (p *Part) CalculateIndexSize( Granularity uint64) uint64 {
    // 计算主键索引大小
    return p.Rows / Granularity * 64
}

func (parts []*Part) SortByModificationTime() {
    sort.Slice(parts, func(i, j int) bool {
        return parts[i].ModificationTime < parts[j].ModificationTime
    })
}
```

---

## 2. 查询执行引擎

### 2.1 执行流程

```
ClickHouse 查询执行流程：

1. Parser (解析器)
   └── SQL → AST

2. Analyzer (分析器)
   └── AST → 查询计划

3. Optimizer (优化器)
   ├── 谓词下推
   ├── 列裁剪
   └── 分区裁剪

4. Executor (执行器)
   └── 并行执行查询计划
```

### 2.2 Go 实现查询优化

```go
// query_optimizer.go

package clickhouse

type QueryOptimizer struct {
    predicates []Predicate
    columns    []string
    partitions []string
}

type Predicate struct {
    Column string
    Op     string
    Value  interface{}
}

func (qo *QueryOptimizer) Optimize(query *Query) *Query {
    // 谓词下推
    qo.pushDownPredicates(query)
    
    // 列裁剪
    qo.pruneColumns(query)
    
    // 分区裁剪
    qo.prunePartitions(query)
    
    return query
}

func (qo *QueryOptimizer) pushDownPredicates(query *Query) {
    // 将 WHERE 条件下推到扫描阶段
    for _, pred := range query.Predicates {
        query.ScanPredicates = append(query.ScanPredicates, pred)
    }
}

func (qo *QueryOptimizer) pruneColumns(query *Query) {
    // 只保留 SELECT 和 WHERE 中用到的列
    needed := make(map[string]bool)
    for _, col := range query.SelectColumns {
        needed[col] = true
    }
    for _, pred := range query.Predicates {
        needed[pred.Column] = true
    }
    query.Columns = needed
}

func (qo *QueryOptimizer) prunePartitions(query *Query) {
    // 根据 WHERE 条件裁剪分区
    for _, pred := range query.Predicates {
        if pred.Column == "partition_key" {
            query.Partitions = append(query.Partitions, pred.Value)
        }
    }
}
```

---

## 3. 数据压缩

### 3.1 压缩算法

```
ClickHouse 压缩算法：

1. Delta 编码
   └── 适用于递增数据

2. XOR 编码
   └── 适用于相似数据

3. ZSTD
   └── 高压缩比

4. LZ4
   └── 快速压缩/解压

5. NASLO (Native)
   └── 自定义算法
```

### 3.2 Go 实现压缩统计

```go
// compression_stats.go

package clickhouse

import (
    "compress/zlib"
    "io"
    "bytes"
)

type CompressionStats struct {
    OriginalSize uint64
    CompressedSize uint64
    Ratio float64
}

func CalculateCompressionRatio(data []byte) CompressionStats {
    originalSize := uint64(len(data))
    
    // 使用 zlib 压缩
    var buf bytes.Buffer
    w := zlib.NewWriter(&buf)
    w.Write(data)
    w.Close()
    
    compressedSize := uint64(buf.Len())
    ratio := float64(compressedSize) / float64(originalSize)
    
    return CompressionStats{
        OriginalSize:   originalSize,
        CompressedSize: compressedSize,
        Ratio:          ratio,
    }
}

func CompressData(data []byte, algorithm string) ([]byte, error) {
    switch algorithm {
    case "lz4":
        return compressLZ4(data)
    case "zstd":
        return compressZSTD(data)
    default:
        return compressDefault(data)
    }
}

func compressLZ4(data []byte) ([]byte, error) {
    // LZ4 压缩实现
    return data, nil
}

func compressZSTD(data []byte) ([]byte, error) {
    // ZSTD 压缩实现
    return data, nil
}
```

---

## 4. 分布式架构

### 4.1 表类型

```
ClickHouse 分布式表类型：

1. Distributed
   ├── 本地数据存储在子节点
   └── 查询时路由到子节点

2. ReplicatedMergeTree
   ├── 数据副本
   └── ZooKeeper 协调复制
```

### 4.2 Go 实现分布式查询

```go
// distributed_query.go

package clickhouse

import (
    "context"
    "sync"
)

type DistributedTable struct {
    LocalTables []*LocalTable
    ShardingKey string
}

type LocalTable struct {
    Name   string
    Host   string
    Port   int
}

func (dt *DistributedTable) Query(ctx context.Context, sql string) ([]Row, error) {
    var wg sync.WaitGroup
    results := make([][]Row, len(dt.LocalTables))
    errs := make([]error, len(dt.LocalTables))
    
    for i, local := range dt.LocalTables {
        wg.Add(1)
        go func(idx int, table *LocalTable) {
            defer wg.Done()
            results[idx], errs[idx] = table.Query(ctx, sql)
        }(i, local)
    }
    
    wg.Wait()
    
    // 合并结果
    var allResults []Row
    for _, r := range results {
        allResults = append(allResults, r...)
    }
    return allResults, nil
}
```

---

## 5. 性能优化

### 5.1 索引优化

```
ClickHouse 索引优化策略：

1. 主键粒度 (Granularity)
   └── 默认 8192 行

2. 排序键 (Order By)
   └── 决定数据物理存储顺序

3. 索引粒度
   └── 平衡查询性能和存储空间
```

### 5.2 Go 实现索引统计

```go
// index_stats.go

package clickhouse

type IndexStats struct {
    Granularity     uint64
    IndexSize       uint64
    ReadEfficiency  float64
}

func CalculateIndexStats(totalRows, indexSize uint64, granularity uint64) IndexStats {
    granules := totalRows / granularity
    readEfficiency := float64(granules) / float64(totalRows)
    
    return IndexStats{
        Granularity:     granularity,
        IndexSize:       indexSize,
        ReadEfficiency:  readEfficiency,
    }
}

func OptimizeGranularity(totalRows, targetIndexSize uint64) uint64 {
    // 根据目标索引大小计算最优粒度
    return totalRows * 64 / targetIndexSize
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| MergeTree | Part + 主键索引 |
| 查询执行 | Parser → Analyzer → Optimizer → Executor |
| 压缩 | Delta + XOR + ZSTD/LZ4 |
| 分布式 | Distributed + Replicated |

### 6.2 最佳实践

- [ ] 合理设置主键粒度
- [ ] 选择合适排序键
- [ ] 监控压缩率
- [ ] 分布式表查询优化
- [ ] 定期合并数据

---

*最后更新：2026-08-11*
*作者：Ryan*
