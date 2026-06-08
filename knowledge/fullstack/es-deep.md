# Elasticsearch 深度 — 倒排索引、分词、集群调优

> 标签: `#Elasticsearch` `#倒排索引` `#分词器` `#集群` `#调优`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. ES 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Client (HTTP/REST)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Node A     │ │   Node B     │ │   Node C     │
    │  (Master)    │ │              │ │              │
    │  ┌────────┐  │ │  ┌────────┐  │ │  ┌────────┐  │
    │  │Primary │  │ │  │Primary │  │ │  │Replica │  │
    │  │ Shard 0 │  │ │  │ Shard 1 │  │ │  │ Shard 0│  │
    │  │Shard 1  │  │ │  │Shard 0  │  │ │  │Shard 1 │  │
    │  └───┬────┘  │ │  └───┬────┘  │ │  └───┬────┘  │
    │      │       │ │      │       │ │      │       │
    │  ┌───▼────┐  │ │  ┌───▼────┐  │ │  ┌───▼────┐  │
    │  │ Lucene │  │ │  │ Lucene │  │ │  │ Lucene │  │
    │  │Segment │  │ │  │Segment │  │ │  │Segment │  │
    │  └────────┘  │ │  └────────┘  │ │  └────────┘  │
    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 2. 倒排索引（Inverted Index）

### 2.1 正排 vs 倒排

```
正排索引（数据库方式）:
  doc_id → doc_content
  1 → "中国北京"
  2 → "中国上海"
  3 → "美国纽约"
  
  查询 "中国": 需要全表扫描 → O(N)

倒排索引（ES 方式）:
  term → doc_ids[]
  "中国" → [1, 2]
  "北京" → [1]
  "上海" → [2]
  "美国" → [3]
  "纽约" → [3]
  
  查询 "中国": 直接查 term → [1, 2] → O(1)
```

### 2.2 倒排索引数据结构

```
Term Dictionary (词条字典):
  ┌──────────┬──────────────┬────────────┐
  │   Term   │ Posting List │ Term Index │
  │ (词条)   │ ( postings ) │ (跳表)     │
  ├──────────┼──────────────┼────────────┤
  │ "北京"   │ doc:1, freq:1│ Offset: A  │
  │ "上海"   │ doc:2, freq:1│            │
  │ "中国"   │ doc:1,2,     │            │
  │          │   freq:2     │            │
  └──────────┴──────────────┴────────────┘

Posting List ( postings 列表):
  doc_id_1, freq_1, offset_1, position_1,
  doc_id_2, freq_2, offset_2, position_2,
  ...
  
  - doc_id: 文档 ID（FST 编码压缩）
  - freq: 词频（Term Frequency）
  - offset: 在 postings 文件中的偏移量
  - position: 词条在文档中的位置（用于短语查询）
  
Term Index（词条索引，内存中的跳表）:
  存储 Term Dictionary 中每个 Term 的首字母位置
  查询时先在 Term Index 中找到范围，再加载对应的 FST
  实现: Fixed-Skip Table（固定跳表）

FST (Finite State Transducer):
  ES 8.x 替代 Lucene 的 KDTree 存储 Term Dictionary
  有向无环图，支持高效的前缀匹配、范围查询
  压缩比高，内存占用小
```

### 2.3 倒排索引创建流程

```
1. Analyzer (分析器) 处理文本:
   "Hello World!" → tokenizer → ["hello", "world"]
   
2. 将 term 写入 Term Dictionary
   
3. 将 (doc_id, term) 写入 Postings
   
4. 构建 Term Index（跳表）用于加速查找
   
5. 写入 Segment（LSM 树风格，先写内存，再 flush 到磁盘）
```

---

## 3. 分词器（Analyzer）深度解析

### 3.1 Analyzer 组成

```
Analyzer = Character Filter + Tokenizer + Token Filter

流程:
  原始文本 → Character Filter → Tokenizer → Tokens → Token Filter → 最终词条

Character Filter (字符过滤):
  - HTML Strip Char Filter: 去除 HTML 标签
  - Pattern Replace Char Filter: 正则替换
  - Mapping Char Filter: 字符映射

Tokenizer (分词器):
  - Standard Analyzer: 标准分词（默认）
  - Simple Analyzer: 按非字母分词，转小写
  - Whitespace Analyzer: 按空格分词
  - Keyword Analyzer: 不分词，整个字符串作为一个词条
  - Chinese Analyzer: IK、HanLP 等中文分词

Token Filter (词条过滤):
  - Lowercase: 转小写
  - Stop: 去除停用词（the, is, at 等）
  - Synonym: 同义词替换
  - Stemming: 词干提取
  - Edge Ngram: 前缀 n-gram（用于自动补全）
```

