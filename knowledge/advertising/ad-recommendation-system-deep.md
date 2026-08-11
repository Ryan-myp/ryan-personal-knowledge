# 广告推荐系统深度解析

> 深入广告推荐系统：召回、排序、重排、冷启动、多目标优化。
> 包含真实生产环境推荐系统架构设计。
> 适用对象：推荐系统工程师、算法工程师

---

## 1. 推荐系统架构

### 1.1 整体架构

```
广告推荐系统架构：

┌─────────────────────────────────────────────────────────────┐
│                    推荐系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  召回层 (Recall)                                             │
│  ├── 规则召回                                                │
│  ├── 协同过滤召回                                            │
│  ├── 向量召回 (Embedding)                                   │
│  └── 热门召回                                                │
│                                                             │
│  预排序层 (Pre-ranking)                                      │
│  ├── 粗排模型                                                │
│  └── 快速筛选                                                │
│                                                             │
│  精排序层 (Ranking)                                          │
│  ├── 特征工程                                                │
│  ├── 排序模型 (DeepFM/DCN)                                  │
│  └── 分数计算                                                │
│                                                             │
│  重排层 (Re-ranking)                                         │
│  ├── 业务规则过滤                                            │
│  ├── 多样性调整                                              │
│  └── 频控处理                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现推荐系统核心

```go
// recommendation_system.go

package ad

import (
    "context"
    "sync"
)

type RecommendationSystem struct {
    recall    *RecallEngine
    preRank   *PreRanker
    rank      *Ranker
    rerank    *Reranker
    config    *Config
}

type Config struct {
    RecallCount    int
    PreRankCount   int
    RankCount      int
    RerankCount    int
    DiversityWeight float64
}

type UserContext struct {
    UserID     string
    Interests  []string
    History    []HistoryItem
    Demographics map[string]interface{}
}

type AdCandidate struct {
    AdID       string
    Score      float64
    Features   map[string]float64
    CreativeID string
}

func NewRecommendationSystem(config *Config) *RecommendationSystem {
    return &RecommendationSystem{
        recall:  NewRecallEngine(),
        preRank: NewPreRanker(),
        rank:    NewRanker(),
        rerank:  NewReranker(config),
        config:  config,
    }
}

func (rs *RecommendationSystem) Recommend(ctx context.Context, user *UserContext, context *AdContext) ([]AdCandidate, error) {
    // 1. 召回
    candidates := rs.recall.Recall(ctx, user, context, rs.config.RecallCount)
    
    // 2. 预排序
    preRanked := rs.preRank.PreRank(ctx, candidates, rs.config.PreRankCount)
    
    // 3. 精排序
    ranked := rs.rank.Rank(ctx, preRanked)
    
    // 4. 重排
    final := rs.rerank.Rerank(ctx, ranked, user, rs.config.RerankCount)
    
    return final, nil
}
```

---

## 2. 召回引擎

### 2.1 召回策略

```
召回策略：

├── 规则召回
│   ├── 定向规则匹配
│   ├── 资质筛选
│   └── 黑白名单
│
├── 协同过滤召回
│   ├── Item-CF (相似广告)
│   └── User-CF (相似用户)
│
├── 向量召回
│   ├── Embedding 模型
│   ├── ANN 检索 (Faiss)
│   └── 向量相似度计算
│
└── 热门召回
    ├── 实时热门
    └── 长期热门
```

### 2.2 Go 实现召回引擎

```go
// recall_engine.go

package ad

import (
    "context"
    "sort"
)

type RecallEngine struct {
    ruleRecall    *RuleRecall
    cfRecall      *CFRecall
    vectorRecall  *VectorRecall
    hotRecall     *HotRecall
}

func NewRecallEngine() *RecallEngine {
    return &RecallEngine{
        ruleRecall:   NewRuleRecall(),
        cfRecall:     NewCFRecall(),
        vectorRecall: NewVectorRecall(),
        hotRecall:    NewHotRecall(),
    }
}

