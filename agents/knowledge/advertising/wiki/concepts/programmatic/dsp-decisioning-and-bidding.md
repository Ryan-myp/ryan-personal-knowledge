---
schema_version: "1"
id: programmatic-dsp-decisioning-and-bidding
title: DSP 决策链路、价值出价与预算节奏
layer: business
knowledge_type: bidding_strategy
category: programmatic_advertising
subcategory: dsp-decisioning
platform: all
source: 个人广告知识库归纳；IAB Tech Lab OpenRTB
source_ref: "knowledge/advertising/ad-dsp-architecture-deep.md; knowledge/advertising/dsp-core-architecture-deep.md; knowledge/advertising/dsp-bidding-engine-deep.md; knowledge/advertising/dsp-bidding-strategy-deep.md; https://iabtechlab.com/standards/openrtb/"
version: "1.0.1"
confidence: 0.86
updated_at: "2026-10-26"
tags: [dsp, pctr, pcvr, value-bidding, bid-shading, budget-pacing, frequency-cap]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/ad-dsp-architecture-deep.md"
wikilinks: ["[[programmatic-advertising-entity]]", "[[programmatic-rtb-and-openrtb-auction]]", "[[programmatic-measurement-and-diagnostics]]"]
---

# DSP 决策链路、价值出价与预算节奏

DSP 的任务不是对每个请求都出价，而是在严格响应时限、投放资格、预算、频控、隐私和业务目标约束下，选择是否参与、使用哪个创意及出价多少。

## 请求决策流水线

```text
接收并校验协议
  -> 判断账户 / Campaign / Line Item / 创意是否符合库存机会
  -> 检查同意状态、可用数据、排除项与频次
  -> 获取可用特征并估计点击 / 转化 / 价值
  -> 结合竞价规则、剩余预算和 pacing 计算出价
  -> 选择可投创意并构造协议响应
  -> 记录 no-bid / 出价 / 胜负 / 展示 / 成本 / 转化反馈
```

每一层都可能短路为 no-bid。画像服务或模型超时不能假装为高置信价值；应按事先定义的降级规则使用可解释的较弱信号或不出价，并记录降级原因。

## 从业务目标到每次展示价值

在简化的 CPM 等价口径下，可以把一次机会的期望价值表达为：

```text
期望价值 / impression
  = P(目标事件 | impression, 可用特征) × 该事件的业务价值
期望 CPM 等价价值
  = 期望价值 / impression × 1000
```

若目标事件按点击成本或转化成本报价，可用概率把目标成本转换为每千次展示的期望值：

```text
点击目标：P(click | impression) × 目标 CPC × 1000
转化目标：P(conversion | impression) × 目标 CPA × 1000
```

若模型只给出“点击后的转化概率”，则 `P(conversion | impression)` 还需要结合 `P(click | impression)`；若转化价值因人/订单而不同，应预测价值或使用可靠的价值信号。上述只是期望值框架，不是某平台的实际出价 API 公式，也未包括费用、拍卖支付规则、赢标概率、边际效用和预算影子价格。

出价可以概念化为最大化“赢得机会的概率 × 预期业务价值，减去预期媒体成本”，同时满足预算、频次、创意资格和风险约束。只有拍卖规则与计价口径已知时，才可将出价与实际成本直接比较。CPM/CPC/CPA 的产品名称并不能说明平台内部按何种 auction payment rule 结算。

## 第一价格、Bid Shading 与校准

第一价格环境下，胜者通常承担自己的有效出价，因此 DSP 可能基于历史竞争/清算价格分布估算 win curve，并对真实估值做 shading。目标是降低期望成本，同时守住赢标量或转化价值；不是按固定比例打折。新库存、稀疏样本、隐私信号变化、Exchange 规则变化和策略切换都会让历史分布失效。

每次策略调整至少比较出价覆盖、win rate、实际 CPM、转化质量、边际 CPA/ROAS 和预算消耗；不要只凭 win rate 决定加价或降价。模型概率需要校准，并按媒体、格式、设备、市场和目标事件检查漂移；训练标签的延迟与选择偏差也必须纳入解释。

## 预算 pacing 与频控

Pacing 把活动预算和交付周期映射为随时间变化的参与/出价策略。它需要考虑剩余预算、活动剩余时间、可用库存、目标效率、转化延迟和消耗预测；匀速花费并非总是最优，过早花完与期末欠量也不是仅靠乘一个固定系数能解决。

预算控制可包含账户/活动/广告组限额、并发预留、短期速率限制和事后对账。分布式竞价下如果只依赖每机本地计数，可能出现暂时超投；若采用预留或分片预算，要定义租约、未赢标释放、进程故障恢复和最终对账规则。频控则应明确主体、作用域、时间窗、跨设备去重能力和隐私许可；不支持身份匹配时不能承诺全域频控。

## DSP 诊断卡

| 现象 | 优先检查 | 不要先做 |
|---|---|---|
| Bid rate 很低 | 目标、库存/格式资格、排除项、同意信号、底价、预算状态 | 盲目提高 bid |
| Bid rate 正常但 win rate 低 | 竞价类型、有效出价、底价、Deal、竞争分布、超时 | 将所有输标归因于模型差 |
| 赢标增加但成本失控 | first-price 支付口径、bid shading、pacing、并发预算、重复请求 | 只看平均出价 |
| 点击/转化预测不错但业务差 | 校准、展示后选择偏差、事件去重、转化价值和延迟、供应质量 | 用平台归因数直接当增量 |
| 模型/特征故障 | 请求阶段时长、缓存命中、缺失率、降级比例和输出版本 | 用旧笔记的固定毫秒预算作 SLA |

## 官方参考

- [IAB Tech Lab OpenRTB](https://iabtechlab.com/standards/openrtb/)
