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
