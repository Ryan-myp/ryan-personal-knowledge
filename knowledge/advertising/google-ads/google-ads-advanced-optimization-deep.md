# Google Ads 高级投放策略与优化实战

## 一、账户结构设计深度策略

### 1.1 账户结构金字塔

```
Customer (广告账户)
├── Campaign 1: 品牌词保护 (预算 20%)
│   ├── Ad Group: 品牌核心词
│   │   ├── Keywords: [Brand], [Brand Product]
│   │   └── Ads: 品牌专属广告
│   └── Ad Group: 品牌长尾词
│       ├── Keywords: [Brand + feature], [Brand + use case]
│       └── Ads: 品牌 + 特性广告
├── Campaign 2: 竞品词拦截 (预算 10%)
│   ├── Ad Group: 竞品 A
│   │   ├── Keywords: [Competitor A], Competitor A vs Brand
│   │   └── Ads: 差异化对比广告
│   └── Ad Group: 竞品 B
│       ├── Keywords: [Competitor B]
│       └── Ads: 差异化对比广告
├── Campaign 3: 品类词推广 (预算 40%)
│   ├── Ad Group: 核心品类词
│   │   ├── Keywords: "category product", [category product]
│   │   └── Ads: 核心产品广告
│   ├── Ad Group: 细分品类词
│   │   ├── Keywords: "subcategory product"
│   │   └── Ads: 细分产品广告
│   └── Ad Group: 长尾品类词
│       ├── Keywords: [long-tail category keywords]
│       └── Ads: 长尾关键词广告
├── Campaign 4: 再营销 (预算 20%)
│   ├── Ad Group: 网站访客 30 天
│   │   ├── Audience: 所有网站访客
│   │   └── Ads: 品牌再营销广告
│   ├── Ad Group: 购物车放弃 7 天
│   │   ├── Audience: 加入购物车未购买
│   │   └── Ads: 促销再营销广告
│   └── Ad Group: 已购买用户
│       ├── Audience: 已购买用户
│       └── Ads: 交叉销售广告
└── Campaign 5: 品牌曝光 (预算 10%)
    ├── Ad Group: 广泛匹配
    │   ├── Keywords: broad match keywords
    │   └── Ads: 品牌形象广告
    └── Ad Group: 受众定向
        ├── Audience: 兴趣受众
        └── Ads: 品牌故事广告
```

### 1.2 账户结构设计原则

**设计原则：**

| 原则 | 说明 | 示例 |
|------|------|------|
| 主题聚焦 | 每个广告组围绕一个主题 | "Running Shoes" 而非 "All Products" |
| 关键词数量 | 5-20 个相关关键词 | 避免过多稀释相关性 |
| 广告相关性 | 广告文案与关键词高度相关 | 关键词出现在标题中 |
| 独立预算 | 重要产品线独立广告系列 | 高利润产品独立预算 |
| 分层管理 | 按业务目标分层 | 品牌、转化、流量分开 |

**常见错误：**

```
❌ 错误做法：
├── 一个广告系列包含所有产品
├── 一个广告组包含 100+ 关键词
├── 广告文案与关键词不相关
└── 预算集中在低效关键词

✅ 正确做法：
├── 按产品/目标拆分广告系列
├── 每个广告组 5-20 个相关关键词
├── 广告文案包含关键词
└── 预算按 ROI 分配
```

## 二、预算分配策略深度解析

### 2.1 预算分配模型

**基于 ROI 的预算分配：**

```
总预算 $10,000/月分配：

Step 1: 分析各广告组 ROI
├── 品牌词广告组: ROAS 800%, 花费 $1,500
├── 核心品类词: ROAS 400%, 花费 $3,500
├── 长尾词广告组: ROAS 600%, 花费 $2,000
├── 竞品词广告组: ROAS 300%, 花费 $1,000
└── 再营销广告组: ROAS 1000%, 花费 $2,000

Step 2: 识别优化机会
├── 高 ROAS + 低预算 → 增加预算
│   └── 再营销: +30% → $2,600
├── 高 ROAS + 高预算 → 保持
│   └── 品牌词: 保持 $1,500
├── 中 ROAS + 中预算 → 优化后保持
│   └── 核心品类: 保持 $3,500
├── 低 ROAS + 高预算 → 减少预算
│   └── 竞品词: -20% → $800
└── 低 ROAS + 低预算 → 测试优化
    └── 广泛匹配: 保持 $500 (测试)

Step 3: 重新分配
├── 品牌词: $1,500 (15%)
├── 核心品类: $3,500 (35%)
├── 长尾词: $2,000 (20%)
├── 竞品词: $800 (8%)
├── 再营销: $2,600 (26%)
└── 广泛匹配: $100 (1%)
```

