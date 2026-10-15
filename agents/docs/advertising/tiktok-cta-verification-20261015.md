# TikTok CTA 修复与实测记录

日期：2026-10-15。范围仅为 TikTok CTA 与内置模板复用；App 推广本轮暂缓。

## 结论

- 测试账号仅使用 `7397068114548195329`。
- `tiktok.test.traffic` 已通过真实 `/chat` 模板创建、平台签名确认与独立查询回读；不是 mock 或仅有 HTTP 200。
- Campaign `1879077627470977`、Ad Group `1879077634040146`、Ad `1879077640812033` 均回读到 `operation_status=DISABLE`，Ad 的 `effective_status=PAUSED`。
- Ad 的 `ad_configuration.call_to_action_id` 回读为 `7696698198538112006`，与内置模板一致。
- TikTok 内部创意素材为 `material_operation_status=ENABLE`；Campaign、Ad Group、Ad 均暂停，不等同于素材单独也被暂停，更不代表广告投放已经启用。
- 此 Traffic 模板使用 Upgraded Smart+：Campaign 实际目标为 `WEB_CONVERSIONS`，广告组为 `CLICK` / `CPC`。没有将请求中的 Traffic 别名伪装成渠道实际目标值。
- Product Sales Ad 仍因帖子与身份不匹配而失败，只固化可回查的 CTA Portfolio，模板保留 `provider_limited`，不能宣称完整创建通过。

## 根因与修复

之前只发送 `LEARN_MORE` / `SHOP_NOW` 按钮枚举，该账户的实际组合未能创建。
成功路径为：推荐 CTA 资产 -> 使用同组 `asset_content` 与 `asset_ids` 创建 CTA Portfolio
-> 将返回 ID 放入 `ad_configuration.call_to_action_id`，不同时发送按钮枚举。

本次成功 Portfolio 的内容为 `Learn more`，资产 ID 为 `201781`、`201535`。
Traffic 与 Product Sales 模板当前复用这个 CTA，不将其描述为 `Shop now`。

实现边界：

- Provider 注册 `tiktok_recommend_ctas` 与有界 Portfolio list 只读 Tool。
- `tiktok_create_creative_portfolio` 默认 dry-run；live 仅支持经平台确认的非投放 CTA Portfolio。
- CTA 内容闭合校验，缺少文案或非空资产 ID 列表时在发请求前报错，不接受任意 JSON 或授权字段。
- Portfolio get 使用官方 GET/query 协议，修复旧 POST 调用。
- Smart+ CTA picker 通过账户范围内精确 get 获取新 selection token，不保存或硬编码授权 token。
- 蓝图支持 Portfolio ID；存在 ID 时不再要求按钮枚举，用户更换 CTA 时声明重置另一种选择。
- 同时提交 Portfolio 与按钮枚举时明确拒绝，不静默选择其中之一。
- TikTok 更新 Tool 从创建 schema 取字段时使用深拷贝，避免嵌套字段的 picker 元数据互相覆盖。
- 旧 Campaign 的 picker 按 ID 精确回查，不再受最近 20 个 Campaign 列表窗口影响。
- 通用 Harness / Run Kernel 未修改，外部写入仍经过既有权限、白名单、确认、幂等与审计链路。

## 真实证据

本地证据目录：`outputs/tiktok-template-e2e-20261014/`，未将整批运行产物提交源码。

| 证据文件（相对 `cases/`） | 验证内容 |
| --- | --- |
| `tiktok-cta-recommendations-landing-20261015.json` | LANDING_PAGE 推荐资产 |
| `tiktok-cta-recommendations-product-destination-20261015.json` | APP_DOWNLOAD 推荐资产 |
| `tiktok-cta-portfolio-create-recommended-20261015.json` | 经确认的真实 CTA Portfolio 创建 |
| `tiktok-cta-portfolio-readback-20261015.json` | Portfolio 内容与资产 ID 独立回读 |
| `tiktok-test-traffic-native-live-cb437eb7.json` | 模板完整对话，两轮含确认，三层创建均成功 |
| `tiktok-cta-native-campaign-readback-20261015.json` | Campaign 独立查询与暂停状态 |
| `tiktok-cta-native-adgroup-readback-20261015.json` | Ad Group 独立查询、父级、预算、时间、优化目标 |
| `tiktok-cta-native-ad-readback-20261015.json` | Ad 独立查询、CTA 绑定、创意引用与有效暂停状态 |
| `tiktok-sales-cta-probe-7696698198538112006.json` | Product Sales 的独立身份失败，不计为通过 |
| `tiktok-cta-portfolio-list-after-create-20261015.json` | 列表端点真实返回空，不伪造数据 |

`provider-http.jsonl` 包含对应脱敏 HTTP 方法、路径、业务返回码和 request ID。
新建模板对话只覆盖 Campaign 名称、开始时间、结束时间、总预算，其他创建参数来自内置模板。

列表限制：该账号 Portfolio list 返回空，但同一 Portfolio 的 get 与 Ad 绑定均成功。
模板因此使用精确 get，不依赖 list 能否枚举该 CTA；不能据空列表断言资产不存在，也不将列表标记为“已验证有结果”。

## 验收与恢复边界

回归覆盖默认 dry-run、非法 CTA 内容、查询上限、畸形推荐响应、GET 协议、
精确 Campaign 查询、账户内 CTA picker、蓝图条件必填及冲突 CTA 拒绝。

- `make ad-agent-check` 通过：编译、Tool 能力审计、302 个 Tool 的契约快照、1781 项 Agent 测试与差异检查。
- 定向回归 491 项通过。覆盖率采样中，所测 TikTok / update contracts 模块整体为 74%，并非全项目覆盖率。
- 同一采样与 `git diff --unified=0` 对照：所测 Provider 文件的可执行新增行覆盖 49/56，即 87.5%，不包含 JSON / 蓝图数据行，也不是分支覆盖率。
- 本地 `8765` 服务已重启并回读确认 Traffic 蓝图 `3.3.0`、模板 `live_verified`；精确 CTA picker 返回有效选项。保留 `dry_run` 和未开启的 live 开关。
- 隔离 live 测试服务 `8766` 已停止。

仓库整体 qguard 当前为 0 分且未通过，不能以本次功能实测替代该门禁或声称整体质量达标。

外部创建没有自动回滚承诺：后续层级失败时已创建的父级仍保留暂停，恢复应复用其 ID，
不能为了重试 CTA 重复创建父级。回退本次代码需同时回退模板、蓝图、Tool 契约和客户端，
重启服务加载一致版本；回退代码不会删除已创建的测试资源。

官方依据：TikTok Business API 的 CTA Portfolio 指南（文档 ID `1738672212167682`）、
Portfolio List（`1766324010279938`）及官方 Business API SDK
`f809c396520df2d7b201a9ccc5378d822b728ed3`。未新增观察性系统，沿用结构化 Tool 结果与审计。
