---
schema_version: "1"
id: meta-permissions-versioning-and-errors
title: Meta Marketing API 权限、版本与失败恢复手册
layer: platform
knowledge_type: error_pattern
category: diagnostics
subcategory: permissions-versioning-and-errors
platform: meta
source: Meta Marketing API 官方文档
source_ref: https://developers.facebook.com/docs/graph-api/overview
version: "1.0.0"
confidence: 0.92
updated_at: "2026-09-08"
tags: [meta, marketing-api, permissions, versioning, rate-limit, recovery]
status: published
---

# Meta Marketing API 权限、版本与失败恢复手册

Meta 的节点、边和字段请求必须同时满足应用权限、广告账户角色、资产关联和当前 Graph API 版本。能够读取 Ad Account 不代表能够读取 Page、Instagram、Pixel、Catalog 或受众；能够读取也不代表允许写入。

## 请求前的四层校验

1. **身份层**：确认可信 principal 对应的租户、用户和账户范围，不使用请求体中的用户字段替代身份。
2. **权限层**：按动作区分读取 Insights、读取素材、修改预算、发布广告和管理受众所需权限。
3. **资产层**：确认 Page、Instagram、Pixel、Catalog、商品集与广告账户的关联关系和状态。
4. **版本层**：固定 Graph API 版本，检查字段、边、Insights breakdown 和归因设置是否仍可用。

## 分页、字段与 Insights

列表接口必须消费 cursor，设置 page size、最大页数和总返回上限。字段只取当前决策所需内容，避免把大对象、素材二进制和无关扩展字段送入上下文。Insights 请求要一起记录 level、fields、breakdowns、日期窗口和归因设置；同一指标在不同 level 或 breakdown 下不能直接相加。

## 失败处理

| 信号 | 判断 | 恢复方式 |
|---|---|---|
| 权限或资产不可用 | 继续请求不会改变授权 | 停止并指出缺失的账户/资产范围 |
| 字段、参数或策略错误 | 请求契约不满足 | 修正输入后重新生成计划 |
| 频率或服务暂时异常 | 可能稍后成功 | 有界退避，限制并发与页数 |
| 写入超时 | 结果未知 | 读取线上对象和状态后再恢复 |
| 部分成功 | 一批对象状态不同 | 按对象 readback，未完成项逐项处理 |

不要把删除当作通用回滚；已交付广告优先暂停或下线，并保留审计摘要。预算、优化事件和素材替换都要记录变更前后值，避免旧快照覆盖线上新变更。

## 版本升级回归

升级前用测试账户验证 Campaign、Ad Set、Ad、Creative、Insights 和事件读取五类路径。特别检查目标与优化事件兼容性、特殊广告类别、受众限制、actions 指标结构和日期/时区口径。升级后在报告中显式标注 API 版本、读取时间和归因设置。

## 官方参考

- [Graph API overview](https://developers.facebook.com/docs/graph-api/overview)
- [Graph API versioning](https://developers.facebook.com/docs/graph-api/versioning)
- [Marketing API](https://developers.facebook.com/docs/marketing-api)
