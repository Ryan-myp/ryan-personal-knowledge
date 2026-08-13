# DV360 测量、归因与排障深度实战

## 一、测量与归因深度策略

### 1.1 转化追踪配置

**Google Ads 集成：**

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

**第三方测量集成：**

| 工具 | 用途 | 集成方式 |
|------|------|----------|
| Moat | 品牌安全和可见性 | API 集成 |
| DoubleVerify | 品牌安全和可见性 | 标签集成 |
| Integral Ad Science | 广告质量 | API 集成 |
| comScore | 受众测量 | SDK 集成 |

### 1.2 归因模型深度解析

**各模型对比：**

| 模型 | 逻辑 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| Last Click | 最后点击 | 简单直观 | 忽视前期触点 | 简单转化路径 |
| First Click | 首次点击 | 重视获客 | 忽视转化触点 | 品牌认知 |
| Linear | 均匀分配 | 公平 | 不反映真实影响 | 全链路分析 |
| Time Decay | 时间衰减 | 重视近期触点 | 忽视首次接触 | 短期转化 |
| Position Based | 首尾加权 | 平衡品牌与转化 | 配置固定 | 品牌 + 效果 |
| Data-Driven | 算法分配 | 最准确 | 需要大量数据 | 优化投放 |

**数据驱动归因 (DDA) 要求：**

| 要求 | 说明 |
|------|------|
| 数据量 | 1000+ 转化/月 |
| 转化路径 | 多触点路径 |
| 时间窗口 | 30-90 天 |
| 模型更新 | 每周自动更新 |

## 二、常见问题与排障

### 2.1 投放异常处理

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 展示量骤降 | 预算耗尽、库存不足、审核拒绝 | 检查预算、扩大 Exchange、查看审核 |
| 可见率低 | 投放位置差、创意尺寸不当 | 调整位置、优化创意尺寸 |
| CPA 突然上升 | 竞争加剧、流量质量变化 | 分析流量来源、调整定向 |
| 转化量骤降 | 追踪代码故障、落地页错误 | 检查追踪、测试落地页 |

### 2.2 品牌安全事件处理

**品牌安全事件分类：**

| 级别 | 说明 | 响应时间 |
|------|------|----------|
| 严重 | 品牌出现在敏感内容旁 | 立即暂停 |
| 高 | 品牌出现在争议内容旁 | 1 小时内 |
| 中 | 品牌出现在低质量网站 | 24 小时内 |
| 低 | 品牌出现在非理想位置 | 48 小时内 |

**处理流程：**

```
1. 检测品牌安全事件
   ↓
2. 评估严重程度
   ↓
3. 执行响应措施
   ├── 暂停投放
   ├── 更新黑名单
   └── 通知相关团队
   ↓
4. 根本原因分析
   ↓
5. 预防措施
   ├── 更新过滤规则
   ├── 加强监控
   └── 培训团队
```

### 2.3 数据追踪问题

**常见追踪问题：**

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 转化数据丢失 | Pixel 故障、SDK 错误 | 检查代码、测试事件 |
| 数据延迟 | 归因窗口期、处理时间 | 等待 24-48 小时 |
| 数据不一致 | 过滤条件不同 | 统一设置 |
| 重复计数 | 多重追踪 | 去重配置 |

## 三、优化技巧

### 3.1 性能优化

**关键指标监控：**

| 指标 | 优秀 | 良好 | 一般 |
|------|------|------|------|
| CTR | >0.1% | 0.05-0.1% | <0.05% |
| Viewability | >70% | 60-70% | <60% |
| ROAS | >400% | 250-400% | <250% |
| CPA | <20% 客单价 | 20-35% 客单价 | >35% 客单价 |

**优化流程：**

```
1. 每日监控
   ├── 展示量
   ├── 点击量
   ├── 转化率
   └── 花费
   ↓
2. 每周分析
   ├── 趋势分析
   ├── 竞品对比
   └── 受众表现
   ↓
3. 每月优化
   ├── 预算重新分配
   ├── 创意轮换
   ├── 受众更新
   └── 策略调整
```

### 3.2 报告与分析

**关键报告类型：**

