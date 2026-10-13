---
schema_version: "1"
id: google-ads-measurement-and-diagnostics
title: Google Ads 转化、报表与故障诊断
layer: platform
knowledge_type: workflow
platform: google-ads
source: Google Ads 官方文档 + 当前报表 Tool Source + marketingskills data-reading 方法
source_ref: "https://developers.google.com/google-ads/api/docs/conversions/reporting"
version: "1.1.0"
confidence: 0.9
updated_at: "2026-10-13"
tags: [google, conversion, gaql, reporting, attribution, diagnostics]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-13"
---

# Google Ads 转化、报表与故障诊断

## 转化测量的分层

```text
业务结果
  -> 事件设计（lead / purchase / install / value）
  -> Conversion Action 与 primary/secondary 语义
  -> 网站、App、离线或增强型转化回传
  -> Google Ads 归因与报表
  -> CRM/订单数据校准
```

转化动作“收到”不等于“计入优化”，也不等于“已归因”。分析时分别记录事件触发、匹配、去重、计入转化、转化值和导入延迟。把 micro conversion（查看商品、开始结账）与 macro conversion（付费、合格线索）混在同一主优化目标，会让自动出价学习到错误信号。

## GAQL 查询原则

- 先确定 customer、资源粒度、日期范围、账户时区和币种。
- 再选择兼容的 resource、metrics 和 segments；不是所有字段都能任意组合。
- 对 Search 关注 query/keyword/ad_group，Shopping/PMax 关注 asset、asset group、listing/product 维度，Campaign 报告用于预算与目标层判断。
- 保留过滤条件、分页、拉取时间和数据新鲜度；派生 CTR、CPC、CPA、ROAS 时写明分子分母。
- `conversions`、`all_conversions`、转化价值和跨设备/建模指标不能不加说明地相加。

## 报表可见性与转化语义

- 搜索词报告并不保证呈现所有查询。Google 会因隐私标准省略查询活动不足的搜索词；可见搜索词不能直接当作全部搜索需求的代表。只有在账户、Campaign 范围、日期、日期口径和指标定义兼容时，才可以用可见搜索词点击量除以 Campaign 点击量报告“已披露点击覆盖率”。这是报表覆盖程度，不是对隐藏查询的抽样推算。若当前 Tool 没有提供搜索词或可比总量，覆盖率就是 Unknown。
- Search Term 与 Performance Max 的报告资源范围不同。不要用普通 `search_term_view` 没有返回数据来推断 PMax 没有搜索需求；应先确认当前 API 版本和已注册 Tool 支持的报告类型。当前能力未暴露所需报表时，不宣称已完成该项审计。
- `conversions` 与 `all_conversions` 语义不同；后者可能包含未计入主 `Conversions` 列的转化操作。先确认转化动作、目标设置和事件含义，再把它称为购买、合格线索或安装。按转化动作分段会改变行粒度，且全零行可能不返回；没有行不等于转化动作不存在，也不足以单独证明活动为零。
- 转化数据可能延迟。明确区分报告日期口径；若用户问“转化发生在哪天”，只有在当前查询支持并实际返回按转化日期统计的字段时才按该口径回答。不得静默混比点击日期与转化日期序列。
- 离线模拟数据、测试夹具和无来源汇总不是账户证据。当前内置报表 Handler 在无 Provider client 时可能返回 `simulated: true` / `data_status: offline_no_client`；这类结果必须标明模拟/离线，不得描述为真实账户表现。缺少可信来源标记时按 Unknown 处理。

## 漏斗诊断树

| 层级 | 信号 | 排查方向 |
|---|---|---|
| 曝光 | impressions 很低 | 状态、审核、预算、出价、资格、定向 |
| 点击 | CTR 低 | 查询意图、广告相关性、资产、竞争位置 |
| 到站 | clicks 有但 sessions 少 | 跟踪参数、重定向、站点可用性 |
| 行为 | 到站有但事件少 | 页面事件、Consent、Tag、事件条件 |
| 计数 | 事件有但 Ads 少 | Conversion Action、primary 设置、导入/延迟 |
| 价值 | 转化有但 ROI 差 | 价值回传、订单去重、毛利、新老客结构 |

“报表为空”不能直接解释为“没有投放”：还要检查日期是否按账户时区、资源是否属于 customer、过滤/权限、报表延迟、分页和字段组合。

## 数据校准

每周至少比较三个口径：平台报告、分析工具和后端订单/CRM。差异先按归因窗口、时区、去重、取消退款、跨设备与建模拆解；不要用一个固定比例强行校正所有 Campaign。线索业务还要追踪 MQL/SQL/成交，而不是只用表单提交优化。

## 安全与执行边界

查询可以通过当前已注册报告 Tool 读取，但字段以 schema 为准。转化动作、用户列表和事件回传属于敏感或写操作，默认 dry-run，必须经过权限、账户范围、live gate、幂等和审计；知识库不保存任何认证材料或原始个人信息。

效果诊断应分别报告来源状态、报表完整性、数据成熟度和投放结果。查询成功不是报表完整的证明；空结果、零指标、被省略的行、权限错误、部分分页和模拟数据不能混为一类。分析低样本时报告实际分母与限制，不套用统一点击数或转化数阈值。

官方参考：

- [About the search terms report](https://support.google.com/google-ads/answer/2472708)
- [Conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting)
- [Search term view](https://developers.google.com/google-ads/api/fields/v25/search_term_view)

方法来源：报表误读排查和证据化审计结构参考并重新表述自
[marketingskills 的 Google Ads data-reading guide](https://github.com/coreyhaines31/marketingskills/blob/main/skills/ads/references/reading-google-ads-data.md)
与
[Google Ads audit checklist](https://github.com/coreyhaines31/marketingskills/blob/main/skills/ads/references/google-ads-audit-checklist.md)；
未导入脚本、外部执行流程或固定阈值。
