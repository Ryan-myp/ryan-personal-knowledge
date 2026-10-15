# 页面执行模式切换

日期：2026-10-15。

## 用户约定

页面的 `dry_run` / `live` 是当前身份的实际执行模式，不是无效偏好。
模式保存在服务端，按 tenant / user 隔离；新 Run 使用提交时的模式，已启动 Run 不会被之后的切换改写。

- `dry_run`：生成计划和参数预览，不执行外部广告写入。
- `live`：执行已获批准的 Tool；仍需账户授权、确认、幂等、审计及 Provider 状态校验。
- 选择 live 不授予新权限，不生成用户确认，也不等于启用投放。

## 本次根因

用户已在页面选择 live，但本地服务仍用默认关闭写入的配置启动。
原接口即使 live 不可用也返回切换成功，将问题推迟到确认创建后才暴露。

## 修复

- POST `/settings/execution-mode` 在保存 live 前检查 `ads.write`、部署开关、写入许可和非空 Tool 白名单。
- 无写入权限返回 403；部署未就绪返回 409，保留原模式，不返回假成功。
- `/health` 与设置接口复用相同部署能力判断。
- 页面读取/保存模式期间锁定创建和确认按钮；live 不可用时不允许打开创建确认，保留草稿。
- 创建请求显式携带确认时的模式；模式变化后，旧的本地确认及平台签名确认不能静默用于另一模式。
- 草稿预览将不可用 live 明确标记为不可用，不再写“确认后提交”。

没有修改通用 Harness 或复制 Runtime；变化只在部署配置、HTTP 模式接口及前端交互适配。

## 本地测试配置

默认 `agents/ad_agent/config.yaml` 继续保留 `dry_run`、关闭 live 写入和空写入白名单。
新增 `agents/ad_agent/config.test-live.yaml`，仅允许：

| 渠道 | 测试账号 |
| --- | --- |
| Google Ads | `9055507554` |
| Meta | `2806375919473667` |
| TikTok | `7397068114548195329` |

该配置只批准 19 个创建 Tool，没有批准激活、恢复、删除或任意更新。
现有 Provider 契约约束暂停投放；Google App Ad 的例外是子级必须 ENABLED，
但创建前必须回查 Campaign / Ad Group 均为 PAUSED，不能将其描述为全部子级也暂停。

本机被 Git 忽略的 `.env` 仅新增两个公开部署设置：`AD_AGENT_ENABLE_LIVE=1`、
`AD_AGENT_CONFIG_PATH=agents/ad_agent/config.test-live.yaml`，没有改动凭证。
页面日常切换不再需要重新配置或重启服务。
显式启动同一 API 服务的命令为 `make ad-agent-run-test`，绑定 `127.0.0.1:8765`，
复用现有数据库、身份、会话、Tools 与确认链路，不是第二套测试 Runtime。
普通安全配置仍可通过显式环境覆盖运行；没有将部署许可交给网页请求自行修改。

## 验证证据

证据目录：`outputs/workspace-mode-e2e-20261015/`。

- 从真实浏览器页面选择 dry-run，界面返回保存成功；独立 GET 设置确认 `mode=dry_run`，见 `page-dry-run.json`。
- 从同一页面选择 live，独立读取确认 `mode=live` 且 `live_mode_available=true`，见 `page-live.json`。
- 使用 Google Shopping 内置模板准备暂停测试计划，请求不显式覆盖模式，继承页面已保存的 live。
- 服务返回平台签名确认，`needs_confirmation=true`，不再报 `allow_live_writes is disabled`。
- 本轮没有继续确认，没有实际创建或启用外部广告，不能将此记录当作新广告创建成功的证据。
- 页面截图为 `page-live-switch.png`，确认阶段证据为 `live-awaiting-confirmation.json`。

默认安全环境下执行 `make ad-agent-check`：1799 项 Agent 测试通过，编译、能力审计、
310 个 Tool 契约快照与差异检查通过。前端 Node 回归 30 项通过，覆盖模式失败回退、
提交锁定及旧确认失效。全仓 qguard 仍未通过，不宣称整体质量门禁达标。

回退需要恢复本地部署设置并重启服务，再从页面选择 dry-run。
回退不会删除历史会话、改变已创建资源，也不承诺中止已执行的外部操作。
