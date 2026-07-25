# DV360 投放策略与优化深度实战

## 一、投放策略制定

### 1.1 账户结构设计

**DV360 账户结构最佳实践：**

```
Advertiser (广告主)
├── IO 1: 品牌曝光
│   ├── Line Item 1: Programmatic Guaranteed
│   │   ├── 创意: 品牌视频
│   │   └── 定向: 广泛受众
│   └── Line Item 2: PMP
│       ├── 创意: 品牌展示
│       └── 定向: 高价值受众
├── IO 2: 效果投放
│   ├── Line Item 1: Open Auction
│   │   ├── 创意: 产品广告
│   │   └── 定向: 意向受众
│   ├── Line Item 2: Preferred Deal
│   │   ├── 创意: 再营销广告
│   │   └── 定向: 网站访客
│   └── Line Item 3: PG
│       ├── 创意: 促销广告
│       └── 定向: 高转化受众
└── IO 3: 跨媒体投放
    ├── Line Item 1: 展示广告
    ├── Line Item 2: 视频广告
    ├── Line Item 3: 音频广告
    └── Line Item 4: 零售媒体
```

### 1.2 预算分配策略

**预算分配模型：**

```
总预算 $100,000/月
├── 品牌曝光 (40%) $40,000
│   ├── Programmatic Guaranteed $20,000
│   └── PMP $20,000
├── 效果投放 (50%) $50,000
│   ├── Open Auction $30,000
│   ├── Preferred Deal $10,000
│   └── PG $10,000
└── 测试预算 (10%) $10,000
    ├── 新媒体测试
    └── 新受众测试
```

### 1.3 交易类型选择

**交易类型选择指南：**

| 交易类型 | 成本 | 库存质量 | 适用场景 |
|----------|------|----------|----------|
| Open Auction | 低 | 参差不齐 | 大规模投放 |
| Preferred Deal | 中 | 优质 | 品牌安全要求高 |
| PMP | 中高 | 优质 | 高端品牌 |
| PG | 高 | 保证 | 大额品牌投放 |

**交易组合策略：**

```
混合交易策略
├── 70% Open Auction → 规模
├── 20% PMP/Preferred → 质量
└── 10% PG → 保证
```

## 二、高级优化技巧

### 2.1 定向优化策略

**定向分层管理：**

| 层级 | 定向类型 | 预算分配 | 优化目标 |
|------|----------|----------|----------|
| L1 | 第一方受众 | 30% | 高转化 |
| L2 | 第二方受众 | 25% | 精准投放 |
| L3 | 第三方受众 | 25% | 扩量 |
| L4 | 上下文定向 | 20% | 品牌安全 |

**受众细分优化：**

```
In-Market Audiences 优化
├── 高意向受众 → 提高出价 +30-50%
├── 中意向受众 → 基准出价
└── 低意向受众 → 降低出价 -20%

Life Events 优化
├── 新婚 → 家居、旅游产品 +20%
├── 搬家 → 家具、装修产品 +20%
├── 新工作 → 职业装、理财 +15%
└── 新生儿 → 母婴产品 +25%
```

### 2.2 创意优化策略

**创意格式优化：**

| 格式 | 适用场景 | 优化重点 |
|------|----------|----------|
| 横幅广告 | 品牌曝光 | 尺寸适配、视觉吸引 |
| 原生广告 | 内容营销 | 与自然内容融合 |
| 视频广告 | 品牌故事 | 前 5 秒、字幕 |
| 富媒体广告 | 互动体验 | 交互设计、加载速度 |

**创意 A/B 测试：**

| 测试维度 | 变体 A | 变体 B | 预期影响 |
|----------|--------|--------|----------|
| 格式 | 静态图片 | HTML5 | CTR ±20% |
| 尺寸 | 300x250 | 728x90 | 可见性 ±15% |
| 文案 | 产品导向 | 情感导向 | CTR ±10% |
| CTA | Buy Now | Learn More | CVR ±15% |

**创意疲劳管理：**

```
创意疲劳指标
├── CTR 下降 >20%
├── CPA 上升 >30%
└── 频次 >3

应对策略
├── 更新创意素材
├── 调整文案角度
├── 更换 CTA
├── 测试新格式
└── 暂停低效创意
```

### 2.3 竞价优化策略

