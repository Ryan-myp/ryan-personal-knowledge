# Elasticsearch 搜索引擎深度解析

> 深入 Elasticsearch 核心：倒排索引、查询引擎、聚合分析、性能优化。
> 源码级分析，包含生产环境优化案例。
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

### 1.2 Lucene 实现

```go
// 简化版倒排索引
package elasticsearch

import (
    "sort"
    "strings"
)

type PostingsList struct {
    DocIDs  []int
    TF      []int  // Term Frequency
    Positions [][]int // 词项位置
}

type InvertedIndex struct {
    terms map[string]*PostingsList
}

func (idx *InvertedIndex) AddDocument(docID int, content string) {
    terms := tokenize(content)
    for _, term := range terms {
        if idx.terms[term] == nil {
            idx.terms[term] = &PostingsList{}
        }
        idx.terms[term].DocIDs = append(idx.terms[term].DocIDs, docID)
    }
}

func tokenize(text string) []string {
    // 分词逻辑
    words := strings.Fields(text)
    return words
}
```

---

## 2. 查询引擎

### 2.1 查询类型

```
查询类型：

1. Leaf Queries
   ├── match: 匹配查询
   ├── term: 精确匹配
   ├── range: 范围查询
   └── wildcard: 通配符查询

2. Compound Queries
   ├── bool: 布尔组合
   ├── dis_max: 不相关最大
   ├── constant_score: 常量评分
   └── function_score: 函数评分
```

### 2.2 Go 实现查询

```go
// query.go

package elasticsearch

type Query interface {
    Score(docID int) float64
    Execute() []int
}

type MatchQuery struct {
    Field  string
    Value  string
}

func (q *MatchQuery) Score(docID int) float64 {
    // BM25 评分
    tf := q.getTF(docID)
    df := q.getDF()
    N := q.getTotalDocs()
    
    idf := math.Log(1 + (N-df+0.5)/(df+0.5))
    k1 := 1.5
    b := 0.75
    avgDL := q.getAvgDL()
    dl := q.getDL(docID)
    
    tfNorm := tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl/avgDL))
    return idf * tfNorm
}

type BoolQuery struct {
    Must    []Query
    Filter  []Query
    Should  []Query
    MustNot []Query
}

func (q *BoolQuery) Score(docID int) float64 {
    score := 0.0
    for _, must := range q.Must {
        score += must.Score(docID)
    }
    for _, should := range q.Should {
        score += should.Score(docID)
    }
    return score
}
```

---

## 3. 聚合分析

### 3.1 聚合类型

```
聚合类型：

1. Metrics Aggregations
   ├── avg: 平均值
   ├── sum: 求和
   ├── min: 最小值
   ├── max: 最大值
   └── stats: 统计信息

2. Bucket Aggregations
   ├── terms: 按值分桶
   ├── date_histogram: 时间直方图
   ├── range: 范围分桶
   └── geo_distance: 距离分桶

3. Pipeline Aggregations
   ├── avg_bucket: 桶平均值
   ├── sum_bucket: 桶求和
   └── derivative: 导数
```

### 3.2 Go 实现聚合

```go
// aggregation.go

package elasticsearch

type Aggregation interface {
    Execute(docs []Document) AggregationResult
}

type TermsAggregation struct {
    Field  string
    Size   int
}

func (agg *TermsAggregation) Execute(docs []Document) AggregationResult {
    buckets := make(map[string]*Bucket)
    
    for _, doc := range docs {
        value := doc.Fields[agg.Field]
        key := fmt.Sprintf("%v", value)
        
        if buckets[key] == nil {
            buckets[key] = &Bucket{Key: key, DocCount: 0}
        }
        buckets[key].DocCount++
    }
    
    // 排序并取前N个
    sorted := make([]*Bucket, 0, len(buckets))
    for _, b := range buckets {
        sorted = append(sorted, b)
    }
    sort.Slice(sorted, func(i, j int) bool {
        return sorted[i].DocCount > sorted[j].DocCount
    })
    
    if len(sorted) > agg.Size {
        sorted = sorted[:agg.Size]
    }
    
    return AggregationResult{Buckets: sorted}
}
```

---

## 4. 性能优化

### 4.1 索引优化

```
索引优化策略：

1. 分片策略
   ├── 根据数据量设置分片数
   └── 避免过多/过少分片

2. 映射设计
   ├── 合理设置字段类型
   ├── 禁用不需要的字段
   └── 使用 keyword 子字段

3. 写入优化
   ├── 批量写入
   ├── 调整 refresh_interval
   └── 使用 bulk API
```

### 4.2 查询优化

```
查询优化策略：

1. 使用 filter context
   └── 不参与评分，可缓存

2. 避免深度分页
   └── 使用 search_after

3. 优化排序
   └── 避免多字段排序

4. 合理使用采样
   └── search_type=count
```

---

## 5. 生产优化

### 5.1 JVM 调优

```
JVM 调优参数：

-Xms4g -Xmx4g                    # 堆内存
-XX:+UseG1GC                       # 使用 G1 收集器
-XX:G1HeapRegionSize=4m            # Region 大小
-XX:InitiatingHeapOccupancyPercent=35  # 并发标记阈值
```

### 5.2 系统调优

```
系统调优：

1. 文件描述符
   ulimit -n 65536

2. 内存锁定
   vim /etc/security/limits.conf
   * soft memlock unlimited
   * hard memlock unlimited

3. 虚拟内存
   sysctl -w vm.swappiness=1
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 索引 | 倒排索引 + Lucene |
| 查询 | 查询树 + 评分 |
| 聚合 | 分桶 + 计算 |
| 优化 | 分片 + 调优 |

### 6.2 最佳实践

- [ ] 合理设计索引映射
- [ ] 使用 filter context
- [ ] 监控集群健康
- [ ] 定期优化索引
- [ ] 备份重要数据

---

*最后更新：2026-08-11*
*作者：Ryan*