### 2.2 动态预算调整

**每日预算调整策略：**

```
调整规则：
├── 预算消耗 < 50% → 次日增加 10-20%
├── 预算消耗 50-90% → 保持现状
├── 预算消耗 > 95% → 次日减少 5-10%
└── 连续 3 天消耗 > 95% → 检查出价和定向

季节性调整：
├── 促销季 (+50-100% 预算)
├── 淡季 (-20-30% 预算)
└── 平日 vs 周末差异调整
```

## 三、高级优化技巧

### 3.1 关键词优化深度策略

**关键词分层管理：**

| 层级 | 关键词类型 | 匹配类型 | 出价策略 | 预算占比 |
|------|-----------|----------|----------|----------|
| L1 | 品牌词 | 精确匹配 | 最高出价 | 15-20% |
| L2 | 核心品类词 | 短语匹配 | 高出价 | 40-50% |
| L3 | 长尾词 | 精确/短语 | 中等出价 | 20-25% |
| L4 | 广泛匹配词 | 广泛 + 否定 | 低出价 | 10-15% |
| L5 | 竞品词 | 短语/精确 | 高出价 | 5-10% |

**搜索词报告优化流程：**

```
每周优化流程：
1. 导出搜索词报告
2. 分析高转化搜索词 → 添加为关键词
3. 分析低效搜索词 → 添加为否定关键词
4. 发现新机会 → 添加到测试组
5. 更新否定关键词库
```

### 3.2 广告文案优化

**A/B 测试框架：**

| 测试维度 | 变体 A | 变体 B | 预期影响 |
|----------|--------|--------|----------|
| 标题 | 品牌词 | 产品词 | CTR ±15% |
| 描述 | 促销信息 | 产品信息 | CVR ±10% |
| CTA | Shop Now | Learn More | CVR ±8% |
| 附加信息 | 有站点链接 | 无站点链接 | CTR ±12% |

### 3.3 落地页优化

**落地页优化 checklist：**

```
加载速度：
├── [ ] 页面加载时间 <3 秒
├── [ ] 图片压缩 (WebP 格式)
├── [ ] 减少 HTTP 请求
├── [ ] 使用 CDN
└── [ ] 异步加载脚本

用户体验：
├── [ ] 清晰的导航结构
├── [ ] 移动端友好设计
├── [ ] 大字体、易阅读
├── [ ] 充足的留白
└── [ ] 一致的视觉风格

转化优化：
├── [ ] 明确的 CTA 按钮
├── [ ] 简化的表单 (3 字段以内)
├── [ ] 信任标识 (SSL、支付图标)
├── [ ] 用户评价和案例
└── [ ] 移除分散注意力的元素
```

## 四、行业最佳实践

### 4.1 电商行业

**投放策略：**

| 阶段 | 策略 | 预算分配 |
|------|------|----------|
| 新品上市 | 广泛匹配 + 品牌词 | 40% 品牌、30% 品类、30% 广泛 |
| 日常销售 | 精准匹配 + 再营销 | 30% 品牌、40% 品类、30% 再营销 |
| 促销活动 | 提高出价 + 扩展受众 | 50% 品类、30% 品牌、20% 广泛 |

**关键指标基准：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CTR | >2% | 1-2% | <1% |
| CVR | >5% | 2-5% | <2% |
| ROAS | >500% | 300-500% | <300% |
| CPA | <30% 毛利 | 30-50% 毛利 | >50% 毛利 |

### 4.2 B2B 行业

**投放策略：**

| 阶段 | 策略 | 关键词类型 |
|------|------|-----------|
| 品牌认知 | 展示网络 + 视频 | 品类词、行业词 |
| 需求生成 | 搜索广告 + 再营销 | 解决方案词、长尾词 |
| 转化推动 | 精准搜索 + Lead Ads | 品牌词、竞品词 |

**关键指标基准：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CTR | >1.5% | 1-1.5% | <1% |
| CPL | <$100 | $100-300 | >$300 |
| 销售合格线索率 | >30% | 20-30% | <20% |

## 五、自测题

1. 如何设计合理的账户结构？
2. 预算分配的动态调整策略是什么？
3. 关键词优化的完整流程是怎样的？
4. 落地页优化的关键要素有哪些？
5. 不同行业的核心指标基准是什么？

