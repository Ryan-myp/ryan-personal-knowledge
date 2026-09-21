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
Integration Source 和 Infrastructure 生命周期；业务入口不应直接绕过它创建 Runtime。
平台默认给 Harness 装配 `ToolExecutionPolicy`，统一执行输入 Schema、权限、风险、
live 开关、Run 内幂等和审计门禁。

产品只能通过标准 Harness 的 Agent loop 和 Tool/Skill 适配器接入场景行为。
它不能创建业务专用 Pipeline、第二个 Agent、第二个 Runtime 或第二套 Tool 门禁；
Run、Session、Tool、Skill、审计和权限边界始终由中台契约统一负责。
