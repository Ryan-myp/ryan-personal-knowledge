# 前沿洞察笔记

> 通过 blogwatcher/arxiv 收集的 LLM/Agent/MLOps 前沿洞察

## 2026-06

### 2026-06-08 — Agent 编排的最新趋势

**来源**: 基于 Hermes 实际使用经验总结
**标签**: #agent #orchestration #multi-agent
**重要度**: ⭐⭐⭐⭐⭐

**核心观点**:
- 多 Agent 编排正在从"手动规则"向"智能路由"演进
- RRF (Reciprocal Rank Fusion) 融合策略在知识检索中效果显著
- delegate_task 的子代理隔离模式是生产级 Agent 系统的关键设计
- Skill 蒸馏是经验复用的核心机制——把排障经验写成 SKILL.md

**对我们的意义**:
- Hermes 的 delegate_task + Skills + Memory 架构已经覆盖了现代 Agent 编排的核心模式
- 下一步可以关注：多 Agent 协作的自动发现、Skill 的自动进化
- 广告平台的 ad-ai-coding 就是 RRF 融合的实战案例