## 六、动手验证

```bash
# - 检查广告组主题聚焦度
# - 分析关键词分布
# - 评估预算分配合理性

# - 分析搜索词报告
# - 添加高转化关键词
# - 排除无效搜索词
# - 调整匹配类型

# - A/B 测试不同标题
# - 优化描述文案
# - 添加附加资产
# - 监控 CTR 变化

# - 检查加载速度
# - 优化 CTA 按钮
# - 简化表单
# - 添加社会证明

# - 分析各关键词 ROI
# - 调整设备出价
# - 调整地域出价
# - 设置时段出价
```

---

## 第七部分：Go 生产级实现

### Google Ads 智能出价优化器 — Go 源码

```go
package main

import (
	"fmt"
	"math"
	"sync"
	"time"
)

// BidStrategy represents a Google Ads bidding strategy.
type BidStrategy int

const (
	ManualCPC BidStrategy = iota
	TargetCPA
	TargetROAS
	MaxConversions
	EnhancedCPM
)

func (s BidStrategy) String() string {
	return []string{"manual_cpc", "target_cpa", "target_roas", "max_conversions", "enhanced_cpm"}[s]
}

// AdGroup represents a Google Ads ad group.
type AdGroup struct {
	ID              string
	Name            string
	BidStrategy     BidStrategy
	MaxCPC          float64
	TargetCPA       float64
	TargetROAS      float64
	Status          string // "enabled", "paused", "removed"
	DailyBudget     float64
}

// PerformanceMetrics tracks real-time performance data.
type PerformanceMetrics struct {
	Impressions  int
	Clicks       int
	Conversions  int
	Cost         float64
	Revenue      float64
	AvgPosition  float64
	CTR          float64
	ConversionRate float64
}

// SmartBidOptimizer adjusts bids based on performance data.
type SmartBidOptimizer struct {
	mu          sync.RWMutex
	adGroups    map[string]*AdGroup
	metrics     map[string]*PerformanceMetrics
	history     map[string][]BidAdjustment
	learningRate float64
}

// BidAdjustment records a bid change for learning.
type BidAdjustment struct {
	Timestamp time.Time
	OldBid    float64
	NewBid    float64
	Reason    string
	Outcome   float64 // actual impact on conversions
}

// NewSmartBidOptimizer creates a new optimizer instance.
func NewSmartBidOptimizer() *SmartBidOptimizer {
	return &SmartBidOptimizer{
		adGroups:     make(map[string]*AdGroup),
		metrics:      make(map[string]*PerformanceMetrics),
		history:      make(map[string][]BidAdjustment),
		learningRate: 0.1,
	}
}

// UpdateMetrics updates the performance metrics for an ad group.
func (o *SmartBidOptimizer) UpdateMetrics(agID string, m *PerformanceMetrics) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.metrics[agID] = m
}

// CalculateOptimalBid determines the optimal CPC for an ad group.
func (o *SmartBidOptimizer) CalculateOptimalBid(agID string) (float64, error) {
	o.mu.RLock()
	ag, exists := o.adGroups[agID]
	metrics, hasMetrics := o.metrics[agID]
	o.mu.RUnlock()

	if !exists {
		return 0, fmt.Errorf("ad group %s not found", agID)
	}

	var bid float64
	switch ag.BidStrategy {
	case TargetCPA:
		bid = o.calculateTargetCPABid(ag, metrics)
	case TargetROAS:
		bid = o.calculateTargetROASBid(ag, metrics)
	case MaxConversions:
		bid = o.calculateMaxConversionsBid(ag, metrics)
	case EnhancedCPM:
		bid = o.calculateECPMBid(ag, metrics)
	default:
		bid = ag.MaxCPC
	}

	// Apply learning rate for gradual adjustments
	o.mu.RLock()
	history := o.history[agID]
	o.mu.RUnlock()

	if len(history) > 0 {
		lastAdj := history[len(history)-1]
		delta := bid - lastAdj.NewBid
		bid = lastAdj.NewBid + delta*o.learningRate
	}

	return math.Round(bid*100) / 100, nil
}

func (o *SmartBidOptimizer) calculateTargetCPABid(ag *AdGroup, m *PerformanceMetrics) float64 {
	if m.ConversionRate == 0 || m.Conversions == 0 {
		return ag.TargetCPA * 0.5 // conservative start
	}
	// bid = target_CPA * conversion_rate * position_factor
	positionFactor := 1.0
	if m.AvgPosition < 2.0 {
		positionFactor = 1.2 // boost for top positions
	} else if m.AvgPosition > 4.0 {
		positionFactor = 0.8 // reduce for lower positions
	}
	return ag.TargetCPA * m.ConversionRate * positionFactor
}

func (o *SmartBidOptimizer) calculateTargetROASBid(ag *AdGroup, m *PerformanceMetrics) float64 {
	if m.Revenue == 0 || m.Conversions == 0 {
		return ag.MaxCPC * 0.5
	}
	actualROAS := m.Revenue / m.Cost
	targetRatio := ag.TargetROAS / actualROAS
	// If actual ROAS < target, reduce bids; otherwise increase
	bid := ag.MaxCPC * math.Min(1.5, math.Max(0.5, targetRatio))
	return bid
}

func (o *SmartBidOptimizer) calculateMaxConversionsBid(ag *AdGroup, m *PerformanceMetrics) float64 {
	// Bid up to budget limit to maximize conversions
	dailyBudget := ag.DailyBudget
	clicksPerDay := int(dailyBudget / math.Max(m.Cost/float64(m.Clicks), 0.01))
	estimatedConv := clicksPerDay * m.ConversionRate

	if estimatedConv > 0 {
		return dailyBudget / float64(clicksPerDay)
	}
	return ag.MaxCPC * 0.8
}

func (o *SmartBidOptimizer) calculateECMPBid(ag *AdGroup, m *PerformanceMetrics) float64 {
	// eCPM = CPC * CTR * 1000
	ecpm := ag.MaxCPC * m.CTR * 1000
	return ecpm / 1000 // convert back to effective CPC
}

// RecordAdjustment logs a bid adjustment for learning.
func (o *SmartBidOptimizer) RecordAdjustment(agID string, adj BidAdjustment) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.history[agID] = append(o.history[agID], adj)
	// Keep only last 30 days of history
	cutoff := time.Now().Add(-30 * 24 * time.Hour)
	i := 0
	for _, h := range o.history[agID] {
		if h.Timestamp.After(cutoff) {
			o.history[agID][i] = h
			i++
		}
	}
	o.history[agID] = o.history[agID][:i]
}
```

