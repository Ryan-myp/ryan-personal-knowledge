# 三渠道目标覆盖与创建合同升级（2026-10-29）

## 本轮改动

- Meta：增加 Awareness 图片/视频链接广告的 Campaign → Ad Set → Ad 蓝图、Tool 和起步模板；覆盖 REACH、IMPRESSIONS 优化。六大 ODAX 目标均有对应入口。旧目标在 Meta client 边界规范化；消息获客使用 Engagement，兼容旧模板的 OUTCOME_MESSAGES。
- TikTok：Lead 纳入支持范围，使用 Upgraded Smart+ 三步创建；原生表单与网站表单分别校验。网站表单使用 EXTERNAL_WEBSITE、CONVERT、Pixel、转化事件和落地页，不强制 Instant Page。补充独立 WEB_CONVERSIONS 向导及起步模板。Lead 不再同时进入旧 Campaign/Ad Group/Ad 创建链路。
- Google：传统 Video、Smart 新建受到平台限制，live 在任何预算写入前拒绝；草稿和蓝图明确说明限制及 Demand Gen / Performance Max 替代入口。已有资源查询保持可用。Local Services PMax 的 v26 能力尚未接入当前 v24 连接器。
- 通用蓝图目录默认只列同 ID 的最新语义版本；显式版本查询和历史模板仍能读取旧版本。Lead 2.0.2、Messaging 1.0.0 文件保留，新增 2.1.0、1.1.0。
- 目标审计从 Provider Tool schema 的 creation_selector 元数据枚举出发，逐项要求蓝图或明确限制，避免仅检查已存在的格式目录。没有修改中心 Parser/Router 的业务分支。

## 支持口径

| 渠道 | 本轮补齐 | 仍然需要区分的边界 |
| --- | --- | --- |
| Meta | Awareness；ODAX 旧目标兼容；消息目标规范化 | 各目标下的所有版位、优化目标、素材组合并未全部实测；Awareness 当前向导为链接图片/视频及 REACH、IMPRESSIONS |
| TikTok | Lead 原生表单/网站表单；WEB_CONVERSIONS；选择链路与出价预校验 | Lead 消息、电话、多承接位置、搜索及行业专用变体没有完整合同；TopView、Brand Takeover 仍未集成；WEB_CONVERSIONS 新向导当前覆盖 CONVERT |
| Google | Video/Smart 平台限制前置；Local Services 版本边界 | Local、Hotel、Travel 等专用类型仍有账户、Feed、资产资格依赖；不能将合同存在等同于已真实创建成功 |

目标枚举审计统计包含兼容别名，不代表独立广告类型数量。离线合同状态不会覆盖或提升原有真实 API 验证账本。

## 执行、迁移与恢复

默认 dry_run；真实写操作继续经过现有 principal、账号范围、权限、live 开关、确认、幂等和审计。
父级已创建后子级失败，继续使用原有资源 ID 恢复，不自动重建整条链或宣称外部写入已回滚。
Lead 缺失 Pixel、事件、目的地或自定义出价会在 schema/client 边界给出具体错误。
未执行渠道 API 请求，也未调整真实广告资源。测试中的 live=True 只连接本地替换的 transport。
没有数据库 schema 迁移，没有覆盖用户模板或更换数据库。内置 Skill 版本单独递增，说明内容使用中文，API 字段和 Account/Campaign/Ad Set 等术语保留。
回滚时应保留新增蓝图文件，避免本轮新保存的模板引用失效；无需回滚数据库结构。后续可将目标覆盖结果接入现有审计/监控，不新增观察性底座。

## 官方依据

- [Google Video Campaign API 边界](https://developers.google.com/google-ads/api/docs/video/overview)：传统 Video Campaign 新建限制；不能据此禁掉所有 VideoResponsiveAdInfo 操作。
- [Google Smart Campaign 创建说明](https://developers.google.com/google-ads/api/docs/smart-campaigns/create-campaign)：2026-09-23 停止新建。
- [Google Local Services Campaign](https://developers.google.com/google-ads/api/docs/campaigns/local-service-campaigns)：v26 PMax Local Services 能力。
- [Meta 官方 Campaign SDK](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/campaign.py)：当前 ODAX 目标。
- [TikTok Upgraded Smart+ 网站 Lead 示例](https://business-api.tiktok.com/portal/docs/create-an-upgraded-smart-lead-generation-campaign-with-location-as-website/v1.3)：网站表单的 Ad Group 与 Ad 参数。

验证结果见同日 evidence 文件。全仓 QGuard 仍包含历史质量债务，不能把功能测试通过写成质量门禁全部通过。

## 最终验证

- `make ad-agent-check` 通过：3332 个 Python 测试、编译、能力与知识审计、检索检查及 diff 检查。
- 前端 Node 测试 213 个通过；新建入口和全部管理页离线浏览器检查无脚本错误。
- 使用原 LaunchAgent、配置与数据库重启，监听 `0.0.0.0:8766`；原有 14 份用户模板按 ID 核对保留。
- QGuard 全仓：769 文件、4997 个告警、0 分，门禁未通过，未更改检查阈值。
