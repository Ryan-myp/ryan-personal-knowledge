# 推荐系统深度：重排层（Re-ranking）— MMR/打散/多样性

> 从精排 Top-N 中选出最终展示列表，平衡相关性、多样性和用户体验

---

## 第一部分：为什么需要重排？

### 重排解决的问题

```
精排后的问题：
1. 同质化严重：Top 10 都是同一类目的物品
2. 位置偏差：好物品排在后面没人看
3. 缺乏探索：只推荐热门，长尾物品没机会
4. 用户体验差：连续看到相同品牌/作者

重排的目标：
1. 多样性：覆盖不同类目/品牌/类型
2. 打散：同类物品不连续出现
3. 位置优化：好物品放前面
4. 探索：引入一定比例的新颖物品
```

### 重排在推荐漏斗中的位置

```
召回（1000万 → 1000）→ 粗排（1000 → 200）→ 精排（200 → 50）→ 重排（50 → 10）→ 展示

重排的输入：精排 Top-50
重排的约束：多样性、打散、业务规则
重排的输出：最终展示 Top-10
```

---

## 第二部分：MMR（最大边界相关算法）

### MMR 原理

```
MMR = max(λ × Relevance(d, Q) - (1-λ) × max_{r ∈ R} Similarity(d, r))

其中：
- d: 候选文档/物品
- Q: 用户查询/兴趣
- R: 已选集合
- λ: 权衡参数（0-1）

核心思想：
1. 选择与用户兴趣最相关的物品（Relevance）
2. 同时选择与已选物品最不相似的物品（Diversity）
3. λ 越大越相关，λ 越小越多样
```

### MMR 实现

```go
package main

import (
    "fmt"
    "math"
)

// Item 物品
type Item struct {
    ID       string
    Category string
    Relevance float64  // 精排分数
}

// MMR 重排器
type MMR struct {
    lambda float64 // 相关性权重
}

func NewMMR(lambda float64) *MMR {
    return &MMR{lambda: lambda}
}

// Similarity 简化版：同类目不相似，不同类目相似
func (m *MMR) Similarity(a, b Item) float64 {
    if a.Category == b.Category {
        return 0.0 // 同类目不相似（我们希望打散）
    }
    return 1.0 // 不同类目相似（我们希望保留）
}

// Rank 执行 MMR 重排
func (m *MMR) Rank(items []Item, k int) []Item {
    if len(items) <= k {
        return items
    }
    
    var selected []Item
    remaining := make([]Item, len(items))
    copy(remaining, items)
    
    // 1. 选择第一个（最高相关性）
    bestIdx := 0
    for i := 1; i < len(remaining); i++ {
        if remaining[i].Relevance > remaining[bestIdx].Relevance {
            bestIdx = i
        }
    }
    selected = append(selected, remaining[bestIdx])
    remaining = append(remaining[:bestIdx], remaining[bestIdx+1:]...)
    
    // 2. 迭代选择剩余 k-1 个
    for len(selected) < k && len(remaining) > 0 {
        var bestItem Item
        var bestScore float64 = -math.MaxFloat64
        
        for _, item := range remaining {
            // 相关性
            relevance := item.Relevance
            
            // 多样性（与已选集合的最大相似度）
            maxSim := 0.0
            for _, sel := range selected {
                sim := m.Similarity(item, sel)
                if sim > maxSim {
                    maxSim = sim
                }
            }
            
            // MMR 分数
            score := m.lambda*relevance - (1-m.lambda)*maxSim
            
            if score > bestScore {
                bestScore = score
                bestItem = item
            }
        }
        
        selected = append(selected, bestItem)
        
        // 从 remaining 中移除
        for i, item := range remaining {
            if item.ID == bestItem.ID {
                remaining = append(remaining[:i], remaining[i+1:]...)
                break
            }
        }
    }
    
    return selected
}

func main() {
    items := []Item{
        {ID: "1", Category: "electronics", Relevance: 0.95},
        {ID: "2", Category: "electronics", Relevance: 0.90},
        {ID: "3", Category: "clothing", Relevance: 0.85},
        {ID: "4", Category: "clothing", Relevance: 0.80},
        {ID: "5", Category: "books", Relevance: 0.75},
        {ID: "6", Category: "books", Relevance: 0.70},
        {ID: "7", Category: "food", Relevance: 0.65},
        {ID: "8", Category: "food", Relevance: 0.60},
    }
    
    mmr := NewMMR(0.7) // λ=0.7，偏重相关性
    result := mmr.Rank(items, 5)
    
    fmt.Println("MMR 重排结果:")
    for i, item := range result {
        fmt.Printf("%d. %s (category: %s, relevance: %.2f)\n", i+1, item.ID, item.Category, item.Relevance)
    }
}
```

