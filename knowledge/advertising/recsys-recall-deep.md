# 推荐系统深度：召回层（Recall）— 多路召回/向量召回/规则召回

> 从百万/千万级候选集中快速筛选出千级候选，是推荐系统的"漏斗第一层"

---

## 第一部分：召回的本质

### 为什么需要召回？

```
推荐系统漏斗：
用户请求 → 召回层（1000万 → 1000）→ 粗排层（1000 → 200）→ 精排层（200 → 50）→ 重排层（50 → 10）→ 展示

没有召回的问题：
1. 候选集太大，无法对所有候选做精细排序
2. 精排模型复杂（DIN/多塔），单次推理 10-50ms，1000 万候选 = 100 小时
3. 召回层必须在 5-10ms 内完成，为后续层留出时间

核心矛盾：
- 召回要快（毫秒级）
- 召回要准（覆盖用户可能感兴趣的物品）
```

### 召回的核心指标

| 指标 | 含义 | 典型值 |
|------|------|--------|
| **召回率@K** | 用户真正喜欢的物品有多少被召回 | 30-60% |
| **覆盖率** | 召回层能覆盖多少比例的物品 | > 80% |
| **新颖性** | 召回的物品是否都是热门 | 越低越好 |
| **延迟** | 召回层总耗时 | < 10ms |
| **QPS** | 每秒处理的请求数 | 10K-100K |

---

## 第二部分：多路召回架构

### 整体架构

```
                    ┌─────────────┐
                    │  用户请求    │
                    │  uid, context│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ 热门召回  │ │ 协同召回  │ │ 向量召回  │
        │ Hot      │ │ CF       │ │ Embedding│
        └────┬─────┘ └────┬─────┘ └────┬─────┘
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ 行为召回  │ │ 内容召回  │ │ 规则召回  │
        │ Behavior │ │ Content  │ │ Rule     │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │  去重融合    │
                    │ Dedup + Fuse│
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  候选集 K    │
                    │  ~1000 items│
                    └─────────────┘
```

### 各路召回详解

#### 1. 热门召回（Hot Recall）

```go
// 热门召回：基于全局热度 + 时间衰减
type HotRecall struct {
    redisClient *redis.Client
    decayRate   float64 // 时间衰减速率
}

func (h *HotRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    // 1. 从 Redis Sorted Set 获取全局热门
    key := "hot:global"
    items := h.redisClient.ZRevRangeWithScores(ctx, key, 0, int64(limit-1)).Val()
    
    // 2. 应用时间衰减
    now := time.Now()
    var results []Item
    for _, item := range items {
        score := item.Score * math.Exp(-h.decayRate*now.Sub(item.Member.(time.Time)).Hours())
        results = append(results, Item{
            ID:   item.Member.(string),
            Score: score,
        })
    }
    
    return results, nil
}
```

**关键点**：
- 使用 Redis ZSET 存储热度分，天然支持排序
- 时间衰减防止"老热门"一直霸榜
- 冷启动用户（新用户/无行为）的兜底策略

#### 2. 协同过滤召回（CF Recall）

```go
// 基于物品的协同过滤（ItemCF）
type ItemCFRecall struct {
    cache     *redis.Client
    graphDB   *neo4j.Client // 物品相似度图
}

func (i *ItemCFRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    // 1. 获取用户历史行为物品
    userItems := i.getUserHistory(ctx, userID)
    
    // 2. 对每个历史物品，找相似物品
    var candidates map[string]float64 // itemID -> score
    
    for _, item := range userItems {
        // 从图数据库获取 Top-K 相似物品
        similarItems := i.graphDB.GetSimilarItems(ctx, item.ID, limit*2)
        
        for _, sim := range similarItems {
            candidates[sim.ID] += sim.Similarity * item.Weight
        }
    }
    
    // 3. 排序取 Top-K
    sorted := sortByScore(candidates)
    return sorted[:limit], nil
}
```

**关键点**：
- ItemCF 比 UserCF 更稳定（物品变化慢于用户）
- 相似度用余弦相似度或改进的 Jaccard
- 离线预计算物品相似度矩阵，在线查表

#### 3. 向量召回（Vector Recall / ANN）

```go
// 基于向量相似度的召回（使用 FAISS）
type VectorRecall struct {
    faissIndex  *faiss.IndexIDMap // IVF_PQ 索引
    embedder    *EmbeddingService // 用户/物品 embedding
}

func (v *VectorRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    // 1. 获取用户 embedding
    userVec := v.embedder.GetUserEmbedding(ctx, userID)
    
    // 2. FAISS 近似最近邻搜索
    // D: 维度, K: 召回数量
    distances, indices := v.faissIndex.Search(userVec, int64(limit))
    
    // 3. 返回物品列表
    var results []Item
    for i := 0; i < len(indices[0]); i++ {
        if indices[0][i] >= 0 { // -1 表示无效
            results = append(results, Item{
                ID:    int(indices[0][i]),
                Score: float32(distances[0][i]),
            })
        }
    }
    
    return results, nil
}
```

