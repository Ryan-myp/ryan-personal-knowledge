# Elasticsearch 深度：倒排索引/分片策略/查询优化

> 逐行解析倒排索引 + 分片策略 + 查询执行引擎 + 生产排障

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解倒排索引

```
传统数据库（MySQL）= 正排索引
┌──────────┬──────────┬──────────┐
│ 文档 ID  │ 内容      │ 标签      │
├──────────┼──────────┼──────────┤
│ 1        │ 苹果好吃  │ 水果      │
│ 2        │ 香蕉好吃  │ 水果      │
│ 3        │ 苹果手机  │ 电子产品  │
└──────────┴──────────┴──────────┘
查询"苹果"：扫描所有文档，找包含"苹果"的

搜索引擎（ES）= 倒排索引
┌──────────┬──────────┐
│ 词       │ 文档列表  │
├──────────┼──────────┤
│ 苹果     │ [1, 3]   │
│ 香蕉     │ [2]      │
│ 好吃     │ [1, 2]   │
│ 水果     │ [1, 2]   │
│ 电子     │ [3]      │
│ 产品     │ [3]      │
└──────────┴──────────┘
查询"苹果"：直接查倒排索引，返回 [1, 3]
```

**核心优势**：从 O(n) 降到 O(1)

---

## 第二部分：倒排索引深度解析

### 2.1 倒排索引结构

```
Term Dictionary（词词典）
┌─────────────────────────────────────────────────────┐
│ 苹果 → Term Index 位置 0x1A00, DocFreq=2            │
│ 香蕉 → Term Index 位置 0x1B00, DocFreq=1            │
│ 好吃 → Term Index 位置 0x1C00, DocFreq=2            │
│ 水果 → Term Index 位置 0x1D00, DocFreq=2            │
└─────────────────────────────────────────────────────┘
        ↓ (Bloom Filter 快速判断词是否存在)
        ↓ (Binary Search 二分查找定位词)

Term Index（词索引，内存中）
┌─────────────────────────────────────────────────────┐
│ 苹果 → Postings List 位置 0x2A00                     │
│ 香蕉 → Postings List 位置 0x2B00                     │
│ 好吃 → Postings List 位置 0x2C00                     │
└─────────────────────────────────────────────────────┘
        ↓

Postings List（ postings 列表）
┌─────────────────────────────────────────────────────┐
│ 苹果: [doc_id=1, freq=1, positions=[0,5]]           │
│          [doc_id=3, freq=1, positions=[0]]          │
│                                                     │
│ 香蕉: [doc_id=2, freq=1, positions=[0]]             │
│                                                     │
│ 好吃: [doc_id=1, freq=2, positions=[2,7]]           │
│          [doc_id=2, freq=1, positions=[2]]          │
└─────────────────────────────────────────────────────┘
```

### 2.2 Go 模拟倒排索引

```go
package elasticsearch

import (
    "bytes"
    "sort"
)

// InvertedIndex 倒排索引
type InvertedIndex struct {
    termDictionary map[string]*TermInfo      // 词 → 词信息
    termIndex      map[rune]*TermInfo      // 首字符 → 词信息（加速查找）
    postingsList   map[string]*PostingsList // 词 →  postings 列表
}

type TermInfo struct {
    Term      string   // 词
    DocFreq   int      // 文档频率（包含该词的文档数）
    Position  int64    // 在 Term Dictionary 中的位置
}

type PostingsList struct {
    Docs []*DocInfo
}

type DocInfo struct {
    DocID     int
    Freq      int      // 词频
    Positions []int    // 词位置
}

// AddDocument 添加文档到倒排索引
func (ii *InvertedIndex) AddDocument(docID int, text string) {
    // 1. 分词（简化：按空格分词）
    terms := ii.tokenize(text)
    
    // 2. 为每个词更新 postings 列表
    for pos, term := range terms {
        // 检查词是否在词典中
        if _, ok := ii.termDictionary[term]; !ok {
            ii.termDictionary[term] = &TermInfo{
                Term:     term,
                DocFreq:  0,
                Position: int64(len(ii.termDictionary)),
            }
        }
        
        termInfo := ii.termDictionary[term]
        termInfo.DocFreq++
        
        // 更新 postings 列表
        if _, ok := ii.postingsList[term]; !ok {
            ii.postingsList[term] = &PostingsList{
                Docs: make([]*DocInfo, 0),
            }
        }
        
        // 添加文档信息
        ii.postingsList[term].Docs = append(ii.postingsList[term].Docs, &DocInfo{
            DocID:     docID,
            Freq:      1,
            Positions: []int{pos},
        })
    }
}

// Search 搜索词
func (ii *InvertedIndex) Search(term string) []*DocInfo {
    postings, ok := ii.postingsList[term]
    if !ok {
        return nil
    }
    return postings.Docs
}

// tokenize 分词（简化版）
func (ii *InvertedIndex) tokenize(text string) []string {
    // 实际 ES 使用 Analyzer + Tokenizer
    // 这里简化为按空格分割
    return bytes.Split([]byte(text), []byte(" "))
}
```

