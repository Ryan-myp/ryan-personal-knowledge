---
name: google-ads-api-expert
description: "Google Ads 专家 Skill：负责账户层级、广告类型、出价、素材、GAQL 报表、变更验证和故障诊断的业务判断与 SOP"
version: 2.0.0
author: Ryan
created: 2026-09-08
tags: [google, google-ads, search, shopping, performance-max, gaql, bidding, reporting]
aliases: [google, google ads, gads, 谷歌]
parser_platform: google
---

# Google Ads API 专家 Skill

> 本 Skill 提供 Google Ads 业务知识、参数依赖和操作 SOP。它不是 Tool 注册表，也不直接
> import Google SDK、读取凭证或发起 API 请求。可执行能力只能来自当前 Registry 中已注册、
> 通过 schema/权限/dry-run/live gate 的 Google Tool Source Tool。

## 先做的判断：账户、资源和请求类型

Google Ads 的账户边界优先于 Campaign 语义：先确认当前 principal 授权的 customer，再确认
请求针对单一 customer、经理账户下的子客户，还是跨客户汇总。账户标识和认证材料属于部署配置，
不能让用户通过业务 Tool 写入，也不能回显到 Prompt、日志或错误中。

资源关系如下，不能跨层级猜 ID：

```text
Manager / Customer
        │
     Campaign ── CampaignBudget / BiddingStrategy
        ├── AdGroup ── AdGroupCriterion(Keyword) / Ad
        └── AssetGroup(PMax) ── AssetGroupAsset / ListingGroupFilter
        └── CampaignAsset / ConversionGoal / Experiment
```

用户只说“Google 广告”时先追问广告类型、customer、资源范围和目标；用户给出名称时，先走
当前已注册的只读 lookup/list 能力，不能把名称拼成 resource name。Google 资源名通常形如
`customers/{customer_id}/campaigns/{campaign_id}`，但对外应以 Tool schema 接受的字段为准。

## 广告类型与创建决策

| 场景 | 关键对象 | 必须确认的依赖 | 不能做的推断 |
|---|---|---|---|
| Search | Campaign → AdGroup → Keyword/RSA | 搜索网络、语言/地域、出价、最终 URL、关键词与匹配类型 | 不能把“搜索”自动改成 PMax |
| Display | Campaign → AdGroup → responsive/display Ad | 受众/内容定向、素材比例、出价、落地页 | 不能把图片素材当作 RSA 文案 |
| Shopping | Campaign → AdGroup/Product group → Product ad | Merchant Center、feed、商品分组、国家/语言、预算 | 不能用普通 Search ad 代替商品广告 |
| Video | Campaign → AdGroup → Video ad | YouTube 视频、视频格式、目标、CPV/CPM 依赖 | 不能凭 URL 生成 video ID |
| App | `MULTI_CHANNEL` Campaign → AdGroup → App ad | App ID、操作系统、应用目标、素材与深链 | 不能把 app 名称当 app_id |
| Performance Max | Campaign → AssetGroup → Assets | final URLs、文本/图片/Logo、business name、目标设置 | PMax 不走普通 AdGroup 关键词链路 |
| Demand Gen/Hotel/Local/Travel/Smart | 由当前 Schema 决定 | 专用设置、素材和下级资源覆盖情况 | 通用 Campaign Tool 不等于完整类型支持 |

`MAX`、`APP` 等历史/用户友好别名只允许在已验证 Client 的兼容边界内归一化；对外计划和
确认摘要优先使用当前 Tool Source Schema 的规范枚举。未被当前广告类型 Schema 标记为
`supported_dry_run` 的格式，只能说明为“已识别但当前未覆盖”，不能声称可以创建。

## 出价、预算与参数依赖

- 预算通常在 CampaignBudget，金额单位和币种必须从当前 Tool schema/账户配置确认；不要把
  普通货币值、micros 和账户币种混用。
- 一个 Campaign 绑定一个有效预算和出价策略；预算调整是写操作，先生成 dry-run 变更摘要，
  展示旧值、新值、日/月节奏和风险，不直接提交。
- Target CPA、Target ROAS、Maximize Conversions、Manual CPC 等策略的目标字段有条件依赖；
  用户未提供硬约束时不能用默认 bid 或目标替代。
- Target Impression Share 需要位置、上限等配套字段；视频的 Target CPM/CPV、App/PMax 的
  conversion goal/asset 约束同样按 schema 条件校验。
- Campaign、AdGroup、Ad、AssetGroup 的父级 ID 必须来自同一 customer，并按声明的
  `parent_resource_type` / `parent_resource_id_field` 连接。缺父级时优先 lookup，而不是重建。

