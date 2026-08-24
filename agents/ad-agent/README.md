# ad-agent: 单 Agent + 多 Skills 广告投放架构

## 架构概述

基于 [DAP Agent](https://github.com/...) Go 架构模式，用 Python 实现的**单 Agent + 多平台 Skill** 广告投放系统。

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────┐
│  AgentRuntime（单 Agent 主循环）              │
│  ├─ IntentParser（意图解析）                   │
│  ├─ IntentRouter（意图 → 平台工具路由）         │
│  ├─ ToolRegistry（工具注册与执行）              │
│  ├─ WriteGuard（写入前保护）                    │
│  └─ MultiAgentBridge（预留：多 Agent 切换）    │
└──────────────────────────────────────────────┘
        │           │           │           │
        ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ Meta   │ │ Google │ │ TikTok │ │ DV360  │
   │ Skill  │ │ Skill  │ │ Skill  │ │ Skill  │
   └────────┘ └────────┘ └────────┘ └────────┘
```

## 设计原则（借鉴 DAP Agent）

| DAP Agent (Go) | ad-agent (Python) | 说明 |
|---------------|-------------------|------|
| `CapabilityModule` | `BaseCapability` | 业务模块标准接口 |
| `core.ToolRegistry` | `SimpleToolRegistry` | 工具注册中心 |
| `skill.Contract` | `SkillContract` | Skill 合约定义 |
| `engine.Runtime` | `AgentRuntime` | 主循环运行时 |
| `WriteExecutionGuard` | `WriteGuard` | 写入保护钩子 |
| `Contribution` | `intent_to_tools` | 意图→工具映射 |
| `MultiAgentBridge` | `MultiAgentBridge` | 多 Agent 桥接（预留） |

**核心原则：Core 只认接口，不 import 业务。**

## 目录结构

```
agents/ad_agent/
├── __init__.py                 # 公开 API
├── core/
│   ├── interfaces.py           # 核心接口定义（对应 Go: internal/core/interfaces.go）
│   ├── tool_registry.py        # 工具注册表（对应 Go: internal/core/registry/registry.go）
│   └── intent.py               # 意图解析与路由（对应 Go: .../schedule/agent/turn_router.go）
├── runtime/
│   ├── skill.py                # Skill 加载器（对应 Go: internal/skill/loader.go）
│   └── runtime.py              # Agent 主循环（对应 Go: internal/core/engine/runtime.go）
├── capabilities/
│   ├── base.py                 # Capability 基类（对应 Go: internal/capabilities/contract/runtime.go）
│   └── platform_capabilities.py # 各平台具体实现
├── user_skills/
│   └── orchestrator.py         # 跨平台编排 Skill
└── demo.py                     # 演示脚本
```

## 快速开始

```python
from agents.ad_agent import AgentRuntime, create_meta_capability, create_google_capability

# 1. 创建 Runtime
runtime = AgentRuntime()

# 2. 注册平台 Capability
runtime.register_capability(create_meta_capability())
runtime.register_capability(create_google_capability())

# 3. 执行用户请求
result = runtime.run(
    user_input="用这张海报图投放 Meta 和 Google，预算100元/天",
    user_id="user_123",
)

print(result["reply"])
print(result["results"])
```

## 添加新平台

只需 3 步：

```python
# 1. 新建 capability 文件
class MyPlatformCapability(BaseCapability):
    platform_name = "my_platform"
    
    def register_tools(self):
        return [
            (ToolDefinition(...), MyToolHandler()),
        ]

# 2. 注册到 Runtime
runtime.register_capability(MyPlatformCapability())

# 3. 在 IntentRouter 添加映射（可选，默认已有模板）
```

## 多 Agent 切换（预留）

```python
from agents.ad_agent.runtime.runtime import MultiAgentBridge

class MyMultiAgentBridge(MultiAgentBridge):
    def dispatch(self, user_input, **kwargs):
        # 拆分为多个 Agent 实例协作
        ...
    
    def collect_results(self, agent_results):
        # 汇总各 Agent 结果
        ...

runtime.attach_multi_agent_bridge(MyMultiAgentBridge())
result = runtime.run_multi_agent(user_input)
```

## 与 DAP Agent 的关键差异

| 方面 | DAP Agent | ad-agent |
|-----|-----------|---------|
| 语言 | Go | Python |
| 持久化 | MySQL + Redis | 内存（可扩展） |
| 定时任务 | Schedule 模块 | 暂不支持 |
| 审批流 | 内置 | 通过 WriteGuard |
| UI 卡片 | A2UI 协议 | 简化 card_payload |
| MCP 工具 | 完整支持 | 预留接口 |

## 演示

```bash
cd /Users/yanping.ma/ryan-personal-knowledge
python3 agents/demo.py
```
