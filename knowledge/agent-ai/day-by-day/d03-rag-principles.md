      print("文档:", r.page_content)
  ```
  ---
  *今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
  *答不出自测题？回去重读对应章节。*

---

### RAG 系统的 Go 实现

```go
package rag

import (
	"fmt"
	"strings"
	"sync"
)

type Document struct {
	ID      string
	Content string
}

type VectorStore struct {
	documents map[string]*Document
	mu        sync.RWMutex
}

func NewVectorStore() *VectorStore {
	return &VectorStore{documents: make(map[string]*Document)}
}

func (vs *VectorStore) Add(doc *Document) {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	vs.documents[doc.ID] = doc
}

func (vs *VectorStore) Search(query string, topK int) []*Document {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	lower := strings.ToLower(query)
	type scored struct { doc *Document; score float64 }
	var results []scored

	for _, doc := range vs.documents {
		score := 0.0
		for _, word := range strings.Fields(lower) {
			if strings.Contains(strings.ToLower(doc.Content), word) {
				score += 1.0
			}
		}
		if score > 0 {
			results = append(results, scored{doc, score})
		}
	}

	for i := 0; i < len(results); i++ {
		for j := i + 1; j < len(results); j++ {
			if results[j].score > results[i].score {
				results[i], results[j] = results[j], results[i]
			}
		}
	}

	n := topK
	if n > len(results) { n = len(results) }
	result := make([]*Document, n)
	for i := 0; i < n; i++ { result[i] = results[i].doc }
	return result
}

type RAGPipeline struct {
	store         *VectorStore
	contextWindow int
}

func NewRAGPipeline(vs *VectorStore) *RAGPipeline {
	return &RAGPipeline{store: vs, contextWindow: 1000}
}

func (p *RAGPipeline) Answer(query string) string {
	results := p.store.Search(query, 3)
	if len(results) == 0 {
		return "No relevant documents"
	}

	var context strings.Builder
	for _, doc := range results {
		context.WriteString(doc.Content[:min(p.contextWindow, len(doc.Content))])
		context.WriteString("\n---\n")
	}

	return fmt.Sprintf("Query: %s\nContext: %s\nAnswer: Based on context, %s", query, context.String(), query)
}

func min(a, b int) int { if a < b { return a }; return b }

func main() {
	vs := NewVectorStore()
	vs.Add(&Document{ID: "1", Content: "Go is a statically typed, compiled programming language"})
	vs.Add(&Document{ID: "2", Content: "RAG combines retrieval with language model generation"})

	pipe := NewRAGPipeline(vs)
	answer := pipe.Answer("What is Go?")
	fmt.Printf("Answer: %s\n", answer)
}
```

---

## 自测题

### 问题 1
RAG 系统中为什么需要 Query Rewriting（查询改写）？

<details>
<summary>查看答案</summary>

1. 用户查询通常简短模糊，直接检索效果差
2. 改写后的查询包含更多关键词，召回率更高
3. 可以消除查询中的歧义
4. HyDE 是高级改写策略，先生成假设文档再检索

</details>

### 问题 2
Go 的 vector search 中为什么用线性扫描而不是哈希？

<details>
<summary>查看答案</summary>

1. 向量相似度是近似最近邻搜索，不是精确匹配
2. 哈希只支持等值查找，不支持"最接近"
3. 对于小规模向量库，线性扫描 + 排序是最简单有效的方案
4. 大规模向量库会用 HNSW、IVF 等近似算法

</details>