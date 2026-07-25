# 广告商业思维深度：ROI/CPA/CAC/LTV 分析

> 从广告主视角，深度解析广告商业指标和 ROI 分析

---

## 第一部分：核心商业指标

### 指标定义

```
┌─────────────────────────────────────────────────────────────────────┐
│ 广告核心指标                                                         │
│                                                                      │
│ 1. CPC (Cost Per Click)                                              │
│    = 总花费 / 点击次数                                                 │
│    示例：¥1000 / 500 次 = ¥2/次                                      │
│                                                                      │
│ 2. CPM (Cost Per Mille)                                            │
│    = (总花费 / 展示次数) × 1000                                       │
│    示例：¥1000 / 500000 次 × 1000 = ¥2                              │
│                                                                      │
│ 3. CPA (Cost Per Action)                                            │
│    = 总花费 / 转化次数                                                 │
│    示例：¥1000 / 50 次 = ¥20/转化                                    │
│                                                                      │
│ 4. CTR (Click Through Rate)                                         │
│    = 点击次数 / 展示次数 × 100%                                       │
│    示例：500 / 500000 × 100% = 0.1%                                 │
│                                                                      │
│ 5. CVR (Conversion Rate)                                            │
│    = 转化次数 / 点击次数 × 100%                                       │
│    示例：50 / 500 × 100% = 10%                                      │
│                                                                      │
│ 6. ROAS (Return on Ad Spend)                                        │
│    = 广告收入 / 广告花费 × 100%                                       │
│    示例：¥5000 / ¥1000 × 100% = 500%                                │
│                                                                      │
│ 7. ROI (Return on Investment)                                       │
│    = (广告收入 - 广告花费) / 广告花费 × 100%                          │
│    示例：(¥5000 - ¥1000) / ¥1000 × 100% = 400%                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：LTV/CAC 分析

### LTV 计算

```
LTV (Life Time Value) 用户终身价值：
┌─────────────────────────────────────────────────────────────────────┐
│ 简化模型：                                                           │
│ LTV = ARPU × 用户生命周期 (月)                                        │
│                                                                      │
│ 详细模型：                                                           │
│ LTV = Σ (月收入 × 留存率) / (1 + 折现率)^t                           │
│                                                                      │
│ 示例：                                                               │
│ • ARPU = ¥10/月                                                      │
│ • 月留存率 = 80%                                                     │
│ • 折现率 = 10%                                                       │
│                                                                      │
│ Month 1: ¥10 × 1.0 / 1.1^1 = ¥9.09                                  │
│ Month 2: ¥10 × 0.8 / 1.1^2 = ¥6.61                                  │
│ Month 3: ¥10 × 0.64 / 1.1^3 = ¥4.81                                 │
│ ...                                                                  │
│ LTV ≈ ¥45                                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### CAC 计算

```
CAC (Customer Acquisition Cost) 获客成本：
┌─────────────────────────────────────────────────────────────────────┐
│ 简化模型：                                                           │
│ CAC = 营销总花费 / 新增用户数                                         │
│                                                                      │
│ 示例：                                                               │
│ • 营销花费 = ¥100,000                                                │
│ • 新增用户 = 5,000                                                   │
│ • CAC = ¥100,000 / 5,000 = ¥20                                     │
│                                                                      │
│ 关键比率：                                                           │
│ LTV/CAC > 3: 健康                                                    │
│ LTV/CAC = 1-3: 需要优化                                              │
│ LTV/CAC < 1: 不可持续                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### ROI 优化策略

```
ROI 优化策略：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 提高 CTR                                                          │
│    • 优化创意（A/B 测试）                                             │
│    • 精准定向                                                         │
│    • 优化广告位                                                       │
│                                                                      │
│ 2. 提高 CVR                                                          │
│    • 优化落地页                                                       │
│    • 简化转化流程                                                     │
│    • 社会证明（评价/证书）                                            │
│                                                                      │
│ 3. 降低 CPA                                                          │
│    • 智能出价（目标 CPA）                                             │
│    • 排除低效渠道                                                     │
│    • 优化投放时段                                                     │
│                                                                      │
│ 4. 提高 LTV                                                          │
│    • 用户分层运营                                                     │
│    • 个性化推荐                                                       │
│    • 会员体系                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：预算分配

### 多平台预算分配

