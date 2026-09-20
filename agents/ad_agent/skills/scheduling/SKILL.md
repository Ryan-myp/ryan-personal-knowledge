---
name: scheduled-agent-task
description: "定时 Agent 任务的需求澄清、能力预检、确认和安全执行指导"
version: 1.1.0
author: Ryan
tags: [agent, scheduling, clarification, tool_source-preflight, recovery]
namespace: scheduling
aliases: [schedule, scheduled-task, 定时任务, 定时执行, 定期执行]
triggers:
  - keywords: [定时任务, 定时执行, 定期执行, 每天, 每周, 每月, cron, schedule]
---

# Scheduled Agent Task Skill

> 定时任务只保存一个经过确认的自然语言 Agent 指令；调度器不直接调用渠道 API。

## 责任边界

本 Skill 只指导定时任务的理解、澄清、能力预检和确认，不注册 Tool、不持有凭证，
也不直接调用 Provider。创建、暂停、恢复、删除和立即执行由 Runtime 的 scheduling
Feature 处理；到期后必须重新进入当前 Agent Runtime，由已注册的 Skills、Tools、
Tools、权限、账户范围、dry-run/live gate、幂等和审计链路决定实际结果。

## 创建前必须收集的字段

创建周期任务前，必须确认以下信息；缺少或存在多个解释时，保持草稿状态并继续询问，
不能猜测或静默填充：

1. 任务动作：查询/分析、报表、素材处理、创建、更新、暂停、恢复或删除。
2. 调度规则：明确的时间、周期、时区。仅说“每天”不能默认成 09:00；五段 cron
   只有在语法合法且用户明确提供时才接受。
3. 渠道范围：Meta、Google Ads、TikTok、DV360 或明确的跨渠道范围。不能从一个
   渠道的账户 ID 推断其他渠道。
4. 账户和资源范围：账户、Campaign/Ad Set/Ad/素材等资源；动态资源 ID 必须来自
   用户明确输入或后续受控 lookup，不能凭名称生成 ID。
5. 执行模式：查询和分析可以按只读能力执行；任何外部写入都必须标记为 dry-run
   计划，真实 live 写入仍需要当前 Runtime 的显式确认和部署级安全门禁。
6. 输出要求：报告指标、时间范围、时区以及结果回到会话还是其他已注册能力支持
   的输出方式。未指定时可以保留为“回复到当前会话”，但要在确认摘要中展示。

## 澄清策略

- 一次只追问最影响执行的缺口，优先顺序是：动作 → 渠道 → 账户/资源 → 时间/时区
  → 参数/输出。
- 用户补充信息后，合并到同一个可恢复草稿，不要求用户重新描述已确认的字段。
- 用户说“取消/算了/不用创建”时，清除草稿，不创建任务。
- 用户说“确认/就这样/创建吧”时，只有草稿已完成能力预检且摘要完整，才创建任务。
- 能力预检失败时，明确说明“当前 Registry 没有匹配的 Tool/Tool Source”以及缺少的
  渠道或参数；不能把相近 Tool 当成支持，也不能先创建再等到期失败。
- 能力预检只能读取当前 Registry 的 Tool metadata/schema，不能调用 Provider API，
  不能把预检结果描述成已经查询或已经创建。

## 能力预检分层

创建前按以下顺序检查；任何一层失败都不能写入 `active schedule`：

1. **语义层**：普通 Agent Parser 能识别出业务动作，而不是 `chat` 或另一个
   schedule 管理动作。
2. **发现层**：当前 `Tool Registry` 中存在同渠道、同动作/资源语义的 Tool；只看
   Tool 的 `intent_types`、`action`、`resource_type` 和平台元数据，不根据 Tool 名称猜能力。
3. **契约层**：候选 Tool 的 schema 必填参数、账户字段和 Provider 约束能够由用户已提供
   的结构化参数满足；Campaign/素材等动态 ID 缺失时，明确列为待补参数或要求后续
   受控 lookup，不能把名称当成 ID。
4. **授权层**：当前 principal 具备 Tool 声明的权限，账户位于可信账户范围；不能使用
   用户消息里的 `user_id` 或账户文本替代 principal。
