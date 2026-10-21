---
schema_version: "1"
id: google-asset-performance-reporting
title: Google Ads 广告素材级报表与表现解读
layer: platform
wiki_type: concept
knowledge_type: workflow
category: reporting
subcategory: asset-performance-reporting
platform: google-ads
source: Google Ads API 官方报告文档与项目内 Provider Tool contract
source_ref: "https://developers.google.com/google-ads/api/docs/performance-max/asset-reporting"
source_kind: official
authority: official
evidence_level: reviewed
last_verified_at: "2026-10-21"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-10-21"
tags: [google-ads, asset, creative, performance-max, reporting, gaql]
status: published
---

# Google Ads 广告素材级报表与表现解读

Google Ads 的素材表现不是一个可跨广告类型通用的报表。查询前先选与投放对象匹配的资源，再固定 Campaign、日期范围和报表粒度。当前项目提供两个只读入口：

| Tool | 主资源 | 适用范围 | 重要字段 |
|---|---|---|---|
| `google_get_ad_asset_report` | `ad_group_ad_asset_view` | 与 Ad 关联的资产报告；具体广告类型和字段受 API 兼容规则限制 | Ad、Asset、字段类型、`performance_label`、逐日指标 |
| `google_get_asset_group_asset_report` | `asset_group_asset` | Performance Max Asset Group 素材 | Asset Group、Asset、字段类型、状态、逐日转化数与转化价值 |

两个 Tool 都需要 Campaign ID，并支持有限日期区间和有界结果数。`asset_group_asset` 的 v24 兼容字段仅提供有限的转化类指标；不能从这个资源请求 impressions、clicks 或 cost，也不能用空值补成零。Tool 只读取广告报告，不上传、创建或替换素材；当前 provider API 版本以 Tool contract 为准。缺少账户权限或报告字段时，应返回实际 API 错误或空结果状态，不合成零值。

## 解读规则

- Ad 资产报告与 PMax Asset Group 资产报告是不同资源，不能用一个查询模板假定所有广告类型都适用。
- `performance_label` 是 Google 对该资源中资产表现的相对标签，不等于完整的素材级支出、增量效果或跨 Campaign 排名。不能把标签翻译成确定的“赢家/输家”。
- PMax `asset_group_asset` 素材行返回的转化类指标不是素材层面的完整交付报表；需要花费、点击或展示时，应使用兼容的 Ad Group/Asset Group 报告并保持粒度，不把组级数据下推到单个素材。
- 有逐日指标也不代表素材单独随机分流；受众、版位、竞价、资产组合、投放量和学习状态都会影响报告值。将其作为平台内观察信号，而非创意因果实验结论。
- 每次报告都记录账户、Campaign、日期、Asset/Asset Group、字段类型、返回行数、数据来源和抓取时间。比较时保持层级、日期与指标定义一致。
- 缺少某个资产行可能来自不兼容的报告资源、无交付/低量、字段组合限制或数据延迟；先检查查询契约和 Campaign 类型，不把空行自动解释成零表现。
- 跨日、跨层级或跨资产组合汇总之前先确认可加性；不可加指标、相对标签和组合级指标不得求和。

## 可复核闭环

```text
Campaign / 广告类型
  -> 选择匹配的 GAQL 资源
  -> 按日期和 Campaign 限定范围
  -> 读取 Asset / Asset Group 关联和平台指标
  -> 标记字段兼容、数据量和报告成熟度
  -> 结合素材版本、投放结构和实验设计解释
  -> 若需替换素材，另走创意制作、预览、批准与广告变更流程
```

素材报告回答的是平台报告了什么，不回答换素材会不会带来增量。创意胜负应通过可比的实验或受控迭代验证；如 API 不返回可用分层，不用模型猜出素材贡献。

## 版本与来源

项目当前 Google Ads Provider 固定使用 API v24；截至 2026-10-21，官方最新主版本为 v26（2026-10-14 发布），v24 计划于 2027-05 sunset。升级需要单独核对资源字段兼容、枚举、请求行为和 live readback，不应仅替换 URL 版本号。本页能力按项目 v24 Tool contract 描述。

- [Performance Max asset reporting](https://developers.google.com/google-ads/api/docs/performance-max/asset-reporting)
- [AdGroupAdAssetView v24 fields](https://developers.google.com/google-ads/api/fields/v24/ad_group_ad_asset_view)
- [AssetGroupAsset v24 fields](https://developers.google.com/google-ads/api/fields/v24/asset_group_asset)
- [Google Ads API release notes](https://developers.google.com/google-ads/api/docs/release-notes)
