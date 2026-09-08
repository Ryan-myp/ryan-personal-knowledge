---
name: tiktok-ads-expert
description: "TikTok Ads 专家 Skill：负责广告层级、Smart/电商/应用/Lead/Spark 创意、定向与素材资产、Pixel/CAPI、报表和投放诊断"
version: 2.0.0
author: Ryan
created: 2026-09-08
tags: [tiktok, ads, smart-plus, spark-ads, ecommerce, app, lead-generation, pixel, reporting]
aliases: [tiktok ads, tiktok, douyin, 抖音]
parser_platform: tiktok
---

# TikTok Ads 专家 Skill

> 本 Skill 只提供 TikTok 广告业务知识、对象依赖、参数判断和 SOP。它不是 Tool 注册表，
> 不持有认证材料，不执行 API。实际能力必须由当前 Registry 中 TikTok Capability
> 发布的 Tool 按 schema、账户范围、权限、dry-run/live gate、幂等和审计执行。

## 账户、对象和身份边界

TikTok Ads 的账户通常称 advertiser account；Campaign、Ad Group 和 Ad 是主要投放层级，
素材、Pixel、Audience、Catalog、Product Set、Identity 等是外部依赖。先确认 principal 授权
的 advertiser 和业务区域，再确认资源 ID。不要把 TikTok item、Spark post、identity、pixel、
catalog 或 product set 的 ID 混用，也不能用名称推断 ID。

```text
Advertiser Account
      └── Campaign (objective / campaign type)
             └── Ad Group (budget / schedule / targeting / bid)
                    └── Ad (creative / identity / tracking)
Assets: image / video / creative portfolio
Commerce: catalog ── product set
Measurement: pixel ── events / audience
Identity: TikTok account / creator authorization
```

认证材料由受信任 Runtime 注入，Skill、Tool 输入、日志和模型上下文不能承载凭证。用户只
说“TikTok 广告”时先问目标（转化、流量、App、Lead、商品销售、品牌）、advertiser、地区、
投放时间、预算和素材来源。

## Campaign → Ad Group → Ad 决策

| 层级 | 关键职责 | 必须确认 |
|---|---|---|
| Campaign | objective、campaign_type、预算边界 | 目标、投放类型、账户、预算模式 |
| Ad Group | 预算、排期、优化、出价、定向、版位 | promotion type、billing、budget、location、placement、bid |
| Ad | 文案、媒体、身份、追踪 | ad format、素材 ID、identity、落地页/深链 |

不要因为用户说“创建广告”就跳过 Campaign/Ad Group；如果用户只需要创建单个 Ad，仍要
验证父级 ID、账户归属和当前 Ad 格式 Tool。跨层级批量创建要把每一项的父级、资源依赖和
部分失败结果分别记录。

## 目标、预算与优化约束

- `objective_type`、`campaign_type`、`promotion_type`、`optimization_goal`、`billing_event`、
  `budget_mode`、`bid_type` 必须来自当前 Tool schema 的枚举，不能把 Google/Meta 的目标名
  直接套用。
- Ad Group 的预算模式决定 daily/lifetime、最低预算和排期字段；用户未说明币种、日预算、
  排期时不能用默认值代替。
- 出价策略与优化目标有条件依赖；例如 custom bid 需要对应 conversion bid price，目标、
  计费和出价不匹配时在进入 Provider 前阻塞。
- `SCHEDULE_FROM_NOW`、固定开始时间和全天投放是不同语义；明确时区、开始时间、结束时间
  和素材审核准备时间。不能把“尽快”变成一个任意时间戳。
- 地域、语言、设备、操作系统、兴趣和行为属于动态目录，必须用当前账户/地区可用的只读
  lookup；lookup 候选不等于已写入定向。

## 广告格式和资产依赖

### 普通 In-Feed / 图片 / 视频 / 轮播

先确认素材尺寸、时长、文件格式、落地页、CTA、tracking 和广告身份。素材上传、素材查询、
Creative 组合和 Ad 创建是不同动作；不能用本地文件路径或 URL 假装已经获得 image/video ID。

### Spark Ads

Spark 使用已授权的原生 TikTok 内容，需确认 creator/identity 授权、TikTok item 或 Spark post
引用、评论/互动使用方式、落地页和 tracking。Spark 的原生内容授权状态与广告创建状态不同；
没有授权或 post ID 时不能用普通视频广告替代，也不能声称保留了原生互动。

### App / Lead / Commerce

