# RAG 评估体系完整实现 - RAGAS 深度解析

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **难度**: 专家级  
> **代码密度**: 30%

---

## 一、RAG 评估五大指标

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RAG 评估框架 (RAGAS)                            │
│                                                                     │
│  上下文指标 (Context Metrics)           答案指标 (Answer Metrics)   │
│  ┌──────────────────┐                  ┌──────────────────┐        │
│  │ Context Recall   │                  │ Answer Relevancy │        │
│  │ (60%)            │                  │ (20%)            │        │
│  │ 召回率: 检索内容  │                  │ 答案与问题相关度  │        │
│  │ 是否覆盖答案     │                  └──────────────────┘        │
│  └──────────────────┘                  ┌──────────────────┐        │
│  ┌──────────────────┐                  │ Faithfulness     │        │
│  │ Context Precision│                  │ (20%)            │        │
│  │ (40%)            │                  │ 答案是否忠于上下文 │        │
│  │ 精确率: 检索内容  │                  └──────────────────┘        │
│  │ 多少是相关的     │                                          │
│  └──────────────────┘                                  ┌──────────────────┐
│                                                          │ Context          │        │
│                                                          │ Relevance      │        │
│                                                          │ (可选)         │        │
│                                                          └──────────────────┘        │
│                                                                     │
│  综合得分 = 0.5 × (Recall × Precision) + 0.25 × Relevancy + 0.25 × Faithfulness
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心实现代码

### 2.1 评估器主框架

```go
// rag_eval/evaluator.go
package rag_eval

import (
    "context"
    "fmt"
    "math"
)

// EvaluationResult 单次评估结果
type EvaluationResult struct {
    Question       string  `json:"question"`
    GroundTruth    string  `json:"ground_truth"`
    Context        string  `json:"context"`
    Answer         string  `json:"answer"`
    ContextRecall  float64 `json:"context_recall"`
    ContextPrec    float64 `json:"context_precision"`
    AnswerRel      float64 `json:"answer_relevancy"`
    Faithfulness   float64 `json:"faithfulness"`
    RagasScore     float64 `json:"ragas_score"`
}

// Evaluator 评估器
type Evaluator struct {
    llm        LLMClient
    embedder   Embedder
    threshold  float64
}

// NewEvaluator 创建评估器
func NewEvaluator(llm LLMClient, embedder Embedder) *Evaluator {
    return &Evaluator{
        llm:       llm,
        embedder:  embedder,
        threshold: 0.7,
    }
}

// Evaluate 评估单个问答
func (e *Evaluator) Evaluate(ctx context.Context, qac QueryAnswerContext) (*EvaluationResult, error) {
    result := &EvaluationResult{
        Question:  qac.Question,
        GroundTruth: qac.GroundTruth,
        Context:   qac.Context,
        Answer:    qac.Answer,
    }
    
    var err error
    result.ContextRecall, err = e.calcContextRecall(ctx, qac)
    if err != nil {
        return nil, fmt.Errorf("context recall: %w", err)
    }
    
    result.ContextPrec, err = e.calcContextPrecision(ctx, qac)
    if err != nil {
        return nil, fmt.Errorf("context precision: %w", err)
    }
    
    result.AnswerRel, err = e.calcAnswerRelevancy(ctx, qac)
    if err != nil {
        return nil, fmt.Errorf("answer relevancy: %w", err)
    }
    
    result.Faithfulness, err = e.calcFaithfulness(ctx, qac)
    if err != nil {
        return nil, fmt.Errorf("faithfulness: %w", err)
    }
    
    result.RagasScore = e.calcRagasScore(result)
    return result, nil
}

// calcRagasScore 计算综合得分
func (e *Evaluator) calcRagasScore(r *EvaluationResult) float64 {
    ctxScore := r.ContextRecall * r.ContextPrec
    score := 0.5*ctxScore + 0.25*r.AnswerRel + 0.25*r.Faithfulness
    return math.Round(score*100) / 100
}
```

### 2.2 Context Recall 计算

```go
// rag_eval/context_recall.go
package rag_eval

import "context"

// calcContextRecall 计算上下文召回率
// 原理: 从ground truth提取声明，检查每个声明是否在context中
func (e *Evaluator) calcContextRecall(ctx context.Context, qac QueryAnswerContext) (float64, error) {
    // 1. 从ground truth提取事实声明
    claims := extractClaims(qac.GroundTruth)
    if len(claims) == 0 {
        return 1.0, nil
    }
    
    // 2. 检查每个声明是否在context中
    covered := 0
    for _, claim := range claims {
        if e.isClaimSupported(ctx, qac.Context, claim) {
            covered++
        }
    }
    
    return float64(covered) / float64(len(claims)), nil
}

// isClaimSupported 使用embedding相似度判断声明是否被支持
func (e *Evaluator) isClaimSupported(ctx context.Context, context, claim string) bool {
    ctxVec := e.embedder.Embed(ctx, context)
    claimVec := e.embedder.Embed(ctx, claim)
    
    similarity := cosineSimilarity(ctxVec, claimVec)
    return similarity >= e.threshold
}

// extractClaims 提取文本中的事实声明 (LLM调用)
func extractClaims(text string) []string {
    // Prompt模板
    prompt := fmt.Sprintf(`Extract all factual claims from this text as a JSON array:
