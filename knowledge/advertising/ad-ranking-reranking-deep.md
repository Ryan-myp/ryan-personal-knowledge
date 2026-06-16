# 广告排序与重排深度：多样性/去重/位置偏置/业务规则

> 精排后的重排逻辑 + 多样性控制 + 业务规则 + 生产实现

---

## 第一部分：为什么精排后还需要重排？

### 排序 vs 重排

```
精排（Ranking）：
→ 输入：200 个候选广告
→ 输出：按 eCPM 排序的 Top 10
→ 目标：最大化收入

重排（Re-ranking）：
→ 输入：精排 Top 10
→ 输出：最终展示的 1 个广告
→ 目标：平衡收入 + 用户体验 + 业务规则

问题：
精排只看 eCPM，不考虑：
→ 同一个广告主的广告不能连续出现
→ 同一个创意的广告不能重复展示
→ 不同类型广告的多样性
→ 广告位置偏置
→ 业务规则（如品牌安全）
```

### 类比理解

```
精排 = 按价格排序商品
→ 最贵的商品排在最前面

重排 = 货架陈列
→ 不能把所有苹果放在一排
→ 不能把所有手机放在一排
→ 要考虑美观、体验、促销
```

---

## 第二部分：重排算法

### 2.1 重排流程

```
精排 Top 10 → 去重 → 多样性控制 → 业务规则过滤 → 位置偏置 → 最终选择

1. 去重：
   → 同一个广告主的广告最多出现 N 次
   → 同一个创意的广告不重复

2. 多样性控制：
   → 不同类型广告穿插展示
   → 避免同质化

3. 业务规则过滤：
   → 品牌安全过滤
   → 广告位适配过滤
   → 频次控制

4. 位置偏置：
   → 不同位置的点击率不同
   → 调整 eCPM 考虑位置因素
```

### 2.2 代码实现

```go
package dsp

import (
    "sort"
)

// ReRanker 重排器
type ReRanker struct {
    // 配置
    maxSameAdvertiser int      // 同一广告主最大出现次数
    maxSameCreative   int      // 同一创意最大出现次数
    diversityWeight   float64 // 多样性权重
    positionBias      []float64 // 位置偏置系数
}

// ReRank 重排
func (rr *ReRanker) ReRank(ads []*RankedAd, slot SlotInfo) *RankedAd {
    // 1. 去重
    deduplicated := rr.deduplicate(ads)
    
    // 2. 多样性控制
    diverse := rr.diversify(deduplicated, slot)
    
    // 3. 业务规则过滤
    filtered := rr.applyBusinessRules(diverse, slot)
    
    // 4. 位置偏置
    biased := rr.applyPositionBias(filtered, slot)
    
    // 5. 选择最优
    return biased[0]
}

// deduplicate 去重
func (rr *ReRanker) deduplicate(ads []*RankedAd) []*RankedAd {
    result := make([]*RankedAd, 0)
    advertiserCount := make(map[string]int)
    creativeSeen := make(map[string]bool)
    
    for _, ad := range ads {
        // 检查同一广告主数量
        if advertiserCount[ad.AdvertiserID] >= rr.maxSameAdvertiser {
            continue
        }
        
        // 检查同一创意
        if creativeSeen[ad.CreativeID] {
            continue
        }
        
        result = append(result, ad)
        advertiserCount[ad.AdvertiserID]++
        creativeSeen[ad.CreativeID] = true
    }
    
    return result
}

// diversify 多样性控制
func (rr *ReRanker) diversify(ads []*RankedAd, slot SlotInfo) []*RankedAd {
    // 按类别分组
    categoryMap := make(map[string][]*RankedAd)
    for _, ad := range ads {
        categoryMap[ad.Category] = append(categoryMap[ad.Category], ad)
    }
    
    // 轮流选择不同类别的广告
    result := make([]*RankedAd, 0)
    categories := getCategories(categoryMap)
    
    for len(result) < len(ads) {
        for _, category := range categories {
            if len(result) >= len(ads) {
                break
            }
            if len(categoryMap[category]) > 0 {
                result = append(result, categoryMap[category][0])
                categoryMap[category] = categoryMap[category][1:]
            }
        }
    }
    
    return result
}

// applyBusinessRules 应用业务规则
func (rr *ReRanker) applyBusinessRules(ads []*RankedAd, slot SlotInfo) []*RankedAd {
    result := make([]*RankedAd, 0)
    
    for _, ad := range ads {
        // 1. 品牌安全过滤
        if !rr.isBrandSafe(ad) {
            continue
        }
        
        // 2. 广告位适配过滤
        if !rr.isSlotCompatible(ad, slot) {
            continue
        }
        
        // 3. 频次控制
        if rr.isFrequencyExceeded(ad, slot.UserID) {
            continue
        }
        
        result = append(result, ad)
    }
    
    return result
}

// applyPositionBias 应用位置偏置
func (rr *ReRanker) applyPositionBias(ads []*RankedAd, slot SlotInfo) []*RankedAd {
    // 根据位置调整 eCPM
    positionFactor := rr.positionBias[slot.Position]
    
    for _, ad := range ads {
        // 位置偏置后的 eCPM
        ad.PositionAdjustedECPM = ad.ECPM * positionFactor
    }
    
    // 按调整后 eCPM 排序
    sort.Slice(ads, func(i, j int) bool {
        return ads[i].PositionAdjustedECPM > ads[j].PositionAdjustedECPM
    })
    
    return ads
}
```

