---
schema_version: "1"
id: four-platform-ad-agent-handbook
title: 四大广告平台 Agent 专业知识总览
layer: business
knowledge_type: business_strategy
category: cross_platform_foundation
subcategory: four-platform-ad-agent-handbook
platform: all
source: Google Ads、Meta Marketing API、TikTok Marketing API、Display & Video 360 官方文档与广告运营方法论
source_ref: agents/ad_agent/knowledge_base/business/four-platform-ad-agent-handbook.md
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google-ads, meta, tiktok, dv360, marketing-api, hierarchy, measurement, optimization, diagnostics, agent]
status: published
---

# 四大广告平台 Agent 专业知识总览

这篇总览回答五类高频问题：广告对象如何组织、不同平台如何创建和修改、数据怎样可信地进入优化、异常怎样定位、Agent 如何在不越权的前提下给出可执行建议。它是导航和决策框架，不替代各平台专题文档、当前 Tool schema、账户权限或平台实时政策。

## 一、统一心智模型

广告系统可以抽象为六层，但四个平台对层级名称、继承关系和字段能力的实现不同：

```text
账户与身份
  -> 目标与活动（Campaign）
  -> 预算与投放单元（Ad Group / Ad Set / IO / Line Item）
  -> 广告与创意（Ad / Creative / Asset）
  -> 事件与价值（Pixel / CAPI / Conversion / Floodlight）
  -> 报表与决策（Insights / GAQL / Report / CRM）
```

| 统一层 | Google Ads | Meta | TikTok | DV360 |
|---|---|---|---|---|
| 账户 | Customer/Manager | Business/Ad Account | Business Center/Advertiser | Partner/Advertiser |
| 活动 | Campaign | Campaign | Campaign | Campaign/IO |
| 投放单元 | Ad Group、Asset Group | Ad Set | Ad Group | Line Item |
| 广告 | Ad、Ad Group Ad | Ad | Ad | Ad/Creative |
| 定向 | Criterion、Audience、Listing | Targeting、Audience | Targeting、Audience | Targeting Assignment |
| 测量 | Conversion Action | Pixel、Dataset、CAPI | Pixel、Events API、MMP | Floodlight、CM360 |
| 报表 | GAQL/Search/Stream | Insights | Integrated Report | Report Query/Async |

统一层只用于理解和编排。不能把 Google 的 Ad Group 参数直接映射成 Meta 的 Ad Set 参数，也不能因为四个平台都有“Campaign”就假设目标、预算继承和状态语义相同。

## 二、四个平台的定位与取舍

| 平台 | 强项 | 最适合的信号 | 主要风险 |
|---|---|---|---|
| Google Ads | 搜索意图、商品、跨库存自动化 | 搜索词、转化动作、商品源、价值 | 目标过紧、查询粒度错误、商品/转化信号不稳 |
| Meta | 社交内容、广泛探索、再营销 | Pixel/CAPI 事件、创意、受众、价值 | 去重失败、归因误读、学习期被频繁改动 |
| TikTok | 短视频内容与快速创意迭代 | 视频前段留存、事件、素材供给 | 事件浅、素材疲劳、Spark 授权和质量风险 |
| DV360 | 程序化采购、Deal、品牌安全与规模 | 供应质量、可见性、频次、Floodlight | 资格与竞价混淆、层级复杂、报告异步延迟 |

平台选择先看业务约束：搜索需求、商品供给、内容生产能力、用户生命周期、品牌安全、媒体库存和测量成熟度。不要用一个平台的低 CPA 直接证明另一个平台“不值得投”，跨平台比较必须先统一口径并考虑增量。

## 三、对象生命周期

绝大多数广告对象都应按以下生命周期管理，但具体状态枚举以当前平台 schema 为准：

```text
规划 -> 创建草稿 -> 校验/审核 -> 暂停状态上线
  -> 学习/探索 -> 稳定交付 -> 调整预算/出价/创意
  -> 暂停/下线 -> 归档或保留历史
```

### 创建前

- 确认账户、市场、时区、币种、业务目标和最终转化事件。
- 根据目标选择平台对象和父子关系，不从名称猜 ID。
- 查询当前 Registry Tool 的字段、枚举、权限、effect、风险和 API 版本。
- 读取父对象现状，判断是否已经存在同一业务对象，设计幂等键。
- 明确预算、出价、定向、素材、商品、落地页和测量的最小可用集合。

### 创建中

- 按父子依赖顺序创建，保留每一步的请求摘要、响应资源 ID 和状态。
- 默认先生成 dry-run 计划，展示字段掩码、影响对象、预计副作用和回退方案。
- 对批量操作设置数量、并发、超时和响应大小上限。
- 部分失败时保存成功与失败明细，不能用整体成功覆盖子项失败。

