# RAG 系统源码级深度剖析 — 检索增强生成全链路

> 标签: `#RAG` `#检索增强` `#向量数据库` `#语义检索` `#Re-ranker` `#源码级`
> 创建日期: 2026-06-08 | 作者: Ryan
> 定位: 资深专家级 — 从向量索引到生成，全链路源码级剖析

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 RAG 是什么？

RAG（Retrieval-Augmented Generation）将**外部知识检索**与**大语言模型生成**结合，解决 LLM 幻觉、知识过期、缺乏引用来源三大痛点。

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG 系统架构                              │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 索引阶段  │    │ 检索阶段  │    │ 生成阶段  │              │
│  │ Indexing  │    │ Retrieval│    │ Generation│              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │                     │
│       ├─ 文档解析      ├─ 查询编码      ├─ Prompt 拼接        │
│       ├─ 分块策略      ├─ 向量检索      ├─ Context 排序      │
│       ├─ 向量化        ├─ Re-ranking    ├─ LLM 生成          │
│       └─ 存入向量库     └─ 过滤/扩展     └─ 引用溯源          │
│                                                             │
│  ┌──────────────────────────────────────────┐              │
│  │          向量数据库 (Vector DB)           │              │
│  │  Milvus / FAISS / Chroma / Pinecone      │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 关键指标

| 指标 | 含义 | 目标值 |
|------|------|--------|
| **Recall@K** | Top-K 中是否包含相关文档 | > 0.85 |
| **MRR** | 首个相关文档的平均排名倒数 | > 0.7 |
| **Context Precision** | 返回上下文中的相关比例 | > 0.9 |
| **Context Recall** | 真实相关知识被检索覆盖比例 | > 0.8 |
| **Answer Faithfulness** | 回答是否忠于上下文 | > 0.85 |

---

## 第二部分：源码级深度剖析

### 2.1 文档分块（Chunking）— 源码级实现

分块质量直接影响检索效果。好的分块策略：保持语义完整性 + 控制窗口大小 + 重叠覆盖。

```go
// chunk.go — 多策略文档分块实现（Go 版）
package rag

import (
	"regexp"
	"strings"
	"github.com/sashabaranov/go-openai"
)

// ChunkConfig 分块配置
type ChunkConfig struct {
	MaxTokens     int    // 最大 token 数（默认 512）
	OverlapTokens int    // 重叠 token 数（默认 64）
	Strategy      string // "recursive" | "semantic" | "heading"
	MinChunkSize  int    // 最小 chunk 大小，太短的丢弃
}

// Chunk 分块结果
type Chunk struct {
	Text      string  `json:"text"`
	Tokens    int     `json:"tokens"`
	StartTime int     `json:"start_time"` // 原文位置（字符偏移）
	EndTime   int     `json:"end_time"`
	Heading   string  `json:"heading,omitempty"` // 所属标题
	SegmentID int     `json:"segment_id"`        // 段落ID
}

// TokenCounter 简易 token 计数器（兼容 tiktoken-go）
type TokenCounter struct {
	encoder *tiktoken.Encoder
}

func (tc *TokenCounter) Count(text string) int {
	return len(tc.encoder.Encode(text, nil, nil))
}

// RecursiveChunker 递归分块器 — 最实用策略
func RecursiveChunker(text string, cfg ChunkConfig, tc *TokenCounter) []Chunk {
	// 第一步：按最大块分割
	rawSegments := splitByMaxTokens(text, cfg.MaxTokens, tc)
	
	var chunks []Chunk
	var current Chunk
	current.Text = ""
	current.StartTime = 0
	
	for _, seg := range rawSegments {
		segTokens := tc.Count(seg)
		
		// 单个段落超过 maxTokens，强制截断
		if segTokens > cfg.MaxTokens {
			if current.Text != "" {
				chunks = append(chunks, current)
				current = Chunk{}
			}
			// 强制切分
			forced := forceSplit(seg, cfg.MaxTokens, tc)
			chunks = append(chunks, forced...)
			continue
		}
		
		// 检查合并后是否超限
		combinedTokens := tc.Count(current.Text + seg)
		if combinedTokens <= cfg.MaxTokens+cfg.OverlapTokens {
			if current.Text == "" {
				current.StartTime = seg.StartTime
			}
			current.Text += seg.Text
			current.EndTime = seg.EndTime
			continue
		}
		
		// 输出当前块
		if len(current.Text) > cfg.MinChunkSize {
			chunks = append(chunks, current)
		}
		
		// 新块从上一块的末尾重叠开始
		chunkTokens := tc.Count(current.Text)
		overlapStart := max(0, chunkTokens-cfg.OverlapTokens)
		overlapText := tokensToString(current.Text, overlapStart, chunkTokens)
		
		current = Chunk{
			Text:      overlapText + seg.Text,
			StartTime: seg.StartTime,
			EndTime:   seg.EndTime,
		}
	}
	
	if len(current.Text) > cfg.MinChunkSize {
		chunks = append(chunks, current)
	}
	return chunks
}
```

