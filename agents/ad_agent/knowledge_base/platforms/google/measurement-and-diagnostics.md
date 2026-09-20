---
schema_version: "1"
id: google-ads-measurement-and-diagnostics
title: Google Ads 转化、报表与故障诊断
layer: platform
knowledge_type: workflow
platform: google-ads
source: Google Ads 官方文档 + 当前报表 Capability
source_ref: "https://developers.google.com/google-ads/api/docs/conversions/overview"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google, conversion, gaql, reporting, attribution, diagnostics]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
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
