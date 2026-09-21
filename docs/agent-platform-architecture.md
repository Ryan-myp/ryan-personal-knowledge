# Agent 中台六层架构

本仓库采用标准的通用 Agent Platform 形态。平台只有一个通用 Agent；广告不是
Runtime 特例，而是一个应用场景。其他业务使用同一套 Harness、Tools、Skills、
数据 Port 和集成 Port 接入。

## 1. 六层总览

```text
┌────────────────────────────────────────────────────────────────────┐
│ 应用场景层                                                         │
│ 客服｜知识问答｜营销助手｜数据分析｜流程自动化｜研发助手｜更多场景 │
│ ScenarioDefinition：选择 Skills、Tools、数据和策略                 │
└────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│ Agent 层                                                           │
│ 一个通用 Agent：default-agent                                      │
│ AgentDefinition：身份、版本、提示词、扩展来源和能力边界            │
└────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│ Agent 中台核心能力层                                               │
│ Run/Session/Turn｜Model｜Tools｜Skills｜Knowledge｜Memory           │
│ Task｜Security｜Observability｜Protocol｜AgentPlatform              │
│ 真实执行统一进入 Agent Harness，不复制业务 Runtime                 │
└────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│ 数据层                                                             │
│ 会话、Run/Event、知识库、Raw Source、Memory、任务、审计和业务数据   │
│ 通过 Data Port 注入；当前 SQLite 只是部署实现，不向上泄漏           │
└────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│ 集成层                                                             │
│ Local Handler｜SDK/HTTP Connector｜MCP Client｜企业系统/API/消息      │
│ 统一转换为 Tool Source + Tool Executor，并经过同一安全执行门禁      │
└────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────────────────────────────────────┐
│ 基础设施层                                                         │
│ 计算、容器/K8s、存储、网络、队列、WAF、CI/CD、监控和日志             │
│ 由部署组合根提供，不进入 Agent 业务逻辑                             │
└────────────────────────────────────────────────────────────────────┘
```

右侧的 Agent 市场、治理运营中心和核心价值属于横切面，不新增第七套执行引擎：

```text
Agent 市场       = Agent/Scenario catalog、发布、版本和复用
治理运营中心     = 权限、审计、指标、链路、成本、版本、灰度和回滚
核心价值         = 降本增效、快速创新、复用共享、安全可控、持续进化
```

## 2. 代码目录

```text
agents/
├── agent_harness/                 # 中台核心执行内核
│   ├── runtime_kernel.py          # Run/Session/Lease/Mode
│   ├── agent.py                   # Model → Tool → Model loop
│   ├── turn_pipeline.py           # 通用回合阶段
│   ├── tool_catalog.py             # Tool contract catalog
│   ├── skills.py                   # 标准 SKILL.md catalog
│   ├── run_store.py                # 持久化 Port
│   └── observability.py            # metrics Port
├── agent_platform/                # 六层平台契约与装配入口
│   ├── architecture.py            # 六层和横切能力词汇
│   ├── definitions.py              # Agent/Scenario definition
│   ├── platform.py                 # AgentPlatform registry/factory
│   ├── core/                       # 中台核心 Port
│   ├── tools/                      # Tool 策略与 Tool 门禁
│   ├── data/                       # 数据 Port
│   ├── integrations/               # 外部集成 Port
│   ├── infrastructure/             # 部署基础设施 Port
│   └── governance/                 # 治理策略
└── ad_agent/                      # 广告场景实现
    ├── agent_definition.py         # 广告场景的 Agent/Skill/Tool 装配
    ├── skills/                     # 广告 Skills
    ├── tools/providers/             # 广告 Tool Sources
    ├── api_clients/                 # Provider SDK/HTTP adapters
    ├── domain/ad/                  # 广告领域模型
    ├── persistence/                 # 数据层适配
    └── runtime/                    # 广告场景的 Tool/数据/基础设施装配
```

`agents/ad_agent/runtime/` 只负责广告场景的 Tool、数据和基础设施装配，不是平台核心
Run Kernel。通用身份、Session 并发、Run 生命周期、Turn Handler 和 Tool Source
生命周期只归 `agents/agent_harness/`；场景层不能再创建第二套 Kernel、Pipeline、
Router 或 Tool 门禁。

## 3. 四个边界

### 场景只做组合

场景通过 `ScenarioDefinition` 选择 Agent 及其 Skill/Tool Source。它不直接 import
Provider Client，不定义权限，也不创建新的 Runtime。

### Agent 只描述产品能力

`AgentDefinition` 保存产品身份、版本、系统提示、Skill Source、Tool Source 和元数据。
它不保存凭证，不执行代码，也不决定某个 Provider 的 HTTP 细节。

### Tool 是唯一动作入口

本地函数、SDK/HTTP Connector 和 MCP Client 都先变成标准 Tool Source。Tool 必须
经过 schema、principal、权限、effect、dry-run/live、确认、幂等、超时、输出上限和
审计门禁。Skill 只提供自然语言上下文。

### 数据和基础设施只通过 Port

知识、Memory、Session、Run、Task 和审计都由 Port 表达。上层不绑定 SQLite、队列、
具体云厂商或 HTTP 框架；替换存储或部署方式不会改 Agent 和 Scenario 定义。

## 4. 广告如何接入

```python
from agents.ad_agent import (
    advertising_agent_definition,
    create_meta_tool_source,
)
from agents.agent_platform import AgentPlatform, ScenarioDefinition

platform = AgentPlatform()
platform.register_agent(advertising_agent_definition(
    tool_sources=(create_meta_tool_source(),),
))
platform.register_scenario(ScenarioDefinition(
    scenario_id="marketing-assistant",
    agent_id="default-agent",
))
application = platform.create_application(
    "marketing-assistant",
    model=model,
)
```

`create_application()` 返回的是六层 `PlatformApplication`。它内部持有标准 Harness
Runtime，同时管理选中的 Tool Sources、数据 Port 和基础设施资源的启动/关闭；调用方
不需要绕过平台直接创建第二个 Runtime。

平台默认给 Harness 注入 `ToolExecutionPolicy`，因此通用 Agent 的 Tool 调用同样经过
输入 Schema、权限、风险确认、live 开关、Run 内幂等和审计门禁；Provider API 仍只由
Tool Executor/Connector 实现。

广告 Tools/Skills 可以被知识问答、数据分析或其他应用场景复用；复用只发生在
Source 装配层，不把广告渠道、账户字段或 Provider API 带进中台核心。

## 5. 当前实现的简化点

当前只实现平台最小闭环：标准 Harness、Agent/Scenario catalog、六层 Port、治理
策略和广告产品声明。知识中心、记忆中心、任务调度、模型中心、统一通信协议的具体
生产实现继续由现有产品组合根注入；这保持了层级完整，同时避免在 SQLite 之外提前
绑定某个基础设施供应商。
