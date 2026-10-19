---
schema_version: "1"
id: programmatic-rtb-and-openrtb-auction
title: RTB 与 OpenRTB：一次展示竞价的生命周期
layer: business
knowledge_type: workflow
category: programmatic_advertising
subcategory: auction-mechanics
platform: all
source: Personal advertising knowledge base synthesis; IAB Tech Lab OpenRTB and Programmatic Auction Definitions
source_ref: "knowledge/advertising/rtb-system-design-deep.md; knowledge/advertising/rtb-flow-implementation-deep.md; knowledge/advertising/ad-protocol-openrtb-tcf-deep.md; https://iabtechlab.com/programmatic-auction-definitions/; https://github.com/InteractiveAdvertisingBureau/openrtb2.x/releases"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-10-19"
tags: [rtb, openrtb, bid-request, bid-response, auction, impression, bid-floor, timeout, selling-platform, final-auctioneer, multi-stage-auction, ad-rendering]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/rtb-system-design-deep.md"
wikilinks: ["[[programmatic-advertising-entity]]", "[[programmatic-dsp-decisioning-and-bidding]]", "[[programmatic-ssp-exchange-and-yield]]"]
---

# RTB 与 OpenRTB：一次展示竞价的生命周期

RTB（Real-Time Bidding）把可售展示机会交给有时限的实时处理链路。OpenRTB 是常见的交易请求/响应标准之一，用于交换竞价上下文；它不规定所有供应链路由、每一层的排序策略、最终页面广告选择、计费实现或业务策略。

生态角色与交易模式总览见 [[programmatic-advertising-entity]]。

IAB Tech Lab 与 MRC 于 2026 年 finalized 的 Programmatic Auction Definitions 强调：拍卖是某个参与方按相对价值和适用规则筛选、评估竞争报价的过程。它可能不仅按价格排序，也可能结合资格、Deal、业务目标、频控、竞争隔离、创意质量等条件；一个供应链中可以存在多次竞价和多个拍卖人。

## 逐阶段交易流程

```text
0. 库存控制方配置广告位与最终决策规则
1. Ad Request Initiator 发起请求并传递广告位/上下文/约束
2. Selling Platform 校验请求、供给授权、格式与可用信号
3. Selling Platform 按许可/规则丰富请求（若适用）
4. 将请求路由给合格 Buying Platform（并非每个买方都会收到每个请求）
5. Buying Platform 内部评估 Campaign，返回 no-bid、错误、超时或一个/多个报价
6. 对返回报价做协议/字段/超时等技术校验
7. 检查买方、广告域名、创意、价格、Deal 和供应限制等业务资格
8. 在当前拍卖层按价格及相对价值规则竞争；记录费用、折扣、净价和相关口径
9. 中间 Auctioneer 可将一个或多个可接受报价继续送往上游
10. Final Auctioneer 做最终资格判断并尝试渲染；获选报价不保证一定成功渲染
11. 记录渲染/计费事件、费用、清算价和相关遥测
12. 在参与方之间对账并解释差异
```

以上是标准化的通用步骤，不是单一线性调用图。一个请求可以在多跳供应链上重复执行其中部分步骤；一个平台也可能合并多个角色。Selling Platform 的胜出报价也不一定成为 Final Auctioneer 的最终广告：Publisher Ad Server 可能按直销订单、保量义务或其他优先级选出另一个广告。

## 多跳竞价、Final Auctioneer 与最终渲染

一次程序化交易可能经过多个 Selling Platform 和 Auctioneer；每一层都有自己的有效报价、资格规则和结果。上游的 winning bid（赢标报价）只说明它赢得了当前这一层，不代表它赢得了整条链路。Final Auctioneer 会执行最后的选择，再尝试让广告渲染；Publisher Ad Server 常承担该角色，但真实实现可能不同。因此必须分别记录“该层赢标”“最终被选中”“广告成功渲染”和“计费展示”，不能把 win 直接当成 impression。

## OpenRTB 请求与响应

Bid Request 通常由请求 ID、一个或多个 `imp`（展示机会）、`site` 或 `app` 上下文、`device`、可选 `user`、法规/隐私信息、拍卖参数和扩展字段组成。响应包含与请求关联的 ID，以及 `seatbid` / `bid` 等买方响应结构；每个 bid 需要对应一个有效的 `impid`，并提供价格和符合该机会的广告/创意信息。具体字段应按双方约定的 OpenRTB 版本、媒体格式和扩展实现校验。

