# 微信读书精华：用户画像 + 广告数据定量分析 + 设计模式 蒸馏笔记

> 来源：《用户画像：平台构建与业务实践》- 张型龙
>       《广告数据定量分析》- 齐云涧
>       《设计模式的艺术》- 刘伟
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：用户画像

### 用户画像三层模型

```
用户画像架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 基础属性层（Who）                                                    │
│ •  demographics: 年龄/性别/地域/职业                                 │
│ •  设备信息: 手机型号/操作系统/网络                                   │
│ •  行为标签: 注册时长/活跃度/消费能力                                 │
│                                                                     │
│ 兴趣偏好层（What）                                                   │
│ •  浏览偏好: 类目偏好/品牌偏好/价格区间                               │
│ •  内容偏好: 文章/视频/直播偏好                                      │
│ •  购物偏好: 购买频次/客单价/品类                                    │
│                                                                     │
│ 行为预测层（Will）                                                   │
│ •  购买意愿: 购买概率/品类倾向                                       │
│ •  流失风险: 流失概率/原因                                           │
│ •  生命周期: 新客/活跃/沉默/流失                                     │
│                                                                     │
│ 数据源：                                                            │
│ • 第一方：用户行为日志、交易数据、注册信息                            │
│ • 第二方：合作伙伴数据                                               │
│ • 第三方：公开数据、数据供应商                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 标签体系

```
标签分类：
┌─────────────────────────────────────────────────────────────────────┐
│ 事实标签（客观数据）                                                 │
│ • 性别、年龄、城市、手机型号                                         │
│ • 注册时间、最后登录时间                                             │
│                                                                     │
│ 统计标签（聚合计算）                                                 │
│ • 近7天登录次数、近30天消费金额                                      │
│ • 平均客单价、购买频次                                               │
│                                                                     │
│ 模型标签（算法预测）                                                 │
│ • 购买概率、流失概率、LTV                                            │
│ • 用户分层（RFM模型）                                                │
│ • 相似人群（Lookalike）                                              │
│                                                                     │
│ 广告场景标签：                                                       │
│ • 广告敏感度：对广告的点击/转化概率                                  │
│ • 出价意愿：愿意支付的 CPM/CPC                                       │
│ • 创意偏好：喜欢的广告样式/风格                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：广告数据定量分析

### 核心指标体系

```
广告指标体系：
┌─────────────────────────────────────────────────────────────────────┐
│ 曝光层：                                                             │
│ • Impressions: 展示次数                                              │
│ • Reach: 独立触达人数                                                │
│ • Frequency: 人均展示次数                                            │
│                                                                     │
│ 点击层：                                                             │
│ • Clicks: 点击次数                                                   │
│ • CTR: 点击率 = Clicks / Impressions                                │
│ • CPC: 平均点击成本 = Spend / Clicks                                │
│                                                                     │
│ 转化层：                                                             │
│ • Conversions: 转化次数                                              │
│ • CVR: 转化率 = Conversions / Clicks                                │
│ • CPA: 平均转化成本 = Spend / Conversions                           │
│ • ROAS: 广告支出回报率 = Revenue / Spend                            │
│                                                                     │
│ 效率层：                                                             │
│ • eCPM: 千次展示收益 = (Revenue / Impressions) * 1000               │
│ • Fill Rate: 填充率 = 实际展示 / 请求次数                           │
│ • Win Rate: 中标率 = 中标次数 / 竞价次数                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 归因模型

```
归因模型对比：
┌────────────────┬────────────┬────────────┬────────────┐
│     模型       │  特点      │  优点      │  缺点      │
├────────────────┼────────────┼────────────┼────────────┤
│ Last Click     │ 最后点击   │ 简单       │ 忽略其他   │
│ First Click    │ 首次点击   │ 看重获客   │ 忽略后续   │
│ Linear         │ 均分       │ 公平       │ 不区分价值 │
│ Time Decay     │ 时间衰减   │ 重视近期   │ 参数难调   │
│ Position Based │ 首末加权   │ 综合考量   │ 权重固定   │
│ Data Driven    │ 数据驱动   │ 最准确     │ 需要数据   │
└────────────────┴────────────┴────────────┴────────────┘

