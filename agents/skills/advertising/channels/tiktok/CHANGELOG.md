# 变更记录

## 2.1.0 - 2026-10-29

- 对齐目标覆盖与当前创建边界；区分离线合同、真实验证和平台限制。


## 2.0.2 - 2026-10-26

- 与测试账号结构化账本对齐：Product Sales 只通过暂停父级，Ad 被商品选择限制；App Promotion 的 Ad 名称更新不支持。
- 不再在 Skill 正文固定过时的恢复 ID；恢复前只读查询当前账本和真实状态。

## 2.0.0 - 2026-09-08

- 重写 TikTok Campaign/Ad Group/Ad 层级与目标、预算、排期、出价依赖。
- 增加 Spark、App、Lead、Commerce、Pixel/CAPI、报表和资产恢复 SOP。
- 移除凭证/直接 API 执行示例，明确动态 lookup 与 Tool schema 边界。
