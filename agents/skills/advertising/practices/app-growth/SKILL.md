---
name: app-growth
description: "评估 App 付费获客、商店页转化与安装后激活、留存和价值之间的增长链路 (app paid acquisition and post-install growth)"
version: "1.1.0"
namespace: advertising
triggers:
  - [App 增长, app growth, 应用推广, 应用安装广告, app campaign, app promotion]
  - [ASO, 应用商店优化, App Store 页面, Google Play 页面, 商店转化, store listing conversion]
  - [安装后留存, app activation, app retention, cohort LTV, CPI 低但留存差]
---

# App 获客与安装后增长

本 Skill 把付费 App 获客与商店页、激活、留存和收入放在同一条漏斗里评估。它补充
`businesses/app`、账户诊断、测量/归因 Skills 和 Wiki 的《App 与游戏广告增长深度打法》，
不替代平台 Skill、实时 Tool 结果或 MMP/分析系统。

## 分析流程

1. **明确业务决策。** 确认平台、iOS/Android、国家/语言、获客或再营销目标、商业模式，
   以及本次要决定的是预算、商店页、事件优化还是用户质量。
2. **建立证据链。** 分开使用当前 Run 中授权的广告报表、用户提供的商店页面/截图、
   事件与 cohort 数据。标记来源、时间范围、时区、归因口径、数据成熟度和缺失项。
3. **按漏斗定位。** 对照展示/点击 → 商店访问 → 安装 → 首次打开 → 激活 → 留存 →
   付费或广告收入。先确认各阶段定义、分母和事件连接；不可比较的环节不强行计算转化率。
4. **区分问题所在。** 低点击率可能与广告表达有关；点击后商店转化可能与消息匹配、
   页面信息或商店素材有关；安装后质量可能与用户承诺、事件信号、产品激活或地区版本有关。
   这些是排查方向，不是单凭一个指标就能确认的根因。
5. **形成优先级。** 把已观察事实、推断和待验证假设分开。先处理证据充分且影响明确的问题；
   对策略性变化用 `experimentation-design` 写出唯一主要变量、主指标、护栏和停止规则。
6. **用 cohort 判断质量。** 在可用数据下按安装/投放 cohort、平台、市场、系统、素材和版本
   检查激活、留存、收入、退款及回收期。近期 cohort 未成熟时标为初步结果，不把预测 LTV 当实际收入。

商店页审查需要时加载 `references/store-listing-review.md`。跨漏斗的事件、归因和回收期口径
优先引用 Wiki 与现有 measurement Skills，不在本 Skill 重复维护平台动态规格或固定 benchmark。
需要做 iOS 商店市场初筛时，可调用 `public_app_research_app_store_search`；已有 App
Store ID 或 Bundle ID 时可调用 `public_app_research_app_store_lookup`。使用前加载
`references/store-market-research.md`，并将商店元数据与广告表现数据分开。

## 结论边界

- 不以最低 CPI 单独宣布用户质量或商业结果更好；同时检查下游事件、cohort 成熟度和价值。
- 不从广告平台归因数直接推导增量或财务收入；对齐后台/CRM/商店数据定义和去重后再比较。
- 没有对应读取 Tool 时，只分析用户提供的材料；不得声称已访问、对账或验证 MMP、GA4、
  CRM、订单、Google Play 或 App Store Connect。公开 App Store Search 结果只代表商店目录
  元数据，不代表广告投放、转化、下载或留存表现。
- 不假设商店 A/B、产品页优化或广告实验 Tool 已连接；先确认当前注册能力。
- 不输出未经核实的商店字符限制、审核政策、评分阈值或“提升 X%”保证。

## 执行边界

本 Skill 只提供分析、页面审查和实验草案，不创建或编辑 App Store / Google Play 页面，
不配置 MMP/分析事件，也不修改广告预算、出价、素材或状态。所有广告操作仍必须经当前注册
Tool 与 Runtime 的权限、执行模式、确认、幂等和审计门禁。

## 输出

简要列出：平台/OS/市场和评估窗口、证据来源及完整性、漏斗阶段发现、事实/推断/Unknown、
首要问题与可证伪假设、主指标和护栏、所缺数据及下一步。没有完整漏斗数据时，明确写出结论
只覆盖哪一段。