| 字段/对象 | 作用 | 排查要点 |
|---|---|---|
| `id` | 关联请求和响应 | 日志、超时、胜出通知应能关联同一请求 |
| `imp` | 描述可售机会及其格式 | 一个请求可含多个机会；核对尺寸、视频/原生要求和底价 |
| `site` / `app` | 描述 Web 或应用上下文 | 检查域名、Bundle、Store URL 等身份是否可信且一致 |
| `device` / `user` / `regs` | 设备、可用用户信号与合规上下文 | 缺失或受限时应正确降级，不得绕开同意状态 |
| `tmax` | 该竞价请求允许的响应时间上限 | 不是 DSP 的通用 SLA；要预留网络、解析和返回时间 |
| `bidfloor` / `bidfloorcur` | 机会的底价及货币表达 | 必须处理币种、精度、换算与价格口径 |
| `at` | 声明拍卖类型/支付语义 | 以所协商的规范版本和 Exchange 契约解释，不推断全局规则 |
| `deal` | 描述受限交易机会 | Deal ID、允许买方、价格、格式和有效期均需匹配 |

OpenRTB 2.x 是持续维护的版本化规范。截至 2026-10-19，IAB Tech Lab 的 `openrtb2.x` 发布记录最新为 `2.6-202606`，其发布节奏为按需更新；集成应锁定买卖双方实际支持的 dated release、扩展和 feature，而不是把一份旧示例 JSON 或“OpenRTB 2.6”笼统字符串当成完整契约。

## 拍卖、排序与结算不能混为一谈

- 在简单的第一价格拍卖中，胜者按有效最高报价结算；但实际链路可能有多个拍卖层、按参与方计算的净价、费用/折扣和业务资格，不能把该简化模型套到所有计费账单。
- 第二价格及其变体依据相应拍卖规则确定价格；底价、Deal、价格转换和上游拍卖会改变“第二高价”的简化解释。
- 固定价或保量交易不应误读为开放竞价。PMP 也可能仍然通过拍卖竞争。
- 竞价响应里的 `price`、Exchange 的清算价、买方账单、卖方净收入是不同口径；平台费、汇率、结算调整和事件归因都可能造成差异。

不得把旧笔记中的“所有 RTB 都是最高价获胜”“二价拍卖只支付第二高价”或某个固定支付 tick 当成普遍规则。竞价类型和 payment rule 必须以具体交易契约为准。

## no-bid 与超时排查

1. **请求根本未发出**：检查库存配置、Ad Request Initiator、SDK/标签和广告位资格。
2. **Selling Platform 未路由到买方**：核对请求校验、授权/供应链、地区/格式、商业筛选和路由策略。
3. **买方主动 no-bid、报错或超时**：检查 Campaign 资格、预算/频控、可用信号、响应处理和 `tmax`；四种结果必须分别记录。
4. **报价技术校验或业务资格失败**：核对请求/响应 ID、`impid`、币种/价格、创意和 Deal、广告域/买方许可、超时与版本扩展。
5. **报价在中间层没有胜出**：查该层的参与分母、净价、费用/折扣、底价、非价格资格和具体 loss reason；不能一概归因于“出价低”。
6. **Selling Platform 胜出但没成为最终广告**：核查上游 Auctioneer / Final Auctioneer 的后续选择，特别是直销与合同优先级。
7. **最终获选但未渲染或未计费**：区分创意获取、格式错误、页面离开、渲染、billable event、计费通知与对账。

日志只保留诊断所需的脱敏请求标识与字段，不把完整 IP、用户 ID、设备标识、竞价请求或响应无限期放入普通日志。

## 官方参考

- [IAB Tech Lab OpenRTB specifications](https://iabtechlab.com/standards/openrtb/)
- [OpenRTB 2.x releases](https://github.com/InteractiveAdvertisingBureau/openrtb2.x/releases)
- [OpenRTB 2.x repository](https://github.com/InteractiveAdvertisingBureau/openrtb2.x)
- [IAB Tech Lab Programmatic Auction Definitions](https://iabtechlab.com/programmatic-auction-definitions/)
- [Final Programmatic Auction Definitions](https://github.com/InteractiveAdvertisingBureau/programmatic-auction-definitions/blob/main/auction%20definitions.md)
