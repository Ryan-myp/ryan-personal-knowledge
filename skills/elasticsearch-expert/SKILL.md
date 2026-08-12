---
name: elasticsearch-expert
description: "Elasticsearch 专家技能 — 倒排索引、分词器、查询优化、集群调优"
version: 1.0.0
author: ryan
tags: [elasticsearch, search, index, query, performance, expert]
---

# Elasticsearch 专家技能

> 从 Lucene 底层到生产调优，掌握 ES 内核级知识

## 核心能力

### 1. 倒排索引
- **分词器**：Analyzer、Tokenizer、Filter
- **倒排结构**：Term → DocID → Position → Offset
- **存储优化**：FST、Posting List、Norms
- **查询执行**：布尔查询、短语查询、模糊查询

### 2. 查询优化
- **查询 DSL**：Query String、Query DSL
- **性能优化**：Filter Context、Cache 策略
- **分页优化**：Scroll、Search After
- **聚合优化**：Composite Aggregation、Sub-aggregation

### 3. 集群调优
- **分片策略**：Shard 数量、副本设置
- **索引策略**：Index Template、ILM
- **节点配置**：JVM Heap、Thread Pool
- **运维管理**：集群健康、节点膨胀

### 4. 生产实践
- **数据导入**：Bulk API、Ingest Pipeline
- **数据查询**：高亮、排序、分页
- **数据更新**：Document 更新、Delete By Query
- **灾难恢复**：Snapshot、Restore

## 知识库引用

| 主题 | 文档 |
|------|------|
| ES 内核 | `knowledge/elasticsearch/elasticsearch-kernel-deep.md` |
| 查询引擎 | `knowledge/elasticsearch/elasticsearch-query-engine-deep.md` |
| 搜索架构 | `knowledge/elasticsearch/search-engine-architecture-deep.md` |
| 索引优化 | `knowledge/elasticsearch/elasticsearch-index-optimization-deep.md` |
| 生产实战 | `knowledge/middleware/ad-elasticsearch-deep.md` |

## 使用场景

### 场景 1: 设计索引方案
1. 分析查询模式和数据特点
2. 设计合适的 Mapping 和 Analyzer
3. 设置合理的 Shard 和 Replica
4. 配置 ILM 策略

### 场景 2: 优化查询性能
1. 使用 Profile API 分析查询
2. 优化 Query DSL 结构
3. 利用 Filter Context 缓存
4. 调整 Index Settings

### 场景 3: 集群运维
1. 监控集群健康状态
2. 处理节点膨胀和分片不均衡
3. 执行滚动升级
4. 配置备份策略

## 自测题

<details>
<summary>Q1: Elasticsearch 的分词器 (Analyzer) 工作流程是什么？</summary>

**答案**：
1. **Character Filter**：预处理（去除 HTML 标签等）
2. **Tokenizer**：切分为 Token（Standard/Whitespace/NGram 等）
3. **Token Filter**：过滤和转换（小写、停用词、同义词等）
4. **输出**：最终的 Token 列表用于构建倒排索引

自定义 Analyzer 示例：
```json
{
  "analyzer": {
    "my_analyzer": {
      "type": "custom",
      "tokenizer": "standard",
      "filter": ["lowercase", "my_synonym"]
    }
  }
}
```

</details>

<details>
<summary>Q2: 如何处理 Elasticsearch 的大分页性能问题？</summary>

**答案**：
1. **Deep Pagination 问题**：from + size 在大偏移量时性能差
2. **解决方案**：
   - **Search After**：基于游标的分页，适合深度翻页
   - **Scroll API**：适合批量导出，不适合实时查询
   - **限制深度**：设置最大分页深度（如 10000）
   - **Elasticsearch 7.x+**：使用 `search_after` 替代 `from/size`

```json
// Search After 示例
{
  "size": 10,
  "query": { "match": { "title": "elasticsearch" } },
  "sort": ["_doc", "12345"],
  "search_after": ["12345"]
}
```

</details>

<details>
<summary>Q3: Elasticsearch 的 Index Lifecycle Management (ILM) 是什么？</summary>

**答案**：
1. **概念**：自动管理索引从创建到删除的整个生命周期
2. **阶段**：
   - **Hot**：频繁读写，高性能存储
   - **Warm**：较少读写，低成本存储
   - **Cold**：归档数据，极低成本
   - **Delete**：删除过期数据
3. **操作**：
   - **Roll over**：索引达到条件时滚动到新索引
   - **Shrink**：减少分片数量
   - **Force merge**：合并段文件
   - **Delete**：删除索引

</details>
