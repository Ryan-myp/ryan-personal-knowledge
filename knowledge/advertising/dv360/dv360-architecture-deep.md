# DV360 平台架构与程序化购买深度解析

## 一、DV360 平台概述

### 1.1 平台定位

**DV360（Display & Video 360）** 是 Google 的企业级程序化广告平台，支持跨媒体、跨渠道的广告投放和管理。

**核心价值主张：**
1. **跨媒体投放**：支持展示、视频、音频、电视、零售媒体
2. **多 DSP 接入**：通过 Exchange 连接多个广告交换平台
3. **实时竞价**：基于 RTB（Real-Time Bidding）的程序化购买
4. **数据驱动**：结合 Google Ads Data Hub（ADH）实现跨平台归因
5. **企业级管理**：支持多层级账户结构和批量操作

**市场规模：**
- 全球程序化广告市场规模超过 2000 亿美元
- DV360 占据企业级程序化广告市场主导地位
- 覆盖全球 90%+ 的桌面和移动展示广告库存

### 1.2 竞争格局

| 平台 | 市场份额 | 核心优势 | 劣势 |
|------|----------|----------|------|
| DV360 | 35% | Google 生态、跨媒体、数据整合 | 学习曲线陡、成本高 |
| The Trade Desk | 25% | 独立 DSP、界面友好 | Google 数据整合弱 |
| Amazon DSP | 15% | 电商数据、Amazon 生态 | 非 Amazon 平台覆盖有限 |
| Programmatic 其他 | 25% | 垂直领域优势 | 规模有限 |

### 1.3 程序化广告生态系统

```
┌─────────────────────────────────────────────────────────────┐
│              Programmatic Advertising Ecosystem              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Advertisers (广告主)                                         │
│  └── 使用 DV360 管理平台                                     │
│                                                               │
│  ↓ 投放管理                                                  │
│                                                               │
│  DSP (Demand-Side Platform)                                   │
│  ├── DV360                                                   │
│  ├── The Trade Desk                                          │
│  ├── Amazon DSP                                              │
│  └── 其他 DSP                                               │
│                                                               │
│  ↓ 竞价请求 (RTB)                                            │
│                                                               │
│  Ad Exchange (广告交换)                                       │
│  ├── Google AdX (最大)                                       │
│  ├── OpenX                                                   │
│  ├── PubMatic                                                │
│  ├── Index Exchange                                          │
│  └── 其他 SSP                                                │
│                                                               │
│  ↓ 流量供应                                                  │
│                                                               │
│  SSP (Supply-Side Platform)                                   │
│  ├── Google Ad Manager (GAM)                                 │
│  ├── Prebid                                                   │
│  └── 其他 SSP                                               │
│                                                               │
│  ↓ 库存供应                                                  │
│                                                               │
│  Publishers (发布商)                                          │
│  ├── 网站 (Websites)                                         │
│  ├── App (移动应用)                                           │
│  ├── Connected TV (联网电视)                                  │
│  └── Audio (音频平台)                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 二、账户体系架构

### 2.1 账户层级结构

```
360 Connector (360 连接器)
├── Advertisers (广告主)
│   ├── Insertion Orders (IO，订单项)
│   │   ├── Line Items (线条项目)
│   │   │   ├── Creatives (创意)
│   │   │   ├── Targeting (定向)
│   │   │   └── Schedule (排期)
│   │   └── Budget (预算)
│   ├── Partners (合作伙伴)
│   └── Users (用户)
├── Campaigns (广告系列)
├── Reports (报告)
└── Tools (工具)
```

### 2.2 Insertion Order (IO) 详解

**定义：** IO 是广告主与发布商之间的订购协议，定义预算、排期和投放目标。

**关键属性：**

| 属性 | 说明 | 示例 |
|------|------|------|
| Name | IO 名称 | "Q1_Brand_Campaign" |
| Type | IO 类型 | Programmatic Guaranteed, PMP, Open |
| Budget | 总预算 | $100,000 |
| Schedule | 投放时间 | 2024-01-01 至 2024-03-31 |
| Exchange | 投放 Exchange | Google AdX, OpenX |
| Status | 状态 | ACTIVE, PAUSED, ENDED |

**IO 类型：**

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| Programmatic Guaranteed (PG) | 程序化保量采购 | 品牌大额投放 |
| Private Market Place (PMP) | 私有市场交易 | 优质库存采购 |
| Preferred Deal (PD) | 优先交易 | 优先购买权 |
| Open Auction | 公开竞价 | 常规投放 |

## 三、程序化购买详解

### 3.1 RTB（实时竞价）流程

```
用户访问网站/App
    ↓
