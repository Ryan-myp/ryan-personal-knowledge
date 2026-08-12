# RAG 评估体系深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、评估框架架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       RAG 评估框架                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    评估维度                                  │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  检索质量   │  │  生成质量   │  │    端到端质量       │  │   │
│  │  │ Retrieve    │  │ Generate    │  │    End-to-End      │  │   │
│  │  ├─────────────┤  ├─────────────┤  ├─────────────────────┤  │   │
│  │  │ • Recall    │  │ • Faithfulness│ │ • Answer Relevance │  │   │
│  │  │ • Precision │  │ • Context     │ │ • Context Recall   │  │   │
│  │  │ • MRR       │  │   Precision  │ │ • Context Precision │  │   │
│  │  │ • NDCG      │  │ • Semantic   │ │ • Semantic Similarity│ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  评估流程:                                                          │
│  构建测试集 → 执行检索 → 生成回答 → 多维度评估 → 生成报告           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、检索质量评估

### 2.1 传统信息检索指标

```go
// 文件: rag_eval/retrieval_metrics.go
package rag_eval

import "sort"

// Metrics 评估指标
type Metrics struct {
    Recall_at_K   float64
    Precision_at_K float64
    MRR           float64
    NDCG_at_K     float64
}

// CalculateRecall 计算 Recall@K
func CalculateRecall(retrieved []Document, relevant []string, k int) float64 {
    if len(relevant) == 0 {
        return 0
    }
    
    k = min(k, len(retrieved))
    relevantSet := make(map[string]bool)
    for _, r := range relevant {
        relevantSet[r.ID] = true
    }
    
    hits := 0
    for i := 0; i < k; i++ {
        if relevantSet[retrieved[i].ID] {
            hits++
        }
    }
    
    return float64(hits) / float64(len(relevant))
}

// CalculatePrecision 计算 Precision@K
func CalculatePrecision(retrieved []Document, relevant []string, k int) float64 {
    if k == 0 {
        return 0
    }
    
    relevantSet := make(map[string]bool)
    for _, r := range relevant {
        relevantSet[r.ID] = true
    }
    
    hits := 0
    for i := 0; i < k; i++ {
        if relevantSet[retrieved[i].ID] {
            hits++
        }
    }
    
    return float64(hits) / float64(k)
}

// CalculateMRR 计算 Mean Reciprocal Rank
func CalculateMRR(results [][]Document, relevant []string) float64 {
    totalRR := 0.0
    for _, retrieved := range results {
        relevantSet := make(map[string]bool)
        for _, r := range relevant {
            relevantSet[r.ID] = true
        }
        
        for i, doc := range retrieved {
            if relevantSet[doc.ID] {
                totalRR += 1.0 / float64(i+1)
                break
            }
        }
    }
    
    return totalRR / float64(len(results))
}

// CalculateNDCG 计算 NDCG@K
func CalculateNDCG(retrieved []Document, relevant []string, k int) float64 {
    k = min(k, len(retrieved))
    
    relevantSet := make(map[string]bool)
    for _, r := range relevant {
        relevantSet[r.ID] = true
    }
    
    // DCG
    dcg := 0.0
    for i := 0; i < k; i++ {
        if relevantSet[retrieved[i].ID] {
            dcg += 1.0 / math.Log2(float64(i+2))
        }
    }
    
    // Ideal DCG
    idealRelevants := min(len(relevant), k)
    idcg := 0.0
    for i := 0; i < idealRellevants; i++ {
        idcg += 1.0 / math.Log2(float64(i+2))
    }
    
    if idcg == 0 {
        return 0
    }
    
    return dcg / idcg
}
```

### 2.2 语义相关性评估

```go
// 文件: rag_eval/semantic_eval.go
package rag_eval

import (
    "github.com/desertbit/timer"
    "github.com/samber/lo"
)

// SemanticSimilarity 语义相似度评估
type SemanticSimilarity struct {
    embeddingModel *EmbeddingModel
}

// CalculateSimilarity 计算查询与文档的语义相似度
func (s *SemanticSimilarity) CalculateSimilarity(query string, docs []Document) []float64 {
    queryEmbedding := s.embeddingModel.Encode(query)
    
    similarities := make([]float64, len(docs))
    for i, doc := range docs {
        docEmbedding := s.embeddingModel.Encode(doc.Content)
        similarities[i] = cosineSimilarity(queryEmbedding, docEmbedding)
    }
    
    return similarities
}

// cosineSimilarity 余弦相似度
func cosineSimilarity(a, b []float32) float64 {
    var dot, normA, normB float64
    for i := range a {
        dot += float64(a[i] * b[i])
        normA += float64(a[i] * a[i])
        normB += float64(b[i] * b[i])
    }
    if normA == 0 || normB == 0 {
        return 0
    }
    return dot / (math.Sqrt(normA) * math.Sqrt(normB))
}
```

