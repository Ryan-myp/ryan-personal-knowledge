# Elasticsearch聚合查询 - 资深专家深度实现

## 一、聚合类型

### 1.1 指标聚合

```json
{
  "aggs": {
    "avg_price": { "avg": { "field": "price" } },
    "total_sales": { "sum": { "field": "sales" } },
    "max_price": { "max": { "field": "price" } },
    "min_price": { "min": { "field": "price" } },
    "stats_price": { "stats": { "field": "price" } }
  }
}
```

### 1.2 桶聚合

```json
{
  "aggs": {
    "groups": {
      "terms": {
        "field": "category",
        "size": 10
      }
    }
  }
}
```

## 二、复杂聚合

### 2.1 嵌套聚合

```json
{
  "aggs": {
    "groups": {
      "terms": { "field": "category" },
      "aggs": {
        "avg_price": { "avg": { "field": "price" } },
        "price_stats": { "stats": { "field": "price" } }
      }
    }
  }
}
```

### 2.2 日期直方图

```json
{
  "aggs": {
    "sales_over_time": {
      "date_histogram": {
        "field": "created_at",
        "fixed_interval": "1d",
        "format": "yyyy-MM-dd"
      },
      "aggs": {
        "total_sales": { "sum": { "field": "sales" } }
      }
    }
  }
}
```

### 2.3 范围聚合

```json
{
  "aggs": {
    "price_ranges": {
      "range": {
        "field": "price",
        "ranges": [
          { "to": 100 },
          { "from": 100, "to": 500 },
          { "from": 500 }
        ]
      }
    }
  }
}
```

## 三、性能优化

### 3.1 字段类型选择

```
推荐类型:
- 数值: keyword (精确匹配)
- 文本: text (全文检索) + keyword (精确匹配)
- 日期: date
- 地理: geo_point
- 二进制: binary
```

### 3.2 聚合优化

```json
{
  "aggs": {
    "categories": {
      "terms": {
        "field": "category",
        "size": 10,
        "execution_hint": "map"  // 小基数用map
      }
    }
  }
}
```

## 四、Go客户端

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

func NewESClient(addr string) (*ESClient, error) {
	client, err := elastic.NewClient(elastic.SetURL(addr))
	if err != nil {
		return nil, err
	}
	return &ESClient{client: client}, nil
}

func (c *ESClient) Aggregation(query elastic.Query) (*elastic.SearchResult, error) {
	res, err := c.client.Search(c.index).
		Query(query).
		Size(0).
		Do(context.Background())
	return res, err
}
```

## 五、面试高频题

### Q1: ES和MySQL有什么区别？

```
A:
ES: 倒排索引，适合全文搜索
MySQL: B+树，适合事务处理
```

### Q2: 如何优化ES查询性能？

```
A:
1. 使用filter替代query
2. 避免深层分页
3. 合理设置分片数
```

## 六、自测题

1. 如何实现多维度聚合？
2. ES的分片和副本有什么区别？

---

## 参考文档

- [ES官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/aggregations.html)
