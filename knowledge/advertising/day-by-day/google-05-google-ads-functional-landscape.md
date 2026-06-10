# Google Ads — 平台功能全景深度梳理

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — 平台功能全覆盖

---

## 第一部分: Campaign 类型全览

### 1.1 八种 Campaign 类型详解

```
┌──────────────────────────────────────────────────────────────────┐
│                    Google Ads Campaign 体系                       │
│                                                                  │
│  Search Family:                                                  │
│  ├── Standard Search Campaign (SSC) — 完全控制                   │
│  ├── Smart Campaign — 简化版，适合小商家                          │
│  └── Performance Max (PMax) — 跨渠道自动化                       │
│                                                                  │
│  Display Family:                                                 │
│  ├── Standard Display Campaign — 自定义素材                      │
│  ├── Display Campaign (旧版) — 展示优先                           │
│  └── PMax (包含 Display)                                        │
│                                                                  │
│  Video Family:                                                   │
│  ├── Video Action Campaign (VAC) — 转化导向                     │
│  ├── In-Stream Skippable — YouTube 可跳过广告                    │
│  ├── In-Stream Non-Skippable — YouTube 不可跳过广告              │
│  ├── Bumper Ads — 6 秒不可跳过                                   │
│  ├── Out-Stream — 网站内视频广告                                 │
│  ├── Shorts Ads — TikTok 式竖屏短视频                            │
│  └── Max for Video — AI 视频广告                                │
│                                                                  │
│  Shopping Family:                                                │
│  ├── Standard Shopping — 手动关键词/出价                          │
│  ├── Performance Max Shopping — 自动化                          │
│  └── Local Inventory Ads (LIA) — 本地库存                        │
│                                                                  │
│  App Family:                                                     │
│  ├── App Campaign (Install) — 应用安装                           │
│  ├── App Campaign (Engagement) — 应用内互动                      │
│  ├── App Campaign (Revenue) — 应用内购买                         │
│  └── App Re-engagement — 召回老用户                              │
│                                                                  │
│  Discovery (已合并到 PMax):                                      │
│  └── 曾经是跨渠道 (Feed/Discover/Gmail) 的展示广告                │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 每种 Campaign 的深层特性

```
Standard Search Campaign (SSC):
────────────────────────────────────
├─ 出价策略: Manual CPC / Enhanced CPC / Smart Bidding (tCPA/tROAS/Max Conv/tImp Share)
├─ 定向: 关键词/受众/位置/设备/时段/语言/RSA/Dynamic Search Ads
├─ 广告格式: Responsive Search Ad (RSA) / Expanded Text Ad (ETA, 已退役)
├─ 展示位置: Google Search / Google Partners (Search Network Only)
├─ 报告粒度: 关键词级别 (最细)
├─ API 资源: CampaignService, AdGroupService, AdGroupCriterionService, AdGroupAdService
├─ 优势: 完全控制, 详细数据, 灵活优化
└─ 劣势: 管理成本高, 需要专业知识

Performance Max (PMax):
────────────────────────────────────
├─ 出价策略: tCPA / tROAS / Max Conversions / Max Conversion Value
├─ 定向: Signals (受众关键词/兴趣/网站URL/位置)
├─ 广告格式: Asset Groups (Images/Videos/Logos/Text/Headlines/Descriptions)
├─ 展示位置: Search/Display/YouTube/Gmail/Maps/Google Network
├─ 报告粒度: 广告系列级别 (最粗, 无关键词级数据)
├─ API 资源: CampaignService, AssetGroupService, AssetGroupAssetRelationService
├─ 优势: 自动化, 跨渠道, AI 优化
└─ 劣势: 黑盒, 无法控制关键词, 品牌词可能被竞对拦截

