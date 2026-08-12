# RAG 生产级深度实现 - 多路召回与混合检索

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 32%

---

## 一、多路召回架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG 多路召回架构                                   │
│                                                                     │
│  查询                                                                │
│    │                                                               │
│    ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Query Expansion                         │   │
│  │  (HyDE / Sub-Question / Rewriting)                          │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│              ┌──────────────┼──────────────┐                       │
│              ▼              ▼              ▼                       │
│     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│     │ BM25       │ │ Dense       │ │ Graph       │              │
│     │ (关键词)    │ │ (向量)      │ │ (知识图谱)  │              │
│     └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│            │               │               │                       │
│            └───────────────┼───────────────┘                       │
│                            ▼                                       │
│              ┌─────────────────────────┐                          │
│              │    RRF Fusion           │                          │
│              │  (Reciprocal Rank Fusion)│                          │
│              └──────────┬──────────────┘                          │
│                         ▼                                         │
│              ┌─────────────────────────┐                          │
│              │    Re-ranking           │                          │
│              │  (Cross-Encoder)        │                          │
│              └──────────┬──────────────┘                          │
│                         ▼                                         │
│              ┌─────────────────────────┐                          │
│              │    Context Assembly     │                          │
│              └─────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、HyDE 实现

```python
# rag/hyde.py
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# HyDE: 假设性文档嵌入
hyde_prompt = PromptTemplate(
    input_variables=["question"],
    template="""Given only the following question, 
    generate a hypothetical document that answers this question.
    The document should be detailed and specific.

Question: {question}

Hypothetical document:"""
)

# 使用 LLM 生成假设性文档
def hyde_generate(llm, question: str) -> str:
    chain = hyde_prompt | llm | StrOutputParser()
    return chain.invoke({"question": question})

# 示例
question = "什么是广告竞价中的 RTB？"
hypothetical_doc = hyde_generate(llm, question)
# 输出: "RTB (Real-Time Bidding) 是程序化广告中的实时竞价机制..."
```

---

## 三、RRF 融合实现

```go
// rag/rrf_fusion.go
package rag

import (
    "sort"
)

// ScoredDoc 带分数的文档
type ScoredDoc struct {
    ID      string
    Score   float64
    Source  string
}

// RRFFusion RRF 融合
func RRFFusion(results [][]ScoredDoc, k int) []ScoredDoc {
    scores := make(map[string]float64)
    docs := make(map[string]ScoredDoc)
    
    for _, res := range results {
        for rank, doc := range res {
            // RRF 公式: score = 1 / (rank + k)
            score := 1.0 / float64(rank+60)
            scores[doc.ID] += score
            docs[doc.ID] = doc
        }
    }
    
    // 排序
    type scored struct {
        id    string
        score float64
    }
    var sorted []scored
    for id, score := range scores {
        sorted = append(sorted, scored{id, score})
    }
    sort.Slice(sorted, func(i, j int) bool {
        return sorted[i].score > sorted[j].score
    })
    
    // 返回 Top-K
    var final []ScoredDoc
    for _, s := range sorted {
        if len(final) >= k {
            break
        }
        final = append(final, docs[s.id])
    }
    return final
}
```

---

## 四、Cross-Encoder 重排序

```python
# rag/cross_encoder.py
from sentence_transformers import CrossEncoder

# 初始化 Cross-Encoder
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def rerank(query: str, documents: list[str], top_k: int = 5) -> list[str]:
    # 构建查询-文档对
    pairs = [[query, doc] for doc in documents]
    
    # 计算相关性分数
    scores = cross_encoder.predict(pairs)
    
    # 排序
    scored_docs = sorted(
        zip(documents, scores),
        key=lambda x: x[1],
        reverse=True
    )
    
    return [doc for doc, _ in scored_docs[:top_k]]

# 示例
query = "广告竞价原理"
docs = ["RTB是...", "DSP是...", "SSP是..."]
reranked = rerank(query, docs, top_k=2)
```

---

## 五、完整 RAG Pipeline

```go
// rag/pipeline.go
package rag

import "context"

// RAGPipeline RAG 管道
type RAGPipeline struct {
    bm25    BM25Retriever
    dense   DenseRetriever
    graph   GraphRetriever
    reranker CrossEncoderReranker
}

// Query 执行完整 RAG 查询
func (p *RAGPipeline) Query(ctx context.Context, query string, k int) ([]Document, error) {
    // 1. 多路召回
    bm25Results := p.bm25.Search(ctx, query, k*2)
    denseResults := p.dense.Search(ctx, query, k*2)
    graphResults := p.graph.Search(ctx, query, k*2)
    
    // 2. RRF 融合
    fused := RRFFusion([][]ScoredDoc{bm25Results, denseResults, graphResults}, k*3)
    
    // 3. Cross-Encoder 重排序
    final := p.reranker.Rerank(ctx, query, fused, k)
    
    return final, nil
}
```

---

## 六、自测题

1. **HyDE 的核心思想是什么？**
   - 先生成假设性文档，再检索相似文档

2. **RRF 为什么有效？**
   - 不同检索系统的排名可以融合，减少单一系统的偏差

3. **Cross-Encoder 相比 Cross-Encoder 的优势？**
   - 更准确但更慢，适合最终排序

