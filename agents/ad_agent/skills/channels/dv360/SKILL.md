---
name: dv360-expert
description: "DV360 专家 Skill：负责 Partner/Advertiser 作用域、Campaign/IO/Line Item 媒体购买、定向分配、创意审批、报表异步流程和品牌安全判断"
version: 3.0.0
author: Ryan
created: 2026-09-08
tags: [dv360, display-video, programmatic, insertion-order, line-item, targeting, creative, reporting]
aliases: [display video 360, display & video 360, dv 360]
---

# Display & Video 360 专家 Skill

> 本 Skill 提供 DV360 的媒体购买知识、层级关系、参数依赖和运营 SOP。它不是 Tool 注册表，
> 不直接调用 Google API、不读取认证材料，也不把示例能力描述成已上线。
> 实际执行只能依赖当前 Registry 中已注册的 DV360 Tool Source Tool，并经过 schema、权限、
> advertiser scope、dry-run/live gate、确认、幂等和审计。

## 账户边界和资源层级

DV360 的 Partner 与 Advertiser 是权限和数据边界，Advertiser 下才是具体投放资源。先确认
principal 授权的 advertiser、partner/组织关系和账户币种，再处理资源；不要把 Campaign ID、
IO ID、Line Item ID 或 Creative ID 跨 advertiser 复用。

```text
Partner / Organization
        └── Advertiser
              ├── Campaign
              │     └── Insertion Order (IO)
              │             └── Line Item
              │                    ├── Targeting assignments
              │                    └── Creative associations
              ├── Creative / Creative Asset
              └── Report definition ── Report result
```

当前项目的最小执行关系以 Tool schema 为准：创建/查询 IO 需要 advertiser/campaign/IO 关系，
Line Item 需要 IO，定向分配需要 advertiser、line item 和 targeting type，创意需要 advertiser。
如果当前 Tool Source 没有发布 Campaign 创建、完整 Flight、某种 Creative subtype、Inventory
Source 或品牌安全编辑能力，只能说明为未覆盖，不能用通用字段模拟成功。

## 媒体购买决策

| 对象 | 负责什么 | 创建/更新前必须确认 |
|---|---|---|
| Campaign | 业务/营销组织与跨 IO 归属 | advertiser、名称、目标、父级关系 |
| IO | 预算、投放周期、媒体购买方向 | start/end、预算、频控、渠道/库存约束 |
| Line Item | 具体采购策略和执行单元 | IO、类型、预算、排期、出价、定向、创意 |
| Targeting assignment | Line Item 的人群/环境/库存限制 | targeting type、已存在的 option、互斥组合 |
| Creative | 可投放素材及审批状态 | advertiser、格式、尺寸、媒体、审核状态 |

预算和排期既可能存在于 IO，也可能细化到 Line Item；回答“改预算”时先确认目标层级，
不要把 IO 预算当成 Line Item budget。Programmatic Guaranteed、Preferred Deal、Open
Auction 等采购类型的库存与交付承诺不同，不能只凭名称选择。

## 定向、库存和品牌安全

- 定向类型、选项 ID、geo、device、audience、environment、brand safety 和 inventory
  source 必须通过当前能力与 schema 校验。动态 targeting option 不能由名称或模型猜 ID。
- 先读取已存在的 targeting assignment，再计算新增/删除差异；删除/替换是高风险写操作，
  要逐项展示影响范围和恢复方式。
- Line Item 的定向组合可能因采购类型、库存来源和广告格式受限；无法证明组合合法时停在
  dry-run/needs_input，不用“平台会自动兼容”掩盖缺口。
- 频控、可见性、品牌安全和敏感内容控制是投放策略而非装饰字段，需说明作用层级和默认值
  来源。不能把“品牌安全”泛化成已启用全部保护。

## 创意与审批

Creative 创建、关联和审批是不同状态：素材存在不等于已关联，已关联不等于审核通过，审核
通过也不等于 Line Item 已开始投放。对 Banner、Video、Native 等格式先确认尺寸、时长、
媒体引用、点击/落地页、追踪和 advertiser 归属。

