---
schema_version: "1"
id: provider-live-e2e-memory
title: 广告测试账号 Live E2E 长期记忆
layer: experience
wiki_type: concept
knowledge_type: test_account_e2e
platform: all
source: 仓库内 Live /chat 与 Provider 测试证据
source_ref: agents/tools/advertising/contracts/provider_live_e2e_memory.json
source_kind: code
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-26"
version: "1.1.0"
confidence: 1.0
updated_at: "2026-10-26"
tags: [e2e, test-account, templates, regression, live]
status: published
---

# 广告测试账号 Live E2E 长期记忆

本页是 Agent 在广告创建测试前应检索的操作记忆。它不是聊天历史，也不替代 Provider Tool schema。

检索词：测试账号、广告类型、内置模板参数、真实 API、Campaign、Ad Group、Ad、创建更新查询、live E2E、失败根因、故障恢复、HTTP 502、不重复创建。

## 记忆分层

- 内置模板 `agents/applications/advertising/contracts/builtin_creation_templates.json` 是可复用参数的唯一事实源。不要凭聊天记录重新猜素材、App、商品目录、定向或 CTA。
- `agents/tools/advertising/contracts/provider_live_e2e_memory.json` 固定当前范围、确认过的测试账号、每个广告类型的模板版本和参数 SHA-256、已有资源 ID/状态、逐层覆盖状态、证据引用、已知根因与恢复方式。模板改值后，旧 observation 只能通过显式 `historical_template_locks` 按蓝图版本、摘要和证据引用登记；新 observation 仍必须匹配当前模板摘要。
- `agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl` 是 E2E runner 自动追加的脱敏运行账本：每个 live `/chat` 阶段先记 pending，返回后记结果、实际创建的资源 ID、状态和错误摘要。它不保存 Prompt、完整 Tool 参数、原始响应、选择令牌或凭证。pending/ambiguous 记录必须先通过只读查询对账，不能重发 create。
- `agents/tests/advertising/test_provider_e2e_memory.py` 校验模板版本/参数快照与长期记忆一致。参数改变时必须先完成对应真实测试，再显式更新摘要和哈希。
- `scripts/advertising/provider_live_e2e_memory.py` 是 E2E runner 的可执行记忆读取器：服务启动时校验全部模板锁和测试账号；模板 live E2E 对照账户、蓝图和版本，并把资源历史、失败记录与恢复指导写入 case。每次模板 E2E 在任何 `/chat` 调用前，都会按 provider + 广告类型打印记忆预检：锁定参数摘要、已有资源 ID、适用根因和下一步动作。`build_live_e2e_memory_report()` 也可按渠道/模板读取同一份结构化记忆，并可选择输出模板参数原值。任何已知发生过 live 创建的模板默认不能再次创建整条层级；先查回并复用父级，只恢复缺失子级。明确要新建另一组暂停层级时，必须同时提供 `--allow-new-hierarchy --confirm-resource-readback`，后者表示操作者已逐项只读回查记忆中的资源；这两个开关都不能绕过 unresolved/ambiguous 写入、已知 Provider 阻塞或未解决根因的保护。
- `outputs/` 中的 case 文件与 Provider HTTP 记录是逐次实测证据，不应把它们的原始响应整体注入 Prompt。

只有测试账号上的真实 `/chat` 加 Provider 请求/回读可标记为 `live`。Dry-run、纯 Tool 单测和模型文字回复都不能升级 E2E 状态。

## 安全不变量

