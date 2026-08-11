# Elasticsearch 深度解析

> 本文档深入解析 Elasticsearch 的核心架构、倒排索引、查询执行、分片策略和性能优化。
> 适用对象：搜索工程师、后端工程师、大数据工程师

---

## 1. ES 架构概览

### 1.1 核心概念

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Elasticsearch 架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Cluster                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  Node 1     │  │  Node 2     │  │  Node 3     │         │   │
│  │  │  (Master)   │  │  (Data)     │  │  (Data)     │         │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │   │
│  │         │                │                │                 │   │
│  │         └────────────────┼────────────────┘                 │   │
│  │                          │                                  │   │
│  │              ┌───────────▼───────────┐                     │   │
│  │              │      Shards           │                     │   │
│  │              │  Primary + Replica    │                     │   │
│  │              └───────────────────────┘                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                    ┌────────▼────────┐                             │
│                    │     Index       │ 逻辑分层                      │
│                    └────────┬────────┘                             │
│                             │                                       │
│                    ┌────────▼────────┐                             │
│                    │     Type        │ 已废弃 (7.x+)                │
│                    └────────┬────────┘                             │
│                             │                                       │
│                    ┌────────▼────────┐                             │
│                    │     Document    │ 基本数据单元                  │
│                    └─────────────────┘                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心术语

| 术语 | 说明 |
|------|------|
| **Cluster** | 多个 Node 组成的集群 |
| **Node** | 集群中的单个服务器 |
| **Index** | 索引，逻辑上的数据集合 |
| **Shard** | 分片，Index 的物理拆分 |
| **Replica** | 副本，Shard 的备份 |
| **Document** | 文档，JSON 格式的数据 |
| **Mapping** | 映射，定义字段类型 |
| **Analyzer** | 分词器，文本处理 |

---

## 2. 倒排索引原理

### 2.1 正排索引 vs 倒排索引

```
正排索引（MySQL）：
┌──────────┬────────────────────────────────────┐
│  doc_id  │           content                  │
├──────────┼────────────────────────────────────┤
│    1     │ "Elasticsearch is fast"            │
│    2     │ "Fast and distributed"             │
│    3     │ "Search engine"                    │
└──────────┴────────────────────────────────────┘

倒排索引（ES）：
┌──────────┬────────────────────────────────────┐
│  term    │        doc_ids ( postings )        │
├──────────┼────────────────────────────────────┤
│ elasticsearch │ [1]                           │
│ fast     │ [1, 2]                            │
│ distributed │ [2]                           │
│ search   │ [3]                             │
│ engine   │ [3]                             │
└──────────┴────────────────────────────────────┘
```

### 2.2 FST（有限状态转换器）

ES 使用 FST 压缩倒排索引，将 term 字典压缩为有向无环图：

```go
// FST 结构（简化）
type FST struct {
    nodes    []*Node      // 节点列表
    arcs     []*Arc       // 边
    input    []rune       // 输入字符
    output   []int64      // 输出（doc_id 列表）
}

type Node struct {
    id       int
    transitions map[rune]*Node  // 字符到节点的映射
    output    *Output         // 输出数据
}

type Arc struct {
    input  rune      // 输入字符
    target int       // 目标节点 ID
    weight int64     // 输出权重
}
```

### 2.3 Postings List 压缩

```
原始 postings list: [1, 5, 8, 12, 15, 23, 45, 67]

压缩方式 1: Gap Encoding
gap = [1, 4, 3, 4, 3, 8, 22, 22]

压缩方式 2: VInt (Variable Integer)
[1, 0x84, 0x18, 0x20, 0x18, 0x40, 0xA2, 0x8E]

压缩方式 3: Frame of Reference
适合连续值，使用 bit-packing
```

---

## 3. 写入流程

### 3.1 完整写入时序图