### 创建后

- 验证 API 接收、平台线上状态、审核状态和报表可见性。
- 记录“请求成功”“线上生效”“首次交付”“数据成熟”四个时间点。
- 初期只观察，不同时大改预算、出价、定向、素材和事件目标。

## 四、平台专题摘要

### 4.1 Google Ads

Google Ads 的基础关系通常是 `Customer -> Campaign -> Ad Group -> Ad/Keyword`；Search 还依赖关键词与广告相关性，Shopping/PMax 还依赖商品源、Listing/Asset Group 与转化价值。Google 的资源名、父资源和字段可组合性是 API 操作的核心事实。

**适合的决策顺序**：

1. Search 先看查询意图、关键词/广告组、匹配范围、否定词、广告相关性和落地页。
2. Shopping/PMax 先看商品批准、价格库存、商品 ID、资产组、最终 URL 和价值事件。
3. 价值出价前确认价值、币种、退款、订单去重、primary/secondary 和数据成熟度。
4. 报表用 GAQL 固定资源、字段、分段、日期、时区、分页和可加性。
5. 写入使用 mutate 的 dry-run/校验能力或当前 Tool 等价门禁；部分失败必须可定位和重放。

**常见误判**：PMax 花费少不一定是目标 ROAS 的问题，可能是商品资格、资产审核、预算或转化事件；GAQL 行数变多不一定是数据增长，可能是新增 segment 导致粒度展开；转化下降不一定是竞价问题，可能是 Consent、标签、离线回传或报告延迟。

### 4.2 Meta Ads

Meta 的基础关系通常是 `Business/Ad Account -> Campaign -> Ad Set -> Ad -> Creative`。Campaign 表达目标，Ad Set 组织预算、排期、定向、优化事件和版位，Ad/Creative 承载身份、素材、文案、链接和追踪。Campaign 预算集中分配与 Ad Set 预算边界是不同的控制语义。

**适合的决策顺序**：

1. 先把业务目标映射到能稳定接收且有业务意义的事件。
2. 再确定 Campaign 目标、Ad Set 优化事件、预算、受众和排除。
3. Pixel/CAPI 双通道使用同一稳定 `event_id` 与事件语义完成去重。
4. 素材测试区分 Hook、场景、证明、报价、CTA 和页面承接，不只比较 CTR。
5. Insights 固定 level、fields、breakdowns、time range、归因设置和分页。

**常见误判**：Advantage 自动化不是取消业务边界；广泛受众不代表无需排除和合规检查；CAPI 事件多不代表增量多；Ad Set 表现差不应在数据未成熟时同时换目标、预算和素材。

### 4.3 TikTok Ads

TikTok 的基础关系通常是 `Advertiser -> Campaign -> Ad Group -> Ad -> Creative`。Campaign 表达目标，Ad Group 负责预算、排期、定向、版位、优化和出价，Ad/Creative 负责视频、身份、落地页和追踪。Smart+ 扩大自动探索空间，Spark Ads 则引入有机内容身份、互动资产和授权风险。

**适合的决策顺序**：

1. 先确认目标事件、Pixel/Events API/MMP 映射和后端有效结果。
2. 再确认 Ad Group 的预算类型、排期、优化事件、出价和受众容量。
3. 建立 Hook、场景、证明、演示、优惠和 CTA 的素材矩阵。
4. Spark 发布前验证帖子、身份、音乐、评论、授权期限和原帖状态。
5. 报表固定 advertiser、对象层级、dimensions、metrics、日期粒度和时区。

**常见误判**：安装稳定不代表付费事件稳定；高播放不代表高质量转化；同一视频换字幕不等于创意探索；报表空值可能是分页、异步、权限、延迟或查询维度错误。

### 4.4 DV360

DV360 的基础关系可理解为 `Partner -> Advertiser -> Campaign -> IO -> Line Item -> Ad/Creative`，Line Item 还通过 Targeting Assignment、Deal/Exchange、库存与品牌安全规则共同决定竞价资格。Floodlight/CM360 负责把媒体触点与业务事件连接起来。

**适合的决策顺序**：

1. 先定位预算和设置属于 Campaign、IO 还是 Line Item。
2. 区分库存没有资格、Deal 未生效、定向过窄与竞价输掉。
3. 同时观察花费、win rate、可见性、完成率、频次、供应路径和 Floodlight。
4. 放宽定向时一次只动一个主要边界，保留品牌安全和质量护栏。
5. 异步报告保存 query definition、任务状态、生成时间、分页和下载校验。

**常见误判**：提高 bid 不能修复审批或资格问题；Deal 的高质量不能外推到所有开放库存；高平台转化不能跳过 CRM/订单对账；报告未 ready 不能当成零数据。

## 五、测量与归因

### 最小数据契约

