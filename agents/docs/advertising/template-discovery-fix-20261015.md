# 对话模板查询修复

日期：2026-10-15。

## 根因

模板存储和 `/creation-templates` 已有数据，但普通自然语言对话缺少可调用的模板目录 Tool。
前期创建测试通过请求直接指定模板 ID，验证了“已选模板后的执行”，没有验证“从对话发现模板”。
因此模型会改查 Campaign、预算，并重复索要模板里已有的 Merchant ID。

## 实现

- 为有持久化模板服务和创建蓝图的已注册渠道，组装两个本地只读 Tool：模板列表、模板详情/草稿预览。
- Tool 契约位于 `agents/tools/advertising/creation_templates.py`，不持有 Provider client 或凭证。
- 创建模块绑定已有模板服务；集成注册模块只消费此接口，按现有 PluginManifest 和 Tool Source 生命周期注册。
- 名称按 namespace 生成，例如 `google_ads_list_creation_templates`、`google_ads_get_creation_template`。没有在 Harness 或中心 Parser 中添加渠道/模板分支。
- 从可信请求向执行上下文传递租户和账户授权范围。模板过滤复用 API 的同一服务，不从 Tool 参数获取用户身份。
- 列表明确标注 `data_status=local`，不是外部广告 API 的查询证据。预览不创建、不更新广告。
- 用户选择模板后返回现有创建卡片，保留名称、预算和日期。覆盖值必须属于蓝图字段，不能携带凭证或可执行配置。
- 修正应用权限门禁：显式 principal 缺少的 Tool 权限，不能由服务端默认权限补足。未授权用户不能读取模板。
- 注册失败只清理本轮新增插件；重复注册不能误删原有模板插件。卸载渠道时同步移除其模板 Tools。

## 真实验证

本地证据：`outputs/template-discovery-e2e-20261015/`。

| 场景 | 结果 |
| --- | --- |
| Google 测试账号 `9055507554`，全新对话只问“有模板吗” | 调用本地模板 Tool，返回 PMax、Shopping、App 三种模板 |
| Meta 测试账号 `2806375919473667`，查询内置模板 | 本地 Tool 返回四个匹配模板，不调用 Campaign / Budget 等无关 API |
| TikTok 测试账号 `7397068114548195329`，查询流量模板 | 返回一个匹配模板；不代表 App 或 Sales 的广告创建也已通过 |
| Google 多轮对话：创建意图、名称/时间/预算、有模板吗、选择 Shopping | 查询并预览成功，返回创建草稿卡片 |
| 浏览器重新打开该对话，再打开创建工作区 | 模板与预填卡片可恢复并正确显示 |

Shopping 草稿实际保留：

- 名称：`ai-test1`。
- 日预算：`20`。
- 开始 / 结束日期：`2026-10-18` / `2026-10-20`。
- Merchant ID：`115791065`，`user_required=false`，不再要求用户重复填写。
- 没有外部广告写入，本轮也没有把 dry-run 结果计为广告创建成功。

首轮完整对话记录为 `qa-template-discovery-864a4946.json`。
三渠道独立查询分别为 `qa-template-catalog-google-ads-f924fa8c.json`、
`qa-template-catalog-meta-fcfb670e.json`、`qa-template-catalog-tiktok-587a109d.json`。
重复测试 `qa-template-discovery-058744c3.json` 的最后一步曾遇到模型限流，
平台返回明确的 `RateLimitError`；随后同会话重试成功，见 `qa-template-discovery-058744c3-recovery.json`。
保留失败记录，不将模型限流误报为“没有模板”，也不将失败尝试算作通过。

## 验收与边界

回归涵盖闭合 schema、账户/用户/租户隔离、无权限拒绝、字段归属、预填值、
真实 Run 门禁、重复注册与插件卸载。新增两个模块的定向行覆盖率采样为 90%，不代表全项目覆盖率。
`make ad-agent-check` 通过：编译、1796 项全量 Agent 测试、能力审计、310 个 Tool
的契约快照与差异检查。最终定向回归 44 项通过。
`8765` 已重启；重启后再次进行三渠道真实模型查询，均通过。
最新证据为 `qa-template-catalog-google-ads-53095f3f.json`、
`qa-template-catalog-meta-b8230e04.json`、`qa-template-catalog-tiktok-3bd43c07.json`。
仓库 qguard 仍为 0 分且未通过，未将本次功能修复描述为整体质量门禁达标。

无需数据库迁移，不改写已有模板和聊天记录。回退需同时回退 Tool Source、应用绑定、
权限修改、场景提示和契约快照，重启进程以恢复一致的注册表；不需要清理任何外部广告资源。
