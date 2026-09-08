---
schema_version: "1"
id: app-game-growth-playbook
title: App 与游戏广告增长深度打法：从安装到 LTV
layer: business
knowledge_type: business_strategy
platform: all
source: App/游戏增长方法论 + 四平台 App 投放能力
source_ref: agents/ad_agent/knowledge_base/business/app-game-growth-playbook.md
version: "1.0.0"
confidence: 0.82
updated_at: "2026-09-08"
tags: [app, gaming, install, retention, cohort, ltv, mmp, monetization]
status: published
---

# App 与游戏广告增长深度打法：从安装到 LTV

## 事件漏斗

```text
ad click -> store/deep link -> install -> first open -> registration
  -> onboarding/tutorial -> activation -> purchase/ad revenue -> D1/D7/D30 retention/LTV
```

安装成本（CPI）只是第一层信号。App 目标、平台事件、MMP、SDK、商店和深链必须形成一致事件图；如果 install 上报正常但 first open/注册缺失，切换到深层优化只会让系统学习到错误或稀疏信号。

## 事件分层

| 层 | 例子 | 决策用途 |
|---|---|---|
| 交付 | impression、click、install | 媒体规模与成本 |
| 激活 | first_open、registration、tutorial_complete | 新用户质量 |
| 价值 | purchase、subscription、ad_revenue | 短期回收 |
| 留存 | D1/D7/D30、回访 | cohort 质量 |
| 业务 | payer rate、ARPU、LTV | 预算与利润 |

每个事件定义唯一键、时间单位、金额币种、版本、系统、地区和是否用于优化。平台接收到事件、归因到广告、报告可见和进入自动出价不是同一个状态。

## 冷启动到规模化

1. **链路验收**：用测试设备验证安装、事件、去重、订单/收入和 consent。
2. **浅层稳定**：先用能稳定获得的事件，确认素材、地区、系统和页面承接。
3. **质量切换**：事件量和延迟达到业务可接受范围后，逐步切换到注册、付费或价值事件。
4. **cohort 复盘**：按投放日期、平台、地区、系统、素材、版本和渠道 cohort 观察留存/LTV。
5. **规模约束**：用可承受 CAC、回收期、库存/客服/内容供给和边际 LTV 决定放量。

## 游戏专属诊断

素材点击率高但 D7 LTV 低，常见于素材承诺与真实玩法不一致、奖励诱导不合适或地区/设备不匹配。把素材角度、商店页、tutorial 完成、首日关键行为和付费 cohort 串起来，不要简单把低 CPI 的素材标记为赢家。

## 订阅与广告变现

订阅要区分 trial start、trial convert、renewal、refund 和 churn；广告变现要区分展示量、填充率、eCPM 和用户留存。收入事件应保留订单/订阅 ID 并处理退款，避免重复回传造成虚高 ROAS。LTV 预测是模型值，要与真实 cohort 分开标记。

## 素材与市场测试

一次实验只改变一个主要变量：玩法展示、角色、冲突、收益、价格、语言或 CTA。国家扩量前确认翻译、本地支付、商店评分、合规和客服承接；不同系统、版本和地区的 CPI/ROAS 不应直接使用同一个阈值。

## 决策规则

| 结果 | 结论 |
|---|---|
| CPI 高、D7 LTV 高 | 不急于淘汰，先评估可接受回收期 |
| CPI 低、激活差 | 优化承诺一致性和事件质量 |
| 安装稳定、付费事件稀疏 | 检查金额/去重，谨慎切深层目标 |
| 短期 ROAS 好、留存差 | 检查低质量促销和价值预测偏差 |
| 事件延迟长 | 用 cohort/滞后校准，不用当天数据决策 |
