# 微信读书精华：大模型 RAG 实战 蒸馏笔记

> 来源：《大模型RAG实战：RAG原理、应用与系统构建》- 汪鹏 谷清水 卞龙鹏
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：RAG 核心架构

### RAG 三阶段

```
RAG 流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 索引阶段（Indexing）                                              │
│    ├── 文档加载 → 分块（Chunking）                                   │
│    ├── 向量化 → Embedding Model                                     │
│    └── 存储 → Vector DB / Hybrid Search                            │
│                                                                     │
│ 2. 检索阶段（Retrieval）                                             │
│    ├── 用户问题 → 向量化                                            │
│    ├── 相似度搜索 → Top-K 文档片段                                  │
│    └── 重排序 → Rerank Model                                       │
│                                                                     │
│ 3. 生成阶段（Generation）                                            │
│    ├── 构建 Prompt（问题 + 检索结果）                                │
│    ├── LLM 生成答案                                                 │
│    └── 后处理 → 格式化、过滤                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 分块策略

```
分块策略对比：
┌────────────────┬────────────┬────────────┬────────────┐
│     策略       │  优点      │  缺点      │  适用场景  │
├────────────────┼────────────┼────────────┼────────────┤
│ 固定大小       │ 简单快速   │ 可能切断语义 │ 技术文档   │
│ 按段落         │ 保持段落   │ 段落大小不一 │ 一般文档   │
│ 按句子         │ 粒度精细   │ 可能不完整   │ FAQ      │
│ 语义分块       │ 语义完整   │ 需要模型     │ 长文档     │
│ 递归分块       │ 灵活       │ 实现复杂     │ 混合内容   │
└────────────────┴────────────┴────────────┴────────────┘

推荐配置：
• 块大小：512-1024 tokens
• 重叠：10-20%
• 策略：递归分块 + 语义感知
```

---

## 第二部分：向量数据库

### 主流向量数据库对比

```
┌────────────────┬────────────┬────────────┬────────────┐
│     数据库      │  特点      │  优势      │  劣势      │
├────────────────┼────────────┼────────────┼────────────┤
│ Milvus         │ 分布式     │ 水平扩展   │ 运维复杂   │
│ Pinecone       │ 托管服务   │ 简单易用   │ 价格高     │
│ Weaviate       │ 开源+云    │ 混合搜索   │ 生态较小   │
│ Chroma         │ 嵌入式     │ 轻量       │ 不适合生产 │
│ Qdrant         │ Rust编写   │ 高性能     │ 文档较少   │
│ FAISS          │ 纯向量检索 │ 速度快     │ 无持久化   │
│ pgvector       │ PostgreSQL │ 生态成熟   │ 性能一般   │
└────────────────┴────────────┴────────────┴────────────┘

广告平台推荐：Milvus（分布式）或 Qdrant（高性能）
```

### Embedding 模型选择

```
Embedding 模型对比：
┌────────────────┬────────────┬────────────┬────────────┐
│     模型       │  维度     │  速度      │  精度      │
├────────────────┼────────────┼────────────┼────────────┤
│ text-embedding-3-small  │ 1536  │ 快        │ 中         │
│ text-embedding-3-large  │ 3072  │ 中        │ 高         │
│ bge-large-zh            │ 1024  │ 中        │ 中高（中文）│
│ m3e-base                │ 768   │ 快        │ 中         │
│ text2vec-base-chinese   │ 768   │ 快        │ 中         │
└────────────────┴────────────┴────────────┴────────────┘

推荐：
• 英文：text-embedding-3-large
• 中文：bge-large-zh
• 中英混合：text-embedding-3-large
```

---

## 第三部分：高级 RAG 技术

### 1. 查询重写

```
查询重写技术：
1. HyDE（假设性文档嵌入）
   - 先生成一个假设文档
   - 用假设文档的向量检索
   - 通常比直接用问题检索效果好

2. 多查询重写
   - 生成多个变体查询
   - 并行检索
   - 合并结果

3. 步骤分解
   - 将复杂问题分解为子问题
   - 分别检索
   - 汇总答案
```

### 2. 混合搜索

```
混合搜索架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 用户查询                                                            │
│    ↓                                                                │
│  ┌─────────────┐    ┌─────────────┐                                │
│  │ 向量搜索     │    │ 关键词搜索   │                                │
│  │ (语义匹配)   │    │ (BM25)     │                                │
│  └──────┬──────┘    └──────┬──────┘                                │
│         │                  │                                       │
│         └──────┬───────────┘                                       │
│                ↓                                                  │
│         结果融合（RRF）                                            │
│                ↓                                                  │
│         重排序（Cross-Encoder）                                    │
│                ↓                                                  │
│         Top-K 结果                                                │
└─────────────────────────────────────────────────────────────────────┘

RRF（倒数排名融合）公式：
score(doc) = Σ(1 / (rank_i(doc) + k))
k 通常取 60
```

### 3. 重排序

```
重排序模型：
1. Cross-Encoder（精度高，速度慢）
   - 输入：问题 + 文档
   - 输出：相关性分数
   - 适合 Top-50 重排

2. Dual Encoder（速度快，精度稍低）
   - 分别编码问题和文档
   - 计算相似度
   - 适合大规模检索

推荐方案：Dual Encoder 检索 → Cross-Encoder 重排
```

---

## 第四部分：生产实践

### RAG 评估指标

```
评估指标：
1. 检索质量
   - Recall@K：Top-K 中是否包含正确答案
   - MRR：第一个正确结果的排名