---

## 第三部分：业务规则重排

### 常见重排规则

```go
type Reranker struct {
    rules []Rule
}

type Rule interface {
    Name() string
    Apply(items []Item) []Item
}

// 1. 类目打散规则
type CategoryDisperseRule struct {
    maxPerCategory int
}

func (r *CategoryDisperseRule) Name() string { return "category_disperse" }

func (r *CategoryDisperseRule) Apply(items []Item) []Item {
    categoryCount := make(map[string]int)
    var result []Item
    
    for _, item := range items {
        if categoryCount[item.Category] < r.maxPerCategory {
            result = append(result, item)
            categoryCount[item.Category]++
        }
    }
    
    return result
}

// 2. 品牌打散规则
type BrandDisperseRule struct {
    maxPerBrand int
}

func (r *BrandDisperseRule) Name() string { return "brand_disperse" }

func (r *BrandDisperseRule) Apply(items []Item) []Item {
    brandCount := make(map[string]int)
    var result []Item
    
    for _, item := range items {
        if brandCount[item.Brand] < r.maxPerBrand {
            result = append(result, item)
            brandCount[item.Brand]++
        }
    }
    
    return result
}

// 3. 新品曝光规则
type NewItemBoostRule struct {
    boostFactor float64
}

func (r *NewItemBoostRule) Name() string { return "new_item_boost" }

func (r *NewItemBoostRule) Apply(items []Item) []Item {
    for i := range items {
        if items[i].IsNew {
            items[i].Score *= r.boostFactor
        }
    }
    
    sort.Slice(items, func(i, j int) bool {
        return items[i].Score > items[j].Score
    })
    
    return items
}

// 4. 广告插卡规则
type AdInsertRule struct {
    adPosition int // 每 N 个插入 1 个广告
}

func (r *AdInsertRule) Name() string { return "ad_insert" }

func (r *AdInsertRule) Apply(items []Item) []Item {
    var result []Item
    adCount := 0
    
    for i, item := range items {
        result = append(result, item)
        
        if (i+1) % r.adPosition == 0 && adCount < 2 {
            result = append(result, Item{
                ID:    fmt.Sprintf("ad_%d", adCount),
                Score: item.Score,
                IsAd:  true,
            })
            adCount++
        }
    }
    
    return result
}
```

---

## 第四部分：位置偏差校正

### 位置效应

```
不同位置的点击率差异：
位置 1: CTR 5%
位置 2: CTR 3%
位置 3: CTR 2%
位置 4: CTR 1.5%
位置 5: CTR 1%

问题：好物品排在前面更容易被点击，但这不一定是物品本身的质量

解决方案：位置偏差校正（Position Bias Correction）
```

### 位置校正实现

```go
type PositionBiasCorrector struct {
    positionBiases []float64 // 每个位置的偏差系数
}

func (c *PositionBiasCorrector) Correct(items []Item) []Item {
    for i := range items {
        if i < len(c.positionBiases) {
            // 校正分数 = 原始分数 / 位置偏差
            items[i].CorrectedScore = items[i].Score / c.positionBiases[i]
        }
    }
    
    sort.Slice(items, func(i, j int) bool {
        return items[i].CorrectedScore > items[j].CorrectedScore
    })
    
    return items
}
```

---

## 第五部分：自测题

### Q1: MMR 的 λ 参数怎么选？

**A**:
- λ 接近 1：偏重相关性，多样性低
- λ 接近 0：偏重多样性，相关性低
- 通常通过 A/B 测试选择最优值（0.5-0.8）

### Q2: 重排和精排的区别？

**A**:
- **精排**：给每个物品打分（相关性）
- **重排**：考虑全局约束（多样性、打散、业务规则）

### Q3: 如何处理广告和自然结果的混排？

**A**:
- 广告插卡：每 N 个自然结果插入 1 个广告
- 广告降权：广告分数乘以降权系数
- 位置限制：广告不能出现在前 1-2 位

---

## 第六部分：生产实践

### 1. 重排流水线

```
精排 Top-50
    ↓
MMR 多样性重排（λ=0.7）
    ↓
类目/品牌打散
    ↓
新品曝光
    ↓
广告插卡
    ↓
位置偏差校正
    ↓
最终 Top-10
```

### 2. 性能要求

| 指标 | 要求 |
|------|------|
| 延迟 | < 5ms |
| QPS | 10K-100K |
| 可配置 | 规则热更新 |

### 3. A/B 测试

```
实验组 1: MMR λ=0.5（高多样性）
实验组 2: MMR λ=0.7（平衡）
实验组 3: MMR λ=0.9（高相关性）
对照组: 无重排

评估指标：
- CTR
- 类目覆盖率
- 人均浏览深度
- GMV
```
