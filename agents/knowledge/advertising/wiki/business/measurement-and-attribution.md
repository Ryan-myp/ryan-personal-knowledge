---
schema_version: "1"
id: cross-platform-measurement-attribution
title: 跨平台事件、归因与增量评估
layer: business
knowledge_type: general
platform: all
source: 四平台测量文档 + 广告归因方法论
source_ref: "internal://ad-agent/playbook/cross-platform-measurement-attribution"
version: "1.0.0"
confidence: 0.86
updated_at: "2026-09-08"
tags: [measurement, attribution, conversion, incrementality, mmp, crm, privacy]
status: published
source_kind: "internal"
authority: "operator"
evidence_level: "provisional"
last_verified_at: "2026-09-08"
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

## 归因差异拆解

平台之间差异通常来自窗口、时区、点击/浏览规则、跨设备、隐私建模、重复事件、退款取消、自然流量和数据刷新延迟。先做定义对齐，再做数字对账；不要用固定比例“校准”所有渠道。

## MMP、CRM 与离线回传

App 使用 MMP/平台事件时保持 install、post-install event、广告点击 ID 和 cohort 口径一致；B2B 把 lead 与 CRM 阶段回传关联；电商用订单号去重并处理退款。离线导入成功不等于平台已完成匹配、计入优化或归因可见。

## 增量评估

当预算决策涉及品牌词、再营销、高意向人群或大额放量，应考虑 holdout、geo split、时间序列、转换提升或平台实验。实验要预先定义主指标、保护指标、分流、运行周期、最小样本、显著性/不确定性和停止规则；不能把观测到的归因 ROAS 直接解释为增量 ROAS。

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
