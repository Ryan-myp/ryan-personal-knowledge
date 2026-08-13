# Elasticsearch聚合查询 - 资深专家深度实现

## 一、聚合类型

### 1.1 指标聚合

```json
{
  "aggs": {
    "avg_price": { "avg": { "field": "price" } },
    "total_sales": { "sum": { "field": "sales" } },
    "price_stats": { "stats": { "field": "price" } }
  }
}
```

### 1.2 桶聚合

```json
{
  "aggs": {
    "group_by_category": {
      "terms": {
        "field": "category",
        "size": 10
      }
    }
  }
}
```

## 二、嵌套聚合

```json
{
  "aggs": {
    "categories": {
      "terms": { "field": "category" },
      "aggs": {
        "avg_price": { "avg": { "field": "price" } },
        "price_distribution": {
          "histogram": {
            "field": "price",
            "interval": 100
          }
        }
      }
    }
  }
}
```

## 三、性能优化

```yaml
# 索引调优
index:
  number_of_shards: 5
  number_of_replicas: 1
  refresh_interval: 30s
  
# 查询优化
search:
  max_buckets: 10000
  composite_size: 1000
```

## 四、面试高频题

### Q1: Terms聚合和Histogram聚合的区别？

```
A: Terms按关键字分桶，Histogram按数值区间分桶。
```

### Q2: 如何处理大聚合场景？

```
A: 使用composite aggregation分页查询。
```

## 五、自测题

1. 设计一个商品分析聚合查询
2. 如何实现多指标聚合？

---

## 参考文档

- [ES聚合文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations.html)