```
Client      HTTP Server    Coordinator    Shard (Primary)    Shard (Replica)
   │              │              │                  │                  │
   │  Index doc   │              │                  │                  │
   ├─────────────►│              │                  │                  │
   │              │  解析 routing│                  │                  │
   │              ├─────────────►│                  │                  │
   │              │              │  路由到对应 shard │                  │
   │              │              ├──────────────────►│                  │
   │              │              │                  │                  │
   │              │              │                  │  写入 Translog   │
   │              │              │                  ├─────────────────►│
   │              │              │                  │                  │
   │              │              │                  │  写入内存索引     │
   │              │              │                  ├─────────────────►│
   │              │              │                  │                  │
   │              │              │                  │  复制给 replica  │
   │              │              │                  ├──────────────────────────────►│
   │              │              │                  │                  │
   │              │              │◄─────────────────┤                  │
   │              │              │  写入完成         │                  │
   │              │◄─────────────┤                  │                  │
   │◄─────────────│              │                  │                  │
   │  Acknowledged│              │                  │                  │
```

### 3.2 写入关键步骤

```go
type IndexRequest struct {
    index      string           // 索引名
    id         string           // 文档 ID
    document   map[string]any   // 文档内容
    opType     string           // index/create/delete
    refresh    bool             // 是否立即刷新
    timeout    time.Duration    // 超时时间
}

func (s *IndexService) Index(req IndexRequest) (*IndexResponse, error) {
    // 1. 验证文档
    if err := s.validate(req); err != nil {
        return nil, err
    }
    
    // 2. 路由到正确分片
    shard := s.router.Route(req.index, req.id)
    
    // 3. 生成操作 ID（用于去重）
    opID := s.generateOpID(req)
    
    // 4. 写入 Translog（持久化）
    if err := s.translog.Write(shard, req); err != nil {
        return nil, err
    }
    
    // 5. 写入内存索引
    if err := s.indexWriter.Add(shard, req); err != nil {
        return nil, err
    }
    
    // 6. 复制给 replica
    if err := s.replication.Copy(shard, req); err != nil {
        return nil, err
    }
    
    // 7. 刷新（可选）
    if req.refresh {
        s.flush(shard)
    }
    
    return &IndexResponse{
        ID:      req.id,
        Shard:   shard,
        Version: s.version + 1,
    }, nil
}
```

---

## 4. 查询流程

### 4.1 查询执行流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        查询执行流程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 查询解析 (Query Parsing)                                        │
│     ┌─────────────────────────────────────────┐                   │
│     │  JSON → Query DSL → Query Object Tree   │                   │
│     └─────────────────────────────────────────┘                   │
│                          │                                         │
│  2. 查询路由 (Query Routing)                                      │
│     ┌─────────────────────────────────────────┐                   │
│     │  确定查询哪些分片 (primary + replicas)  │                   │
│     └─────────────────────────────────────────┘                   │
│                          │                                         │
│  3. 分布式查询 (Distributed Query)                                │
│     ┌─────────────────────────────────────────┐                   │
│     │  Coordinator → 各分片执行查询            │                   │
│     └─────────────────────────────────────────┘                   │
│                          │                                         │
│  4. 局部排序与 TopN (Local Sort & TopN)                           │
│     ┌─────────────────────────────────────────┐                   │
│     │  每个分片返回 top N 结果                 │                   │
│     └─────────────────────────────────────────┘                   │
│                          │                                         │
│  5. 全局排序与合并 (Global Sort & Merge)                          │
│     ┌─────────────────────────────────────────┐                   │
│     │  Coordinator 合并结果，返回最终排序      │                   │
│     └─────────────────────────────────────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 评分机制 (TF-IDF / BM25)

```go
// BM25 评分公式
func BM25Score(tf, docLen, avgDocLen, fieldLen float64, k1, b float64) float64 {
    // IDF 部分
    idf := math.Log(1.0 + (docCount-tf+0.5)/(tf+0.5))
    
    // TF 部分
    tfFactor := tf * (k1 + 1)
    tfDenom := tf + k1*(1-b+b*fieldLen/avgDocLen)
    
    return idf * tfFactor/tfDenom
}

type BM25Params struct {
    K1 float64  // 词频饱和度（默认 1.2）
    B  float64  // 长度归一化（默认 0.75）
}
```

