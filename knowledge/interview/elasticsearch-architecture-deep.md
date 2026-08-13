# ES架构深度 - 资深专家深度实现

## 一、ES核心架构

### 1.1 集群架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Elasticsearch集群架构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                          ┌─────────────┐                                │
│                          │  Master     │ 管理集群状态                    │
│                          │  Node       │                                 │
│                          └──────┬──────┘                                │
│                                 │                                      │
│              ┌──────────────────┼──────────────────┐                    │
│              │                  │                  │                    │
│        ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐            │
│        │ Data Node │      │ Data Node │      │ Data Node │            │
│        │  索引分片  │      │  索引分片  │      │  索引分片  │            │
│        └───────────┘      └───────────┘      └───────────┘            │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心概念

```go
// 核心数据结构
type Index struct {
    Name       string
    Shards     int           // 主分片数
    Replicas   int           // 副本数
    Segments   []*Segment    // 段文件
    Mapping    Mapping       // 映射定义
    Settings   Settings      // 索引设置
}

type Segment struct {
    ID          string
    DocsCount   int64
    MemorySize  int64
    Fields      []Field
}

type ShardingStrategy interface {
    Route(docID string, totalShards int) int
}
```

## 二、分片机制实现

### 2.1 分片分配算法

```java
// Elasticsearch分片分配
public class ShardAllocationStrategy {
    
    // 基于文档ID的哈希路由
    public int allocate(String docId, int numShards) {
        // SHA-256哈希
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] hash = md.digest(docId.getBytes(StandardCharsets.UTF_8));
        
        // 转换为正整数
        int hashInt = ByteBuffer.wrap(hash).getInt(0);
        return Math.abs(hashInt) % numShards;
    }
    
    // 均衡分配算法
    public List<ShardAllocation> balance(List<Node> nodes, List<Shard> shards) {
        // 最小化移动原则
        Map<Node, Integer> nodeLoad = new HashMap<>();
        
        for (Shard shard : shards) {
            Node bestNode = findBestNode(nodes, nodeLoad, shard);
            nodeLoad.merge(bestNode, 1, Integer::sum);
        }
        
        return constructAllocations(nodeLoad);
    }
    
    private Node findBestNode(List<Node> nodes, Map<Node, Integer> currentLoad, Shard shard) {
        return nodes.stream()
            .min(Comparator.comparingInt(n -> 
                currentLoad.getOrDefault(n, 0) + estimateCost(n, shard)
            )).orElse(nodes.get(0));
    }
}
```

### 2.2 副本同步机制

```go
type ReplicaSync struct {
    Primary    *Shard
    Replicas   []*Shard
    SyncState  SyncState
}

type SyncState int

const (
    Synced SyncState = iota
    Syncing
    Stale
)

// 乐观锁版本控制
type VersionControl struct {
    Version     int64
    SeqNo       int64
    PrimaryTerm int64
}

func (r *ReplicaSync) sync(doc *Document) error {
    // 1. 主分片写入
    primarySeqNo, err := r.Primary.write(doc)
    if err != nil {
        return err
    }
    
    // 2. 异步复制到副本
    go func() {
        for _, replica := range r.Replicas {
            replica.write(doc, primarySeqNo)
        }
    }()
    
    return nil
}
```

## 三、倒排索引实现

### 3.1 FST（有限状态转换器）

```go
// Lucene FST实现
type FST struct {
    root *Node
    data []byte
}

type Node struct {
    label      string
    output     []byte
    children   map[string]*Node
    isTerminal bool
}

func (f *FST) addTerm(term string, output []byte) {
    node := f.root
    for _, ch := range term {
        if node.children[string(ch)] == nil {
            node.children[string(ch)] = &Node{}
        }
        node = node.children[string(ch)]
    }
    node.isTerminal = true
    node.output = output
}

func (f *FST) lookup(term string) ([]byte, bool) {
    node := f.root
    for _, ch := range term {
        child, ok := node.children[string(ch)]
        if !ok {
            return nil, false
        }
        node = child
    }
    return node.output, node.isTerminal
}
```

### 3.2 Postings List

```go
type PostingsList struct {
    Term       string
    DocIDs     []int64
    Positions  [][]int      // 词位置
    Norms      []byte       // 归一化因子
}

type TermDictionary struct {
    fst *FST
    postings map[string]*PostingsList
}

func (td *TermDictionary) search(term string) *PostingsList {
    output, found := td.fst.lookup(term)
    if !found {
        return nil
    }
    return td.postings[term]
}

// Boolean Query执行
func (td *TermDictionary) booleanQuery(queries []Query) []*Document {
    results := make([][]int64, len(queries))
    
    for i, q := range queries {
        results[i] = td.search(q.Term).DocIDs
    }
    
    // AND操作
    return intersect(results)
}
```