```text
asset uploaded
   -> creative definition
   -> creative assigned / associated
   -> policy review
   -> approved / rejected / pending
   -> eligible for Line Item delivery
```

审核 pending 时不能通过重复创建 Creative 绕过；拒审要保留平台原因、修订建议和重新审核
路径。当前未发布的格式或创意模板只作为规划信息，不承诺可以上传。

## 报表与异步任务

DV360 报表通常涉及 report definition、异步生成和 report result 三阶段。先确认 advertiser、
时间窗口及时区、维度、指标、过滤、数据 freshness 和导出格式；再创建/执行报告并轮询或
读取结果。Report definition 成功不等于结果已经生成，result 可读也不等于今天的数据已最终
结算。

性能分析至少区分 impressions、clicks、media cost、CTR、viewability、video completion、
conversions 等原始/派生口径，并标明粒度、币种、归因来源和延迟。不同 Partner/Advertiser、
媒体类型、费用口径或时间窗口不可直接相加；缺失值和异步未完成不能补零。

当前项目如果只注册了 Line Item report，就只能查询该覆盖范围；Campaign/Creative/全量
分时报告没有对应 Tool 时必须明确“不支持当前执行”，不能依据 Skill 中的理想化报告名猜接口。

## 标准执行流程

```text
partner / advertiser scope
  -> Campaign / IO / Line Item parent
  -> budget / flight / inventory / bid
  -> targeting lookup + assignment diff
  -> creative + approval state
  -> current Tool schema + permission
  -> dry-run + confirmation
  -> live write (if approved)
  -> readback / report result / audit
```

长耗时报告和媒体购买操作要记录状态、task/run ID、轮询次数、超时和最终结果。写操作默认
dry-run；未知状态先 readback，不能重复创建 IO、Line Item 或 Creative。限流和瞬态网络错误
采用有界退避，参数、权限、父级和审批错误停止重试并返回缺口。

## 常见故障判断

| 现象 | 优先排查 | 处理原则 |
|---|---|---|
| Resource not found | advertiser/partner、父级 ID、区域/权限 | 不跨 advertiser 重试 |
| Invalid parent | IO/Campaign/Line Item 层级关系 | 先读取父资源，不自动创建父级 |
| Targeting rejected | targeting type、option、采购类型组合 | 返回具体组合缺口 |
| Creative pending/rejected | 格式、规格、政策、关联状态 | 区分审核与投放，不绕过审核 |
| Report not ready | definition/result、异步状态、时间窗口 | 记录轮询/超时，不当作空报表 |
| Budget/flight mismatch | IO 与 Line Item 预算和时间层级 | 明确影响层级后再变更 |
| Permission/partner error | principal advertiser scope、组织授权 | 不索要或输出密钥/partner 配置 |

## 标准回答和边界

查询应包含 partner/advertiser、资源层级、日期/时区、报表阶段、币种、指标口径和数据延迟。
变更应包含父级、预算/排期/定向/创意差异、审批风险、dry-run 和确认要求，并明确“尚未
写入 DV360”。不要将计划中的 Flight、Audience、Inventory Source 或报告能力说成已注册
可执行能力。

## 参考资料与自测

- `references/operational-playbook.md`：DV360 媒体购买、定向、创意审批和报表清单。
- `agents/ad_agent/knowledge_base/expertise/error-patterns.md`：跨渠道错误处理背景。
- 官方入口：https://developers.google.com/display-video/api

自测：

1. 用户只给 Line Item ID 要改预算，能否直接执行？不能，需确认 advertiser、IO/预算层级、
   当前状态和 Tool schema。
2. Report definition 创建成功是否代表报表可下载？不代表，还要等待并读取 report result。
3. Skill 写了某个 Creative Tool 是否代表服务支持？不代表，必须以当前 Registry 的
   Tool Source Tool 和契约审计为准。
