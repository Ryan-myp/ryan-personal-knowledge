---
schema_version: "1"
id: advertising-optimization-diagnostic-framework
title: 广告投放全链路诊断与优化决策树
layer: experience
knowledge_type: best_practice
platform: all
source: 广告运营实战方法论 + 当前四渠道 Skill
source_ref: agents/ad_agent/skills/channels/*/SKILL.md
version: "1.0.0"
confidence: 0.84
updated_at: "2026-09-08"
tags: [optimization, diagnosis, funnel, learning, pacing, decision-tree]
status: published
---

# 广告投放全链路诊断与优化决策树

## 五层诊断顺序

```text
数据可用性
  -> 投放资格与交付
  -> 媒体/素材效率
  -> 页面与事件转化
  -> 业务价值与增量
```

不要跳过前层直接调出价。没有曝光先查状态、审核、预算、出价、定向、库存、父级和权限；有曝光无点击查创意和相关性；有点击无到站查链接和页面；有到站无事件查事件链路；有事件但成本差查价值、受众质量、竞争和归因。

## 指标分解

```text
spend = impressions × CPM / 1000
clicks = impressions × CTR
conversions = clicks × CVR
CPA = CPM / 1000 / CTR / CVR
```

这组分解用于定位变化来源，不代表平台实际竞价公式。CPA 上升时至少拆解 CPM、CTR、CVR、事件延迟、新老客和商品/线索价值，避免把一个结果指标归因给错误层级。

## 异常分类

| 类型 | 典型信号 | 处理 |
|---|---|---|
| 资格异常 | rejected、not eligible、invalid parent | 修正字段/资产/权限，不重试 |
| 交付异常 | spend/imp 少、pacing 失衡 | 查预算、飞行、bid、库存、定向、审核 |
| 数据异常 | 空报表、跳变、平台与后端不一致 | 查时区、窗口、分页、延迟、去重 |
| 效率异常 | CPA/ROAS 变化 | 拆漏斗与价值，再选动作 |
| 学习扰动 | 修改后波动、重新学习 | 固定观察窗口，减少同时变更 |
| 系统异常 | timeout、rate limit、unknown state | 有界退避 + readback + 幂等 |

## 动作优先级

1. 修复测量和硬阻塞。
2. 修复素材、页面、商品源或线索质量。
3. 在一个变量上做定向/版位/出价实验。
4. 对胜出单元逐步放量，并观察边际效率。
5. 用业务结果和增量实验复盘平台优化是否有效。

## 变更记录

每次动作写明假设、目标层级、变化字段、预期方向、主/保护指标、观察窗口、停止/回滚条件、执行模式、审计 ID 和数据来源。未知状态不得重复创建；写操作默认 dry-run，live 需要显式授权和测试账号/权限门禁。

## 证据等级

| 等级 | 条件 | 输出动作 |
|---|---|---|
| A | 查询完整、数据成熟、后端一致且有实验支持 | 可执行小步变更或放量 |
| B | 平台数据完整，但后端/增量证据不足 | 仅做有护栏的测试 |
| C | 延迟、缺页、事件异常或口径冲突 | 只输出排查和补数计划 |

诊断结论必须把事实、推断和待确认项分开。报表为空、状态未知或事件不成熟时，不得自动暂停、加预算、切换目标或删除对象。
