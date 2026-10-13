---
schema_version: "1"
id: evidence-driven-performance-diagnosis
title: 广告效果证据驱动诊断与决策卡
layer: business
knowledge_type: best_practice
category: diagnostics
subcategory: evidence-driven-performance-diagnosis
platform: all
source: 跨平台广告测量与运营方法论 + marketingskills audit guardrails
source_ref: "https://github.com/coreyhaines31/marketingskills/blob/main/skills/ads/references/audit-guardrails.md"
version: "1.1.0"
confidence: 0.9
updated_at: "2026-10-13"
tags: [diagnostics, evidence, funnel, marginal-efficiency, causal-inference, decision-card, cross-platform]
status: published
source_kind: "internal"
authority: "operator"
evidence_level: "provisional"
last_verified_at: "2026-10-13"
---

# 广告效果证据驱动诊断与决策卡

广告优化不是从指标直接跳到动作，而是从“现象 → 假设 → 证据 → 最小变更 → 观察 → 回退/放量”。Agent 给出建议时，必须说明证据是否足够、还缺什么数据、动作影响哪个层级以及什么条件下不应执行。

## 先判断数据是否可用

在解释 CPA、ROAS 或转化之前，先建立数据可用性标签：

| 标签 | 判定问题 | 允许做的事 |
|---|---|---|
| fresh | 数据是否在预期刷新时间内 | 监控交付，不下确定结论 |
| complete | 分页、异步任务和日期范围是否完整 | 做描述性比较 |
| mature | 归因窗口和后端事件是否成熟 | 做预算/策略判断 |
| reconciled | 平台与后端口径是否已对账 | 使用业务价值做决策 |
| causal | 是否有实验或准实验设计 | 表述增量结论 |

缺少标签时，结论应明确降级为“待验证”。不能用图表有数据替代数据完整性，也不能用平台归因替代因果证据。

## 审计健康度与证据覆盖率

账户审计的每个适用检查必须标为以下一种状态：

| 状态 | 含义 | 计分处理 |
|---|---|---|
| Pass | 已取得足够证据且检查通过 | 进入已核验项 |
| Fail | 已取得足够证据且检查失败 | 进入已核验项 |
| Unknown | 所需报表、权限、时间窗或来源不可用 | 降低覆盖率，不降低健康度 |
| N/A | 该检查对当前账户或投放目标不适用 | 从分子、分母都排除 |

健康度和证据覆盖率必须分开报告：

- **健康度** = `Pass / (Pass + Fail)`，仅代表已核验的适用检查。
- **证据覆盖率** = `(Pass + Fail) / 全部适用检查`；Unknown 留在分母，N/A 不计入。
- 已知来源访问失败、授权失败或查询失败时，不得将该平台或数据源当作 0 分并混入汇总。

本项目的默认呈现规则是：覆盖率至少 80% 才给出完整健康分；60%–79% 标为暂定并列明未知项；低于 60% 只报告已确认发现和缺失证据，不给单一健康分。这些比例是审计报告的呈现约定，不是平台标准或跨行业基准。没有搜索词、Pixel/CAPI、商品源或转化报表证据时，应标 Unknown 并指出需要的具体来源，不能据经验猜 Fail。

分数衡量已观察到的健康检查结果，不衡量 Agent 拿到多少数据。回答前应先说明适用检查数量、已核验数量、覆盖率，以及被排除的 N/A 项。

## 统一指标口径

| 指标 | 公式 | 解释边界 |
|---|---|---|
| CTR | clicks / impressions | 反映点击吸引力，不代表成交 |
| CVR | conversions / clicks 或 sessions | 分母必须固定，事件定义要写明 |
| CPA | spend / attributed conversions | 平台归因，不等于有效获客成本 |
| ROAS | attributed value / spend | 价值口径、退款和归因窗口决定含义 |
| 边际 CPA | 新增 spend / 新增 conversions | 需要前后相同窗口和足够样本 |
| 边际 ROAS | 新增 value / 新增 spend | 不能用平均 ROAS 代替 |
| 有效 CPA | spend / 后端有效结果 | 需要 CRM/订单去重和状态定义 |

同一份报告不能混用发生日、报告日、账户时区、UTC、不同币种或不同归因窗口。跨平台比较前先统一日期、币种、事件层级、退款口径、增值税/手续费和数据延迟。

## 全链路诊断树

