---
name: agent-architecture-expert
description: "Agent 架构专家技能 — ReAct、Planner、Multi-Agent、Tool Use、Memory 系统"
version: 1.0.0
author: ryan
tags: [agent, architecture, react, multi-agent, rag, expert]
---

# Agent 架构专家技能

> 从 ReAct 到 Multi-Agent 编排，掌握生产级 Agent 系统设计

## 核心能力

### 1. Agent 模式
- **ReAct**：Reasoning + Acting 循环
- **Planner**：任务分解与执行规划
- **Reflexion**：自我反思与改进
- **Tool Use**：Function Calling / MCP
- **Multi-Agent**：多 Agent 协作编排

### 2. 记忆系统
- **短期记忆**：对话上下文、工作记忆
- **长期记忆**：向量数据库、知识图谱
- **语义记忆**：事实性知识存储
- **程序性记忆**：技能与流程
- **agentmemory**：持久化记忆引擎

### 3. 工具集成
- **MCP (Model Context Protocol)**：标准化工具接口
- **Function Calling**：LLM 原生工具调用
- **Tool 设计原则**：幂等性、错误处理、超时控制
- **工具编排**：串行、并行、条件分支

### 4. 生产化
- **可观测性**： tracing、日志、指标
- **性能优化**：缓存、批处理、流式响应
- **安全与 guardrails**：内容过滤、权限控制
- **错误恢复**：重试、降级、回滚

## 知识库引用

| 主题 | 文档 |
|------|------|
| Agent 架构 | `knowledge/agent-ai/agent-architecture-deep.md` |
| 设计模式 | `knowledge/agent-ai/weread-agent-design-patterns-deep.md` |
| LangChain | `knowledge/agent-ai/weread-langchain-deep.md` |
| AgentExecutor | `knowledge/agent-ai/agent-deep-dive.md` |
| Multi-Agent | `knowledge/agent-ai/ai-agent-system-design-deep-v2.md` |
| ReAct | `knowledge/agent-ai/react-deep-dive.md` |
| RAG | `knowledge/agent-ai/rag-deep-dive.md` |
| Memory | `knowledge/agent-ai/agentmemory-deep-dive.md` |
| 实战手册 | `knowledge/agent-ai/agent-practical-handbook.md` |
| 安全治理 | `knowledge/agent-ai/ad-ai-evaluation-security-deep.md` |

## 使用场景

### 场景 1: 设计 Agent 系统
1. 确定任务类型 → 查找型/创作型/操作型
2. 选择 Agent 模式 → ReAct / Planner / Multi-Agent
3. 设计工具集 → 参考 MCP 规范
4. 实现记忆系统 → 短期 + 长期记忆

### 场景 2: 调试 Agent 行为
1. 启用 tracing 查看完整执行链路
2. 分析 tool call 的输入输出
3. 检查 memory 的检索效果
4. 优化 prompt 和工具定义

### 场景 3: 性能优化
1. 识别瓶颈 → LLM 调用 / 工具执行 / 记忆检索
2. 应用优化策略 → 缓存 / 批处理 / 流式
3. 监控关键指标 → 延迟 / 成功率 / token 消耗

## Agent 模式对比

| 模式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| ReAct | 通用任务 | 简单、可解释 | 循环可能无限 |
| Planner | 复杂多步 | 结构化、可控 | 规划可能出错 |
| Multi-Agent | 复杂协作 | 专业化、可扩展 | 协调成本高 |
| Tool Use | 需要外部能力 | 能力强 | 工具设计复杂 |

## 自测题

<details>
<summary>Q1: ReAct 模式的 loop 什么时候终止？</summary>

**答案**：
1. **Final Answer**：当 LLM 输出包含特定标记时
2. **Max Iterations**：防止无限循环，设置最大步骤数
3. **Tool Error**：工具执行失败时
4. **User Interrupt**：用户主动中断
5. **Confidence Threshold**：LLM 输出置信度低于阈值

</details>

<details>
<summary>Q2: Multi-Agent 系统如何协调？</summary>

**答案**：
1. **Manager-Scheduler**：中心化管理，分发任务
2. **Kanban**：看板模式，Agent 自主领取任务
3. **黑板模式**：共享状态，Agent 读写同一黑板
4. **Peer-to-Peer**：Agent 间直接通信
5. **混合模式**：Manager + Kanban 结合

</details>

<details>
<summary>Q3: agentmemory 的混合模式是什么？</summary>

**答案**：
- **保留 Hermes 内置记忆**：短对话上下文、会话状态
- **agentmemory 作为增强层**：跨会话持久化、语义检索
- **优势**：不影响现有架构，额外获得长期记忆能力
- **依赖**：iii-engine (v0.11.2) + @agentmemory/agentmemory (npm)

</details>
