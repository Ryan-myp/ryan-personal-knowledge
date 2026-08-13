# 图数据库Neo4j深度解析

> 深入图数据库Neo4j：Cypher查询、图算法、性能优化、应用场景。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：数据工程师、后端工程师

---

## 1. Cypher查询语言

### 1.1 核心语法

```
Cypher查询语法：

┌─────────────────────────────────────────────────────────────┐
│  创建节点：                                                  │
│  CREATE (n:Person {name: 'Alice', age: 30})                 │
│                                                             │
│  创建关系：                                                  │
│  MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'}) │
│  CREATE (a)-[:FRIEND]->(b)                                  │
│                                                             │
│  查询：                                                      │
│  MATCH (p:Person) RETURN p                                  │
│  MATCH (p:Person {name: 'Alice'}) RETURN p.name, p.age      │
│  MATCH (a:Person)-[:FRIEND]->(b:Person) RETURN a, b         │
│                                                             │
│  路径查询：                                                  │
│  MATCH path = (a:Person)-[:FRIEND*1..3]->(b:Person)         │
│  WHERE a.name = 'Alice' AND b.name = 'Eve'                  │
│  RETURN path                                                  │
│                                                             │
│  聚合查询：                                                  │
│  MATCH (p:Person)-[:FRIEND]->(friend)                       │
│  RETURN p.name, count(friend) as friendCount                │
│  ORDER BY friendCount DESC                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 图算法

### 2.1 核心算法

```
Neo4j图算法：

┌─────────────────────────────────────────────────────────────┐
│  中心度算法：                                                │
│  ├── PageRank：页面重要性评分                                 │
│  ├── Betweenness：中介中心度                                  │
│  └── Closeness：接近中心度                                   │
│                                                             │
│  社区发现算法：                                              │
│  ├── Label Propagation：标签传播                              │
│  ├── Louvain：模块度优化                                     │
│  └── Strongly Connected Components：强连通分量               │
│                                                             │
│  路径算法：                                                  │
│  ├── Shortest Path：最短路径                                  │
│  ├── Dijkstra：带权最短路径                                   │
│  └── A*：启发式搜索                                         │
│                                                             │
│  相似性算法：                                                │
│  ├── Node Similarity：节点相似性                             │
│  └── Node Embeddings：节点嵌入                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Cypher中，创建节点的关系使用什么符号：
   A. ->  B. ()  C. {}  D. []
   答案：A

---

> 本文档适用对象：数据工程师、后端工程师
> 难度：资深专家级