**分块策略对比：**

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **固定长度** | 简单、均匀 | 切断语义、浪费空间 | 纯文本、结构化数据 |
| **按标题分块** | 语义完整、层次清晰 | 标题边界不确定 | 文档、手册、论文 |
| **递归分块** | 平衡语义和粒度 | 重叠策略需调参 | **通用首选** ⭐ |
| **语义分块** | 基于句子相似度 | 需要额外的 NLP 模型 | 对话、问答对 |
| **按段落分块** | 保留段落结构 | 段落长度差异大 | 代码、技术文档 |

### 2.2 向量化（Embedding）— 源码级

Embedding 模型是 RAG 的基石。选择和质量直接影响检索效果。

```go
// embedding.go — 向量嵌入实现
package rag

import (
	"context"
	"math"
	"github.com/sashabaranov/go-openai"
)

// EmbeddingModel 向量化接口
type EmbeddingModel interface {
	// EmbedText 将文本转为向量
	EmbedText(ctx context.Context, text string) ([]float32, error)
	// EmbedBatch 批量向量化（提升吞吐量）
	EmbedBatch(ctx context.Context, texts []string) ([][]float32, error)
	// Dim 向量维度
	Dim() int
	// Name 模型名称
	Name() string
}

// OpenAIEmbedder OpenAI Embedding 实现
type OpenAIEmbedder struct {
	client *openai.Client
	model  string
	dim    int
}

func NewOpenAIEmbedder(apiKey, model string) *OpenAIEmbedder {
	dimMap := map[string]int{
		"text-embedding-3-small": 1536,
		"text-embedding-3-large": 3072,
		"text-embedding-ada-002": 1536,
	}
	return &OpenAIEmbedder{
		client: openai.NewClient(apiKey),
		model:  model,
		dim:    dimMap[model],
	}
}

func (e *OpenAIEmbedder) EmbedText(ctx context.Context, text string) ([]float32, error) {
	resp, err := e.client.CreateEmbeddings(ctx, openai.EmbeddingRequest{
		Model: openai.EmbeddingModel(e.model),
		Input: []string{text},
	})
	if err != nil {
		return nil, err
	}
	return resp.Data[0].Embedding, nil
}

// CosineSimilarity 余弦相似度（检索核心）
func CosineSimilarity(a, b []float32) float32 {
	if len(a) != len(b) {
		panic("dimension mismatch")
	}
	var dot, magA, magB float64
	for i := range a {
		dot += float64(a[i]) * float64(b[i])
		magA += float64(a[i]) * float64(a[i])
		magB += float64(b[i]) * float64(b[i])
	}
	if magA == 0 || magB == 0 {
		return 0
	}
	return float32(dot / (math.Sqrt(magA) * math.Sqrt(magB)))
}

// 国产替代方案：BAAI/bge-m3, Tencent/Hunyuan
// HuggingFace 集成（使用 transformers 本地推理）：
// python: from sentence_transformers import SentenceTransformer
// model = SentenceTransformer('BAAI/bge-m3')
// embeddings = model.encode(chunks, normalize_embeddings=True)
```

