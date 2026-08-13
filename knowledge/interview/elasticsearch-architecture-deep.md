# Elasticsearch架构 - 资深专家深度实现

## 一、核心架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Elasticsearch架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │   Node A    │    │   Node B    │    │   Node C    │               │
│   │  (Master)   │    │  (Data)     │    │  (Data)     │               │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│          │                  │                  │                       │
│   ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐               │
│   │  Primary    │    │  Primary    │    │  Primary    │               │
│   │  Shard 0    │    │  Shard 1    │    │  Shard 2    │               │
│   └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                         │
│   • 集群: 多个节点组成                                                  │
│   • 索引: 逻辑数据库                                                    │
│   • 分片: 数据分片 (0-255)                                              │
│   • 副本: 分片副本 (高可用)                                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、倒排索引

```java
// 文档: "The quick brown fox"
// 分词后: ["the", "quick", "brown", "fox"]

// 倒排索引结构
class InvertedIndex {
    Map<String, List<Long>> terms;
    
    void add(Document doc) {
        for (Token token : analyzer.analyze(doc.getText())) {
            String term = token.getText();
            long docId = doc.getId();
            
            if (!terms.containsKey(term)) {
                terms.put(term, new ArrayList<>());
            }
            terms.get(term).add(docId);
        }
    }
    
    List<Long> search(String query) {
        // FSDirectory查询
        return terms.get(query);
    }
}
```

## 三、查询优化

```go
package query

import (
    "sort"
)

type QueryOptimizer struct {
    cache *QueryCache
}

func (q *QueryOptimizer) optimize(query *Query) *Query {
    // 1. 常量折叠
    query = q.foldConstants(query)
    
    // 2. 谓词下推
    query = q.pushDownPredicates(query)
    
    // 3. 子查询去重
    query = q.deduplicateSubqueries(query)
    
    return query
}

func (q *QueryOptimizer) execute(query *Query) *SearchResponse {
    // 1. 查询路由
    shards := q.route(query)
    
    // 2. 并行查询
    results := make([]*PartialResult, len(shards))
    for i, shard := range shards {
        results[i] = shard.search(query)
    }
    
    // 3. 合并排序
    return q.merge(results)
}
```

## 四、面试高频题

### Q1: ES为什么快？

```
A:
1. 倒排索引
2. 列式存储
3. 分布式并行
4. 近实时搜索
```

### Q2: 如何解决深分页问题？

```
A:
1. Search After
2. 滚动查询
3. 限制最大结果数
```

## 五、自测题

1. 解释倒排索引原理
2. 如何实现高可用？
3. 如何优化查询性能？

---

## 参考文档

- [Elasticsearch官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/)
- [Lucene源码](https://github.com/apache/lucene)
