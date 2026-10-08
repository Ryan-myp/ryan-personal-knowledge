# Agent Platform

这是仓库的通用 Agent 中台边界。它不包含广告业务、Provider 名称或渠道路由，
只负责把标准 Agent Harness 组织成可复用的平台入口。

## 六层结构

```text
应用场景层        scenarios/
      ↓
Agent 层          一个 AgentDefinition / 单 Agent 注册
      ↓
中台核心层        agents.agent_harness + core/ + tools/
      ↓
数据层            data/ 以及各产品注入的 Knowledge/Memory/Run Store Port
      ↓
集成层            integrations/ 以及 Tool Source / SDK-HTTP / MCP Adapter
      ↓
基础设施层        infrastructure/ 以及部署、队列、网络、计算和存储实现
```

`governance/`、可观测性和 Agent 市场是横切能力，不创建第二个 Runtime。
平台只注册一个通用 Agent；广告只是一个应用场景，通过场景选择广告 Skills、Tools、
Provider Adapter 和数据实现接入，其他业务复用同一 Agent 和同一 Run Kernel。

## 使用方式

```python
from agents.agent_platform import AgentDefinition, AgentPlatform, ScenarioDefinition

platform = AgentPlatform()
platform.register_agent(AgentDefinition(
    agent_id="default-agent",
    display_name="General Agent",
    skill_sources=(knowledge_skills,),
    tool_sources=(knowledge_tools,),
))
platform.register_scenario(ScenarioDefinition(
    scenario_id="knowledge-qa",
    agent_id="default-agent",
))
application = platform.create_application("knowledge-qa", model=model)
```

`application` 是六层 `PlatformApplication`，统一负责 Harness 执行、Data Port、
Integration Source 和 Infrastructure 生命周期。`PlatformDependencies.integrations`
中的 Tool Source 会与场景选择的 Source 合并后注册到同一个 Harness；业务入口不应
直接绕过它创建 Runtime。
应用同时提供 `healthcheck()` 和 `readiness()`，用于检查 Runtime、Skill/Tool
目录、外部集成和基础设施状态；未启动应用会明确返回 `not_started`，已关闭应用
不会接受新的 Run。

`DataLayer` 中注入的 Knowledge、Memory、Session 和 Run Store 也属于应用生命周期：
如果实现了 `start()`/`close()`，平台会按声明顺序启动、按逆序关闭，并在启动失败时回滚
已经成功启动的 Store。实现 `check()` 或 `healthcheck()` 的 Store 会出现在受限的
`healthcheck()` 输出中；平台不会通过真实数据查询来探测健康状态，也不会把凭证字段
复制到健康结果。
平台默认给 Harness 装配 `ToolExecutionPolicy`，统一执行输入 Schema、权限、风险、
live 开关、跨进程 SQL 幂等和审计门禁。`GovernancePolicy` 的默认执行模式、Tool 数量、
最大回合数、Skill 上下文上限、Tool 超时、只读重试和熔断参数会真实下沉到 Harness，
而不是只停留在架构元数据。Tool Call 依赖由 Harness 按拓扑批次执行；写操作不会自动
重试，超时写入会进入未知效果恢复态。
通用 Policy 的 live 写操作还要求请求携带非空 tenant/user principal；请求文本或
`TurnRequest.user_id` 不能替代认证。principal 必须由可信入口或 Worker 身份解析器
构造，平台对象本身不负责验证外部身份令牌。

Knowledge 与 Memory 通过 Harness 的 `BoundedContextProvider` 作为有界 advisory
context 注入。它们可以提供检索证据和用户偏好，但不能提供身份、权限、账户范围或
Tool 授权；Knowledge 使用 tenant/user 范围，Memory 额外使用 session 范围。MCP 同样
只是通用 `MCPToolSource`/`MCPToolExecutor` 集成，不属于广告 Runtime 专属能力。

Knowledge 的语义增强使用 `data.semantic` 的 `EmbeddingProvider` 与
`SemanticIndex` port。默认仍可只使用 Markdown + lexical/BM25；启用后按 scope
建立向量索引，并在 semantic 服务异常时降级到 lexical，检索结果始终保留原始
document/chunk provenance。

产品只能通过标准 Harness 的 Agent loop 和 Tool/Skill 适配器接入场景行为。
它不能创建业务专用 Pipeline、第二个 Agent、第二个 Runtime 或第二套 Tool 门禁；
Run、Session、Tool、Skill、审计和权限边界始终由中台契约统一负责。

仓库内的 `agents.agent_platform.examples.ticket_support` 是一个不依赖广告包的参考
应用。它只注册一个 Skill Source 和一个 Tool Source，使用同一个
`AgentPlatform`、`PlatformApplication` 和 Harness，可作为新业务接入的最小起点。

## 持久任务与负载基线

`infrastructure/durable/` 包含应用无关的 TaskExecutor、Task Store 协议、
Scheduler、Outbox、事件修复和 RuntimeSupervisor；广告只注入自己的 SQL Store
与可信 task handler。新业务可以用 `DurableAgentService` 把可信主体的请求排队，
由 Worker 重新解析主体并进入同一 `PlatformApplication.run()`。任务 payload 只
保存输入和 session ID；读取任务必须提供可信 principal，Worker 重新解析出的
租户和用户必须与持久记录一致。应用仍须提供符合端口的持久 Store、RunStore 和
可信身份解析器。平台提供 `SQLiteTaskQueueStore` 和 `SQLiteRunStore` 作为本地实现；
Run 事件在入库前做凭证字段脱敏，并支持按主体读取持久轨迹。SQLite 适用于单主机
部署和开发验证，不构成多主机生产数据库。业务可替换持久化 adapter，而不改
TaskExecutor、DurableAgentService 或 Agent Run；RunStore 通过 `DataLayer` 注入。
`DurableAgentService.close()` 只停止它自己的 Worker；共享
`PlatformApplication` 由应用组合根关闭。

`DurableAgentService` 暴露的提交、读取、列表、暂停、恢复和取消操作都需要可信
principal，并按 tenant/user 过滤。重复幂等键只有在任务类型和请求 payload 相同时
才返回既有任务；键被用于不同请求时明确报冲突。对 `recovery_required` 任务，恢复
前必须由调用方完成外部状态核对，并使用独立的 recovery reference 操作持久 Store。
提交入口默认限制输入为 100,000 字符，session ID 和幂等键各限制为 255 字符。

通用 Run 的无网络并发基线：

```bash
PYTHONPATH=. ./scripts/ad-agent-python -m agents.agent_platform.benchmarks.runtime_load \
  --iterations 200 --concurrency 8
```

它测量本机 Harness 调度开销，不调用真实模型或 Provider，不能用来宣称生产吞吐。
广告只读测试账号查询脚本会为每个实际 Provider Tool 调用保存 `latency_ms`；
只有完成受控实测后才能汇总 Provider 延迟，跳过和模拟结果不计入。