- 只使用仓库可信配置中的已确认测试账号；不能从请求体推导认证主体或扩大账户范围。
- 新建 Campaign 和 Ad Group 必须保持渠道对应的暂停值：Google/Meta 为 `PAUSED`，TikTok Smart+ 为 `DISABLE`，TikTok 旧版 App 模板的 `0` 是其声明的暂停值。
- Google Ads v24 的 App Ad 不接受 `PAUSED`。测试模板可将 App Ad 设为 `ENABLED`，但 Campaign 和 Ad Group 必须经实时回读确认仍为 `PAUSED`；不得启用父级或将 Ad 描述为暂停。
- 其他无法在 Provider 侧满足已确认安全状态的资源仍应记为 Provider 限制；不得隐瞒实际回读状态。
- 父级已成功创建、子级失败时，从已有父级继续失败步骤。先查询/对账，禁止为“重跑整条模板”重复创建 Campaign。
- `blocked_by_provider` 和账本中 `unresolved` 的已知根因会阻止全层级模板重跑；即使显式指定 `--allow-new-hierarchy` 也不能绕过。先按预检打印的处理建议恢复已有资源或采集缺失诊断。
- 查询/lookup 遇到 502 时只恢复 lookup；没有 Provider 写请求证据就不能声称子级已创建。
- 已有 live 测试资源 ID 必须从机器账本读取，名称更新/查询测试复用原层级；只有明确授权时才能创建另一组 paused hierarchy。
- 账本中的历史状态不能覆盖当前只读回验。若记录显示某旧层级曾为 `ENABLED`，先读取并判断是否可安全操作；不得把它当成当前暂停资源，也不得自动修改状态。

## 可复用恢复规则

- TikTok Smart+ Ad 使用新版 `creative_list` 结构，暂停状态在 Ad 顶层 `operation_status=DISABLE`。E2E Recorder 必须按 Smart+ 契约识别，不能用旧版 `creatives[]` 判断。修改 Recorder 后，必须重启加载它的隔离 E2E 服务。
- 只恢复一个子 Tool 时，`/chat` 不要附带 `creation_template_id` 或 `creation_blueprint_id/version`，否则 Runtime 会重新打开全层级创建表单。`platform_params` 按 Tool 名组织；已选原值与 `selection_tokens` 放在同一个 Tool 参数对象内。
- TikTok `identity/get` 或父级 lookup 返回 HTTP 502 时，不要重复创建已有 Campaign/Ad Group。待 lookup 正常返回后重新签发绑定当前 session、账户和 Tool 的选择凭证，再恢复单个失败子步骤。
- TikTok Smart+ 列表可能先从普通 `ad/get` 返回 Creative 形状的记录：若 `smart_plus_ad_id` 存在，它才是投放 Ad 的 ID；不同的 `ad_id` 是关联 Creative ID，列表中的 `operation_status` 也是 Creative 状态。客户端现在将 Ad ID 归一到 `smart_plus_ad_id`，把 Creative 信息分字段保留，并优先从 `smart_plus/ad/get` 读取 Smart+ Ad 当前名称/投放状态。选择器只能使用规范 Ad ID。Creative `ENABLE` 不代表 Ad 正在投放，暂停判定看 Smart+ Ad 自身 `operation_status=DISABLE`。
- TikTok Smart+ 更新时，名称/文案等内容更新只传用户要求改变的字段。用户说“保持暂停”描述的是不改变现状，不要把 `status=DISABLE` 混进 `updates`；只有用户明确要求状态变化时才单独调用状态更新 Tool。状态和内容不可在同一更新请求中混传。
- TikTok App Promotion 的 child-only 恢复必须从当前内置模板读取 App、Identity、素材和 tracking URL，并为当前 session 重新签发选择令牌；不能复制旧 case 的 `identity_id`。历史 Singapore identity Ad 保持暂停并作为失败证据保留，不覆盖 Indonesia 模板的验证结论。
- 如果 Ad 列表发生短暂 `ConnectionError`/502，先只重试读取，并用单 Ad `get` 对账；不要因读取失败重发创建或更新。若读取持续失败，准确报告未验证，保留现有资源 ID。
- Google Ads 测试账号 `9055507554` 的 Campaign `24366769615`、Ad Group `204899076647` 已实测为 `PAUSED`。v24 对该 App Ad 类型拒绝 `PAUSED` 状态，正确演示方式是只在两个暂停父级下创建 `ENABLED` App Ad；任何父级状态未知或启用时必须拒绝子级写入。先续用这组父级，不要重复创建。
- Meta App 历史模板记录过 `ValueError`，具体旧根因不可追溯；2026-10-26 当前模板参数已通过三层 dry-run 和回归，暂停 Campaign、Ad Set、Ad 经 child-only 恢复创建并回读。原生一键 live 模板仍未通过：Campaign 成功后重交整卡被重复写门禁挡住。只续建缺失子级，不把分层通过说成一键模板通过。
- 历史 TikTok App 测试中，省略 tracking URL 会被拒；通用 `example.com` URL 也因格式错误被拒。当前模板的 AppsFlyer click/impression 示例链接已由暂停演示的真实创建和回读验证为 API 可接受，但它们是合成占位值，不证明真实 MMP 归因或可投放性。App 视频创建还必须同时带模板图片和视频。

