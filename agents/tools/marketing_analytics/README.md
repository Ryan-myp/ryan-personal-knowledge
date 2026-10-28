# GA4 与 Search Console 只读 Tools

该 Tool Source 提供只读 Google Analytics 4（GA4）和 Google Search Console 能力，供广告与增长分析使用。它注册到现有 Agent Runtime/Tool Registry，不建立新的 Agent、路由或 MCP 执行入口。

## 启用前配置

1. 在 Google Cloud 项目启用 **Google Analytics Admin API**、**Google Analytics Data API** 和/或 **Google Search Console API**。只启用实际要用的 API。
2. 配置 Google OAuth Client，并授权有相应只读权限的用户。为 GA4 使用 scope `https://www.googleapis.com/auth/analytics.readonly`；为 Search Console 使用 `https://www.googleapis.com/auth/webmasters.readonly`。Refresh Token 必须在用户同意相应 scope 后生成；提交 refresh 请求不会扩大已有授权范围。
3. 在系统“模型与密钥”设置的“渠道与分析数据源”中，分别选择 **Google Analytics 4** 或 **Search Console**，填写 OAuth Client ID、Client Secret、Refresh Token。凭证通过系统加密设置 Vault 保存。不要把 token 粘贴到对话、知识库、日志或 Skill 文件。
4. 共享部署使用的是部署级 OAuth 凭证：GA4 账号需能访问相应 Property，Search Console 账号需有相应 Site Property 权限。当前没有个人 OAuth 登录/回调或每用户凭证隔离；使用共享实例时，查询范围受这组授权账号可访问的资源约束。
5. 若设置了 `AD_AGENT_SERVICE_PERMISSIONS`，将 `analytics.read` 加入其逗号分隔权限；若使用 `AD_AGENT_API_KEY_PRINCIPALS`，也要仅为允许访问分析数据的 principal 单独授予 `analytics.read`。默认 `agents/ad_agent/config.yaml` 已包含该只读权限。

## 可用能力

### GA4

- `ga4_list_properties`：发现当前授权可访问的 Account / Property。
- `ga4_get_metadata`：读取 Property 当前可用的 dimensions 与 metrics；建议先查询 metadata，再生成报告。
- `ga4_run_report`：查询给定日期范围的聚合 GA4 报告，最多 1,000 行/页，并支持受限 offset 分页。

### Search Console

- `gsc_list_sites`：发现当前授权可访问的 URL-prefix 或 Domain Property。
- `gsc_search_analytics`：按 date、query、page、country、device、searchAppearance 分组查询有限行数的搜索表现，可选择 web/image/video/news/discover 等搜索类型。

## 限制与安全

- 只读；不配置 GA4 events/key events、GTM、Pixel、CAPI、网站、Search Console 属性或站点验证。
- GA4 Tool 返回聚合报告，不读取用户级事件、原始用户身份或 CRM/订单明细。`keyEvents`/收入字段存在不代表 CRM 合格线索或财务结果已经核实。
- Search Console API 可能省略匿名/低频查询或长尾数据，可能存在数据延迟；响应不保证全量。它也不提供所有生成式搜索系统的品牌引用数据。
- 外部请求固定为 Google OAuth/官方 API host，使用短连接超时、响应字节上限和行数上限；错误对用户脱敏。API 速率限制仍由 Google 配额决定，避免循环高频重复读取。
- 本地测试使用 Mock；不会自动请求真实 Google API。实际连通性只有在用户配置凭证并执行一次受授权查询后才能确认。