Video Action Campaign (VAC):
────────────────────────────────────
├─ 出价策略: tCPA / tROAS / Max Conversions / tVCPM / tReach
├─ 定向: 受众/关键词/placement/位置
├─ 广告格式: In-Stream/Out-Stream/Bumper/Shorts
├─ 展示位置: YouTube/YouTube Partners/Google Video Network
├─ 报告粒度: 视频广告级别
├─ API 资源: CampaignService, VideoService, AdGroupAdService
├─ 优势: 转化导向, 跨视频位置
└─ 劣势: 需要视频素材

Standard Shopping:
────────────────────────────────────
├─ 出价策略: Manual CPC / Enhanced CPC / tROAS
├─ 定向: 关键词 (不是受众)
├─ 广告格式: Product Ads (来自 Product Feed)
├─ 展示位置: Google Shopping / Google Search Shopping Tab
├─ 报告粒度: 产品/产品组级别
├─ API 资源: CampaignService, ProductPartitionService, FeedService, FeedItemService
├─ 优势: 基于产品, 自动匹配搜索词
└─ 劣势: Feed 管理复杂, 无法用受众定向

Local Inventory Ads (LIA):
────────────────────────────────────
├─ 出价策略: tROAS / tCPA / Max Conv
├─ 定向: 位置 (门店半径)
├─ 广告格式: Product Ads + 门店信息 (距离/库存)
├─ 展示位置: Google Search (本地结果) / Google Maps
├─ API 资源: CampaignService, LocalInventorySetService, LocalInventorySpecService
└─ 适合: 有实体店 + 线上渠道的品牌
```

---

## 第二部分: GAQL (Google Ads Query Language)

### 2.1 GAQL 结构

```
GAQL 是 Google Ads API 的 SQL-like 查询语言:

SELECT field1, field2
FROM resource_type
WHERE filter_conditions
GROUP BY dimension1, dimension2
ORDER BY metric DESC
LIMIT 1000

示例:
SELECT
  campaign.id,
  campaign.name,
  ad_group.id,
  ad_group.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.ctr
FROM ad_group
WHERE
  segments.date BETWEEN 2026-01-01 AND 2026-01-31
  AND campaign.status = ENABLED
ORDER BY metrics.conversions DESC
LIMIT 100

分页:
- 使用 page_token (分页标记)
- 每次请求最多返回 10,000 条记录
- GoogleAdsService.search 或 search_stream (推荐, 大数据量)
```

### 2.2 Metrics 分类

```
性能指标 (Performance Metrics):
├─ impressions: 展示次数
├─ clicks: 点击次数
├─ cost_micros: 花费 (微单位, 1 unit = 10^6 micros)
├─ conversions: 转化次数
├─ conversion_value: 转化价值
├─ views: 视频展示 (YouTube)
├─ active_view_impressions: 活跃展示 (可见广告)
├─ active_view_measurable_impressions: 可测量展示
├─ active_view_measurable_milliseconds: 可测量时间
├─ view_through_conversions: 展示转化

衍生指标 (Derived Metrics):
├─ ctr: 点击率 (clicks / impressions)
├─ avg_cpc: 平均 CPC (cost / clicks)
├─ avg_cpm: 平均 CPM (cost / impressions * 1000)
├─ cpa: 平均 CPA (cost / conversions)
├─ roas: 广告回报率 (conversion_value / cost)

视频指标 (Video Metrics):
├─ quartile_1: 首段播放完成
├─ quartile_25: 25% 播放完成
├─ quartile_50: 50% 播放完成 (中点)
├─ quartile_75: 75% 播放完成
├─ quartile_100: 完整播放完成
├─ completed_views: 完整播放
├─ retained_views_2s: 2秒留存
├─ retained_views_10s: 10秒留存
├─ retained_views_30s: 30秒留存
├─ view_rate: 视频观看率
├─ view_cost: 视频观看成本

互动指标 (Engagement Metrics):
├─ interactions: 互动次数
├─ interaction_rate: 互动率
├─ interaction_type: 互动类型 (click/phone_call/view_tel/email/zoom/directions/map_call/map_click/website_click)

