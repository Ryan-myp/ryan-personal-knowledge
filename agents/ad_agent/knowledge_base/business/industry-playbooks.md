---
schema_version: "1"
id: industry-advertising-playbooks
title: 电商、App 游戏与 B2B 线索行业投放打法
layer: business
knowledge_type: business_strategy
platform: all
source: 广告行业方法论 + 四平台官方能力边界
source_ref: agents/ad_agent/knowledge_base/business/industry-playbooks.md
version: "1.0.0"
confidence: 0.78
updated_at: "2026-09-08"
tags: [ecommerce, app, gaming, b2b, lead-generation, industry, strategy]
status: published
---

# 电商、App 游戏与 B2B 线索行业投放打法

## 电商

核心链路是商品可发现性 → 商品详情 → 加购 → 结账 → 购买 → 复购。先保证商品源、价格库存、购买价值和退款口径稳定，再按新客/再营销、高毛利/引流品、地区和季节建立可解释切片。Google Shopping/PMax、Meta Catalog、TikTok Product Sales 都依赖目录状态，但目录字段和 Tool 能力不互通。

优化顺序：商品源质量 → 素材卖点 → 页面速度/承诺一致 → 购买事件与价值 → 新老客结构 → 预算与目标。平台 ROAS 上升但毛利下降时，应改看贡献利润 ROAS、折扣、退款与新客质量。

## App 与游戏

把 install、注册、tutorial complete、付费、留存和广告变现拆成事件漏斗；安装量不能代表用户质量。冷启动先稳定 SDK/MMP/平台事件与去重，再逐步从安装优化切到注册、付费或价值优化。游戏还要按素材题材、国家、系统、版本、D0/D7 留存和付费 cohort 评估，避免只用 CPI 淘汰高 LTV 用户。

## B2B 与 Lead Gen

表单提交只是中间事件。建议建立 lead → MQL → SQL → opportunity → closed-won 的回传链路，并在 CRM 侧去重、标注来源和销售周期。预算决策用有效线索成本、商机成本和获客成本，而不是最便宜的表单 CPL。较长转化周期要使用 cohort 和滞后校准，不能因为短期平台转化少就立刻切换目标。

## 本地服务与订阅

本地服务同时关注地域覆盖、来电/预约质量、营业时间和线索响应速度；订阅业务关注试用激活、首月/长期留存、退款与 LTV。受众与素材要承诺真实可交付的服务范围，不能用泛化的行业 benchmark 代替当前业务数据。

## 行业选择流程

1. 先确认真实商业结果与可回传事件。
2. 选择能稳定获得该事件的平台目标，而不是先选熟悉的 Campaign 类型。
3. 设计平台内实验单元和跨平台对照口径。
4. 设定主指标、保护指标、最小样本/花费与停止规则。
5. 用后端结果复盘平台优化信号是否真正代表业务价值。

## 三类行业 Runbook

### 电商

先检查商品 ID、价格、库存、配送、退货、页面和订单去重，再判断 Shopping/PMax、Catalog 或 Product Sales 的预算与素材。主指标可按商品利润和新客价值分层，保护指标包含退款率、缺货率、履约能力和贡献利润。

### App/游戏

先验证安装、注册、关键行为、付费、留存和收入事件的版本、时区、MMP 映射与去重。短期 CPI 不足以决定扩量，需按成熟 cohort 看付费、留存、LTV 和回收期；版本发布、商店审核和地区差异要作为外部变量记录。

### B2B/Lead Gen

把表单提交、可联系、MQL、SQL、机会和成交分开建模。平台优化事件可以是稳定的中间信号，但预算复盘应回收到 CRM 有效率、销售周期、成交率、合同毛利和 CAC；线索响应延迟会造成平台窗口与业务窗口错位。
