# Amazon Ads — 平台功能全景深度梳理

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 平台功能全覆盖

---

## 第一部分: Amazon 广告生态系统

### 1.1 Amazon 广告全貌

```
┌──────────────────────────────────────────────────────────────┐
│                  Amazon 广告生态                                │
│                                                              │
│  Amazon 广告是电商广告的核心平台                                │
│                                                              │
│  核心广告产品:                                                │
│  ├── Sponsored Products (SP) — 商品推广                      │
│  ├── Sponsored Brands (SB) — 品牌推广                        │
│  ├── Sponsored Display (SD) — 展示推广                       │
│  ├── Amazon DSP — 展示广告 (独立/自营)                        │
│  ├── Amazon Video Ads — 视频广告 (TV + Fire TV)              │
│  ├── Amazon News Ads — 新闻广告                               │
│  ├── Audiences — 受众营销                                    │
│  └─ Brand Analytics — 品牌分析                               │
│                                                              │
│  与 Google/Meta 的关键差异:                                   │
│  ├── 搜索即购买: 用户意图极其明确                               │
│  ├── 购买转化率极高 (4x-10x 普通电商)                          │
│  ├── 闭环生态: 搜索→展示→购买全在 Amazon                       │
│  └─ 数据丰富: 真实购买数据 (而非推测转化)                       │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 广告产品详细对比

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                   Amazon 广告产品详细对比                                                  │
│                                                                                          │
│  | 产品          | 展示位置              | 定价        | 核心优势                  | 适合场景          │
│  |--------------|--------------------|-----------|-----------------------|----------------|
│  | SP           | 搜索结果页/商品页面   | CPC       | 精准捕获搜索意图        | 所有商品         │
│  | SB           | 搜索结果页顶部/侧边   | CPC/CPM   | 品牌曝光+多商品展示     | 品牌卖家         │
│  | SD           | Amazon内外网站/App    | CPV/CPC   | 再营销/品类扩量         | 所有卖家         │
│  | DSP (Managed)| 亚马逊团队管理        | CPM       | 程序化购买+自动优化     | 大卖家/品牌       │
│  | DSP (Self-Svc)| 自助平台            | CPM/CPC   | 灵活控制+API接入        | 代理商/技术卖家    │
│  | Video Ads    | Fire TV/IMDb/Freevee| CPM       | 视频曝光+品牌认知        | 品牌广告主       │
│  | Audiences    | 跨网站/App           | CPM/CPC   | 受众定向+再营销          | 所有卖家         │
└──────────────────────────────────────────────────────────────────────────────────────────┘

Sponsored Products (SP):
────────────────────────────────────────
├─ 广告位:
│   ├── 搜索结果页顶部 (Top of Search) — 最显眼位置
│   ├── 搜索结果页中部 (Mid of Search)
│   ├── 搜索结果页底部 (Bottom of Search)
│   ├── 商品详情页 (Product Detail Page)
│   ├── 商品详情页底部 (Rest of Search)
│   └─ 品牌店铺页 (Store Page)
│
├─ 出价方式:
│   ├── Fixed Bids — 固定出价
│   ├── Down Only — 只降低出价
│   └─ Dynamic Bids - Down Only or Both — 动态调整
│
├─ 匹配类型:
│   ├── Exact Match — 精确匹配 (最高 CPC, 最高转化)
│   ├── Phrase Match — 短语匹配 (中等 CPC)
│   └─ Broad Match — 广泛匹配 (最低 CPC, 最泛流量)
│
├─ 投放模式:
│   ├── Manual Targeting — 手动关键词投放
│   ├── Automatic Targeting — 自动投放
│   └─ Product/Category Targeting — 商品/品类定向
│
└─ 竞价公式:
    └─ Actual CPC = (Ad Rank / QS) × (1 + 1%)
       Ad Rank = Bid × QS
       QS = 预估 CTR × 预估转化率 × 历史表现

Sponsored Brands (SB):
────────────────────────────────────────
├─ 广告格式:
│   ├── Headline Search Ads (HSA) — 传统SB
│   ├── Video Search Ads (VSA) — 视频搜索广告
│   ├── Store Spotlight — 店铺推广
│   └─ Product Collection — 商品合集
│
├─ 广告组件:
│   ├── Logo (品牌标识)
│   ├── Headline (最多 30 字符)
│   ├── Search Terms (搜索关键词)
│   ├── Products (3-30个商品)
│   └─ Custom Landing Page (自定义落地页)
│
├─ 广告位:
│   ├── Top of Search (搜索结果页顶部) — 最显眼
│   ├── Mid of Search
│   └─ Rest of Search (搜索结果页其他位置)
│
├─ 竞价策略:
│   ├── Dynamic Bids - Down Only
│   ├── Dynamic Bids - Up and Down
│   └─ Fixed Bids
│
└─ 广告组:
    └─ 多个 SB 广告组成一个 SB Campaign
       每个广告组可不同关键词/定向/出价

Sponsored Display (SD):
────────────────────────────────────────
├─ 投放方式:
│   ├── Retargeting — 再营销 (看过但未购买)
│   ├── Audience — 受众定向
│   └─ Contextual — 上下文定向 (商品/品类/兴趣)
│
├─ 广告位:
│   ├── Amazon 内: 商品详情页/购物袋/确认页面
│   ├── Amazon 外: 第三方网站/App
│   └─ Fire TV/OTT 设备
│
├─ 定价:
│   ├── CPV (Cost Per View) — 视频展示
│   ├── CPC (Cost Per Click) — 点击
│   └─ CPM (Cost Per Mille) — 千次展示
│
└─ 定向:
    ├── View/Custom Audiences — 再营销
    ├── Product Targeting — 定向商品/品类
    └─ Interest/Category Targeting — 兴趣/品类
```

