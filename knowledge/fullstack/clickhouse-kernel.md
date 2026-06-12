# ClickHouse 内核/MergeTree 深度

> MergeTree 引擎 / 分区策略 / 物化视图 / 数据压缩 / 查询优化器 / 实时插入

---

## 第一部分：入门引导（5 分钟速览）

### ClickHouse 为什么快？

1. **列式存储**：只读取需要的列，减少 I/O
2. **向量化执行**：SIMD 指令批量处理
3. **数据压缩**：LZ4/ZSTD 高压缩比
4. **MergeTree 引擎**：高效的数据合并

### ClickHouse 架构

```
客户端 → Coordinator（查询分发）
         ├── Shard 1: Node 0（主分片）
         ├── Shard 2: Node 1（主分片）
         └── Replica: Node 2（副本）
```

---

## 第二部分：MergeTree 引擎

### 2.1 MergeTree 数据模型

```
Table
├── Part 1 (20240101_20240107_1_1_0)
│   ├── column1.bin
│   ├── column2.bin
│   └── primary.idx
├── Part 2 (20240108_20240114_2_2_0)
│   ├── column1.bin
│   └── primary.idx
└── Merged Part (20240101_20240114_3_3_0)
    ├── column1.bin
    └── primary.idx
```

### 2.2 Go 实现 MergeTree 核心

```go
package clickhouse

import (
    "os"
    "sync"
)

// MergeTree 引擎核心
type MergeTree struct {
    tableName   string
    parts       []*DataPart
    merges      []*MergeTask
    mu          sync.Mutex
    compactor   *Compactor
}

type DataPart struct {
    name       string
    minDate    string
    maxDate    string
    columns    map[string]*ColumnData
    primaryKey []byte
}

type ColumnData struct {
    name     string
    data     []byte
    index    *BPlusTree
    compressed bool
}

// Insert 插入数据
func (mt *MergeTree) Insert(rows [][]interface{}) error {
    mt.mu.Lock()
    defer mt.mu.Unlock()
    
    // 1. 写入临时 part
    part := &DataPart{
        name:    "temp_" + generateUUID(),
        columns: make(map[string]*ColumnData),
    }
    
    // 2. 按列写入
    for i := range rows[0] {
        col := &ColumnData{
            name: fmt.Sprintf("column%d", i),
            data: make([]byte, 0),
        }
        
        for _, row := range rows {
            col.data = append(col.data, encodeValue(row[i])...)
        }
        
        part.columns[col.name] = col
    }
    
    // 3. 持久化到磁盘
    err := part.persist()
    if err != nil {
        return err
    }
    
    mt.parts = append(mt.parts, part)
    
    // 4. 触发合并
    mt.compactor.maybeCompact()
    
    return nil
}

// Query 查询数据
func (mt *MergeTree) Query(predicate string, columns []string) ([]map[string]interface{}, error) {
    // 1. 数据裁剪：只扫描符合条件的 part
    parts := mt.filterByPredicate(predicate)
    
    // 2. 列裁剪：只读取需要的列
    columnData := make(map[string]*ColumnData)
    for _, colName := range columns {
        columnData[colName] = parts[0].columns[colName]
    }
    
    // 3. 向量化查询
    results := make([]map[string]interface{}, 0)
    for _, part := range parts {
        rows := part.vectorizedScan(predicate, columns)
        results = append(results, rows...)
    }
    
    return results, nil
}
```

### 2.3 合并算法

