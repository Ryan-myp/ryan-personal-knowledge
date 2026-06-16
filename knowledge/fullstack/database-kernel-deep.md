# 数据库内核深度：B+树/索引优化/查询执行

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解数据库索引

```
数据库 = 图书馆
索引 = 图书目录卡

没有索引：
→ 从第一本书开始翻（全表扫描）
→ 找到 1000 本才找到想要的

有索引：
→ 查目录卡（O(log n)）
→ 直接定位到书架
→ 秒级找到
```

### 数据库内核核心组件

```
1. 存储引擎：数据怎么存
2. 查询优化器：SQL 怎么执行
3. 事务管理器：并发控制
4. 缓冲池：内存缓存
5. 日志系统：WAL/Redo Log
```

---

## 第二部分：B+树深度

### 2.1 B+树原理

```
B+树 vs B树：
B树：
- 每个节点都存数据
- 查找可能需要遍历多个节点

B+树：
- 只有叶子节点存数据
- 叶子节点链表连接
- 非叶子节点只存索引
- 更适合范围查询

优势：
1. 树更矮胖：同样数据量，B+树高度更小
2. 范围查询快：叶子节点链表
3. 缓存友好：节点大小 = 页大小
```

### 2.2 Go 实现 B+树

```go
package btree

import (
    "fmt"
    "sort"
)

const (
    MinDegree = 3  // 最小度数
    MaxKeys   = 2*MinDegree - 1  // 最大键数
    MinKeys   = MinDegree - 1      // 最小键数
)

// Node B+树节点
type Node struct {
    isLeaf   bool
    keys     []string
    children []*Node
    data     []interface{} // 叶子节点存储实际数据
}

// Search 搜索
func (n *Node) Search(key string) (interface{}, bool) {
    i := 0
    for i < len(n.keys) && key > n.keys[i] {
        i++
    }
    
    if n.isLeaf {
        if i < len(n.keys) && n.keys[i] == key {
            return n.data[i], true
        }
        return nil, false
    }
    
    return n.children[i].Search(key)
}

// Insert 插入
func (n *Node) Insert(key string, value interface{}) {
    if n.isLeaf {
        // 找到插入位置
        i := sort.SearchStrings(n.keys, key)
        
        // 插入
        n.keys = append(n.keys, "")
        copy(n.keys[i+1:], n.keys[i:])
        n.keys[i] = key
        
        n.data = append(n.data, nil)
        copy(n.data[i+1:], n.data[i:])
        n.data[i] = value
        
        // 检查是否需要分裂
        if len(n.keys) > MaxKeys {
            n.split()
        }
    } else {
        // 找到子节点
        i := sort.SearchStrings(n.keys, key)
        n.children[i].Insert(key, value)
        
        // 检查子节点是否需要分裂
        if len(n.children[i].keys) > MaxKeys {
            n.splitChild(i, n.children[i])
        }
    }
}

// split 叶子节点分裂
func (n *Node) split() {
    mid := len(n.keys) / 2
    
    newLeaf := &Node{
        isLeaf: true,
        keys:   n.keys[mid+1:],
        data:   n.data[mid+1:],
    }
    
    n.keys = n.keys[:mid]
    n.data = n.data[:mid]
    
    // 返回中间键和新的叶子节点
    // ...
}
```

---

## 第三部分：查询优化器

### 3.1 查询执行计划

```
SQL 查询优化步骤：
1. 解析：SQL → AST
2. 绑定：表名/列名 → 内部标识
3. 优化：选择最优执行计划
4. 执行：生成字节码/直接执行

执行计划要素：
- 扫描方式：全表扫描/索引扫描
- 连接方式：Nested Loop/Hash Join/Merge Join
- 排序方式：内存排序/外部排序
```

### 3.2 Go 实现查询优化器

```go
package optimizer

import (
    "fmt"
)

// QueryPlan 查询计划
type QueryPlan struct {
    Type       string      // scan/join/sort
    Table      string
    Index      string
    Condition  string
    Cost       float64
    Children   []*QueryPlan
}

// Optimizer 优化器
type Optimizer struct {
    statistics map[string]TableStatistics
}

type TableStatistics struct {
    Rows      int64
    Columns   map[string]ColumnStatistics
}

type ColumnStatistics struct {
    DistinctValues int64
    NullFraction   float64
    AvgWidth       int32
}

// Optimize 优化查询
func (o *Optimizer) Optimize(query *Query) *QueryPlan {
    // 1. 选择扫描方式
    scanPlan := o.chooseScan(query)
    
    // 2. 选择连接方式
    joinPlan := o.chooseJoin(query)
    
    // 3. 选择排序方式
    sortPlan := o.chooseSort(query)
    
    // 4. 选择最优计划
    return o.selectBestPlan(scanPlan, joinPlan, sortPlan)
}

func (o *Optimizer) chooseScan(query *Query) *QueryPlan {
    plan := &QueryPlan{
        Type:  "scan",
        Table: query.Table,
        Cost:  float64(o.statistics[query.Table].Rows),
    }
    
    // 检查是否有索引
    if index := o.findBestIndex(query.Table, query.Where); index != nil {
        plan.Index = index.Name
        plan.Cost = float64(index.EstimatedRows)
    }
    
    return plan
}

func (o *Optimizer) chooseJoin(query *Query) *QueryPlan {
    if len(query.Joins) == 0 {
        return nil
    }
    
    join := query.Joins[0]
    
    // 根据表大小选择连接算法
    leftRows := o.statistics[join.LeftTable].Rows
    rightRows := o.statistics[join.RightTable].Rows
    
    if leftRows < 1000 && rightRows < 1000 {
        return &QueryPlan{
            Type: "join",
            JoinType: "nested_loop",
            Cost: float64(leftRows * rightRows),
        }
    }
    
    return &QueryPlan{
        Type: "join",
        JoinType: "hash_join",
        Cost: float64(leftRows + rightRows),
    }
}
```

