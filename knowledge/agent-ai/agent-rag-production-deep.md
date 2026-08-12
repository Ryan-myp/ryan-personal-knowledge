# Agent RAG 生产级深度实现 - 多路召回到评估闭环

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/RAG  
> **代码密度**: 32%

---

## 一、多路召回架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG 多路召回流水线                                │
│                                                                     │
│  Query                                                            │
│    │                                                              │
│    ├──► Dense Retrieval (向量) ───► Embedding Model ───► FAISS    │
│    │                                                                │
│    ├──► Sparse Retrieval (BM25) ───► Elasticsearch              │
│    │                                                                │
│    ├──► Hybrid Search ────► RRF Fusion                            │
│    │                                                                │
│    ├──► Knowledge Graph ───► Neo4j Query                         │
│    │                                                                │
│    ├──► Recent Cache ───────► Redis TTL                          │
│    │                                                                │
│    └──► Query Rewrite ──────► LLM Expansion                       │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │              RRF Fusion (Reciprocal Rank Fusion)         │      │
│  │  score(doc) = Σ(1 / (k + rank_i(doc)))                   │      │
│  │  k=60, 融合所有路召回结果                                 │      │
│  └─────────────────────────────────────────────────────────┘      │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、完整实现

```python
# agent_rag/multi_recall.py
from typing import List, Dict
import numpy as np

class MultiRecallRAG:
    """多路召回 RAG 系统"""
    
    def __init__(self):
        self.dense_retriever = DenseRetriever()
        self.sparse_retriever = BM25Retriever()
        self.graph_retriever = GraphRetriever()
        self.cache = TTLCache(ttl=300)
    
    def recall(self, query: str, k: int = 20) -> List[Document]:
        """多路召回"""
        results = {}
        
        # 路1: 向量召回
        dense_results = self.dense_retriever.retrieve(query, top_k=k*2)
        for doc in dense_results:
            results[doc.id] = doc
        
        # 路2: BM25召回
        sparse_results = self.sparse_retriever.retrieve(query, top_k=k*2)
        for doc in sparse_results:
            if doc.id not in results:
                results[doc.id] = doc
        
        # 路3: 知识图谱
        graph_results = self.graph_retriever.query(query)
        for doc in graph_results:
            if doc.id not in results:
                results[doc.id] = doc
        
        # 路4: 缓存命中
        cached = self.cache.get(query)
        if cached:
            for doc in cached:
                if doc.id not in results:
                    results[doc.id] = doc
        
        # 重新排序
        return self.rerank(list(results.values()), top_k=k)
    
    def rerank(self, docs: List[Document], top_k: int) -> List[Document]:
        """重排序 (Cross-Encoder)"""
        # 轻量级过滤后重排
        filtered = docs[:top_k * 3]
        scores = self.cross_encoder.score(docs, filtered)
        ranked = sorted(zip(docs, scores), key=lambda x: -x[1])
        return [d for d, _ in ranked[:top_k]]
```

---

## 三、自测题

1. **RRF公式中的k值为什么通常设为60？**
   - 经验值，平衡不同排序算法的差异

2. **多路召回相比单路召回的优势？**
   - 互补性强，召回率提升30-50%

