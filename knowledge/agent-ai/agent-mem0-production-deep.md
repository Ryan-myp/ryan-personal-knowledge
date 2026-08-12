# AgentMemory 生产实践深度实现 - 三层记忆架构

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/记忆系统  
> **代码密度**: 32%

---

## 一、三层记忆架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AgentMemory 三层架构                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  L1: 短期记忆 (Semantic Cache)                              │   │
│  │  • 存储: Redis / Memcached                                 │   │
│  │  • TTL: 1-24 小时                                          │   │
│  │  • 用途: 对话上下文/最近问答                                │   │
│  │  • 大小: 100-1000 条                                       │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  L2: 中期记忆 (Vector DB)                                   │   │
│  │  • 存储: Qdrant / Milvus / Pinecone                        │   │
│  │  • TTL: 30-90 天                                           │   │
│  │  • 用途: 用户偏好/历史经验/技能沉淀                        │   │
│  │  • 大小: 10K-100K 条                                       │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  L3: 长期记忆 (Knowledge Graph)                             │   │
│  │  • 存储: Neo4j / Dgraph / ArangoDB                         │   │
│  │  • TTL: 永久                                              │   │
│  │  • 用途: 知识图谱/实体关系/事实沉淀                        │   │
│  │  • 大小: 100K-1M 条                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  遗忘曲线:                                                         │
│  L1: 指数衰减 (遗忘快)  → 自动淘汰                                 │
│  L2: 对数衰减 (遗忘慢)  → 按需复习                                 │
│  L3: 稳定保留 (几乎不遗忘) → 定期验证                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、L1 短期记忆

```go
// memory/l1_shortterm.go
package memory

import (
    "context"
    "github.com/redis/go-redis/v9"
    "time"
)

// ShortTermMemory 短期记忆 (语义缓存)
type ShortTermMemory struct {
    rdb  *redis.Client
    TTL  time.Duration
}

// NewShortTermMemory 创建短期记忆
func NewShortTermMemory(rdb *redis.Client, ttl time.Duration) *ShortTermMemory {
    return &ShortTermMemory{rdb: rdb, TTL: ttl}
}

// Save 保存记忆
func (m *ShortTermMemory) Save(ctx context.Context, key string, value interface{}) error {
    return m.rdb.Set(ctx, key, value, m.TTL).Err()
}

// Get 获取记忆
func (m *ShortTermMemory) Get(ctx context.Context, key string) (string, error) {
    return m.rdb.Get(ctx, key).Result()
}

// Delete 删除记忆
func (m *ShortTermMemory) Delete(ctx context.Context, key string) error {
    return m.rdb.Del(ctx, key).Err()
}

// Evict 淘汰策略 (LRU)
func (m *ShortTermMemory) Evict(ctx context.Context, maxItems int) error {
    // 扫描所有 key
    cursor := uint64(0)
    count := 0
    
    for {
        keys, newCursor := m.rdb.Scan(ctx, cursor, "memory:*", 100).Result()
        cursor = newCursor
        
        for _, key := range keys {
            exists, _ := m.rdb.Exists(ctx, key).Result()
            if exists == 0 {
                m.rdb.Del(ctx, key)
                count++
                if count >= len(keys)-maxItems {
                    return nil
                }
            }
        }
        
        if cursor == 0 {
            break
        }
    }
    return nil
}
```

---

## 三、L2 中期记忆 (向量检索)

```go
// memory/l2_vector.go
package memory

import (
    "context"
    "github.com/qdrant/qdrant-client-go/qdrant"
)

// VectorMemory 向量记忆 (中期)
type VectorMemory struct {
    client *qdrant.QdrantClient
    collection string
    dim int
}

// NewVectorMemory 创建向量记忆
func NewVectorMemory(client *qdrant.QdrantClient, collection string, dim int) *VectorMemory {
    return &VectorMemory{
        client: client,
        collection: collection,
        dim: dim,
    }
}

// Store 存储记忆
func (m *VectorMemory) Store(ctx context.Context, id string, vector []float32, payload map[string]interface{}) error {
    point := &qdrant.PointStruct{
        Id: &qdrant.PointId{Num: uint64(id)},
        Vector: vector,
        Payload: payload,
    }
    _, err := m.client.Upsert(ctx, &qdrant.UpsertPoints{
        CollectionName: m.collection,
        Points: []*qdrant.PointStruct{point},
    })
    return err
}

// Search 搜索记忆
func (m *VectorMemory) Search(ctx context.Context, query []float32, limit int) ([]MemoryItem, error) {
    results, err := m.client.Query(ctx, &qdrant.QueryPoints{
        CollectionName: m.collection,
        Query: &qdrant.QuantumSerialization{Vector: query},
        Limit: uint64(limit),
    })
    if err != nil {
        return nil, err
    }
    
    items := make([]MemoryItem, 0, len(results))
    for _, r := range results {
        items = append(items, MemoryItem{
            ID:       r.Id.Num,
            Score:    r.Score,
            Payload:  r.Payload,
        })
    }
    return items, nil
}

type MemoryItem struct {
    ID      uint64
    Score   float64
    Payload map[string]interface{}
}
```

