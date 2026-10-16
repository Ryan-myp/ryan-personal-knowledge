# Changelog

## 2.0.3 - 2026-10-16

- Google App 模板固定 Campaign/Ad Group 为 PAUSED、App Ad 为 ENABLED；父级暂停是阻断投放的安全边界。
- 明确 v24 拒绝 PAUSED App Ad，不再把该 Provider 限制误报成完整创建阻塞。

## 2.0.2 - 2026-10-16

- 记录测试账号 App Campaign 的全层级暂停限制及 Provider 拒绝证据。
- 明确历史 ENABLED App Ad 不能作为全层级暂停创建通过案例。
- 加入测试账号 E2E 长期记忆的检索、续跑和证据更新流程。

## 2.0.1 - 2026-10-14

- App 创意变更明确使用新建与绑定，不原地更新旧广告。
- 演示模板明确区分 ENABLED App Ad 与 PAUSED Campaign/Ad Group，要求确认和实时回验。
- 复用已验证模板参数，只收集名称、排期和预算，不复用新建层级的旧资源 ID。

## 2.0.0 - 2026-09-08

- 重写为基于 Customer/Campaign/Ad Group/AssetGroup 的专家 SOP。
- 增加广告类型、出价依赖、GAQL 报表、Experiment、回查和故障恢复规则。
- 移除凭证/直接 SDK 执行示例，明确 Skill 与 Tool Source/Tool 的边界。