---

## 第二部分: Amazon 广告层级结构

### 2.1 广告账户结构

```
┌──────────────────────────────────────────────────────────────┐
│                  Amazon 广告层级                               │
│                                                              │
│  Campaign (广告系列)                                          │
│  ├── Objective (目标):                                       │
│  │   ├── Traffic — 店铺流量                                   │
│  │   ├── Sales — 商品销售                                    │
│  │   └─ Brand Awareness — 品牌认知                             │
│  ├── Budget:                                                 │
│  │   ├── Daily Budget (日预算)                               │
│  │   └─ Lifetime Budget (总预算)                              │
│  ├── Start/End Date                                         │
│  ├── Ad Scheduling (排期)                                    │
│  └─ Placement (展示位置调整)                                  │
│                                                              │
│  Ad Group (广告组)                                            │
│  ├── Products:                                               │
│  │   ├── Automatic Targeting — 自动商品匹配                    │
│  │   ├── Product Targeting — 手动商品定向                     │
│  │   ├── Category Targeting — 品类定向                       │
│  │   └─ Keyword Targeting — 关键词定向                       │
│  ├── Bidding:                                                │
│  │   ├── Dynamic Bids — 动态调整                              │
│  │   ├── Fixed Bids — 固定出价                               │
│  └─ Placement Bid Adjustment — 展示位置加价                    │
│                                                              │
│  Ads (广告) — 对于 SB/SD/Video, SP 不需要单独创建广告           │
│  ├── Creative: 图片/视频/轮播                                 │
│  ├── Headline: 标题                                          │
│  ├── Description: 描述                                       │
│  └─ CTA: 行动号召                                            │
│                                                              │
│  Placement (展示位置):                                        │
│  ├── Top of Search (搜索结果顶部) — +x% bid                  │
│  ├── Product Pages (商品页面) — +x% bid                     │
│  └─ Rest of Search (搜索结果其他) — +x% bid                  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 投放方式详解

```
Automatic Targeting (自动投放):
────────────────────────────────────────
Amazon 自动匹配关键词和商品:

匹配类型:
├── Close Match (紧密匹配) — 高度相关关键词
├── Substitutes (替代品) — 同类商品
├── Complements (互补品) — 相关商品
└─ Broad Match (广泛匹配) — 相关关键词

用途:
├── Discovery: 发现新关键词
├── Scaling: 扩量
└─ Testing: 测试新商品

优点:
├── 自动管理，节省时间
├── 覆盖长尾词
└─ 发现新机会

缺点:
├── 可能匹配不相关搜索
└─ 需要定期否定关键词

Manual Keyword Targeting (手动关键词):
────────────────────────────────────────
手动添加关键词并设置出价:

关键词类型:
├── Exact Match — 精确匹配
│   └── "wireless earbuds" 仅匹配 "wireless earbuds"
├── Phrase Match — 短语匹配
│   └── "wireless earbuds" 匹配 "cheap wireless earbuds" 等
└─ Broad Match — 广泛匹配
    └── "wireless earbuds" 匹配 "bluetooth earbuds" 等