2. 生成质量
   - Faithfulness：答案是否基于检索内容
   - Answer Relevance：答案是否相关问题
   - Context Precision：检索内容的相关性

3. 整体指标
   - RAGAS 分数：综合评估
   - 人工评估：主观质量
```

### 性能优化

```
优化要点：
1. 缓存：缓存常见查询结果
2. 批量嵌入：批量处理文档
3. 异步检索：并行检索多个来源
4. 增量索引：只索引变更部分
5. 索引压缩：减少存储空间
```

### 常见问题

```
问题 1：检索结果不相关
解决：优化分块策略、使用混合搜索、引入重排序

问题 2：生成幻觉
解决：限制上下文长度、添加引用、使用 Faithfulness 评估

问题 3：响应慢
解决：缓存、异步处理、优化 Embedding 模型

问题 4：上下文太长
解决：智能截断、摘要压缩、多跳检索
```

---

## 第五部分：自测题

### Q1: RAG 的三个阶段？

**A**: 索引（分块+向量化+存储）、检索（搜索+重排）、生成（构建Prompt+LLM生成）。

### Q2: 混合搜索为什么比纯向量搜索好？

**A**: 向量搜索擅长语义匹配，关键词搜索擅长精确匹配，两者互补。

### Q3: HyDE 的原理？

**A**: 先生成假设文档，用假设文档的向量检索，通常比直接用问题检索效果好。

---

## 第六部分：与知识库的对照

```
知识库中已有的 RAG 相关内容：
✅ agent-ai/rag-deep-dive.md — RAG 深度文档
✅ agent-ai/rag-react-combined.md — RAG + React
✅ agent-ai/ai-embedding-vectordb-rag.md — 向量数据库

缺失的知识：
❌ 查询重写（HyDE、多查询）
❌ 混合搜索（RRF 融合）
❌ 重排序（Cross-Encoder）
❌ RAG 评估（RAGAS）
```

---

## 第七部分：Go 生产级实现

### Weread RAG 检索增强生成 — Go 源码

```go
package main

import (
	"fmt"
	"math"
	"sync"
	"time"
)

// Document represents a chunk of text for RAG retrieval.
type Document struct {
	ID        string
	Title     string
	Content   string
	Embedding []float64
	Metadata  map[string]string
}

// RAGRetriever retrieves relevant documents for a query.
type RAGRetriever struct {
	mu         sync.RWMutex
	documents  []*Document
	topK       int
	similarity float64 // minimum similarity threshold
}

func NewRAGRetriever(topK int, minSimilarity float64) *RAGRetriever {
	return &RAGRetriever{
		documents:  make([]*Document, 0),
		topK:       topK,
		similarity: minSimilarity,
	}
}

// AddDocument adds a document to the retrieval index.
func (r *RAGRetriever) AddDocument(doc *Document) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.documents = append(r.documents, doc)
}

// Retrieve finds the top-K most similar documents.
func (r *RAGRetriever) Retrieve(queryEmbedding []float64) ([]*Document, []float64) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	type scoredDoc struct {
		doc     *Document
		score   float64
	}

	var scored []scoredDoc
	for _, doc := range r.documents {
		sim := cosineSimilarity(queryEmbedding, doc.Embedding)
		if sim >= r.similarity {
			scored = append(scored, scoredDoc{doc, sim})
		}
	}

	// Sort by score descending
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	// Take top K
	var results []*Document
	var scores []float64
	for i := 0; i < r.topK && i < len(scored); i++ {
		results = append(results, scored[i].doc)
		scores = append(scores, scored[i].score)
	}

	return results, scores
}

// cosineSimilarity computes the cosine similarity between two vectors.
func cosineSimilarity(a, b []float64) float64 {
	if len(a) != len(b) {
		return 0.0
	}

	var dot, magA, magB float64
	for i := range a {
		dot += a[i] * b[i]
		magA += a[i] * a[i]
		magB += b[i] * b[i]
	}

	if magA == 0 || magB == 0 {
		return 0.0
	}

	return dot / (math.Sqrt(magA) * math.Sqrt(magB))
}
```

---

## 第八部分：自测题

### 问题 1：为什么 RAG 检索用余弦相似度而非欧氏距离？

<details>
<summary>查看答案</summary>

余弦相似度的优势：
1. **方向敏感**：关注向量方向而非长度，适合文本语义
2. **尺度不变**：不受向量范数影响
3. **标准化**：结果始终在 [-1, 1] 范围内

欧氏距离对向量长度敏感，不适合高维稀疏的文本嵌入。

</details>

### 问题 2：Retrieve 函数中为什么用 RLock 而非 Lock？

<details>
<summary>查看答案</summary>

Retrieve 是纯读操作，不修改 documents 列表。使用 RLock 允许多个检索请求并发执行，而 Lock 会阻塞所有其他操作。在高并发场景下，RWMutex 的性能优势明显。

</details>

### 问题 3：RAG 系统中 topK 和 similarity 阈值如何平衡召回率和准确率？

<details>
<summary>查看答案</summary>

- **topK 大**：召回率高但可能引入噪声
- **similarity 高**：准确率高但可能漏掉相关文档
- **平衡策略**：先用高相似度过滤，再取 topK

实际生产中可以用动态阈值：根据查询复杂度调整参数。

</details>