**Embedding 模型选型决策树：**

```
                    ┌─────────────────────┐
                    │  中文场景？          │
                    └─────────┬───────────┘
                   Yes ──┐    │    ┌── Yes ──→ 使用本地部署 BGE-M3/M2
                         │    │          (768维, 跨语种, 长文本)
                   No    │    │
                         ▼    ▼
              ┌──────────────────────┐
              │  在线 API 还是本地？    │
              └──────────┬───────────┘
                Yes ──┐  │  ┌── Yes ──→ BGE-Large-zh (本地)
                      │  │  │        Cohere v3 (英文首选)
                No    │  │  │
                      ▼  ▼  ▼
              ┌──────────────────┐
              │  OpenAI ada-002  │ ← 通用英文场景
              └──────────────────┘
```

### 2.3 向量索引与检索 — 源码级

RAG 检索的核心：近似最近邻搜索（ANN）。主流算法对比：

```go
// vector_index.go — 向量索引接口与实现
package rag

// IndexAlgorithm 索引算法
type IndexAlgorithm string

const (
	IndexHNSW  IndexAlgorithm = "HNSW"   // 图索引，精度最高
	IndexIVFFlat IndexAlgorithm = "IVF_FLAT" // 聚类索引，速度快
	IndexSCANN IndexAlgorithm = "SCANN"   // 近似最近邻
	IndexDiskANN IndexAlgorithm = "DISK_ANN" // 磁盘索引，海量数据
)

// VectorIndex 向量索引接口
type VectorIndex interface {
	// Add 批量添加向量
	Add(ctx context.Context, vectors [][]float32, ids []int64) error
	// Search 近似最近邻搜索
	Search(ctx context.Context, query []float32, topK int) ([]SearchResult, error)
	// Delete 删除向量
	Delete(ctx context.Context, ids []int64) error
	// Count 当前向量数量
	Count(ctx context.Context) (int, error)
}

// SearchResult 检索结果
type SearchResult struct {
	ID       int64   `json:"id"`
	Score    float32 `json:"score"`     // 相似度分数
	Distance float32 `json:"distance"`   // 距离
	Meta     map[string]interface{} `json:"meta,omitempty"`
}

// HNSWIndex HNSW (Hierarchical Navigable Small World) 索引
// 核心参数：M (连接数), efConstruction (构建时搜索深度), ef (查询时搜索深度)
type HNSWIndex struct {
	m        int      // 每节点最大连接数 (默认 16)
	efConstr int      // 构建时的 ef (默认 200)
	ef       int      // 查询时的 ef (默认 100)
	seed     int      // 随机种子
	dims     int      // 向量维度
	distance string   // "L2" | "IP" (内积) | "COSINE"
	
	// 底层实现
	impl *hnswlib.Index // C++ HNSW 绑定
}

func NewHNSWIndex(dims, m, efConstr, ef int, distance string) *HNSWIndex {
	return &HNSWIndex{
		m:        m,
		efConstr: efConstr,
		ef:       ef,
		dims:     dims,
		distance: distance,
	}
}

// QueryWithEF 调整搜索深度 — 精度/速度权衡的关键调参
// ef 越大，精度越高，速度越慢
// 经验法则: ef=100 → 速度/精度均衡, ef=500 → 高精度, ef=50 → 低延迟
func (idx *HNSWIndex) QueryWithEF(ctx context.Context, query []float32, topK, ef int) ([]SearchResult, error) {
	idx.ef = ef // 动态调整
	return idx.impl.Search(query, topK)
}
```

**主流索引算法对比：**