推荐：有足够数据用 Data Driven，否则用 Position Based
```

---

## 第三部分：设计模式

### 创建型模式

```
Go 中的设计模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 单例模式（Singleton）                                             │
│    // 全局唯一实例，如配置管理器                                      │
│    var instance *ConfigManager                                       │
│    var once sync.Once                                                │
│    func GetInstance() *ConfigManager {                               │
│        once.Do(func() { instance = &ConfigManager{} })               │
│        return instance                                               │
│    }                                                                 │
│                                                                     │
│ 2. 工厂模式（Factory）                                               │
│    // 创建广告处理器，根据渠道选择不同实现                            │
│    func NewAdHandler(channel string) AdHandler {                    │
│        switch channel {                                              │
│        case "facebook": return &FacebookHandler{}                    │
│        case "google": return &GoogleHandler{}                        │
│        case "tiktok": return &TikTokHandler{}                        │
│        }                                                            │
│    }                                                                 │
│                                                                     │
│ 3. 建造者模式（Builder）                                             │
│    // 构建复杂的广告请求对象                                         │
│    builder := NewAdRequestBuilder().                                 │
│        SetPlatform("facebook").                                      │
│        SetBudget(1000).                                              │
│        SetTargeting(targeting).                                      │
│        Build()                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 结构型模式

```
Go 中的结构型模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 适配器模式（Adapter）                                             │
│    // 适配不同广告平台的 API 接口                                    │
│    type AdPlatform interface {                                       │
│        CreateCampaign(req *Campaign) error                           │
│        GetReport(startDate, endDate string) (*Report, error)         │
│    }                                                                 │
│                                                                     │
│ 2. 装饰器模式（Decorator）                                           │
│    // 给广告请求添加日志/缓存/限流                                   │
│    type LoggingHandler struct {                                      │
│        next AdHandler                                                 │
│    }                                                                 │
│    func (h *LoggingHandler) Handle(req *Request) {                  │
│        log.Info("handling request")                                  │
│        h.next.Handle(req)                                            │
│    }                                                                 │
│                                                                     │
│ 3. 代理模式（Proxy）                                                 │
│    // 广告请求的缓存代理                                             │
│    type CachedAdHandler struct {                                     │
│        next   AdHandler                                               │
│        cache  Cache                                                    │
│    }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 行为型模式

```
Go 中的行为型模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 策略模式（Strategy）                                              │
│    // 不同的竞价策略                                                  │
│    type BidStrategy interface {                                      │
│        CalculateBid(req *BidRequest) float64                         │
│    }                                                                 │
│    type FixedBidStrategy struct {}                                   │
│    type DynamicBidStrategy struct {}                                 │
│                                                                     │
│ 2. 观察者模式（Observer）                                            │
│    // 广告状态变更通知                                               │
│    type Observer interface {                                         │
│        Update(status string)                                         │
│    }                                                                 │
│    type AdCampaign struct {                                         │
│        observers []Observer                                          │
│    }                                                                 │
│                                                                     │
│ 3. 命令模式（Command）                                               │
│    // 广告操作命令                                                   │
│    type Command interface {                                          │
│        Execute() error                                               │
│        Undo() error                                                  │
│    }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: 用户画像的三层模型？

**A**: 基础属性（Who）、兴趣偏好（What）、行为预测（Will）。

### Q2: 广告核心指标？

**A**: CTR（点击率）、CVR（转化率）、CPC（点击成本）、CPA（转化成本）、ROAS（回报率）。

### Q3: Go 中最常用的设计模式？

**A**: 工厂模式（创建处理器）、策略模式（竞价策略）、装饰器模式（日志/缓存）。

---

## Go 代码实战：用户画像 + 设计模式

### 1. 用户画像标签系统（策略模式 + 工厂模式）