- App：确认 app_id、操作系统、promotion type、深链/商店链接和转化事件。
- Lead：确认 Page/表单引用、隐私政策和线索回传范围；页面/Instant Form 若不是当前 Ads
  Capability 的可执行资源，明确列为外部依赖，不伪造 CRUD。
- Commerce：`CATALOG` 需要先选择 catalog_id、product_set_id 和商品状态；目录/商品集的
  lookup、校验和广告创建不能混成一个未审计请求。
- Identity/creator：identity_id、授权状态和素材拥有者必须与 advertiser scope 对齐。

## Pixel、Events API 与受众

Pixel/CAPI 事件必须明确 pixel、event name、event time、event source、用户匹配字段、
custom data 和去重 ID。邮箱/电话等数据按平台规则规范化和哈希后再进入 Tool；原始 PII、
token、partner 配置、测试码不能写入 Skill、Prompt、日志或持久化结果。

浏览器 Pixel 和服务端 Events API 可能同时发送同一事件，使用稳定 event_id 规划去重；“API
接收成功”不等于事件已去重、已匹配或已归因。Audience 文件上传、计算类型、匹配率和可用时间
也要单独说明，不能把 audience 创建成功描述为立即可投放。

## 报表与性能分析

先确认 advertiser、report level（campaign/adgroup/ad）、日期范围与时区、维度、指标、分页、
币种和归因窗口。常见指标包括 spend、impressions、reach、clicks、CTR、CPC、conversions、
CPA、video views、complete rate、install、purchase value、ROAS，但具体组合以当前 Tool
schema 和接口版本为准。

报告必须区分：平台原始指标、派生指标、归因事件、估算/建模值和数据延迟。不同 objective、
国家币种、归因窗口或 breakdown 不能直接比较；没有曝光不等于没有花费，空数据要先排查
日期、权限、过滤和报表异步生成状态。

## 标准执行流程

```text
advertiser scope
  -> objective / promotion type
  -> Campaign / Ad Group / Ad parents
  -> budget / schedule / optimization / bid
  -> targeting + asset/identity/pixel/catalog lookup
  -> format schema + policy checks
  -> dry-run + confirmation
  -> live write (only if explicitly enabled)
  -> readback / audit / report interpretation
```

写操作默认 dry-run；当前格式若仅支持部分模拟或声明能力，必须显式说明。请求超时、未知
状态或重试时先按幂等键和 readback 判断是否已创建；参数/权限/素材不存在错误不盲目重试。
批量请求要限制数量、并发和重试次数，保留 item 级结果。

## 常见故障判断

| 现象 | 优先排查 | 处理原则 |
|---|---|---|
| Invalid parameter | 枚举、目标组合、预算/出价、素材字段 | 指出具体 schema 缺口，先 dry-run |
| Budget too low / invalid | budget mode、地区最低预算、排期 | 不自动抬高预算，向用户确认 |
| Authorization/identity | advertiser、creator 授权、identity 类型 | 区分账户授权与内容授权 |
| Asset not found | media ID、目录/商品集、区域和账户 | 先 lookup，不把 URL 当 ID |
| Rate limit/timeout | advertiser 频率、分页、并发、异步任务 | 有界退避，先 readback |
| Pixel/CAPI 异常 | event_id、时间单位、哈希、action source | 区分接收、匹配、去重和归因 |
| 报表空或延迟 | 时区、窗口、过滤、异步状态 | 标记数据未就绪，不补零 |

## 标准回答和边界

查询应包含 advertiser、资源层级、日期/时区、归因窗口、关键指标、数据来源和延迟。
变更应包含父级、素材/身份/定向依赖、dry-run 差异、风险、确认和“尚未写入 TikTok”的说明。
不要输出任何凭证、用户原始数据、内部授权范围或未经当前 Registry 验证的 Tool/接口名称。

## 参考资料与自测

- `references/operational-playbook.md`：TikTok 投放、Spark、素材、报表和事件清单。
- `agents/ad_agent/knowledge_base/expertise/error-patterns.md`：跨渠道错误处理背景。
- 官方入口：https://business-api.tiktok.com/portal/docs

自测：

1. Spark Ads 没有 creator 授权时能否降级成普通视频广告？不能，应明确授权缺口。
2. `CATALOG` 广告只给 catalog 名称能否创建？不能，需 lookup 得到 catalog/product set ID。
3. CAPI 的 event_time 用毫秒是否可以直接发送？不能，先按当前契约确认秒级时间与时区语义。
