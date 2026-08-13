# Elasticsearch搜索引擎架构 - 资深专家深度实现

## 一、核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Elasticsearch架构                           │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │  Client  │───►│  Node A  │───►│  Node B  │───►│  Node C  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘
│                         │
│                    ┌────┴────┐
│                    │ Shard   │
│                    │ (主分片)  │
│                    └─────────┘
│                    ┌─────────┐
│                    │ Replica │
│                    │ (副本分片) │
│                    └─────────┘
└─────────────────────────────────────────────────────────────┘
```

## 二、倒排索引

```java
// 文档: "The quick brown fox"
// Token: ["the", "quick", "brown", "fox"]

// 倒排索引结构:
the    → [doc1, doc3]
quick  → [doc1]
brown  → [doc1, doc2]
fox    → [doc2]
```

## 三、查询优化

```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"title": "search"}}
      ],
      "filter": [
        {"term": {"status": "active"}},
        {"range": {"created_at": {"gte": "2024-01-01"}}}
      ]
    }
  },
  "collapse": {
    "field": "user_id"
  }
}
```

## 四、面试高频题

### Q1: 倒排索引和正排索引的区别？

```
A: 倒排索引按关键词查文档，正排索引按文档查关键词。
```

### Q2: 如何优化ES查询性能？

```
A:
1. 合理设置分片数
2. 使用filter缓存
3. 避免深分页
4. 字段类型优化
```

## 五、自测题

1. 设计一个全文检索系统
2. 如何实现高亮显示？

---

## 参考文档

- [ES官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