| 算法 | 构建速度 | 查询速度 | 精度 | 内存占用 | 适用规模 |
|------|----------|----------|------|----------|----------|
| **HNSW** | 慢 | 快 ⭐ | 最高 ⭐ | 高 | 10M 以下 |
| **IVF_FLAT** | 快 | 快 | 中 | 中 | 10M+ |
| **IVF_PQ** | 快 | 最快 | 低 | 最低 | 100M+ |
| **SCANN** | 快 | 快 | 中高 | 中 | 10M+ |
| **DiskANN** | 慢 | 中 | 高 | 最低 | 1B+ |

### 2.4 Re-ranking（重排序）— 源码级

粗筛 Top-K 后精排：召回率 vs 精度的关键权衡。

```go
// reranker.go — 重排序器实现
package rag

import (
	"context"
	"sort"
)

// Reranker 交叉编码器重排序器
type Reranker interface {
	// Rerank 对候选文档重新排序
	// queries: 查询列表
	// documents: 每个查询的候选文档
	Rerank(ctx context.Context, queries []string, documents [][]string) [][]float64
	// Name 模型名称
	Name() string
}

// CrossEncoderReranker 交叉编码器实现
// 核心原理：将 query+document 拼接后输入 BERT 模型，输出相关性分数
// 相比双编码器（Cross-Encoder），精度更高但速度慢 10-100x
type CrossEncoderReranker struct {
	model  *bert.Model // HuggingFace Transformers
	maxLen int
}

func (r *CrossEncoderReranker) Rerank(ctx context.Context, queries []string, documents [][]string) [][]float64 {
	var scores [][]float64
	
	for qi, query := range queries {
		var qs []float64
		for _, doc := range documents[qi] {
			// BERT Cross-Encoder 格式: [CLS] query [SEP] document [SEP]
			prompt := fmt.Sprintf("[CLS] %s [SEP] %s [SEP]", query, doc)
			
			// 编码 + 前向传播
			input := r.model.Tokenize(prompt, r.maxLen)
			output := r.model.Forward(input)
			
			// 取 [CLS] 输出通过分类头
			score := r.model.ClassifierHead(output[0][0])
			qs = append(qs, float64(score))
		}
		scores = append(scores, qs)
	}
	return scores
}

// HybridSearch 混合检索 — 向量 + BM25 + Re-ranking
type HybridSearchResult struct {
	VectorScore  float32 `json:"vector_score"`  // 向量检索分数
	BM25Score    float32 `json:"bm25_score"`    // BM25 分数
	RerankScore  float64 `json:"rerank_score"`  // Re-ranker 分数
	FinalScore   float64 `json:"final_score"`   // 融合后分数
	Chunk        Chunk   `json:"chunk"`
}

// RRF 倒数融合 (Reciprocal Rank Fusion)
// 不需要分数校准，只依赖排名 — 业界最流行的多路融合策略
func RRFFuse(results map[string][]SearchResult, k float64) []SearchResult {
	rankMap := make(map[int64]float64)
	
	for _, resList := range results {
		for rank, res := range resList {
			rankMap[res.ID] += 1.0 / float64(rank+k)
		}
	}
	
	// k 值经验: k=60 (Reciprocal Rank Fusion 论文推荐值)
	// 将 rankMap 转为切片并排序
	type rankedItem struct {
		id    int64
		score float64
	}
	var ranked []rankedItem
	for id, score := range rankMap {
		ranked = append(ranked, rankedItem{id, score})
	}
	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].score > ranked[j].score
	})
	
	var final []SearchResult
	for _, r := range ranked {
		// 从原始结果中找到对应的完整结果
		for _, resList := range results {
			for _, res := range resList {
				if res.ID == r.id {
					res.Score = float32(r.score)
					final = append(final, res)
					break
				}
			}
		}
	}
	return final
}
```

**混合检索融合策略对比：**

| 策略 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| **RRF** | 无需分数校准、只依赖排名 | 无法加权不同信号 | **通用首选** ⭐ |
| **加权平均** | 可精细调参 | 需要归一化、调参复杂 | 分数可校准场景 |
| **Max-Score** | 简单、召回率高 | 精度较低 | 宽松检索 |
| **学习排序 (Learning-to-Rank)** | 精度最高 | 需要标注数据、训练成本高 | 有标注数据的场景 |

