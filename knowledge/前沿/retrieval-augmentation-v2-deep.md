# RAG v2高级系统 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RAG v2 高级架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Query                                                                  │
│     │                                                                    │
│     ▼                                                                    │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │ Query       │    │ Query       │    │ Query       │               │
│   │ Rewrite     │    │ Decompose   │    │ Expand      │               │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│          │                  │                  │                        │
│          └──────────────────┼──────────────────┘                        │
│                             ▼                                           │
│                    ┌─────────────────┐                                   │
│                    │   Hybrid        │                                   │
│                    │   Retrieval     │                                   │
│                    │   (BM25 + Vector│                                   │
│                    │    + Graph)     │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│                             ▼                                            │
│                    ┌─────────────────┐                                   │
│                    │  Rerank         │                                   │
│                    │  (Cross-Encoder)│                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│                             ▼                                            │
│                    ┌─────────────────┐                                   │
│                    │  Response       │                                   │
│                    │  Generation     │                                   │
│                    └─────────────────┘                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、混合检索实现

```go
package ragv2

import (
    "context"
)

// HybridRetriever 混合检索器
type HybridRetriever struct {
    bm25      *BM25Retriever
    vector    *VectorRetriever
    graph     *GraphRetriever
    reranker  *Reranker
}

func (h *HybridRetriever) Retrieve(ctx context.Context, query string, k int) ([]Document, error) {
    // 多路召回
    bm25Docs, _ := h.bm25.Retrieve(ctx, query, k*2)
    vectorDocs, _ := h.vector.Retrieve(ctx, query, k*2)
    graphDocs, _ := h.graph.Retrieve(ctx, query, k*2)
    
    // 融合排序
    allDocs := append(bm25Docs, vectorDocs...)
    allDocs = append(allDocs, graphDocs...)
    
    // Rerank
    ranked := h.reranker.Rerank(ctx, query, allDocs, k)
    return ranked, nil
}

// Reranker 重排序器
type Reranker struct {
    model *CrossEncoder
}

func (r *Reranker) Rerank(ctx context.Context, query string, docs []Document, k int) []Document {
    scores := r.model.Scores(ctx, query, docs)
    
    // 排序
    type scoredDoc struct {
        doc   Document
        score float64
    }
    scored := make([]scoredDoc, len(docs))
    for i, doc := range docs {
        scored[i] = scoredDoc{doc, scores[i]}
    }
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].score > scored[j].score
    })
    
    result := make([]Document, min(k, len(scored)))
    for i, s := range scored[:min(k, len(scored))] {
        result[i] = s.doc
    }
    return result
}
```

## 三、面试高频题

### Q1: RAG v2相比v1有什么改进？

```
A:
1. 多路召回
2. 重排序
3. Query改写
```

### Q2: 如何提高RAG准确率？

```
A:
1. 混合检索
2. 交叉编码器重排序
3. 上下文压缩
```

## 四、自测题

1. 解释RAG v2架构
2. 如何实现混合检索？
3. 如何提升准确率？

---

## 参考文档

- [LlamaIndex](https://docs.llamaindex.ai/)
- [LangChain RAG](https://python.langchain.com/docs/modules/data_connection/)
