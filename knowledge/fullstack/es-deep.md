# Elasticsearch 深度 — Lucene 底层、倒排索引、分词器、集群协议

> 标签: `#Elasticsearch` `#Lucene` `#倒排索引` `#分词器` `#集群` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 整体架构 — Lucene → Elasticsearch

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│                    Application Layer                          │
│  REST API / Java Client / Go Client / Python Client           │
├──────────────────────────────────────────────────────────────┤
│                    Transport Layer                            │
│  HTTP REST API (port 9200) / Transport (port 9300)           │
├──────────────────────────────────────────────────────────────┤
│                    Search / Query Layer                        │
│  Query Parser → Query DSL → QueryTree → Scorer → Collector   │
├──────────────────────────────────────────────────────────────┤
│                    Index / Search Engine                      │
│  Elasticsearch 封装 Lucene Core Engine                        │
├──────────────────────────────────────────────────────────────┤
│                    Lucene Core                                │
│  Segment → Document → Field → Term → Inverted Index           │
│  NRT Reader → SegmentReader → PostingsReader                  │
│  FSDirectory → MMapDirectory                                  │
└──────────────────────────────────────────────────────────────┘

Lucene → Elasticsearch 的映射:
  Lucene Index     → Elasticsearch Index
  Lucene Document  → Elasticsearch Document
  Lucene Field     → Elasticsearch Field
  Lucene Segment   → Elasticsearch Shard (一个 Shard = 一个 Lucene Index)
  Lucene Analyzer  → Elasticsearch Analyzer
  Lucene Query     → Elasticsearch Query
```

### 1.2 核心数据结构

```java
// Lucene Segment 结构 (org.apache.lucene.index)
// 一个 Segment 是不可变的，代表一段时间内的数据快照
// Elasticsearch 的 Shard 包含多个 Segment

// Segment 文件:
// .fdt, .fdx   - Field Dump / Index（字段存储）
// .fnm         - Field Names
// .fdx         - Field Index
// .di          - Doc Values Index（列式存储索引）
// .dvd         - Doc Values Data（列式存储数据）
// .tim, .tvx   - Term Info（词条信息索引）
// .tis         - Term Info（词条信息数据）
// .tp, .tpx    - Term Positions（词条位置信息）
// .nvm         - Norms（标准化因子）
// .prx         - Postings（ postings 列表）
// .doc         - Doc ID 到 Doc Number 的映射
// .liv, .si    - Live Docs / Segment Info

// 倒排索引结构（Postings Format）:
// Term Dictionary:
//   - 按字典序排序的所有词条（Term）
//   - 支持二分查找 / FST（Finite State Transducer）
//   - 每个词条指向 Term Index（ postings 起始位置）
//
// Term Index:
//   - 词条前缀索引（Prefix Index）
//   - 支持前缀搜索、范围搜索
//
// Term Dictionary Entry:
//   - term: 词条文本（如 "hello"）
//   - docFreq: 包含该词条的文档数
//   - postingsOffset: postings 列表在 .prx 文件中的偏移
//
// Postings List:
//   - docId: 文档 ID
//   - tf: 词频（Term Frequency）
//   - positions: 词条位置（用于短语搜索）
//   - offsets: 词条偏移量（用于高亮）
```

### 1.3 分词器（Analyzer）— 源码级

```java
// Elasticsearch Analyzer 链:
// CharFilter → Tokenizer → TokenFilter

// 1. CharFilter（字符过滤器）:
//    - HTML Strip CharFilter: 去除 HTML 标签
//    - Pattern Replace CharFilter: 正则替换
//    - Mapping CharFilter: 字符映射
//    作用: 在分词前清洗文本

// 2. Tokenizer（分词器）:
//    - Standard Analyzer: 基于 Unicode 标准分词
//    - Whitespace Analyzer: 按空白符分词
//    - Keyword Analyzer: 不分词（整体作为一个 Token）
//    - Pattern Analyzer: 按正则分词
//    - Language Analyzer: 语言特定分词（英语/中文/日语等）
//    作用: 将文本切分为 Token 流