func (re *RecallEngine) Recall(ctx context.Context, user *UserContext, context *AdContext, limit int) []AdCandidate {
    var candidates []AdCandidate
    
    // 规则召回
    ruleAds := re.ruleRecall.Rec call(ctx, user, context)
    candidates = append(candidates, ruleAds...)
    
    // 协同过滤召回
    cfAds := re.cfRecall.Recall(ctx, user)
    candidates = append(candidates, cfAds...)
    
    // 向量召回
    vectorAds := re.vectorRecall.Recall(ctx, user)
    candidates = append(candidates, vectorAds...)
    
    // 热门召回
    hotAds := re.hotRecall.Recall(ctx, context)
    candidates = append(candidates, hotAds...)
    
    // 去重
    candidates = deduplicate(candidates)
    
    // 按分数排序
    sort.Slice(candidates, func(i, j int) bool {
        return candidates[i].Score > candidates[j].Score
    })
    
    // 限制数量
    if len(candidates) > limit {
        candidates = candidates[:limit]
    }
    
    return candidates
}

func deduplicate(candidates []AdCandidate) []AdCandidate {
    seen := make(map[string]bool)
    result := make([]AdCandidate, 0)
    
    for _, c := range candidates {
        if !seen[c.AdID] {
            seen[c.AdID] = true
            result = append(result, c)
        }
    }
    return result
}
```

---

## 3. 排序模型

### 3.1 模型架构

```
排序模型架构：

├── 特征层
│   ├── 用户特征
│   ├── 广告特征
│   ├── 上下文特征
│   └── 交叉特征
│
├── 模型层
│   ├── DeepFM
│   ├── DCN
│   └── Wide&Deep
│
└── 输出层
    ├── pCTR
    ├── pCVR
    └── pCTCVR
```

### 3.2 Go 实现排序模型

```go
// ranker.go

package ad

import (
    "context"
    "math"
)

type Ranker struct {
    ctrModel  *CTRModel
    cvrModel  *CVRModel
    weightCTR float64
    weightCVR float64
}

type CTRModel struct {
    // 简化版，实际应加载模型文件
}

type CVRModel struct {
    // 简化版
}

func NewRanker(weightCTR, weightCVR float64) *Ranker {
    return &Ranker{
        ctrModel:  &CTRModel{},
        cvrModel:  &CVRModel{},
        weightCTR: weightCTR,
        weightCVR: weightCVR,
    }
}

func (r *Ranker) Rank(ctx context.Context, candidates []AdCandidate) []AdCandidate {
    for i := range candidates {
        ctr := r.ctrModel.Predict(ctx, &candidates[i])
        cvr := r.cvrModel.Predict(ctx, &candidates[i])
        
        // 综合得分
        candidates[i].Score = r.weightCTR*ctr + r.weightCVR*cvr
    }
    
    // 按得分排序
    sort.Slice(candidates, func(i, j int) bool {
        return candidates[i].Score > candidates[j].Score
    })
    
    return candidates
}

func (m *CTRModel) Predict(ctx context.Context, candidate *AdCandidate) float64 {
    // 简化版预测
    features := candidate.Features
    score := 0.01 // 基础CTR
    
    // 基于特征调整
    if popularity, ok := features["popularity"]; ok {
        score *= (1 + popularity*0.1)
    }
    if relevance, ok := features["relevance"]; ok {
        score *= relevance
    }
    
    return math.Min(1.0, score)
}

func (m *CVRModel) Predict(ctx context.Context, candidate *AdCandidate) float64 {
    // 简化版预测
    features := candidate.Features
    score := 0.05 // 基础CVR
    
    if ctr, ok := features["ctr"]; ok {
        score *= ctr * 10
    }
    if category, ok := features["category"]; ok {
        if category == "ecommerce" {
            score *= 1.5
        }
    }
    
    return math.Min(1.0, score)
}
```

---

## 4. 重排策略

### 4.1 重排目标

```
重排目标：

├── 业务规则
│   ├── 行业多样性
│   ├── 创意去重
│   └── 品牌保护
│
├── 用户体验
│   ├── 广告间距
│   ├── 创意多样性
│   └── 相关性保证
│
└── 商业目标
    ├── 收入最大化
    ├── 填充率保证
    └── 长期价值
```

### 4.2 Go 实现重排器

```go
// reranker.go

package ad

import (
    "context"
    "math/rand"
)

