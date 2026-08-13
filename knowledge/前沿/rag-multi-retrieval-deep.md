# RAG多路召回 - 资深专家深度实现

## 一、召回策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      RAG多路召回架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   查询预处理                                                              │
│   ├── 查询改写                                                            │
│   ├── 子查询生成                                                           │
│   └── 关键词提取                                                           │
│                                                                         →
│   多路召回                                                                │
│   ├── Dense Retrieval (向量检索)                                           │
│   │   └── embedding模型 → 向量数据库                                      │
│   │                                                                   │
│   ├── Sparse Retrieval (稀疏检索)                                          │
│   │   └── BM25 / TF-IDF → 倒排索引                                      │
│   │                                                                   │
│   ├── Graph Retrieval (图检索)                                             │
│   │   └── 知识图谱 → 实体关系遍历                                        │
│   │                                                                   │
│   └── Hybrid Retrieval (混合检索)                                          │
│       └── 多路结果合并                                                     │
│                                                                         →
│   排序重排                                                                │
│   ├── Cross-Encoder重排                                                   │
│   ├── Reranker模型                                                         │
│   └── 融合策略 (RRF/Weighted Sum)                                          │
│                                                                         →
│   上下文构建                                                              │
│   ├── 上下文选择                                                           │
│   ├── 上下文压缩                                                           │
│   └── 提示词拼接                                                           │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、RRF融合算法

```python
import numpy as np

def rrf_fusion(results_list, k=60):
    """
    Reciprocal Rank Fusion (RRF) 融合
    results_list: 多个检索结果的列表
    k: 平滑常数
    """
    fusion_scores = {}
    
    for doc_id in set().union(*[set(r.keys()) for r in results_list]):
        score = 0
        for result in results_list:
            if doc_id in result:
                rank = result[doc_id]
                score += 1 / (k + rank)
        fusion_scores[doc_id] = score
    
    return dict(sorted(fusion_scores.items(), 
                      key=lambda x: x[1], reverse=True))

# 使用示例
dense_results = {"doc1": 1, "doc2": 2, "doc3": 3}
sparse_results = {"doc2": 1, "doc1": 3, "doc4": 4}

final_results = rrf_fusion([dense_results, sparse_results])
# 输出: {'doc2': 0.033, 'doc1': 0.029, ...}
```

## 三、面试高频题

### Q1: 多路召回为什么有效？

```
A:
1. 互补性
2. 覆盖不同语义
3. 提升召回率
```

### Q2: 如何选择融合策略？

```
A:
1. RRF适合稀疏场景
2. Weighted Sum需要调参
3. Learning-to-Rank效果最好
```

## 四、自测题

1. 解释多路召回
2. 如何实现RRF？
3. 如何评估召回效果？

---

## 参考文档

- [RAG技术文档](https://github.com/langchain-ai/langchain)
- [RRF论文](https://plg.uwaterloo.ca/~gvcormac/cormack-rrf-sigir2009.pdf)