发布商向 SSP 发送广告请求
    ↓
SSP 向 Ad Exchange 转发请求
    ↓
Ad Exchange 向多个 DSP 发送竞价请求
    ↓
DSP 实时评估：
├── 用户是否符合定向条件
├── 用户历史价值
├── 当前竞价策略
└── 出价金额
    ↓
DSP 返回出价
    ↓
Ad Exchange 选择最高出价
    ↓
获胜 DSP 的广告展示给用户
    ↓
计费：第二价格拍卖
```

**竞价时间线：**

| 步骤 | 时间 | 说明 |
|------|------|------|
| 广告请求 | 0ms | 用户访问页面 |
| 数据收集 | 50ms | 获取用户信息 |
| 受众匹配 | 100ms | 检查定向条件 |
| 出价决策 | 150ms | 计算出价金额 |
| 返回出价 | 200ms | 提交出价 |
| 拍卖完成 | 250ms | 选择最高出价 |
| 广告展示 | 300ms | 展示获胜广告 |

### 3.2 交易类型

**公开竞价（Open Auction）：**

| 特性 | 说明 |
|------|------|
| 可用性 | 所有 DSP 参与者 |
| 价格 | 市场决定 |
| 库存质量 | 参差不齐 |
| 适用场景 | 大规模投放 |

**私有市场（PMP）：**

| 特性 | 说明 |
|------|------|
| 可用性 | 邀请制 |
| 价格 | 竞价或固定 |
| 库存质量 | 优质 |
| 适用场景 | 高端品牌 |

**程序化保量（PG）：**

| 特性 | 说明 |
|------|------|
| 可用性 | 合同保证 |
| 价格 | 固定 |
| 库存质量 | 保证 |
| 适用场景 | 大额品牌投放 |

### 3.3 竞价策略

**动态竞价：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| Target CPA | 目标每次转化费用 | 转化优化 |
| Target ROAS | 目标广告支出回报率 | 收入优化 |
| Viewable CPM | 可见展示计费 | 品牌曝光 |
| Max Clicks | 最多点击 | 引流 |
| Max Conversions | 最多转化 | 转化 |

## 四、定向策略详解

### 4.1 定向维度

**上下文定向（Contextual Targeting）：**

| 维度 | 说明 | 示例 |
|------|------|------|
| 关键词 | 页面内容关键词 | "running shoes", "fitness" |
| 分类 | 网站分类 | 体育、科技、时尚 |
| URL | 具体网站 | example.com |
| App | 移动应用 | Fitbit, Strava |

**受众定向（Audience Targeting）：**

| 类型 | 说明 | 示例 |
|------|------|------|
| 第一方受众 | 广告主自有数据 | 客户列表、网站访客 |
| 第二方受众 | 发布商数据 | 媒体公司受众 |
| 第三方受众 | 数据提供商 | Google Ads Data Hub |

**人口统计定向：**

| 维度 | 选项 | 示例 |
|------|------|------|
| 年龄 | 13-65+ | 25-34, 35-44 |
| 性别 | 所有、男性、女性 | 女性 25-44 |
| 家长状态 | 所有、有孩子、无孩子 | 有 3 岁以下孩子 |
| 家庭收入 | 所有、分位数 | 前 25% |

### 4.2 受众细分

**In-Market Audiences（意向受众）：**

| 类别 | 说明 | 示例 |
|------|------|------|
| 汽车购买者 | 正在购车的人 | 汽车买家 |
| 酒店预订者 | 正在预订酒店的人 | 旅行者 |
| 在线购物者 | 经常网购的人 | 电商用户 |
| 金融服务者 | 寻求金融服务的人 | 贷款申请者 |

**Life Events（人生大事）：**

| 事件 | 说明 | 适用产品 |
|------|------|----------|
| 新婚 | 最近结婚的人 | 家居、蜜月旅行 |
| 搬家 | 最近搬家的人 | 家具、装修 |
| 新工作 | 刚找到工作的人 | 职业装、理财 |
| 新生儿 | 最近有宝宝的人 | 母婴用品 |

## 五、创意管理详解

### 5.1 创意格式

**展示广告格式：**

| 格式 | 尺寸 | 说明 |
|------|------|------|
| 横幅广告 | 728x90, 300x250 | 标准尺寸 |
| 矩形广告 | 336x280, 300x600 | 大尺寸 |
| 原生广告 | 自适应 | 与内容融合 |
| HTML5 广告 | 自适应 | 富媒体交互 |

**视频广告格式：**

| 格式 | 时长 | 说明 |
|------|------|------|
| Pre-roll | 15-30 秒 | 视频前广告 |
| Mid-roll | 15-60 秒 | 视频中广告 |
| Post-roll | 15-30 秒 | 视频后广告 |
| Bumper | ≤6 秒 | 快闪广告 |

### 5.2 创意优化

**创意 A/B 测试：**

```
测试变量
├── 创意格式
│   ├── 静态图片 vs 视频
│   ├── HTML5 vs 静态
│   └── 不同尺寸
├── 创意内容
│   ├── 不同文案
│   ├── 不同图片
│   └── 不同 CTA
└── 创意风格
    ├── 产品导向 vs 情感导向
    ├── 促销导向 vs 品牌导向
    └── 用户生成 vs 专业制作
