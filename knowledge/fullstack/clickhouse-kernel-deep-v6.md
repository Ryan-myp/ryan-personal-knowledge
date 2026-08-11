# ClickHouse 内核深度解析

> 深入ClickHouse内核：列式存储、MergeTree、向量化执行、压缩算法。
> 源码级分析，包含OLAP场景优化。
> 适用对象：数据工程师、DBA

---

## 1. 列式存储

### 1.1 存储架构

```
ClickHouse 列式存储架构：

┌─────────────────────────────────────────────────────────────┐
│                    列式存储架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Table (表)                                                 │
│  ├── Column 1 (列1)                                         │
│  │   ├── Part 1 (分区1)                                     │
│  │   │   ├── Data.bin (数据文件)                              │
│  │   │   └── Index.idx (索引文件)                             │
│  │   └── Part 2 (分区2)                                     │
│  │       ├── Data.bin                                       │
│  │       └── Index.idx                                      │
│  ├── Column 2 (列2)                                         │
│  └── ...                                                    │
│                                                             │
│  MergeTree 引擎                                              │
│  ├── 数据合并                                                │
│  ├── 索引构建                                                │
│  └── 副本同步                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现列式存储

```go
// columnar_storage.go

package clickhouse

import (
    "sync"
)

type Column struct {
    Name      string
    DataType  string
    Parts     []*Part
}

type Part struct {
    Name     string
    Data     []byte
    Index    *MinMaxIndex
    Rows     int64
}

type MinMaxIndex struct {
    Min []byte
    Max []byte
    Positions []int64
}

type Table struct {
    Name     string
    Columns  map[string]*Column
    mu       sync.RWMutex
}

func NewTable(name string) *Table {
    return &Table{
        Name:    name,
        Columns: make(map[string]*Column),
    }
}

func (t *Table) AddColumn(col *Column) {
    t.mu.Lock()
    defer t.mu.Unlock()
    t.Columns[col.Name] = col
}

func (t *Table) Insert(rows [][]byte) error {
    t.mu.Lock()
    defer t.mu.Unlock()
    
    // 列式存储写入
    for i, row := range rows {
        for colName, col := range t.Columns {
            col.Parts[0].Data = append(col.Parts[0].Data, row[i])
        }
    }
    return nil
}
```

---

## 2. MergeTree 引擎

### 2.1 数据结构

```
MergeTree 核心数据结构：

├── Data Parts (数据段)
│   ├── 有序存储
│   └── 稀疏索引
│
├── Primary Key (主键)
│   ├── 稀疏索引
│   └── nndSkirr算法
│
├── Partition Key (分区键)
│   └── 数据分区
│
└── Sorting Key (排序键)
    └── 数据排序
```

### 2.2 Go 实现 MergeTree

```go
// mergetree.go

package clickhouse

import (
    "sort"
    "sync"
)

type MergeTree struct {
    parts      []*DataPart
    pkIndex    *PrimaryKeyIndex
    mu         sync.Mutex
}

type DataPart struct {
    Name      string
    Rows      int64
    MinMax    [][2]interface{}
    Data      []byte
}

type PrimaryKeyIndex struct {
    Keys     [][]interface{}
    Offsets  []int64
}

func NewMergeTree() *MergeTree {
    return &MergeTree{}
}

func (mt *MergeTree) Insert(part *DataPart) {
    mt.mu.Lock()
    defer mt.mu.Unlock()
    
    mt.parts = append(mt.parts, part)
    mt.buildIndex()
}

func (mt *MergeTree) buildIndex() {
    // 按主键排序
    sort.Slice(mt.parts, func(i, j int) bool {
        return mt.parts[i].MinMax[0][0].(string) < mt.parts[j].MinMax[0][0].(string)
    })
    
    // 构建稀疏索引
    mt.pkIndex = &PrimaryKeyIndex{
        Keys:    make([][]interface{}, 0),
        Offsets: make([]int64, 0),
    }
    
    // 每1024行建一个索引点
    for i, part := range mt.parts {
        if i%1024 == 0 {
            mt.pkIndex.Keys = append(mt.pkIndex.Keys, part.MinMax[0])
            mt.pkIndex.Offsets = append(mt.pkIndex.Offsets, int64(i))
        }
    }
}

