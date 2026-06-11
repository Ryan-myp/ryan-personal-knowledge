-- 选择合适的压缩编解码器:
-- 1. Delta + DoubleDelta: 时间序列
-- 2. LZ4: 快速压缩/解压
-- 3. ZSTD: 高压缩率
```

---

### ClickHouse 的 Go 实现

```go
package clickhouse

import (
	"fmt"
	"sync"
)

type MergeTree struct {
	tableName  string
	primaryKey []string
	dataParts  []*DataPart
	mu         sync.Mutex
}

type DataPart struct {
	ID     string
	Rows   int64
	MinVal interface{}
	MaxVal interface{}
	Indexed bool
}

func NewMergeTree(name string, pk []string) *MergeTree {
	return &MergeTree{tableName: name, primaryKey: pk}
}

func (mt *MergeTree) Insert(part *DataPart) {
	mt.mu.Lock()
	defer mt.mu.Unlock()
	mt.dataParts = append(mt.dataParts, part)
}

func (mt *MergeTree) Merge() {
	mt.mu.Lock()
	defer mt.mu.Unlock()
	if len(mt.dataParts) < 2 { return }
	merged := &DataPart{Rows: mt.dataParts[0].Rows + mt.dataParts[1].Rows, Indexed: true}
	mt.dataParts = append([]*DataPart{merged}, mt.dataParts[2:]...)
}

type ColumnFamily struct {
	name     string
	columns  map[string]string
	compress string
	mu       sync.Mutex
}

func NewColumnFamily(name string) *ColumnFamily {
	return &ColumnFamily{columns: make(map[string]string), compress: "LZ4"}
}

func (cf *ColumnFamily) AddColumn(name, colType string) { cf.columns[name] = colType }
func (cf *ColumnFamily) Schema() map[string]string { return cf.columns }

func main() {
	mt := NewMergeTree("events", []string{"event_id"})
	mt.Insert(&DataPart{ID: "part_1", Rows: 10000})
	mt.Insert(&DataPart{ID: "part_2", Rows: 15000})
	mt.Merge()
	fmt.Printf("After merge: %d parts\n", len(mt.dataParts))

	cf := NewColumnFamily("users")
	cf.AddColumn("name", "String")
	cf.AddColumn("age", "UInt32")
	fmt.Printf("Schema: %v\n", cf.Schema())
}
```

---

## 自测题

### 问题 1
ClickHouse 的 MergeTree 为什么叫 MergeTree 而不是普通的 B+ Tree？

<details>
<summary>查看答案</summary>

1. **列式存储**：MergeTree 按列存储，不是行存储
2. **增量追加**：数据以 part 形式追加，不原地更新
3. **后台合并**：后台线程定期合并 parts（Merge），形成更大 part
4. **稀疏索引**：每个 part 只存 min/max，合并时索引也合并

</details>

### 问题 2
Go 的 struct 组合在 ClickHouse 的 MergeTree 设计中如何体现？

<details>
<summary>查看答案</summary>

1. MergeTree 组合了 DataPart（has-a 关系）
2. ColumnFamily 组合了 map[string]string（列定义）
3. Go 的 struct 天然支持组合模式，不需要继承
4. 实际 ClickHouse 用 C++ 实现，但 Go 的 struct 组合同样优雅

</details>