质量指标 (Quality Metrics):
├─ quality_scores: 质量分 (搜索广告)
├─ expected_ctr: 预期点击率
├─ ad_strength: 广告强度 (RSA 评分)
```

### 2.3 Dimensions (维度)

```
时间维度:
├─ segments.date: 日期 (YYYY-MM-DD)
├─ segments.day_of_week: 星期几 (0=Sunday, 6=Saturday)
├─ segments.hour: 小时 (0-23)
├─ segments.week: 周 (YYYY_Www)
├─ segments.month: 月 (YYYY-MM)
├─ segments.dow: 星期几 (Sunday/Monday...)
├─ segments.hour_of_day: 小时 (0-23)
├─ segments.week_day: 星期 (0-6)
└─ segments.week_of_year: 年中的第几周

设备维度:
├─ customer.device: 设备类型 (mobile/desktop/tablet)
└─ segments.device: 同上

地理位置维度:
├─ customer.geo_target_constant: 地理目标 (国家/地区/城市)
├─ segments.city: 城市
├─ segments.city_criteria_id: 城市 ID
├─ segments.greater_city: 大都会区域
├─ segments.greater_region: 大都会区域
├─ segments.greater_country: 国家
├─ segments.hyperlocal: 超本地
├─ segments.metro_area: 都会区
├─ segments.region: 地区/省份
├─ segments.postal_code: 邮编
├─ segments.location_intent_state: 位置意向状态 (present/in_region/in_interest)
└─ segments.location_type: 位置类型

用户维度:
├─ segments.age_range: 年龄范围 (18-24/25-34/...)
├─ segments.gender: 性别 (MALE/FEMALE/UNKNOWN)
├─ segments.income_range: 收入范围 (lower/upper_middle/upper/higher)
├─ segments parental_status: 父母状态 (parent/non_parent)
└─ segments.user_list_name: 受众列表名称

广告维度:
├─ ad_group.id/name/type: 广告组
├─ ad_group_ad.ad.id/name/status: 广告
├─ ad_group_ad.ad.type: 广告类型 (RESPONSIVE_TEXT_AD/TEXT_AD/VIDEO_AD/...)
├─ ad_group_ad.ads: 嵌套广告字段
└─ criterion.type: 定向类型 (KEYWORD/AD_GROUP/AUDIENCE/...)

广告系列维度:
├─ campaign.id/name/status/type: 广告系列
├─ campaign.ad_serving_optimization_goal: 广告系列投放目标
├─ campaign.advertising_channel_type: 渠道类型 (SEARCH/DISPLAY/VIDEO/SHOPPING/APP/PMAX/DISCOVERY)
├─ campaign.advertising_channel_sub_type: 子渠道类型
└─ campaign.budget: 预算 (共享/独立)

```

### 2.4 嵌套结构

```
GAQL 支持嵌套结构:

1. campaign.ad_groups.ads:
   SELECT campaign.id, campaign.name,
          ad_group.id, ad_group.name,
          ad.id, ad.name, ad.type
   FROM campaign_ad
   WHERE campaign.status = ENABLED

2. campaign.ad_groups.criterion (keywords):
   SELECT campaign.id, ad_group.id, criterion.id, criterion.text
   FROM ad_group_criterion
   WHERE criterion.type = KEYWORD

3. campaign.budget:
   SELECT campaign.id, budget.amount_micros, budget.name
   FROM budget
```

---

## 第三部分: 报告系统深度

### 3.1 报告类型

```
1. Google Ads 内置报告:
   ├── 标准报告 (预设模板)
   │   ├── 广告系列报告
   │   ├── 广告组报告
   │   ├── 广告报告
   │   ├── 关键词报告
   │   ├── 搜索词报告
   │   ├── 受众报告
   │   ├── 位置报告
   │   ├── 设备报告
   │   ├── 时段报告
   │   └── 转化报告
   └── 自定义报告 (自己定义字段和维度)

2. Google Ads API 报告:
   ├── GoogleAdsService.search — 标准查询
   ├── GoogleAdsService.search_stream — 流式查询 (大数据量)
   └── GoogleAdsService.mutate — 修改操作