---

## 5. 分片与副本策略

### 5.1 分片策略

```go
type ShardStrategy struct {
    numPrimary   int         // 主分片数
    numReplica   int         // 副本数
    routing      string      // 路由规则
    allocation     AllocationPolicy  // 分配策略
}

// 分配策略
type AllocationPolicy int
const (
    ALLOC_EXPLICIT AllocationPolicy = iota  // 显式分配
    ALLOC_DECISION                         // 基于决策
    ALLOC_NEW_SHARD                        // 新分片优先
)
```

**分片数量选择原则**：
- 单分片大小：10GB-50GB
- 总数据量 / 单分片大小 = 主分片数
- 副本数：根据高可用需求（默认 1）

### 5.2 路由机制

```go
// 文档路由到分片
func Route(index, docID string, numShards int) int {
    // SHA256 哈希
    hash := sha256.Sum256([]byte(docID))
    hashInt := binary.BigEndian.Uint64(hash[:8])
    
    // 取模
    shard := int(hashInt % uint64(numShards))
    
    return shard
}

// 自定义路由
func CustomRoute(index, routingKey string, numShards int) int {
    hash := sha256.Sum256([]byte(routingKey))
    hashInt := binary.BigEndian.Uint64(hash[:8])
    
    return int(hashInt % uint64(numShards))
}
```

---

## 6. 性能优化

### 6.1 索引优化

```json
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s",
    "translog": {
      "flush_threshold_size": "1gb",
      "sync_interval": "5s",
      "durability": "async"
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
      "created_at": {
        "type": "date",
        "format": "epoch_millis"
      }
    }
  }
}
```

### 6.2 查询优化

```go
// 常见优化技巧
type QueryOptimization struct {
    // 1. 使用 filter context（不走评分）
    FilterQuery query.Query
    
    // 2. 限制返回字段
    SourceFilter *SourceFilter
    
    // 3. 分页优化（deep pagination）
    SearchAfter []any
    
    // 4. 缓存优化
    RequestCache bool
    
    // 5. 预排序优化
    PreSort      bool
}
```

### 6.3 内存优化

```sql
-- JVM Heap 设置（不超过 31GB，避免指针压缩问题）
-Xms31g
-Xmx31g

-- 关键 JVM 参数
-XX:+UseG1GC
-XX:G1HeapRegionSize=16m
-XX:InitiatingHeapOccupancyPercent=75
```

---

## 7. 常见问题排查

### 7.1 热点问题

```sql
-- 查看热点分片
GET _cat/shards?v&h=index,shard,prirep,state,docs,store,ip,node&s=store:desc

-- 查看 JVM 内存
GET _nodes/hot_threads

-- 查看线程池
GET _cat/thread_pool
```

### 7.2 慢查询优化

```sql
-- 开启慢查询日志
PUT _cluster/settings
{
  "persistent": {
    "logger.org.elasticsearch.search": "DEBUG"
  }
}

-- 查看查询耗时
GET _nodes/stats/query
```

---

## 8. 总结

### 8.1 核心原理回顾

| 组件 | 作用 | 关键优化 |
|------|------|----------|
| 倒排索引 | 全文检索 | FST 压缩、Posting List 压缩 |
| 分片 | 水平扩展 | 合理分片数、均匀分配 |
| 副本 | 高可用 | 副本数根据需求设置 |
| Translog | 数据持久化 | async/durability 权衡 |
| Refresh | 数据可见性 | 调整 refresh_interval |

### 8.2 性能优化 checklist

- [ ] 合理设置分片数和大小
- [ ] 调整 refresh_interval
- [ ] 使用 filter context
- [ ] 限制返回字段
- [ ] 避免 deep pagination
- [ ] 监控 JVM 内存使用
- [ ] 定期快照备份

---

*最后更新：2026-08-11*
*作者：Ryan*