### 2.3 Analyzer 分析器

```
Analyzer = Character Filter + Tokenizer + Token Filter

1. Character Filter: 去除 HTML 标签、替换特殊字符
2. Tokenizer: 分词（按空格、标点、正则表达式）
3. Token Filter: 小写转换、停用词过滤、同义词扩展

例如：
输入："Hello, World! 你好世界"
Character Filter: 去除标点 → "Hello World 你好世界"
Tokenizer: 分词 → ["Hello", "World", "你好", "世界"]
Token Filter: 小写 + 停用词 → ["hello", "world", "你好", "世界"]
```

```go
// Analyzer 分析器
type Analyzer interface {
    Analyze(text string) []Token
}

type StandardAnalyzer struct{}

type Token struct {
    Term       string
    StartOffset int
    EndOffset  int
    Position   int
}

func (a *StandardAnalyzer) Analyze(text string) []Token {
    tokens := make([]Token, 0)
    position := 0
    
    // 1. Character Filter: 去除特殊字符
    cleaned := a.removeSpecialChars(text)
    
    // 2. Tokenizer: 分词
    words := a.tokenize(cleaned)
    
    // 3. Token Filter: 小写转换
    for _, word := range words {
        tokens = append(tokens, Token{
            Term:        word,
            StartOffset: 0,
            EndOffset:   len(word),
            Position:    position,
        })
        position++
    }
    
    return tokens
}

func (a *StandardAnalyzer) removeSpecialChars(text string) string {
    // 简化实现
    return text
}

func (a *StandardAnalyzer) tokenize(text string) []string {
    // 简化实现：按空格分词
    return []string{text}
}
```

---

## 第三部分：分片和副本

### 3.1 分片策略

```
Shard 0: doc1, doc3, doc5, doc7
Shard 1: doc2, doc4, doc6, doc8

查询"doc5"：
1. 计算 doc5 的哈希值
2. hash("doc5") % num_shards = 0
3. 查询 Shard 0

为什么需要分片？
1. 单机容量有限（默认 50GB）
2. 并行查询更快
3. 高可用（副本在不同节点）
```

```go
// 分片分配算法
func ShardAllocation(docID string, numShards int) int {
    // 使用 murmur3 哈希
    hash := murmur3.Hash32([]byte(docID))
    return int(hash) % numShards
}

// 分片策略：
// 1. 默认：round-robin（轮询）
// 2. 自定义：按业务字段分片
// 3. 推荐：根据数据量和查询模式选择分片数
```

### 3.2 副本机制

```
Primary Shard 0 → Replica Shard 0 (Node A)
Primary Shard 1 → Replica Shard 1 (Node B)
Primary Shard 2 → Replica Shard 2 (Node C)

故障恢复：
Node A 挂了 → Replica Shard 0 提升为 Primary
Node B 恢复了 → 创建 Replica Shard 1

推荐配置：
- 每个分片至少 1 个副本（2 份数据）
- 副本分布在不同的节点上
- 副本数 = 节点数 - 1
```

---

## 第四部分：查询执行引擎

### 4.1 Boolean Query 执行流程

```
查询：{
    "bool": {
        "must": [{"match": {"title": "广告"}}],
        "filter": [{"term": {"status": "active"}}]
    }
}

执行流程：
1. Filter 阶段：
   - 查倒排索引，找到 status=active 的文档
   - 结果缓存（filter cache）
   
2. Must 阶段：
   - 对缓存结果，查 title=广告的倒排索引
   - 计算 TF-IDF 评分
   
3. 排序和分页
```

### 4.2 TF-IDF 评分

```
Score = TF × IDF × FieldNorm × Boost

TF (Term Frequency): 词在文档中出现的频率
IDF (Inverse Document Frequency): 词的稀有程度
FieldNorm: 字段长度的归一化
Boost: 手动提升系数

例如：
文档 1: "广告广告广告" → TF 高，IDF 低 → 评分高
文档 2: "广告" → TF 低，IDF 低 → 评分低
文档 3: "市场营销" → TF 低，IDF 高 → 评分低
```