### 2.5 查询改写与扩展 — 源码级

用户原始查询往往不够好，需要改写才能提高召回率。

```go
// query_rewrite.go — 查询改写模块
package rag

import (
	"context"
	"strings"
)

// RewriteStrategy 查询改写策略
type RewriteStrategy string

const (
	RewriteHyDE         RewriteStrategy = "hyde"          // Hypothetical Document Embeddings
	RewriteStepBack      RewriteStrategy = "step_back"     // 步骤退避（抽象化）
	RewriteMultiQuery    RewriteStrategy = "multi_query"   // 多查询扩展
	RewriteSubQuery      RewriteStrategy = "sub_query"     // 子查询分解
)

// HyDERewriter HyDE 方法 — 先生成假设文档，再用假设文档检索
// 核心思想：让 LLM 先"回答"问题，生成的"答案"作为检索 query，
// 比原始问题包含更多具体关键词和语义，提高召回率
type HyDERewriter struct {
	model  *openai.Client
	prompt string
}

func NewHyDERewriter(apiKey string) *HyDERewriter {
	return &HyDERewriter{
		model: openai.NewClient(apiKey),
		prompt: `You are an AI assistant. Given the user's question, 
generate a detailed hypothetical answer (2-3 paragraphs) that 
would answer the question. This hypothetical document will be used 
to retrieve relevant knowledge.

Question: {{.Question}}

Hypothetical Answer:`,
	}
}

func (r *HyDERewriter) Rewrite(ctx context.Context, query string) (string, error) {
	resp, err := r.model.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: openai.GPT4oMini,
		Messages: []openai.ChatCompletionMessage{
			{Role: "system", Content: "You generate detailed hypothetical answers for RAG retrieval."},
			{Role: "user", Content: query},
		},
		MaxTokens: 500,
		Temperature: 0.3, // 低温度保证事实性
	})
	if err != nil {
		return "", err
	}
	return resp.Choices[0].Message.Content, nil
}

// StepBackRewriter 步骤退避 — 从具体问题抽象到一般原理
// 核心思想：先退一步问更一般的问题，获得宏观理解，再结合具体问题检索
// 例如："Transformer 的 QKV 注意力机制如何计算" → 
//   第一步："什么是 Transformer 架构？" → 获得整体理解
//   第二步：结合问题和宏观理解检索
type StepBackRewriter struct {
	model *openai.Client
}

func (r *StepBackRewriter) StepBack(ctx context.Context, query string) (string, error) {
	resp, err := r.model.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: openai.GPT4oMini,
		Messages: []openai.ChatCompletionMessage{
			{Role: "system", Content: `Extract the high-level, abstract concepts 
from the following question. Return general principles and theories.
Do NOT answer the question directly. Just provide the high-level concepts.`},
			{Role: "user", Content: query},
		},
		MaxTokens: 200,
	})
	if err != nil {
		return "", err
	}
	return resp.Choices[0].Message.Content, nil
}

// MultiQueryRewriter 多查询扩展
// 从不同角度生成多个查询，提高召回覆盖率
type MultiQueryRewriter struct {
	model *openai.Client
}

func (r *MultiQueryRewriter) Rewrite(ctx context.Context, query string, n int) ([]string, error) {
	resp, err := r.model.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: openai.GPT4oMini,
		Messages: []openai.ChatCompletionMessage{
			{Role: "system", Content: fmt.Sprintf(
				`Write %d different versions of the following question.
Keep the core intent but use different phrasing and perspectives.
Return as a JSON array of strings.`, n)},
			{Role: "user", Content: query},
		},
		MaxTokens: 500,
		Temperature: 0.7, // 较高温度保证多样性
	})
	if err != nil {
		return nil, err
	}
	
	// 解析 JSON 数组
	// ...
	return queries, nil
}
```

---

## 第三部分：生产级 RAG 系统架构