关键词分组策略:
├── High Performer — 高转化词 (加量)
├── Medium Performer — 中等表现
└─ Low Performer — 低表现/需否定

Keyword Research:
├── Amazon Brand Analytics — 搜索频率排名
├── Search Term Report — 实际搜索词
├── Competitor ASINs — 竞对商品关键词
└─ Suggested Keywords — 推荐关键词
```

---

## 第三部分: Amazon DSP

### 3.1 DSP vs SP 的区别

```
DSP (Demand Side Platform) vs SP (Sponsored Products):

┌──────────────────────────────────────────────────────────────┐
│              DSP vs SP 对比                                    │
│                                                              │
│  | 维度      | DSP                   | SP              │
│  |---------|-----------------------|-----------------|
│  | 广告类型  | 展示/视频/再营销        | 搜索广告         │
│  | 竞价类型  | CPM/CPC              | CPC             │
│  | 展示位置  | Amazon内外             | 仅 Amazon       │
│  | 定价方式  | CPM/CPC               | CPC             │
│  | 控制度    | 高 (自助)              | 中              │
│  | 数据深度  | 深 (浏览/行为)         | 浅 (搜索/购买)   │
│  | 适合阶段  | 品牌/再营销/扩量       | 购买意图明确     │
│  └─ 预算    | 高 (通常 $5K+/月)    | 低 ($10+/月)     │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Amazon DSP 功能

```
Amazon DSP 功能:

投放方式:
├── Managed Service (管理服务) — 亚马逊团队操作
│   ├── 适合: 大卖家/品牌
│   ├── 最低预算: $10K+/月
│   ├── 有成功团队 (CSM)
│   └─ 自动优化
│
└── Self-Service (自助服务) — 自己操作
    ├── 适合: 中小卖家/代理商
    ├── 最低预算: $5/day
    ├── API 接口
    └─ 需自己优化

定向方式:
├── First-Party Audiences — 一方数据
│   ├── Custom Audiences (自定义受众)
│   ├── Customer Segments (客户细分)
│   └─ Amazon Store Visitors (店铺访客)
│
├── Amazon Audiences — 亚马逊数据
│   ├── Shopping Interests (购物兴趣)
│   ├── Lifestyle (生活方式)
│   ├── Lifestyle Segments (生活细分)
│   └─ Demographics (人口统计)
│
├── Contextual Targeting — 上下文定向
│   ├── Product Targeting — 商品定向
│   ├── Category Targeting — 品类定向
│   ├── Interest Targeting — 兴趣定向
│   └─ Publisher Targeting — 发布者定向
│
└─ Retargeting — 再营销
    ├── Viewers (看过但未购买)
    ├── Purchasers (已购买 — 向上销售)
    ├── Cart Abandoners (购物车放弃)
    └─ Product Viewers (商品浏览者)

```

---

## 第四部分: 竞价策略

### 4.1 Amazon 竞价类型

```
Amazon 竞价策略:

Dynamic Bids - Down Only (动态降价):
├── Amazon 根据预测转化率降低出价
├── 高转化可能性: 保持出价
├── 低转化可能性: 降低出价
└─ 适合: 大多数广告系列

Dynamic Bids - Up and Down (动态升降):
├── 高转化可能性: 加价 (最多 +100%)
├── 低转化可能性: 降低出价
└─ 适合: 高竞争关键词

Fixed Bids (固定出价):
├── 始终保持设置的价格
├── 不会自动调整
└─ 适合: 预算控制/精确出价

Placement Bid Adjustment (展示位置加价):
├── Top of Search (搜索结果顶部): +x%
├── Product Pages (商品页面): +x%
└─ Rest of Search (搜索结果其他): +x%

Automated Bidding (自动竞价):
├── Dynamic Bids — 基于转化预测
├── Target CPA — 目标每次转化成本
├── Target ROAS — 目标广告回报率
└─ Maximize Conversions — 最大化转化量
```

### 4.2 展示位置优化

```
Placement Bid Adjustment 详解:

展示位置价值排名:
├── 1. Top of Search (TOS) — 转化率最高 (4-10x)
├── 2. Product Pages (PDP) — 转化率中等 (2-4x)
└─ 3. Rest of Search (ROS) — 转化率最低 (0.5-2x)

优化策略:
├── TOS: +20% to +200% — 根据 ASIN 表现调整
├── PDP: +0% to +100% — 根据竞对调整
└─ ROS: -50% to 0% — 降低无效流量

示例:
├── 商品 A: TOS 转化率高 → TOS +150%
├── 商品 B: TOS 和 PDP 表现接近 → TOS +50%, PDP +25%
└─ 商品 C: TOS 效果差 → TOS -30%, PDP +50%
```