---

## 三、生成质量评估

### 3.1 Faithfulness 忠实度评估

```go
// 文件: rag_eval/faithfulness.go
package rag_eval

import "github.com/openai/openai-go"

// FaithfulnessEvaluator 忠实度评估器
type FaithfulnessEvaluator struct {
    client *openai.Client
}

// EvaluateFaithfulness 评估回答是否忠实于上下文
func (e *FaithfulnessEvaluator) EvaluateFaithfulness(
    ctx context.Context,
    question string,
    context string,
    answer string,
) (float64, error) {
    
    prompt := fmt.Sprintf(`
Evaluate the faithfulness of the answer based on the given context.

Question: %s
Context: %s
Answer: %s

Rate from 0 to 1 how faithful the answer is to the context.
Return only a number between 0 and 1.
`, question, context, answer)
    
    resp, err := e.client.Chat.Completions.New(ctx, openai.ChatCompletionNewParams{
        Model: openai.ChatModelGPT4,
        Messages: openai.F([]openai.ChatCompletionMessageParamUnion{
            openai.SystemMessage("You are a faithfulness evaluator."),
            openai.UserMessage(prompt),
        }),
    })
    
    if err != nil {
        return 0, err
    }
    
    score, _ := strconv.ParseFloat(strings.TrimSpace(resp.Choices[0].Message.Content), 64)
    return score, nil
}
```

### 3.2 Answer Relevance 答案相关性评估

```go
// 文件: rag_eval/answer_relevance.go
package rag_eval

// AnswerRelevanceEvaluator 答案相关性评估器
type AnswerRelevanceEvaluator struct {
    embeddingModel *EmbeddingModel
}

// EvaluateRelevance 评估答案与问题的相关性
func (e *AnswerRelevanceEvaluator) EvaluateRelevance(
    question string,
    answer string,
) float64 {
    questionEmbedding := e.embeddingModel.Encode(question)
    answerEmbedding := e.embeddingModel.Encode(answer)
    
    return cosineSimilarity(questionEmbedding, answerEmbedding)
}
```

---

## 四、RAGAS 评估体系

### 4.1 核心指标

```go
// 文件: rag_eval/ragas.go
package rag_eval

// RAGASScores RAGAS 评估分数
type RAGASScores struct {
    ContextRecall        float64
    ContextPrecision    float64
    AnswerRelevance     float64
    Faithfulness        float64
    SemanticSimilarity  float64
}

// RAGASEvaluator RAGAS 评估器
type RAGASEvaluator struct {
    questionGen   QuestionGenerator
    statementGen  StatementGenerator
    faithEval     FaithfulnessEvaluator
    relevEval     AnswerRelevanceEvaluator
}

// Evaluate 执行 RAGAS 评估
func (e *RAGASEvaluator) Evaluate(
    ctx context.Context,
    testCases []TestCase,
) (*RAGASScores, error) {
    
    var totalContextRecall, totalContextPrecision, 
        totalAnswerRelevance, totalFaithfulness float64
    
    for _, tc := range testCases {
        // 评估各维度
        contextRecall, _ := e.evalContextRecall(tc)
        contextPrecision, _ := e.evalContextPrecision(tc)
        answerRelevance, _ := e.evalAnswerRelevance(tc)
        faithfulness, _ := e.evalFaithfulness(tc)
        
        totalContextRecall += contextRecall
        totalContextPrecision += contextPrecision
        totalAnswerRelevance += answerRelevance
        totalFaithfulness += faithfulness
    }
    
    n := float64(len(testCases))
    
    return &RAGASScores{
        ContextRecall:     totalContextRecall / n,
        ContextPrecision:  totalContextPrecision / n,
        AnswerRelevance:   totalAnswerRelevance / n,
        Faithfulness:      totalFaithfulness / n,
        SemanticSimilarity: e.evalSemanticSimilarity(testCases),
    }, nil
}
```

### 4.2 指标解释

```
RAGAS 核心指标:

1. Context Recall (上下文召回率)
   ├─ 定义: 多少比例的可回答信息在检索到的上下文中
   ├─ 计算: 从答案中提取声明，检查是否在上下文中
   └─ 目标: > 0.8

2. Context Precision (上下文精确率)
   ├─ 定义: 检索结果中相关部分的比例
   ├─ 计算: 相关文档数 / 总检索文档数
   └─ 目标: > 0.7

3. Answer Relevance (答案相关性)
   ├─ 定义: 答案与问题的语义相关性
   ├─ 计算: embedding 余弦相似度
   └─ 目标: > 0.8

4. Faithfulness (忠实度)
   ├─ 定义: 答案是否忠实于上下文
   ├─ 计算: LLM 评估声明一致性
   └─ 目标: > 0.9

5. Semantic Similarity (语义相似度)
   ├─ 定义: 答案与 ground truth 的语义相似度
   ├─ 计算: embedding 相似度
   └─ 目标: > 0.85
```