```
预算分配优化问题：
┌─────────────────────────────────────────────────────────────────────┐
│ 给定：                                                               │
│ • 总预算：¥100,000/月                                                │
│ • 平台：Facebook / Google / TikTok                                  │
│ • 各平台历史数据：                                                     │
│   ├── Facebook: CPA=¥50, 容量=¥50,000                               │
│   ├── Google: CPA=¥80, 容量=¥30,000                                 │
│   └── TikTok: CPA=¥30, 容量=¥20,000                                 │
│                                                                      │
│ 目标：最大化转化次数                                                  │
│                                                                      │
│ 贪心算法：                                                           │
│ 1. 按 CPA 升序排序：TikTok (¥30) < Facebook (¥50) < Google (¥80)   │
│ 2. 优先分配给 CPA 最低的平台                                          │
│                                                                      │
│ 分配结果：                                                           │
│ • TikTok: ¥20,000 → 667 次转化                                      │
│ • Facebook: ¥50,000 → 1,000 次转化                                  │
│ • Google: ¥30,000 → 375 次转化                                      │
│ • 总转化：2,042 次                                                   │
│                                                                      │
│ 边际分析：                                                           │
│ • TikTok 饱和后，Facebook 边际 CPA 上升                               │
│ • 需要实时优化预算分配                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: ROAS 和 ROI 的区别？

**A**: ROAS = 收入/花费，ROI = (收入-花费)/花费。ROAS 只看广告效率，ROI 看整体利润。

### Q2: LTV/CAC 为什么大于 3 才算健康？

**A**: 因为还有运营成本、人力成本等，LTV 需要覆盖所有成本后还有利润。

### Q3: 预算分配用什么算法？

**A**: 贪心算法（按 CPA 排序）、线性规划（多约束优化）、强化学习（动态调整）。

---

## 第五部分：生产实践

### 1. 数据看板

```
广告数据看板：
• 实时：今日花费/展示/点击/转化
• 日报：昨日各平台表现
• 周报：趋势分析
• 月报：ROI 分析
```

### 2. 自动化优化

```
自动化优化：
1. 预算自动分配（基于 ROI）
2. 出价自动调整（基于 CPA）
3. 创意自动轮换（基于 CTR）
4. 异常自动告警（基于阈值）
```

### 3. 归因分析

```
归因分析：
1. Last Click：最后点击渠道
2. First Click：首次触达渠道
3. Linear：所有渠道均分
4. Time Decay：时间衰减
5. Position Based：首末位加权
```

---

## Go 代码实战：广告ROI分析引擎

### 1. ROI 计算器

```go
package roi

import (
	"math"
	"sync"
	"time"
)

// CampaignData 广告系列数据
type CampaignData struct {
	ID            string
	Name          string
	Spend         float64
	Revenue       float64
	Clicks        int64
	Conversions   int64
	Impressions   int64
	StartDate     time.Time
	EndDate       time.Time
}

// ROIMetrics ROI指标
type ROIMetrics struct {
	CampaignID      string
	ROAS            float64 // Return on Ad Spend
	CPA             float64 // Cost Per Acquisition
	CPC             float64 // Cost Per Click
	CTR             float64 // Click Through Rate
	CVR             float64 // Conversion Rate
	Profit          float64
	Margin          float64
	PaybackPeriod   time.Duration // 回本周期
}

// ROICalculator ROI计算器
type ROICalculator struct {
	mu sync.Mutex
}

func (c *ROICalculator) Calculate(data *CampaignData) *ROIMetrics {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	roas := data.Revenue / max(data.Spend, 0.01)
	cpa := data.Spend / max(float64(data.Conversions), 1)
	cpc := data.Spend / max(float64(data.Clicks), 1)
	ctr := float64(data.Clicks) / max(float64(data.Impressions), 1)
	cvr := float64(data.Conversions) / max(float64(data.Clicks), 1)
	profit := data.Revenue - data.Spend
	margin := profit / max(data.Revenue, 0.01)
	
	// 回本周期：Spend / DailyProfit
	daysActive := max(data.EndDate.Sub(data.StartDate).Hours()/24, 1)
	dailyProfit := profit / daysActive
	paybackDays := 0.0
	if dailyProfit > 0 {
		paybackDays = data.Spend / dailyProfit
	}
	
	return &ROIMetrics{
		CampaignID:    data.ID,
		ROAS:          roas,
		CPA:           cpa,
		CPC:           cpc,
		CTR:           ctr,
		CVR:           cvr,
		Profit:        profit,
		Margin:        margin,
		PaybackPeriod: time.Duration(paybackDays * 24 * float64(time.Hour)),
	}
}

// PortfolioAnalyzer 投资组合分析
type PortfolioAnalyzer struct {
	campaigns []*CampaignData
}

func NewPortfolioAnalyzer(campaigns []*CampaignData) *PortfolioAnalyzer {
	return &PortfolioAnalyzer{campaigns: campaigns}
}

