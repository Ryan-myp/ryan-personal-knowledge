# Elasticsearch 内核深度解析

> 深入 Elasticsearch 核心：倒排索引、分段合并、查询执行、集群协调。
> 源码级分析 Lucene 引擎，包含性能调优和故障排查。
> 适用对象：搜索工程师、数据工程师、后端架构师

---

## 1. ES 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Elasticsearch 架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  REST API    │    │  Transport   │    │  Client      │          │
│  │  (HTTP)      │    │  (TCP)       │    │  Libraries   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                    │                    │                 │
│         ▼                    ▼                    ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Node 节点层                               │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │   │
│  │  │ HTTP    │  │ Transport│  │ Ingest   │  │ Watcher  │       │   │
│  │  │ Server  │  │ Server  │  │ Pipeline │  │         │       │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Index      │  │  Shard       │  │  Segment     │              │
│  │  (逻辑索引)  │  │  (物理分片)   │  │  (段文件)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Lucene 引擎层                             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │   │
│  │  │ Index   │  │ Search  │  │ Query   │  │ Filter  │       │   │
│  │  │ Writer  │  │ Engine  │  │ Parser  │  │ Compiler│       │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心概念

| 概念 | 说明 | 对应 Lucene 概念 |
|------|------|-----------------|
| Index | 逻辑索引 | Index |
| Shard | 物理分片 | Segment |
| Document | 文档 | Document |
| Field | 字段 | Field |
| Mapping | 映射 | FieldMapping |
| Analyzer | 分词器 | Analyzer |

---

## 2. 倒排索引实现

### 2.1 核心数据结构

```java
// org.apache.lucene.index

public class IndexWriter {
    // 段管理器
    private SegmentInfos segmentInfos;
    
    // 段写入器
    private SegmentWriter[] segmentWriters;
    
    // 词条词典
    private TermsHash termsHash;
    
    // 文档写入器
    private DocumentWriter documentWriter;
    
    public void addDocument(Document doc) throws IOException {
        // 1. 获取或创建段写入器
        SegmentWriter writer = getWriter();
        
        // 2. 写入文档
        writer.addDocument(doc);
        
        // 3. 刷新检查
        maybeRefresh();
    }
}

public class SegmentWriter {
    // 词条表
    private TermsWriter termsWriter;
    
    // 文档存储
    private StoredFieldsWriter storedFieldsWriter;
    
    // 逐出处理
    private DocValuesWriter docValuesWriter;
    
    public void addDocument(Document doc) throws IOException {
        // 1. 处理词条
        termsWriter.processDocument(doc);
        
        // 2. 存储字段
        storedFieldsWriter.addDocument(doc);
        
        // 3. 处理逐出
        docValuesWriter.processDocument(doc);
    }
}
```

### 2.2 词条存储

```java
// org.apache.lucene.codecs

public class Lucene8DocValuesFormat {
    
    // 词条文件
    private static final String DATA_PREFIX = "dvd";
    private static final String INDEX_PREFIX = "dvi";
    private static final String TERMS_PREFIX = "dvt";
    private static final String POSITION_PREFIX = "dvp";
    
    public void writeTerms(
        Directory dir,
        String segment,
        Terms terms,
        boolean separateNorms
    ) throws IOException {
        
        // 1. 写入词条数据
        TermsWriter termsWriter = new TermsWriter(dir, segment);
        termsWriter.write(terms);
        
        // 2. 写入位置信息
        PositionWriter positionWriter = new PositionWriter(dir, segment);
        positionWriter.write(terms);
    }
}

public class TermsWriter {
    // 词条词典
    private final BytesRefHash termsHash;
    
    // 倒排列表
    private final PostingsWriter postingsWriter;
    
    public void write(Terms terms) throws IOException {
        // 1. 构建词条词典
        for (TermsEnum enum : terms.iterator()) {
            termsHash.add(enum.term().bytes);
        }
        
        // 2. 写入倒排列表
        for (TermsEnum enum : terms.iterator()) {
            PostingsEnum postings = enum.postings(null);
            postingsWriter.write(postings);
        }
    }
}
```

---

## 3. 查询执行引擎

### 3.1 查询解析

```java
// org.apache.lucene.queryparser.classic

public class QueryParser {
    
    public Query parse(String queryString) throws ParseException {
        // 1. 词法分析
        TokenStream tokens = analyze(queryString);
        
        // 2. 语法分析
        Query query = buildQuery(tokens);
        
        // 3. 优化查询
        query = optimize(query);
        
        return query;
    }
    
    private Query buildQuery(TokenStream tokens) {
        // 递归下降解析
        Query query = null;
        
        while (tokens.nextToken()) {
            Token token = tokens.token();
            
            switch (token.type()) {
                case TERM:
                    query = new TermQuery(new Term(field, token.text()));
                    break;
                case PREFIX:
                    query = new PrefixQuery(new Term(field, token.text()));
                    break;
                case WILDCARD:
                    query = new WildcardQuery(new Term(field, token.text()));
                    break;
                case FUZZY:
                    query = new FuzzyQuery(new Term(field, token.text()));
                    break;
                case AND:
                    query = new BooleanQuery.Builder()
                        .add(left, BooleanClause.Occur.MUST)
                        .add(right, BooleanClause.Occur.MUST)
                        .build();
                    break;
                case OR:
                    query = new BooleanQuery.Builder()
                        .add(left, BooleanClause.Occur.SHOULD)
                        .add(right, BooleanClause.Occur.SHOULD)
                        .build();
                    break;
            }
        }
        
        return query;
    }
}
```