| 报告 | 用途 | 频率 |
|------|------|------|
| 投放报告 | 监控投放表现 | 每日 |
| 受众报告 | 分析受众效果 | 每周 |
| 创意报告 | 评估创意表现 | 每周 |
| 转化报告 | 分析转化效果 | 每日 |
| ROI 报告 | 评估投资回报 | 每月 |

## 四、自测题

1. 数据驱动归因的要求是什么？
2. 品牌安全事件如何处理？
3. 常见追踪问题有哪些？如何解决？
4. 关键优化指标有哪些？

## 五、动手验证

```bash
# - 设置 Google Tag
# - 配置 Pixel
# - 测试事件

# - 选择归因模型
# - 配置窗口期
# - 监控效果

# - 设置警报
# - 定期审查
# - 更新黑名单

# - 分析性能数据
# - 调整预算分配
# - 更新创意
```

---

## 第七部分：Go 生产级实现

### 归因模型引擎 — Go 源码

```go
package main

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"time"
)

// Touchpoint represents a user interaction with an ad.
type Touchpoint struct {
	ID         string
	CampaignID string
	Timestamp  time.Time
	Channel    string // "search", "display", "video", "social"
	Value      float64 // estimated conversion value
}

// AttributionResult holds the attribution output for a conversion.
type AttributionResult struct {
	Touchpoints []Touchpoint
	Scores      map[string]float64 // campaignID -> attributed value
	Model       string             // "last_click", "first_click", "linear", "time_decay", "position_based"
}

// AttributionEngine calculates conversion attribution across touchpoints.
type AttributionEngine struct {
	mu        sync.RWMutex
	models    map[string]AttributionModel
	history   []ConversionEvent
}

// ConversionEvent records a completed conversion with its touchpoints.
type ConversionEvent struct {
	UserID      string
	Touchpoints []Touchpoint
	ConvertedAt time.Time
	ConversionValue float64
}

// AttributionModel defines the interface for attribution models.
type AttributionModel interface {
	Name() string
	Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64
}

// LastClickModel attributes 100% to the last touchpoint before conversion.
type LastClickModel struct{}

func (m *LastClickModel) Name() string { return "last_click" }

func (m *LastClickModel) Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64 {
	result := make(map[string]float64)
	if len(touchpoints) == 0 {
		return result
	}
	// Sort by timestamp, last one gets full credit
	sort.Slice(touchpoints, func(i, j int) bool {
		return touchpoints[i].Timestamp.After(touchpoints[j].Timestamp)
	})
	result[touchpoints[0].CampaignID] = conversionValue
	return result
}

// FirstClickModel attributes 100% to the first touchpoint.
type FirstClickModel struct{}

func (m *FirstClickModel) Name() string { return "first_click" }

func (m *FirstClickModel) Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64 {
	result := make(map[string]float64)
	if len(touchpoints) == 0 {
		return result
	}
	sort.Slice(touchpoints, func(i, j int) bool {
		return touchpoints[i].Timestamp.Before(touchpoints[j].Timestamp)
	})
	result[touchpoints[0].CampaignID] = conversionValue
	return result
}

// LinearModel distributes credit equally across all touchpoints.
type LinearModel struct{}

func (m *LinearModel) Name() string { return "linear" }

func (m *LinearModel) Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64 {
	result := make(map[string]float64)
	if len(touchpoints) == 0 {
		return result
	}
	credit := conversionValue / float64(len(touchpoints))
	for _, tp := range touchpoints {
		result[tp.CampaignID] += credit
	}
	return result
}

// TimeDecayModel gives more credit to touchpoints closer to conversion.
type TimeDecayModel struct {
	HalfLife time.Duration // conversion value halves every half-life period
}

func (m *TimeDecayModel) Name() string { return "time_decay" }

func (m *TimeDecayModel) Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64 {
	result := make(map[string]float64)
	if len(touchpoints) == 0 {
		return result
	}

	// Calculate weights based on time decay
	now := touchpoints[len(touchpoints)-1].Timestamp // assume sorted
	var totalWeight float64
	weights := make([]float64, len(touchpoints))

	for i, tp := range touchpoints {
		delta := now.Sub(tp.Timestamp).Hours()
		weight := math.Pow(0.5, delta/m.HalfLife.Hours())
		weights[i] = weight
		totalWeight += weight
	}

	// Normalize and assign credit
	for i, tp := range touchpoints {
		result[tp.CampaignID] += conversionValue * (weights[i] / totalWeight)
	}
	return result
}

// PositionBasedModel gives 40% to first, 40% to last, 20% distributed among middle.
type PositionBasedModel struct{}

func (m *PositionBasedModel) Name() string { return "position_based" }

func (m *PositionBasedModel) Attribute(touchpoints []Touchpoint, conversionValue float64) map[string]float64 {
	result := make(map[string]float64)
	if len(touchpoints) == 0 {
		return result
	}

	first := touchpoints[0]
	last := touchpoints[len(touchpoints)-1]
	result[first.CampaignID] += conversionValue * 0.4
	result[last.CampaignID] += conversionValue * 0.4

	// Distribute remaining 20% among middle touchpoints
	middleCount := len(touchpoints) - 2
	if middleCount > 0 {
		middleCredit := conversionValue * 0.2 / float64(middleCount)
		for i := 1; i < len(touchpoints)-1; i++ {
			result[touchpoints[i].CampaignID] += middleCredit
		}
	} else if len(touchpoints) == 1 {
		result[touchpoints[0].CampaignID] = conversionValue
	}

	return result
}

// NewAttributionEngine creates a new attribution engine with all models.
func NewAttributionEngine() *AttributionEngine {
	return &AttributionEngine{
		models: map[string]AttributionModel{
			"last_click":      &LastClickModel{},
			"first_click":     &FirstClickModel{},
			"linear":          &LinearModel{},
			"time_decay":      &TimeDecayModel{HalfLife: 1 * time.Hour},
			"position_based":  &PositionBasedModel{},
		},
		history: make([]ConversionEvent, 0),
	}
}

// Attribute converts a conversion event using the specified model.
func (e *AttributionEngine) Attribute(event ConversionEvent, modelName string) (*AttributionResult, error) {
	e.mu.RLock()
	model, exists := e.models[modelName]
	e.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("unknown attribution model: %s", modelName)
	}

	scores := model.Attribute(event.Touchpoints, event.ConversionValue)
	return &AttributionResult{
		Touchpoints: event.Touchpoints,
		Scores:      scores,
		Model:       modelName,
	}, nil
}
```

