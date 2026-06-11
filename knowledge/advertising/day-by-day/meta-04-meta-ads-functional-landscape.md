# Meta Ads — 平台功能全景深度梳理

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — 平台功能全覆盖

---

## 第一部分: 广告层级体系

### 1.1 Meta 广告层级 (Ad Account Hierarchy)

```
Meta 广告采用四层级结构:

┌──────────────────────────────────────────────────────────────┐
│                  Meta 广告层级                                 │
│                                                              │
│  1. Campaign (广告系列)                                       │
│     ├── 目标 (Objective): 品牌认知/流量/互动/安装/应用互动/线索/销售 │
│     ├── 预算类型: Campaign Budget (ACB) / Ad Group Budget     │
│     ├── 特殊目标: Campaign Budget Optimization / ABO / OCB   │
│     ├── 预算: 日预算/总预算                                    │
│     ├── 广告系列分组 (Ad Set Group)                            │
│     └─ 特殊类型: Advantage+ / ABO / 竞价控制                   │
│                                                              │
│  2. Ad Set (广告组)                                          │
│     ├── 定位 (Targeting): 地域/年龄/性别/语言/兴趣/行为/自定义 │
│     ├── 预算: 日预算/总预算 (ABO)                             │
│     ├── 排期: 开始日期/结束日期                                 │
│     ├── 竞价类型: Lowest Cost / Cost Cap / Bid Cap            │
│     ├── 优化与目标: 转化/点击/展示/视频观看/应用互动/线索/销售   │
│     ├── 出价: CPA/ROAS/频次控制                                │
│     ├── 受众: 自定义/类似/第一方/排除                          │
│     ├── 展示位置: Advantage+ / 手动选择                       │
│     ├── 频率控制: Frequency Cap                               │
│     └─ 报告时间窗口: 7d_click/1d_click/7d_view/1d_view       │
│                                                              │
│  3. Ad (广告)                                                │
│     ├── 格式: 单图/视频/轮播/收藏/动态广告                      │
│     ├── 创意: 图片/视频/标题/文案/CTA链接                       │
│     ├── 产品: Product Set (动态广告)                           │
│     ├── 落地页: URL/动态落地页                                  │
│     ├── 追踪: Pixel/Conversion API                            │
│     └─ 审核状态: Pending/Approved/Rejected                   │
│                                                              │
│  4. Creative (创意) - 可复用                                   │
│     ├── 媒体: 图片/视频/轮播/AR                                │
│     ├── 配置: 标题/描述/CTA/链接                                │
│     └─ 模板: 预置模板/自定义                                    │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Campaign Objective 全解

```
Meta 有 10 种广告系列目标 (Objectives):