3. Google Analytics 4:
   ├── 更细的用户行为数据
   ├── 跨设备/跨会话追踪
   ├── 路径分析
   └── 需要链接 Google Ads

4. BigQuery Export:
   ├── 原始数据导出
   ├── 可以自定义分析
   ├── 成本按查询量计费
   └── 数据保留 120 天 (免费)

5. Looker Studio (原 Data Studio):
   ├── 可视化仪表板
   ├── 实时数据
   └── 多源数据整合
```

### 3.2 报告最佳实践

```
报告使用策略:
1. 日常监控: 内置标准报告 (速度最快)
2. 深度分析: 自定义报告 + 搜索词报告
3. 大规模分析: Google Ads API + BigQuery
4. 用户行为: GA4 链接

报告频率:
├─ 每日: 预算消耗/关键指标
├─ 每周: 关键词表现/搜索词报告
├─ 每月: 全面报告 + 优化建议
└─ 每季度: 战略回顾
```

---

## 第四部分: 转化跟踪全体系

### 4.1 转化类型

```
内置转化类型:
├─ Website: 网页转化 (购买/注册/下载/联系)
├─ Phone calls: 电话转化
│   ├── Incoming calls: 来电
│   ├── Calls from ads: 广告中的电话
│   └─ Forwarded calls: 转接电话
├─ App installs: 应用安装
├─ App engagement: 应用内互动
├─ App purchases: 应用内购买
├─ Google Play: Google Play 转化
├─ Facebook: Facebook 转化
└─ Other: 其他

自定义转化:
├─ 事件类型 (Event): 网页事件
├─ 应用事件 (App Event): 应用内事件
└─ 离线转化 (Offline Conversion): 导入 CRM 数据

转化设置:
├─ 名称 (Name)
├─ 分类 (Category): 销售/线索/网站流量/电话/应用
├─ 属性 (Attribute): 购买/注册/其他
├─ 计数 (Count): One/Every (每个转化 vs 每次转化)
├─ 转化价值 (Value): 固定/不同/使用规则
├─ 使用规则 (Use rule): 基于条件分配价值
├─ 窗口 (Window): 点击后30天/展示后7天
├─ 归属 (Attribution): Last click/Data-driven
└─ 仅计入 (Only include): 转化计数时包含
```

### 4.2 离线转化导入

```
通过 API 导入离线转化:

API 端点: ConversionUploadService

导入类型:
├─ upload_click_conversions — 基于 gclid 上传
├─ upload_conversions — 基于 Enhanced Conversions

增强版上传 (upload_enhanced_conversions):
├─ 支持 email/电话/地址等 PII 数据
├─ 数据自动哈希
├─ 匹配更宽泛
└─ 需要用户同意 (GDPR/CCPA 合规)
```

---

## 第五部分: 账户结构与生态

### 5.1 账户层级

```
账户结构:
┌──────────────────────────────────────────────────────────────┐
│  Manager Account (MCC) / Customer Account                    │
│                                                              │
│  ├── Shared Budget (预算共享)                                 │
│  ├── Shared Set (受众/关键词共享)                              │
│  ├── Campaign                                                  │
│  │   ├── Ad Group Sets (广告组集合, PMax 用)                  │
│  │   ├── Ad Group                                              │
│  │   │   ├── Ad Group Bid Modifier (出价调整)                  │
│  │   │   ├── Ad                                              │
│  │   │   │   ├── Responsive Search Ad (RSA)                  │
│  │   │   │   ├── Dynamic Search Ad (DSA)                     │
│  │   │   │   ├── Call-only Ad                                │
│  │   │   │   └── Shopping Ad (Product)                       │
│  │   │   ├── Criterion (定向)                                │
│  │   │   │   ├── Keyword (关键词)                             │
│  │   │   │   ├── Ad Group Bid Modifier (出价调整)             │
│  │   │   │   ├── Audience (受众)                              │
│  │   │   │   ├── Placement (展示位置)                         │
│  │   │   │   ├── Location (位置)                              │
│  │   │   │   └── Negative Criterion (否定)                   │
│  │   │   └── Feed (商品 Feed)                                │
│  │   └─ Campaign Bid Modifier (出价调整)                      │
│  └── Label (标签)                                             │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 生态集成

