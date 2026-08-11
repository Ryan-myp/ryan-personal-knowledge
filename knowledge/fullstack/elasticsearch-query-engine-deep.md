# Elasticsearch 查询引擎深度解析

> 深入 ES 查询引擎：倒排索引、BM25算法、查询优化、分布式查询。
> 源码级分析 Lucene 核心。
> 适用对象：搜索工程师、数据工程师、后端架构师

---

## 1. 倒排索引

### 1.1 数据结构

```
正排索引 (Forward Index):
┌──────────┬──────────────────────────────────┐
│ Document │        Terms                     │
├──────────┼──────────────────────────────────┤
│ Doc 1    │ "the", "quick", "brown", ...    │
│ Doc 2    │ "the", "lazy", "dog", ...       │
│ Doc 3    │ "quick", "brown", "fox", ...    │
└──────────┴──────────────────────────────────┘

倒排索引 (Inverted Index):
┌──────────┬──────────────────────────────────┐
│   Term   │     Document IDs ( postings )   │
├──────────┼──────────────────────────────────┤
│ "the"    │ [1, 2]                         │
│ "quick"  │ [1, 3]                         │
│ "brown"  │ [1, 3]                         │
│ "lazy"   │ [2]                          │
│ "dog"    │ [2]                          │
│ "fox"    │ [3]                          │
└──────────┴──────────────────────────────────┘
```

### 1.2 倒排索引结构

```c
// Lucene Core (简化)

struct InvertedIndex {
    TermDictionary dictionary;  // 术语字典
    PostingsList postings;       //  postings列表
    FieldInfo fieldInfo;        // 字段信息
}

struct TermDictionary {
    // FST (Finite State Transducer)
    // 前缀树结构，支持前缀匹配
    Node root;
}

struct PostingsList {
    DocIdSet docIds;      // 文档ID集合
    TermFreq termFreq;    // 词频
    Position[] positions; // 位置信息
    Payload[] payloads;   // 负载数据
}
```

---

## 2. BM25 算法

### 2.1 公式推导

```
BM25(q, d) = Σ IDF(qi) * (f(qi, d) * (k1 + 1)) / (f(qi, d) + k1 * (1 - b + b * dl/avgdl))

其中：
- qi: 查询中的第i个词
- d: 文档
- f(qi, d): 词频
- dl: 文档长度
- avgdl: 平均文档长度
- k1: 词频饱和参数 (通常0.9-1.2)
- b: 长度归一化参数 (通常0.75)

IDF(qi) = log((N - n + 0.5) / (n + 0.5) + 1)
- N: 总文档数
- n: 包含qi的文档数
```

### 2.2 Go 实现

```go
// bm25.go

package search

import "math"

type BM25Params struct {
    K1 float64 // 词频饱和参数
    B  float64 // 长度归一化参数
}

type BM25 struct {
    params      BM25Params
    docFreq     map[string]int
    docLengths  []float64
    avgDocLen   float64
    totalDocs   int
}

func NewBM25(params BM25Params) *BM25 {
    return &BM25{
        params:  params,
        docFreq: make(map[string]int),
    }
}

func (b *BM25) AddDocument(docID int, terms []string, length float64) {
    b.docLengths = append(b.docLengths, length)
    b.totalDocs++
    
    for _, term := range terms {
        b.docFreq[term]++
    }
    
    b.updateAvgDocLen()
}

func (b *BM25) Score(docID int, query []string) float64 {
    score := 0.0
    
    for _, term := range query {
        idf := b.IDF(term)
        tf := b.TermFrequency(docID, term)
        dl := b.docLengths[docID]
        
        k1 := b.params.K1
        b := b.params.B
        
        numerator := tf * (k1 + 1)
        denominator := tf + k1*(1-b+b*dl/b.avgDocLen)
        
        score += idf * numerator / denominator
    }
    
    return score
}

func (b *BM25) IDF(term string) float64 {
    n := b.docFreq[term]
    N := float64(b.totalDocs)
    
    return math.Log((N - float64(n) + 0.5) / (float64(n) + 0.5) + 1)
}

func (b *BM25) TermFrequency(docID int, term string) float64 {
    // 简化实现，实际需要存储词频
    return 1.0
}

func (b *BM25) updateAvgDocLen() {
    if b.totalDocs == 0 {
        return
    }
    sum := 0.0
    for _, l := range b.docLengths {
        sum += l
    }
    b.avgDocLen = sum / float64(b.totalDocs)
}
```

---

## 3. 查询优化

### 3.1 查询类型

```
┌─────────────────────────────────────────────────────────────┐
│                    ES 查询类型                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  查询查询 (Query Context)                                    │
│  ├── 判断文档是否匹配                                         │
│  ├── 计算相关性分数                                           │
│  └── 常用：match, term, range, bool                          │
│                                                             │
│  过滤查询 (Filter Context)                                   │
│  ├── 只判断是否匹配，不计算分数                                 │
│  └── 可缓存，性能更好                                         │
│  └── 常用：term, range, exists                               │
│                                                             │
│  复合查询                                                    │
│  ├── bool (布尔组合)                                          │
│  ├── function_score (函数评分)                                │
│  └── constant_score (常量评分)                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 查询优化策略

```go
// query_optimizer.go