┌──────────────────────────────────────────────────────────────┐
│              Meta Campaign Objectives                         │
│                                                              │
│  品牌认知 (Awareness):                                       │
│  ├── Brand Awareness — 品牌知名度                             │
│  │   └─ 优化: 品牌搜索/回忆度                                  │
│  │   └─ 竞价: Lowest Cost / Cost Cap                         │
│  │   └─ 指标: Reach / Frequency / BRAS                       │
│  │   └─ 适用: 新产品上市 / 品牌广告                            │
│  │                                                          │
│  └── Reach — 最大触达                                         │
│      └─ 优化: 最多触达人数                                    │
│      └─ 竞价: Lowest Cost                                   │
│      └─ 指标: Reach / Frequency / CPM                         │
│      └─ 适用: 大活动推广                                      │
│                                                              │
│  流量 (Traffic):                                              │
│  └── Traffic — 引导流量                                        │
│      └─ 优化: 链接点击                                        │
│      └─ 竞价: Lowest Cost / Cost Cap                        │
│      └─ 指标: CPC / CTR / Link Clicks                         │
│      └─ 适用: 网站引流 / 内容推广                              │
│                                                              │
│  互动 (Engagement):                                           │
│  └── Engagement — 增加互动                                     │
│      └─ 优化: 帖子互动/页面互动/消息互动/视频观看/应用互动       │
│      └─ 竞价: Lowest Cost                                   │
│      └─ 指标: CPC / CPM / Cost Per Engagement                 │
│      └─ 适用: 提升品牌互动                                     │
│                                                              │
│  应用 (App):                                                  │
│  ├── App Installs — 应用安装                                  │
│  │   └─ 优化: 安装量                                          │
│  │   └─ 适用: 移动应用推广                                    │
│  │                                                          │
│  └── App Engagement — 应用内互动                              │
│      └─ 优化: 应用内事件 (注册/购买/分享等)                     │
│      └─ 适用: 提升应用活跃度                                    │
│                                                              │
│  线索 (Leads):                                                │
│  └── Leads — 收集线索                                          │
│      └─ 优化: 表单提交/电话/邮件/消息                           │
│      └─ 竞价: Lowest Cost / Cost Cap / Lead Quality         │
│      └─ 指标: CPL / Lead Quality Score                        │
│      └─ 适用: B2B 销售 / 服务推广                              │
│                                                              │
│  销售 (Sales):                                                │
│  └── Conversions — 转化                                        │
│      └─ 优化: 转化 (Pixel/CAPI)                               │
│      └─ 竞价: Lowest Cost / Cost Cap / tROAS                │
│      └─ 指标: CPA / ROAS / Purchase Value                     │
│      └─ 适用: 电商销售 / 转化优化                               │
│                                                              │
│  视频 (Video):                                                │
│  └── Video Views — 视频观看                                    │
│      └─ 优化: 视频观看次数                                     │
│      └─ 竞价: Lowest Cost / Cost Cap                        │
│      └─ 指标: VCPM / Video Views / ThruPlays                │
│      └─ 适用: 品牌视频推广                                     │
│                                                              │
│  本地 (Local):                                                 │
│  └── Local Awareness — 到店流量                                │
│      └─ 优化: 到店次数                                         │
│      └─ 适用: 零售/餐厅                                          │
│                                                              │
│  消息 (Messages):                                              │
│  └── Messages — 消息互动                                       │
│      └─ 优化: Messenger/WhatsApp/Instagram DM 互动            │
│      └─ 适用: 客户服务/销售线索                                  │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 预算类型

```
Meta 预算类型:

1. Campaign Budget (CBP / ACB):
   ├── 在广告系列级别设置预算
   ├── Meta 自动在广告组间分配
   └── 优势: 更稳定, 更好学习, 减少频繁调整

2. Ad Set Budget (ABO):
   ├── 在每个广告组设置预算
   ├── 手动控制每个广告组的支出
   └── 优势: 精细控制, 适合 A/B 测试

3. Special Budgets:
   ├── Campaign Budget Optimization (CBO): 自动分配预算
   ├── Advantage+ Campaign Budget (ACB): 更智能的自动分配
   └── Shared Budget: 跨广告系列共享
```

---

## 第二部分: 定位系统 (Targeting)

### 2.1 定位类型

```
Meta 定位系统:

1. Location (地理位置):
   ├── 国家/地区/城市/邮编
   ├── 半径 (以某点为中心 N 公里)
   ├── 只展示/只触达/正在访问/曾经访问过
   └─ 高级: 动态半径 (根据表现自动调整)

2. Demographics (人口统计):
   ├── 年龄 (13-65+)
   ├── 性别 (Male/Female/All)
   ├── 语言
   ├── 教育水平
   ├── 职业
   ├── 关系状态
   ├── 父母状态
   ├── 家庭收入

3. Interests (兴趣):
   ├── 按兴趣标签筛选
   ├── 按页面粉丝筛选
   ├── 按行为筛选 (购买行为/旅行行为等)
   └─ 扩展: 关联兴趣 (扩大范围)

4. Behaviors (行为):
   ├── 数字活动 (使用 Facebook 的频率)
   ├── 旅行行为
   ├── 购买行为
   ├── 设备使用
   └─ 第三方数据 (信用评分/保险等)

5. Custom Audience (自定义受众):
   ├── 客户列表 (CRM 上传)
   ├── 网站自定义受众 (Pixel 数据)
   ├── 应用自定义受众 (App SDK)
   ├── 页面受众 (页面互动者)
   ├── 视频受众 (视频观看者)
   ├── 消息受众 (Messenger 互动者)
   └─ 混合: 组合多个来源

6. Lookalike Audience (类似受众):
   ├── 基于种子受众创建
   ├── 1-10% 相似度
   ├── 支持国家/地区限制
   └─ 最新: Advantage+ Audience (自动发现)

7. Advantage+ Audience:
   ├── 只提供排除列表
   ├── Meta 自动寻找目标受众
   └── 效果通常优于手动定向
```

