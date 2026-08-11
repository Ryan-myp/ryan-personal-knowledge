# 搜索引擎架构深度解析

> 深入搜索引擎核心：倒排索引、检索算法、排序模型、分布式架构。
> 源码级分析，包含生产环境优化。
> 适用对象：搜索工程师、数据工程师、后端架构师

---

## 1. 倒排索引

### 1.1 数据结构

```
倒排索引结构：

正排索引 (Forward Index):
┌──────────┬─────────────────────────────────────┐
│ DocID    │ Content                              │
├──────────┼─────────────────────────────────────┤
│ 1        │ "Go programming language"           │
│ 2        │ "Python programming language"       │
│ 3        │ "Java programming language"           │
└──────────┴─────────────────────────────────────┘

倒排索引 (Inverted Index):
┌──────────────────┬─────────────────────────────┐
│ Term             │ Posting List                  │
├──────────────────┼─────────────────────────────┤
│ Go               │ [1]                           │
│ Python           │ [2]                           │
│ Java             │ [3]                           │
│ programming      │ [1, 2, 3]                     │
│ language         │ [1, 2, 3]                     │
└──────────────────┴─────────────────────────────┘
```

### 1.2 Go 实现

```go
// inverted_index.go

package search

import (
    "sort"
    "strings"
)

type PostingList struct {
    DocIDs  []int
    TF      []int
    Positions [][]int
}

type InvertedIndex struct {
    terms map[string]*PostingList
}

func (idx *InvertedIndex) AddDocument(docID int, content string) {
    terms := idx.tokenize(content)
    for _, term := range terms {
        if idx.terms[term] == nil {
            idx.terms[term] = &PostingList{}
        }
        pl := idx.terms[term]
        pl.DocIDs = append(pl.DocIDs, docID)
        pl.TF = append(pl.TF, 1)
        pl.Positions = append(pl.Positions, []int{len(pl.DocIDs) - 1})
    }
}

func (idx *InvertedIndex) tokenize(text string) []string {
    text = strings.ToLower(text)
    words := strings.Fields(text)
    return words
}
```

---

## 2. 检索算法

### 2.1 BM25 算法

```
BM25 (Best Matching 25) 算法：

BM25(doc, query) = Σ IDF(qi) * (f(qi, doc) * (k1 + 1)) / (f(qi, doc) + k1 * (1 - b + b * dl/avgdl))

参数：
- k1: 词频饱和参数 (通常 1.2-2.0)
- b: 长度归一化参数 (通常 0.75)
- IDF: 逆文档频率
- f: 词频
- dl: 文档长度
- avgdl: 平均文档长度
```

### 2.2 Go 实现

```go
// bm25.go

package search

import "math"

type BM25 struct {
    k1 float64
    b  float64
    avgdl float64
    n int // 总文档数
}

func (bm *BM25) Score(doc *Document, query []string) float64 {
    score := 0.0
    for _, term := range query {
        tf := doc.TermFreq(term)
        if tf == 0 {
            continue
        }
        df := bm.DocFreq(term)
        idf := math.Log(1.0 + float64(bm.n-df+0.5)/float64(df+0.5))
        dl := float64(len(doc.Content))
        num := tf * (bm.k1 + 1)
        den := tf + bm.k1 * (1 - bm.b + bm.b * dl/bm.avgdl)
        score += idf * num / den
    }
    return score
}
```

---

## 3. 排序模型

### 3.1 学习排序 (LTR)

```
学习排序模型：

1. 手工特征
   ├── TF-IDF
   ├── BM25
   └── 页面特征

2. 机器学习
   ├── RankNet
   ├── LambdaRank
   └── LambdaMART

3. 深度学习
   ├── DSSM (Deep Structured Semantic Model)
   ├── DIEN (Deep Interest Evolution Network)
   └── Transformer-based
```

### 3.2 Go 实现排序

```go
// ranking.go

package search

import (
    "sort"
)

type SearchResult struct {
    DocID   int
    Score   float64
    Content string
}

func (bm *BM25) Search(query string, topN int) []*SearchResult {
    terms := bm.tokenize(query)
    results := make([]*SearchResult, 0)
    
    for docID, doc := range bm.docs {
        score := bm.Score(doc, terms)
        if score > 0 {
            results = append(results, &SearchResult{
                DocID:   docID,
                Score:   score,
                Content: doc.Content,
            })
        }
    }
    
    sort.Slice(results, func(i, j int) bool {
        return results[i].Score > results[j].Score
    })
    
    if len(results) > topN {
        results = results[:topN]
    }
    
    return results
}
```