func (mt *MergeTree) Merge() {
    if len(mt.parts) < 2 {
        return
    }
    
    // 合并数据段
    merged := &DataPart{
        Rows: 0,
        Data: make([]byte, 0),
    }
    
    for _, part := range mt.parts {
        merged.Data = append(merged.Data, part.Data...)
        merged.Rows += part.Rows
    }
    
    mt.parts = []*DataPart{merged}
}
```

---

## 3. 向量化执行

### 3.1 执行原理

```
向量化执行原理：

1. 列式数据读取
   └── 批量读取列数据

2. SIMD 优化
   └── 单指令多数据

3. 向量化计算
   └── 批量处理行数据

4. 结果合并
   └── 向量化输出
```

### 3.2 Go 实现向量化

```go
// vectorized_executor.go

package clickhouse

type VectorizedExecutor struct {
    batchSize int
}

type Batch struct {
    Columns [][]float64
    Size    int
}

func NewVectorizedExecutor(batchSize int) *VectorizedExecutor {
    return &VectorizedExecutor{
        batchSize: batchSize,
    }
}

func (ve *VectorizedExecutor) Execute(query *Query, data [][]float64) []float64 {
    var results []float64
    
    // 批量处理
    for i := 0; i < len(data); i += ve.batchSize {
        end := i + ve.batchSize
        if end > len(data) {
            end = len(data)
        }
        
        batch := data[i:end]
        batchResult := ve.processBatch(query, batch)
        results = append(results, batchResult...)
    }
    
    return results
}

func (ve *VectorizedExecutor) processBatch(query *Query, batch [][]float64) []float64 {
    results := make([]float64, len(batch))
    
    for i, row := range batch {
        // 向量化计算
        var value float64
        for j, col := range row {
            value += col * float64(j)
        }
        results[i] = value
    }
    
    return results
}
```

---

## 4. 压缩算法

### 4.1 压缩策略

```
ClickHouse 压缩策略：

├── 字典压缩
│   └── 高频值字典化
│
├── Delta 压缩
│   └── 差值编码
│
├── LZ4 压缩
│   └── 快速解压
│
└── ZSTD 压缩
    └── 高压缩比
```

### 4.2 Go 实现压缩

```go
// compression.go

package clickhouse

import (
    "github.com/pierrec/lz4"
)

type Compressor interface {
    Compress(data []byte) ([]byte, error)
    Decompress(data []byte) ([]byte, error)
}

type LZ4Compressor struct{}

func (c *LZ4Compressor) Compress(data []byte) ([]byte, error) {
    var buf []byte
    writer := lz4.NewWriter(&buf)
    writer.Write(data)
    writer.Close()
    return buf, nil
}

func (c *LZ4Compressor) Decompress(data []byte) ([]byte, error) {
    var buf []byte
    reader := lz4.NewReader(data)
    reader.Read(&buf)
    return buf, nil
}

type DeltaCompressor struct{}

func (c *DeltaCompressor) Compress(data []int64) []int64 {
    result := make([]int64, len(data))
    if len(data) > 0 {
        result[0] = data[0]
    }
    for i := 1; i < len(data); i++ {
        result[i] = data[i] - data[i-1]
    }
    return result
}

func (c *DeltaCompressor) Decompress(data []int64) []int64 {
    result := make([]int64, len(data))
    if len(data) > 0 {
        result[0] = data[0]
    }
    for i := 1; i < len(data); i++ {
        result[i] = result[i-1] + data[i]
    }
    return result
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 列式存储 | 高效IO |
| MergeTree | 数据管理 |
| 向量化 | 性能优化 |
| 压缩 | 空间节省 |

### 5.2 最佳实践

- [ ] 合理选择分区键
- [ ] 优化排序键
- [ ] 监控合并状态
- [ ] 选择合适的压缩算法

---

*最后更新：2026-08-11*
*作者：Ryan*