---

## 第八部分：自测题

### 问题 1：时间衰减模型中为什么用 `math.Pow(0.5, delta/halfLife)` 而不是指数函数 `math.Exp`？

<details>
<summary>查看答案</summary>

两者数学等价但语义不同：
- `math.Pow(0.5, t)` 直接表达"每经过一个半衰期，权重减半"的直观概念
- `math.Exp(-lambda*t)` 需要计算 lambda = ln(2)/halfLife，不够直观

生产环境中推荐使用 `math.Pow(0.5, ...)` 因为：
1. **可读性**：业务人员能理解"半衰期"概念
2. **可调性**：修改 halfLife 参数即可调整衰减速率
3. **数值稳定性**：对于长时间跨度的衰减，Pow 比 Exp 更稳定

</details>

### 问题 2：PositionBasedModel 中为什么首尾各给 40%，中间 20% 平分？

<details>
<summary>查看答案</summary>

这个比例基于用户购买决策漏斗理论：
- **首次接触（40%）**：负责品牌认知和第一印象，决定用户是否继续了解
- **最终接触（40%）**：负责临门一脚，通常是促销信息或紧迫感触发
- **中间触点（20%）**：负责持续教育和信任建立，虽然重要但不是决定性因素

如果改为 30/30/40（中间更多），适合高考虑周期产品（如 B2B 软件）；
如果改为 50/50/0，则完全忽略中间教育环节，不适合长转化路径。

</details>

### 问题 3：多模型归因对比时，如何判断哪个模型最准确？

<details>
<summary>查看答案</summary>

没有绝对"最准确"的模型，不同场景适用不同模型：

1. **Last Click**：简单直接，但低估上层漏斗（品牌广告）
2. **First Click**：强调获客渠道，但高估首次曝光价值
3. **Linear**：公平分配，但无法区分关键触点和次要触点
4. **Time Decay**：适合短期转化，但对长期培育效果差
5. **Position Based**：平衡首尾重要性，是通用选择

验证方法：
- A/B 测试：用不同模型分配预算，比较 ROAS
- 交叉验证：检查模型预测与实际转化率的吻合度
- 业务对齐：品牌广告用 First Click，效果广告用 Last Click

</details>