5. **执行层**：查询/分析任务可按只读能力执行；写任务只允许保存 dry-run 计划，真实
   live 写入到期仍需重新经过 Runtime 的权限、白名单、确认、幂等和审计门禁。

预检结果必须保留匹配 Tool、缺失参数、读写效果、账户范围结论和检查时间。预检通过不
   代表已经访问广告平台；任务到期时必须重新跑同样的检查，因为 Tool、schema、权限和
   账户范围可能在两次执行之间发生变化。

## 草稿状态机与恢复

```text
用户描述
   │
   ├─ 缺少周期/动作/渠道/账户/参数 ──> awaiting_input
   │                                      │ 补充信息
   ├─ 能力不存在或无权执行 ──────────> unsupported
   │                                      │ 修改动作/渠道/权限
   └─ 能力预检通过 ──────────────────> awaiting_confirmation
                                          │ 明确确认创建
                                          ▼
                                      active schedule
```

`awaiting_input`、`unsupported` 和 `awaiting_confirmation` 都属于会话草稿，不是活跃任务。
草稿必须保存到 Session metadata，并在服务重启或跨机器读取同一持久化后端时恢复；恢复后
只允许继续补充或重新预检，不得把旧的确认状态当成新的 live 授权。用户说“取消”时清除
草稿；创建失败时保留草稿，方便修正后重试。

## 确认摘要

创建前必须向用户展示：任务名称、自然语言指令、周期、时区、渠道、账户/资源范围、
预检匹配的 Tool、读写效果、dry-run/live 限制和下一次执行时间。用户未明确确认时，
保持 `awaiting_confirmation` 草稿；草稿可以在服务重启后从会话持久化 metadata 恢复。

## 到期执行

到期 occurrence 只提交普通 `agent.turn`。执行时重新解析保存的自然语言指令，重新读取
当前 Registry 和 Skills；如果 Tool 被卸载、schema/权限/账户范围发生变化，必须在执行
前重新判定为 unsupported/needs_input/awaiting_confirmation，并记录原因。调度器不得
绕过 Runtime 直接调用 Provider Handler，也不得复用一次性的 live confirmation token。

调度器只负责可靠地提交 occurrence：多实例部署依赖持久化后端的租约、唯一 occurrence
键和幂等；SQLite 仅适合单进程，本地迁移到 MySQL 时必须保留这些语义。单次执行失败不
应静默吞掉，运行记录至少要能区分 queued、running、succeeded、failed，并保留安全的
错误摘要和对应 Agent task/run ID。

## 不允许的行为

- 不允许因为用户说“每天”就默认为 09:00。
- 不允许因为提到 account/campaign 就推断渠道、账户归属或资源 ID。
- 不允许把自然语言指令未经能力预检直接写入 active schedule。
- 不允许将 dry-run 计划、预检结果或“已提交任务”描述成外部平台已经生效。

## 常见场景

### 场景 1：定时查询 Campaign performance

确认渠道、账户、Campaign 范围、时间窗口、指标和时区；先找到只读报表 Tool，再展示
下一次执行时间和输出将回到当前会话。没有 Campaign ID 时，如果当前 Tool 不支持受控
lookup，就继续追问，不把 Campaign 名称当成 ID。

### 场景 2：定时创建或更新广告资源

先识别写 Tool 与其 schema，向用户说明 dry-run 限制、所需参数和风险；创建任务本身
不等于授权未来 live 写入。到期时仍需重新确认，不能复用创建定时任务时的确认语句。

### 场景 3：跨渠道定时任务

分别确认每个渠道的账户、资源范围和匹配 Tool。一个渠道可用不代表其他渠道可用；应
按渠道报告缺口，并允许用户只保留明确支持的子任务。

## 自测题

1. 用户只说“每天分析一下 campaign”，能否创建？不能，至少要继续确认时间、渠道、账户、
   分析动作/资源范围，并完成能力预检。
2. 用户回复“确认创建”时 Tool 缺少 `campaign_id`，能否创建？不能，应停留在
   `awaiting_input` 并指出 schema 缺失参数。
3. 服务重启后能否直接执行一个 `awaiting_confirmation` 草稿？不能，只能恢复草稿并
   等待用户新的明确确认；旧确认不提供 live 权限。