```
Google Ads 生态:
├─ Google Tag Manager (GTM): 标签管理
├─ Google Analytics 4 (GA4): 用户行为分析
├─ Google Search Console: 搜索性能
├─ Google Merchant Center: 商品 Feed
├─ BigQuery: 数据导出与分析
├─ Looker Studio: 可视化
├─ Google Cloud: AI/ML 集成
└─ Google Ads Editor: 桌面端批量编辑
```

---

## 第六部分: 广告格式全览

### 6.1 Search 广告格式

```
Responsive Search Ad (RSA):
├─ 标题: 最多 15 个 (每个 30 字符)
├─ 描述: 最多 4 个 (每个 90 字符)
├─ 最终 URL: 1 个
├─ 显示路径: 2 个 (可选)
├─ 附加信息: 最多 5 个 (附加链接/附加广告文字/结构化摘要)
└─ 动态关键词插入 (DKI): {KeyWord}

Dynamic Search Ad (DSA):
├─ 基于网页内容自动生成标题
├─ 基于 URL 规则生成广告
├─ 基于网站内容匹配搜索词
└─ 适合大量产品的网站
```

### 6.2 Display 广告格式

```
Responsive Display Ad:
├─ 图片: 最多 20 张 (推荐 1:1, 16:9, 4:5, 3:2, 4:3, 1:2, 2:1)
├─ Logo: 最多 5 个 (推荐 1:1, 4:1)
├─ 视频: 最多 5 个 (推荐 16:9, ≥5s)
├─ 标题: 最多 5 个 (30 字符)
├─ 描述: 最多 5 个 (90 字符)
└─ CTA: 选择 (Shop Now/Book Now/Install/Subscribe)

Image Ad:
├─ 上传自定义图片
├─ 支持多种尺寸 (16:9/1:1/2:1/1:2/...)
└─ 适合品牌广告

HTML5 Ad:
├─ 上传 .zip 文件
├─ 支持动画、交互
└─ 适合品牌广告
```

### 6.3 Video 广告格式

```
In-Stream Skippable:
├─ 播放超过 5 秒后可跳过
├─ 计费: 用户观看 30 秒/完整播放/互动 (CTA 点击)
├─ 格式: 横屏 16:9/竖屏 9:16/正方形 1:1
└─ 适用: 品牌故事/产品演示

In-Stream Non-Skippable:
├─ 不可跳过
├─ 最长 15 秒
├─ 计费: 每次展示
└─ 适用: 品牌认知

Bumper Ads:
├─ 6 秒不可跳过
├─ 计费: 每次展示
└─ 适用: 品牌提醒

Out-Stream:
├─ 出现在网站/APP 的 Feed 中
├─ 自动播放
└─ 适用: 移动端品牌曝光

Shorts Ads:
├─ TikTok 式竖屏短视频
├─ 在 YouTube Shorts Feed 中展示
└─ 适用: 年轻受众
```

---

## 第七部分: 出价策略全景

### 7.1 出价策略分类