## 四、查询执行引擎

### 4.1 Query Parser

```go
type QueryParser struct {
    analyzer *Analyzer
    mapper   *FieldMapper
}

func (p *QueryParser) parse(queryString string) Query {
    // 解析查询字符串
    tokens := p.analyzer.Analyze(queryString)
    
    // 构建查询树
    var query Query
    switch tokens[0].Type {
    case TERM:
        query = &TermQuery{
            Field: tokens[0].Value,
            Value: tokens[1].Value,
        }
    case MATCH:
        query = &MatchQuery{
            Field: tokens[0].Value,
            Query: tokens[1].Value,
        }
    case RANGE:
        query = &RangeQuery{
            Field: tokens[0].Value,
            Gte:   tokens[1].Value,
            Lte:   tokens[2].Value,
        }
    }
    
    return query
}
```

### 4.2 Scoring Algorithm

```go
// TF-IDF + BM25评分
type Scorer struct {
    fieldStats map[string]FieldStatistics
}

type FieldStatistics struct {
    DocCount       int64
    TermFreq       int64
    AvgFieldLength float64
}

func (s *Scorer) score(doc *Document, query *Query) float64 {
    termFreq := doc.getFieldFreq(query.Field, query.Term)
    df := s.fieldStats[query.Field].DocCount
    
    idf := math.Log(1 + (float64(s.totalDocs-df+0.5)/(df+0.5)))
    
    // BM25公式
    k1 := 1.5
    b := 0.75
    fieldLength := doc.getFieldLength(query.Field)
    avgFieldLength := s.fieldStats[query.Field].AvgFieldLength
    
    tf := termFreq * (k1 + 1)
    tfNorm := tf / (termFreq + k1*(1-b+b*fieldLength/avgFieldLength))
    
    return idf * tfNorm
}
```

## 五、性能优化策略

### 5.1 索引优化

```yaml
# 索引settings优化
index:
  number_of_shards: 5        # 根据数据量调整
  number_of_replicas: 1      # 生产环境建议1
  refresh_interval: "30s"    # 降低刷新频率
  codec: "best_compression"  # 压缩优化
  
  analysis:
    analyzer:
      my_analyzer:
        type: custom
        tokenizer: standard
        filter: [lowercase, stemmer, stop]
```

### 5.2 查询优化

```go
// 查询缓存
type QueryCache struct {
    cache *lru.Cache
    stats *QueryStats
}

func (c *QueryCache) execute(query Query) (*SearchResponse, error) {
    key := hash(query)
    
    // 尝试从缓存获取
    if result, ok := c.cache.Get(key); ok {
        c.stats.cacheHits++
        return result.(*SearchResponse), nil
    }
    
    // 执行查询并缓存
    result, err := c.executeQuery(query)
    if err != nil {
        return nil, err
    }
    
    c.cache.Add(key, result)
    c.stats.cacheMisses++
    
    return result, nil
}
```

### 5.3 内存管理

```go
type MemoryManager struct {
    heapSize     int64
    usedMemory   int64
    segmentCount int
}

func (m *MemoryManager) canMerge() bool {
    // 段合并条件
    return m.segmentCount > 30 || m.usedMemory > m.heapSize*0.5
}

func (m *MemoryManager) flush() {
    // 强制刷盘
    for _, index := range m.indices {
        index.flush()
    }
}
```

## 六、面试高频题

### Q1: ES为什么这么快？

```
A:
1. 倒排索引：O(1)查找
2. FST压缩：高效存储
3. 并行执行：多分片并发
4. 缓存机制：查询缓存+字段缓存
5. 段合并：优化读取性能
```

### Q2: 分片数如何设置？

```
A:
1. 原则：单分片10-50GB
2. 计算公式：数据量/30GB
3. 注意：分片有内存开销
4. 建议：预分配，不要动态扩容
```

### Q3: 如何避免ES热点？

```
A:
1. 合理选择routing key
2. 均匀分布数据
3. 使用本地预热
4. 监控 shard 分布
```

## 七、自测题

1. 解释倒排索引原理
2. 分片分配算法是什么？
3. 如何优化ES查询性能？

---

## 参考文档

- [Elasticsearch官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Lucene源码分析](https://github.com/apache/lucene)