### 2.2 展示位置 (Placements)

```
Meta 展示位置:

1. Facebook:
   ├── Feed (信息流)
   ├── Stories (快拍)
   ├── Right Column (右侧栏)
   ├── Search (搜索)
   ├── Marketplace (市集)
   ├── In-Article (文章中)
   ├── Reels (短视频)
   └─ Video Feeds (视频流)

2. Instagram:
   ├── Feed (信息流)
   ├── Stories (快拍)
   ├── Reels (短视频)
   ├── Explore (探索)
   └─ Search (搜索)

3. Messenger:
   ├── Stories (快拍)
   ├── Sponsored Messages (赞助消息)
   └─ Place Ad (放置广告)

4. Audience Network:
   ├── Mobile Apps (移动应用)
   ├── Desktop Websites (桌面网站)
   └─ Native Ads (原生广告)

5. Advantage+ Placements:
   ├── 自动选择最优位置
   ├── 跨所有位置展示
   └── 通常推荐开启
```

---

## 第三部分: 竞价与优化

### 3.1 竞价类型

```
Meta 竞价类型:

1. Lowest Cost (最低成本):
   ├── 自动优化, 在预算内获取最多结果
   ├── 适合大多数场景
   └─ 无出价上限

2. Cost Per Impression (CPM):
   ├── 按千次展示付费
   ├── 适合品牌曝光
   └─ 适合视频广告

3. Cost Cap (成本上限):
   ├── 设定平均 CPA 上限
   ├── 允许短期波动
   └─ 适合稳定转化

4. Bid Cap (出价上限):
   ├── 设定单次转化最高出价
   ├── 不会超过此出价
   └─ 适合预算有限

5. Min ROAS (最低 ROAS):
   ├── 设定最低回报率
   └─ 适合追求 ROI 的广告主

6. Target Cost (目标成本):
   ├── 设定稳定成本
   └─ 已部分被 Cost Cap 取代
```

### 3.2 优化与目标

```
广告组优化与目标 (Optimization Goal):

┌──────────────────────────────────────────────────────────────┐
│  广告系列目标 → 优化目标                                       │
│                                                              │
│  Brand Awareness → BRAS (Brand lift) / Reach                │
│  Traffic → Link Clicks / Landing Page Views                 │
│  Engagement → Post Engagement / Page Likes / Message        │
│              / Video Views / Lead Form Views / Quoting      │
│  App → App Installs / App Event / Value                       │
│  Leads → Lead (Form) / Call (Call to Action)                │
│         / Message / WhatsApp Conversation / Email            │
│  Sales → Conversion / Catalog Sales / Store Traffic / Lead  │
│  Video → Video Views / ThruPlay / Landing Page Views        │
│  Messages → Messenger / WhatsApp / Instagram DM             │
└──────────────────────────────────────────────────────────────┘
```

---

## 第四部分: Creative 创意系统

### 4.1 创意格式

```
Meta 创意格式:

1. Single Image (单图):
   ├── 推荐尺寸: 1200x628 (1.91:1)
   ├── 最小尺寸: 600x600 (1:1)
   └─ 适用: 产品展示/品牌广告

2. Video (视频):
   ├── 格式: MP4/MOV
   ├── 推荐尺寸: 1080x1080 (1:1) / 1080x1920 (9:16) / 1920x1080 (16:9)
   ├── 最长: 240 秒 (Feed) / 15 秒 (Stories/Reels)
   └─ 适用: 品牌故事/产品演示

3. Carousel (轮播):
   ├── 最多 10 张卡片
   ├── 每张: 图片/视频 + 标题 + 描述 + CTA
   └─ 适用: 产品系列/服务展示

4. Collection (收藏):
   ├── 主图/视频 + 产品网格
   ├── 点击后打开 Instant Experience
   └─ 适用: 电商

5. Dynamic (动态):
   ├── 自动匹配产品
   ├── 基于 Product Catalog
   └─ 适用: 电商

6. Instant Experience (即时体验):
   ├── 全屏沉浸式体验
   ├── 加载快 (无需跳转)
   └─ 适用: 品牌/电商

7. Messenger/WhatsApp Chat:
   ├── 消息互动广告
   ├── 自动回复 + 人工客服
   └─ 适用: 客户服务/销售
```

