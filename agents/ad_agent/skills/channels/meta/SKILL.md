---
name: meta-marketing-api-expert
description: "Meta Ads 专家 Skill：负责账户与资产依赖、ODAX 目标、Ad Set 投放策略、素材/目录广告、Insights、Pixel/CAPI 和故障诊断"
version: 2.0.0
author: Ryan
created: 2026-09-08
tags: [meta, facebook, instagram, odax, advantage-plus, insights, pixel, capi, catalog]
aliases: [facebook, instagram, fb, meta ads]
---

# Meta Marketing API 专家 Skill

> 本 Skill 是 Meta 业务语义、参数依赖和安全 SOP 的 advisory context。它不注册 Tool、不保存
> 认证材料、不直接调用 Graph API。所有动作必须由当前 Registry 的 Meta
> Tool Source Tool 通过 schema、账户范围、权限、dry-run/live gate、确认、幂等和审计执行。

## 先识别账户和资产边界

Meta 资源通常挂在 Ad Account 下，但 Page、Instagram identity、Pixel、Catalog、Product Set、
Lead Form 和 Custom Audience 的所有权/依赖不同。先确认 principal 授权的账户和业务资产，
不要因为用户给了一个 ID 就推断它属于当前账户。

```text
Business / User
      ├── Ad Account (act_<account_id>)
      │      └── Campaign
      │             └── Ad Set ── Targeting / Budget / Optimization / Bid
      │                    └── Ad ── Ad Creative ── Page / IG / Asset / Catalog
      ├── Page / Instagram identity
      ├── Pixel ── Events / Custom Conversion
      └── Catalog ── Product Set ── Catalog Ad
```

账户对外格式、内部 canonical account_id 和 Tool schema 可能不同；以当前 Tool 的字段契约
为准。认证、应用配置和业务管理资产授权由部署/权限系统注入，不能通过聊天输入或 Skill
更新。账户不明确时，优先使用已注册的只读账户/资产 lookup；不能用名称或模型猜 ID。

## Campaign / Ad Set / Ad 的决策模型

Meta 的广告目标需要先确定用户真正要优化的结果，再映射到当前 Schema 支持的 objective、
optimization_goal、billing_event 和 promoted object。不要把自然语言“转化/获客/互动”直接
当作任意枚举，也不要把旧版 objective 名称和当前 ODAX 目标混用。

| 层级 | 负责什么 | 创建/更新前必须确认 |
|---|---|---|
| Campaign | 业务目标、特殊广告类别、预算策略边界 | objective、special ad categories、账户、预算归属 |
| Ad Set | 受众、版位、预算/排期、优化与计费 | targeting、optimization goal、billing、bid/cost cap、时间 |
| Ad | 具体投放单元 | ad set、Page/身份、creative、追踪、CTA、素材 |
| Creative | 文案、媒体、链接、格式组合 | image/video hash/ID、URL、格式、合规文本 |

用户说“创建一个 Meta Campaign”时，先确定是否只创建 Campaign，还是需要完整 Campaign →
Ad Set → Ad 链路。父级缺失时不能把一套对象压成一个不完整的创建请求。当前某种广告格式
若只有 `partial_dry_run` 或声明能力，不得在回复中包装成完整线上投放能力。

## 预算、优化与定向约束

- 先确认预算在 Campaign 还是 Ad Set 层级、daily/lifetime、币种、排期和预算上限；预算
  更新属于外部写入，必须先展示旧值、新值和影响范围。
- `LOWEST_COST_WITH_BID_CAP`、`COST_CAP`、`LOWEST_COST_WITH_MIN_ROAS` 等策略需要对应
  bid_amount、cost cap 或 ROAS floor；不能用默认数值补齐用户没有给出的硬约束。
- 版位、地域、年龄、性别、兴趣、行为、语言等定向要按当前 Schema 组合。动态 targeting
  ID 必须来自当前账户/渠道的只读 search/lookup Tool；搜索结果只是候选，不是已写入配置。
- Special Ad Categories（例如 employment、housing、credit）会影响受众和定向可用性；
  `NONE` 与受限类别互斥，类别不确定时先问清楚，不能为了通过校验删除用户声明。
- Advantage+/自动化投放并不意味着可以跳过素材、Page、Pixel、Catalog、地域或合规依赖；
  应明确哪些参数由平台自动优化、哪些仍由用户负责。

## 广告格式与资产依赖

### Link / Video / Carousel

确认 Page 或 Instagram actor、link、CTA、image hash/video ID、carousel cards、tracking
URL 和落地页。图片和视频上传/查询与 Creative 组合是不同动作；不能把本地路径、文件名或
外部 URL 直接当已存在的 Meta asset ID。

### Lead Generation