```go
package profile

import (
	"context"
	"encoding/json"
	"sync"
)

// Tag 用户标签
type Tag struct {
	Key       string  `json:"key"`
	Value     string  `json:"value"`
	Score     float64 `json:"score"`
	Source    string  `json:"source"` // behavioral, demographic, inferred
	TTL       int     `json:"ttl"`    // 过期时间(秒)
}

// UserProfile 用户画像（分层模型）
type UserProfile struct {
	UserID      string   `json:"user_id"`
	Demographic Demographics `json:"demographic"`
	Interests   []string `json:"interests"`
	Behaviors   []Behavior `json:"behaviors"`
	Predictions map[string]float64 `json:"predictions"` // CTR/CVR/ARPU预测
	UpdatedAt   int64    `json:"updated_at"`
}

// Demographics 人口统计学特征
type Demographics struct {
	Age     int    `json:"age"`
	Gender  string `json:"gender"`
	Income  string `json:"income"` // low/mid/high
	Location string `json:"location"`
	Education string `json:"education"`
}

// Behavior 行为事件
type Behavior struct {
	Type      string  `json:"type"` // view/click/purchase/share
	Timestamp int64   `json:"timestamp"`
	TargetID  string  `json:"target_id"`
	Metadata  json.RawMessage `json:"metadata"`
}

// TagExtractor 标签提取器接口（策略模式）
type TagExtractor interface {
	Extract(ctx context.Context, userID string) ([]*Tag, error)
	Name() string
}

// BehavioralTagExtractor 行为标签提取器
type BehavioralTagExtractor struct {
	cache *sync.Map // user_id -> tags
}

func (e *BehavioralTagExtractor) Extract(ctx context.Context, userID string) ([]*Tag, error) {
	// 从行为日志中提取兴趣标签
	// 示例：最近7天浏览最多的3个品类
	type := "interest_category"
	score := 0.95
	return []*Tag{
		{Key: type, Value: "tech", Score: score, Source: "behavioral"},
		{Key: type, Value: "finance", Score: score - 0.1, Source: "behavioral"},
	}, nil
}

func (e *BehavioralTagExtractor) Name() string { return "behavioral" }

// DemographicTagExtractor 人口统计学标签提取器
type DemographicTagExtractor struct{}

func (e *DemographicTagExtractor) Extract(ctx context.Context, userID string) ([]*Tag, error) {
	return []*Tag{
		{Key: "age_group", Value: "25-34", Score: 0.8, Source: "demographic"},
		{Key: "gender", Value: "male", Score: 0.9, Source: "demographic"},
		{Key: "income_level", Value: "high", Score: 0.7, Source: "demographic"},
	}, nil
}

func (e *DemographicTagExtractor) Name() string { return "demographic" }

// InferredTagExtractor 推断标签提取器
type InferredTagExtractor struct{}

func (e *InferredTagExtractor) Extract(ctx context.Context, userID string) ([]*Tag, error) {
	// 基于协同过滤推断
	return []*Tag{
		{Key: "purchase_intent", Value: "high", Score: 0.85, Source: "inferred"},
		{Key: "churn_risk", Value: "low", Score: 0.92, Source: "inferred"},
	}, nil
}

func (e *InferredTagExtractor) Name() string { return "inferred" }

// TagEngine 标签引擎（工厂模式）
type TagEngine struct {
	extractors []TagExtractor
}

func NewTagEngine() *TagEngine {
	return &TagEngine{
		extractors: []TagExtractor{
			&BehavioralTagExtractor{},
			&DemographicTagExtractor{},
			&InferredTagExtractor{},
		},
	}
}

func (e *TagEngine) BuildProfile(ctx context.Context, userID string) (*UserProfile, error) {
	var wg sync.WaitGroup
	tagCh := make(chan []*Tag, len(e.extractors))
	
	for _, ext := range e.extractors {
		wg.Add(1)
		go func(extractor TagExtractor) {
			defer wg.Done()
			tags, err := extractor.Extract(ctx, userID)
			if err != nil {
				return // 忽略单个提取器失败
			}
			tagCh <- tags
		}(ext)
	}
	
	go func() { wg.Wait(); close(tagCh) }()
	
	var allTags []*Tag
	for tags := range tagCh {
		allTags = append(allTags, tags...)
	}
	
	return e.mergeToProfile(userID, allTags), nil
}
```

### 2. 广告推荐装饰器模式