---

## 五、自动化评估流程

### 5.1 测试集构建

```go
// 文件: rag_eval/testset_builder.go
package rag_eval

// TestCase 测试用例
type TestCase struct {
    Question  string
    GroundTruth string
    Contexts  []Document
    Answer    string
    Metrics   map[string]float64
}

// TestsetBuilder 测试集构建器
type TestsetBuilder struct {
    documents []Document
    generator QuestionGenerator
}

// BuildTestset 构建测试集
func (b *TestsetBuilder) BuildTestset(n int) ([]TestCase, error) {
    var testCases []TestCase
    
    for i := 0; i < n; i++ {
        // 随机选择文档
        selectedDocs := b.sampleDocuments(3)
        
        // 生成问题
        question, err := b.generator.GenerateQuestion(selectedDocs)
        if err != nil {
            continue
        }
        
        // 获取 ground truth
        groundTruth, err := b.generator.GenerateAnswer(selectedDocs)
        if err != nil {
            continue
        }
        
        testCases = append(testCases, TestCase{
            Question:    question,
            GroundTruth: groundTruth,
            Contexts:    selectedDocs,
        })
    }
    
    return testCases, nil
}
```

### 5.2 评估报告生成

```go
// 文件: rag_eval/report.go
package rag_eval

import "github.com/olekukonko/tablewriter"

// EvaluationReport 评估报告
type EvaluationReport struct {
    Timestamp   time.Time
    DatasetSize int
    Scores      RAGASScores
    Breakdown   map[string]float64
    Recommendations []string
}

// GenerateReport 生成评估报告
func GenerateReport(scores *RAGASScores, testCases []TestCase) *EvaluationReport {
    report := &EvaluationReport{
        Timestamp:   time.Now(),
        DatasetSize: len(testCases),
        Scores:      *scores,
        Breakdown: map[string]float64{
            "context_recall": scores.ContextRecall,
            "context_precision": scores.ContextPrecision,
            "answer_relevance": scores.AnswerRelevance,
            "faithfulness": scores.Faithfulness,
            "semantic_similarity": scores.SemanticSimilarity,
        },
    }
    
    // 生成建议
    report.Recommendations = report.generateRecommendations()
    
    return report
}

func (r *EvaluationReport) generateRecommendations() []string {
    var recs []string
    
    if r.Scores.ContextRecall < 0.7 {
        recs = append(recs, "提高检索召回率: 增加 chunk 重叠，使用多路召回")
    }
    if r.Scores.ContextPrecision < 0.6 {
        recs = append(recs, "提高检索精确率: 优化分块策略，引入重排序")
    }
    if r.Scores.Faithfulness < 0.8 {
        recs = append(recs, "提高忠实度: 添加引用验证，减少幻觉")
    }
    if r.Scores.AnswerRelevance < 0.7 {
        recs = append(recs, "提高答案相关性: 优化提示词，增加指令遵循")
    }
    
    return recs
}
```

---

## 六、性能基准

```
┌─────────────────────────────────────────────────────────────────┐
│                    评估性能基准                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  评估方法              耗时/样本    准确度    成本              │
│  ─────────────────────────────────────────────────────────    │
│  精确率/召回率         <1ms        70%      免费              │
│  NDCG/MRR             <1ms        75%      免费              │
│  语义相似度            5ms        80%      低                │
│  LLM 评估 (GPT-4)    500ms       95%      高                │
│  RAGAS 完整评估       2s          92%      中                │
│                                                                 │
│  推荐方案:                                                       │
│  ├─ 快速迭代: 精确率/召回率 + NDCG                               │
│  ├─ 定期评估: RAGAS 完整评估                                    │
│  └─ 最终验证: LLM 人工评估                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、实战排障指南

```
问题 1: 检索召回率低
症状: Context Recall < 0.6
解决方案:
  - 增加 chunk 重叠 (20% → 30%)
  - 使用混合检索 (向量 + BM25)
  - 引入重排序模型

问题 2: 检索精确率低
症状: Context Precision < 0.5
解决方案:
  - 优化分块大小 (500 → 800 tokens)
  - 添加元数据过滤
  - 使用 Cross-Encoder 重排序

问题 3: 答案不忠实
症状: Faithfulness < 0.7
解决方案:
  - 添加引用要求
  - 使用 Self-RAG 方法
  - 优化提示词模板
```

---

## 八、参考资料

```
核心论文:
├── "RAGAS: Automated Evaluation of Retrieval Augmented Generation"
├── "Faithfulness in Text Summarization"
└── "Measuring and Improving Answer Relevance"

开源实现:
├── ragas (Elastic)
├── DeepEval
└── RAG Triad

最佳实践:
├── LangChain Evaluation
└── LlamaIndex Evaluation
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