### 3.1 完整 RAG Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                     生产级 RAG 全链路                            │
│                                                                │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐ │
│  │ 数据源   │──→│ 文档解析  │──→│ 智能分块   │──→│ 向量化索引  │ │
│  │ PDF/Word │   │ 提取文本  │   │ 元数据注入 │   │ ANN Index  │ │
│  │ DB/网页  │   │ OCR/NLP │   │ 层次结构   │   │ 向量DB     │ │
│  └─────────┘   └──────────┘   └───────────┘   └────────────┘ │
│                                                                  │
│  ┌────────────┐   ┌───────────┐   ┌───────────┐   ┌─────────┐ │
│  │ Prompt组装  │←──│ Context排序│←──│ Re-ranking│←──│ 查询改写 │ │
│  │ 填充模板    │   │ 窗口裁剪   │   │ 交叉编码   │   │ HyDE/MQ │ │
│  └────────────┘   └───────────┘   └───────────┘   └─────────┘ │
│          ↓                                                    │
│  ┌─────────────┐   ┌──────────┐   ┌──────────────┐           │
│  │ LLM 生成     │←──│ 上下文注入 │   │ 引用溯源      │           │
│  │ 最终回答     │   │ 上下文窗口 │   │ 来源标注     │           │
│  └─────────────┘   └──────────┘   └──────────────┘           │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 关键调优参数速查表

| 参数 | 影响 | 推荐范围 | 调优方向 |
|------|------|----------|----------|
| **chunk_size** | 检索粒度 | 200-1000 tokens | 召回率低→增大，精度低→减小 |
| **overlap** | 上下文连续性 | 10-20% chunk_size | 太短→增大 |
| **top_k (检索)** | 候选数量 | 10-50 | 召回率低→增大 |
| **ef (HNSW查询)** | 搜索精度 | 50-500 | 精度低→增大 |
| **rerank_top_n** | 精排数量 | 3-10 | 平衡速度与精度 |
| **temperature (LLM)** | 创造性vs事实性 | 0.1-0.3 | 需要事实→降低 |
| **max_context_tokens** | 注入上下文上限 | 2000-4000 | 根据模型窗口调整 |

---

## 第四部分：实战排障与调优

### 4.1 常见问题与解决方案

| 症状 | 根因 | 解决方案 |
|------|------|----------|
| **检索结果不相关** | embedding 维度不够 / 分块策略不当 | 换 BGE-M3 (1024维)，改为 recursive chunking |
| **LLM 回答遗漏信息** | top_k 太小 / rerank_top_n 不足 | 检索 30-50，精排 5-10 |
| **回答过长/啰嗦** | 注入的上下文太多 | 限制 max_context_tokens，用 RRF 融合 |
| **幻觉仍然严重** | 检索质量差 / 提示词不当 | 加入 fact-checking 步骤，加 citation 要求 |
| **检索速度太慢** | HNSW ef 太大 / 没有缓存 | 降低 ef 到 50，加查询缓存 |
| **中文检索差** | 使用英文 embedding 模型 | 换 BGE-M3 / m3e-base |

### 4.2 RAG 系统 A/B 测试设计

```go
// test_rag.go — RAG 系统评估框架
package rag

import (
	"context"
)

// EvaluationConfig 评估配置
type EvaluationConfig struct {
	Queries     []string          // 测试查询
	GroundTruth []GroundTruth     // 标准答案
	MetricSet   []string          // 评估指标
}

type GroundTruth struct {
	Query     string   `json:"query"`
	Answer    string   `json:"answer"`
	Relevant  []string `json:"relevant_chunks"` // 相关 chunk ID
}

// EvalMetrics 评估指标计算
type EvalMetrics struct {
	RecallAt10    float64 `json:"recall@10"`
	RecallAt20    float64 `json:"recall@20"`
	MRR           float64 `json:"mrr"`
	ContextPrecision float64 `json:"context_precision"`
	ContextRecall   float64 `json:"context_recall"`
	Faithfulness    float64 `json:"faithfulness"`
	AnswerRelevance float64 `json:"answer_relevance"`
}

// 评估流程：
// 1. 对每个 query 执行检索 + 生成
// 2. 计算 Recall@K (是否命中相关文档)
// 3. 计算 MRR (首个相关文档排名)
// 4. LLM-as-Judge 评估回答质量 (Faithfulness, AnswerRelevance)
// 5. 对比不同策略 (HyDE vs 原始 vs 多查询)
```

