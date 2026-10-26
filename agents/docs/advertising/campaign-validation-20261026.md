# Campaign 层级受控验证记录

本轮只允许已确认的 Google Ads、Meta、TikTok 测试账号。写入范围仅限
Campaign、Ad Group/Ad Set、Ad 及直接属于 Campaign 层级的 Asset Group、
Listing Group Filter、Product Group；Creative、预算实体、Pixel、Catalog、
受众等独立资源最多只读。TikTok Lead 仍不在本轮类型范围内。

## 证据口径

- 原始会话与 Provider HTTP 事件保存在 ignored 的
  `outputs/campaign-scope-20261026/`，未加入 Git。
- `scripts/advertising/campaign_e2e_report.py` 要求受控账号、同一 case 的
  真实 HTTP 事件、成功 Tool 结果、`data_status=live` 与 Run ID 同时存在，
  才把**只读**调用标为 `read_verified`。生成的脱敏报告为
  `agents/evals/advertising/evidence/campaign-read-20261026.json`；
  原始诊断副本保存在 ignored 的 `outputs/campaign-scope-20261026/diagnostic.json`。
- 旧的模板记忆只显示 `historical_state`，不等于当前模板全链路通过。
  写操作必须独立核对资源归属、前后状态、子级回读与 Run/Turn 证据，
  本报告不会根据模型回复自动提升其状态。
- 发布门禁仍读取旧版 `provider_e2e_evidence.json` 与
  `provider_query_e2e_evidence.json`，因此本轮诊断不能代替发布验收。

## 2026-10-26 实测

| 渠道 | Campaign 列表 | 单 Campaign | 下层列表 | 写操作 |
| --- | --- | --- | --- | --- |
| Google Ads | Provider `403 CUSTOMER_NOT_ENABLED`，未通过 | 未尝试 | 未尝试 | 未尝试 |
| Meta | 通过，20 条 | 通过，历史测试 Campaign | Ad Set 1 条、Ad 1 条 | 未尝试 |
| TikTok | 通过，20 条 | 通过，历史测试 Campaign | Ad Group 1 条、Ad 1 条 | 未尝试 |

以上 8 条成功读取均由 Tool 结果与匹配的 HTTP 事件证明，只有 Meta/TikTok
的 Traffic 已有父子层级本轮回读；不能据此推断其他广告类型、分页完整性或
创建/更新/删除成功。Google 先前的第一次查询还暴露了测试记录器把 GAQL
`googleAds:search` 的 POST 错判为写入；已在测试服务修复并回归，
重测到达 Provider 后得到上述明确 403。没有为该账号重试写入。

## 同日 Meta / TikTok Live 验收续测

本次续测只使用 Meta `2806375919473667`、TikTok
`7397068114548195329`；Google 未写入，TikTok Lead 未测试。
原始请求、Tool 结果、Run ID 和 Provider 事件位于 ignored 的
`outputs/campaign-acceptance-20261026-b/`。本节只记录本轮实际结果，
不以模型回复或 dry-run 代替 Provider 写入与独立回读。