package search

import "time"

type QueryOptimizer struct {
    cache       *QueryCache
    timeout     time.Duration
    maxClauseCount int
}

func (o *QueryOptimizer) Optimize(query Query) Query {
    // 1. 查询转换
    query = o.convertToOptimalForm(query)
    
    // 2. 添加过滤器
    query = o.addFilters(query)
    
    // 3. 设置超时
    query.SetTimeout(o.timeout)
    
    // 4. 限制结果数
    query.SetMaxClauseCount(o.maxClauseCount)
    
    return query
}

func (o *QueryOptimizer) convertToOptimalForm(query Query) Query {
    // 将 term 查询转换为 filter context
    if q, ok := query.(TermQuery); ok {
        return FilterQuery{Inner: q}
    }
    return query
}
```

---

## 4. 分布式查询

### 4.1 查询执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                  分布式查询执行流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Query Phase (查询阶段)                                   │
│     ├── Coordinator 节点接收请求                             │
│     ├── 将查询广播到所有 shard                               │
│     └── 每个 shard 执行查询，返回 top-k 文档ID              │
│                                                             │
│  2. Fetch Phase (获取阶段)                                   │
│     ├── Coordinator 收集所有文档ID                           │
│     ├── 去重、排序                                          │
│     └── 向对应 shard 获取完整文档                           │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │ Coordinator │◄──►│   Shard 1   │◄──►│   Shard 2   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│        │                    │                    │          │
│        ▼                    ▼                    ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  Query      │    │  Query      │    │  Query      │    │
│  │  + Fetch    │    │  + Fetch    │    │  + Fetch    │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现

```go
// distributed_search.go

package search

import (
    "context"
    "sync"
)

type DistributedSearcher struct {
    shards   []Shard
    coordinator *Coordinator
}

type Shard interface {
    Search(ctx context.Context, query Query) (*SearchResult, error)
}

type Coordinator struct {
    results  chan *ShardResult
    timeout  time.Duration
}

type ShardResult struct {
    shardID  string
    result   *SearchResult
    err      error
}

func (s *DistributedSearcher) Search(ctx context.Context, query Query) (*SearchResult, error) {
    var wg sync.WaitGroup
    results := make([]*ShardResult, len(s.shards))
    
    for i, shard := range s.shards {
        wg.Add(1)
        go func(idx int, s Shard) {
            defer wg.Done()
            
            result, err := s.Search(ctx, query)
            results[idx] = &ShardResult{
                shardID: s.ID(),
                result:  result,
                err:     err,
            }
        }(i, shard)
    }
    
    // 等待所有分片完成
    done := make(chan struct{})
    go func() {
        wg.Wait()
        close(done)
    }()
    
    select {
    case <-done:
        // 合并结果
        return s.mergeResults(results), nil
    case <-time.After(s.coordinator.timeout):
        return nil, ErrTimeout
    }
}

func (s *DistributedSearcher) mergeResults(results []*ShardResult) *SearchResult {
    // 合并、排序、去重
    // ...
    return &SearchResult{}
}
```

---

## 5. 性能调优

### 5.1 索引优化

```json
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s",
    "translog": {
      "durability": "async",
      "sync_interval": "5s"
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_max_word",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "content": {
        "type": "text",
        "analyzer": "ik_smart"
      },
      "timestamp": {
        "type": "date"
      }
    }
  }
}
```

### 5.2 查询优化

```json
// 使用 filter context
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"status": "active"}},
        {"range": {"timestamp": {"gte": "now-7d"}}}
      ],
      "must": [
        {"match": {"title": "广告系统"}}
      ]
    }
  },
  "size": 20,
  "timeout": "5s"
}
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 慢查询 | 响应时间长 | `_slowlog` | 优化查询/索引 |
| 内存溢出 | 节点宕机 | JVM监控 | 增加堆内存 |
| 写入瓶颈 | 写入延迟 | `_nodes/stats` | 调整 refresh_interval |
| 分片不均衡 | 热点分片 | `_cat/shards` | 重新分片 |

### 6.2 监控指标

```go
// metrics.go

package search

import "github.com/prometheus/client_golang/prometheus"

type ESMetrics struct {
    queryLatency    prometheus.Histogram
    queryTotal      prometheus.Counter
    indexLatency    prometheus.Histogram
    indexTotal      prometheus.Counter
    shardFailures   prometheus.Counter
    heapUsage       prometheus.Gauge
}

func NewESMetrics() *ESMetrics {
    return &ESMetrics{
        queryLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name: "es_query_latency_seconds",
            Help: "Query latency",
            Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 5.0},
        }),
        queryTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "es_queries_total",
            Help: "Total queries",
        }),
        // ...
    }
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 倒排索引 | FST + Postings |
| 评分算法 | BM25 |
| 分布式查询 | Query + Fetch 两阶段 |
| 性能优化 | Filter缓存/索引调优 |

### 7.2 最佳实践

- [ ] 合理使用 filter context
- [ ] 优化索引映射
- [ ] 监控 JVM 内存
- [ ] 调整分片数量
- [ ] 定期优化索引

---

*最后更新：2026-08-11*
*作者：Ryan*