**竞价策略选择：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| Target CPA | 目标每次转化费用 | 转化优化 |
| Target ROAS | 目标广告支出回报率 | 收入优化 |
| Viewable CPM | 可见展示计费 | 品牌曝光 |
| Max Clicks | 最多点击 | 引流 |
| Max Conversions | 最多转化 | 转化 |

**频率控制策略：**

| 广告类型 | 推荐频次 | 控制方法 |
|----------|----------|----------|
| 品牌广告 | 3-5 次/周 | 频次目标竞价 |
| 效果广告 | 1-2 次/周 | 受众排除 |
| 再营销 | 2-3 次/周 | 时间窗口控制 |

### 2.4 跨媒体优化

**跨媒体预算分配：**

| 媒体类型 | 预算占比 | 优化目标 |
|----------|----------|----------|
| 展示广告 | 40% | 品牌曝光、再营销 |
| 视频广告 | 30% | 品牌故事、产品演示 |
| 音频广告 | 15% | 品牌曝光、播客投放 |
| 零售媒体 | 15% | 电商转化 |

## 三、常见问题与排障

### 3.1 投放异常处理

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 展示量骤降 | 预算耗尽、库存不足、审核拒绝 | 检查预算、扩大 Exchange、查看审核 |
| 可见率低 | 投放位置差、创意尺寸不当 | 调整位置、优化创意尺寸 |
| CPA 突然上升 | 竞争加剧、流量质量变化 | 分析流量来源、调整定向 |
| 转化量骤降 | 追踪代码故障、落地页错误 | 检查追踪、测试落地页 |

### 3.2 品牌安全问题

**品牌安全层级：**

| 层级 | 措施 | 说明 |
|------|------|------|
| L1 | 黑名单 | 排除不适用网站 |
| L2 | 白名单 | 仅投放指定网站 |
| L3 | 分类过滤 | 排除敏感分类 |
| L4 | 第三方验证 | Moat、DoubleVerify |

### 3.3 数据追踪问题

**转化追踪优化：**

```
转化追踪流程
├── 设置转化目标
│   ├── 网站转化
│   ├── App 转化
│   └── 电话转化
├── 安装追踪代码
│   ├── Google Tag
│   ├── Pixel
│   └── SDK
├── 数据回传
│   ├── 实时回传
│   └── 批量回传
└── 优化投放
    ├── 基于转化数据
    └── 调整出价策略
```

## 四、行业最佳实践

### 4.1 电商行业

**投放策略：**

| 阶段 | 策略 | 预算分配 |
|------|------|----------|
| 品牌认知 | 展示 + 视频 | 50% 品牌、30% 效果、20% 测试 |
| 考虑阶段 | 再营销 + 意向 | 30% 品牌、50% 效果、20% 测试 |
| 转化阶段 | 零售媒体 + 再营销 | 20% 品牌、60% 效果、20% 测试 |

**关键指标基准：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CTR | >0.1% | 0.05-0.1% | <0.05% |
| Viewability | >70% | 60-70% | <60% |
| ROAS | >400% | 250-400% | <250% |
| CPA | <20% 客单价 | 20-35% 客单价 | >35% 客单价 |

### 4.2 汽车行业

**投放策略：**

| 阶段 | 策略 | 创意重点 |
|------|------|----------|
| 认知 | 视频 + 展示 | 车型展示、品牌故事 |
| 考虑 | 再营销 + 意向 | 配置器、试驾预约 |
| 转化 | dealership 定向 | 优惠信息、库存 |

**关键指标基准：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CPC | <$0.50 | $0.50-1.00 | >$1.00 |
| 试驾预约率 | >2% | 1-2% | <1% |
| 单次线索成本 | <$50 | $50-150 | >$150 |
| 销售转化率 | >5% | 2-5% | <2% |

### 4.3 金融行业

**投放策略：**

| 产品 | 策略 | 定向重点 |
|------|------|----------|
| 信用卡 | 意向 + 再营销 | 高收入、高消费 |
| 贷款 | 搜索 + 展示 | 信贷需求、收入 |
| 保险 | 人生大事 + 再营销 | 新婚、新生儿、搬家 |

**关键指标基准：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CPL | <$30 | $30-100 | >$100 |
| 审批通过率 | >40% | 25-40% | <25% |
| 客户获取成本 | <$200 | $200-500 | >$500 |
| 12 个月 ROI | >150% | 100-150% | <100% |

## 五、自测题