```text
结果异常
  -> 数据是否 fresh / complete / mature？
      -> 否：修报告、事件或等待回补
      -> 是：交付是否变化？
          -> 是：查预算、审核、竞价、库存、受众、频控
          -> 否：漏斗哪一段变化？
              -> 曝光到点击：素材、意图、版位、竞争
              -> 点击到到站：链接、页面速度、深链、重定向
              -> 到站到事件：埋点、Consent、事件参数
              -> 事件到有效结果：质量、价格、支付、CRM、退款
```

每次只能选择一个主假设进入验证。若同时改变预算、出价、受众、素材、落地页和事件，结果无法归因，也无法安全回退。

## 假设—证据—动作卡

| 假设 | 最小证据 | 低风险动作 | 回退条件 |
|---|---|---|---|
| 预算限制了增量 | 花费接近预算、边际效率稳定、库存仍有容量 | 小幅增加并保留目标 | 边际 CPA 超护栏 |
| 目标过紧限制交付 | 资格正常、预算未花满、目标与成熟数据不匹配 | 生成目标放宽 dry-run | 花费上升但有效率恶化 |
| 素材疲劳 | 频次升、CTR/CVR 同步降、供给不足 | 引入新角度而非复制 | 新素材质量更差 |
| 事件丢失 | 页面/后端结果稳定、平台事件下降 | 修回传并冻结策略 | 去重或隐私不合规 |
| 受众过窄 | 资格通过但库存小、频次集中 | 放宽一个边界 | 品牌/有效率下降 |
| 平台归因高估 | 平台高、后端或实验不支持 | 限制扩量并做增量测试 | 后端口径确认后再调整 |

## 四平台适配

| 平台 | 优先检查 | 特别不能忽略 |
|---|---|---|
| Google Ads | Customer/Campaign/Ad Group、Conversion Action、GAQL 分段 | primary/secondary、价值、搜索词与 PMax 商品信号 |
| Meta | Campaign/Ad Set/Ad、Pixel/CAPI、Insights breakdown | event_id 去重、归因设置、受众重叠和学习扰动 |
| TikTok | Advertiser/Campaign/Ad Group/Ad、Events API、report dimensions | Smart+/Spark 资产供给、MMP 映射和深层事件 |
| DV360 | Advertiser/IO/Line Item、Deal、Floodlight、Report | 资格 vs 竞价输、供应质量、频控和异步报告 |

平台差异只改变证据来源，不改变决策纪律：先定位层级，再检查数据，再做最小变更。

## 预算放量阶梯

1. **资格层**：状态、审核、账户权限、素材/商品、事件和库存满足。
2. **信号层**：转化定义、去重、价值、延迟和数据新鲜度稳定。
3. **效率层**：成熟窗口内边际 CPA/ROAS 和后端质量可接受。
4. **容量层**：受众、库存、客服、商品、现金流和履约有余量。
5. **放量层**：一次只提高一个主要变量，记录基线、护栏和回退。
6. **复盘层**：比较新增结果和有效业务价值，不把平均数当增量。

未通过上一级时，不得用下一级动作掩盖问题。比如事件不稳定时提高预算，只会放大不可解释的花费。

## 结论置信度

输出建议时使用三档：

- **高**：查询完整、数据成熟、多个独立来源一致，动作影响明确。
- **中**：平台数据完整但后端或增量证据不足，只允许小范围可回退测试。
- **低**：存在延迟、缺页、事件异常、口径不一致或样本稀疏，只输出排查清单。

不要把“平台报告显示”写成“广告造成”；不要把“单日变化”写成“策略失效”；不要把“接口成功”写成“线上生效”。

固定 CPA 倍数、跨目标预算比率和宽泛行业基准都不能单独触发暂停或打分。先核对样本量、转化延迟、目标、毛利、学习状态和适用人群；阈值只能作为待验证的预警信号。

## Agent 输出模板

```text
现象：对象/层级、时间窗、指标和变化方向
数据状态：fresh / complete / mature / reconciled / causal
主要假设：为什么优先验证它
证据：已确认、未确认、冲突来源
建议动作：最小变更、执行模式、影响范围
保护指标：成本、质量、频次、库存或业务约束
回退条件：触发阈值、回退对象、复盘时间
```

涉及写入时只生成 dry-run 计划；真实 live 执行仍必须经过账户范围、权限、测试白名单、确认、幂等和审计门禁。知识库不能替代当前 Tool schema。

方法参考：本审计状态模型与证据覆盖率的呈现原则参考并重新表述自
[marketingskills 的 ads audit guardrails](https://github.com/coreyhaines31/marketingskills/blob/main/skills/ads/references/audit-guardrails.md)；
该上游文件另行注明部分原则源自 claude-ads。此处的覆盖率区间是本项目的报告约定，
不是广告平台官方规则。