### 3.2 评分机制

```java
// org.apache.lucene.search

public class BM25Similarity extends Similarity {
    
    @Override
    public float score(BPStat stat) {
        // BM25 公式
        float k1 = stat.k1;
        float b = stat.b;
        float tf = stat.tf;
        float df = stat.df;
        float docLen = stat.docLen;
        float avgDocLen = stat.avgDocLen;
        float idf = stat.idf;
        
        // IDF 部分
        float idfTerm = idf.compute(df, stat.numDocs);
        
        // TF 部分
        float tfTerm = tf / (k1 * (1 - b + b * docLen / avgDocLen) + tf);
        
        // BM25 评分
        return idfTerm * tfTerm;
    }
}

public class BM25Stats {
    float k1 = 1.5f;    // 词频饱和度
    float b = 0.75f;    // 长度归一化
}
```

---

## 4. 分段合并

### 4.1 Merge 策略

```java
// org.apache.lucene.index

public class TieredMergePolicy extends MergePolicy {
    
    private int maxMergeAtOnce = 10;
    private float segmentsPerTier = 10.0f;
    private long maxMergeSize = 50L * 1024 * 1024 * 1024; // 50GB
    
    @Override
    public MergeSpecification findMerges(MergeTrigger trigger, 
                                          SegmentCommitInfo info) 
                                          throws IOException {
        
        List<MergeSpec> specs = new ArrayList<>();
        
        // 按段大小分组
        TreeMap<Long, List<SegmentCommitInfo>> bySize = groupBySize(info);
        
        // 对每个大小组执行合并
        for (Map.Entry<Long, List<SegmentCommitInfo>> entry : bySize.entrySet()) {
            List<SegmentCommitInfo> segments = entry.getValue();
            
            if (segments.size() >= segmentsPerTier) {
                // 触发合并
                MergeSpec spec = new MergeSpec(
                    segments.subList(0, maxMergeAtOnce),
                    info.getDelCount() > 0
                );
                specs.add(spec);
            }
        }
        
        return specs.isEmpty() ? null : new MergeSpecification(specs);
    }
}
```

### 4.2 Merge 执行

```java
// org.apache.lucene.index

public class MergeThread extends Thread {
    
    private final IndexWriter writer;
    
    @Override
    public void run() {
        while (!isInterrupted()) {
            try {
                MergeSpecification spec = writer.getNextMerge();
                if (spec == null) {
                    break;
                }
                
                // 执行合并
                MergeTask task = new MergeTask(writer, spec);
                task.merge();
                
            } catch (InterruptedException e) {
                break;
            } catch (IOException e) {
                writer.handleMergeError(e);
            }
        }
    }
}

public class MergeTask {
    
    public void merge() throws IOException {
        // 1. 打开输入段
        List<LeafReader> readers = openReaders();
        
        // 2. 创建合并写入器
        SegmentWriter writer = new SegmentWriter(
            DirectoryReader.open(readers)
        );
        
        // 3. 逐个文档写入
        for (LeafReader reader : readers) {
            TermsEnum termsEnum = reader.terms("content").iterator();
            while (termsEnum.next() != null) {
                PostingsEnum postings = termsEnum.postings(null);
                writer.write(postings);
            }
        }
        
        // 4. 提交合并结果
        writer.commit();
        
        // 5. 刷新到磁盘
        writer.flush();
    }
}
```

---

## 5. 性能优化实战

### 5.1 写入优化

```json
{
  "index": {
    "number_of_shards": 5,
    "number_of_replicas": 1,
    "refresh_interval": "30s",
    "translog": {
      "durability": "async",
      "flush_threshold_size": "1gb"
    }
  }
}
```

### 5.2 查询优化

```json
{
  "query": {
    "constant_score": {
      "filter": {
        "term": {
          "status": "active"
        }
      },
      "boost": 1.0
    }
  }
}
```

### 5.3 监控指标

```bash
# 集群健康
curl -XGET 'http://localhost:9200/_cluster/health?pretty'

# 节点统计
curl -XGET 'http://localhost:9200/_nodes/stats?pretty'

# 索引统计
curl -XGET 'http://localhost:9200/_stats?pretty'
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 | 关键优化点 |
|------|----------|-----------|
| 倒排索引 | Terms + Postings | 分段合并策略 |
| 查询引擎 | Parser + Scorer | 缓存、过滤优化 |
| 分词器 | Analyzer | 自定义分词器 |
| 集群协调 | Master + Coord | 分片分配策略 |

### 6.2 性能调优 Checklist

- [ ] 合理设置分片数
- [ ] 调整 refresh interval
- [ ] 使用 constant_score 缓存
- [ ] 避免深度分页
- [ ] 监控 JVM 内存
- [ ] 定期合并分段

---

*最后更新：2026-08-11*
*作者：Ryan*