1. 如何设计 DV360 账户结构？
2. 四种交易类型各有什么特点和适用场景？
3. 频率控制的重要性是什么？如何实施？
4. 品牌安全的保障措施有哪些？
5. 跨媒体归因的难点和解决方案是什么？

## 六、动手验证

```bash
# 1. 审计现有账户结构
# - 检查 IO 和 Line Item 设计
# - 分析交易类型组合
# - 评估预算分配

# 2. 优化定向策略
# - 分析受众表现
# - 优化上下文定向
# - 排除低质量库存

# 3. 优化创意策略
# - A/B 测试不同格式
# - 更新疲劳创意
# - 优化尺寸适配

# 4. 优化竞价策略
# - 分析各 Line Item ROI
# - 调整出价策略
# - 设置频次控制

# 5. 优化品牌安全
# - 更新黑名单
# - 配置第三方验证
# - 监控品牌安全报告
```

---

## 第七部分：Go 生产级实现

### DV360 智能出价优化引擎 — Go 源码

```go
package main

import (
	"fmt"
	"math"
	"sync"
	"time"
)

// BidConfig represents the configuration for a bidding strategy.
type BidConfig struct {
	TargetCPA    float64 // target cost per acquisition
	BidCap       float64 // maximum bid amount
	BidFloor     float64 // minimum bid amount
	Strategy     string  // "target_cpa", "max_conversions", "target_roas"
	RoAS         float64 // return on ad spend target
}

// BidResult holds the output of the bidding engine.
type BidResult struct {
	BidAmount float64 `json:"bid_amount"`
	Strategy  string  `json:"strategy"`
	Confidence float64 `json:"confidence"` // 0-1, how confident in this bid
}

// Optimizer manages bid optimization across campaigns.
type Optimizer struct {
	mu          sync.RWMutex
	campaigns   map[string]*CampaignState
	config      BidConfig
	history     []BidRecord
	decayFactor float64 // for temporal decay
}

// CampaignState tracks the current state of a campaign.
type CampaignState struct {
	ID              string
	TotalSpend      float64
	TotalConversions int
	AvgCTRClickRate float64
	AvgConversionRate float64
	LastUpdated     time.Time
}

// BidRecord stores historical bid data for optimization.
type BidRecord struct {
	CampaignID  string
	BidAmount   float64
	Impressions int
	Clicks      int
	Conversions int
	Timestamp   time.Time
}

// NewOptimizer creates a new bid optimizer.
func NewOptimizer(config BidConfig) *Optimizer {
	return &Optimizer{
		campaigns:   make(map[string]*CampaignState),
		config:      config,
		history:     make([]BidRecord, 0),
		decayFactor: 0.95,
	}
}

// CalculateBid determines the optimal bid for a given campaign.
func (o *Optimizer) CalculateBid(campaignID string, estimatedCTR, estimatedCVR float64) (*BidResult, error) {
	o.mu.RLock()
	state, exists := o.campaigns[campaignID]
	o.mu.RUnlock()

	if !exists {
		// New campaign: use default bidding
		return &BidResult{
			BidAmount:  o.config.TargetCPA * estimatedCVR,
			Strategy:   "target_cpa",
			Confidence: 0.5,
		}, nil
	}

	var bidAmount float64
	switch o.config.Strategy {
	case "target_cpa":
		bidAmount = o.calculateTargetCPABid(state, estimatedCTR, estimatedCVR)
	case "max_conversions":
		bidAmount = o.calculateMaxConversionsBid(state, estimatedCTR, estimatedCVR)
	case "target_roas":
		bidAmount = o.calculateTargetROASBid(state, estimatedCTR, estimatedCVR)
	default:
		bidAmount = o.calculateTargetCPABid(state, estimatedCTR, estimatedCVR)
	}

	// Apply bid caps
	bidAmount = math.Max(bidAmount, o.config.BidFloor)
	bidAmount = math.Min(bidAmount, o.config.BidCap)

	confidence := o.calculateConfidence(state)

	return &BidResult{
		BidAmount:  math.Round(bidAmount*100) / 100,
		Strategy:   o.config.Strategy,
		Confidence: confidence,
	}, nil
}

// calculateTargetCPABid uses the target CPA formula.
func (o *Optimizer) calculateTargetCPABid(state *CampaignState, ctr, cvr float64) float64 {
	// bid = target_CPA * CVR * adjustment_factor
	adjustment := o.getAdjustmentFactor(state)
	bid := o.config.TargetCPA * cvr * adjustment
	return bid
}

// calculateMaxConversionsBid maximizes conversion volume.
func (o *Optimizer) calculateMaxConversionsBid(state *CampaignState, ctr, cvr float64) float64 {
	// bid = budget_remaining / (estimated_conversions * time_remaining)
	budgetRemaining := state.TotalSpend * 0.1 // simplified
	timeRemaining := 1.0                      // normalized
	estimatedConv := ctr * cvr
	if estimatedConv == 0 {
		return o.config.BidFloor
	}
	return budgetRemaining / (estimatedConv * timeRemaining)
}

// calculateTargetROASBid optimizes for return on ad spend.
func (o *Optimizer) calculateTargetROASBid(state *CampaignState, ctr, cvr float64) float64 {
	// bid = avg_order_value * CVR / target_ROAS
	avgOrderValue := 50.0 // placeholder
	bid := avgOrderValue * cvr / o.config.RoAS
	return bid
}

// getAdjustmentFactor adjusts bids based on historical performance.
func (o *Optimizer) getAdjustmentFactor(state *CampaignState) float64 {
	if state.AvgConversionRate == 0 {
		return 1.0
	}
	// If actual CVR > target, increase bid; otherwise decrease
	ratio := state.AvgConversionRate / (o.config.TargetCPA / 50.0)
	if ratio > 1.0 {
		return 1.0 + (ratio-1.0)*0.2 // 20% boost
	}
	return 1.0 - (1.0-ratio)*0.2 // 20% reduction
}

// calculateConfidence returns a confidence score based on data volume.
func (o *Optimizer) calculateConfidence(state *CampaignState) float64 {
	if state.TotalConversions < 10 {
		return 0.3 // low confidence, not enough data
	}
	if state.TotalConversions < 50 {
		return 0.6 // medium confidence
	}
	return 0.9 // high confidence
}

// RecordBid stores a bid record for future optimization.
func (o *Optimizer) RecordBid(record BidRecord) {
	o.mu.Lock()
	defer o.mu.Unlock()

	o.history = append(o.history, record)

	// Update campaign state
	state, exists := o.campaigns[record.CampaignID]
	if !exists {
		o.campaigns[record.CampaignID] = &CampaignState{
			ID: record.CampaignID,
		}
		state = o.campaigns[record.CampaignID]
	}
	state.TotalSpend += record.BidAmount * float64(record.Impressions)
	state.TotalConversions += record.Conversions
	state.LastUpdated = time.Now()
}
```