## 当前范围与状态

截至 2026-10-26，范围为 Google Ads PMax、Shopping、App；Meta Traffic、Catalog Sales、Conversion、App Promotion；TikTok Traffic、Product Sales、App Promotion。TikTok Lead Generation 按用户要求暂不测试。2026-10-26 验收细节见 `agents/docs/advertising/campaign-validation-20261026.md`，下述状态必须与结构化账本和当前 Provider 回读相互核对。

- Meta Traffic、Catalog Sales、Conversion：当前记录为真实 `/chat` 创建、更新和回读通过。
- Meta App Promotion：暂停 Campaign、Ad Set、Ad 已分层创建、改名和回读；Ad 配置状态为 `PAUSED`，但回读 `effective_status=IN_PROCESS`。原生一键 live 模板未完整通过，不能宣传为单次模板 E2E 已通过。
- Google PMax、Shopping：存在真实创建/更新/读取证据，但仍有未完成的当前模板覆盖或 Product Group 更新限制。
- Google App：模板已改为 Campaign/Ad Group `PAUSED`、App Ad `ENABLED`，并保留父级状态核验。2026-10-16 的后续 live 核验在只读 Campaign/Ad Group 查询阶段遇到 HTTP 401 后 403（`The caller does not have permission`），没有发出写请求；因此新模板的 ENABLED App Ad 创建与回读仍待测试账号权限恢复后完成。
- TikTok Traffic：本轮另建暂停层级 `1880079487888913` / `1880080345882434` / `1880080658604161`，Campaign、Ad Group、Ad 的创建、改名与回读通过；Smart+ Ad 的 `DISABLE` 不能从关联 Creative 的 `ENABLE` 推断。旧资源仍在账本，恢复时从机器记忆取当前 ID 并先查状态。
- TikTok Product Sales：本轮暂停 Campaign `1880083317565154` 与 Ad Group `1880083336090337` 已创建、改名、回读。Ad 先因 BC_AUTH_TT 帖子与身份不匹配被拒；换受控身份和完整追踪后 Provider 报 `Invalid product selection`，对应 Catalog 的 Product Set 只读列表为 0。Ad 未创建，不得把旧的“缺 Pixel”当作本轮唯一根因；待测试账号提供有效商品选择后，只恢复缺失 Ad，不写独立 Catalog。
- TikTok App Promotion：本轮暂停 Campaign `1880085399156082`、Ad Group `1880085378463186`、Ad `1880085435261650` 创建并回读；Campaign / Ad Group 改名与 Ad 状态更新已核验，Ad 名称更新不受支持，不能计入已通过。合成 tracking URL 只用于暂停演示，真实 MMP 归因和启用投放未验证。

三个渠道的删除 Tool 仍未开启 live，本轮均未测试删除；不能宣称完整 CRUD。Google 测试账户读取遇到 `CUSTOMER_NOT_ENABLED`，本轮未对 Google 执行写入。Meta Catalog Sales 的 Ad 首次遇到上游限流，先核查列表为空再只续建 Ad；Meta App 创建超时先对账确认无写入再重试。所有这些记录都不能代替原始只读回验和当前账户权限检查。

具体逐层状态、模板版本、参数哈希、已知资源 ID 和证据锚点以机器账本及其追加观察为准。不得把 `partial_live`、`blocked_by_provider` 或 `not_run` 简写成“已打通”。历史资源若缺少 ID 或实际状态，先用查询 Tool 对账；不能通过重新创建来“验证”。
