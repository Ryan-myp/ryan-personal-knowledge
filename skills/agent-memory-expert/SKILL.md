---
name: agent-memory-expert
description: "Agent 记忆专家技能 — 持久化记忆架构、agentmemory 集成、记忆检索优化"
version: 1.0.0
author: ryan
tags: [agent, memory, agentmemory, retrieval, expert]
---

# Agent 记忆专家技能

> 从短期上下文到长期记忆，掌握生产级 Agent 记忆系统

## 核心能力

### 1. 记忆分类
- **工作记忆 (Working Memory)**：当前对话上下文
- **短期记忆 (Short-term)**：最近 N 轮对话
- **长期记忆 (Long-term)**：跨会话持久化
- **语义记忆 (Semantic)**：事实和知识
- **程序性记忆 (Procedural)**：技能和流程
- **情景记忆 (Episodic)**：具体事件和经历

### 2. agentmemory 集成
- **架构**：iii-engine (v0.11.2) + @agentmemory/agentmemory (npm)
- **混合模式**：Hermes 内置记忆 + agentmemory 增强层
- **存储后端**：PostgreSQL + pgvector
- **检索策略**：向量检索 + 关键词检索

### 3. 记忆检索
- **向量检索**：Embedding 相似度搜索
- **关键词检索**：BM25 全文检索
- **混合检索**：向量 + 关键词 RRF 融合
- **时间衰减**：基于时间的记忆重要性调整

### 4. 记忆管理
- **写入策略**：自动摘要、关键信息提取
- **更新策略**：记忆修正、冲突解决
- **遗忘策略**：过期清理、重要性衰减
- **压缩策略**：摘要生成、信息压缩

## 知识库引用

| 主题 | 文档 |
|------|------|
| agentmemory 集成 | `knowledge/agent-ai/agentmemory-deep-dive.md` |
| agentmemory 分析 | `knowledge/agent-ai/archive/agentmemory-analysis.md` |
| agentmemory 集成指南 | `references/agentmemory-integration.md` |
| 记忆架构 | `knowledge/agent-ai/agentmemory-deep-dive.md` |

## 使用场景

### 场景 1: 集成 agentmemory
1. 参考 `references/agentmemory-integration.md`
2. 配置 iii-engine 和 npm 包
3. 设计混合记忆架构
4. 测试记忆写入和检索

### 场景 2: 优化记忆检索
1. 分析检索准确度
2. 调整 Embedding 模型
3. 优化检索策略（向量+关键词）
4. 引入时间衰减因子

### 场景 3: 记忆管理策略
1. 设计写入触发条件
2. 实现记忆压缩和摘要
3. 配置过期清理策略
4. 建立人工审核机制

## 混合模式架构

```
┌─────────────────────────────────────────┐
│           Agent 记忆系统                  │
├─────────────────────────────────────────┤
│  短期记忆 (Hermes 内置)                  │
│  ├── 当前对话上下文                      │
│  └── 最近 N 轮对话                       │
├─────────────────────────────────────────┤
│  长期记忆 (agentmemory)                  │
│  ├── 语义记忆 (事实知识)                 │
│  ├── 程序性记忆 (技能流程)               │
│  └── 情景记忆 (事件经历)                 │
├─────────────────────────────────────────┤
│  检索层                                  │
│  ├── 向量检索 (pgvector)                │
│  ├── 关键词检索 (PG full-text)          │
│  └── RRF 融合                            │
└─────────────────────────────────────────┘
```

## 自测题

<details>
<summary>Q1: 为什么需要混合记忆模式而不是只用一种？</summary>

**答案**：
1. **短期记忆**：对话上下文需要快速访问，内置内存最快
2. **长期记忆**：跨会话信息需要持久化，向量数据库适合
3. **职责分离**：各司其职，避免单一系统过载
4. **成本优化**：短期用小内存，长期用廉价存储
5. **灵活性**：可以根据场景选择不同的记忆策略

</details>

<details>
<summary>Q2: 记忆写入的触发条件有哪些？</summary>

**答案**：
1. **周期性写入**：每隔 N 轮对话写入一次
2. **事件触发**：重要事件、决策、结论时写入
3. **用户要求**：用户明确要求记住某些信息
4. **系统判断**：LLM 判断信息重要性后写入
5. **混合策略**：周期 + 事件 + LLM 判断结合

</details>

<details>
<summary>Q3: 如何处理记忆冲突？</summary>

**答案**：
1. **时间优先**：新信息覆盖旧信息
2. **置信度加权**：高置信度信息优先
3. **来源追溯**：追溯信息来源可靠性
4. **人工审核**：冲突严重时无人机审核
5. **版本记录**：保留历史版本，支持回溯

</details>
