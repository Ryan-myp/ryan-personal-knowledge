# Google 页面确认与创建修复

日期：2026-10-15。只使用 Google 测试账号 `9055507554`。

## 原会话根因

截图对应会话 `66fb1903-bc67-4e2a-909d-d91cb4a2f899`：

1. 第一次签名确认的原始请求包含账号、名称、预算、排期和 Shopping 模板。
2. `executeConfirm()` 仅在输入框补了账号时才发送账号，也仅在补参数时才发送参数。
   普通确认按钮因此丢掉整个原始表单，下一轮退回询问账号。
3. `ask_account` / `ask_params` 又被当作 `confirmed=true` 的审批提交，
   导致“确认信息与当前写入计划不匹配”。
4. 新回复的聊天确认入口引用了历史展示用的脱敏凭证，而不是响应顶层的一次性凭证。
5. 移除确认卡后，没有清理右侧确认视图，留下空白工作区。

原历史记录未改写，没有自动重放用户原来的“夏季促销 Shopping”请求。

## 修复边界

- 确认使用原始请求的不可变快照，保留账号、所有 namespace 参数、模板、版本、
  排期、预算、执行模式和 Tool allowlist；后续编辑不能偷偷改写已经批准的请求。
- 补账号、补参数只是继续规划，必须先取得新的签名确认，不能借此执行写入。
- 新响应入口使用顶层一次性凭证；历史、过期或脱敏凭证只能重新生成计划。
  重新生成时清除失效的资源选择 token，再按当前账号重新校验。
- 会话或模式变化时阻止旧确认；确认结束后不留下空白右侧面板。
- 后端仍只在顶层 API 响应返回一次性确认 token，不写入历史、日志或模型上下文。
- 权限、测试账号白名单、live 开关、签名、幂等和审计校验没有放宽。

## 页面实测发现的其他问题

向导将隐藏字段也序列化，例如把 PMax 专属的 `brand_guidelines_enabled=false`
带进 Shopping，真实 Google API 返回 400。现在过滤评估为隐藏的字段及对应选择证明，
并在 Google Tool schema 和 SDK 创建预算前拒绝非 PMax 的品牌指南字段。

Shopping 模板补齐与三个子字段一致的 `shopping_setting` 对象，
避免 Merchant 字段已填但向导仍误报对象缺失。

成功的真实 live 写入现在也能建立后续只读查询的账号上下文；
失败、计划、模拟及未知结果不能建立该上下文，也不能据此自动授权新写入。

回查曾暴露模型把 `500000 micros` 错算为 5。Google 查询 DTO 增加
`cpc_bid_amount=0.5`、`cpc_bid_unit=account_currency`，保留原始 micros，
不改变写入金额，也不假定账户币种是美元。

## 真实创建与回查

从运行中的页面选择内置 Shopping 模板，逐项填写名称、预算 20、
2026-10-18 至 2026-10-20 排期，带入对话、提交计划、
重新打开聊天确认入口，再点击“确认执行”。
没有手工替换确认请求，没有直接调用 Provider client 创建。

实际会话：`4357ea24-13c5-4602-ae63-f5ecee129e28`。
创建 Run 为 `succeeded`，四个创建 Tool 均成功，执行模式均为 live。
随后通过同一页面对话实际调用四个详情 Tool 回查：

| 对象 | ID | API 回查状态 |
| --- | --- | --- |
| Campaign | 24363097189 | PAUSED |
| Ad Group | 206275755252 | PAUSED，关联上述 Campaign |
| Shopping Product Ad | 828106916302 | PAUSED，关联上述 Ad Group |
| Product Group | 293946777986 | ENABLED，关联上述 Ad Group |

预算 `20000000 micros` 对应账户货币 20；Merchant `115791065`、排期和父子关联一致。
Ad 的实际回查包含 `delivery_blocked_by_parent=true`。

不能把商品分组状态伪报为 PAUSED：本次 API 虽收到 PAUSED 请求，回查仍为 ENABLED。
新增前置校验要求 live 创建商品分组时 Campaign 和 Ad Group 均已核实为 PAUSED，
阻止挂到已启用或状态未核实的父级。该校验不能锁定外部平台未来的状态变化。

## 证据

本地目录：`outputs/google-confirmation-e2e-20261015/`。

- `before.json`：原失败会话、确认请求及后续参数丢失的记录。
- `qa-v4-before-confirm.json`：实际提交前的完整请求，已断言没有 PMax 专属字段。
- `qa-v4-completed-run.json`：四个实际创建 Tool 的成功事件。
- `qa-readback-run.json`：四个真实查询结果，均为 `data_status=live`。
- `qa-restarted-cpc-readback.json`：重启后不再选择账号的查询，金额明确为 0.5 账户货币单位。
- `history-requires-new-plan.png`：原历史确认只提供“重新生成确认计划”，未点击写入。
- 页面截图另行保留，包含真实创建及查询结果。

实测期间曾因旧向导的 PMax 字段触发一次 Google 400，没有把该次失败计作成功。
旧 SDK 的预算创建先于 Campaign，失败尝试可能留下未绑定预算；未自动删除外部资源。
本轮没有启用投放、切换到非测试账号，或对原历史请求执行补跑。

## 交付与恢复

前端资源版本为 `20261015-confirmation-v4`，需刷新页面。
服务重启保留原执行模式；旧记录中已经脱敏或过期的确认须重新生成后再次确认。
没有新 SQL 表、迁移历史消息、另起 Runtime 或增加 Provider 执行入口。

Provider 输入契约、只读返回字段和 Tool 说明已更新，契约快照同步。
回退需要恢复代码、模板及快照并重启；回退不会撤销外部已成功创建的资源。
沿用现有 Run 事件和审计，不增加独立观察性链路。

最终 `make ad-agent-check` 完成编译、能力审计和 310 个 Tool 契约快照校验，
1892 项 Agent 测试通过，保留 1 项依赖弃用警告；前端 Node 回归 50 项通过，
`git diff --check` 通过。全仓 qguard 仍未通过，不宣称整体质量门禁达标。
