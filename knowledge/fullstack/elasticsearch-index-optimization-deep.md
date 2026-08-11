# Elasticsearch 索引优化深度解析

> 深入 Elasticsearch 索引优化：分片策略、映射设计、查询优化。
> 源码级分析，包含生产环境优化案例。
> 适用对象：搜索工程师、数据工程师、后端架构师

---

## 1. 分片策略

### 1.1 分片设计原则

```
┌─────────────────────────────────────────────────────────────┐
│                    分片设计原则                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  分片数量                                                      │
│  ├── 单个分片大小：30GB-50GB 为宜                            │
│  ├── 总分片数 = 总数据量 / 单分片大小                        │
│  └── 避免过多分片（增加资源开销）                              │
│                                                             │
│  主分片 vs 副本分片                                           │
│  ├── 主分片：数据分片，不可变                                  │
│  ├── 副本分片：数据备份，可读可写                              │
│  └── 副本数 = 1-2（根据容灾需求）                            │
│                                                             │
│  分片分布                                                     │
│  ├── 跨节点分布                                              │
│  ├── 避免单节点压力过大                                      │
│  └── 使用分片分配过滤                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现分片计算

```go
// shard_calculator.go

package es

import "math"

type ShardCalculator struct {
    totalSize     int64  // 总数据量 (bytes)
    shardSize     int64  // 单分片大小 (bytes)
    replicaCount  int    // 副本数
}

func NewShardCalculator(totalSize, shardSize int64, replicaCount int) *ShardCalculator {
    return &ShardCalculator{
        totalSize:    totalSize,
        shardSize:    shardSize,
        replicaCount: replicaCount,
    }
}

func (sc *ShardCalculator) Calculate() (primaryShards, totalShards int) {
    // 计算主分片数
    primaryShards = int(math.Ceil(float64(sc.totalSize) / float64(sc.shardSize)))
    
    // 限制分片数范围
    if primaryShards < 1 {
        primaryShards = 1
    }
    if primaryShards > 1000 {
        primaryShards = 1000
    }
    
    // 计算总分片数（主分片 + 副本）
    totalShards = primaryShards * (1 + sc.replicaCount)
    
    return primaryShards, totalShards
}
```

---

## 2. 映射设计

### 2.1 字段类型选择

```
字段类型选择指南：

┌─────────────────────────────────────────────────────────────┐
│  字段类型        │ 适用场景          │ 示例                │
├─────────────────────────────────────────────────────────────┤
│  text           │ 全文检索          │ 文章内容            │
│  keyword        │ 精确匹配          │ 状态、类型          │
│  integer/long   │ 整数              │ 用户ID、数量        │
│  float/double   │ 浮点数            │ 价格、评分          │
│  date           │ 日期时间          │ 创建时间、更新时间   │
│  boolean        │ 布尔值            │ 是否有效            │
│  object         │ 嵌套对象          │ 地址、配置          │
│  nested         │ 嵌套数组          │ 标签列表            │
│  geo_point      │ 地理位置          │ 坐标                │
│  ip             │ IP 地址           │ 用户 IP             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 映射模板

```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_max_word",
        "fields": {
          "keyword": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "status": {
        "type": "keyword"
      },
      "created_at": {
        "type": "date",
        "format": "yyyy-MM-dd HH:mm:ss"
      },
      "price": {
        "type": "float"
      },
      "location": {
        "type": "geo_point"
      }
    }
  }
}
```

---

## 3. 查询优化

### 3.1 查询性能分析

```
查询性能优化策略：

1. 使用 Filter Context
   ├── 不计算评分
   ├── 可利用缓存
   └── 适用于精确匹配

2. 避免 Wildcard 查询
   ├── 前缀通配符性能好
   └── 前缀通配符性能差

3. 优化分页
   ├── 深度分页性能差
   └── 使用 search_after

4. 控制返回字段
   ├── 只返回需要的字段
   └── 使用 _source filtering
```

### 3.2 Go 实现查询优化

```go
// query_optimizer.go

package es

import (
    "context"
    "github.com/olivere/elastic"
)

type QueryOptimizer struct {
    client *elastic.Client
}

func NewQueryOptimizer(client *elastic.Client) *QueryOptimizer {
    return &QueryOptimizer{client: client}
}

// 使用 Filter Context 优化精确匹配
func (q *QueryOptimizer) OptimizedSearch(ctx context.Context, index, query string) (*elastic.SearchResult, error) {
    // 构建 filter query
    filterQuery := elastic.NewBoolQuery().
        Filter(elastic.NewTermQuery("status", "active")).
        Must(elastic.NewQueryStringQuery(query))
    
    // 只返回需要的字段
    result, err := q.client.Search(index).
        Query(filterQuery).
        Source(false).
        SourceIncludes("title", "price", "status").
        Size(10).
        Do(ctx)
    
    return result, err
}

// 使用 search_after 优化分页
func (q *QueryOptimizer) SearchWithAfter(
    ctx context.Context,
    index, query string,
    pageSize int,
    searchAfter []interface{},
) (*elastic.SearchResult, error) {
    result, err := q.client.Search(index).
        Query(elastic.NewQueryStringQuery(query)).
        Size(pageSize).
        SearchAfter(searchAfter...).
        Sort("id", true).
        Do(ctx)
    
    return result, err
}
```

---

## 4. 索引生命周期管理

### 4.1 ILM 策略

```json
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "30d"
          }
        }
      },
      "warm": {
        "min_age": "30d",
        "actions": {
          "shrink": {
            "number_of_shards": 1
          }
        }
      },
      "cold": {
        "min_age": "90d",
        "actions": {
          "freeze": {}
        }
      },
      "delete": {
        "min_age": "180d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

---

## 5. 监控诊断

### 5.1 关键指标

```sql
-- 查看索引状态
GET _cat/indices

-- 查看分片分配
GET _cat/shards

-- 查看节点状态
GET _cat/nodes

-- 查看慢查询
GET /_slowlog/search?level=warn
```

### 5.2 Go 实现监控

```go
// monitor.go

package es

import (
    "github.com/olivere/elastic"
)

type Monitor struct {
    client *elastic.Client
}

func NewMonitor(client *elastic.Client) *Monitor {
    return &Monitor{client: client}
}

func (m *Monitor) GetClusterHealth() (*elastic.ClusterHealthResponse, error) {
    return m.client.ClusterHealth().Do(context.Background())
}

func (m *Monitor) GetIndexStats(index string) (*elastic.IndicesStatsResponse, error) {
    return m.client.IndicesStats(index).Do(context.Background())
}

func (m *Monitor) GetNodeStats() (*elastic.CatNodesResponse, error) {
    return m.client.CatNodes().Do(context.Background())
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 分片 | 数据分片+副本 |
| 映射 | 字段类型设计 |
| 查询 | Filter/Query分离 |
| ILM | 生命周期管理 |

### 6.2 最佳实践

- [ ] 合理设置分片数
- [ ] 使用 Filter Context
- [ ] 避免深度分页
- [ ] 配置 ILM 策略
- [ ] 监控关键指标

---

*最后更新：2026-08-11*
*作者：Ryan*
