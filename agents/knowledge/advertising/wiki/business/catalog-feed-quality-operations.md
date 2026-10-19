---
schema_version: "1"
id: catalog-feed-quality-operations
title: 商品目录与广告 Feed 质量运营
layer: business
knowledge_type: workflow
category: industry_playbooks
subcategory: catalog-feed-quality-operations
platform: all
source: 跨平台商品目录和 Feed 运营方法论
source_ref: "internal://ad-agent/playbook/catalog-feed-quality-operations"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-10-19"
tags: [catalog, product-feed, ecommerce, merchant-center, product-set, listing-group, inventory, diagnostics]
status: published
wiki_type: concept
source_kind: internal
authority: operator
evidence_level: provisional
last_verified_at: "2026-10-19"
---

# 商品目录与广告 Feed 质量运营

商品目录不是一次性上传的附件，而是连接商品源、平台审核/资格、广告结构、素材与购买事件的持续数据产品。广告出现“商品少、投放不稳或点击后不成交”时，应先确定问题在源数据、平台摄取、商品资格、广告选择还是站外购买链路，不先把所有问题归给出价。

## 统一商品身份

业务侧为商品和变体维护稳定主键，并明确父商品、颜色/尺寸等变体、市场、语言和币种。各平台可有自己的目录 ID、商品 ID、商品集或 listing 分组；这些标识不能假设相同，也不能因改标题或图片而随意改变身份。保存一张有访问控制的映射表，将业务商品键关联到各平台 ID 和最近一次同步状态。

## Feed 数据质量契约

| 字段/关系 | 运营检查 |
|---|---|
| ID 与变体 | 稳定、唯一、父子关系一致；落地页对应正确变体 |
| 标题与描述 | 描述真实商品、规格和主要差异；避免关键词堆砌或与页面冲突 |
| 图片/视频 | 资源可访问、对应当前商品、无错误价格或不允许的宣传 |
| 价格与促销 | Feed、落地页、结账币种/数值及促销窗口一致 |
| 库存与可售状态 | 缺货、预售、地区可售和配送限制及时同步 |
| 品牌/类别/属性 | 分类与产品事实一致，必要属性完整，不凭空填造 |
| URL 与市场 | 地区、语言、库存、价格、重定向和深链正确 |
| 更新鲜度 | 记录源更新时间、同步时间、摄取结果、错误和重试状态 |
| 业务价值 | 维护毛利、退款、履约、新客价值等内部维度，不把这些私有口径冒充平台属性 |

合规性和必填字段依具体渠道、商品类别、地区及广告格式而变。以上是数据治理检查表，不是所有平台通用的 API 字段清单；具体属性与枚举必须按当前官方文档、Feed 诊断和 Tool schema 确认。

## 商品状态链路

```text
业务商品源
  -> 标准化和校验
  -> 渠道映射/同步
  -> 平台摄取与商品级诊断
  -> 可投资格与广告中的商品选择
  -> 点击到商品页/加购/购买
  -> 订单、退款、毛利和库存复盘
```

每一环保留计数和失败原因：源商品总量、适用商品量、字段校验通过量、渠道成功摄取量、可投商品量、被广告实际选中的商品量，以及最终有效订单量。只有总数没有阶段性分母，无法判断损失发生在哪里。

## 诊断路径

| 现象 | 排查顺序 |
|---|---|
| 源有商品、平台目录没有 | 同步作业、权限、区域/语言映射、平台摄取错误、分页或延迟 |
| 目录有商品、广告不可选 | 商品审核/资格、目标市场、目录归属、商品集/Listing 约束、当前广告格式 |
| 可投商品骤减 | 源同步差异、缺货/价格变化、批量拒绝、地区或政策变化 |
| 商品广告点击低 | 搜索/受众意图、商品图片、价格竞争力、标题/商品类别相关性 |
| 点击正常、商品页转化低 | URL/变体、页面价格库存、速度、配送、信任和结账 |
| 报表有购买但利润差 | 新老客、折扣、退款、毛利、履约和商品组合 |
| 平台数和订单系统不一致 | 日期/时区、币种、重复订单、归因窗口、取消退款、延迟回补 |

排障先按商品 ID 或稳定业务键抽样追踪端到端记录。平台只返回聚合错误时，不应猜测具体商品原因；应读取平台诊断或导出当前允许的商品级错误，再决定修复源、映射、审核还是广告选择。

## 广告结构与商品分层

按商品、毛利、库存、市场、季节和业务目标分组，只有当分组能产生不同预算、创意、目标或决策时才拆成独立投放单元。过度拆分会造成样本与预算稀释；不分层则可能让高流量低毛利商品掩盖高价值商品。

Google Shopping/PMax、Meta Catalog、TikTok Product Sales 和 DV360 商品相关方案对目录对象、身份、模板、商品选择、素材与报告的定义不同。跨平台策略层可共享业务分类和利润分层，但具体平台对象、ID、字段及更新限制必须分别核验，不能复用同一份 API payload。

## 上线与回滚检查

上线前至少确认：商品主键稳定；抽样商品页面与价格/库存一致；Feed 同步新鲜；商品资格和目标地区匹配；广告使用的目录与商品集合正确；追踪事件携带可对账的业务订单键；库存、履约和退款护栏明确。

大批量字段映射或目录规则修改应先抽样和分批发布，保留旧映射、快照与错误清单。发现大量商品拒绝或业务页面不一致时，暂停继续扩量，恢复已验证的映射或 Feed 版本，并重新读取平台状态；不要盲目重复创建目录或广告。

参考入口：

- [Google Merchant API product data](https://developers.google.com/merchant/api/guides/products/overview)
- [Google Ads Shopping campaigns](https://support.google.com/google-ads/answer/2454022)
- [Meta Marketing API catalogs](https://developers.facebook.com/docs/marketing-api/catalog/)
- [TikTok Business documentation](https://business-api.tiktok.com/portal/docs)

平台文档和可用字段会变化；参考入口用于找到最新定义，当前账户诊断与 Tool schema 才能确认实际能力。
