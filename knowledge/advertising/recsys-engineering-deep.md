# 推荐系统深度：工程架构 + 在线学习

> 高并发低延迟的工程实现 + 实时特征 + 在线学习

---

## 第一部分：高并发推荐系统架构

### 整体架构

```
用户请求 (QPS 100K)
    ↓
┌─────────────────────────────────────────────────┐
│                    API Gateway                   │
│              (限流/鉴权/路由)                      │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 用户服务  │ │ 物品服务  │ │ 行为服务  │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │             │            │
         ▼             ▼            ▼
    ┌─────────────────────────────────────┐
    │          推荐服务 (Go)               │
    │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
    │  │召回  │ │粗排 │ │精排  │ │重排  │   │
    │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘   │
    │     │       │        │        │       │
    │     └───────┴────────┴────────┘       │
    └────────────────┬──────────────────────┘
                     │
    ┌────────────────┼──────────────────────┐
    ▼                ▼              ▼        ▼
┌──────┐      ┌──────────┐   ┌──────┐  ┌──────┐
│Redis │      │ FAISS    │   │ES    │  │Kafka │
│缓存  │      │向量索引   │   │特征库 │  │行为流│
└──────┘      └──────────┘   └──────┘  └──────┘
```

### Go 推荐服务实现

```go
package recommendation

import (
    "context"
    "sync"
    "time"
)

// RecommendationService 推荐服务
type RecommendationService struct {
    recall     RecallService
    ranker     Ranker
    reranker   Reranker
    cache      *redis.Client
}

// Recommend 推荐入口
func (s *RecommendationService) Recommend(ctx context.Context, userID string, count int) ([]Item, error) {
    // 1. 检查缓存
    cachedKey := fmt.Sprintf("recommend:%s:%d", userID, count)
    if cached, err := s.getFromCache(ctx, cachedKey); err == nil && len(cached) > 0 {
        return cached, nil
    }
    
    // 2. 并行召回
    var wg sync.WaitGroup
    var mu sync.Mutex
    var allRecalls []Item
    
    routes := []RecallRoute{s.recall.HotRecall, s.recall.CFRecall, s.recall.VectorRecall}
    perRoute := count * 3
    
    for _, route := range routes {
        wg.Add(1)
        go func(r RecallRoute) {
            defer wg.Done()
            items, err := r.Recall(ctx, userID, perRoute)
            if err != nil {
                return
            }
            mu.Lock()
            allRecalls = append(allRecalls, items...)
            mu.Unlock()
        }(route)
    }
    wg.Wait()
    
    // 3. 去重
    allRecalls = deduplicate(allRecalls, perRoute)
    
    // 4. 粗排
    coarse := s.ranker.CoarseRank(allRecalls, count*2)
    
    // 5. 精排
    fine := s.ranker.FineRank(ctx, coarse, count*5)
    
    // 6. 重排
    result := s.reranker.Rerank(fine, count)
    
    // 7. 写缓存
    s.setCache(ctx, cachedKey, result, 5*time.Minute)
    
    return result, nil
}
```

### 性能优化策略

| 优化项 | 方案 | 效果 |
|--------|------|------|
| **多级缓存** | L1 (本地) + L2 (Redis) + L3 (DB) | 命中率 90%+ |
| **异步预取** | 预测用户下一个请求，提前加载 | 延迟降低 50% |
| **连接池** | DB/Redis 连接池 | QPS 提升 3x |
| **批量请求** | 合并多次请求 | 网络开销减少 |
| **CDN** | 静态物品信息 CDN | 首屏加载 < 100ms |

---

## 第二部分：实时特征

### 实时特征管道

```
用户行为 → Kafka → Flink → Redis → 推荐服务

1. 用户点击物品
2. 行为日志 → Kafka (实时)
3. Flink 流处理：
   - 实时聚合（最近 1 小时点击）
   - 特征计算（CTR、CVR）
   - 更新 Redis
4. 推荐服务读取 Redis 实时特征
5. 延迟：< 100ms
```

### Flink 实时特征计算

```go
// Flink Job: 实时用户行为聚合
type UserBehaviorAggregator struct {
    kafkaSource *KafkaSource
    redisSink   *RedisSink
}

func (a *UserBehaviorAggregator) Execute(ctx context.Context) error {
    stream := a.kafkaSource
        .keyBy(func(event BehaviorEvent) string { return event.UserID })
        .window(TumblingEventTimeWindows.of(time.Minute))
        .aggregate(func(windowEvents []BehaviorEvent) UserFeatures {
            return UserFeatures{
                ClickCount:    len(windowEvents),
                CategorySet:   extractCategories(windowEvents),
                AvgPosition:   avgPosition(windowEvents),
                TimeSpent:     totalTimeSpent(windowEvents),
            }
        })
        .addSink(a.redisSink)
    
    return stream.Execute()
}
```