### 3.2 中文分词实战

```json
// IK 分词器配置
PUT /my_index
{
  "settings": {
    "analysis": {
      "analyzer": {
        "ik_max_word": {
          "type": "ik_max_word"
        },
        "ik_smart": {
          "type": "ik_smart"
        }
      }
    }
  }
}

// IK 分析
POST /my_index/_analyze
{
  "analyzer": "ik_max_word",
  "text": "中华人民共和国国歌"
}
// 结果: [中华人民共和国, 中华人民, 中华, 华人, 人民, 人民共和国, 共和国, 国歌]

// IK smart
POST /my_index/_analyze
{
  "analyzer": "ik_smart",
  "text": "中华人民共和国国歌"
}
// 结果: [中华人民共和国, 国歌]
```

### 3.3 分词策略选择

```
场景: 全文搜索
  → Standard Analyzer / IK Analyzer
  → 需要分词，支持全文检索

场景: 精确匹配（邮箱、手机号、ID）
  → Keyword Analyzer
  → 不分词，整个字符串作为词条

场景: 自动补全
  → Edge Ngram Tokenizer
  → 生成前缀词条

场景: 搜索建议
  → Completion Suggester (Inverted Index + FST)
  → 支持拼音、模糊匹配
```

---

## 4. 文档写入与查询流程

### 4.1 写入流程

```
1. Client 发送 Index/Create/Update/Delete 请求
2. Coordinator Node 接收请求
3. 计算 doc_id = hash(routing) % num_primary_shards
4. 路由到对应的 Primary Shard
5. Primary Shard 写入 Translog（先写日志，保证持久性）
6. Primary Shard 写入内存中的 Lucene Index
7. Primary Shard 通知 Replicas 写入
8. Replicas 写入 Translog + 内存 Index
9. Primary Shard 收集所有 Replicas 确认
10. Coordinator Node 返回成功

Translog 刷盘:
  - translog.durability: request（每次写操作刷盘）/ async（后台异步刷盘）
  - translog.sync_interval: 同步间隔（默认 5s）
  
Fsync:
  - 定期将内存 Index flush 到磁盘（Segment）
  - 默认 30 分钟，或 translog 超过 512MB
```

### 4.2 查询流程

```
1. Client 发送 Search 请求
2. Coordinator Node 接收请求
3. 将查询路由到所有相关 Shard（基于 routing 或 _shards）
4. 各 Shard 执行查询:
   a. 查询 Cache 中是否有结果
   b. 如果没有，执行查询:
      - 解析查询条件 → Query Parser
      - 构建 Query Object（TermQuery / RangeQuery / BoolQuery）
      - 遍历 Posting List，计算 Score
      - Top-K 排序（使用 Priority Queue）
   c. 返回 Top-K 结果给 Coordinator
5. Coordinator 合并各 Shard 的 Top-K（全局排序）
6. 返回最终结果

Query Cache:
  - 缓存 Filter 查询的结果（不变的数据）
  - 基于查询字符串的 hashCode 缓存
  - 不适用于带参数的查询（如 range）

Field Data Cache:
  - 排序和聚合时加载字段数据到内存
  - 注意: 可能导致 OOM，慎用
```

---

## 5. 集群架构与调优

### 5.1 分片策略

```
分片数量:
  - Primary Shard: 数据分片，不可更改（创建时确定）
  - Replica Shard: 副本，提供高可用和读扩展
  
  原则:
  - Primary Shard 不宜过多（每 GB 数据 15-20 个 shard）
  - 单个 shard 大小建议 10-50GB
  - Replica Shard 数量: 1-2 个（根据资源调整）

分片路由:
  - routing 参数: 控制文档路由到哪个 shard
  - _routing: 文档字段控制路由
  
  PUT /logs-2026.06/{log_type}
  - 按月分索引，按日志类型 routing
  - 同类型日志在同 shard，避免跨 shard 聚合
```

### 5.2 内存管理

