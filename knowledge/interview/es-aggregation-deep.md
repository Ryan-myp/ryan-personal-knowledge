# ES聚合查询 - 资深专家深度实现

## 一、聚合类型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Elasticsearch 聚合类型                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   类型                | 用途                                    │
│   ────────────────────┼──────────────────────────────────────────────│
│   Metric              | 数值计算 (avg, sum, max, min)              │
│   Bucket              | 分组统计 (terms, date_histogram)           │
│   Pipeline            | 基于其他聚合 (moving_avg, derivative)       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、聚合查询实现

```json
{
  "size": 0,
  "query": {
    "term": {
      "status": "active"
    }
  },
  "aggs": {
    "by_category": {
      "terms": {
        "field": "category",
        "size": 10
      },
      "aggs": {
        "avg_price": {
          "avg": {
            "field": "price"
          }
        },
        "price_stats": {
          "stats": {
            "field": "price"
          }
        }
      }
    },
    "sales_over_time": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "day"
      },
      "aggs": {
        "total_sales": {
          "sum": {
            "field": "amount"
          }
        }
      }
    }
  }
}
```

## 三、面试高频题

### Q1: 聚合的性能优化？

```
A:
1. 限制聚合深度
2. 使用doc_values
3. 预聚合数据
```

### Q2: 如何处理大分页？

```
A:
1. search_after
2. 游标分页
3. 限制结果集
```

## 四、自测题

1. 解释聚合类型
2. 如何实现嵌套聚合？
3. 如何优化性能？

---

## 参考文档

- [ES Aggregations](https://www.elastic.co/guide/en/elasticsearch/reference/current/aggregations.html)
- [ES Query DSL](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html)