```

## 六、测量与归因详解

### 6.1 转化追踪

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

| 工具 | 说明 | 用途 |
|------|------|------|
| Moat | 品牌安全和可见性 | 品牌测量 |
| DoubleVerify | 品牌安全和可见性 | 验证测量 |
| Integral Ad Science | 广告安全性和质量 | 质量控制 |
| comScore | 受众测量 | 效果评估 |

### 6.2 归因模型

**归因模型类型：**

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| Last Click | 最后一次点击 | 简单转化 |
| First Click | 第一次点击 | 新客获取 |
| Linear | 均匀分配 | 全链路分析 |
| Time Decay | 时间衰减 | 短期转化 |
| Position Based | 首尾加权 | 品牌 + 转化 |
| Data-Driven | 数据驱动 | 优化投放 |

## 七、自测题

1. 程序化广告的生态系统是怎样的？
2. RTB 竞价流程是怎样的？时间线如何？
3. 四种交易类型各有什么特点？
4. 归因模型有哪些？各自适用什么场景？

## 八、动手验证

```bash
# 1. 创建 DV360 账户
# 访问 https://dv360.google.com

# 2. 创建 IO
# - 设置预算
# - 设置排期
# - 选择 Exchange

# 3. 创建 Line Item
# - 选择广告格式
# - 设置定向
# - 上传创意

# 4. 设置转化追踪
# - 配置 Google Tag
# - 设置归因模型
# - 集成第三方测量

# 5. 监控和优化
# - 每日检查表现
# - 每周优化定向
# - 每月分析 ROI
```

---

## 第七部分：Go 生产级实现

### DV360 广告请求处理引擎 — Go 源码

```go
package main

import (
	"fmt"
	"sync"
	"time"
)

// AdRequest represents an incoming ad request from a publisher.
type AdRequest struct {
	UserID      string
	PageURL     string
	DeviceType  string // "mobile", "desktop", "tablet"
	GeoLocation string // "US", "CN", "JP"
	Timestamp   time.Time
}

// AdSlot represents a placement on the page where an ad can be shown.
type AdSlot struct {
	ID       string
	Width    int
	Height   int
	Format   string // "banner", "video", "native"
	MinCPM   float64
}

// MatchedAd is an ad that passed all filtering criteria.
type MatchedAd struct {
	AdID    string
	CPM     float64
	Creative string
	Targeting map[string]string
}

// DV360Bidder handles the core ad matching and bidding logic.
type DV360Bidder struct {
	mu       sync.RWMutex
	adIndex  map[string][]MatchedAd // format -> ads
	budgetDB map[string]float64     // advertiser -> remaining budget
}

func NewDV360Bidder() *DV360Bidder {
	return &DV360Bidder{
		adIndex:  make(map[string][]MatchedAd),
		budgetDB: make(map[string]float64),
	}
}

// RegisterAd adds an ad to the index by format for fast lookup.
func (b *DV360Bidder) RegisterAd(ad MatchedAd) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.adIndex[ad.Creative] = append(b.adIndex[ad.Creative], ad)
}

