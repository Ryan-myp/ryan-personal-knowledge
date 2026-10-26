---
schema_version: "1"
id: programmatic-advertising-entity
title: 程序化广告与计算广告
layer: business
knowledge_type: general
category: programmatic_advertising
subcategory: overview
platform: all
source: 个人广告知识库归纳；IAB Tech Lab
source_ref: "knowledge/advertising/programmatic-ads-personalized-targeting-deep.md; knowledge/advertising/day-by-day/dv360-03-auction-mechanism-deep.md; https://iabtechlab.com/programmatic-auction-definitions/; https://iabtechlab.com/standards/openrtb/"
version: "1.0.1"
confidence: 0.88
updated_at: "2026-10-26"
tags: [programmatic, computational-advertising, dsp, ssp, ad-exchange, adx, rtb, pmp, auctioneer, final-auctioneer, selling-platform, buying-platform, ad-request-initiator, ad-inventory-controller]
status: published
wiki_type: entity
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/programmatic-ads-personalized-targeting-deep.md"
---

# 程序化广告与计算广告

程序化广告是利用软件和标准化数据交换自动完成广告库存交易、投放和测量的一类方法；RTB 是其中一种按单次展示机会进行实时竞价的交易机制，不是程序化广告的同义词。计算广告更广，关注在广告主目标、媒体库存、用户/上下文信号、拍卖规则和预算约束下，如何做匹配、排序、定价、交付与效果评估。

## 生态角色

| 角色 | 主要问题 | 典型职责 |
|---|---|---|
| 广告主 / 代理商 | 哪些机会值得购买，业务结果如何 | 目标、素材、预算、测量与合规责任 |
| DSP（需求方平台） | 对这次展示出多少价、是否参与 | 需求接入、资格过滤、价值估计、预算节奏、出价和创意选择 |
| SSP（供应方平台） | 如何管理和出售媒体库存 | 库存与广告位管理、需求路由、底价/交易配置、收益与质量管理 |
| Ad Exchange / ADX | 如何连接买卖双方并按规则组织交易 | 请求路由、竞价编排、Deal 约束、胜者与结算处理 |
| Publisher Ad Server | 多种广告需求和合同如何竞争同一库存 | 直销/保量订单、优先级、频次、投放规则和最终广告选择 |
| 数据、测量与验证服务 | 可用信号是否合规，交付是否有效 | 受众/上下文数据、可见性、品牌安全、无效流量和结果测量 |

这些是逻辑职责，不代表每家公司的产品边界。一个产品可能同时承担 SSP、Exchange 或 Ad Server 的部分职责；判断时以具体交易链路、合同和数据流为准。DMP/CDP 是数据组织或激活能力，不是拍卖方，也不会自动获得使用个人数据的许可。

## 拍卖流程角色：Auctioneer、Final Auctioneer、Selling Platform

IAB Tech Lab 与 MRC 于 2026 年发布的拍卖术语定义，提供一组比 DSP/SSP 产品标签更适合描述交易链路的角色：

| 流程角色 | 含义 | 常见映射（不是一对一） |
|---|---|---|
| Ad Inventory Controller | 对该广告机会拥有销售权的实体 | Publisher 或授权库存控制方 |
| Ad Request Initiator | 按库存控制方指示创建请求的系统 | Publisher Ad Server、SDK、Wrapper 或请求服务 |
| Selling Platform | 将广告请求路由给供应链参与方的平台 | SSP、Exchange 或其他销售侧平台 |
| Buying Platform | 评估机会是否符合 Campaign 并提出购买报价的平台 | DSP 或其他需求平台 |
| Auctioneer | 收集竞争报价并按规则做资格筛选/评估的系统 | Selling Platform、Exchange、Ad Server 等 |
| Final Auctioneer | 最终决定是否接受某报价并尝试投放广告的系统 | 常见为 Publisher Ad Server |

同一公司可以在同一条链路中承担多个角色；一个请求也可能经过多跳 Selling Platform，并在不止一个环节发生竞价。拍卖决策通常结合价格与其他资格/价值信号，例如直销承诺、Deal 条件、创意格式、交付节奏、频次、竞争隔离与渲染可靠性。因此“最高 bid 一定胜出”不是通用规则。

## 交易模式

| 模式 | 常见交易安排 | 需要核实 |
|---|---|---|
| Open Auction | 开放给符合条件需求方的竞价机会 | 是否有底价、每个供应链节点的拍卖规则、净价和资格条件 |
| PMP / Private Auction | 通过 Deal 或邀请限定可参与的买方，通常仍可能竞价 | 买方名单、Deal ID、价格/底价、媒体和格式限制 |
| Preferred Deal | 买卖双方约定价格/优先机会，通常不等同于保量合同 | 优先级是在何处应用；没有买方响应时库存如何回到其他需求 |
| Programmatic Guaranteed | 双方通过程序化系统执行约定的价格与库存交付安排 | 交付量、排期、违约/补量与其他广告需求如何参与最终选择 |

交易名称、优先级、价格和结算语义会因平台产品而异；“程序化”描述交易自动化，不代表每一步都是开放拍卖。即使 Deal 已确定，最终 Ad Server 仍可能按其订单优先级和业务规则选择其他广告。DV360 的 Deal 细节见 [[dv360-deals-auctions-and-bid-strategy]]。

## 关键概念地图

- 一次展示如何形成竞价请求、DSP 如何响应、Exchange 如何处理结果：[[programmatic-rtb-and-openrtb-auction]]
- DSP 如何从转化价值、拍卖和预算约束做决策：[[programmatic-dsp-decisioning-and-bidding]]
- SSP、ADX、Header Bidding 与库存收益：[[programmatic-ssp-exchange-and-yield]]
- ads.txt、sellers.json、SupplyChain 与流量质量：[[programmatic-supply-path-transparency-and-quality]]
- 如何定义程序化指标并按漏斗定位问题：[[programmatic-measurement-and-diagnostics]]

## 阅读边界

本组页面是跨平台的概念与工程知识，不代表本项目的广告 Agent 已具备 DSP/SSP/ADX 竞价服务或对应 API。平台字段、交易资格、账号权限和真实能力以平台官方文档、账户证据及当前 Tool schema 为准。旧个人笔记中的示例代码、固定延迟/QPS、案例提升百分比和设备指纹方案未作为已验证事实引入。

## 官方参考

- [IAB Tech Lab OpenRTB](https://iabtechlab.com/standards/openrtb/)
- [IAB Tech Lab Programmatic Auction Definitions](https://iabtechlab.com/programmatic-auction-definitions/)
