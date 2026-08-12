---
name: agent-rag-expert
description: "RAG 专家技能 — 检索增强生成、向量数据库、Embedding、检索优化"
version: 1.0.0
author: ryan
tags: [agent, rag, embedding, vectordb, retrieval, expert]
---

# RAG 专家技能

> 从 Embedding 到检索优化，掌握生产级 RAG 系统设计

## 核心能力

### 1. Embedding 系统
- **模型选型**：text-embedding-3、text-ada-002、BGE、Jina
- **维度选择**：256/512/1024/3072 维度的权衡
- **Batch 处理**：批量编码优化、并行处理
- **更新策略**：增量更新、全量重建

### 2. 向量数据库
- **Milvus**：高性能、分布式、云原生
- **Pinecone**：托管服务、易用性
- **Weaviate**：图数据库融合、内置向量
- **Qdrant**：过滤查询、Rust 编写高性能
- **ES + Dense Vector**：混合搜索方案

### 3. 检索优化
- **Hybrid Search**：关键词 + 向量混合
- **RRF 融合**：Reciprocal Rank Fusion
- **重排序 (Rerank)**：Cross-Encoder 精排
- **Query 改写**：扩展查询、重写查询

### 4. 生产化
- **延迟优化**：缓存、近似搜索 (HNSW)
- **成本控制**：Token 优化、结果截断
- **质量评估**：RETRO-F1、Hallucination 检测
- **迭代优化**：Bad Case 收集与改进

## 知识库引用

| 主题 | 文档 |
|------|------|
| RAG 深度 | `knowledge/agent-ai/rag-deep-dive.md` |
| Embedding 优化 | `knowledge/agent-ai/ai-embedding-vectordb-rag.md` |
| Embedding 微调 | `knowledge/agent-ai/ai-embedding-vectordb-finetune.md` |
| RAG + ReAct | `knowledge/agent-ai/rag-react-combined.md` |
| LangChain RAG | `knowledge/agent-ai/weread-langchain-deep.md` |
| RAG 实战 | `knowledge/agent-ai/weread-rag-deep.md` |

## 使用场景

### 场景 1: 设计 RAG 系统
1. 确定知识库规模和更新频率
2. 选择 Embedding 模型和向量库
3. 设计检索 Pipeline（召回 + 重排）
4. 实现 Query 改写和上下文管理

### 场景 2: 优化检索质量
1. 分析 Bad Case（召回不准、内容不相关）
2. 调整 Embedding 模型或维度
3. 优化分块策略（Chunk Size、Overlap）
4. 引入 Rerank 模型

### 场景 3: 性能优化
1. 使用 HNSW 近似搜索降低延迟
2. 实现结果缓存（相似查询复用）
3. 批量 Embedding 预计算
4. 流式响应降低首 Token 延迟

## 关键参数

```yaml
# RAG 配置
chunk_size: 512        # 分块大小
chunk_overlap: 64      # 重叠大小
top_k: 5               # 召回数量
rerank_top_k: 3        # 重排数量
similarity_threshold: 0.7  # 相似度阈值
max_context_tokens: 2000  # 最大上下文 token
```

## 自测题

<details>
<summary>Q1: RAG 中 Chunk Size 如何选择？</summary>

**答案**：
- **太小**（<128）：语义不完整，检索精度低
- **太大**（>1024）：噪声多，影响相关性
- **推荐**：512-768 tokens，配合 64-128 overlap
- **影响因素**：文档类型、Embedding 模型、检索策略
- **实验验证**：通过 RETRO-F1 等指标评估不同大小

</details>

<details>
<summary>Q2: 什么是 RRF 融合？如何实现？</summary>

**答案**：
RRF (Reciprocal Rank Fusion) 融合多个检索结果：
```python
def rrf_fusion(results_list, k=60):
    score_map = {}
    for results in results_list:
        for rank, doc in enumerate(results):
            score_map[doc] = score_map.get(doc, 0) + 1/(rank + k)
    return sorted(score_map.items(), key=lambda x: -x[1])
```
- k 是补偿系数，通常 60
- 越高排名文献贡献越大
- 简单有效，无需训练

</details>

<details>
<summary>Q3: 如何评估 RAG 系统质量？</summary>

**答案**：
1. **检索质量**：Hit Rate@K、MRR、NDCG
2. **生成质量**：RETRO-F1、Faithfulness、Answer Relevance
3. **Hallucination 检测**：答案是否有事实依据
4. **端到端评估**：人工评分 + 自动化指标
5. **Bad Case 分析**：定期 review 失败案例

</details>