| 类型 | 创建 Campaign / 下层 / Ad | 更新并回读 | 结论 |
| --- | --- | --- | --- |
| Meta Traffic | `120252061614330251` / `120252061617130251` / `120252061618390251`；三层 PAUSED 且各自 live 回读 | 三层名称更新并回读 PAUSED | 创建、更新、查询逐层通过 |
| Meta Catalog Sales | `120252061670350251` / `120252061674610251` / `120252061702870251`；Ad 首次遇 Meta throttle，核对列表为空后只恢复 Ad；三层 PAUSED 回读 | 三层名称更新并独立回读 PAUSED | 创建、更新、查询逐层通过；Ad `effective_status=IN_PROCESS` |
| Meta Conversion | `120252062074900251` / `120252062075220251` / `120252062075890251`；三层 PAUSED 回读 | 三层名称更新并独立回读 PAUSED | 创建、更新、查询逐层通过 |
| Meta App Promotion | `120252062235750251` / `120252062284440251` / `120252062288410251`；模板 dry-run 通过；live 创建 Campaign 后子级逐层续做并回读 | 三层名称更新并独立回读 PAUSED | 分层创建、更新、查询通过；原生一键 live 模板链仍未通过，Ad `effective_status=IN_PROCESS` |
| TikTok Traffic | `1880079487888913` / `1880080345882434` / `1880080658604161`；三层 DISABLE 回读 | 三层名称更新并回读 DISABLE | 创建、更新、查询逐层通过 |
| TikTok Product Sales | `1880083317565154` / `1880083336090337` 已创建并回读 DISABLE；Ad 未创建。BC_AUTH_TT 素材/身份不匹配；CUSTOMIZED_USER 配完整追踪后 Provider 报 `Invalid product selection`，Catalog 商品集为 0 | Campaign、Ad Group 改名回读 DISABLE；Ad 无法更新 | 父级创建、更新、查询通过；Ad 被测试账号商品前置资源阻塞 |
| TikTok App Promotion | `1880085399156082` / `1880085378463186` / `1880085435261650`；三层创建并回读 DISABLE | Campaign、Ad Group 改名回读；Ad 状态更新为 DISABLE 并回读（不支持名称更新） | 创建、查询及支持的更新字段通过 |

旧版历史层级已单独读回 Meta Traffic、Meta Catalog Sales 的三层，
TikTok Product Sales 旧父 Campaign（下层列表为空）及 TikTok App
Promotion 的 Campaign / Ad Group。旧 Product Sales 父 Campaign 是
Website/Web Conversions，而当前模板是 App/Catalog，不可混用父级。
此次新建资源保留暂停，用于回读和失败恢复；未启用任何层级。
Meta App 与 Catalog Sales 的 Ad 虽配置 `PAUSED`，Provider 回读的
`effective_status` 为 `IN_PROCESS`，不能说实际状态已暂停。
TikTok 对外 Product Sales 在当前 Smart+ 适配器的 Provider 请求目标为
`WEB_CONVERSIONS`；本报告分别保留业务目标和请求值。

验收过程中发现并修复的代码问题：

- E2E 请求把冗长否定句混入 `user_input`，干扰工具选择；现在用户意图原样传递，
  账户、Tool 范围及写权限仍由服务端结构化门禁控制。
- 验收脚本误把选择凭证放在 `campaign_id`；现在 live 请求会拒绝资源字段中的
  `ps1...`，原始 ID 与 `selection_tokens` 分别提交。
- TikTok Smart+ 的 `request_id` 必须为十进制 int64；三个创建 Tool 收紧
  schema，客户端在请求 Provider 前校验。显式单视频创意只有一项且未填封面时，
  可复用同请求的顶层 `image_web_uris`；显式封面仍优先。
- Meta Campaign / Ad Set / Ad 详情字段在 Provider 契约中限定有效集合，
  客户端拒绝无效字段，避免模型臆造 `is_active`、`adset_name`、
  `promoted_object` 后让 Graph API 报 400。Meta Campaign 的选择目录
  在提供精确 ID 时走账号归属核验加单对象读取，未提供 ID 时仍可列表浏览。
  单对象 GET 后来仍遇 504，说明上游故障未被本地优化完全消除。
- Meta App 的首个本轮 live 模板请求在 LLM Tool-call 生成阶段超时 500 秒，
  Provider 无对应写事件；验收脚本的空资源默认值类型错误又漏记了
  `ambiguous`。修复后停止旧隔离请求，以精确名称查询（Provider GET 200、
  无对应 Campaign）完成对账，记录 `no_write` 事件后才重试。
- 第二次 Meta App 的 Campaign 创建成功，验收驱动又提交整张创建卡，
  被重复写门禁挡住。现在任何一层真实创建成功后立即停止整卡重放，
  本轮只续建缺失的 Ad Set、Ad。原生一键 live 模板链仍需单独验证。
