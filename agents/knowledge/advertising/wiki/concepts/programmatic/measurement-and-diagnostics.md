---
schema_version: "1"
id: programmatic-measurement-and-diagnostics
title: 程序化广告指标口径与交付诊断
layer: business
knowledge_type: error_pattern
category: programmatic_advertising
subcategory: measurement-diagnostics
platform: all
source: Personal advertising knowledge base synthesis; IAB Tech Lab OpenRTB; Prebid
source_ref: "knowledge/advertising/rtb-system-design-deep.md; knowledge/advertising/dsp-bidding-engine-deep.md; knowledge/advertising/ssp-system-design-deep.md; https://iabtechlab.com/standards/openrtb/; https://docs.prebid.org/"
version: "1.0.0"
confidence: 0.85
updated_at: "2026-10-19"
tags: [programmatic, bid-rate, win-rate, fill-rate, ecpm, viewability, ivt, diagnostics]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: reviewed
last_verified_at: "2026-10-19"
derived_from: "knowledge/advertising/rtb-system-design-deep.md"
wikilinks: ["[[programmatic-advertising-entity]]", "[[programmatic-rtb-and-openrtb-auction]]", "[[programmatic-dsp-decisioning-and-bidding]]", "[[programmatic-ssp-exchange-and-yield]]", "[[programmatic-supply-path-transparency-and-quality]]"]
---

# 程序化广告指标口径与交付诊断

程序化链路横跨请求、竞价、展示、计费和结果回传。对账前先确认事件口径、时区、币种、去重键、归因窗口、报告延迟和费用层级；同名指标可能使用不同分母，不能跨平台或跨供应商直接拼接。

## 指标定义先写分母

| 指标 | 一种常见定义 | 必须注明的边界 |
|---|---|---|
| Bid rate | 返回有效 bid 的请求数 / 收到的合格请求数 | 排除主动 no-bid、无效响应和超时的规则 |
| Win rate | 赢标数 / 参与竞价数，或赢标数 / 出价数 | 分母不同会显著改变读数；需说明 auction/imp 粒度 |
| Fill rate | 填充展示数 / 可售请求数，或 / 广告机会数 | 每个系统对请求、广告位和实际展示的定义不同 |
| Buyer eCPM | 买方花费 / 对应展示数 × 1000 | 花费是毛额还是含平台费用，展示归属如何计数 |
| Publisher net eCPM | 媒体净收入 / 对应展示数 × 1000 | 扣费、退款、汇兑和结算窗口 |
| Render / viewability | 成功渲染或达到测量定义的可见展示 | 测量供应商、适用环境、样本覆盖和延迟 |
| CTR / CVR / CPA / ROAS | 按明确的点击、展示、转化、成本或价值口径计算 | 归因来源、窗口、去重、退款与增量边界 |

`request`、`bid`、`win`、`render`、`billable impression`、`viewable impression` 和 `conversion` 是不同事件，不能在日志或报表里统称为“曝光”。Ad Rendering（素材被绘制、播放或加入目标 DOM）不等同于 Viewability；成功渲染也不自动证明该展示满足某个可见性测量标准。买方 spend 和媒体净收入之间也不必相等。

## 从问题现象沿链路定位

```text
机会量下降
  -> 请求/广告位/SDK 是否正常
Bid rate 下降
  -> DSP 资格、目标、底价、同意信号、超时和创意适配
Win rate 下降
  -> 出价/币种/拍卖规则/Deal/底价/竞争与有效响应
Win 正常但展示少
  -> Ad Server 最终选择、素材下载、格式/政策、页面渲染与计数事件
展示和花费正常但业务结果差
  -> 媒体/版位质量、IVT、可见性、频次、落地页、事件质量与归因延迟
```

## 诊断顺序

1. **统一时间和身份**：对齐请求 ID、imp ID、Deal/媒体/创意标识、账户和时区；建立买方、Exchange、媒体三侧的事件关联。
2. **验证分母与漏斗**：同一时间窗分别统计可售机会、发出请求、有效响应、有效竞价、赢标、渲染、计费展示和回传结果。
3. **按维度分解**：Exchange/SSP、Publisher、域名/App、广告位、格式、Deal、地区、设备、时间段和创意；检查样本量，不从稀疏切片推断稳定规律。
4. **拆开价格与资格**：资格不过、底价未达、输给竞价、Deal 不匹配和超时分别报告；不要统称“出价太低”。
5. **核对数据成熟度**：比较平台与后端的计数延迟、回传失败、去重、退款和归因窗口。未成熟周期标记暂定，不按零处理。
6. **设计验证和回滚**：一次只改变一个主要因素，预先定义主要指标、质量护栏、观察窗口和停止条件；策略变化后检查边际结果而不只看总体平均。

| 症状 | 更可能的链路问题 | 下一步证据 |
|---|---|---|
| 请求不少、DSP 几乎不出价 | 定向/预算/资格/隐私/创意约束过窄，或请求不匹配 | no-bid reason、过滤阶段、`imp` 格式和目标状态 |
| 出价不少、赢标骤降 | 底价、竞争、币种、Deal 或有效 bid 被拒 | Exchange auction type、loss reason、floor 和 currency |
| 赢标增加、实际展示没涨 | Ad Server 竞争、素材或渲染失败、事件去重差异 | winner 到 render 的关联、creative load 和计数日志 |
| Fill/CPM 上升、业务价值变差 | 供应质量、流量组合、频次、落地页或归因问题 | 分供应路径的 IVT/可见性/转化和边际 CPA/ROAS |
| 买方花费与媒体收入对不上 | 毛净口径、费用/退款、汇率、账期或计费展示差异 | 买卖双方结算字段、展示定义、币种与账期 |

不要把延迟、QPS、填充率、胜率或效果提升写成跨系统 benchmark。先建立本链路的基线、SLO 和测量覆盖，再判断异常程度。

## 官方参考

- [IAB Tech Lab OpenRTB](https://iabtechlab.com/standards/openrtb/)
- [Prebid documentation](https://docs.prebid.org/)
