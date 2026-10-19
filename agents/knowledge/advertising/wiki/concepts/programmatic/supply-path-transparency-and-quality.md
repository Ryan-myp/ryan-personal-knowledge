---
schema_version: "1"
id: programmatic-supply-path-transparency-and-quality
title: 程序化供应链透明度、流量质量与隐私边界
layer: business
knowledge_type: best_practice
category: programmatic_advertising
subcategory: supply-quality
platform: all
source: Personal advertising knowledge base synthesis; IAB Tech Lab
source_ref: "knowledge/advertising/ad-protocol-openrtb-tcf-deep.md; knowledge/advertising/programmatic-ads-personalized-targeting-deep.md; https://iabtechlab.com/ads-txt/; https://iabtechlab.com/sellers-json/; https://iabtechlab.com/supply-chain-object/"
version: "1.0.0"
confidence: 0.87
updated_at: "2026-10-19"
tags: [ads-txt, app-ads-txt, sellers-json, schain, supply-chain, ivt, brand-safety, privacy]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/ad-protocol-openrtb-tcf-deep.md"
wikilinks: ["[[programmatic-advertising-entity]]", "[[programmatic-ssp-exchange-and-yield]]", "[[programmatic-measurement-and-diagnostics]]"]
---

# 程序化供应链透明度、流量质量与隐私边界

程序化采购跨越媒体、SSP、Exchange、代理和 DSP 等环节。透明度文件可以帮助确认某个卖方账号、实体和转售链路如何声明，但不能单独证明每次展示都是真实、可见、合规或高质量。

## 三类供应链信号

| 信号 | 主要回答 | 不应推断为 |
|---|---|---|
| `ads.txt` / `app-ads.txt` | 网站/App 发布者公开声明哪些卖方可销售其库存，以及授权关系类型 | 该文件存在就能证明流量真实或广告一定可投 |
| `sellers.json` | 中介/交易方公开其卖方账号对应的实体信息 | 所有 seller ID 都能唯一、实时、完整映射到最终媒体 |
| `SupplyChain` (`schain`) | 一次竞价供应路径中声明的参与节点及链路完整性 | 节点少就一定更安全或收入更高 |

IAB Tech Lab 对 ads.txt、sellers.json 和 SupplyChain object 分别定义了不同目的；它们需要交叉使用。截至 2026-10-19，ads.txt/app-ads.txt 1.1 已增加 `OWNERDOMAIN` 和 `MANAGERDOMAIN` 声明；这些是参与方公开的关系信息，不是平台独立验证或流量质量背书。检查时还要考虑发布文件更新延迟、Seller ID 命名空间、域名/App 身份匹配、`DIRECT` / `RESELLER` 声明、供应商缓存及协议扩展。缺失或冲突应先标为待核查，而不是自动判定欺诈。

## 可复现的路径核验

1. **确认库存身份**：规范化网站域名或 App Bundle/Store URL，并与广告请求、媒体账户和报告维度核对。
2. **核对授权声明**：在对应 ads.txt/app-ads.txt 中查 Exchange/SSP 的 seller account ID、关系类型和必要的认证标识。
3. **解析卖方实体**：查询相应 sellers.json，区分 publisher、intermediary 和隐藏/机密卖方等状态；保留采集时间与来源。
4. **检查请求路径**：解析 OpenRTB `source`/扩展中的 SupplyChain 节点，查看节点顺序、seller ID、域名和链路完整性声明。
5. **做一致性判定**：缺失、匹配、冲突、未知分别记录；由运营/合规流程判断是否限制供应，保留原始证据摘要与更新时间。
6. **用交付证据复核**：把路径与竞价、成本、渲染、IVT、可见性、投诉和转化质量联结，避免只凭文本文件下结论。

## Supply Path Optimization（SPO）

SPO 的目标是让购买侧更好地选择可验证、有效率且符合质量要求的供应路径。决策不应退化成“只买最短链路”：不同路径可能有独有库存、不同身份信号、费用、重复拍卖、延迟和测量覆盖。

建议以供应商/Exchange/媒体/格式/Deal 分层审视：

- 到达率、请求重复或重复竞价、有效响应与赢标；
- 买方成本、卖方净收益、供应费用和计价口径；
- 域名/App 身份、授权关系、SupplyChain 完整性和异常变更；
- IVT、品牌安全、可见性、渲染、用户体验及业务结果；
- 库存覆盖、独有触达、增量价值与数据可验证性。

减少中介可能减少某些费用或重复，但若同时损失有效库存、竞价竞争或身份匹配，净效果未必更好。任何路径排除都应先有可比较的样本、合适的指标和回退条件。

## 流量质量与隐私

把机器人/无效流量、域名或 App 欺骗、异常点击、低可见性、创意加载失败、内容不适配和测量归因误差分开诊断。一个供应商的 IVT 或 brand-safety 信号不是全市场通用真值，需记录检测规则、覆盖、延迟和豁免。

只处理当前交易和用户许可允许使用的数据；按目的最小化采集、传输、保留和共享。OpenRTB 中的设备/用户/地区法规信号不能被忽略；用户拒绝、平台限制或信号缺失时，应采取合规的上下文投放/不个性化路径。旧笔记中的浏览器/设备指纹示例不应作为推荐方案；不得通过隐蔽指纹重建身份或规避同意机制。法律适用性应由合规负责人按地区和当前合同确认。

## 官方参考

- [IAB Tech Lab ads.txt](https://iabtechlab.com/ads-txt/)
- [IAB Tech Lab sellers.json](https://iabtechlab.com/sellers-json/)
- [IAB Tech Lab SupplyChain object](https://iabtechlab.com/supply-chain-object/)
- [IAB Tech Lab OpenRTB](https://iabtechlab.com/standards/openrtb/)