所有平台数据和后端结果至少带：平台、账户、对象层级、资源 ID、事件名、事件发生时间、账户时区、币种、金额口径、归因窗口、数据更新时间、来源系统、去重键和数据状态。

金额必须区分媒体花费、订单收入、毛利、退款后收入和预测 LTV；结果必须区分发生、接收、匹配、去重、归因、报告可见和后端确认。

### 对账顺序

1. 对齐日期范围、时区、币种、层级、过滤器、事件名和归因窗口。
2. 对齐展示、点击、事件接收、平台归因、订单、退款和回补延迟。
3. 用订单 ID、事件 ID、点击标识或稳定组合键去重。
4. 保留原始快照、查询契约和聚合规则，不用新结果覆盖历史。
5. 将差异分为口径、延迟、隐私/建模、重复/漏报和真实业务变化。

### 归因表达

| 证据 | 可以说 | 不可以直接说 |
|---|---|---|
| 平台归因 | 平台在其窗口内分配了结果 | 广告造成了全部结果 |
| 后端订单/CRM | 业务系统确认了结果 | 结果全部来自某平台 |
| 前后对比 | 变更后观察到相关变化 | 变化就是增量 |
| Geo/时间实验 | 在设计条件下有增量证据 | 实验外所有市场都同样成立 |
| 随机 Holdout | 实验范围内的因果差异 | 可以忽略季节和供给干扰 |

## 六、优化决策框架

先判定异常属于哪一层：

```text
交付层：有没有资格、库存和展示？
信号层：事件、价值、去重和延迟可靠吗？
效率层：边际 CPA/ROAS 是否达到业务护栏？
质量层：订单、有效线索、退款、留存和 LTV 如何？
容量层：商品、客服、现金流、库存和品牌风险能否承受？
```

### 预算

平均 CPA/ROAS 只描述过去，边际 CPA/ROAS 才帮助判断新增预算。调度前检查交付资格、信号成熟度、边际效率、容量和跨平台口径；调度时设置最大增幅、最小保留预算、保护指标和回退条件。

### 出价

出价目标必须和可观测、稳定且有业务意义的事件匹配。目标过紧可能减少花费，目标过松可能购买低质量结果；在事件或价值不稳定时，调整目标只是掩盖测量问题。

### 受众与定向

定向是库存与信号的权衡，不是越窄越精准。要同时看受众容量、重叠、频次、质量、地域/合规边界和增量证据。每次放宽或收紧一个主要边界，并用实验或后端结果验证。

### 创意

创意优化看完整漏斗：首屏注意、观看/互动、点击/到站、事件、有效结果和长期价值。素材 winner 要有足够曝光、稳定窗口、相同口径和后端质量；高 CTR 但低付费不应直接放量。

## 七、统一诊断卡

| 现象 | 第一检查 | 第二检查 | 暂不做 |
|---|---|---|---|
| 花费为零 | 状态、审核、预算、排期 | 定向、库存、Deal、出价 | 直接加预算 |
| 花费过快 | 时区、pacing、预算类型 | 频次、库存集中、边际成本 | 只看日均 |
| 点击下降 | 素材、意图、竞争、版位 | 链接、页面、追踪 | 直接换优化目标 |
| 转化下降 | 事件触发、回传、去重、延迟 | 页面、商品、CRM、促销 | 立即放宽出价 |
| ROAS 上升但规模小 | 目标约束、库存容量 | 价值分布、边际效率 | 一次性翻倍预算 |
| 平台与后端不一致 | 日期/时区/窗口/币种 | 重复、退款、建模、漏报 | 用固定比例校正 |
| 报表为空 | 查询资源、权限、状态 | 分页、异步、数据成熟度 | 把空值填成 0 |

## 八、Agent 的标准输出

每次给出广告建议时，按以下结构组织：

```text
对象：平台 / 账户 / 层级 / 资源 ID
现象：时间窗、指标、变化方向
数据状态：fresh / complete / mature / reconciled / causal
主要假设：为何优先验证
已确认证据：查询、事件、后端或实验结果
待确认信息：缺失字段、延迟或冲突口径
建议动作：最小变更、影响范围、执行模式
保护指标：成本、质量、频次、库存、利润或合规
回退条件：阈值、对象、时间和责任人
```

如果信息不足，输出排查清单而不是编造平台事实；如果涉及写入，先生成 dry-run 计划；live 必须通过可信 principal、账户权限、测试白名单、显式确认、幂等和审计。知识文档不能保存凭证、原始 PII、Provider client 或可执行脚本。

## 官方参考

- [Google Ads API documentation](https://developers.google.com/google-ads/api/docs)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis)
- [TikTok Business API](https://business-api.tiktok.com/portal/docs)
- [Display & Video 360 API](https://developers.google.com/display-video/api)
