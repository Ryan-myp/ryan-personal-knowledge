# MySQL分库分表 - 资深专家深度实现

## 一、分片策略

```go
package sharding

// 分片键选择
type ShardKey string

const (
    UserID ShardKey = "user_id"
    OrderID ShardKey = "order_id"
)

// 分片算法
type ShardAlgorithm interface {
    Shard(key uint64, shards int) int
}

// 一致性Hash
type ConsistentHash struct {
    circle map[int]string
    nodes  []int
}

func (ch *ConsistentHash) Shard(key uint64, shards int) int {
    hash := murmurhash(key) % 1024
    // 查找节点
    for _, n := range ch.nodes {
        if n >= hash {
            return n
        }
    }
    return ch.nodes[0]
}
```

## 二、中间件方案

```yaml
# ShardingSphere配置
spring:
  shardingsphere:
    datasource:
      names: ds0,ds1
      ds0:
        driver-class-name: com.mysql.cj.jdbc.Driver
        url: jdbc:mysql://localhost:3306/db0
      ds1:
        driver-class-name: com.mysql.cj.jdbc.Driver
        url: jdbc:mysql://localhost:3306/db1
    rules:
      sharding:
        tables:
          orders:
            actual-data-nodes: ds$->{0..1}.orders$->{0..1}
            database-strategy:
              hint:
                algorithm-class-name: com.example.HintShardingAlgorithm
            table-strategy:
              inline:
                sharding-column: order_id
                algorithm-expression: orders$->{order_id % 2}
```

## 三、跨库查询

```go
// 分布式查询优化
type DistributedQuery struct {
    shards []string
}

func (dq *DistributedQuery) Query(sql string, params ...any) ([]map[string]any, error) {
    var results []map[string]any
    
    // 并行查询所有分片
    var wg sync.WaitGroup
    mu := sync.Mutex{}
    
    for _, shard := range dq.shards {
        wg.Add(1)
        go func(s string) {
            defer wg.Done()
            conn := GetConnection(s)
            rows, err := conn.Query(sql, params...)
            if err != nil {
                return
            }
            mu.Lock()
            defer mu.Unlock()
            results = append(results, scanRows(rows)...)
        }(shard)
    }
    
    wg.Wait()
    return results, nil
}
```

## 四、面试高频题

### Q1: 如何选择分片键？

```
A:
1. 查询频率高的字段
2. 数据分布均匀的字段
3. 避免跨库JOIN
```

### Q2: 如何解决跨库分页？

```
A:
1. 游标分页
2. 延迟关联
3. 本地分页合并
```

## 五、自测题

1. 解释分片策略
2. 如何实现全局唯一ID？
3. 如何处理跨库事务？

---

## 参考文档

- [ShardingSphere文档](https://shardingsphere.apache.org/)
- [MySQL官方文档](https://dev.mysql.com/doc/)
