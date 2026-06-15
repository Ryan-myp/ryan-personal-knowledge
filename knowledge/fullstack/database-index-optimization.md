# 数据库索引优化与 B+ 树原理

> B+ 树实现/聚簇索引/覆盖索引/索引下推/执行计划分析

---

## 第一部分：入门引导（5 分钟速览）

### 为什么索引能加速查询？

```
无索引：全表扫描 O(n)
有索引：B+ 树查找 O(log n)

100 万行数据：
- 全表扫描：~1000ms
- B+ 树索引：~3ms
```

### B+ 树 vs B 树

```
B 树：数据存储在任意节点
B+ 树：数据只在叶子节点，非叶子节点只存索引

B+ 树优势：
1. 查询稳定：所有查询都要到叶子节点
2. 范围查询快：叶子节点链表连接
3. 磁盘利用率高：内部节点只存索引
```

---

## 第二部分：B+ 树实现

### 2.1 Go 实现 B+ 树

```go
package bplustree

type Node struct {
    isLeaf   bool
    degree   int
    keys     []interface{}
    children []*Node
    values   []interface{}  // 仅叶子节点
    next     *Node          // 叶子节点链表
}

type BPlusTree struct {
    root    *Node
    degree  int
}

func NewBPlusTree(degree int) *BPlusTree {
    root := &Node{
        isLeaf: true,
        degree: degree,
    }
    return &BPlusTree{root: root, degree: degree}
}

func (bt *BPlusTree) Insert(key, value interface{}) {
    if bt.root == nil {
        bt.root = &Node{
            isLeaf: true,
            degree: bt.degree,
            keys:   []interface{}{key},
            values: []interface{}{value},
        }
        return
    }
    
    // 查找叶子节点
    leaf := bt.findLeaf(bt.root, key)
    
    // 插入键值对
    bt.insertIntoLeaf(leaf, key, value)
    
    // 如果节点满，分裂
    if len(leaf.keys) > leaf.degree {
        bt.splitLeaf(leaf)
    }
}

func (bt *BPlusTree) findLeaf(node *Node, key interface{}) *Node {
    if node.isLeaf {
        return node
    }
    
    // 找到合适的子节点
    i := 0
    for ; i < len(node.keys); i++ {
        if less(key, node.keys[i]) {
            break
        }
    }
    
    return bt.findLeaf(node.children[i], key)
}

func (bt *BPlusTree) insertIntoLeaf(leaf *Node, key, value interface{}) {
    // 找到插入位置
    pos := 0
    for ; pos < len(leaf.keys); pos++ {
        if less(key, leaf.keys[pos]) {
            break
        }
    }
    
    // 插入键值对
    leaf.keys = append(leaf.keys, nil)
    copy(leaf.keys[pos+1:], leaf.keys[pos:])
    leaf.keys[pos] = key
    
    leaf.values = append(leaf.values, nil)
    copy(leaf.values[pos+1:], leaf.values[pos:])
    leaf.values[pos] = value
}

func (bt *BPlusTree) splitLeaf(leaf *Node) {
    mid := len(leaf.keys) / 2
    
    // 创建新叶子节点
    newLeaf := &Node{
        isLeaf: true,
        degree: bt.degree,
        keys:   leaf.keys[mid:],
        values: leaf.values[mid:],
        next:   leaf.next,
    }
    leaf.keys = leaf.keys[:mid]
    leaf.values = leaf.values[:mid]
    leaf.next = newLeaf
    
    // 提升中间键到父节点
    bt.promoteKey(leaf.parent, leaf.keys[len(leaf.keys)-1], newLeaf)
}
```

### 2.2 索引查询

```go
func (bt *BPlusTree) Get(key interface{}) (interface{}, bool) {
    leaf := bt.findLeaf(bt.root, key)
    
    // 在叶子节点二分查找
    pos := bt.binarySearch(leaf.keys, key)
    if pos < len(leaf.keys) && equal(key, leaf.keys[pos]) {
        return leaf.values[pos], true
    }
    
    return nil, false
}

func (bt *BPlusTree) RangeQuery(start, end interface{}) []Pair {
    leaf := bt.findLeaf(bt.root, start)
    var result []Pair
    
    for leaf != nil {
        for i, key := range leaf.keys {
            if greater(key, end) {
                return result
            }
            if greaterOrEqual(key, start) {
                result = append(result, Pair{key, leaf.values[i]})
            }
        }
        leaf = leaf.next
    }
    
    return result
}
```

---

## 第三部分：MySQL 索引类型

### 3.1 聚簇索引 vs 二级索引