func (a *PortfolioAnalyzer) Analyze() map[string]*ROIMetrics {
	results := make(map[string]*ROIMetrics)
	calc := &ROICalculator{}
	
	for _, campaign := range a.campaigns {
		results[campaign.ID] = calc.Calculate(campaign)
	}
	
	return results
}

func (a *PortfolioAnalyzer) TopPerformers(n int) []*ROIMetrics {
	results := a.Analyze()
	
	var metrics []*ROIMetrics
	for _, m := range results {
		metrics = append(metrics, m)
	}
	
	sort.Slice(metrics, func(i, j int) bool {
		return metrics[i].ROAS > metrics[j].ROAS
	})
	
	if n > len(metrics) {
		n = len(metrics)
	}
	return metrics[:n]
}
```

### 2. A/B Test 统计检验

```go
package roi

import "math"

// ABTestResult A/B测试结果
type ABTestResult struct {
	VariantA    VariantData
	VariantB    VariantData
	Lift        float64
	PValue      float64
	Confidence  float64
	Significant bool
	SampleSize  int
	Power       float64
}

type VariantData struct {
	Group       string
	Spend       float64
	Revenue     float64
	Clicks      int64
	Conversions int64
}

func RunABTest(a, b VariantData) *ABTestResult {
	roasA := a.Revenue / max(a.Spend, 0.01)
	roasB := b.Revenue / max(b.Spend, 0.01)
	lift := (roasB - roasA) / max(roasA, 0.01)
	
	// Z-test for ROAS difference
	// 使用 delta method 近似标准误
	seA := roasA * math.Sqrt(1.0/max(float64(a.Clicks),1) + 1.0/max(float64(a.Conversions),1))
	seB := roasB * math.Sqrt(1.0/max(float64(b.Clicks),1) + 1.0/max(float64(b.Conversions),1))
	
	zScore := lift / max(seA+seB, 0.001)
	pValue := 2 * (1 - normalCDF(math.Abs(zScore)))
	confidence := 1 - pValue
	
	return &ABTestResult{
		VariantA:    a,
		VariantB:    b,
		Lift:        lift,
		PValue:      pValue,
		Confidence:  confidence,
		Significant: pValue < 0.05,
		SampleSize:  int(a.Clicks + b.Clicks),
		Power:       1 - normalCDF(math.Abs(zScore)-1.96),
	}
}

func normalCDF(x float64) float64 {
	a1, a2, a3, a4, a5 := 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
	p := 0.3275911
	sign := 1.0
	if x < 0 {
		sign = -1
	}
	x = math.Abs(x)
	t := 1.0 / (1.0 + p*x)
	y := 1.0 - (((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.Exp(-x*x/2)
	return 0.5 * (1.0 + sign*y)
}
```

### 自测题

<details>
<summary>Q1: ROAS > 1 就代表赚钱吗？为什么 Margin 更重要？</summary>

**答案**：

**ROAS vs Margin**：
```
ROAS = Revenue / Spend = 1.5（每花1元赚1.5元）
但 Profit = Revenue - Spend - COGS

如果 COGS = 1.2元（商品成本），则：
Profit = 1.5 - 1 - 1.2 = -0.7 → 亏钱！

Margin = Profit / Revenue = -0.7/1.5 = -47%
```

**关键**：ROAS 只看广告投入产出，Margin 看整体盈利。广告平台必须同时监控两者。

</details>

<details>
<summary>Q2: A/B Test 的 P-value < 0.05 意味着什么？常见误解有哪些？</summary>

**答案**：

**正确理解**：P-value = 0.05 表示"如果 H0 为真（两组无差异），观察到当前差异的概率是5%"。

**常见误解**：
1. ❌ "P=0.05 表示 B 比 A 好的概率是95%" → 错！这是 Bayes Factor
2. ❌ "P>0.05 表示两组没有差异" → 错！可能是样本量不足
3. ❌ "P=0.04 比 P=0.06 重要得多" → 错！两者都是边缘显著

生产环境推荐报告 **Confidence + Effect Size + Power** 三个指标。

</details>

<details>
<summary>Q3: PaybackPeriod（回本周期）在oCPC场景下为什么不可靠？</summary>

**答案**：

**问题**：oCPC 的转化可能发生在点击后多日（延迟转化）。

```
Day 1: 用户点击广告
Day 3: 用户下单（转化计入）
Day 5: 用户退款

ROI计算应该用 Day 5 的数据，但 PaybackPeriod 用 Day 1 算 → 错误
```

**解决方案**：用 **归因窗口**（attribution window）调整——只计算点击后7天内的转化。

</details>
