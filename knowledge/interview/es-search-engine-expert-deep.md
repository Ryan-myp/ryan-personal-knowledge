# ES搜索引擎架构 - 资深专家深度实现

## 一、核心架构

### 1.1 倒排索引

```
正向索引: Document → Terms
倒排索引: Terms → Documents

示例:
Document 1: "The quick brown fox"
Document 2: "The quick red dog"

倒排索引:
"the"  → [Doc1, Doc2]
"quick" → [Doc1, Doc2]
"brown" → [Doc1]
"fox"   → [Doc1]
"red"   → [Doc2]
"dog"   → [Doc2]
```

### 1.2 Lucene结构

```
┌─────────────────────────────────────────────────────┐
│  Index (索引库)                                        │
│  ├── Segment 1                                      │
│  │   ├── .fn (Field Info)                          │
│  │   ├── .fdt (Fields Data)                         │
│  │   ├── .pos (Position)                           │
│  │   ├── .tim (Term Info)                          │
│  │   └── .tif (Term Index)                         │
│  ├── Segment 2                                      │
│  └── ...                                            │
└─────────────────────────────────────────────────────┘
```

## 二、查询优化

### 2.1 Filter vs Query

```json
// Filter: 缓存结果，不计算相关性
{
  "query": {
    "bool": {
      "filter": [
        { "term": { "status": "active" } },
        { "range": { "price": { "gte": 100 } } }
      ],
      "must": [
        { "match": { "description": "laptop" } }
      ]
    }
  }
}
```

### 2.2 分页优化

```json
// 深分页问题
{
  "query": { "match_all": {} },
  "from": 10000,
  "size": 10
}

// 解决方案: search_after
{
  "query": { "match_all": {} },
  "search_after": [1645678901234, "doc_id"],
  "size": 10
}
```

## 三、分词器

### 3.1 内置分词器

```json
// standard: 按非字母切分
// keyword: 不分词
// whitespace: 按空格切分
// english: 英语语言分析
// chinese: 中文分词 (IK)
```

### 3.2 IK分词器配置

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "ik_max_word": {
          "tokenizer": "ik_max_word"
        }
      }
    }
  }
}
```

## 四、Go集成

```go
package elasticsearch

import (
	"context"
	"github.com/olivere/elastic"
)

type ESClient struct {
	client *elastic.Client
	index  string
}

func NewClient(addr string) (*ESClient, error) {
	client, err := elastic.NewClient(elastic.SetURL(addr))
	if err != nil {
		return nil, err
	}
	return &ESClient{client: client}, nil
}

func (c *ESClient) Index(doc ID, data interface{}) error {
	_, err := c.client.Index(c.index).
		Id(doc).
		BodyJson(data).
		Do(context.Background())
	return err
}

func (c *ESClient) Search(query elastic.Query) (*elastic.SearchResult, error) {
	return c.client.Search(c.index).
		Query(query).
		Do(context.Background())
}
```

## 五、面试高频题

### Q1: ES为什么快？

```
A:
1. 倒排索引
2. 列式存储
3. 缓存机制
4. 并行查询
```

### Q2: 如何处理海量数据？

```
A:
1. 合理分片
2. 冷热分离
3. 索引生命周期管理
```

## 六、自测题

1. 解释倒排索引原理
2. 如何优化深分页？

---

## 参考文档

- [ES官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
