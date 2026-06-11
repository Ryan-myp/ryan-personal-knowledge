// 1. wildcard 查询（*abc*）: 需要扫描所有文档
// 2. 正则表达式查询: 需要扫描所有文档
// 3. 通配符查询: 前缀通配符（abc*）比后缀通配符（*abc）快
// 4. 嵌套查询: 嵌套对象性能差
```

---

### Elasticsearch 的 Go 实现

```go
package elasticsearch

import (
	"fmt"
	"strings"
	"sync"
)

type Document struct {
	ID     string
	Fields map[string]string
}

type Index struct {
	name   string
	docMap map[string]*Document
	mu     sync.RWMutex
}

func NewIndex(name string) *Index {
	return &Index{name: name, docMap: make(map[string]*Document)}
}

func (i *Index) Put(doc *Document) {
	i.mu.Lock()
	defer i.mu.Unlock()
	i.docMap[doc.ID] = doc
}

func (i *Index) Get(id string) (*Document, bool) {
	i.mu.RLock()
	defer i.mu.RUnlock()
	d, ok := i.docMap[id]
	return d, ok
}

func (i *Index) Search(query string) []*Document {
	i.mu.RLock()
	defer i.mu.RUnlock()
	lower := strings.ToLower(query)
	var results []*Document
	for _, d := range i.docMap {
		for _, v := range d.Fields {
			if strings.Contains(strings.ToLower(v), lower) {
				results = append(results, d)
				break
			}
		}
	}
	return results
}

type Shard struct {
	indexName string
	primary   bool
	replicas  []*Shard
	mu        sync.Mutex
}

func (s *Shard) Replicate() {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, r := range s.replicas {
		// sync to replica
	}
}

type Mapping struct {
	fields map[string]struct {
		Type string
		Analyzer string
	}
}

func (m *Mapping) AddField(name, fieldtype, analyzer string) {
	m.fields[name] = struct {
		Type string
		Analyzer string
	}{fieldtype, analyzer}
}

func main() {
	idx := NewIndex("products")
	idx.Put(&Document{ID: "1", Fields: map[string]string{"name": "running shoes", "price": "89.99"}})
	idx.Put(&Document{ID: "2", Fields: map[string]string{"name": "wireless headphones", "price": "49.99"}})
	if doc, ok := idx.Get("1"); ok { fmt.Printf("Got: %s\n", doc.Fields["name"]) }
	results := idx.Search("shoes")
	fmt.Printf("Search results: %d\n", len(results))
}
```

---

## 自测题

### 问题 1
Elasticsearch 的倒排索引和 B+ 树索引在什么场景下应该用哪个？

<details>
<summary>查看答案</summary>

1. **倒排索引**：适合全文搜索、模糊匹配、关键词检索
2. **B+ 树**：适合范围查询、排序、精确匹配
3. ES 默认用倒排索引（Lucene），但 doc_values 底层是列式存储
4. 实际 ES 文档同时有倒排索引 + doc_values（列存） + stored fields

</details>

### 问题 2
Go 的 map 并发读写为什么需要 Mutex 保护？

<details>
<summary>查看答案</summary>

Go map 不是并发安全的：
1. 并发读写同一个 map 会 panic ("concurrent map writes")
2. sync.RWMutex 允许多读一写，适合读多写少场景
3. Go 1.9+ 的 sync.Map 适合键集固定、读写交替的场景
4. ES 的 Index 用 RWMutex 是正确做法：Search 多读，Put 独占写

</details>