// SetBudget sets or updates an advertiser's budget.
func (b *DV360Bidder) SetBudget(advertiser string, budget float64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.budgetDB[advertiser] = budget
}

// MatchAds finds all ads matching the request within the time budget.
func (b *DV360Bidder) MatchAds(req AdRequest, slots []AdSlot, timeBudget time.Duration) []MatchedAd {
	start := time.Now()
	var results []MatchedAd

	b.mu.RLock()
	for _, slot := range slots {
		ads := b.adIndex[slot.Format]
		for _, ad := range ads {
			if time.Since(start) > timeBudget {
				break
			}
			// Check budget
			budget, ok := b.budgetDB[ad.AdID]
			if !ok || budget <= 0 {
				continue
			}
			// Check minimum CPM
			if ad.CPM < slot.MinCPM {
				continue
			}
			results = append(results, ad)
		}
	}
	b.mu.RUnlock()

	return results
}

// Deduplicate removes duplicate ads by AdID, keeping highest CPM.
func Deduplicate(ads []MatchedAd) []MatchedAd {
	seen := make(map[string]MatchedAd)
	for _, ad := range ads {
		existing, exists := seen[ad.AdID]
		if !exists || ad.CPM > existing.CPM {
			seen[ad.AdID] = ad
		}
	}
	results := make([]MatchedAd, 0, len(seen))
	for _, ad := range seen {
		results = append(results, ad)
	}
	return results
}
```

### Go 代码深度解析

**sync.RWMutex 为什么用 RWMutex 而非 Mutex？**

广告匹配是**读多写少**场景（每秒万级请求只注册少量新广告），RWMutex 允许多个读操作并发，显著提升吞吐量：

```
Mutex:     1000 req/s（串行读写）
RWMutex:   5000+ req/s（读操作并行）
```

**时间预算保护：**

```go
if time.Since(start) > timeBudget { break }
```

广告竞价延迟要求 < 100ms，必须防止某个慢查询拖垮整体响应。

---

## 第八部分：自测题

### 问题 1：DV360 广告匹配中，为什么 adIndex 用 `map[string][]MatchedAd` 而不是直接存 `[]MatchedAd` 全量扫描？

<details>
<summary>查看答案</summary>

**O(1) vs O(n) 的关键差异**：

```
全量扫描: n=10000 ads → 每次请求遍历 10000 条 → ~5ms
格式索引: 按 format 分组 → 只遍历 banner 格式的 200 条 → ~0.1ms
```

`map[string][]MatchedAd` 的 key 是广告格式（banner/video/native），匹配时先按 slot.Format 查 Map 拿到对应格式的 ads 列表，再逐个检查预算和 CPM。这样避免了全量扫描。

如果数据量小（< 100），全量扫描反而更快（Map 查找有 overhead）。但 DV360 有百万级广告，索引是必须的。

</details>

### 问题 2：MatchAds 函数中为什么用 RLock/RUnlock 而不是 Lock/Unlock？

<details>
<summary>查看答案</summary>

**读多写少的并发模型**：

- `RegisterAd` 和 `SetBudget` 是写操作，使用 `Lock/Unlock`（排他锁）
- `MatchAds` 是读操作，使用 `RLock/RUnlock`（共享锁）

RLock 允许多个 MatchAds 同时执行（因为只读 adIndex 和 budgetDB），而 Lock 会阻塞所有其他操作。

在广告竞价场景中，QPS 通常在 10000+，而广告注册/预算更新可能只有几次/秒。如果用普通 Mutex，所有竞价请求会串行化，严重降低吞吐量。

</details>

### 问题 3：Deduplicate 函数中为什么用 map[string]MatchedAd 去重而不是先排序再去重？

<details>
<summary>查看答案</summary>

**时间复杂度对比**：

```
排序去重: O(n log n) + O(n) 遍历
Map去重: O(n) 单次遍历
```

对于 n=100 的广告候选集，两种方法差异不大。但 Map 去重的优势在于：
1. **边遍历边决策**：遇到重复 AdID 时直接比较 CPM，保留最高者
2. **无需额外排序步骤**：省掉 O(n log n) 的排序开销
3. **天然支持高 CPM 优先**：`if !exists || ad.CPM > existing` 一行搞定

当广告候选集变大（n > 10000）时，排序去重可能更省内存（Map 需要 O(n) 额外空间），但在广告竞价的小候选集场景下，Map 去重是最优选择。

</details>

---

## 第七部分：Go 生产级实现

### DV360 广告请求处理引擎 — Go 源码

```go
package main

