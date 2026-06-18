# 微信读书精华：Agent设计模式 蒸馏笔记

> 来源：《Agent设计模式 图解可复用智能体架构》- 黄佳
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：Agent 核心模式

### 1. ReAct 模式（Reasoning + Acting）

```
核心思想：让 Agent 交替进行"思考"和"行动"

流程：
Thought → Action → Observation → Thought → Action → ... → Answer

示例：
Thought: 用户想查广告数据，我需要调用查询工具
Action: query_ad_data(platform="facebook", metric="impressions")
Observation: {"impressions": 1500000, "clicks": 5000, "ctr": 0.33%}
Thought: CTR 低于行业均值，建议优化创意
Answer: 本周 Facebook 广告 CTR 为 0.33%，低于行业均值 0.5%，建议优化创意素材

代码模式：
class ReActAgent:
    def run(self, query):
        while not self.is_finished():
            thought = self.llm.think(query, self.observation_history)
            action = self.llm.choose_action(thought, self.available_tools)
            observation = self.tool_executor.execute(action)
            self.observation_history.append((thought, action, observation))
        return self.llm.final_answer(self.observation_history)
```

### 2. Plan-and-Execute 模式

```
核心思想：先规划再执行，适合多步骤任务

流程：
1. 分析任务 → 生成计划（步骤列表）
2. 执行步骤 1 → 检查结果
3. 执行步骤 2 → 检查结果
4. ...
5. 汇总结果

适用场景：
- 广告创建（选品 → 建计划 → 建策略 → 上传素材 → 发布）
- 数据分析（拉数据 → 清洗 → 分析 → 生成报告）
- 多平台投放（Facebook → Google → TikTok）

代码模式：
class PlanExecuteAgent:
    def run(self, task):
        plan = self.llm.create_plan(task)
        for step in plan.steps:
            result = self.execute_step(step)
            if result.failed:
                plan = self.llm.replan(plan, result.error)
            self.progress.append(result)
        return self.summarize(self.progress)
```

### 3. Reflection 模式

```
核心思想：Agent 对自己的输出进行反思和改进

流程：
1. 生成初稿
2. 反思：检查是否有错误/遗漏
3. 改进：修正问题
4. 再反思：确认改进是否充分

适用场景：
- 广告文案优化
- 代码审查
- 报告生成

代码模式：
class ReflectionAgent:
    def run(self, task, iterations=3):
        draft = self.llm.generate(task)
        for i in range(iterations):
            critique = self.llm.reflect(draft, criteria=self.checklist)
            improved = self.llm.improve(draft, critique)
            draft = improved
        return draft
```

---

## 第二部分：高级模式

### 4. Multi-Agent Collaboration

```
核心思想：多个 Agent 协作完成复杂任务

角色分工：
- Coordinator：任务分发和结果汇总
- Planner：制定执行计划
- Executor：执行具体任务
- Reviewer：审查结果质量

通信方式：
- 消息队列（异步）
- 共享内存（同步）
- API 调用（RPC）

适用场景：
- 大型广告活动管理
- 多平台内容生成
- 复杂数据分析

代码模式：
class MultiAgentSystem:
    def run(self, task):
        coordinator = CoordinatorAgent()
        plan = coordinator.plan(task)
        results = []
        for step in plan.steps:
            agent = self.get_agent_for_step(step)
            result = agent.execute(step)
            results.append(result)
        return coordinator.aggregate(results)
```

### 5. Tool-Use Agent

```
核心思想：Agent 通过工具扩展能力

工具类型：
- 查询工具：获取数据（API、数据库）
- 计算工具：执行计算
- 操作工具：修改状态（创建、更新、删除）
- 生成工具：生成内容（文案、图片）

安全考虑：
- 工具权限分级
- 高危操作需要确认
- 操作审计日志

代码模式：
class ToolUseAgent:
    def run(self, task):
        tools = self.register_tools()
        while not self.is_done():
            action = self.llm.decide_action(task, tools)
            if action.is_tool_call():
                result = tools[action.tool_name].execute(action.args)
                self.update_context(result)
            else:
                return self.llm.answer(task)
```

### 6. Memory-Augmented Agent

```
核心思想：Agent 具有记忆能力，可以学习和适应

记忆类型：
- 短期记忆：当前对话上下文
- 长期记忆：用户偏好、历史行为
- 工作记忆：当前任务的中间状态

应用场景：
- 个性化推荐
- 用户画像更新
- 策略优化

代码模式：
class MemoryAgent:
    def run(self, task, user_id):
        short_term = self.get_context(task)
        long_term = self.memory_store.get(user_id)
        combined = self.merge(short_term, long_term)
        response = self.llm.generate(combined)
        self.memory_store.update(user_id, response)
        return response
```

---

## 第三部分：模式选择指南

```
任务复杂度 vs 模式选择：
┌────────────────┬──────────────────┬──────────────────┐
│    任务类型     │     推荐模式      │     复杂度       │
├────────────────┼──────────────────┼──────────────────┤
│ 简单查询       │ Tool-Use         │ ⭐              │
│ 多步操作       │ Plan-and-Execute │ ⭐⭐            │
│ 需要反思改进   │ Reflection       │ ⭐⭐            │
│ 复杂协作       │ Multi-Agent      │ ⭐⭐⭐          │
│ 个性化服务     │ Memory-Augmented │ ⭐⭐⭐          │
│ 通用场景       │ ReAct            │ ⭐⭐            │
└────────────────┴──────────────────┴──────────────────┘

组合使用：
ReAct + Memory → 有记忆的交互式 Agent
Plan-and-Execute + Multi-Agent → 分布式复杂任务处理
Reflection + Tool-Use → 高质量工具调用结果
```

---

## 第四部分：实践建议

### 1. 从小开始

```
起步建议：
1. 先用 ReAct 模式处理简单任务
2. 验证可行后，逐步增加 Memory
3. 复杂任务再引入 Multi-Agent
```

### 2. 注重安全

```
安全要点：
1. 工具调用需要权限控制
2. 高危操作需要二次确认
3. 所有操作记录审计日志
4. 定期审查 Agent 行为
```

### 3. 持续优化

```
优化方向：
1. 收集用户反馈，改进 Prompt
2. 监控 Agent 性能，优化响应时间
3. 定期更新工具和能力
4. A/B 测试不同模式的效果
```

---

## 第五部分：自测题

### Q1: ReAct 模式的核心是什么？

**A**: 交替进行思考和行动，每一步都有观察反馈。

### Q2: 什么时候用 Multi-Agent？

**A**: 任务复杂、需要多种专业技能、可以并行处理时。

### Q3: Memory-Augmented Agent 的记忆分几种？

**A**: 短期（对话上下文）、长期（用户偏好）、工作（任务中间状态）。

---

## 第六部分：与 dap-agent 的对照

```
dap-agent 使用的模式：
✅ ReAct: planning/agent.go 中的 planWithStandardADK
✅ Tool-Use: MCPToolCaller 调用 DAP Admin API
✅ Memory: 6 层记忆系统
✅ Plan-and-Execute: workflow.yaml 定义的步骤序列
✅ Reflection: slot_guard 校验 + 用户确认
✅ Multi-Agent: Dispatcher 分发到不同 Agent

缺失的模式：
❌ 完整的 Reflection 迭代（只有 slot_guard 校验）
❌ 高级 Memory 检索（episodic 有但没用到）
```