```go
// TF-IDF 计算
func CalculateScore(doc *Document, query *Query) float64 {
    tf := ii.calculateTF(doc, query.Term)
    idf := ii.calculateIDF(query.Term)
    fieldNorm := ii.calculateFieldNorm(doc)
    boost := query.Boost
    
    return tf * idf * fieldNorm * boost
}

func (ii *InvertedIndex) calculateTF(doc *Document, term string) float64 {
    // TF = 词频 / 文档总词数
    count := doc.TermCounts[term]
    totalWords := len(doc.Words)
    return float64(count) / float64(totalWords)
}

func (ii *InvertedIndex) calculateIDF(term string) float64 {
    // IDF = log(总文档数 / 包含该词的文档数)
    totalDocs := ii.TotalDocuments()
    docFreq := ii.termDictionary[term].DocFreq
    return math.Log(float64(totalDocs) / float64(docFreq))
}
```

### 4.3 Fielddata 和 DocValues

```
Fielddata（用于聚合和排序）：
- 加载到堆内存
- 反向索引：doc_id → field_value
- 适合 keyword 类型
- 问题：内存占用大

DocValues（列式存储）：
- 存储在磁盘
- 正向索引：field_value → doc_ids
- 适合 text 类型
- 推荐：默认开启

区别：
- Fielddata：内存中，反向索引
- DocValues：磁盘中，正向索引
```

---

## 第五部分：生产排障案例

### 5.1 查询慢

```
现象：搜索接口响应时间从 50ms 变成 5s

排查：
1. 检查是否有全表扫描（type: ALL）
2. 检查是否有跨分片查询
3. 检查 fielddata 是否过大
4. 检查是否有深分页

解决方案：
1. 添加合适的索引
2. 使用 search_after 替代 from/size
3. 限制 fielddata 大小
4. 使用 filter 缓存
```

```json
// 深分页问题
// ❌ 错误：from=10000, size=10
{
    "query": { "match_all": {} },
    "from": 10000,
    "size": 10
}

// ✅ 正确：使用 search_after
{
    "query": { "match_all": {} },
    "size": 10,
    "search_after": [1234567890, "doc_id"]
}
```

### 5.2 内存溢出

```
现象：ES 节点 OOM

排查：
1. jmap -heap <pid> 查看堆内存使用
2. _cat/nodes?v&h=name,heap.percent,mem.percent
3. 检查 fielddata 大小

解决方案：
1. 限制 fielddata 大小：indices.fielddata.cache.size
2. 增加 JVM 堆内存（不超过 31GB）
3. 使用 doc_values 替代 fielddata
```

### 5.3 分片不平衡

```
现象：某些节点负载高，某些节点负载低

排查：
1. _cat/shards?v 查看分片分布
2. _cat/nodes?v 查看节点负载

解决方案：
1. 手动重新分配分片
2. 使用 reroute API
3. 调整分片策略
```

```json
// 手动重新分配分片
POST /_cluster/reroute
{
    "commands": [
        {
            "move": {
                "index": "my_index",
                "shard": 0,
                "from_node": "node1",
                "to_node": "node2"
            }
        }
    ]
}
```

---

## 第六部分：自测题

### 问题 1
倒排索引为什么比正排索引快？

<details>
<summary>查看答案</summary>

1. **O(1) 查找**：直接定位到 postings list
2. **不需要扫描全文**：只查需要的词
3. **Bloom Filter**：快速判断词是否存在
4. **Term Index**：内存中加速查找
5. **适用场景**：搜索、全文检索

</details>

### 问题 2
Fielddata 和 DocValues 有什么区别？

<details>
<summary>查看答案</summary>

1. **Fielddata**：内存中，反向索引
2. **DocValues**：磁盘中，正向索引
3. **Fielddata**：适合聚合和排序
4. **DocValues**：适合过滤和排序
5. **推荐**：使用 doc_values，限制 fielddata

</details>

### 问题 3
如何优化 ES 查询性能？

<details>
<summary>查看答案</summary>

1. **使用 filter 上下文**：不计算评分，可缓存
2. **限制分片数**：每个索引 5-10 个分片
3. **使用 search_after**：避免深分页
4. **合理设置 replica**：提高读取吞吐量
5. **监控 JVM 堆**：不超过 31GB

</details>

---

*本文档基于 Elasticsearch 源码和生产实战整理。*