## 素材和层级 SOP

### Search

先确认 Campaign 与 AdGroup，再确认关键词文本、match type、否定关键词范围和 RSA 的
headlines/descriptions 数量与重复度。关键词意图、落地页和广告文案要一致；不要因用户说
“加关键词”而自动创建 Campaign。

### Shopping / PMax

先确认 Merchant Center/feed 或商品资源是否可用，再选择商品分组或 AssetGroup。PMax 的
文字资产、图片、Logo、视频、最终 URL 和 business name 是组合契约；缺少必需资产时要列出
缺口。商品/素材资源 ID 不能由文件名或 URL 猜测，必须使用已注册的上传或 lookup 能力。

### Experiment

Experiment 是独立生命周期，涉及基础 Campaign、实验类型、实验预算/流量、开始/结束时间和
实验指标。不能把实验的 schedule/end/graduate/promote 当作普通 Campaign pause/update，
也不能在没有基础 Campaign 校验的情况下创建实验。

## GAQL 报表与诊断

报表请求先确认 customer、资源粒度、日期范围、时区、币种、segments 和指标。GAQL 的
resource、metrics、segments 必须来自当前版本兼容组合；不要把不同粒度的指标直接相加，
也不要把昨日实时数据描述成最终结算数据。

至少区分：impressions、clicks、cost、CTR、average CPC、conversions、conversion value、
CPA、ROAS、view-through/视频指标（若该资源支持）。派生指标要给分母、时间窗口和数据源；
零曝光、延迟回传和归因窗口不足时标记“不可判断”，不补零或臆造。

```text
选择粒度/资源
  -> 校验 GAQL 字段兼容性
  -> 按 customer 时区确定日期边界
  -> 只读查询/分页
  -> 保留原始字段与统一指标
  -> 标注延迟、币种、归因窗口和异常
```

## 变更、重试与失败恢复

1. 先读取父资源当前状态，形成变更前快照和目标差异。
2. Tool schema 校验 required、enum、conditional rules、父级资源和账户范围。
3. 写操作默认 dry-run；确认摘要必须包含影响资源、预算/出价变化、风险和幂等键。
4. 真实 live 仅能在 Runtime 显式 live、白名单、权限、确认和审计全部通过时执行。
5. Mutate 失败时按错误类别处理：参数/权限错误不盲目重试；配额/瞬时错误采用有上限的
   指数退避；未知状态先只读回查，不能无证据重复创建。
6. 批量操作要保留每个 operation 的成功/失败、resource name、request ID（如受控输出）和
   可重试性；部分失败不能被汇总成“全部成功”。

不要在 Skill 中写死 SDK 方法、Provider endpoint 或 Tool 名称。当前 Tool 的超时、输出上限、
replay policy、readback Tool 和 live_support 才是执行合同；到期定时任务还必须重新预检。

## 常见故障判断

| 现象 | 优先排查 | 处理原则 |
|---|---|---|
| 资源不存在 | customer、资源名、父级和 principal scope | 先只读确认，不跨账户重试 |
| Invalid argument | enum、micros、日期、字段组合、条件规则 | 修参数后重新 dry-run |
| Permission denied | customer 授权、OAuth scope、manager 链路 | 明确缺少权限，不索要凭证文本 |
| Quota/rate limit | 请求量、分页、批量大小、并发 | 有界退避，记录 retry-after/错误摘要 |
| Mutate 状态未知 | 超时、网络中断、部分失败 | 先回查 resource，再决定是否补偿 |
| 报表为空 | 日期/时区、字段粒度、数据延迟、过滤条件 | 说明原因，不当作无投放 |

## 给用户的标准输出

查询类回答应包含 customer/资源范围、日期范围及时区、原始数据来源、关键指标、异常和
不可比项。变更类回答应包含 dry-run 计划、逐项资源、旧值/新值、风险、下一步确认和
“尚未写入 Google Ads”的明确说明。任何凭证、manager 配置和内部认证材料均不得输出。

## 参考资料与自测

- `references/operational-playbook.md`：按广告类型的 preflight、创建和回查清单。
- `agents/ad_agent/knowledge_base/platforms/google/`：层级、约束和工作流背景资料。
- 官方文档入口：https://developers.google.com/google-ads/api/docs

自测：

1. 用户说“创建一个 Google 广告”，应先问哪三类信息？广告类型、customer/账户范围、目标
   与资源依赖；不能直接选择 Search 或 PMax。
2. PMax 能否用普通 AdGroup/Keyword 流程创建？不能，应识别 AssetGroup 与素材组合。
3. GAQL 查询返回空结果是否等于没有投放？不等于，需排查日期时区、延迟、过滤和字段粒度。
