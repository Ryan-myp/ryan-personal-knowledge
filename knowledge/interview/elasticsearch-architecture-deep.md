# Elasticsearch架构 - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Elasticsearch架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Cluster                                                                │
│   ├── Node 1                                                            │
│   │   ├── Index: orders                                                 │
│   │   │   ├── Shard 0 (Primary)                                         │
│   │   │   ├── Shard 1 (Primary)                                         │
│   │   │   └── Shard 2 (Replica)                                         │
│   │   └── Index: products                                               │
│   │       ├── Shard 0 (Primary)                                         │
│   │       └── Shard 1 (Replica)                                         │
│   │                                                                      │
│   ├── Node 2                                                            │
│   │   └── Replicas of Node 1                                            │
│   │                                                                      │
│   └── Node 3                                                            │
│       └── Replicas of Node 1                                            │
│                                                                         │
│   特点:                                                                   │
│   • 分布式搜索                                                           │
│   • 倒排索引                                                             │
│   • 近实时查询                                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、倒排索引

```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "standard"
      },
      "price": {
        "type": "float"
      },
      "created_at": {
        "type": "date"
      }
    }
  }
}
```

## 三、查询优化

```json
// 分面搜索
{
  "aggs": {
    "categories": {
      "terms": {
        "field": "category",
        "size": 10
      }
    }
  }
}

// 高亮显示
{
  "highlight": {
    "fields": {
      "title": {}
    }
  }
}
```

## 四、面试高频题

### Q1: ES如何保证高可用？

```
A:
1. 多副本机制
2. 自动故障转移
3. 数据分片
```

### Q2: 如何优化查询性能？

```
A:
1. 合理分片
2. 字段类型选择
3. 缓存策略
```

## 五、自测题

1. 解释倒排索引原理
2. 如何实现全文检索？
3. 如何优化写入性能？

---

## 参考文档

- [ES官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [ES源码](https://github.com/elastic/elasticsearch)
