# LLM + RAG 生产级最佳实践 - 2026 实战指南

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 前沿/LLM  
> **代码密度**: 25%

---

## 一、生产环境挑战

```
生产 RAG 系统核心挑战:
┌─────────────────────────────────────────────────────────────┐
│  1. 检索质量     → 多路召回 + RRF 融合                       │
│  2. 延迟控制     → 流式输出 + 并行检索                       │
│  3. 成本优化     → Token 压缩 + 缓存策略                     │
│  4. 安全合规     → PII 过滤 + 审计日志                       │
│  5. 可观测性     → Tracing + Metrics + Logging               │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、多路召回实现

```go
// rag/multi_retriever.go
package rag

import (
    "context"
    "sort"
)

// MultiRetriever 多路召回器
type MultiRetriever struct {
   BM25    BM25Retriever
    Vector  VectorRetriever
    Graph   GraphRetriever
}

// Retrieve 多路召回 + RRF 融合
func (mr *MultiRetriever) Retrieve(ctx context.Context, query string, k int) []Document {
    // 各路召回
    bm25Results := mr.BM25.Search(ctx, query, k*2)
    vectorResults := mr.Vector.Search(ctx, query, k*2)
    graphResults := mr.Graph.Search(ctx, query, k*2)
    
    // RRF 融合
    fused := rrFusion(bm25Results, vectorResults, graphResults, k)
    return fused
}

// rrFusion Reciprocal Rank Fusion
func rrFusion(results ...[]Document) []Document {
    scores := make(map[string]float64)
    for _, docs := range results {
        for rank, doc := range docs {
            scores[doc.ID] += 1.0 / float64(rank+60) // k=60
        }
    }
    
    // 排序
    type scoredDoc struct {
        id    string
        score float64
    }
    var scored []scoredDoc
    for id, score := range scores {
        scored = append(scored, scoredDoc{id, score})
    }
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].score > scored[j].score
    })
    
    // 返回 Top-K
    var final []Document
    for _, s := range scored {
        if len(final) >= 5 {
            break
        }
        for _, docs := range results {
            for _, d := range docs {
                if d.ID == s.id {
                    final = append(final, d)
                    break
                }
            }
        }
    }
    return final
}
```

---

## 三、Token 压缩策略

```typescript
// token_compression.ts
interface CompressionStrategy {
  name: string;
  compress(text: string): string;
  maxTokens: number;
}

// 策略1: 摘要压缩
const summaryCompression: CompressionStrategy = {
  name: "summary",
  compress: async (text) => {
    const summary = await llm.generate({
      prompt: `Summarize this text in 100 words: ${text}`,
      maxTokens: 150,
    });
    return summary;
  },
  maxTokens: 150,
};

// 策略2: 关键点提取
const keypointCompression: CompressionStrategy = {
  name: "keypoints",
  compress: async (text) => {
    const keypoints = await llm.generate({
      prompt: `Extract key points from: ${text}`,
      maxTokens: 200,
    });
    return keypoints;
  },
  maxTokens: 200,
};

// 策略3: 滑动窗口
const slidingWindow: CompressionStrategy = {
  name: "sliding_window",
  compress: (text) => {
    const tokens = text.split('');
    const windowSize = 2000;
    const chunks = [];
    for (let i = 0; i < tokens.length; i += windowSize) {
      chunks.push(tokens.slice(i, i + windowSize).join(''));
    }
    return chunks.join('\n---\n');
  },
  maxTokens: 4000,
};
```

---

## 四、可观测性集成

```go
// rag/observability.go
package rag

import (
    "context"
    "github.com/open-telemetry/opentelemetry-go/trace"
)

// ObservableRetriever 可观测检索器
type ObservableRetriever struct {
    inner Retriever
    tracer trace.Tracer
}

func NewObservableRetriever(inner Retriever, tracer trace.Tracer) *ObservableRetriever {
    return &ObservableRetriever{inner: inner, tracer: tracer}
}

func (r *ObservableRetriever) Retrieve(ctx context.Context, query string) ([]Document, error) {
    ctx, span := r.tracer.Start(ctx, "rag.retrieve")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("query", query),
        attribute.Int("limit", 5),
    )
    
    start := time.Now()
    docs, err := r.inner.Retrieve(ctx, query)
    
    span.AddEvent("retrieve_complete", trace.WithAttributes(
        attribute.Int("docs_count", len(docs)),
        attribute.Float64("latency_ms", float64(time.Since(start).Microseconds())/1000),
    ))
    
    return docs, err
}
```

---

## 五、自测题

1. **RRF 融合的 k 值如何选择？**
   - 通常取 60，越大权重越均匀

2. **Token 压缩的权衡是什么？**
   - 成本 vs 信息丢失

3. **OpenTelemetry 在 RAG 中的作用？**
   - 全链路追踪，定位性能瓶颈