---

## 第五部分：自测

### Q1：HyDE（假设文档嵌入）方法的核心原理是什么？它在什么场景下效果最显著？

<details>
<summary>点击查看参考答案</summary>

HyDE 让 LLM 先生成一份"假设性答案"，然后用这份答案的向量去检索。核心原理是：**假设答案的语义空间与真实相关文档更接近**，比原始查询包含更多具体关键词。

**效果显著的场景**：
- 事实性问答（"XX 公司的 Q3 财报数据"）
- 专业领域查询（法律条文、医学文献）
- 原始查询过于简短模糊时

**不适用场景**：生成额外 LLM 调用开销大，对实时性要求高的场景慎用。
</details>

### Q2：为什么 RRF（倒数融合）比加权平均更受欢迎？

<details>
<summary>点击查看参考答案</summary>

RRF 的核心优势是**不需要分数校准**。不同检索源（向量、BM25、知识图谱）的分数尺度完全不同，加权平均需要先归一化再调参。RRF 只依赖排名信息：

```
Score = Σ 1 / (rank_i + k)
```

- 天然处理不同数量的结果集
- 参数 k 固定为 60（论文推荐值），无需针对每个场景调参
- 实现简单、可解释性强
</details>

### Q3：HNSW 索引的 M 和 ef 参数分别控制什么？如何调优？

<details>
<summary>点击查看参考答案</summary>

**M（连接数）**：每个节点在层级图中最多连接 M 个邻居节点。
- M 越大，精度越高，但内存和构建时间也越大
- 默认 16，精度敏感场景可设为 32

**ef（搜索深度）**：查询时在候选集中探索的节点数。
- ef 越大，召回率越高，但查询越慢
- efConstruction（构建时）> ef（查询时）
- 经验：ef=100 平衡，ef=500 高精度，ef=50 低延迟

**调优原则**：
1. 先固定 M，调整 ef 找到精度-延迟拐点
2. M 一般不需要超过 32
3. 如果延迟可接受，优先调高 ef 而非 M
</details>

### Q4：在生产环境中，如何保证 RAG 系统检索结果的可溯源性？

<details>
<summary>点击查看参考答案</summary>

三个层面的溯源保障：

1. **Chunk 级别溯源**：每个 chunk 携带 source_file、page_number、section_heading
2. **检索结果标注**：返回结果附带 confidence_score 和 relevance_reason
3. **回答引用**：LLM 输出中标注 [source: file.pdf#p12] 格式的引用

Go 实现：
```go
type Chunk struct {
    Text       string            `json:"text"`
    SourceFile string            `json:"source_file"`
    PageNum    int               `json:"page_number"`
    Section    string            `json:"section"`
    VectorID   int64             `json:"vector_id"`
    ChunkIndex int               `json:"chunk_index"`
    Metadata   map[string]string `json:"metadata"`
}
```
</details>

---

## 第六部分：动手验证

### 6.1 最小可运行 RAG 系统（Go）

以下是一个完整的、可运行的最小 RAG 系统，整合了分块→向量化→检索→重排序→生成的全链路：

```bash
# 运行验证
cd ~/ryan-personal-knowledge/knowledge/agent-ai/
# 用 Python 验证（环境更简单）
python3 rag_minimal_demo.py
```

完整的可运行代码见 `agent-ai/day-by-day/d03-rag-principles.md` 和 `d04-rag-optimization.md`，包含 Milvus 集成、BGE-M3 embedding、HyDE 查询改写等完整示例。

---

*本文基于微信读书《Agent设计模式》、《大模型RAG实战》及开源项目（LangChain、LlamaIndex、LangSmith）整理*