---

## 第五部分: Meta Graph API

### 5.1 API 核心端点

```
Meta Graph API 核心端点:

┌──────────────────────────────────────────────────────────────┐
│              Meta Graph API 核心端点                          │
│                                                              │
│  端点              | 用途                        | 方法     │
│  ├─ /v20.0/{adaccount}/campaigns  | 管理广告系列      | GET/POST/PUT/DELETE │
│  ├─ /v20.0/{adaccount}/adsets     | 管理广告组        | GET/POST/PUT/DELETE │
│  ├─ /v20.0/{adaccount}/ads        | 管理广告          | GET/POST/PUT/DELETE │
│  ├─ /v20.0/{adaccount}/assets      | 管理创意          | GET/POST/PUT/DELETE │
│  ├─ /v20.0/{adaccount}/customconversions | 自定义转化   | GET/POST/PUT/DELETE │
│  ├─ /v20.0/{pixel}/events          | 发送转化事件      | POST              │
│  ├─ /v20.0/{pixel}/batch           | 批量事件          | POST              │
│  ├─ /v20.0/{adaccount}/insights    | 获取洞察数据      | GET               │
│  └─ /v20.0/{business}/adaccounts   | 获取广告账户      | GET               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 字段选择器 (Field Selector)

```
Meta Graph API 支持字段选择:

GET /v20.0/{ad_account_id}/insights?fields=
  campaign.name,
  adset.name,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_per_total_action,
  date_preset=last_30d
  &access_token={token}

高级字段选择:
├─ 嵌套字段: adcreatives{title,image_url}
├─ 排序: ?sort=metric_name
├─ 过滤: ?filtering=[{field:"date_preset",operator:"lt",value:"last_7d"}]
└─ 分页: ?limit=100&after={cursor}

字段分组:
├─ metrics: 所有指标
├─ breakdowns: 所有细分
├─ actions: 所有行动
└─ action_values: 所有行动价值
```

### 5.3 批量操作 (Batch API)

```
Meta 批量操作:

允许一次性执行多个请求:

POST /v20.0/{business_id}?batch=[
  {
    "name": "create_campaign",
    "method": "POST",
    "relative_url": "{ad_account_id}/campaigns",
    "body": "name=Test Campaign&objective=CONVERSIONS&status=PAUSED"
  },
  {
    "name": "create_adset",
    "method": "POST",
    "relative_url": "{ad_account_id}/adsets",
    "body": "name=Test Ad Set&campaign_id={result=create_campaign:$.id}&status=PAUSED"
  },
  {
    "name": "get_insights",
    "method": "GET",
    "relative_url": "{ad_account_id}/insights?fields=metrics&time_range={%27since%27:%272026-01-01%27,%27until%27:%272026-01-31%27}"
  }
]

速率限制:
├─ 每个 batch: 最多 40 个请求
├─ 每 600 秒: 5000 个请求 (广告账户级别)
└─ 每 600 秒: 1000 个请求 (Pixel 级别)
```

---

## 第六部分: 转化追踪体系

### 6.1 转化追踪方式

```
Meta 转化追踪:

1. Meta Pixel:
   ├── 网页追踪代码
   ├── 标准事件: Purchase/Lead/AddToCart/CompleteRegistration/ViewContent/InitiateCheckout/AddToWishlist/Subscribe/Contact/Donate/CustomizeProduct/FindLocation/StartTrial/Contact/DemographicUpdate/ValueUpdate/UpdateAddress/UpdatePhone
   ├── 自定义事件: user_defined_event_name
   ├── 事件参数: value/currency/content_id/num_items/content_type/content_names
   └─ 安装: 直接代码/Google Tag Manager/Meta Partner

2. Conversion API (CAPI):
   ├── 服务器端事件追踪
   ├── 与 Pixel 互补 (弥补客户端追踪限制)
   ├── 用户 ID 匹配 (email/phone/外部 ID)
   ├── 适合: 电商/高价值转化
   └─ 实现: 直接 API/第三方 (Shopify/WordPress 等)

3. App Events:
   ├── App SDK 追踪
   ├── 标准应用事件
   └─ 适合: 移动应用