---

## 第八部分：自测题

### 问题 1：SmartBidOptimizer 中为什么用 learningRate 做渐进调整而不是直接应用新出价？

<details>
<summary>查看答案</summary>

Google Ads 算法本身对出价突变非常敏感，直接大幅调整会导致：
1. **学习期重置**：Google 需要重新收集数据，效果波动大
2. **预算消耗过快**：出价突然提高可能导致预算在几小时内耗尽
3. **质量分下降**：频繁调整可能影响广告质量评分

使用 learningRate（通常 0.1-0.2）可以：
- 每次调整不超过上次的 10%，平滑过渡
- 给 Google 算法足够的学习时间
- 降低 A/B 测试的噪声

</details>

### 问题 2：TargetROAS 策略中 `actualROAS/targetRatio` 的计算为什么用 `math.Min(1.5, math.Max(0.5, ...))` 限制范围？

<details>
<summary>查看答案</summary>

这个限制防止出价极端波动：

```
ratio = targetROAS / actualROAS
如果 ratio > 1.5：出价最多增加 50%
如果 ratio < 0.5：出价最多减少 50%
```

原因：
1. **避免过度反应**：短期 ROAS 波动可能是噪声，不是趋势
2. **防止预算耗尽**：出价翻倍可能导致预算几分钟内花完
3. **保持竞争力**：出价减半可能导致完全失去展示

实际生产中可以使用更精细的控制：
```go
bidChange := math.Log(targetRatio) * 0.5  // 对数缩放，变化更平滑
```

</details>

### 问题 3：RecordAdjustment 中为什么只保留 30 天的历史记录？

<details>
<summary>查看答案</summary>

30 天是广告优化的黄金窗口：
1. **数据相关性**：超过 30 天的数据可能因季节性、市场变化而失去参考价值
2. **内存管理**：历史数据随时间线性增长，需要定期清理
3. **学习周期**：Google Ads 智能出价的学习周期通常为 7-14 天，30 天足够覆盖多个学习周期

如果业务有长周期特征（如年度促销），可以扩展为：
```go
cutoff := time.Now().Add(-90 * 24 * time.Hour) // 90天
```
但需要同时增加内存容量和计算开销。

</details>
