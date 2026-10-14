# Changelog

## 2.0.1 - 2026-10-14

- App 创意变更明确使用新建与绑定，不原地更新旧广告。
- 演示模板明确区分 ENABLED App Ad 与 PAUSED Campaign/Ad Group，要求确认和实时回验。
- 复用已验证模板参数，只收集名称、排期和预算，不复用新建层级的旧资源 ID。

## 2.0.0 - 2026-09-08

- 重写为基于 Customer/Campaign/Ad Group/AssetGroup 的专家 SOP。
- 增加广告类型、出价依赖、GAQL 报表、Experiment、回查和故障恢复规则。
- 移除凭证/直接 SDK 执行示例，明确 Skill 与 Tool Source/Tool 的边界。