4. Offline Conversions:
   ├── 导入线下转化数据
   ├── 匹配用户
   └─ 适合: 零售/服务行业

5. Enhanced Match:
   ├── 自动匹配用户信息
   ├── 提高匹配率
   └─ 支持: email/phone/address/外部 ID
```

---

## 第七部分: Advantage+ 产品

### 7.1 Advantage+ 系列

```
Meta Advantage+ 产品线:

1. Advantage+ Campaign Budget (ACB):
   ├── 广告系列级别预算
   ├── Meta 自动分配
   └─ 推荐: 大多数场景

2. Advantage+ Audience:
   ├── 只提供排除列表
   ├── Meta 自动发现受众
   └─ 推荐: 大多数场景

3. Advantage+ Creative:
   ├── 自动测试不同创意组合
   ├── 动态创意优化
   └─ 推荐: 大多数场景

4. Advantage+ Shopping Campaign (ASC):
   ├── 电商自动化
   ├── 基于产品 Feed
   ├── 自动优化创意和受众
   └─ 需要: 产品 Catalog

5. Advantage+ Lead Ads:
   ├── 销售线索自动化
   ├── 自动优化受众
   └─ 适合: B2B/服务
```

---

## 第八部分: 账户结构与 API 资源

### 8.1 账户体系

```
Meta 账户体系:

┌──────────────────────────────────────────────────────────────┐
│                  Meta Business Manager                       │
│                                                              │
│  Business Manager (业务管理器)                                 │
│  ├── 广告账户 (Ad Accounts)                                   │
│  │   └─ 可多个 (不同客户/不同品牌)                             │
│  ├── 像素 (Pixel)                                             │
│  │   └─ 每个广告账户可有多个                                   │
│  ├── 产品目录 (Catalog)                                       │
│  │   └─ 用于动态广告                                          │
│  ├── 页面 (Pages)                                             │
│  │   └─ Facebook 页面                                         │
│  ├── Instagram 账户 (Instagram Accounts)                      │
│  ├── 应用 (Apps)                                              │
│  │   └─ 用于 App Tracking                                     │
│  ├── 用户 (Users)                                             │
│  │   └─ 团队成员/外部合作伙伴                                   │
│  └─ 权限管理                                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 第九部分: API 资源映射

```
┌──────────────────────────────────────────────────────────────┐
│              Meta Graph API 资源映射                          │
│                                                              │
│  资源              | API 端点                   | 用途       │
│  ├─ Campaign       | /{ad_account}/campaigns    | 管理广告系列 │
│  ├─ AdSet          | /{ad_account}/adsets       | 管理广告组   │
│  ├─ Ad             | /{ad_account}/ads          | 管理广告     │
│  ├─ AdCreative     | /{ad_account}/creatives    | 管理创意     │
│  ├─ AdAccount      | /{business}/adaccounts     | 管理广告账户 │
│  ├─ Pixel          | /{pixel_id}/events         | 发送事件     │
│  ├─ Event          | /{pixel_id}/events         | 批量事件     │
│  ├─ Insights       | /{ad_account}/insights     | 获取数据     │
│  ├─ CustomConversion| /{ad_account}/customconversions| 自定义转化 │
│  ├─ Catalog        | /{catalog_id}/products     | 产品目录     │
│  ├─ ProductSet     | /{catalog_id}/productsets  | 产品集       │
│  ├─ ProductGroup   | /{catalog_id}/productgroups| 产品组       │
│  ├─ CustomAudience | /{ad_account}/customaudiences| 自定义受众  │
│  ├─ LookalikeAudience | /{ad_account}/lookalikes | 类似受众    │
│  └─ Asset          | /{ad_account}/assets       | 管理资产     │
└──────────────────────────────────────────────────────────────┘
```

---

## 自测题

### 问题 1
Meta 有多少种广告系列目标 (Objectives)?

<details>
<summary>查看答案</summary>

10 种: Brand Awareness, Reach, Traffic, Engagement, App Installs, App Engagement, Leads, Sales, Video Views, Messages, Local Awareness
</details>

### 问题 2
Advantage+ Audience 的核心逻辑是什么？

<details>
<summary>查看答案</summary>

- 只提供排除列表 (不要投给谁)
- Meta 在剩余用户中自动寻找高价值用户
- 效果通常优于手动定向
</details>