---

## 四、L3 长期记忆 (知识图谱)

```go
// memory/l3_kg.go
package memory

import (
    "context"
    "github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

// KnowledgeGraph 知识图谱 (长期)
type KnowledgeGraph struct {
    driver neo4j.Driver
}

// NewKnowledgeGraph 创建知识图谱
func NewKnowledgeGraph(uri, user, password string) (*KnowledgeGraph, error) {
    driver, err := neo4j.NewDriver(uri, neo4j.BasicAuth(user, password, ""))
    if err != nil {
        return nil, err
    }
    return &KnowledgeGraph{driver: driver}, nil
}

// AddEntity 添加实体
func (kg *KnowledgeGraph) AddEntity(ctx context.Context, name, entityType string) error {
    session := kg.driver.NewSession(neo4j.SessionConfig{AccessMode: neo4j.Write})
    defer session.Close()
    
    _, err := session.Run(ctx, 
        "CREATE (e:`"+entityType+"` {name: $name}) RETURN e",
        map[string]interface{}{"name": name},
    )
    return err
}

// AddRelation 添加关系
func (kg *KnowledgeGraph) AddRelation(ctx context.Context, from, to, relation string) error {
    session := kg.driver.NewSession(neo4j.SessionConfig{AccessMode: neo4j.Write})
    defer session.Close()
    
    _, err := session.Run(ctx,
        "MATCH (a {name: $from}), (b {name: $to}) CREATE (a)-[r:`"+relation+"`]->(b) RETURN r",
        map[string]interface{}{"from": from, "to": to},
    )
    return err
}

// Query 查询
func (kg *KnowledgeGraph) Query(ctx context.Context, pattern string) ([]map[string]interface{}, error) {
    session := kg.driver.NewSession(neo4j.SessionConfig{AccessMode: neo4j.Read})
    defer session.Close()
    
    result, err := session.Run(ctx, pattern, nil)
    if err != nil {
        return nil, err
    }
    return result.Collect()
}
```

---

## 五、遗忘曲线

```go
// memory/forgetting_curve.go
package memory

import "time"

// ForgettingCurve 艾宾浩斯遗忘曲线
type ForgettingCurve struct{}

// CalculateRetention 计算保留率
func (fc *ForgettingCurve) CalculateRetention(hoursSinceCreation float64) float64 {
    // Ebbinghaus 公式: R = e^(-t/S)
    // S = 睡眠周期 (约 24h)
    // t = 时间 (小时)
    s := 24.0
    retention := math.Exp(-hoursSinceCreation / s)
    return retention
}

// ShouldForget 判断是否应该遗忘
func (fc *ForgettingCurve) ShouldForget(hoursSinceCreation float64, threshold float64) bool {
    retention := fc.CalculateRetention(hoursSinceCreation)
    return retention < threshold
}

// ScheduleReview 安排复习时间
func (fc *ForgettingCurve) ScheduleReview(hoursSinceCreation float64) time.Time {
    // 复习间隔: 1h, 24h, 7d, 30d
    intervals := []float64{1, 24, 168, 720}
    for _, interval := range intervals {
        if hoursSinceCreation < interval {
            return time.Now().Add(time.Duration(interval) * time.Hour)
        }
    }
    return time.Now().Add(720 * time.Hour)
}
```

---

## 六、自测题

1. **为什么需要三层架构？**
   - 不同层级对应不同的记忆容量和访问速度需求

2. **遗忘曲线的实际作用？**
   - 自动淘汰低价值记忆，释放存储资源