```
JVM Heap 管理:
  - ES 建议堆内存 ≤ 31GB（避免指针压缩失效）
  - 50% 留给 Lucene，50% 留给 JVM
  - -Xms 和 -Xmx 设置相同，避免动态扩容

重要参数:
  indices.fielddata.cache.size: 15-20%（Field Data 缓存）
  indices.queries.cache.size: 10%（Query Cache）
  indices.breaker.total.limit: 70%（总断路限制）
  indices.breaker.fielddata.limit: 40%
  indices.breaker.request.limit: 60%

监控:
  - GC 时间: 应该 < 500ms，避免 Stop-The-World
  - 使用 G1GC（ES 7.x+ 默认）
  - 关注 heap 使用率，超过 75% 需要扩容
```

### 5.3 写入优化

```
写入优化:
  1. 批量写入: bulk API，每批 1000-5000 条
  2. 禁用 replica: index.number_of_replicas=0（导入时）
  3. 增加 translog 刷新间隔: index.translog.durability=async
  4. 合并 segment: POST /_forcemerge?max_num_segments=1
  5. 增加 refresh_interval: 30s → 5min（导入时）

写入吞吐:
  - 单节点: 5-10k doc/s（SSD）
  - 集群: 根据节点数线性扩展
```

### 5.4 查询优化

```
查询优化:
  1. 使用 filter context（不走评分，可缓存）
  2. 避免 wildcard 前缀通配（*abc → abc*）
  3. 使用 keyword 字段做聚合/排序
  4. 限制返回字段: _source filtering
  5. 使用 search_after 替代 from/size 深度分页
  6. 预计算常用聚合

深度分页优化:
  ❌ from=10000, size=10 （跨 shard 排序，内存爆炸）
  ✅ search_after: 记录上次最后一个文档的 sort_value
  
  POST /_search
  {
    "size": 10,
    "search_after": [1573515653265],  // 上次最后一条的 sort
    "sort": [{"timestamp": "desc"}]
  }
```

### 5.5 集群高可用

```
脑裂防护:
  - discovery.seed_hosts: 发现节点列表
  - cluster.initial_master_nodes: 初始 master 节点列表
  - gateway.recover_after_nodes: 最少 N 个节点恢复
  
  设置:
  cluster.routing.allocation.require._name: "master"
  cluster.routing.allocation.total_shards_per_node: 2

故障转移:
  - Master 节点故障 → 选举新 Master（Zab 协议）
  - 数据节点故障 → Replicas 提升为 Primary
  - 脑裂 → 设置 minimum_master_nodes = N/2 + 1

监控:
  - GET /_cluster/health: 集群状态
  - GET /_cat/nodes?v: 节点信息
  - GET /_cat/shards?v: 分片分布
  - GET /_nodes/stats/jvm: JVM 状态
  - GET /_cat/thread_pool?v: 线程池
```

---

## 6. 实战场景

### 6.1 日志聚合

```json
PUT /logs-2026.06
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  },
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "level": {"type": "keyword"},
      "message": {"type": "text", "analyzer": "ik_max_word"},
      "service": {"type": "keyword"},
      "ip": {"type": "ip"},
      "trace_id": {"type": "keyword"}
    }
  }
}

// 查询最近 1 小时的错误日志
GET /logs-2026.06/_search
{
  "query": {
    "bool": {
      "filter": [
        {"range": {"@timestamp": {"gte": "now-1h"}}},
        {"term": {"level": "ERROR"}}
      ]
    }
  },
  "sort": [{"@timestamp": "desc"}],
  "size": 100
}
```

### 6.2 全文搜索

```json
PUT /products
{
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "ik_max_word",
        "fields": {
          "keyword": {"type": "keyword"}
        }
      },
      "price": {"type": "float"},
      "category": {"type": "keyword"},
      "description": {
        "type": "text",
        "analyzer": "ik_max_word"
      }
    }
  }
}

// 混合搜索: 全文 + 过滤 + 排序
GET /products/_search
{
  "query": {
    "bool": {
      "must": [
        {"multi_match": {
          "query": "iPhone 手机壳",
          "fields": ["name^3", "description"]
        }}
      ],
      "filter": [
        {"term": {"category": "配件"}},
        {"range": {"price": {"lte": 100}}}
      ]
    }
  },
  "sort": [{"_score": "desc"}, {"price": "asc"}]
}
```

### 6.3 聚合分析

```json
// 按 category 统计
GET /products/_search
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": {"field": "category", "size": 10}
    }
  }
}

// 嵌套聚合: 每个 category 的平均价格
GET /products/_search
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": {"field": "category", "size": 10},
      "aggs": {
        "avg_price": {"avg": {"field": "price"}},
        "price_stats": {"stats": {"field": "price"}}
      }
    }
  }
}
```

---

*本文档基于 ES 8.x 整理，涵盖核心机制与实战优化*