---

## 第五部分: 报告系统

### 5.1 Amazon 广告报告类型

```
Amazon 广告报告:

标准报告:
├── Search Term Report — 搜索词报告 (最重要)
│   ├── 实际用户搜索词
│   ├── 点击/展示/转化数据
│   ├── 用于: 找新关键词/添加否定关键词
│   └─ 更新频率: 每小时
│
├── Search Term Performance Report — 搜索词性能
│   ├── 搜索词 → ASIN 匹配
│   ├── 出价建议
│   └─ 匹配建议
│
├── Placement Report — 展示位置报告
│   ├── TOS/PDP/ROS 分别的性能
│   └─ 用于优化 Placement Bid Adjustment
│
├── Ad Group Report — 广告组报告
│   ├── 每个广告组的表现
│   └─ 用于优化广告组结构
│
├── Campaign Report — 广告系列报告
│   ├── 每个广告系列的表现
│   └─ 用于预算分配
│
├── Product Targeting Report — 商品定向报告
│   ├── 每个 ASIN/品类的表现
│   └─ 用于优化商品定向
│
└─ Ad Performance Report — 广告表现报告
    ├── 每个广告的表现
    └─ 用于优化广告创意

自定义报告:
├── 选择指标和维度
├── 选择时间范围
└─ 自定义分组

广告组报告:
├── 每个广告组的表现
└─ 用于优化广告组结构

Campaign Report:
├── 每个广告系列的表现
└─ 用于预算分配

Product Targeting Report:
├── 每个 ASIN/品类的表现
└─ 用于优化商品定向

Ad Performance Report:
├── 每个广告的表现
└─ 用于优化广告创意
```

### 5.2 关键指标

```
Amazon 广告关键指标:

┌──────────────────────────────────────────────────────────────┐
│              Amazon 核心指标                                    │
│                                                              │
│  展示指标:                                                   │
│  ├── Impressions — 展示次数                                    │
│  └─ CTR — 点击率                                              │
│                                                              │
│  销售指标:                                                   │
│  ├── Ad Sales — 广告带来销售额                                 │
│  ├── Ad Units — 广告带来单位数                                 │
│  └─ ACOS — Advertising Cost of Sales                         │
│                                                              │
│  ACOS = Ad Spend / Ad Sales × 100%                           │
│  ├── ACOS < 目标 ACOS → 盈利                                  │
│  ├── ACOS = 目标 ACOS → 盈亏平衡                              │
│  └─ ACOS > 目标 ACOS → 亏损                                   │
│                                                              │
│  TACOS = Total Ad Spend / Total Sales × 100%                 │
│  ├── 包含有机销售                                               │
│  └─ 衡量整体广告效率                                           │
│                                                              │
│  转化指标:                                                   │
│  ├── Conversion Rate (CVR) = Orders / Clicks                  │
│  ├── ROAS = Ad Sales / Ad Spend                               │
│  └─ CPC = Ad Spend / Clicks                                   │
│                                                              │
│  其他:                                                       │
│  ├── New-to-Brand (NTB) — 新品牌客户                          │
│  ├── Repeat Purchase Rate — 复购率                             │
│  └─ Share of Voice (SOV) — 声量份额                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 第六部分: Amazon Brand Analytics

### 6.1 Brand Analytics 功能

```
Amazon Brand Analytics (ABA):

┌──────────────────────────────────────────────────────────────┐
│              Brand Analytics 功能                              │
│                                                              │
│  品牌拥有者 (Registered Brand) 可用:                          │
│                                                              │
│  1. Search Frequency Rank (搜索频率排名)                      │
│  ├── 关键词搜索量排名                                          │
│  ├── 对比竞品搜索量                                            │
│  └─ 按关键词/品类/品牌筛选                                     │
│                                                              │
│  2. Market Basket Analysis (市场篮子分析)                     │
│  ├── "一起购买" (Buy Together)                                │
│  ├── 购买 A 商品的顾客也购买了什么                              │
│  └─ 用于: 找互补商品/竞对                                     │
│                                                              │
│  3. Repeat Purchase Rate (重复购买率)                         │
│  ├── 某商品的复购率                                            │
│  └─ 按品类/品牌/供应商                                        │
│                                                              │
│  4. Demographics (人口统计)                                   │
│  ├── 年龄: 18-24, 25-34, 35-44, 45-54, 55-64, 65+           │
│  ├── 性别: Male/Female                                      │
│  └─ 收入: <$25K, $25-50K, $50-75K, $75-100K, $100K+        │
│                                                              │
│  5. Amazon Originals (仅限注册品牌)                            │
│  └─ 品牌搜索词报告                                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 第七部分: 自测题

