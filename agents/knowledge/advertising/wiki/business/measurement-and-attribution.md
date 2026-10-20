---
schema_version: "1"
id: cross-platform-measurement-attribution
title: 跨平台事件、归因与增量评估
layer: business
knowledge_type: general
platform: all
source: 四平台测量文档 + 内部广告归因方法论 + marketingskills attribution
source_ref: "https://github.com/coreyhaines31/marketingskills/blob/main/skills/attribution/references/measurement-paradigms.md"
version: "1.2.0"
confidence: 0.9
updated_at: "2026-10-20"
tags: [measurement, attribution, conversion, incrementality, mmp, crm, privacy, meridian, mmm]
status: published
source_kind: "internal"
authority: "operator"
evidence_level: "provisional"
last_verified_at: "2026-10-20"
---

# 跨平台事件、归因与增量评估

## 一套事件字典

事件命名应同时表达业务对象、动作、价值和时间：view_item、add_to_cart、purchase、lead、qualified_lead、install、registration、subscription 等只是例子，实际字典需与业务后端一致。每个事件定义 owner、触发条件、唯一键、价值、币种、去重规则、允许延迟和是否用于优化。

## 四层数据口径

| 层 | 说明 | 典型用途 |
|---|---|---|
| 投放交付 | impression、click、spend、reach | 媒体交付与成本 |
| 事件接收 | Pixel/CAPI/SDK/离线事件 | 数据链路健康 |
| 平台归因 | 平台窗口内的 attributed conversion/value | 平台优化与运营 |
| 业务结果 | 订单、毛利、MQL、留存、增量 | 最终决策 |

四层数据不能直接当成同一个数字。报告中注明平台、资源 level、日期/时区、归因窗口、币种、数据延迟、维度和是否建模。

## 平台归因、路径分配与增量不是同一件事

- **平台归因**回答平台按自己的窗口和规则给广告分配了多少转化，不回答没有广告时这些转化是否仍会发生。
- **MTA/规则模型**在被观测到的用户路径上分配触点信用；路径缺失、隐私限制和身份拼接会改变结果，也不自动建立因果关系。
- **MMM**用汇总时间序列估算渠道贡献和饱和趋势，适合有足够历史与支出的组合决策；模型结果依赖数据、控制变量和规格，不能当作逐条 Campaign 的即时真值。
- **增量实验/准实验**在设计、分组、样本、污染和执行符合要求时，估计某次投放变化造成的结果差异；报告仍须给出不确定性和适用范围。

各平台采用的转化定义、窗口、跨设备规则和建模口径不同，同一转化可能被多个平台归因。因此平台转化、平台 ROAS 默认并列呈现，不能直接相加，也不能乘固定倍数当“真实值”或增量。预算迁移的重要决策应尽量用实验/准实验校准平台归因和 MMM；数据不足时明确只能给方向性判断。

## 归因差异拆解

平台之间差异通常来自窗口、时区、点击/浏览规则、跨设备、隐私建模、重复事件、退款取消、自然流量和数据刷新延迟。先做定义对齐，再做数字对账；不要用固定比例“校准”所有渠道。

## MMP、CRM 与离线回传

App 使用 MMP/平台事件时保持 install、post-install event、广告点击 ID 和 cohort 口径一致；B2B 把 lead 与 CRM 阶段回传关联；电商用订单号去重并处理退款。离线导入成功不等于平台已完成匹配、计入优化或归因可见。

## 增量评估

当预算决策涉及品牌词、再营销、高意向人群或大额放量，应考虑 holdout、geo split、时间序列、转换提升或平台实验。实验要预先定义主指标、保护指标、分流、运行周期、最小样本、显著性/不确定性和停止规则；不能把观测到的归因 ROAS 直接解释为增量 ROAS。

## MMM 数据准入与 Meridian 参考

MMM 是渠道级、汇总时间序列方法，不是把 Campaign 报表直接丢进模型。以 Google Meridian 的公开数据要求作为准入参考，而不是当成所有 MMM 的硬性普适门槛：

- **历史长度**：Meridian 的一般经验建议是 Geo-level 至少 2 年周数据、National-level 至少 3 年；只有月数据时建议至少 3 年。它同时明确说明数据充足性还取决于模型参数数量、媒体变化、信噪比及后验区间，不能只按周数判定模型可靠。
- **面板粒度**：优先准备连续的 `geo × week × channel` 面板。KPI 要能跨时间和 Geo 加总，例如收入、订单量或转化数；CTR、CPA、ROAS 等比率不能按行直接求和。
- **媒体与控制变量**：每个付费渠道要有花费，以及可加总的曝光指标（如 impression、click；在缺少物理曝光时 spend 可作 proxy，但须说明 CPM/CPC 变化会混淆媒体量与成本）。收集有时间序列的混杂因素/控制变量；控制变量不应因为方便就删掉。
- **完整性与滞后**：补齐 Geo 和时间面板。已确认停投/无曝光的媒体缺口可填零；KPI 与控制变量缺失不能一概填零，应使用有依据的插补并记录方法。媒体历史还应覆盖模型设置的 carryover/max lag。
- **粒度与模型检查**：汇总到渠道而非逐 Campaign 拟合；按可估参数检查数据量与媒体投入变化，完成 EDA、模型健康检查及不确定性分析。Geo 信息可帮助部分池化，但不自动保证识别或因果有效。

本 Agent 的短期跨渠道预算建议工具使用至少 8 个成熟周，属于**历史平均效率的方向性启发式**，不是 Meridian/MMM，也达不到上述 Meridian 历史跨度建议。小样本数据不得用于声称边际回报、因果增量或长期预算最优。

## 隐私边界

只收集实现测量所需的数据，遵循用户授权、地区法规、保留周期和供应商条款。原始 PII 不进入知识库、Prompt、日志或普通报表；Tool 仅接收当前契约允许的脱敏/哈希字段。

## 归因模型选择

| 业务问题 | 可先用的口径 | 需要补的验证 |
|---|---|---|
| 平台内日常优化 | 平台归因窗口 | 后端质量与延迟 |
| 渠道路径分析 | 规则、多触点或数据驱动归因 | 身份覆盖和路径完整性 |
| 品牌/再营销是否增量 | Holdout、Geo 或时间序列 | 随机性、外部干扰和功效 |
| 用户长期价值 | Cohort/LTV | 成熟周期、退款和毛利 |
| 大额预算迁移 | 增量实验 + 边际效率 | 容量、供给和预算可回退 |

归因模型不是越复杂越准确。路径缺失、身份不稳定、事件重复或样本稀疏时，复杂模型只会制造更精确的错觉。每份结论要写模型、窗口、覆盖率、假设、不可观测部分和适用边界。

选择方法要匹配决策成本：日常运营可以把平台报表/MTA 当方向性信号；跨渠道组合预算且有足够时间序列时评估 MMM；高金额或争议大的预算迁移优先设计可信的增量实验。不要用观察性归因结果构造未经验证的平台“校正倍数”。

方法参考：MTA、MMM 与增量评估的适用边界参考并重新表述自本地
[marketingskills measurement paradigms](https://github.com/coreyhaines31/marketingskills/blob/main/skills/attribution/references/measurement-paradigms.md)；
实际选择仍需根据当前数据可用性和决策成本判断。Meridian 数据采集、历史跨度、
面板完整性与数据量/参数比参考 Google 官方文档：
[Collect and organize your data](https://developers.google.com/meridian/docs/pre-modeling/collect-data)、
[Amount of data needed](https://developers.google.com/meridian/docs/pre-modeling/amount-data-needed)。