确认 Page、Instant Form、隐私政策 URL、问题和线索读取范围。Ad 创建引用的是已存在的
form/page 资产时，先 lookup；当前没有完整 Form CRUD 就明确说明缺口，不能伪造已创建表单。

### Catalog / Product

先确认 Business、Catalog、Product Set、feed 更新状态和账户权限，再创建目录广告。Catalog
广告的 promoted object、product set、link、素材和 tracking 必须保持同一业务资产边界。

### Creative 资产

Creative 采用稳定的媒体引用和版本化文案；更新时区分可变字段与需要新建 Creative 的字段。
保留旧 Creative/Ad 的审计关联，不能把“新素材已上传”描述成“广告已上线”。

## Insights、归因与 CAPI

### Insights 报表

先确认 account、object level（campaign/adset/ad）、日期范围、时区、归因窗口、fields、
breakdowns 和分页。Meta 的 `spend`、`impressions`、`reach`、`frequency`、`clicks`、
`ctr`、`cpc`、`cpm`、`actions`、`conversions`、`purchase_roas` 等字段并非在所有层级、
breakdown 和时间窗口都可同时使用。缺失、延迟或隐私聚合数据不能静默补零。

回答性能问题时至少说明：数据拉取时间、统计窗口、归因设置、币种、分母、动作类型和
是否发生 iOS/隐私建模。不同 attribution setting 的结果不能直接横向比较；CAPI/Pixel
事件回传延迟时要区分“广告实际没有转化”和“数据尚未归因”。

### Pixel 与 CAPI

Pixel 是浏览器/客户端信号，CAPI 是服务端事件，两者应通过 `event_id` 做去重并共享一致的
事件命名和 action source。CAPI 事件至少要明确 event_name、秒级 event_time、action_source、
event_source_url（适用时）、user_data 和 custom_data。邮箱/电话等匹配字段进入 Tool 前应
按平台规则规范化并哈希；不要在 Skill、Prompt、日志或结果中保存原始 PII、token 或测试码。

`test_event_code` 只用于受控联调，不能作为生产数据配置。发送事件是外部写入/数据回传，
仍要经过 live 权限、幂等和审计；“事件请求成功”不等于 Meta 已完成归因。

## 标准执行流程

```text
账户/资产 scope
  -> objective + special category
  -> Campaign / Ad Set / Ad 层级
  -> targeting 与 budget/bid 依赖
  -> Page/Pixel/Catalog/Form/素材 lookup
  -> 当前 Tool schema + permissions
  -> dry-run 计划 / 用户确认
  -> live 写入（若部署明确允许）
  -> readback + 审计 + 结果解释
```

写操作默认只生成 dry-run；批量动作必须逐项展开并记录部分失败。返回未知或超时状态时先
使用已注册 readback 查询，不要直接重复 create。重试只适用于明确的瞬态/限流错误，必须有
上限和幂等键；参数、权限、账户范围和资产不存在错误应先修正，不应盲目重试。

## 常见故障判断

| 现象 | 排查顺序 | 正确动作 |
|---|---|---|
| Invalid parameter | objective、enum、层级、字段组合、资产依赖 | 返回具体字段缺口，重新 dry-run |
| Permission error |账户、Page/Pixel/Catalog 所有权、权限 scope | 不索要或回显凭证，明确授权缺口 |
| Rate limit | app/account/user 维度请求量、并发、分页 | 按响应信号有界退避，避免重复写入 |
| Ad rejected | 政策、素材、落地页、特殊类别、身份 | 标明平台审核状态，不承诺自动通过 |
| Insights 空/异常 | 日期、时区、归因、breakdown、延迟 | 说明数据限制，不等于无投放 |
| CAPI 重复 | event_id、浏览器/服务端事件映射 | 先检查去重链路，再补发 |

## 标准回答和边界

查询应输出账户/资源范围、对象层级、日期与归因窗口、关键指标、数据延迟和不可比项。
变更应输出逐项 dry-run、父子资源、预算/定向/素材差异、风险和确认要求，并明确“尚未
写入 Meta”。不要输出认证材料、原始 PII、业务管理凭证或内部授权范围。

## 参考资料与自测

- `references/operational-playbook.md`：Meta 创建、报表、Pixel/CAPI 和资产依赖清单。
- `agents/ad_agent/knowledge_base/expertise/error-patterns.md`：跨渠道错误处理背景。
- 官方入口：https://developers.facebook.com/docs/marketing-api

自测：

1. 用户说“创建转化广告”时，能否直接创建 Ad？不能，需确认 Campaign/Ad Set、Page、
   link、Pixel/转化事件、素材和当前 Tool 支持的目标组合。
2. CAPI 返回成功是否表示广告已产生转化？不表示，还要区分接收、去重和后续归因。
3. 用户给出一个兴趣名称能否直接写入 targeting？不能，先用当前账户范围内的只读 lookup。