// 3. TokenFilter（词元过滤器）:
//    - Lowercase Filter: 转小写
//    - Stop Token Filter: 去除停用词（the, a, an 等）
//    - Stemming Filter: 词干提取（run → run, running → run）
//    - Synonym Filter: 同义词扩展
//    - NGram Token Filter: n-gram 分词
//    - EdgeNGram Token Filter: 前缀 n-gram
//    - Keyword Marker Filter: 标记关键词（不参与 stem）
//    - Shingle Token Filter: 词组生成（bigram/trigram）
//    作用: 对 Token 进行后处理

// 自定义 Analyzer 示例:
public class CustomAnalyzer extends AbstractAnalyzer {
    @Override
    protected Analyzer.TokenStreamComponents createComponents(String fieldName) {
        Tokenizer tokenizer = new CustomTokenizer();
        TokenStream tokens = tokenizer;
        tokens = new LowercaseFilter(tokens);
        tokens = new StopFilter(tokens, StopWords.ENGLISH);
        tokens = new SnowballPorterFilter(tokens, "English");
        return new Analyzer.TokenStreamComponents(tokenizer, tokens);
    }
}

// 中文分词策略:
// 1. IK Analyzer: IKTokenizer + IKSegmenter
//    - 支持细粒度/智能分词
//    - 支持自定义词典
// 2. Jieba Analyzer: jieba 分词 + 词性标注
//    - 支持精确模式/全模式/搜索引擎模式
// 3. HanLP Analyzer: HanLP 分词
//    - 支持 NER、依存句法分析
//    - 支持自定义词典和规则
```

---

## 2. 倒排索引深度 — Lucene 实现

### 2.1 IndexWriter 写入流程

```java
// IndexWriter 写入流程:
// 1. 文档 → Analyzer 分词 → TokenStream
// 2. TokenStream → Term → DocValues（列式存储）
// 3. DocValues → Segment Writer
// 4. Segment Writer 写入 Segment 文件
// 5. 提交（commit）→ 创建新 Segment
// 6. 后台线程合并（merge）小 Segments

// Lucene 的写入路径:
IndexWriter.addDocument(Documents) {
    // 1. 对每个文档分词
    for (Field field : doc) {
        TokenStream stream = analyzer.tokenStream(field.name(), field);
        // 2. 将 Token 写入 postings
        for (Term term : stream) {
            postingsWriter.addPosting(term, docId, position);
        }
    }
    
    // 3. 写入 DocValues
    docValuesWriter.write(doc);
    
    // 4. 写入 stored fields
    storedFieldsWriter.write(doc);
}

// IndexWriter 配置:
// maxBufferedDocs: 内存中文档数上限（默认 10000）
// maxBufferedBytes: 内存中文档大小上限（默认 16MB）
// mergePolicy: 合并策略（TieredMergePolicy 默认）
// mergeScheduler: 合并调度器（ConcurrentMergeScheduler 默认）
// ramBufferSizeMB: 缓冲大小
```

### 2.2 Segment Merge（段合并）

```java
// TieredMergePolicy（默认合并策略）:
// 核心逻辑:
// 1. 如果小 Segment 的数量超过阈值 → 合并
// 2. 合并后的 Segment 大小不超过 maxSegmentSize
// 3. 合并比例由 maxMergedSegmentMB / mergeFactor 决定
//    - 默认: 10MB / 10（即 10 个 1MB 的 Segment 合并为 1 个 10MB）
//    - 实际: mergeFactor = 10，表示每 10 个相同大小的 Segment 合并为一个

// 合并过程:
// 1. 选择待合并的 Segments（mergePolicy.selectSegmentsToMerge）
// 2. 创建新的 Segment Writer
// 3. 遍历所有待合并的 Segments，读取文档并写入新 Segment
// 4. 写入完成后，用新 Segment 替换旧 Segments
// 5. 旧 Segments 被标记删除，等待 GC