```
┌──────────────────────────────────────────────────────────────┐
│              Google Ads 出价策略体系                          │
│                                                              │
│  手动出价:                                                   │
│  ├── Manual CPC — 手动设置 CPC                               │
│  ├── Enhanced CPC — 基于 pCVR 自动调整                        │
│  └── CPM — 按千次展示 (Display/Video)                         │
│                                                              │
│  智能出价 (Smart Bidding):                                  │
│  ├── Maximize Clicks — 最大化点击数                           │
│  ├── Maximize Conversions — 最大化转化数                      │
│  ├── Maximize Conversion Value — 最大化转化价值                │
│  ├── Target CPA (tCPA) — 目标每次转化费用                      │
│  ├── Target ROAS (tROAS) — 目标广告回报率                     │
│  ├── Target Impression Share — 目标展示份额                   │
│  ├── Target Outrank Share — 目标超越对手份额                   │
│  ├── Viewable CPM (vCPM) — 目标可见展示千次费用                │
│  ├── Cost Per Thousand (CPM) — 千次展示费用                    │
│  ├── Target Reach — 目标触达                                   │
│  └── Target Ad Outrank — 目标超越对手                          │
│                                                              │
│  视频/Display 特有:                                          │
│  ├── vCPM — 可见展示千次费用                                   │
│  ├── Target Reach — 目标触达                                   │
│  └── Frequency Cap — 频次控制                                 │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 出价策略对比

```
┌────────────────────────────────────────────────────────────────┐
│                    出价策略对比                                   │
│                                                                │
│  | 策略                  | 适用场景              | 数据要求      |
│  |---------------------|-------------------|-------------|
│  | Manual CPC          | 需要精细控制          | 无           |
│  | Enhanced CPC        | 基础优化             | 有转化数据    |
│  | Max Clicks          | 拉新/流量            | 无           |
│  | Max Conversions     | 追求转化量            | ≥15/月       |
│  | tCPA                | 控制 CPA             | ≥15/月       |
│  | tROAS               | 追求 ROI             | ≥15/月       |
│  | tImpression Share   | 品牌曝光             | 无           |
│  | vCPM                | 品牌展示             | 无           |
└────────────────────────────────────────────────────────────────┘
```

---

## 第八部分: API 资源映射表

```
┌──────────────────────────────────────────────────────────────────┐
│              Google Ads API 资源映射表                            │
│                                                                  │
│  资源                  | API 端点                  | 用途       │
│  ├─ Campaign           | CampaignService          | 管理广告系列 │
│  ├─ AdGroup            | AdGroupService           | 管理广告组   │
│  ├─ AdGroupAd          | AdGroupAdService         | 管理广告     │
│  ├─ AdGroupCriterion   | AdGroupCriterionService  | 管理定向/关键词 │
│  ├─ CampaignCriterion  | CampaignCriterionService | 管理广告系列定向 │
│  ├─ Customer           | CustomerService          | 管理客户     │
│  ├─ Feed               | FeedService              | 管理 Feed    │
│  ├─ FeedItem           | FeedItemService          | 管理 Feed 项  │
│  ├─ SharedSet          | SharedSetService         | 管理共享集    │
│  ├─ Asset              | AssetService             | 管理素材     │
│  ├─ CustomerAsset      | CustomerAssetService     | 管理客户素材  │
│  ├─ CustomerLabel      | CustomerLabelService     | 管理标签     │
│  ├─ Budget             | BudgetService            | 管理预算     │
│  ├─ ConversionUpload   | ConversionUploadService  | 上传转化     │
│  ├─ GoogleAdsService   | GoogleAdsService         | 查询数据     │
│  └─ ReportService      | ReportService            | 下载报告     │
└──────────────────────────────────────────────────────────────────┘
```

---

*今天花 90 分钟：系统掌握 Google Ads 平台功能体系*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
Google Ads 有多少种 Campaign 类型？

<details>
<summary>查看答案</summary>

8 种: Standard Search, Smart, PMax, Standard Display, Shopping, Video Action, App, Bumper (独立视频格式)
</details>

### 问题 2
GAQL 查询最多返回多少条记录？

<details>
<summary>查看答案</summary>

10,000 条。大数据量使用 search_stream
</details>

### 问题 3
哪种智能出价需要最少 15 次转化/月？

<details>
<summary>查看答案</summary>

tCPA, tROAS, Max Conversions, Max Conversion Value 都需要 ≥15 次转化/月
</details>

---

*今天花 90 分钟：系统掌握 Google Ads 平台功能体系*
*答不出自测题？回去重读对应章节。*
