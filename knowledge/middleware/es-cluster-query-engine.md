# Elasticsearch 集群/分片/查询引擎深度

> ES 集群架构（Master/Node）/ 分片策略 / 倒排索引 / 查询执行引擎 / Fielddata / 聚合 / 索引优化

---

## 第一部分：入门引导（5 分钟速览）

### Elasticsearch 为什么快？

1. **倒排索引**：从词到文档的映射，搜索 O(1)
2. **列式存储**：Fielddata 优化聚合查询
3. **分布式架构**：分片并行搜索
4. **Lucene 引擎**：成熟的搜索底层

### ES 集群架构

```
客户端 → Coordinator Node
         ├── Primary Shard 0 (Master)
         ├── Replica Shard 0 (Data Node 1)
         ├── Primary Shard 1 (Data Node 2)
         └── Replica Shard 1 (Data Node 3)
```

---

## 第二部分：倒排索引原理

### 2.1 倒排索引结构

```
Term Dictionary → Term Index → Postings List
"广告" → [doc1, doc3, doc5]
"竞价" → [doc2, doc4]
"点击" → [doc1, doc2, doc5]
```

### 2.2 Go 实现倒排索引

```go
package elasticsearch

import (
    "sort"
    "strings"
)

// InvertedIndex 倒排索引
type InvertedIndex struct {
    termDict   map[string][]int    // 词 → 文档 ID 列表
    docLengths map[int]int         // 文档长度（BM25 计算）
    docTerms   map[int]map[string]int // 文档 → 词频
}

// Analyzer 分词器
type Analyzer struct {
    stopwords map[string]bool
}

func (a *Analyzer) Analyze(text string) []string {
    // 简单分词：按空格和标点分割
    words := strings.FieldsFunc(text, func(r rune) bool {
        return r == ' ' || r == ',' || r == '.' || r == ';'
    })
    
    // 去除停用词
    result := make([]string, 0)
    for _, word := range words {
        if !a.stopwords[word] {
            result = append(result, word)
        }
    }
    
    return result
}

// Index 索引文档
func (ii *InvertedIndex) Index(docId int, text string, analyzer *Analyzer) {
    terms := analyzer.Analyze(text)
    termFreq := make(map[string]int)
    for _, term := range terms {
        termFreq[term]++
    }
    
    ii.docTerms[docId] = termFreq
    ii.docLengths[docId] = len(terms)
    
    for term, freq := range termFreq {
        ii.termDict[term] = append(ii.termDict[term], docId)
    }
}

// Search 搜索
func (ii *InvertedIndex) Search(query string, analyzer *Analyzer) []int {
    terms := analyzer.Analyze(query)
    
    // 获取每个词的 postings list
    postings := make([][]int, len(terms))
    for i, term := range terms {
        postings[i] = ii.termDict[term]
    }
    
    // 求交集（AND 查询）
    if len(postings) == 0 {
        return nil
    }
    
    result := postings[0]
    for i := 1; i < len(postings); i++ {
        result = ii.intersection(result, postings[i])
    }
    
    return result
}

func (ii *InvertedIndex) intersection(a, b []int) []int {
    result := make([]int, 0)
    i, j := 0, 0
    
    for i < len(a) && j < len(b) {
        if a[i] == b[j] {
            result = append(result, a[i])
            i++
            j++
        } else if a[i] < b[j] {
            i++
        } else {
            j++
        }
    }
    
    return result
}
```

### 2.3 BM25 评分

```go
func (ii *InvertedIndex) BM25Score(docId int, query []string, analyzer *Analyzer) float64 {
    k1 := 1.2  // 词频饱和参数
    b := 0.75  // 长度归一化参数
    avgDocLen := float64(ii.averageDocLength())
    
    score := 0.0
    docTerms := ii.docTerms[docId]
    docLen := ii.docLengths[docId]
    
    for _, term := range query {
        tf := float64(docTerms[term])
        df := float64(len(ii.termDict[term]))
        N := float64(len(ii.docLengths))
        
        // IDF 计算
        idf := math.Log((N - df + 0.5) / (df + 0.5) + 1)
        
        // TF 计算
        tfNorm := tf * (k1 + 1) / (tf + k1 * (1 - b + b * float64(docLen) / avgDocLen))
        
        score += idf * tfNorm
    }
    
    return score
}
```

---

## 第三部分：分片策略

### 3.1 分片分配

```go
type ShardAllocator struct {
    nodes     map[string]*Node
    shards    map[int]*Shard
    replicas  int
}

type Shard struct {
    shardId   int
    primary   string  // 主分片所在节点
    replicas  []string // 副本分片所在节点
    routing   string  // 路由键
}

func (sa *ShardAllocator) AllocateShard(shardId int, routing string) error {
    // 1. 计算目标节点
    targetNode := sa.getNodeByRouting(routing)
    
    // 2. 创建主分片
    sa.shards[shardId] = &Shard{
        shardId: shardId,
        primary: targetNode.ID,
    }
    
    // 3. 分配副本
    for i := 0; i < sa.replicas; i++ {
        replica := sa.getReplicaNode(targetNode.ID)
        sa.shards[shardId].replicas = append(sa.shards[shardId].replicas, replica.ID)
    }
    
    return nil
}

func (sa *ShardAllocator) getNodeByRouting(routing string) *Node {
    hash := crc32.ChecksumIEEE([]byte(routing))
    idx := int(hash % uint32(len(sa.nodes)))
    
    nodes := make([]*Node, 0)
    for _, node := range sa.nodes {
        nodes = append(nodes, node)
    }
    
    sort.Slice(nodes, func(i, j int) bool {
        return nodes[i].ID < nodes[j].ID
    })
    
    return nodes[idx]
}
```