---

## 第三部分：多样性控制

### 3.1 多样性策略

```
策略 1：类别轮换
→ 电商广告 → 游戏广告 → 教育广告 → 电商广告
→ 避免同质化

策略 2：广告主轮换
→ 广告主 A → 广告主 B → 广告主 C
→ 公平分配流量

策略 3：创意轮换
→ 同一广告主的广告使用不同创意
→ 避免用户疲劳
```

### 3.2 代码实现

```go
// DiversityController 多样性控制器
type DiversityController struct {
    maxSameCategory int // 同一类别最大出现次数
    maxSameAdvertiser int // 同一广告主最大出现次数
}

// Control 多样性控制
func (dc *DiversityController) Control(ads []*RankedAd) []*RankedAd {
    result := make([]*RankedAd, 0)
    categoryCount := make(map[string]int)
    advertiserCount := make(map[string]int)
    
    for _, ad := range ads {
        // 检查类别数量
        if categoryCount[ad.Category] >= dc.maxSameCategory {
            continue
        }
        
        // 检查广告主数量
        if advertiserCount[ad.AdvertiserID] >= dc.maxSameAdvertiser {
            continue
        }
        
        result = append(result, ad)
        categoryCount[ad.Category]++
        advertiserCount[ad.AdvertiserID]++
    }
    
    return result
}
```

---

## 第四部分：位置偏置

### 4.1 位置偏置原理

```
不同位置的点击率不同：
→ 顶部位置：CTR 高
→ 中部位置：CTR 中
→ 底部位置：CTR 低

调整 eCPM：
→ 位置调整后 eCPM = 原始 eCPM × 位置偏置系数
→ 位置偏置系数 > 1：该位置 CTR 高于平均
→ 位置偏置系数 < 1：该位置 CTR 低于平均

示例：
→ 顶部位置：偏置系数 1.2
→ 中部位置：偏置系数 1.0
→ 底部位置：偏置系数 0.8
```

### 4.2 代码实现

```go
// PositionBias 位置偏置计算器
type PositionBias struct {
    biases map[int]float64 // position -> bias factor
}

// NewPositionBias 创建位置偏置计算器
func NewPositionBias() *PositionBias {
    return &PositionBias{
        biases: map[int]float64{
            1: 1.2, // 顶部
            2: 1.0, // 中部
            3: 0.8, // 底部
        },
    }
}

// GetBiasFactor 获取位置偏置系数
func (pb *PositionBias) GetBiasFactor(position int) float64 {
    if factor, ok := pb.biases[position]; ok {
        return factor
    }
    return 1.0 // 默认
}

// AdjustECPM 调整 eCPM
func (pb *PositionBias) AdjustECPM(ecpm float64, position int) float64 {
    return ecpm * pb.GetBiasFactor(position)
}
```

---

## 第五部分：业务规则

### 5.1 品牌安全

```
品牌安全过滤：
→ 广告内容不适配目标受众
→ 广告内容与页面内容冲突
→ 广告主不希望自己的广告出现在某些网站

实现：
→ 广告主设置黑名单网站
→ 广告平台设置白名单网站
→ 实时过滤不安全的广告
```

### 5.2 广告位适配

```
广告位适配：
→ Banner 广告：300×250, 728×90
→ 信息流广告：原生样式
→ 开屏广告：全屏

实现：
→ 广告位指定支持的格式
→ 广告指定支持的格式
→ 匹配成功才展示
```

---

## 第六部分：自测题

### 问题 1
为什么精排后还需要重排？

<details>
<summary>查看答案</summary>

1. **精排只看 eCPM**：不考虑用户体验
2. **重排考虑多样性**：避免同质化
3. **重排考虑业务规则**：品牌安全/频次控制
4. **重排考虑位置偏置**：不同位置 CTR 不同
5. **目标**：平衡收入 + 用户体验
</details>

### 问题 2
位置偏置的原理是什么？

<details>
<summary>查看答案</summary>

1. **不同位置 CTR 不同**：顶部 > 中部 > 底部
2. **调整 eCPM**：eCPM × 位置偏置系数
3. **偏置系数**：顶部 1.2, 中部 1.0, 底部 0.8
4. **目的**：公平评估不同位置的广告价值
5. **实现**：根据历史数据计算偏置系数
</details>

---

*本文档基于广告排序重排生产实战整理。*