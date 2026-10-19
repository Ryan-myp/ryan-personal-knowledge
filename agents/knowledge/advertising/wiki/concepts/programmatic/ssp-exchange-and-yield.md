---
schema_version: "1"
id: programmatic-ssp-exchange-and-yield
title: SSP、Ad Exchange、Header Bidding 与库存收益
layer: business
knowledge_type: best_practice
category: programmatic_advertising
subcategory: ssp-exchange-yield
platform: all
source: Personal advertising knowledge base synthesis; IAB Tech Lab; Prebid
source_ref: "knowledge/advertising/ssp-deep.md; knowledge/advertising/ssp-system-deep.md; knowledge/advertising/ssp-system-design-deep.md; knowledge/advertising/ad-hb-header-bidding-optimization.md; https://iabtechlab.com/programmatic-auction-definitions/; https://docs.prebid.org/overview/intro-to-header-bidding.html"
version: "1.0.0"
confidence: 0.86
updated_at: "2026-10-19"
tags: [ssp, ad-exchange, adx, header-bidding, prebid, waterfall, floor-price, yield]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/ssp-system-design-deep.md"
wikilinks: ["[[programmatic-advertising-entity]]", "[[programmatic-rtb-and-openrtb-auction]]", "[[programmatic-supply-path-transparency-and-quality]]", "[[programmatic-measurement-and-diagnostics]]"]
---

# SSP、Ad Exchange、Header Bidding 与库存收益

SSP 面向媒体供给侧，管理可售库存、买方接入、交易规则和收益；Ad Exchange 提供买卖双方连接及交易/拍卖能力。二者是逻辑职责，不必然对应两套独立系统或两家公司。部分产品把 SSP、Exchange、Ad Server 或需求聚合做在同一服务中。

## SSP 到展示的主要职责

```text
媒体/广告位接入
  -> 库存、格式、内容与交易资格归一化
  -> 读取 Deal、底价、隐私和质量规则
  -> 选择或路由需求方（OpenRTB / 直客 / 联盟 / SDK）
  -> 在时限内收集有效响应并执行适用竞价
  -> 与 Publisher Ad Server 的直销订单和优先级规则协同
  -> 返回广告并记录请求、竞价、渲染、结算与质量事件
```

Exchange 负责什么、SSP 负责什么，需按架构和合同确定；同一场交易中可能存在 Exchange auction、SSP 内部筛选和 Publisher Ad Server 的最终决策多个阶段。“ADX 一定独立于 SSP”或“Exchange 选中的广告一定展示”都不是安全假设。

## Waterfall 与 Header Bidding

| 方式 | 典型调度 | 常见优势 | 主要代价/风险 |
|---|---|---|---|
| Waterfall | 按优先级串行询价或交给下一级 | 实现直观、优先级明确 | 前序报价可能挡住后续更高价值需求，延迟与价格透明度受实现影响 |
| Client-side Header Bidding | 页面/SDK 在受控时间窗并行询价，再把结果交给 Ad Server | 让多个需求方竞争同一机会，增加可比价信息 | 浏览器/SDK 延迟、超时、并发、用户体验和实现配置复杂 |
| Server-side Header Bidding | 服务端聚合多个 Bidder 请求和响应 | 减少客户端工作，可集中治理连接 | 服务端上下文/身份信号可能不同，新增跳数和排障边界 |
| 混合/统一拍卖 | 多种需求路径进入统一或分层决策 | 可兼顾直接合同与开放需求 | 规则和最终价格更复杂，必须区分各拍卖层的有效报价 |

Header Bidding 更准确可理解为“Ad Server 前的竞价（pre-ad-server bidding）”：它不再局限于网页 HTML header，也覆盖移动 App、视频播放器和服务端请求。Prebid 等框架帮助发布方向需求伙伴收集 bids，再把部分/全部结果交给 Ad Server；Ad Server 仍会把这些 bids 与直销、保量及其他广告需求一起判断，最终展示结果可能不是 Header Bidding 返回的 bid。它不等同于统一支付规则。Waterfall 也不是所有实现都“第一家有填充就结束”，需按实际配置观察。

## 收益优化不是单纯提价

优化目标应同时考虑媒体净收益、填充、延迟、用户体验、合同承诺、质量和可见性。底价过高会减少合格需求与填充；过低可能低价售出、改变需求分布或影响直接销售。动态底价应以可解释的数据分段、对照实验和回退机制验证，而不是拿单一历史 eCPM 分位点套用所有时段。

收益拆解至少区分：

- **机会量**：广告请求、有效广告位、可出售库存和可竞价展示。
- **参与与填充**：发出竞价、有效响应、达到底价、最终被选中和实际渲染。
- **价格**：买方出价、拍卖清算价、买方花费、卖方毛收入和扣费后净收入。
- **质量**：可见性、视频播放、IVT、品牌安全、用户体验和转化/增量结果。

一个环节改善可能损害另一个环节。比如提高 floor 可能抬高成交 CPM 但降低填充；增加 bidder 可能增加竞争，但也增加超时、重复拍卖和费用。应按媒体/广告位/格式/地区/交易/设备分层，再看边际净收益。

## 集成排查

1. 广告机会是否正确产生，尺寸/格式/页面或 App 标识是否匹配？
2. Bidder adapter 是否收到请求，request/response 是否可按 ID 配对？
3. 超时是否覆盖了真实连接耗时；无响应、no-bid 和无效响应是否分开统计？
4. 底价、币种、Deal 和创意限制是否导致过滤？
5. Ad Server 最终选了谁，HB 结果如何参与其竞争？
6. 胜出后创意是否成功获取、渲染并触发正确的计费/展示事件？

Prebid 官方文档描述的超时和 adapter 设置只适用于具体集成配置。必须在真实页面/应用、地区、网络和竞价伙伴组合上测量延迟与超时损失，不把旧笔记里的 800ms 或 100ms 当成通用常数。

## 官方参考

- [Prebid Introduction to Header Bidding](https://docs.prebid.org/overview/intro-to-header-bidding.html)
- [IAB Tech Lab OpenRTB](https://iabtechlab.com/standards/openrtb/)
- [IAB Tech Lab Programmatic Auction Definitions](https://iabtechlab.com/programmatic-auction-definitions/)
