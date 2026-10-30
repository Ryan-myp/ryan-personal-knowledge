# 执行引擎与平台运行服务分离

## 交付范围

现有广告应用现在可以在启动时注入经过部署审核的 `ExecutionEngine`。默认仍是
`NativeExecutionEngine`，继续使用当前模型配置。替代引擎拥有自己的决策循环，
平台通过 `EngineSession` 提供上下文、工具执行、流式文字和最终回复入口。

这次交付的是可运行、经过离线替代引擎验证的引擎边界，**没有安装或接通 Hermes Agent
或 Claude Agent SDK，也没有验证它们与 Agnes 的兼容性**。原有 `claude_sdk` Skill
评测引擎仍是只读的 Anthropic API 评测适配器，不是生产 Agent SDK。

## 职责与验收对应

| 要求 | 实现位置 | 验证 |
| --- | --- | --- |
| 一次 Run 只使用一个决策引擎 | `Agent.run`、`ExecutionEngine.run` | 替代引擎测试中的原生模型若被调用立即失败 |
| 唯一身份、run_id、turn_id、Session 租约 | 现有 `AgentRuntime` / Run Kernel | 冒用请求 user_id 不改变可信 principal；只有一组开始/结束事件 |
| 复用工具门禁 | `EngineSession.call_tools` → 原有 host continuation → `ToolExecutionCoordinator` | schema、权限、allowlist、live 门禁、确认交互、审计、调用上限 |
| 动态工具发现继续有效 | `snapshot` 与原有 `RunToolDiscovery` | 从另一线程执行发现回调后，下一快照可见新 Tool |
| 历史、Skills、知识继续由平台管理 | 原有 `_model_inputs`、SkillCatalog、ContextProvider、StatePersistence | 多轮历史、租户上下文、检查点恢复、篡改快照不影响 host |
| 界面结果与流式契约保留 | 原有 RunResult、`model_start/model_delta/model_end`、tool/turn 事件 | 最终消息、工具记录、确认卡片仍使用相同结构 |
| 取消和失败不重放副作用 | 可撤销 EngineSession、执行超时、有限并发 | 取消、超时占槽、迟到调用拒绝、异常保留已完成工具结果 |
| 复用插件治理 | `PluginKind.ENGINE`、现有 PluginRegistry | 未审核插件拒绝，启动激活，关闭清理，运行期间不替换 |
| 真实广告组合可使用新边界 | `AdvertisingComposition(execution_engine=...)` | 不创建第二套广告应用或 Run Kernel 即可完成一次真实组合运行 |

```text
HTTP / 定时任务 / 广告应用
  → AgentRuntime / Run Kernel
      → Agent：上下文、历史、检查点、结果与事件
          ↔ 一个 ExecutionEngine：模型决策循环
          → ToolExecutionCoordinator
              → 现有 policy / scope / confirmation / idempotency / audit
              → ToolBinding / Provider / MCP
```

`Agent._execute_steps` 是公共状态推进过程，不再主动请求下一次模型响应。
默认引擎调用原来的 ModelExecutionCoordinator；替代引擎直接驱动自己的 loop，
再把 ToolCall 或最终文字交回 host。没有把 SDK 当作普通模型嵌套进自研循环。

## 新接口

- `AgentApplication.create(engine=..., engine_plugins=..., engine_timeout_seconds=...)`
- `AgentPlatform.create_application(..., engine=...)`；多个 Scenario 共享一个引擎。
- `AdvertisingComposition(execution_engine=...)`；这是可信部署代码参数，不是 HTTP
  请求、上传 Skill 或管理 JSON 可以指定的动态 import/命令入口。
- `ExecutionEngine.manifest` 必须是 `kinds=("engine",)`、trusted/executable 的
  PluginManifest。广告组合直接复用其已有 PluginRegistry。
- `EngineSession.snapshot()` 返回有界、脱敏、可独立修改的消息与工具 schema 副本；
  不返回 principal、原始 TurnRequest、Provider client 或执行器。控制元数据不能由引擎回写。
- `call_tools([...])` 经原有门禁、输出限额、检查点保存后返回结果。需要用户输入、确认、
  失败恢复或达到上限时，host 终止该 Run 并抛出 `EngineStopped` 通知适配器停止。
- `emit_text(delta)` 复用 `model_delta`；只用于用户可见的回答文字，不转发 SDK 内部日志。
- `finish(reply, usage=...)` 只提交回答与 usage，不能指定成功状态；状态由实际工具结果决定。
- `check_cancelled()` 供 SDK 等待/回调期间主动检查。SDK 仍需关闭自己的连接或子进程。
- `configure_model()` 只允许原生引擎修改其模型客户端。非原生引擎明确报错，避免 UI
  显示模型切换成功、实际仍由另一个 SDK 使用旧模型。