**FAISS 索引类型对比**：

| 索引类型 | 精度 | 速度 | 内存 | 适用场景 |
|---------|------|------|------|---------|
| **Flat** | 100% | 慢 | 大 | 小规模（< 100K） |
| **IVF** | 90-95% | 快 | 中 | 大规模，可调节精度 |
| **PQ** | 80-90% | 很快 | 小 | 超大规模，内存受限 |
| **HNSW** | 95-99% | 快 | 大 | 高精度需求 |
| **IVF_PQ** | 85-95% | 很快 | 小 | **工业界主流** |

**IVF_PQ 工作原理**：
```
1. IVF（倒排索引）：将向量空间划分为 K 个簇，只搜索最近的 N 个簇
2. PQ（乘积量化）：将高维向量分解为多个子空间，每个子空间用码本压缩
   
示例：128 维向量 → 分解为 8 个子空间 × 16 维 → 每个子空间 256 个码字
     内存占用：128×4B = 512B → 8B（压缩 64 倍）
```

#### 4. 行为召回（Behavior Recall）

```go
// 基于用户行为的召回
type BehaviorRecall struct {
    redisClient *redis.Client
}

func (b *BehaviorRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    var results []Item
    
    // 1. 基于浏览历史
    browsed := b.redisClient.ZRevRange(ctx, "user:browsed:"+userID, 0, 10).Val()
    for _, itemID := range browsed {
        // 找同类目物品
        siblings := b.findSiblings(ctx, itemID, limit/3)
        results = append(results, siblings...)
    }
    
    // 2. 基于购买历史
    purchased := b.redisClient.ZRevRange(ctx, "user:purchased:"+userID, 0, 5).Val()
    for _, itemID := range purchased {
        // 找关联物品（购物篮分析）
        related := b.findRelated(ctx, itemID, limit/3)
        results = append(results, related...)
    }
    
    // 3. 基于收藏/点赞
    favorited := b.redisClient.ZRevRange(ctx, "user:favorited:"+userID, 0, 10).Val()
    for _, itemID := range favorited {
        similar := b.findSimilar(ctx, itemID, limit/3)
        results = append(results, similar...)
    }
    
    return deduplicate(results)[:limit], nil
}
```

#### 5. 内容召回（Content-Based Recall）

```go
// 基于物品内容的召回
type ContentRecall struct {
    esClient *elastic.Client // Elasticsearch
}

func (c *ContentRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    // 1. 获取用户偏好标签
    userTags := c.getUserTags(ctx, userID)
    
    // 2. ES 多条件查询
    query := elastic.NewBoolQuery()
    for _, tag := range userTags {
        query.Must(elastic.NewTermQuery("tags", tag))
    }
    query.Must(elastic.NewRangeQuery("price").Gte(userTags.MinPrice).Lte(userTags.MaxPrice))
    query.Must(elastic.NewTermQuery("status", "active"))
    
    searchResult, err := c.esClient.Search().
        Index("items").
        Query(query).
        Size(limit).
        Do(ctx)
    
    // 3. 返回结果
    var results []Item
    for _, hit := range searchResult.Hits.Hits {
        var item Item
        json.Unmarshal(hit.Source, &item)
        results = append(results, item)
    }
    
    return results, nil
}
```

#### 6. 规则召回（Rule-Based Recall）

```go
// 基于业务规则的召回
type RuleRecall struct {
    ruleEngine *RuleEngine
}

func (r *RuleRecall) Recall(ctx context.Context, userID string, limit int) ([]Item, error) {
    userProfile := r.ruleEngine.GetUserProfile(ctx, userID)
    var results []Item
    
    // 规则 1：地域偏好
    if userProfile.Region == "Shanghai" {
        shanghaiItems := r.getRegionalItems(ctx, "Shanghai", 10)
        results = append(results, shanghaiItems...)
    }
    
    // 规则 2：时间段
    hour := time.Now().Hour()
    if hour >= 20 && hour <= 23 {
        // 晚间偏好娱乐内容
        entertainment := r.getCategoryItems(ctx, "entertainment", 10)
        results = append(results, entertainment...)
    }
    
    // 规则 3：新物品曝光
    if userProfile.IsNewUser {
        newItems := r.getNewItems(ctx, 20)
        results = append(results, newItems...)
    }
    
    return deduplicate(results)[:limit], nil
}
```

---