### 问题 3
Meta 批量操作每 600 秒的限制是多少？

<details>
<summary>查看答案</summary>

- 广告账户级别: 5000 个请求
- Pixel 级别: 1000 个请求
- 每个 batch: 最多 40 个请求
</details>

---

### Meta Ads 功能体系的 Go 实现

```go
package metaads

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

type AdFormat string
const (
	FormatImage AdFormat = "IMAGE"
	FormatVideo AdFormat = "VIDEO"
	FormatCarousel AdFormat = "CAROUSEL"
	FormatCollection AdFormat = "COLLECTION"
)

type CampaignObjective string
const (
	ObjectiveBrandAwareness CampaignObjective = "BRAND_AWARENESS"
	ObjectiveReach CampaignObjective = "REACH"
	ObjectiveTraffic CampaignObjective = "TRAFFIC"
	ObjectiveEngagement CampaignObjective = "ENGAGEMENT"
	ObjectiveLeads CampaignObjective = "LEADS"
	ObjectiveSales CampaignObjective = "SALES"
)

type Campaign struct {
	ID           string            `json:"id"`
	Name         string            `json:"name"`
	Objective    CampaignObjective `json:"objective"`
	Status       string            `json:"status"`
	DailyBudget  float64           `json:"daily_budget"`
	SpecialAdCat string            `json:"special_ad_category"`
	AdSets       []*AdSet          `json:"ad_sets"`
}

type AdSet struct {
	ID         string        `json:"id"`
	Name       string        `json:"name"`
	Status     string        `json:"status"`
	BidAmount  float64       `json:"bid_amount"`
	OptimizationGoal string   `json:"optimization_goal"`
	Targeting  *Targeting    `json:"targeting"`
}

type Targeting struct {
	GeoLocations map[string]interface{} `json:"geo_locations"`
	Ages         []int                  `json:"ages"`
	Genders      []int                  `json:"genders"`
	Interests    []map[string]string    `json:"interests"`
}

type DynamicProductAd struct {
	SetID    string   `json:"set_id"`
	ImageURL string   `json:"image_url"`
	Headline string   `json:"headline"`
	CTA      string   `json:"cta"`
	Products []string `json:"products"`
}

type BatchOperation struct {
	requests []*BatchReq
	mu       sync.Mutex
}

type BatchReq struct {
	Name   string            `json:"name"`
	Method string            `json:"method"`
	Path   string            `json:"path"`
	Params map[string]string `json:"params"`
}

func (b *BatchOperation) AddCampaign(name, obj string, budget float64) string {
	id := fmt.Sprintf("camp_%d", len(b.requests))
	b.mu.Lock()
	defer b.mu.Unlock()
	b.requests = append(b.requests, &BatchReq{
		Name: id, Method: "POST", Path: "/act_123/campaigns",
		Params: map[string]string{"name": name, "objective": string(obj), "daily_budget": fmt.Sprintf("%.0f", budget)},
	})
	return id
}

func (b *BatchOperation) Execute() ([]BatchResp, error) {
	b.mu.Lock()
	reqs := make([]*BatchReq, len(b.requests))
	copy(reqs, b.requests)
	b.mu.Unlock()
	var results []BatchResp
	for i := 0; i < len(reqs); i += 50 {
		end := i + 50
		if end > len(reqs) { end = len(reqs) }
		chunk := reqs[i:end]
		results = append(results, BatchResp{Status: 200, Body: json.RawMessage("{}")})
	}
	return results, nil
}

type BatchResp struct {
	Status  int
	Body    json.RawMessage
	Headers map[string]string
}

func main() {
	camp := &Campaign{Name: "Summer Sale", Objective: ObjectiveSales, DailyBudget: 500.0}
	fmt.Printf("Campaign: %s (%s)\n", camp.Name, camp.Objective)

	batch := &BatchOperation{}
	batch.AddCampaign("Sale Q1", ObjectiveSales, 1000)
	batch.AddCampaign("Brand Awareness", ObjectiveBrandAwareness, 2000)
	resps, _ := batch.Execute()
	fmt.Printf("Batch: %d requests\n", len(resps))
}
```

---

*今天花 90 分钟：系统掌握 Meta Ads 平台功能体系*
*答不出自测题？回去重读对应章节。*