### 问题 1
ACOS 和 TACOS 的区别是什么？

<details>
<summary>查看答案</summary>

ACOS = Ad Spend / Ad Sales (只看广告销售)
TACOS = Total Ad Spend / Total Sales (包含有机销售)
TACOS 更能反映整体广告效率
</details>

### 问题 2
Amazon 广告有三种竞价方式，分别是什么？

<details>
<summary>查看答案</summary>

1. Dynamic Bids - Down Only (动态降价)
2. Dynamic Bids - Up and Down (动态升降)
3. Fixed Bids (固定出价)
</details>

### 问题 3
展示位置优化的三个位置分别是什么？

<details>
<summary>查看答案</summary>

1. Top of Search (TOS) — 搜索结果顶部 (转化率最高)
2. Product Pages (PDP) — 商品页面 (转化率中等)
3. Rest of Search (ROS) — 搜索结果其他位置 (转化率最低)
</details>

---

*今天花 90 分钟：系统掌握 Amazon Ads 平台功能体系*
*答不出自测题？回去重读对应章节。*

---

### Amazon Ads 功能体系的 Go 实现

```go
package amazonads

import (
	"fmt"
	"sync"
	"time"
)

type AdType string
const (
	AdTypeSponsoredProducts AdType = "SPONSORED_PRODUCTS"
	AdTypeSponsoredBrands AdType = "SPONSORED_BRANDS"
	AdTypeSponsoredDisplay AdType = "SPONSORED_DISPLAY"
)

type CampaignObjective string
const (
	ObjectiveSales CampaignObjective = "SALES"
	ObjectiveTraffic CampaignObjective = "TRAFFIC"
	ObjectiveBrandAwareness CampaignObjective = "BRAND_AWARENESS"
)

type SponsoredProduct struct {
	ProductID    string
	Asin         string
	Bid          float64
	State        string
	CampaignID   string
	Targeting    string
}

type SponsoredBrand struct {
	BrandName  string
	Headline   string
	Products   []string
	Bid        float64
	CampaignID string
}

type AdGroup struct {
	ID     string
	Name   string
	Type   AdType
	Status string
	Ads    []interface{}
}

type AmazonAdsClient struct {
	portfolioID string
	mu          sync.Mutex
	campaigns   map[string]*Campaign
	adGroups    map[string]*AdGroup
}

func NewAmazonAdsClient(portfolioID string) *AmazonAdsClient {
	return &AmazonAdsClient{portfolioID: portfolioID, campaigns: make(map[string]*Campaign)}
}

type Campaign struct {
	ID          string
	Name        string
	Type        AdType
	Objective   CampaignObjective
	PortfolioID string
	DailyBudget float64
	Status      string
	StartDate   time.Time
	EndDate     time.Time
}

func (c *AmazonAdsClient) CreateCampaign(name string, adType AdType, objective CampaignObjective, budget float64) *Campaign {
	c.mu.Lock()
	defer c.mu.Unlock()
	cp := &Campaign{
		ID: fmt.Sprintf("camp_%d", len(c.campaigns)),
		Name: name, Type: adType, Objective: objective,
		PortfolioID: c.portfolioID, DailyBudget: budget, Status: "ENABLED",
	}
	c.campaigns[cp.ID] = cp
	return cp
}

func (c *AmazonAdsClient) GetCampaigns() []*Campaign {
	c.mu.Lock()
	defer c.mu.Unlock()
	result := make([]*Campaign, 0, len(c.campaigns))
	for _, cp := range c.campaigns {
		result = append(result, cp)
	}
	return result
}

func main() {
	client := NewAmazonAdsClient("portfolio_123")
	cp := client.CreateCampaign("Summer Sale", AdTypeSponsoredProducts, ObjectiveSales, 100.0)
	fmt.Printf("Created: %s (%s)\n", cp.Name, cp.Type)
	for _, c := range client.GetCampaigns() {
		fmt.Printf("  %s: $%.0f/day\n", c.Name, c.DailyBudget)
	}
}
