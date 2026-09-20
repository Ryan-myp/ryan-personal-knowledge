---
schema_version: "1"
id: tiktok-app-commerce-operations
title: TikTok App、Lead、商品销售与事件回传
layer: platform
knowledge_type: workflow
platform: tiktok
source: TikTok Ads API 官方文档 + TikTok Capability/Skill
source_ref: "https://business-api.tiktok.com/portal/docs?id=1738865671534594"
version: "1.0.0"
confidence: 0.84
updated_at: "2026-09-08"
tags: [tiktok, app, gaming, product-sales, catalog, lead, pixel, events-api, mmp]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# TikTok App、Lead、商品销售与事件回传

## App 增长漏斗

```text
曝光/点击 -> 商店或深链打开 -> install -> first_open -> registration/tutorial -> purchase/ad_revenue -> D1/D7/D30 value
```

App Promotion 创建前确认 app_id、操作系统、商店链接/深链、MMP 或 SDK 事件、事件命名、时区、版本和隐私授权。安装是浅层结果，游戏和订阅产品要按 cohort 比较注册率、留存、付费率、ARPU/LTV 与退款，不要只追求最低 CPI。

## 事件质量检查

事件字典应包含 event_name、唯一 event_id、event_time 单位、action source、value/currency、商品/订单或 App 属性。Pixel 与服务端 Events API 双发时保持同一业务事件 ID；接收、匹配、去重、报表可见和被用于优化是不同阶段。测试事件 code 与生产配置分离，原始用户数据不进入日志或知识库。

## 商品销售

Product Sales 依赖 advertiser 下可用的 Catalog/Product Set、商品选择、库存/价格、商品 ID、落地页和购买价值。当前项目可以读取并校验部分商品引用，但 Catalog/Product Set 的创建/更新/删除存在计划中的覆盖边界，不能从一个 catalog 名称直接推断可执行资源。

## Lead 质量

Lead 方案要定义表单来源、隐私政策、字段最小化、销售 SLA、去重键和 CRM 回传。分析从 lead → contacted → qualified → opportunity → won，按销售周期做 cohort；优化目标切换到 qualified lead 前，先确保事件量与延迟可支撑学习。便宜的原生表单可能带来更多无效线索，不应只用 CPL 评估。

## 目标诊断

| 目标 | 主指标 | 保护指标 |
|---|---|---|
| App 安装 | install、CPI | 首开、注册、D7 留存、LTV |
| App 价值 | purchase、ROAS/LTV | 事件延迟、退款、留存 |
| 商品 | purchase value、ROAS | 毛利、退款、商品状态 |
| Lead | lead、CPL | 有效率、MQL、成交率 |
| 流量/观看 | LPV、CPC、有效观看 | 页面质量、后续转化 |

## 当前执行边界

当前项目覆盖 App、Audience、Pixel/Event、Catalog/Product Set lookup、Report 和相关 Ad 创建链路；具体目标组合、枚举、最低预算、地区资格与 live 支持必须经过 Registry Tool schema 校验。