```go
type Compactor struct {
    tree *MergeTree
}

func (c *Compactor) maybeCompact() {
    c.tree.mu.Lock()
    defer c.tree.mu.Unlock()
    
    // 检查是否有需要合并的 parts
    if len(c.tree.parts) < 2 {
        return
    }
    
    // 找出可以合并的 parts（同一分区）
    mergeable := c.findMergeableParts()
    if len(mergeable) < 2 {
        return
    }
    
    // 创建合并任务
    mergeTask := &MergeTask{
        source: mergeable,
        target: "merged_" + generateUUID(),
    }
    
    c.tree.merges = append(c.tree.merges, mergeTask)
    
    // 后台执行合并
    go c.executeMerge(mergeTask)
}

func (c *Compactor) executeMerge(task *MergeTask) error {
    // 1. 读取所有源 part 的数据
    mergedColumns := make(map[string]*ColumnData)
    for _, part := range task.source {
        for name, col := range part.columns {
            if mergedColumns[name] == nil {
                mergedColumns[name] = &ColumnData{name: name}
            }
            mergedColumns[name].data = append(mergedColumns[name].data, col.data...)
        }
    }
    
    // 2. 写入新的 part
    newPart := &DataPart{
        name:    task.target,
        columns: mergedColumns,
    }
    err := newPart.persist()
    if err != nil {
        return err
    }
    
    // 3. 替换旧 parts
    c.tree.parts = append(c.tree.parts, newPart)
    for _, part := range task.source {
        part.remove()
    }
    
    return nil
}
```

---

## 第三部分：分区策略

### 3.1 分区键

```go
type PartitionStrategy struct {
    partitionKey string
    partitions   map[string][]*DataPart
}

func (ps *PartitionStrategy) AddPart(part *DataPart) {
    // 根据分区键计算分区
    partitionKey := ps.computePartitionKey(part)
    
    ps.partitions[partitionKey] = append(ps.partitions[partitionKey], part)
}

func (ps *PartitionStrategy) computePartitionKey(part *DataPart) string {
    // 示例：按日期分区
    return part.minDate[:7] // YYYY-MM
}

func (ps *PartitionStrategy) DropOldPartitions(keepDays int) error {
    cutoff := time.Now().AddDate(0, 0, -keepDays)
    
    for key, parts := range ps.partitions {
        if ps.isPartitionOlderThan(key, cutoff) {
            // 删除旧分区
            for _, part := range parts {
                err := part.remove()
                if err != nil {
                    return err
                }
            }
            delete(ps.partitions, key)
        }
    }
    
    return nil
}
```

### 3.2 分区修剪

```go
func (mt *MergeTree) PartitionPruning(predicate string) []*DataPart {
    // 从谓词中提取分区键条件
    partitionKeys := ps.extractPartitionConditions(predicate)
    
    // 只扫描匹配的分区
    var results []*DataPart
    for key, parts := range mt.partitions {
        if ps.matchesPredicate(key, partitionKeys) {
            results = append(results, parts...)
        }
    }
    
    return results
}
```

---

## 第四部分：物化视图

### 4.1 物化视图实现

```go
type MaterializedView struct {
    name        string
    sourceTable string
    viewQuery   string
    viewData    *MergeTree
}

func (mv *MaterializedView) Create(sourceTable, query string) error {
    mv.sourceTable = sourceTable
    mv.viewQuery = query
    
    // 执行创建视图的 SQL
    err := mv.executeDDL(query)
    if err != nil {
        return err
    }
    
    // 触发数据填充
    go mv.fillData()
    
    return nil
}

func (mv *MaterializedView) fillData() {
    // 从源表读取数据并写入物化视图
    rows, err := mv.executeQuery(fmt.Sprintf("SELECT * FROM %s", mv.sourceTable))
    if err != nil {
        return
    }
    
    // 转换数据格式
    viewRows := mv.transformRows(rows)
    
    // 写入物化视图
    err = mv.viewData.Insert(viewRows)
    if err != nil {
        return
    }
}

func (mv *MaterializedView) transformRows(rows [][]interface{}) [][]interface{} {
    // 应用物化视图的转换逻辑
    result := make([][]interface{}, len(rows))
    for i, row := range rows {
        result[i] = mv.applyTransform(row)
    }
    return result
}
```

---

## 第五部分：自测题

### 问题 1
ClickHouse 的 MergeTree 相比传统 RDBMS 的索引有什么优势？

<details>
<summary>查看答案</summary>

1. **列式存储**：只读取需要的列
2. **数据压缩**：高压缩比减少 I/O
3. **批量处理**：向量化执行提高吞吐量
4. **自动合并**：后台合并小文件为大文件
5. **稀疏索引**：primary key 跳跃索引减少内存占用

</details>

### 问题 2
ClickHouse 如何保证实时写入的查询性能？

<details>