---

## 第八部分：自测题

### 问题 1：智能出价中 Target CPA 策略的公式 `bid = target_CPA * CVR * adjustment` 为什么是乘法而不是加法？

<details>
<summary>查看答案</summary>

乘法关系反映的是**概率期望**的数学本质：

```
E[conversion] = CTR × CVR
Expected cost per conversion = bid / (CTR × CVR)
```

要使期望成本等于目标 CPA：
```
bid / (CTR × CVR) = target_CPA
→ bid = target_CPA × CTR × CVR
```

如果用加法（如 `bid = target_CPA + CVR`），当 CVR 接近 0 时 bid 仍会很高，导致浪费预算。乘法确保低转化率的广告位自动降低出价。

</details>

### 问题 2：calculateConfidence 函数为什么用 10 和 50 作为置信度分界点？

<details>
<summary>查看答案</summary>

这是统计学中的经验法则：
- **< 10 次转化**：统计显著性不足，置信度 0.3，系统会偏向保守出价
- **10-50 次转化**：中等置信度 0.6，开始信任历史数据
- **≥ 50 次转化**：高置信度 0.9，充分信任模型预测

根据中心极限定理，样本量 ≥ 30 时样本均值近似正态分布。50 是一个更保守的安全阈值，确保有足够的数据支撑决策。

</details>

### 问题 3：getAdjustmentFactor 中为什么使用 0.2 作为调整系数（boost/reduction）？

<details>
<summary>查看答案</summary>

0.2 是**学习率**（learning rate）的选择：

- 太大（如 0.5）：出价波动剧烈，可能导致预算快速耗尽或过度节省
- 太小（如 0.05）：学习速度太慢，无法及时响应转化率变化
- 0.2 是经验值：在稳定性和响应速度之间取得平衡

生产环境通常使用自适应学习率：
```go
learningRate := 0.2 / math.Sqrt(float64(state.TotalConversions))
```
随着数据量增加，学习率自动降低，避免在数据充足时过度调整。

</details>