---

## 第四部分：缓冲池管理

### 4.1 Buffer Pool 原理

```
Buffer Pool = 内存中的页面缓存

核心组件：
1. Page：固定大小的数据块（通常 16KB）
2. LRU List：最近最少使用链表
3. Hash Table：按 (table, page_id) 快速查找
4. Flush LRU：脏页刷新链表

工作流：
1. 读请求 → 检查 Buffer Pool → 命中则返回
2. 未命中 → 从磁盘读取 → 放入 Buffer Pool
3. 写请求 → 修改 Buffer Pool → 标记为 dirty
4. 后台线程 → 定期刷新 dirty page
```

### 4.2 Go 实现 Buffer Pool

```go
package bufferpool

import (
    "container/list"
    "sync"
)

const PageSize = 16 * 1024 // 16KB

type Page struct {
    ID       int64
    Data     []byte
    Dirty    bool
    PinCount int
}

type BufferPool struct {
    pages     map[int64]*Page
    lruList   *list.List
    lruMap    map[int64]*list.Element
    maxSize   int
    mu        sync.RWMutex
    diskIO    DiskIO
}

type DiskIO interface {
    ReadPage(id int64) ([]byte, error)
    WritePage(id int64, data []byte) error
}

func NewBufferPool(maxSize int, dio DiskIO) *BufferPool {
    return &BufferPool{
        pages:   make(map[int64]*Page),
        lruList: list.New(),
        maxSize: maxSize,
        diskIO:  dio,
    }
}

// GetPage 获取页面
func (bp *BufferPool) GetPage(id int64) (*Page, error) {
    bp.mu.Lock()
    defer bp.mu.Unlock()
    
    // 检查是否在 Buffer Pool 中
    if page, ok := bp.pages[id]; ok {
        page.PinCount++
        bp.lruList.MoveToFront(bp.lruMap[id])
        return page, nil
    }
    
    // 需要从磁盘读取
    if len(bp.pages) >= bp.maxSize {
        bp.evict()
    }
    
    data, err := bp.diskIO.ReadPage(id)
    if err != nil {
        return nil, err
    }
    
    page := &Page{
        ID:   id,
        Data: data,
    }
    
    bp.pages[id] = page
    elem := bp.lruList.PushFront(page)
    bp.lruMap[id] = elem
    
    return page, nil
}

// WritePage 写入页面
func (bp *BufferPool) WritePage(id int64, data []byte) error {
    bp.mu.Lock()
    defer bp.mu.Unlock()
    
    page, ok := bp.pages[id]
    if !ok {
        return fmt.Errorf("page not found")
    }
    
    copy(page.Data, data)
    page.Dirty = true
    
    return nil
}

// evict 驱逐页面
func (bp *BufferPool) evict() {
    // 找到 LRU 页面
    back := bp.lruList.Back()
    if back == nil {
        return
    }
    
    page := back.Value.(*Page)
    
    // 如果是脏页，刷新到磁盘
    if page.Dirty {
        bp.diskIO.WritePage(page.ID, page.Data)
    }
    
    // 从 Buffer Pool 中移除
    delete(bp.pages, page.ID)
    delete(bp.lruMap, page.ID)
    bp.lruList.Remove(back)
}
```

---

## 第五部分：生产排障案例

### 5.1 索引失效

```
现象：查询突然变慢

排查：
1. EXPLAIN 查看执行计划
2. 检查索引是否被使用
3. 检查数据分布

根因：LIKE '%xxx%' 导致索引失效

解决方案：
1. 使用前缀匹配
2. 使用全文索引
3. 使用 Elasticsearch
```

### 5.2 缓冲池命中率低

```
现象：CPU 使用率高，IO 等待高

排查：
1. 检查 Buffer Pool 命中率
2. 检查页面大小
3. 检查工作集大小

根因：Buffer Pool 太小

解决方案：
1. 增大 Buffer Pool
2. 优化查询减少扫描
3. 添加合适索引
```

---

## 第六部分：自测题

### 问题 1
B+树相比 B树有什么优势？

<details>
<summary>查看答案</summary>

1. **范围查询**：叶子节点链表
2. **树更矮**：非叶子节点只存索引
3. **缓存友好**：节点大小 = 页大小
4. **磁盘 IO 少**：高度更小
5. **Go 实现**：B+树结构

</details>

### 问题 2
查询优化器如何选择执行计划？

<details>
<summary>查看答案</summary>

1. **统计信息**：表大小/列分布
2. **代价模型**：IO/CPU/内存
3. **扫描方式**：全表/索引
4. **连接算法**：Nested Loop/Hash/Merge
5. **Go 实现**：Optimizer

</details>

### 问题 3
Buffer Pool 的工作流程？

<details>
<summary>查看答案</summary>

1. **LRU**：最近最少使用
2. **Pin**：防止被驱逐
3. **Dirty**：脏页标记
4. **Flush**：后台刷新
5. **Go 实现**：BufferPool

</details>

---

*本文档基于数据库内核原理整理。*