---

## 4. 分布式架构

### 4.1 分片架构

```
分布式搜索引擎架构：

┌─────────────────────────────────────────────────────────────┐
│                  分布式搜索引擎                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  查询层 (Query Layer)                                        │
│  ├── 查询解析                                                │
│  ├── 路由分发                                                │
│  └── 结果合并                                                │
│                                                             │
│  索引层 (Index Layer)                                        │
│  ├── Shard 1 (分片1)                                        │
│  │   ├── Segment 1                                          │
│  │   ├── Segment 2                                          │
│  │   └── Segment 3                                          │
│  ├── Shard 2 (分片2)                                        │
│  └── Shard 3 (分片3)                                        │
│                                                             │
│  副本层 (Replica Layer)                                      │
│  ├── Leader 副本 (读写)                                      │
│  └── Follower 副本 (只读)                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现分布式搜索

```go
// distributed_search.go

package search

import (
    "context"
    "sync"
)

type DistributedSearch struct {
    shards []*Shard
    mu     sync.RWMutex
}

type Shard struct {
    ID      int
    Nodes   []*Node
    leader  *Node
}

type Node struct {
    Address string
    client  *HTTPClient
}

func (ds *DistributedSearch) Search(ctx context.Context, query string) ([]*SearchResult, error) {
    var wg sync.WaitGroup
    results := make([][]*SearchResult, len(ds.shards))
    errors := make([]error, len(ds.shards))
    
    for i, shard := range ds.shards {
        wg.Add(1)
        go func(idx int, s *Shard) {
            defer wg.Done()
            results[idx], errors[idx] = s.Search(ctx, query)
        }(i, shard)
    }
    
    wg.Wait()
    
    // 合并结果
    allResults := make([]*SearchResult, 0)
    for _, r := range results {
        allResults = append(allResults, r...)
    }
    
    // 排序去重
    return ds.mergeAndSort(allResults), nil
}
```

---

## 5. 性能优化

### 5.1 索引优化

```
索引优化策略：

1. 段合并 (Segment Merge)
   ├── 定期合并小段
   ├── 减少打开文件数
   └── 提升查询性能

2. 缓存优化
   ├── 查询结果缓存
   ├── 倒排索引缓存
   └── 统计信息缓存

3. 过滤优化
   ├── 前置过滤
   └── 谓词下推
```

### 5.2 查询优化

```
查询优化策略：

1. 查询计划优化
   ├── 谓词下推
   ├── 常量折叠
   └── 子查询展开

2. 并行查询
   ├── 分片并行
   └── 段并行

3. 结果缓存
   ├── 查询结果缓存
   └── 中间结果缓存
```

---

## 6. 监控告警

### 6.1 关键指标

```
搜索系统监控指标：

1. 查询性能
   ├── QPS
   ├── P99 延迟
   └── 错误率

2. 索引健康
   ├── 索引大小
   ├── 段数量
   └── 合并频率

3. 资源使用
   ├── CPU 使用率
   ├── 内存使用
   └── 磁盘 I/O
```

### 6.2 告警规则

```
告警规则配置：

1. 延迟告警
   ├── P99 > 100ms (Warning)
   └── P99 > 500ms (Critical)

2. 错误率告警
   ├── 错误率 > 1% (Warning)
   └── 错误率 > 5% (Critical)

3. 资源告警
   ├── CPU > 80% (Warning)
   ├── 内存 > 90% (Critical)
   └── 磁盘 > 85% (Warning)
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 索引 | 倒排索引 +  postings list |
| 检索 | BM25 + 向量检索 |
| 排序 | 学习排序 (LTR) |
| 分布式 | 分片 + 副本 |

### 7.2 最佳实践

- [ ] 合理设计分片策略
- [ ] 优化索引结构
- [ ] 实施查询缓存
- [ ] 建立监控告警
- [ ] 定期性能测试

---

*最后更新：2026-08-11*
*作者：Ryan*