---

## 第三部分：在线学习

### 为什么需要在线学习？

```
离线训练的问题：
1. 模型滞后：训练数据是昨天的，用户兴趣是今天的
2. 概念漂移：用户兴趣随时间变化
3. 冷启动：新物品没有历史数据

在线学习解决方案：
1. 实时更新模型参数
2. 实时捕捉用户兴趣变化
3. 快速适应新物品
```

### 在线学习架构

```
实时数据流：
用户行为 → Kafka → Flink → Online Model Update

1. 用户点击物品
2. 实时计算特征
3. 更新模型参数（增量学习）
4. 模型热更新（不重启服务）
```

### 增量学习实现

```go
// 简化版在线学习：实时更新物品热度
type OnlineLearner struct {
    redisClient *redis.Client
    decayRate   float64
}

func (l *OnlineLearner) Update(userID string, itemID string, reward float64) {
    // 1. 更新用户-物品交互
    l.redisClient.ZIncrBy(context.Background(),
        fmt.Sprintf("user_items:%s", userID),
        reward,
        itemID,
    )
    
    // 2. 更新物品热度
    l.redisClient.ZIncrBy(context.Background(),
        "global_hot",
        reward,
        itemID,
    )
    
    // 3. 更新物品类目热度
    category := l.getItemCategory(itemID)
    l.redisClient.ZIncrBy(context.Background(),
        fmt.Sprintf("category_hot:%s", category),
        reward,
        itemID,
    )
}

func (l *OnlineLearner) GetHotItems(category string, limit int) []Item {
    return l.redisClient.ZRevRangeWithScores(
        context.Background(),
        fmt.Sprintf("category_hot:%s", category),
        0,
        int64(limit-1),
    ).Val()
}
```

---

## 第四部分：A/B 测试框架

### 实验设计

```go
type ABTest struct {
    name    string
    variants map[string]float64 // variant -> weight
    metrics []string
}

func (t *ABTest) Assign(userID string) string {
    // 确定性分配：相同用户永远相同 variant
    hash := hash(userID + t.name)
    bucket := hash % 100
    
    var current float64
    for variant, weight := range t.variants {
        current += weight
        if float64(bucket) < current {
            return variant
        }
    }
    return ""
}

func (t *ABTest) RecordMetric(userID string, metric string, value float64) {
    // 记录指标到 Kafka
    event := ExperimentEvent{
        UserID: userID,
        Test:   t.name,
        Variant: t.Assign(userID),
        Metric: metric,
        Value:  value,
    }
    t.kafkaProducer.Send(event)
}
```

### 显著性检验

```go
// 双样本 T 检验
func TTest(groupA, groupB []float64) (float64, float64) {
    meanA, stdA := meanStd(groupA)
    meanB, stdB := meanStd(groupB)
    
    nA, nB := len(groupA), len(groupB)
    se := math.Sqrt(stdA*stdA/float64(nA) + stdB*stdB/float64(nB))
    
    tScore := (meanA - meanB) / se
    
    // 简化 p-value 计算
    pValue := 2 * (1 - cdfT(tScore))
    
    return tScore, pValue
}
```

---

## 第五部分：监控与告警

### 关键监控指标

| 指标 | 阈值 | 告警级别 |
|------|------|---------|
| **QPS** | < 1K | Warning |
| **P99 延迟** | > 100ms | Critical |
| **错误率** | > 1% | Critical |
| **缓存命中率** | < 80% | Warning |
| **AUC** | 下降 > 5% | Warning |
| **CTR** | 下降 > 3% | Critical |

### 日志系统

```
推荐服务日志：
- 请求日志：userID, timestamp, latency, variant
- 行为日志：userID, itemID, action, position
- 错误日志：error, stack trace

日志采集：
- Logstash → Kafka → Elasticsearch → Kibana
- 实时告警：Prometheus + AlertManager
```

---

## 第六部分：总结

### 推荐系统完整技术栈

| 层级 | 技术选型 | 延迟要求 |
|------|---------|---------|
| **召回** | FAISS + Redis + ES | < 5ms |
| **粗排** | LR / 小树模型 | < 5ms |
| **精排** | DeepFM / DIN / MMOE | < 50ms |
| **重排** | MMR + 业务规则 | < 5ms |
| **特征** | Flink + Redis | < 100ms |
| **在线学习** | 增量更新 + 热更新 | 实时 |

### 性能目标

| 指标 | 目标值 |
|------|--------|
| QPS | 100K+ |
| P99 延迟 | < 50ms |
| 缓存命中率 | > 90% |
| AUC 提升 | +0.5%+ |
| CTR 提升 | +2%+ |