import (
	"fmt"
	"sync"
	"time"
)

// AdRequest represents an incoming ad request from a publisher.
type AdRequest struct {
	UserID      string
	PageURL     string
	DeviceType  string
	GeoLocation string
	Timestamp   time.Time
}

// AdSlot represents a placement on the page where an ad can be shown.
type AdSlot struct {
	ID       string
	Width    int
	Height   int
	Format   string
	MinCPM   float64
}

// MatchedAd is an ad that passed all filtering criteria.
type MatchedAd struct {
	AdID    string
	CPM     float64
	Creative string
	Targeting map[string]string
}

// DV360Bidder handles the core ad matching and bidding logic.
type DV360Bidder struct {
	mu       sync.RWMutex
	adIndex  map[string][]MatchedAd
	budgetDB map[string]float64
}

func NewDV360Bidder() *DV360Bidder {
	return &DV360Bidder{
		adIndex:  make(map[string][]MatchedAd),
		budgetDB: make(map[string]float64),
	}
}

func (b *DV360Bidder) RegisterAd(ad MatchedAd) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.adIndex[ad.Creative] = append(b.adIndex[ad.Creative], ad)
}

func (b *DV360Bidder) SetBudget(advertiser string, budget float64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.budgetDB[advertiser] = budget
}

func (b *DV360Bidder) MatchAds(req AdRequest, slots []AdSlot, timeBudget time.Duration) []MatchedAd {
	start := time.Now()
	var results []MatchedAd

	b.mu.RLock()
	for _, slot := range slots {
		ads := b.adIndex[slot.Format]
		for _, ad := range ads {
			if time.Since(start) > timeBudget {
				break
			}
			budget, ok := b.budgetDB[ad.AdID]
			if !ok || budget <= 0 {
				continue
			}
			if ad.CPM < slot.MinCPM {
				continue
			}
			results = append(results, ad)
		}
	}
	b.mu.RUnlock()

	return results
}

func Deduplicate(ads []MatchedAd) []MatchedAd {
	seen := make(map[string]MatchedAd)
	for _, ad := range ads {
		existing, exists := seen[ad.AdID]
		if !exists || ad.CPM > existing.CPM {
			seen[ad.AdID] = ad
		}
	}
	results := make([]MatchedAd, 0, len(seen))
	for _, ad := range seen {
		results = append(results, ad)
	}
	return results
}
```

### Go 代码深度解析

**sync.RWMutex 为什么用 RWMutex 而非 Mutex？**

广告匹配是读多写少场景（每秒万级请求只注册少量新广告），RWMutex 允许多个读操作并发，显著提升吞吐量。

**时间预算保护：**

```go
if time.Since(start) > timeBudget { break }
```

广告竞价延迟要求 < 100ms，必须防止某个慢查询拖垮整体响应。

---

## 第八部分：自测题

### 问题 1：DV360 广告匹配中，为什么 adIndex 用 `map[string][]MatchedAd` 而不是直接存 `[]MatchedAd` 全量扫描？

<details>
<summary>查看答案</summary>

全量扫描: n=10000 ads → 每次请求遍历 10000 条 → ~5ms
格式索引: 按 format 分组 → 只遍历 banner 格式的 200 条 → ~0.1ms

map[string][]MatchedAd 的 key 是广告格式，匹配时先按 slot.Format 查 Map 拿到对应格式的 ads 列表，再逐个检查预算和 CPM。这样避免了全量扫描。

</details>

### 问题 2：MatchAds 函数中为什么用 RLock/RUnlock 而不是 Lock/Unlock？

<details>
<summary>查看答案</summary>

读多写少的并发模型：RegisterAd 和 SetBudget 是写操作使用 Lock/Unlock，MatchAds 是读操作使用 RLock/RUnlock。RLock 允许多个 MatchAds 同时执行，而 Lock 会阻塞所有其他操作。在广告竞价场景中 QPS 通常在 10000+，如果用普通 Mutex 所有竞价请求会串行化。

</details>

### 问题 3：Deduplicate 函数中为什么用 map[string]MatchedAd 去重而不是先排序再去重？

<details>
<summary>查看答案</summary>

排序去重: O(n log n) + O(n) 遍历
Map去重: O(n) 单次遍历

Map 去重的优势：边遍历边决策，遇到重复 AdID 时直接比较 CPM 保留最高者；无需额外排序步骤；天然支持高 CPM 优先。

</details>

---

## 第七部分：Go 生产级实现

### DV360 广告请求处理引擎 — Go 源码

```go
package main