```
聚簇索引（主键索引）：
┌────────┬────────┬──────────────┐
│ 主键    │ 版本   │ 行数据        │
├────────┼────────┼──────────────┤
│ 1001   │ 1      │ 张三, 25岁   │
│ 1002   │ 2      │ 李四, 30岁   │
│ 1003   │ 1      │ 王五, 28岁   │
└────────┴────────┴──────────────┘

二级索引（姓名索引）：
┌────────┬────────┐
│ 姓名    │ 主键    │
├────────┼────────┤
│ 张三   │ 1001   │
│ 李四   │ 1002   │
│ 王五   │ 1003   │
└────────┴────────┘

回表：二级索引 → 聚簇索引 → 行数据
```

### 3.2 覆盖索引优化

```sql
-- 不使用覆盖索引（需要回表）
SELECT * FROM users WHERE age > 25;

-- 使用覆盖索引（不需要回表）
SELECT id, name FROM users WHERE age > 25;
-- 或者
CREATE INDEX idx_age_name ON users(age, name);
SELECT name FROM users WHERE age > 25;
```

### 3.3 索引下推

```go
// 传统索引扫描
func TraditionalIndexScan(index, table *BPlusTree, condition Condition) []Row {
    // 1. 通过索引找到所有匹配的主键
    keys := index.RangeQuery(condition.Min, condition.Max)
    
    // 2. 回表获取完整行
    var results []Row
    for _, key := range keys {
        row := table.Get(key.PrimaryKey)
        // 3. 在服务器端过滤
        if condition.Match(row) {
            results = append(results, row)
        }
    }
    return results
}

// 索引下推优化
func IndexConditionPushdown(index, table *BPlusTree, condition Condition) []Row {
    // 1. 通过索引找到所有匹配的主键
    keys := index.RangeQuery(condition.Min, condition.Max)
    
    var results []Row
    for _, key := range keys {
        row := table.Get(key.PrimaryKey)
        // 2. 在存储引擎层过滤（减少回表）
        if condition.MatchPartial(row) {
            results = append(results, row)
        }
    }
    return results
}
```

---

## 第四部分：执行计划分析

### 4.1 EXPLAIN 解读

```sql
EXPLAIN SELECT * FROM ads WHERE campaign_id = 123 AND status = 'active';
```

```
id | select_type | table | type | possible_keys | key | key_len | ref | rows | Extra
---|-------------|-------|------|---------------|-----|---------|-----|------|-------
1  | SIMPLE      | ads   | ref  | idx_campaign  | idx_campaign | 4 | const | 1000 | Using where
```

- **type**: ref = 使用索引等值查询
- **rows**: 预估扫描行数
- **Extra**: Using where = 需要额外过滤

### 4.2 索引优化原则

```
1. 最左前缀原则：复合索引 (a,b,c)，查询必须从 a 开始
2. 选择性高的列放前面：区分度大的列放在索引前列
3. 避免函数操作：WHERE YEAR(date) = 2024 无法使用索引
4. 避免 LIKE 前缀通配符：LIKE '%abc' 无法使用索引
5. 覆盖索引：SELECT 只查索引列，避免回表
6. 索引下推：MySQL 5.6+ 支持，减少回表
```

---

## 第五部分：自测题

### 问题 1
为什么 B+ 树比 B 树更适合数据库索引？

<details>
<summary>查看答案</summary>

1. **范围查询**：叶子节点链表连接，O(n) 扫描
2. **查询稳定**：所有查询都到叶子节点
3. **磁盘友好**：内部节点只存索引，一页可存更多
4. **IO 次数少**：树高度更低
5. **Redis 有序集合**：跳表实现，内存友好

</details>

### 问题 2
什么情况下索引会失效？

<details>
<summary>查看答案</summary>

1. **函数操作**：WHERE UPPER(name) = 'ABC'
2. **类型转换**：WHERE phone = 13800000000（字符串列）
3. **OR 条件**：WHERE a=1 OR b=2（b 无索引）
4. **LIKE 前缀**：WHERE name LIKE '%abc'
5. **隐式转换**：字符串列传数字

</details>

### 问题 3
覆盖索引为什么能提升性能？

<details>
<summary>查看答案</summary>

1. **避免回表**：不需要查聚簇索引
2. **减少 IO**：只读索引树，数据在内存
3. **减少 CPU**：不需要加载完整行
4. **适用场景**：SELECT 只查索引列
5. **Go 实现**：BPlusTree.RangeQuery

</details>

---

*本文档基于数据库索引原理整理。*