%s

Claims:`, text)
    
    // 调用LLM提取声明
    // 实际实现需要接入LLM API
    return []string{} // TODO: 接入真实LLM
}
```

### 2.3 Faithfulness 计算

```go
// rag_eval/faithfulness.go
package rag_eval

import "context"

// calcFaithfulness 计算忠实度
// 衡量答案中的声明是否都能在上下文中找到依据
func (e *Evaluator) calcFaithfulness(ctx context.Context, qac QueryAnswerContext) (float64, error) {
    // 1. 从答案提取声明
    answerClaims := extractClaims(qac.Answer)
    if len(answerClaims) == 0 {
        return 1.0, nil
    }
    
    // 2. 检查每个声明是否在context中有依据
    supported := 0
    for _, claim := range answerClaims {
        if e.isClaimSupported(ctx, qac.Context, claim) {
            supported++
        }
    }
    
    return float64(supported) / float64(len(answerClaims)), nil
}
```

---

## 三、批量评估

```go
// rag_eval/batch.go
package rag_eval

import (
    "context"
    "fmt"
    "math"
)

// BatchResult 批量评估结果
type BatchResult struct {
    Total       int                `json:"total"`
    AvgScores   map[string]float64 `json:"average"`
    Distribution map[string][]float64 `json:"distribution"`
}

// BatchEvaluate 批量评估
func (e *Evaluator) BatchEvaluate(ctx context.Context, datasets []QueryAnswerContext) (*BatchResult, error) {
    var scores struct {
        Recall, Prec, Rel, Faith float64
    }
    
    dist := make(map[string][]float64)
    
    for i, qac := range datasets {
        result, err := e.Evaluate(ctx, qac)
        if err != nil {
            fmt.Printf("Error at %d: %v\n", i, err)
            continue
        }
        
        scores.Recall += result.ContextRecall
        scores.Prec += result.ContextPrec
        scores.Rel += result.AnswerRel
        scores.Faith += result.Faithfulness
        
        dist["recall"] = append(dist["recall"], result.ContextRecall)
        dist["precision"] = append(dist["precision"], result.ContextPrec)
        
        if (i+1)%10 == 0 {
            fmt.Printf("Evaluated %d/%d\n", i+1, len(datasets))
        }
    }
    
    n := float64(len(datasets))
    avg := map[string]float64{
        "context_recall":   math.Round(scores.Recall/n*100) / 100,
        "context_precision": math.Round(scores.Prec/n*100) / 100,
        "answer_relevancy": math.Round(scores.Rel/n*100) / 100,
        "faithfulness":     math.Round(scores.Faith/n*100) / 100,
    }
    
    return &BatchResult{
        Total:       len(datasets),
        AvgScores:   avg,
        Distribution: dist,
    }, nil
}
```

---

## 四、传统 IR 指标

```go
// rag_eval/ir_metrics.go
package rag_eval

import "math"

// MRR 计算平均倒数排名
func CalculateMRR(ranks []int) float64 {
    if len(ranks) == 0 {
        return 0
    }
    sum := 0.0
    for _, r := range ranks {
        if r > 0 {
            sum += 1.0 / float64(r)
        }
    }
    return sum / float64(len(ranks))
}

// NDCG 计算归一化折损累计增益
func CalculateNDCG(rels []int, k int) float64 {
    if k > len(rels) {
        k = len(rels)
    }
    dcg := calcDCG(rels[:k])
    idcg := calcDCG(sortDesc(copySlice(rels))[:k])
    if idcg == 0 {
        return 0
    }
    return dcg / idcg
}

func calcDCG(rels []int) float64 {
    var dcg float64
    for i, r := range rels {
        dcg += float64(r) / math.Log2(float64(i+2))
    }
    return dcg
}

// Recall@K
func RecallAtK(relevant, retrieved []string, k int) float64 {
    ret := retrieved[:min(k, len(retrieved))]
    relSet := make(map[string]bool)
    for _, r := range relevant {
        relSet[r] = true
    }
    hits := 0
    for _, r := range ret {
        if relSet[r] {
            hits++
        }
    }
    if len(relevant) == 0 {
        return 0
    }
    return float64(hits) / float64(len(relevant))
}
```

---

## 五、评估指标对照表

| 指标 | 含义 | 计算方式 | 目标值 |
|------|------|---------|--------|
| Context Recall | 检索覆盖率 | 声明匹配率 | >0.8 |
| Context Precision | 检索精确率 | 相关片段占比 | >0.7 |
| Faithfulness | 答案忠实度 | 声明支持率 | >0.9 |
| Answer Relevancy | 答案相关性 | 语义相似度 | >0.8 |
| **RAGAS Score** | **综合得分** | **加权组合** | **>0.75** |

---

## 六、自测题

1. **Context Recall 和 Precision 的区别？**
   - Recall: 答案所需信息是否都被检索到
   - Precision: 检索到的内容是否都相关

2. **Faithfulness 为什么重要？**
   - 检测LLM幻觉，确保答案基于检索内容而非训练数据

3. **RAGAS 公式如何推导？**
   - 0.5 × recall × precision (检索质量) + 0.25 × relevancy + 0.25 × faithfulness (生成质量)