import (
	"fmt"
	"sync"
	"time"
)

// AdRequest represents an incoming ad request from a publisher.
type AdRequest struct {
	UserID      string
	PageURL     string
	DeviceType  string
	GeoLocation string
	Timestamp   time.Time
}

// AdSlot represents a placement on the page where an ad can be shown.
type AdSlot struct {
	ID       string
	Width    int
	Height   int
	Format   string
	MinCPM   float64
}

// MatchedAd is an ad that passed all filtering criteria.
type MatchedAd struct {
	AdID    string
	CPM     float64
	Creative string
	Targeting map[string]string
}

// DV360Bidder handles the core ad matching and bidding logic.
type DV360Bidder struct {
	mu       sync.RWMutex
	adIndex  map[string][]MatchedAd
	budgetDB map[string]float64
}

func NewDV360Bidder() *DV360Bidder {
	return &DV360Bidder{
		adIndex:  make(map[string][]MatchedAd),
		budgetDB: make(map[string]float64),
	}
}

func (b *DV360Bidder) RegisterAd(ad MatchedAd) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.adIndex[ad.Creative] = append(b.adIndex[ad.Creative], ad)
}

func (b *DV360Bidder) SetBudget(advertiser string, budget float64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.budgetDB[advertiser] = budget
}

func (b *DV360Bidder) MatchAds(req AdRequest, slots []AdSlot, timeBudget time.Duration) []MatchedAd {
	start := time.Now()
	var results []MatchedAd

	b.mu.RLock()
	for _, slot := range slots {
		ads := b.adIndex[slot.Format]
		for _, ad := range ads {
			if time.Since(start) > timeBudget {
				break
			}
			budget, ok := b.budgetDB[ad.AdID]
			if !ok || budget <= 0 {
				continue
			}
			if ad.CPM < slot.MinCPM {
				continue
			}
			results = append(results, ad)
		}
	}
	b.mu.RUnlock()

	return results
}

func Deduplicate(ads []MatchedAd) []MatchedAd {
	seen := make(map[string]MatchedAd)
	for _, ad := range ads {
		existing, exists := seen[ad.AdID]
		if !exists || ad.CPM > existing.CPM {
			seen[ad.AdID] = ad
		}
	}
	results := make([]MatchedAd, 0, len(seen))
	for _, ad := range seen {
		results = append(results, ad)
	}
	return results
}
```

---

## 第八部分：自测题

### 问题 1：DV360 广告匹配中，为什么 adIndex 用 `map[string][]MatchedAd` 而不是全量扫描？

<details>
<summary>查看答案</summary>

全量扫描: n=10000 ads → 每次请求遍历 10000 条
格式索引: 按 format 分组 → 只遍历对应格式的 ads

map[string][]MatchedAd 的 key 是广告格式，匹配时先按 slot.Format 查 Map 拿到对应列表，再逐个检查预算和 CPM。避免了 O(n) 全量扫描。

</details>

### 问题 2：MatchAds 函数中为什么用 RLock/RUnlock 而不是 Lock/Unlock？

<details>
<summary>查看答案</summary>

读多写少场景：RegisterAd/SetBudget 是写操作用 Lock/Unlock，MatchAds 是读操作用 RLock/RUnlock。RLock 允许多个 MatchAds 同时执行（因为只读），而 Lock 会阻塞所有其他操作。QPS 10000+ 时用普通 Mutex 会导致串行化。

</details>

### 问题 3：Deduplicate 用 map 去重 vs 排序去重的 Trade-off？

<details>
<summary>查看答案</summary>

排序去重: O(n log n) + O(n) 遍历
Map去重: O(n) 单次遍历

Map 去重优势：边遍历边决策，遇到重复 AdID 直接比较 CPM 保留最高者；无需额外排序步骤。小候选集（n < 100）Map 最优，大数据量（n > 10000）排序去重可能更省内存。

</details>