## 第三部分：召回融合与去重

### 多路召回融合策略

```go
type RecallFuser struct {
    weights map[string]float64 // 各路召回权重
}

func (f *RecallFuser) Fuse(ctx context.Context, recalls map[string][]Item, limit int) []Item {
    // 1. 分数归一化
    normalized := make(map[string][]Item)
    for route, items := range recalls {
        normalized[route] = f.normalizeScores(items)
    }
    
    // 2. 加权融合
    scoredMap := make(map[string]float64) // itemID -> weightedScore
    for route, items := range normalized {
        weight := f.weights[route]
        for _, item := range items {
            scoredMap[item.ID] += item.Score * weight
        }
    }
    
    // 3. 排序取 Top-K
    type scoredItem struct {
        ID    string
        Score float64
    }
    var scored []scoredItem
    for id, score := range scoredMap {
        scored = append(scored, scoredItem{id, score})
    }
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].Score > scored[j].Score
    })
    
    // 4. 去重
    seen := make(map[string]bool)
    var results []Item
    for _, s := range scored[:limit] {
        if !seen[s.ID] {
            seen[s.ID] = true
            results = append(results, Item{ID: s.ID, Score: s.Score})
        }
    }
    
    return results
}
```

### 融合权重调优

| 召回路 | 默认权重 | 适用场景 |
|--------|---------|---------|
| 热门 | 0.1 | 冷启动用户 |
| ItemCF | 0.25 | 有行为历史的用户 |
| 向量 | 0.3 | 所有用户（主力） |
| 行为 | 0.15 | 深度行为用户 |
| 内容 | 0.1 | 新品/长尾物品 |
| 规则 | 0.1 | 特定业务场景 |

---

## 第四部分：自测题

### Q1: 为什么向量召回比 ItemCF 更受欢迎？

**A**: 
- ItemCF 依赖显式交互数据（点击/购买），冷启动物品无法参与
- 向量召回通过 embedding 捕捉语义相似性，能推荐从未交互过的物品
- 向量召回支持跨类别推荐（"买了手机的人也看了耳机"）

### Q2: FAISS 的 IVF_PQ 索引如何调参？

**A**:
- **nlist**（簇数）：越大越精确，但内存和查询时间增加。通常取 sqrt(物品数)
- **nprobe**（查询时遍历的簇数）：越大越精确，但延迟增加。通常取 nlist 的 5-10%
- **M**（PQ 子空间数）：越小压缩率越高，但精度下降。通常取 dim/4
- **subQuantizers**（每个子空间的码本大小）：默认 256，可降低到 64 节省内存

### Q3: 如何评估召回层的效果？

**A**:
- **离线指标**：HitRate@K, NDCG@K, MRR
- **在线指标**：CTR, CVR, 停留时长, GMV
- **多样性**：Coverage, Intra-list Similarity
- **新颖性**：Novelty（推荐非热门物品的比例）

---

## 第五部分：动手验证

### 完整召回系统 Demo