```go
package ad

// AdDecorator 广告装饰器接口
type AdDecorator interface {
	Decorate(ad *Ad, context *BidContext) *Ad
	Name() string
}

// FrequencyCapDecorator 频次控制装饰器
type FrequencyCapDecorator struct {
	controller *FrequencyController
}

func (d *FrequencyCapDecorator) Decorate(ad *Ad, ctx *BidContext) *Ad {
	if !d.controller.ShouldShow(ctx.CampaignID, ctx.UserID) {
		return nil
	}
	return ad
}

func (d *FrequencyCapDecorator) Name() string { return "frequency_cap" }

// BudgetCheckDecorator 预算检查装饰器
type BudgetCheckDecorator struct {
	manager *BudgetManager
}

func (d *BudgetCheckDecorator) Decorate(ad *Ad, ctx *BidContext) *Ad {
	if !d.manager.HasBudget(ctx.CampaignID) {
		return nil
	}
	return ad
}

func (d *BudgetCheckDecorator) Name() string { return "budget_check" }

// BlacklistDecorator 黑名单装饰器
type BlacklistDecorator struct {
	blocklist map[string]bool
}

func (d *BlacklistDecorator) Decorate(ad *Ad, ctx *BidContext) *Ad {
	if d.blocklist[ctx.UserID] {
		return nil
	}
	return ad
}

func (d *BlacklistDecorator) Name() string { return "blacklist" }

// AdFilterChain 装饰器链
type AdFilterChain struct {
	decorators []AdDecorator
}

func (c *AdFilterChain) Add(decorator AdDecorator) *AdFilterChain {
	c.decorators = append(c.decorators, decorator)
	return c
}

func (c *AdFilterChain) Filter(ads []*Ad, ctx *BidContext) []*Ad {
	result := ads
	for _, dec := range c.decorators {
		filtered := make([]*Ad, 0, len(result))
		for _, ad := range result {
			if decorated := dec.Decorate(ad, ctx); decorated != nil {
				filtered = append(filtered, decorated)
			}
		}
		result = filtered
	}
	return result
}
```

### 自测题

<details>
<summary>Q1: 用户画像的三种标签来源（behavioral/demographic/inferred）在生产环境如何加权？</summary>

**答案**：

**加权公式**：
```
final_score = w1 × behavioral_score + w2 × demographic_score + w3 × inferred_score

典型权重：
- behavioral: 0.5（最实时、最准确）
- demographic: 0.2（稳定但粗糙）
- inferred: 0.3（有模型置信度）
```

**关键决策**：behavioral 权重最高因为：① 用户行为是真实意图 ② 时效性强 ③ 可更新。demographic 权重低因为：① 数据可能过时 ② 群体统计不代表个体。

</details>

<details>
<summary>Q2: 装饰器模式的 Filter 链为什么用串行而非并行？有什么风险？</summary>

**答案**：

**串行原因**：装饰器之间有依赖关系——必须先做 budget_check，再做 frequency_cap，最后做 blacklist。如果并行执行，budget 耗尽后还做频次检查就是浪费计算资源。

**风险与优化**：
```go
// 优化：短路执行
func (c *AdFilterChain) Filter(ads []*Ad, ctx *BidContext) []*Ad {
	result := ads
	for _, dec := range c.decorators {
		// 如果已经空了，直接返回（短路）
		if len(result) == 0 {
			break
		}
		// ... 继续过滤
	}
	return result
}
```

</details>

<details>
<summary>Q3: TagEngine.BuildProfile 中并发提取标签，如果某个提取器返回错误，为什么选择忽略而不是返回错误？</summary>

**答案**：

**设计决策**：用户画像系统是**容错系统**——部分标签缺失不影响整体可用性。

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 忽略单个失败 | 不影响其他标签 | 可能缺少重要维度 | **画像系统** |
| 返回全部失败 | 保证完整性 | 一个标签缺失导致整个画像不可用 | 金融风控 |
| 降级方案 | 用缓存兜底 | 增加复杂度 | 生产标准 |

实际生产中会加降级：如果 behavioral 提取器失败，使用上次缓存的标签。

</details>