### 3.2 分片路由

```go
func (sa *ShardAllocator) RouteDocument(docId string, index string) string {
    // _routing 字段决定分片
    routing := sa.getDocumentRouting(docId)
    
    // 计算分片 ID
    hash := crc32.ChecksumIEEE([]byte(routing))
    shardId := int(hash % uint32(sa.getNumberOfPrimaryShards(index)))
    
    shard := sa.shards[shardId]
    if shard == nil {
        return ""
    }
    
    return shard.primary
}
```

---

## 第四部分：查询执行引擎

### 4.1 查询解析

```go
type QueryParser struct {
    analyzer *Analyzer
}

type Query struct {
    Type     string          // match, term, range, bool
    Fields   map[string]FieldQuery
    Boost    float64
    Children []*Query
}

type FieldQuery struct {
    Term      string
    MinValue  interface{}
    MaxValue  interface{}
    Operator  string // AND, OR
}

func (qp *QueryParser) Parse(queryStr string) (*Query, error) {
    // 简单解析：match field:value
    parts := strings.Fields(queryStr)
    if len(parts) != 2 {
        return nil, fmt.Errorf("invalid query")
    }
    
    field := parts[0]
    value := parts[1]
    
    return &Query{
        Type: "match",
        Fields: map[string]FieldQuery{
            field: {Term: value},
        },
        Boost: 1.0,
    }, nil
}
```

### 4.2 查询执行

```go
type QueryEngine struct {
    index *InvertedIndex
    parser *QueryParser
}

func (qe *QueryEngine) Execute(queryStr string) ([]int, []float64) {
    query, err := qe.parser.Parse(queryStr)
    if err != nil {
        return nil, nil
    }
    
    // 执行查询
    docIds := qe.executeQuery(query)
    
    // 计算评分
    scores := make([]float64, len(docIds))
    for i, docId := range docIds {
        scores[i] = qe.index.BM25Score(docId, []string{queryStr}, qe.parser.analyzer)
    }
    
    // 按评分排序
    sortScores(docIds, scores)
    
    return docIds, scores
}

func (qe *QueryEngine) executeQuery(query *Query) []int {
    switch query.Type {
    case "match":
        return qe.matchQuery(query)
    case "term":
        return qe.termQuery(query)
    case "bool":
        return qe.boolQuery(query)
    default:
        return nil
    }
}

func (qe *QueryEngine) matchQuery(query *Query) []int {
    results := make([][]int, len(query.Fields))
    i := 0
    
    for field, fq := range query.Fields {
        postings := qe.index.termDict[fq.Term]
        results[i] = postings
        i++
    }
    
    // AND 查询
    if len(results) == 0 {
        return nil
    }
    
    result := results[0]
    for i := 1; i < len(results); i++ {
        result = qe.index.intersection(result, results[i])
    }
    
    return result
}
```

---

## 第五部分：聚合查询

### 5.1 Terms 聚合

```go
type AggregationEngine struct {
    index *InvertedIndex
}

type AggregationResult struct {
    Buckets []Bucket
    Total   int
}

type Bucket struct {
    Key    string
    Count  int
    DocIds []int
}

func (ae *AggregationEngine) TermsAggregation(field string, size int) *AggregationResult {
    // 按字段值分组
    buckets := make(map[string]*Bucket)
    
    for docId, termFreq := range ae.index.docTerms {
        for term, freq := range termFreq {
            if bucket, ok := buckets[term]; ok {
                bucket.Count += freq
                bucket.DocIds = append(bucket.DocIds, docId)
            } else {
                buckets[term] = &Bucket{
                    Key:    term,
                    Count:  freq,
                    DocIds: []int{docId},
                }
            }
        }
    }
    
    // 取 Top N
    sortedBuckets := make([]*Bucket, 0, len(buckets))
    for _, bucket := range buckets {
        sortedBuckets = append(sortedBuckets, bucket)
    }
    
    sort.Slice(sortedBuckets, func(i, j int) bool {
        return sortedBuckets[i].Count > sortedBuckets[j].Count
    })
    
    if len(sortedBuckets) > size {
        sortedBuckets = sortedBuckets[:size]
    }
    
    return &AggregationResult{
        Buckets: sortedBuckets,
        Total:   len(buckets),
    }
}
```

---

## 第六部分：自测题

### 问题 1
ES 倒排索引相比传统数据库 B+ 树有什么优势？

<details>
<summary>查看答案</summary>

1. **全文搜索**：倒排索引天然支持全文检索
2. **模糊匹配**：支持前缀、通配符搜索
3. **相关性评分**：BM25 评分排序
4. **B+ 树局限**：只适合精确匹配和范围查询
5. **ES 内部**：Lucene 的倒排索引 + B+ 树（DocValues）

</details>

### 问题 2
ES 分片过多或过少有什么影响？

<details>
<summary>查看答案</summary>

1. **分片过多**：
   - 每个分片占用内存
   - 集群元数据膨胀
   - 搜索时合并开销大
2. **分片过少**：
   - 无法水平扩展
   - 单节点压力大
   - 并行搜索能力弱
3. **最佳实践**：每个分片 10-50GB，总数不超过节点数 × 3
4. **动态调整**：ES 不支持减少分片数，只能重建索引

</details>

### 问题 3
ES 聚合查询为什么慢？如何优化？

<details>