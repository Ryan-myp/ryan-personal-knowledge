# ES架构深度 - 资深专家深度实现

## 一、倒排索引

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      倒排索引结构                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Term Dictionary (词项字典)                                             │
│   ├── apple: [doc1, doc3, doc5]                                          │
│   ├── banana: [doc2, doc4]                                               │
│   └── cherry: [doc1, doc2, doc5]                                         │
│                                                                         →
│   Posting List ( postings list)                                           │
│   ├── apple: {1, 3, 5} → freq: {2, 1, 3} → positions: {[0], [2], [1]}   │
│   └── banana: {2, 4} → freq: {1, 2} → positions: {[1], [0, 3]}          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、分片架构

```yaml
# 分片配置
cluster:
  indices:
    logs:
      shards: 5           # 主分片
      replicas: 1         # 副本分片
      
# 分布示例
shard_0: primary → node1 | replica → node2
shard_1: primary → node2 | replica → node3  
shard_2: primary → node3 | replica → node1
shard_3: primary → node1 | replica → node3
shard_4: primary → node2 | replica → node1
```

## 三、面试高频题

### Q1: 倒排索引原理？

```
A:
1. 文本分词
2. 建立Term-Doc映射
3. 倒排快速检索
```

### Q2: 如何实现高可用？

```
A:
1. 副本分片
2. 自动故障转移
3. 脑裂防护
```

## 四、自测题

1. 解释倒排索引
2. 如何实现分片？
3. 如何优化查询性能？

---

## 参考文档

- [ES官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/)
- [Elasticsearch白皮书](https://www.elastic.co/resources/elasticsearch-whitepaper)
