---
schema_version: "1"
id: dv360-api-operations-and-reporting
title: DV360 API 采购资源、定向分配与报表生命周期
layer: platform
knowledge_type: workflow
category: platform_foundation
subcategory: api-operations-and-reporting
platform: dv360
source: Display & Video 360 API 官方文档
source_ref: https://developers.google.com/display-video/api
version: "1.0.0"
confidence: 0.91
updated_at: "2026-09-08"
tags: [dv360, api, advertiser, insertion-order, line-item, reporting, targeting]
status: published
---

# DV360 API 采购资源、定向分配与报表生命周期

DV360 是程序化采购资源管理系统，核心对象不是单一 Campaign，而是 Partner、Advertiser、Insertion Order、Line Item、Creative、Targeting Assignment 和 Report。对象层级与预算、排期、定向、频控、品牌安全和素材审批共同决定实际交付。

## 资源层级与责任

| 层级 | 主要职责 | 诊断重点 |
|---|---|---|
| Partner | 组织与合作方范围 | 访问边界、账户权限 |
| Advertiser | 广告主、品牌与默认设置 | 货币、时区、默认品牌安全 |
| Insertion Order | 预算、目标和投放周期 | 预算分配、flight、目标 |
| Line Item | 采购策略与交付单元 | 出价、定向、频控、库存 |
| Creative | 可交付素材与审批 | 尺寸、格式、审核、关联 |
| Targeting Assignment | 版位、受众、地域等分配 | 继承、覆盖、冲突 |

创建或更新时必须从可信 principal/configuration 获得 partner、advertiser 和账户范围。用户输入中的 ID 只作为候选值校验，不是身份认证依据。

## 采购与 Line Item 工作流

1. 确认 advertiser 的币种、时区、品牌安全和默认库存规则。
2. 创建或读取 Insertion Order，设置预算、日期、目标和 flight 结构。
3. 创建 Line Item，选择类型、预算、出价、频控、排期和库存策略。
4. 分配定向条件，分别校验受众、地域、设备、环境、版位、内容分类和品牌安全。
5. 关联 Creative，确认审批和尺寸/格式与 Line Item 兼容。
6. 执行 preflight：父子状态、日期、预算、目标、定向、素材和报告口径全部通过后再启用。

预算不能只看 IO 总预算。要同时检查 flight 分配、Line Item pacing、日均预算、竞价可用性和库存规模，避免“预算存在但没有可交付库存”的假象。

## 定向分配与继承

DV360 定向通常通过 assignment 关联，生效值可能来自 Advertiser、IO、Line Item 或具体资源。更新前要区分新增、替换、删除和继承解除，不能把全量配置当成 patch。定向冲突时优先输出生效路径和被覆盖的规则，而不是只列出资源 ID。

品牌安全诊断应拆成：平台默认、Advertiser 默认、IO/Line Item 覆盖、库存来源和内容分类。频控则要区分用户、设备、Line Item 和跨媒体触达，跨层级频控不可用单个报表字段推断。

## 报表生命周期

DV360 报告通常包含配置、运行和读取三个阶段。报告请求可能是异步的，Agent 必须轮询状态、设置总超时和取消策略，读取完成文件或结果时限制大小并记录查询定义。

报表交付规范：

- 固定日期范围、时区、Partner/Advertiser 范围和费用口径。
- 将 impressions、clicks、conversions、media cost、billable cost、fees 和 revenue 分开标记。
- 维度越细，数据延迟、空值和重复汇总风险越高；先做小报告验证。
- 比较不同来源时，保留 platform、exchange、billing 和 attribution 定义。
- 报表为空时依次检查状态、日期、时区、过滤器、权限、数据延迟和是否存在可交付库存。

## 更新、删除与失败恢复

只更新明确允许变更的字段，并使用 API 要求的字段掩码或资源 patch 语义。已投放对象删除前先评估预算、报表、定向和创意依赖；通常暂停/下线比删除更适合运营恢复。错误处理要区分权限、父资源状态、字段校验、配额、异步任务超时和外部服务失败。

批量操作发生部分成功时，以重新读取的线上状态为准，记录已完成对象和待处理对象。重试必须有幂等键、最大次数和退避；不能因为本地任务结束就声称外部投放已回滚。

## 官方参考

- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [API structure](https://developers.google.com/display-video/api/concepts/structure)
- [Targeting](https://developers.google.com/display-video/api/concepts/targeting)
- [Reporting](https://developers.google.com/display-video/api/concepts/reporting)
- [Google Marketing Platform help](https://support.google.com/displayvideo/topic/6042460)