- TikTok Product Sales 更换为经账户查询的 CUSTOMIZED_USER 并补齐只读
  核验的追踪 App 与暂停测试 URL 后，Provider 返回
  `Invalid product selection`；同一 Catalog 当前没有 Product Set。
  模型错误声称没有 `tiktok_list_apps`，实际已成功调用该工具；
  `ui_hidden` 的系统字段现在不会展示给模型编造 `request_id`。

未闭环的真实问题：TikTok Product Sales 需要测试账号提供有效的 Product
Set/商品选择，本轮不越权创建独立 Catalog 资源；Meta App 原生一键 live
模板链仍未完整通过。TikTok App Ad 只支持状态更新，不算改名已验证。
三渠道删除 Tool 的 `live_support` 仍为 false，本轮没有绕过权限直接删资源，
不能宣称完整 CRUD。模型回复曾把仅查询到的 Ad
推断成父 Ad Group `ENABLE`，独立 Ad Group 回读实际为 `DISABLE`；
验收一律取结构化 Provider 数据，回复准确性仍需专门回归。

## 写操作边界与下一步

受控 E2E 服务的 live Tool 白名单已限制为 Campaign 层级。
传输记录器拒绝独立 Creative、CTA Portfolio、上传、Pixel 等非层级写入，
未知 TikTok POST 默认拒绝；Meta/TikTok 更新与删除要求本隔离实例记录的
账号、资源类型、ID 归属。旧版仅记录扁平 ID 的文件不再授予这两个渠道
的写权限，需由同一隔离实例新建资源建立类型化账本。
Google 删除还要求完整 customer resource name 匹配。
Google `googleAds:search` 的 POST 只接受查询形态；`ads:mutate` 仅放行
属于本次测试 Ad Group Ad 的 Ad 内容更新，更新的 resource name 必须与
URL 中账号和资源类型一致。
默认部署继续 `dry_run`、`allow_live_writes=false`。

三个渠道的删除 Tool 当前均为 `live_support=false`。不能通过脚本绕过此
契约直接调用 Provider；真实删除仍是**未验证**。后续需先将“本次 Run
新建资源的类型化归属证明”下沉到 Tool 权限门禁，支持独立确认、幂等、
未知效果恢复和删除后回读，再只清理本次测试创建的暂停层级。

下一次受控写入按渠道、按广告类型进行：

1. 先恢复 Google 测试账号可访问性，逐层只读核对账本现有资源；
   不在 `CUSTOMER_NOT_ENABLED` 状态下试写。
2. Meta/TikTok 先对账本已有父子资源做只读核对，解决既有模板缺口，
   不重复创建完整 Campaign。确需新建时，以锁定模板、唯一名称、暂停状态、
   明确确认和持久化 observation 执行。
3. 每次创建后立刻按 ID 回读，更新仅针对本次测试创建的资源；未明结果
   先查后恢复，不能盲重试。独立的非 Campaign API 只做查询验证。

早期只读诊断结束已停止隔离的 `127.0.0.1:8893` 实例；续测隔离
`127.0.0.1:8895` 在本轮完成后停止。未改动 `0.0.0.0:8766` 服务或
既有非本轮测试资源。

## 对话质量与门禁

真实模型、离线 Provider 的 15 条对话回归跑了两轮，均为 14/15。
第一次流程图请求超出 Tool 次数上限，第二次模糊创建请求超出上限；
聚焦复测均通过，说明重复调用仍存在波动。脱敏汇总见
`agents/evals/advertising/evidence/conversation-quality-20261026.json`。
评测 CLI 已复用模型 adapter，并在后续报告中记录有界 Tool 名称和调用数，
但尚未用新格式重新跑完整模型套件；不能宣称质量门禁通过。
该套件不是独立盲测，也不能代替真实 Provider 写入验证。