// 合并优化:
// 1. 合并时 skip 已删除的文档（tombstones）
// 2. 使用 DocValues 的 compaction 优化
// 3. 后台合并不阻塞写入

// 合并触发条件:
// 1. Segment 数量 > mergeFactor × maxMergeAtOnce
// 2. 总大小 > maxMergeAtOnce × maxSegmentSize
// 3. 最小 Segment 大小 < maxMergeAtOnce × maxSegmentSize
```

### 2.3 查询执行引擎

```java
// Elasticsearch 查询路径:
// 1. 用户发送 DSL 查询
// 2. Query Parser 解析 DSL → Query 对象
// 3. 遍历所有 Shard，发送到每个 Shard 执行
// 4. Shard 内部: Query → Scorer → Collector
// 5. 合并所有 Shard 的结果 → Top N

// Lucene 查询执行:
// TermQuery:
//   - 从 Term Dictionary 查找词条
//   - 获取 postings 列表
//   - 返回包含该词条的文档
//
// BooleanQuery:
//   - 对子查询分别评分
//   - 合并评分（SUM/MAX/MIN）
//   - 过滤不满足条件的文档
//
// 评分公式 (BM25):
// score(q, d) = Σ [ IDF(t) × TF(t, d) × (TF(t, d) + k1 × (1 - b + b × |d| / avgLen)) ]
//   IDF(t) = ln((N - n(t) + 0.5) / (n(t) + 0.5) + 1)
//   TF(t, d) = 词条 t 在文档 d 中出现的次数
//   k1 = 1.2 (默认)
//   b = 0.75 (默认)
//   |d| = 文档 d 的长度
//   avgLen = 平均文档长度

// 评分优化:
// 1. IDF 预计算并存储在 .tim 文件中
// 2. TF 从 .prx 文件读取
// 3. 文档长度存储在 .doc 文件中
// 4. 使用 DocValues 缓存热点 IDF
```

---

## 3. 集群协议 — Raft vs Zen Discovery

### 3.1 ES 集群发现

```java
// ES 集群发现流程:
// 1. 节点启动，广播 Ping 消息
// 2. 收到 Ping 的节点回复 Pong
// 3. 主节点收集所有节点信息
// 4. 选举主节点（基于 node_id 排序）
// 5. 主节点分配 Shard

// Zen Discovery（ES < 7.0）:
// 1. 设置 discovery.zen.minimum_master_nodes = (N/2) + 1
// 2. 选举流程:
//    - 主节点故障 → 剩余主节点重新选举
//    - 新主节点选出 → 更新集群状态
//    - 从节点连接新主节点

// Cluster Manager（ES 7.0+）:
// 1. 移除"主节点"概念，改为"Cluster Manager"
// 2. 选举基于 Raft 协议
// 3. 配置: cluster.initial_master_nodes

// 集群状态变更:
// 1. 写入变更请求
// 2. Cluster Manager 应用变更
// 3. 广播新集群状态到所有节点
// 4. 所有节点加载新集群状态
// 5. Shard 分配/重新平衡
```

### 3.2 Shard 分配与路由

```java
// Shard 分配:
// 1. Primary Shard: 负责写操作
// 2. Replica Shard: 负责读操作 + 高可用
// 3. 分配策略:
//    - 尽量将 Primary 和 Replica 分配到不同节点
//    - 尽量均匀分配 Shard 数量
//    - 考虑 Shard 大小和节点负载

// 路由公式:
// shard_number = hash(routing_value) % number_of_primary_shards
// routing_value 默认是 _id
// 自定义 routing: PUT /index/_doc/1?routing=user_123

// 重新平衡:
// 1. 节点加入/退出 → 触发 rebalance
// 2. Cluster Manager 计算新的 Shard 分配
// 3. 将 Shard 从一个节点移动到另一个节点
// 4. 移动过程:
//    - 创建 Replica
//    - 复制数据到新节点
//    - 等待复制完成
//    - 将 Replica 提升为 Primary
//    - 删除旧 Primary

