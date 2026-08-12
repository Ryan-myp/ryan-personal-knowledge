---
name: agent-observability-expert
description: "Agent 可观测性专家技能 — 链路追踪、日志分析、性能监控、调试方法"
version: 1.0.0
author: ryan
tags: [agent, observability, tracing, debugging, monitoring, expert]
---

# Agent 可观测性专家技能

> 从链路追踪到性能优化，掌握生产级 Agent 系统可观测性

## 核心能力

### 1. 链路追踪 (Tracing)
- **Trace 结构**：Span、Parent-Child 关系、Context Propagation
- **分布式追踪**：OpenTelemetry、Jaeger、Tempo
- **Agent 专属**：Tool Call 追踪、Memory 检索追踪、决策点记录
- **采样策略**：全量/按延迟/按错误率采样

### 2. 日志体系
- **结构化日志**：JSON 格式、统一字段
- **日志级别**：DEBUG/INFO/WARN/ERROR
- **日志采集**：Fluentbit/Filebeat → Loki/ES
- **日志查询**：LogQL、Kibana、CloudWatch

### 3. 性能监控
- **指标体系**：QPS、延迟、成功率、Token 消耗
- **关键指标**：
  - Tool Call 延迟分布
  - LLM 响应时间
  - Memory 检索延迟
  - Token 消耗趋势
- **告警策略**：阈值告警、异常检测告警

### 4. 调试方法
- **交互式调试**：Step-by-step 执行、断点
- **Replay 调试**：重放历史请求
- **A/B 对比**：不同配置的并行对比
- **慢查询分析**：定位性能瓶颈

## 知识库引用

| 主题 | 文档 |
|------|------|
| Agent 可观测性 | `knowledge/agent-ai/day-by-day/d07-security-observability.md` |
| 系统可观测性 | `knowledge/advertising/ad-observability-deep.md` |
| 性能监控 | `knowledge/fullstack/observability-deep-dive.md` |
| 链路追踪 | `knowledge/middleware/ad-elasticsearch-deep.md` |

## 使用场景

### 场景 1: 设计可观测性方案
1. 确定追踪粒度（请求级/对话级/步骤级）
2. 选择追踪后端（Jaeger/Tempo/Loki）
3. 定义关键指标和告警规则
4. 实现日志采集和查询

### 场景 2: 排查 Agent 问题
1. 查看 Trace 定位问题环节
2. 分析 Tool Call 输入输出
3. 检查 Memory 检索结果
4. 定位性能瓶颈

### 场景 3: 性能优化
1. 分析 P99 延迟分布
2. 识别慢查询和重复计算
3. 应用缓存和批处理
4. 验证优化效果

## 关键指标

```yaml
# Agent 核心监控指标
metrics:
  agent:
    requests_total: "总请求数"
    requests_failed: "失败请求数"
    latency_p50_ms: "P50 延迟"
    latency_p99_ms: "P99 延迟"
    tokens_consumed: "Token 消耗"
    tool_calls_total: "工具调用总数"
    tool_calls_failed: "工具调用失败数"
    memory_retrievals: "记忆检索次数"
    memory_hit_rate: "记忆命中率"
```

## 自测题

<details>
<summary>Q1: Agent 系统的 Tracing 和普通 API 有什么不同？</summary>

**答案**：
1. **嵌套结构**：Agent 有 ReAct 循环，trace 是嵌套的
2. **Tool Call**：每次工具调用是一个子 Span
3. **Memory 操作**：记忆检索和写入需要单独追踪
4. **LLM 调用**：需要记录 prompt 和 response
5. **决策点**：Agent 的决策分支需要标记

</details>

<details>
<summary>Q2: 如何设计 Agent 的告警策略？</summary>

**答案**：
1. **错误率告警**：失败率 > 5% 持续 5 分钟
2. **延迟告警**：P99 > 5s 或增长超过 20%
3. **Token 告警**：单日消耗超过预算
4. **工具告警**：特定工具连续失败
5. **记忆告警**：记忆检索成功率下降

</details>

<details>
<summary>Q3: Replay 调试的原理是什么？</summary>

**答案**：
1. **请求录制**：记录原始请求和配置
2. **结果回放**：使用相同输入重新执行
3. **对比分析**：对比不同版本的输出差异
4. **应用场景**：
   - Prompt 优化验证
   - 模型升级效果对比
   - 配置变更影响评估

</details>