type Reranker struct {
    config *Config
}

func NewReranker(config *Config) *Reranker {
    return &Reranker{config: config}
}

func (rr *Reranker) Rerank(ctx context.Context, candidates []AdCandidate, user *UserContext, limit int) []AdCandidate {
    // 1. 业务规则过滤
    filtered := rr.applyBusinessRules(candidates, user)
    
    // 2. 多样性调整
    diversified := rr.addDiversity(filtered, user)
    
    // 3. 频控处理
    final := rr.applyFrequencyControl(diversified, user)
    
    // 4. 限制数量
    if len(final) > limit {
        final = final[:limit]
    }
    
    return final
}

func (rr *Reranker) applyBusinessRules(candidates []AdCandidate, user *UserContext) []AdCandidate {
    var result []AdCandidate
    for _, c := range candidates {
        // 应用业务规则
        if rr.isAllowed(c, user) {
            result = append(result, c)
        }
    }
    return result
}

func (rr *Reranker) addDiversity(candidates []AdCandidate, user *UserContext) []AdCandidate {
    result := make([]AdCandidate, 0)
    seenCategories := make(map[string]bool)
    
    for _, c := range candidates {
        cat := c.Features["category"].(string)
        if !seenCategories[cat] || len(result) < 3 {
            seenCategories[cat] = true
            result = append(result, c)
        }
    }
    
    return result
}

func (rr *Reranker) applyFrequencyControl(candidates []AdCandidate, user *UserContext) []AdCandidate {
    // 简化版频控
    result := make([]AdCandidate, 0)
    seenAds := make(map[string]bool)
    
    for _, c := range candidates {
        if !seenAds[c.AdID] {
            seenAds[c.AdID] = true
            result = append(result, c)
        }
    }
    
    return result
}

func (rr *Reranker) isAllowed(candidate AdCandidate, user *UserContext) bool {
    // 简化版规则检查
    return true
}
```

---

## 5. 冷启动策略

### 5.1 冷启动问题

```
冷启动问题：

├── 新用户冷启动
│   ├── 基于人口属性
│   ├── 基于初始兴趣
│   └── 热门推荐
│
├── 新广告冷启动
│   ├── 相似广告迁移
│   ├── 广泛定向
│   └── 探索预算
│
└── 新场景冷启动
    ├── 迁移学习
    └── 元学习
```

### 5.2 Go 实现冷启动

```go
// cold_start.go

package ad

type ColdStartStrategy struct {
    demographics []DemographicProfile
    hotAds       []AdCandidate
    exploration  float64
}

type DemographicProfile struct {
    AgeRange    [2]int
    Gender      string
    Interests   []string
    Recommended []string
}

func NewColdStartStrategy() *ColdStartStrategy {
    return &ColdStartStrategy{
        exploration: 0.1,
    }
}

func (cs *ColdStartStrategy) Recommend(user *UserContext, limit int) []AdCandidate {
    if user.UserID != "" {
        // 有用户ID，使用正常推荐
        return nil
    }
    
    // 新用户冷启动
    var candidates []AdCandidate
    
    // 1. 基于人口属性
    if profile := cs.getDemographicProfile(user); profile != nil {
        for _, adID := range profile.Recommended {
            candidates = append(candidates, AdCandidate{
                AdID:   adID,
                Score:  0.5,
            })
        }
    }
    
    // 2. 热门广告
    for _, ad := range cs.hotAds {
        candidates = append(candidates, ad)
    }
    
    // 3. 探索
    if rand.Float64() < cs.exploration {
        candidates = append(candidates, cs.getRandomAds(5))
    }
    
    return candidates
}
```

---

## 6. 总结

### 6.1 核心组件回顾

| 组件 | 职责 |
|------|------|
| 召回 | 快速筛选候选集 |
| 预排序 | 粗排降维 |
| 精排序 | 精确打分 |
| 重排 | 业务规则调整 |

### 6.2 最佳实践

- [ ] 多路召回保证覆盖率
- [ ] 精排序模型持续迭代
- [ ] 重排保证用户体验
- [ ] 冷启动策略保障新用户

---

*最后更新：2026-08-11*
*作者：Ryan*
