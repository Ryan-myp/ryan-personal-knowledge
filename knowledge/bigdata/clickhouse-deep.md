# ClickHouse 深度：MergeTree 引擎/查询优化/生产实践

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 ClickHouse

```
ClickHouse = 专门做报表的图书馆

传统数据库（MySQL）：
→ 每个书架放一条记录
→ 找特定记录快
→ 统计所有记录慢

ClickHouse：
→ 每个书架放一类记录
→ 按列存储
→ 统计极快，找特定记录慢
```

### ClickHouse 核心特性

```
1. 列式存储：同列数据连续存储
2. 向量化执行：SIMD 指令加速
3. 数据压缩：同类型数据压缩率高
4. 分布式：自动分片和副本
```

---

## 第二部分：MergeTree 深度

### 2.1 MergeTree 存储格式

```
MergeTree 数据组织：
Data Parts：
→ 每个 Part 是一个数据片段
→ 包含 .bin/.mrk 等文件

Primary Key：
→ 稀疏索引
→ 不覆盖所有数据
→ 用于跳过无关数据

Partition Key：
→ 物理分区
→ 决定数据放在哪个目录
```

### 2.2 Go 实现简化 MergeTree

```go
package mergetree

import (
    "fmt"
    "sort"
)

// MergeTree MergeTree 引擎
type MergeTree struct {
    parts      []DataPart
    primaryKey []string
}

// DataPart 数据片段
type DataPart struct {
    Name     string
    Columns  map[string][]byte
    Size     int64
    MinMax   map[string][2]interface{}
}

// 稀疏索引
type SparseIndex struct {
    Keys     []string
    Offsets  []int64
}

// Insert 插入数据
func (mt *MergeTree) Insert(rows [][]interface{}) error {
    part := DataPart{
        Name:    fmt.Sprintf("part-%d", len(mt.parts)),
        Columns: make(map[string][]byte),
    }
    
    // 写入数据
    for _, row := range rows {
        for i, col := range row {
            part.Columns[mt.primaryKey[i]] = append(part.Columns[mt.primaryKey[i]], col.([]byte)...)
        }
    }
    
    // 构建索引
    part.MinMax = mt.buildMinMax(part.Columns)
    
    mt.parts = append(mt.parts, part)
    
    // 合并
    mt.merge()
    
    return nil
}

// buildMinMax 构建最小最大值索引
func (mt *MergeTree) buildMinMax(columns map[string][]byte) map[string][2]interface{} {
    minMax := make(map[string][2]interface{})
    
    for name, data := range columns {
        minVal := data[0]
        maxVal := data[0]
        
        for i := 1; i < len(data); i++ {
            if data[i] < minVal {
                minVal = data[i]
            }
            if data[i] > maxVal {
                maxVal = data[i]
            }
        }
        
        minMax[name] = [2]interface{}{minVal, maxVal}
    }
    
    return minMax
}

// merge 合并数据片段
func (mt *MergeTree) merge() {
    if len(mt.parts) < 10 {
        return
    }
    
    // 合并所有 parts
    merged := DataPart{
        Name:    fmt.Sprintf("merged-%d", len(mt.parts)),
        Columns: make(map[string][]byte),
    }
    
    for _, part := range mt.parts {
        for name, data := range part.Columns {
            merged.Columns[name] = append(merged.Columns[name], data...)
        }
    }
    
    mt.parts = []DataPart{merged}
}

// Select 查询
func (mt *MergeTree) Select(condition string) [][]interface{} {
    var results [][]interface{}
    
    for _, part := range mt.parts {
        // 利用索引跳过无关数据
        if mt.skipPart(part, condition) {
            continue
        }
        
        // 扫描数据
        results = append(results, mt.scanPart(part, condition)...)
    }
    
    return results
}

// skipPart 利用索引跳过
func (mt *MergeTree) skipPart(part DataPart, condition string) bool {
    // 检查条件是否在 MinMax 范围内
    // ...
    return false
}
```

---

## 第三部分：查询优化

### 3.1 ClickHouse 查询执行

```
查询优化步骤：
1. 解析 SQL
2. 优化器转换
3. 选择执行计划
4. 向量化执行

优化技巧：
1. 使用 PREWHERE 代替 WHERE
2. 选择合适的索引
3. 使用物化视图
4. 合理分区
```

### 3.2 Go 实现查询优化

```go
package query

import (
    "strings"
)

// QueryOptimizer 查询优化器
type QueryOptimizer struct{}

// Optimize 优化查询
func (qo *QueryOptimizer) Optimize(sql string) string {
    // 1. 谓词下推
    sql = qo.pushDownPredicates(sql)
    
    // 2. 列裁剪
    sql = qo.columnPruning(sql)
    
    // 3. 常量折叠
    sql = qo.constantFolding(sql)
    
    return sql
}

// pushDownPredicates 谓词下推
func (qo *QueryOptimizer) pushDownPredicates(sql string) string {
    // 将 WHERE 条件推到数据源
    // ...
    return sql
}

// columnPruning 列裁剪
func (qo *QueryOptimizer) columnPruning(sql string) string {
    // 只读取需要的列
    // ...
    return sql
}

// constantFolding 常量折叠
func (qo *QueryOptimizer) constantFolding(sql string) string {
    // 预先计算常量表达式
    // ...
    return sql
}
```

---

## 第四部分：生产排障案例

### 4.1 Merge 阻塞

```
现象：查询变慢，Merge 堆积

排查：
1. system.merges 查看正在进行的 Merge
2. system.metrics 查看 Merge 相关指标
3. 检查磁盘 IO

根因：写入频率太高，Merge 跟不上

解决方案：
1. 批量写入
2. 调整 Merge 参数
3. 增加磁盘 IO
```

### 4.2 内存不足

```
现象：查询 OOM

排查：
1. system.metrics 查看内存使用
2. 检查查询复杂度
3. 检查数据量

根因：大表 JOIN 导致内存溢出

解决方案：
1. 增加 max_memory_usage
2. 使用 JOIN 优化
3. 分批处理
```

---

## 第五部分：自测题

### 问题 1
ClickHouse 相比 MySQL 有什么优势？

<details>
<summary>查看答案</summary>

1. **列式存储**：统计查询快 100 倍
2. **数据压缩**：节省存储
3. **向量化执行**：SIMD 加速
4. **分布式**：自动分片
5. **Go 实现**：MergeTree

</details>

### 问题 2
MergeTree 的稀疏索引是什么？

<details>
<summary>查看答案</summary>

1. **Min-Max 索引**：每行数据的最小最大值
2. **稀疏**：不覆盖所有数据
3. **跳过扫描**：跳过无关数据
4. **数据局部性**：同列数据连续
5. **Go 实现**：SparseIndex

</details>

### 问题 3
ClickHouse 的查询优化技巧？

<details>
<summary>查看答案</summary>

1. **PREWHERE**：比 WHERE 更早过滤
2. **物化视图**：预计算
3. **合理分区**：按时间分区
4. **列裁剪**：只读需要的列
5. **Go 实现**：QueryOptimizer

</details>

---

*本文档基于 ClickHouse 原理整理。*