// Shard 级别的一致性:
// 1. 每个 Shard 是独立的 Lucene Index
// 2. Shard 内的文档是有序的（docId）
// 3. 跨 Shard 的文档顺序不可保证
```

---

## 4. DocValues — 列式存储

### 4.1 DocValues 原理

```java
// DocValues = 列式存储（Column-oriented storage）
// 与倒排索引的对比:
// 倒排索引: Term → [DocId1, DocId2, DocId3, ...]
// DocValues: DocId → [Field1_value, Field2_value, ...]

// 列式存储的优势:
// 1. 排序: 直接按列排序，不需要遍历所有文档
// 2. 聚合: 按列聚合（SUM/AVG/MAX/MIN），IO 少
// 3. 脚本: 按字段值执行脚本，缓存友好
// 4. 过滤: 按字段值过滤，位图运算快

// DocValues 类型:
// 1. SortedDocValues: 排序的 doc value（用于排序）
// 2. NumericDocValues: 数值类型 doc value
// 3. SortedSetDocValues: 排序的集合 doc value（用于聚合）
// 4. BinaryDocValues: 二进制 doc value（用于存储）
// 5. SortedNumericDocValues: 排序的数值集合 doc value

// 写入 DocValues:
// IndexWriter.writeDocValues() {
//     for (int docId = 0; docId < maxDoc; docId++) {
//         for (Field field : doc) {
//             if (field.docValueEnabled()) {
//                 docValuesWriter.write(docId, field.name(), field.value());
//             }
//         }
//     }
// }
```

### 4.2 DocValues 存储格式

```java
// DocValues 文件格式:
// .dv 文件:
// - Header: magic number, codec version, field count
// - Field Data: 按字段名顺序存储
//   - 每个字段的 doc value 按 docId 顺序存储
//   - 使用可变长度编码（variable-length encoding）

// 编码方式:
// 1. PForDelta: 定长编码（适合小整数）
// 2. VInt: 可变长度整数编码
// 3. VLong: 可变长度长整数编码
// 4. RunLength: 重复值编码

// 内存映射:
// 1. 使用 MMapDirectory 内存映射文件
// 2. 按需加载（demand loading）
// 3. 操作系统负责页面置换（LRU）
// 4. 避免将整个 DocValues 加载到内存
```

---

## 5. 性能调优

### 5.1 写入优化

```java
// 写入优化策略:
// 1. 批量写入（Bulk API）:
//    - 减少网络往返
//    - 减少 segment 数量
//    - 使用 bulk processor
//
// 2. 调整 refresh_interval:
//    - 默认: 1s（影响性能）
//    - 写入时设为 -1（禁用）
//    - 写入完成后恢复
//
// 3. 调整 max_merge_at_once:
//    - 默认: 10
//    - 减少合并频率
//
// 4. 使用 _bulk API 批量写入:
PUT /_bulk
{ "index": { "_index": "test", "_id": "1" } }
{ "name": "test" }
{ "index": { "_index": "test", "_id": "2" } }
{ "name": "test2" }
```

### 5.2 查询优化

```java
// 查询优化策略:
// 1. 使用 filter 缓存:
//    - 减少评分计算
//    - 结果自动缓存
//    - 使用 constant_score 替代 bool + must
//
// 2. 使用 range filter:
//    - 避免 term 查询的倒排查找
//    - 使用 RangeQuery 直接扫描
//
// 3. 使用 highlight 缓存:
//    - 避免重复高亮计算
//    - 设置 highlight fragment_size
//
// 4. 使用 routing:
//    - 减少查询涉及的 Shard 数量
//    - 精确路由到单个 Shard

// 避免的操作:
// 1. wildcard 查询（*abc*）: 需要扫描所有文档
// 2. 正则表达式查询: 需要扫描所有文档
// 3. 通配符查询: 前缀通配符（abc*）比后缀通配符（*abc）快
// 4. 嵌套查询: 嵌套对象性能差
```

---

*本文档基于 Elasticsearch 8.x / Lucene 9.x 源码整理，覆盖倒排索引、分词、集群协议、DocValues*
