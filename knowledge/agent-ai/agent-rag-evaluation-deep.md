# Agent RAG 评估系统深度实现 - RAGAS五大指标

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/RAG评估  
> **代码密度**: 30%

---

## 一、RAGAS评估指标

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAGAS 五大评估指标                                │
│                                                                     │
│  1. Context Relevance (上下文相关性)                                 │
│  ─────────────────────────────                                      │
│  • 评估检索到的文档与问题的相关性                                    │
│  • 计算方法: 检索内容中包含多少有用信息                              │
│                                                                     │
│  2. Answer Semantic Similarity (答案语义相似度)                       │
│  ─────────────────────────────                                      │
│  • 评估生成答案与参考答案的语义相似度                                │
│  • 使用嵌入向量计算余弦相似度                                        │
│                                                                     │
│  3. Faithfulness (忠实度)                                            │
│  ─────────────────────────────                                      │
│  • 评估答案是否忠实于检索到的上下文                                  │
│  • 检测方法: 基于上下文能否推导出答案中的声明                        │
│                                                                     │
│  4. Context Recall (上下文召回率)                                     │
│  ─────────────────────────────                                      │
│  • 评估参考答案中有多少被检索到                                      │
│  • 计算方法: 检索内容覆盖参考答案的比例                              │
│                                                                     │
│  5. Answer Accuracy (答案准确性)                                      │
│  ─────────────────────────────                                      │
│  • 评估答案的事实准确性                                              │
│  • 需要ground truth或专家评分                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、实现代码

```go
// agent/rag_eval.go
package agent

import (
    "context"
)

// RAGASResult RAGAS评估结果
type RAGASResult struct {
    ContextRelevance float64
    AnswerSimilarity float64
    Faithfulness     float64
    ContextRecall    float64
    AnswerAccuracy   float64
    OverallScore     float64
}

// RAGASEvaluator RAG评估器
type RAGASEvaluator struct {
    llm        LLMClient
    embedding  EmbeddingClient
    groundTruth map[string]string
}

// Evaluate 执行评估
func (e *RAGASEvaluator) Evaluate(ctx context.Context, query string, 
    context []Document, answer string) (*RAGASResult, error) {
    
    result := &RAGASResult{}
    
    // 1. Context Relevance
    result.ContextRelevance = e.evalContextRelevance(ctx, query, context)
    
    // 2. Answer Similarity
    gt, ok := e.groundTruth[query]
    if ok {
        result.AnswerSimilarity = e.computeSimilarity(answer, gt)
    }
    
    // 3. Faithfulness
    result.Faithfulness = e.evalFaithfulness(ctx, context, answer)
    
    // 4. Context Recall
    if ok {
        result.ContextRecall = e.evalContextRecall(ctx, context, gt)
    }
    
    // 5. 综合评分
    result.OverallScore = result.calculateOverall()
    
    return result, nil
}

// calculateOverall 计算综合评分
func (r *RAGASResult) calculateOverall() float64 {
    return (r.ContextRelevance + r.AnswerSimilarity + 
            r.Faithfulness + r.ContextRecall) / 4
}
```

---

## 三、自测题

1. **为什么要用RAGAS评估？**
   - 传统指标不够，RAGAS专门针对RAG系统设计

2. **Faithfulness的重要性？**
   - 检测幻觉问题，确保答案忠实于上下文

