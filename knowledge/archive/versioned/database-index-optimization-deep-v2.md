# 数据库索引优化深度实战

> 深入数据库索引优化：B+树、哈希索引、全文索引、索引设计原则。
> 包含真实生产环境索引设计方案。
> 适用对象：DBA、后端工程师、架构师

---

## 1. B+树索引原理

### 1.1 数据结构

```
B+树结构：
├── 根节点 (Root)
├── 内部节点 (Internal)
└── 叶子节点 (Leaf)
    └── 叶子节点双向链表连接
```

### 1.2 Go 实现 B+树

```go
// bplus_tree.go

package index

type Node struct {
    IsLeaf   bool
    Keys     []string
    Values   []interface{}
    Children []*Node
    Next     *Node
}

type BPlusTree struct {
    Root  *Node
    Order int
}

func (t *BPlusTree) Search(key string) interface{} {
    node := t.findLeaf(key)
    for _, k := range node.Keys {
        if k == key {
            idx := indexOf(node.Keys, k)
            return node.Values[idx]
        }
    }
    return nil
}

func (t *BPlusTree) findLeaf(key string) *Node {
    node := t.Root
    for !node.IsLeaf {
        i := 0
        for i < len(node.Keys) && key > node.Keys[i] {
            i++
        }
        node = node.Children[i]
    }
    return node
}
```

---

## 2. 索引设计原则

### 2.1 最左前缀原则

```
联合索引 (a, b, c) 适用场景：
├── WHERE a = 1
├── WHERE a = 1 AND b = 2
├── WHERE a = 1 AND b = 2 AND c = 3
└── WHERE a = 1 AND c = 3  (部分使用)

不适用：
├── WHERE b = 2
└── WHERE c = 3
```

### 2.2 索引选择性

```
选择性 = 唯一值数量 / 总行数

高选择性 (>0.9)：适合做索引
低选择性 (<0.1)：不适合做索引

示例：
├── 性别字段：选择性低 (2/1000000)
├── 状态字段：选择性中等 (5/1000000)
└── ID字段：选择性高 (1000000/1000000)
```

---

## 3. 覆盖索引

### 3.1 概念

```
覆盖索引：查询的列都在索引中，无需回表

示例：
SELECT id, name FROM users WHERE status = 1;

索引：idx_status_name (status, name)
├── 覆盖索引：直接从索引获取 name
└── 无需回表查询主键
```

### 3.2 Go 实现

```go
// covering_index.go

package index

type CoveringIndex struct {
    Columns []string
    Index   *BPlusTree
}

func (ci *CoveringIndex) IsCovering(columns []string) bool {
    for _, col := range columns {
        if !contains(ci.Columns, col) {
            return false
        }
    }
    return true
}

func contains(slice []string, val string) bool {
    for _, s := range slice {
        if s == val {
            return true
        }
    }
    return false
}
```

---

## 4. 索引失效场景

### 4.1 常见失效场景

```
1. 函数操作
   ❌ WHERE YEAR(create_time) = 2024
   ✅ WHERE create_time >= '2024-01-01' AND create_time < '2025-01-01'

2. 隐式类型转换
   ❌ WHERE phone = 13800138000  (phone 是字符串)
   ✅ WHERE phone = '13800138000'

3. OR 条件
   ❌ WHERE a = 1 OR b = 2  (b 无索引)
   ✅ 使用 UNION ALL

4. 模糊查询前导通配符
   ❌ WHERE name LIKE '%test%'
   ✅ WHERE name LIKE 'test%'
```

### 4.2 Go 检测索引失效

```go
// index_validator.go

package index

type SQLValidator struct {
    tableSchema map[string][]Column
}

type Column struct {
    Name   string
    Type   string
    IsIndex bool
}

func (v *SQLValidator) CheckIndexUsage(sql string) []Issue {
    var issues []Issue
    // 解析 SQL
    // 检查 WHERE 条件
    // 检查索引使用情况
    return issues
}
```

---

## 5. 索引优化实战

### 5.1 慢查询优化

```
慢查询优化流程：

1. 定位慢查询
   SHOW SLOW QUERY LOG

2. 分析执行计划
   EXPLAIN SELECT ...

3. 添加索引
   ALTER TABLE ... ADD INDEX ...

4. 验证效果
   对比优化前后性能
```

### 5.2 Go 实现索引分析

```go
// index_analyzer.go

package index

import "database/sql"

type IndexAnalyzer struct {
    db *sql.DB
}

func (a *IndexAnalyzer) AnalyzeTable(tableName string) []IndexInfo {
    var indexes []IndexInfo
    rows, _ := a.db.Query("SHOW INDEX FROM " + tableName)
    defer rows.Close()
    
    for rows.Next() {
        var info IndexInfo
        // 解析索引信息
        indexes = append(indexes, info)
    }
    return indexes
}

type IndexInfo struct {
    Name      string
    Columns   []string
    Cardinality int
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 概念 | 说明 |
|------|------|
| B+树 | 数据库索引数据结构 |
| 最左前缀 | 联合索引使用原则 |
| 覆盖索引 | 避免回表优化 |
| 选择性 | 索引设计关键指标 |

### 6.2 最佳实践

- [ ] 合理设计联合索引
- [ ] 避免索引失效
- [ ] 使用覆盖索引
- [ ] 定期分析慢查询
- [ ] 监控索引使用情况

---

*最后更新：2026-08-11*
*作者：Ryan*