```go
package main

import (
    "context"
    "fmt"
    "math"
    "sort"
    "sync"
)

// Item 物品
type Item struct {
    ID    string
    Score float64
}

// RecallRoute 召回路由接口
type RecallRoute interface {
    Name() string
    Recall(ctx context.Context, userID string, limit int) []Item
}

// 热门召回
type HotRecall struct{}

func (h *HotRecall) Name() string { return "hot" }

func (h *HotRecall) Recall(ctx context.Context, userID string, limit int) []Item {
    items := make([]Item, limit)
    for i := 0; i < limit; i++ {
        items[i] = Item{ID: fmt.Sprintf("hot_%d", i), Score: 100.0 - float64(i)*5}
    }
    return items
}

// ItemCF 召回
type ItemCFRecall struct{}

func (i *ItemCFRecall) Name() string { return "itemcf" }

func (i *ItemCFRecall) Recall(ctx context.Context, userID string, limit int) []Item {
    items := make([]Item, limit)
    for i := 0; i < limit; i++ {
        items[i] = Item{ID: fmt.Sprintf("cf_%d", i), Score: 80.0 - float64(i)*3}
    }
    return items
}

// 向量召回
type VectorRecall struct{}

func (v *VectorRecall) Name() string { return "vector" }

func (v *VectorRecall) Recall(ctx context.Context, userID string, limit int) []Item {
    items := make([]Item, limit)
    for i := 0; i < limit; i++ {
        items[i] = Item{ID: fmt.Sprintf("vec_%d", i), Score: 90.0 - float64(i)*2}
    }
    return items
}

// RecallFuser 召回融合器
type RecallFuser struct {
    routes  []RecallRoute
    weights map[string]float64
}

func NewRecallFuser() *RecallFuser {
    return &RecallFuser{
        routes: []RecallRoute{
            &HotRecall{},
            &ItemCFRecall{},
            &VectorRecall{},
        },
        weights: map[string]float64{
            "hot":    0.1,
            "itemcf": 0.25,
            "vector": 0.3,
        },
    }
}

func (f *RecallFuser) Fuse(ctx context.Context, userID string, limit int) []Item {
    var mu sync.Mutex
    scoredMap := make(map[string]float64)
    
    // 并行召回
    var wg sync.WaitGroup
    for _, route := range f.routes {
        wg.Add(1)
        go func(r RecallRoute) {
            defer wg.Done()
            items := r.Recall(ctx, userID, limit*3)
            weight := f.weights[r.Name()]
            
            mu.Lock()
            for _, item := range items {
                scoredMap[item.ID] += item.Score * weight
            }
            mu.Unlock()
        }(route)
    }
    wg.Wait()
    
    // 排序取 Top-K
    type scoredItem struct {
        ID    string
        Score float64
    }
    var scored []scoredItem
    for id, score := range scoredMap {
        scored = append(scored, scoredItem{id, score})
    }
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].Score > scored[j].Score
    })
    
    // 去重
    seen := make(map[string]bool)
    var results []Item
    for _, s := range scored[:limit] {
        if !seen[s.ID] {
            seen[s.ID] = true
            results = append(results, Item{ID: s.ID, Score: math.Round(s.Score*100) / 100})
        }
    }
    
    return results
}

func main() {
    ctx := context.Background()
    fuser := NewRecallFuser()
    
    results := fuser.Fuse(ctx, "user_123", 10)
    
    fmt.Println("=== 召回融合结果 ===")
    for i, item := range results {
        fmt.Printf("%2d. %-15s score: %.2f\n", i+1, item.ID, item.Score)
    }
    
    // 验证并行召回
    fmt.Println("\n=== 并行度测试 ===")
    start := time.Now()
    for i := 0; i < 100; i++ {
        fuser.Fuse(ctx, fmt.Sprintf("user_%d", i), 100)
    }
    elapsed := time.Since(start)
    fmt.Printf("100 次召回融合耗时: %v, 平均: %v\n", elapsed, elapsed/100)
}
```

---

## 第六部分：生产实践

### 1. 冷启动策略

```
新用户/新物品：
1. 新用户 → 热门召回 + 规则召回（人口统计特征）
2. 新物品 → 内容召回 + 探索性推荐（Epsilon-Greedy）
3. 过渡期 → 混合策略，逐步切换到个性化召回
```

### 2. 实时召回

```
实时行为 → 实时更新 embedding → 实时召回
1. 用户点击物品 → 发送 Kafka 消息
2. Flink 实时聚合 → 更新用户画像
3. Redis 实时缓存 → 最新召回结果
4. 延迟：< 100ms
```

### 3. 索引更新

```
离线训练（每天）：
1. 收集用户行为数据
2. 训练 embedding 模型
3. 更新 FAISS 索引
4. 灰度发布

在线增量更新（实时）：
1. 新物品 → 实时计算 embedding
2. 追加到 FAISS 索引
3. 定期重组索引（每周）
```

### 4. 性能优化

| 优化项 | 方案 | 效果 |
|--------|------|------|
| **缓存** | Redis 缓存召回结果 | QPS 提升 10x |
| **预计算** | 离线计算物品相似度 | 在线查表 O(1) |
| **并行** | 多路召回并行执行 | 延迟降低 60% |
| **剪枝** | 早期过滤低分物品 | 计算量减少 40% |
| **CDN** | 热门物品 CDN 分发 | 首屏加载 < 100ms |

---

## 第七部分：与广告系统的关系

### 召回在广告系统中的角色

```
广告请求流程：
1. 用户打开 App
2. 广告请求 → 广告召回层
3. 广告召回：
   - 热门广告（新品推广）
   - 定向召回（地域/兴趣/行为）
   - 向量召回（用户-广告 embedding 匹配）
   - 规则召回（预算充足/高 eCPM）
4. 粗排：快速过滤低质量广告
5. 精排：深度学习模型打分
6. 竞价：RTB 实时竞价
7. 重排：广告+自然内容混排
```

### 广告召回 vs 推荐召回

| 维度 | 推荐系统 | 广告系统 |
|------|---------|---------|
| **候选集** | 百万级物品 | 千级广告主 |
| **目标** | 用户满意度 | eCPM 最大化 |
| **召回策略** | 个性化为主 | 定向 + 个性化 |
| **实时性** | 小时级更新 | 分钟级更新 |
| **冷启动** | 热门兜底 | 预算/定向兜底 |