- health 与 RunResult 增加安全的引擎 ID/版本；原有字段未改名。

未知附件能力不会静默丢弃：非原生引擎必须在受审 manifest 的 metadata 中声明
`input_media: true` 后，才会收到 InputMedia；声明前应完成图片、文档、视频处理适配。

## 安全与失败恢复

引擎是**受信任的部署代码**，EngineSession 不是 Python 沙箱。不得让用户上传 Python
代码后直接构造 ExecutionEngine。未来接入外部 SDK，应禁用其 Bash、文件写入、独立
MCP 和其他绕过平台的业务执行入口，并限制子进程继承的环境与目录权限。

替代引擎默认最长 300 秒，可显式设为不超过 3600 秒；广告组合使用现有 turn timeout。
超时/取消会撤销该 Run 的工具入口，迟到回调不能再执行工具。无法强杀的线程在实际退出
前继续占用并发槽，不能靠重试无限创建后台线程。外部写入的未知结果仍由原有执行器
标记 recovery_required，不能把本地取消等同于广告平台回滚。

检查点保存失败会阻止下一批动作。SDK 抛错或提前返回不自动切换另一引擎重做请求；
已完成工具的结果保留。恢复使用平台检查点与统一对话历史；不把外部 SDK session ID
当作平台身份或副作用恢复凭据。跨 SDK 的私有压缩状态、内部记忆并不保证可迁移。

## Hermes / Claude Agent SDK 后续适配边界

| 组件 | 可复用部分 | 仍需适配/验证 |
| --- | --- | --- |
| Skills / 知识 | 原有租户加载、版本、检索与有界文本 | 外部引擎原生 Skill 文件加载并非自动接通；不可给 SDK 可写共享知识目录 |
| Tools | schema 投影、业务实现、策略与执行记录 | SDK 名称映射、动态工具集合、回调与停止信号；不得直连 Provider |
| Hermes Agent | 可作为独立决策循环 | 当前入口有环境加载与自己的 Session 生命周期；需隔离宿主并收束业务执行入口 |
| Claude Agent SDK | 官方自定义工具/MCP 回调与流式客户端 | 专用受控 MCP 回调、内置工具禁用、认证隔离、取消/断开、usage 映射 |
| UI / 管理 / 定时任务 | 原有 API 与数据服务 | 具体 SDK 的多模态、错误与进度适配必须完成验收后才能开放切换 |

参考：
- https://github.com/NousResearch/hermes-agent
- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/custom-tools

## 迁移与回滚

无需数据库迁移，未更换数据库、端口、模型密钥、模板或知识库。
现有调用不传 engine 时维持默认原生行为；新入口只在进程启动时选择引擎。
引擎实例在进程内复用，多个 Session 可并发进入 `run(session)`；适配器必须把 SDK
会话、连接状态与取消句柄按该 EngineSession 隔离，不能把“当前会话”存成共享字段。
回滚外部引擎时停下/完成已有 Run，移除部署注入并重启即可；不自动恢复未知副作用。
观察性继续使用现有 Run/Tool/Model 事件；未来 SDK trace 可在该边界映射，无需改业务 Tool。

验证结果记录于同名 evidence JSON。测试全部离线，不请求真实广告 API 或外部模型。


## 本轮验证结果

- `make ad-agent-check`：完整通过，3586 项 Python 测试、266 项前端测试、328 个 Tool
  contracts、86 页内置知识与本地检索 benchmark 通过。
- 新增引擎边界/平台/广告组合定向测试：30 项通过；`execution_engine.py` 语句覆盖
  179/189（94.71%，报告四舍五入为 95%），不代表全仓覆盖率。
- 新模块 qguard：83/B、通过。两项提醒是引擎边界的通用 Exception 捕获，均交回
  host 记录失败，没有吞掉异常或记录原始诊断文本。
- 全仓 qguard：786 文件、4998 项发现、0/F、未通过；原有大量长函数等问题仍在。
  没有降低门槛或新增忽略规则。原有长 Run 方法本次改为 host continuation，尚未进一步拆分。
- `git diff --check`：通过。
- 服务已恢复监听 `0.0.0.0:8766`，确认激活 `harness.native-engine@1.0.0`。
  重启前后 514 个会话、14 个用户模板、5 个定时任务及 354 个 Runtime tools 保持一致；
  数据库已备份。LaunchAgent 首次 bootstrap 返回 exit 5，确认未注册后重试成功。
- 未调用真实广告 API 或外部模型，未提交或 push。
