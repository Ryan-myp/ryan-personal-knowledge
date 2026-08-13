# Agent 架构深度蒸馏

> 来源：LangChain + MetaGPT 开源源码
> 蒸馏日期：2026-01-15
> 核心价值：生产级 Agent 架构 + 实战设计模式

---

## 一、Agent 核心架构

### 1.1 Agent 循环
```python
# LangChain Agent 核心循环
class AgentExecutor:
    def __init__(self, agent, tools, **kwargs):
        self.agent = agent
        self.tools = tools
        
    def run(self, input_text):
        steps = []
        while True:
            # 1. 思考（LLM 推理）
            output = self.agent.plan(steps, input_text)
            
            # 2. 行动（调用工具）
            action = output.action
            tool_output = self._execute_tool(action.tool, action.tool_input)
            
            # 3. 观察（更新状态）
            steps.append({
                "thought": output.thought,
                "action": action,
                "observation": tool_output
            })
            
            # 4. 判断是否完成
            if output.is_final_answer():
                return output.final_answer
```

### 1.2 Tool Calling 模式
```python
# 工具定义
class SearchTool(BaseTool):
    name = "search"
    description = "搜索互联网信息"
    
    def _run(self, query: str) -> str:
        # 实际搜索逻辑
        return search_engine.query(query)
    
    def _arun(self, query: str) -> str:
        # 异步版本
        return asyncio.run(self._run(query))

# 工具注册
agent = Agent(
    tools=[SearchTool(), CalculatorTool(), CodeInterpreterTool()]
)
```

---

## 二、主流 Agent 模式对比

### 2.1 ReAct Pattern（推理+行动）
```python
# ReAct Prompt Template
REACT_PROMPT = """
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}
"""
```

**实战应用**：
```python
# 广告归因分析 Agent
agent = create_react_agent(
    llm=gpt_4,
    tools=[
        AttributionCalculator(),
        LastTouchAnalyzer(),
        FirstTouchAnalyzer(),
        U-shapedModel()
    ],
    prompt=REACT_PROMPT
)

result = agent.run("""
分析 campaign_id=12345 的归因模式
比较 Last Touch 和 U-Shaped 模型的差异
""")
```

### 2.2 Plan-and-Solve Pattern
```python
# Plan-and-Solve 实现
class PlanAndSolveAgent:
    def __init__(self, llm):
        self.llm = llm
        
    def solve(self, problem: str) -> str:
        # Step 1: 生成计划
        plan = self.llm.generate(f"""
        Generate a step-by-step plan to solve: {problem}
        Output the plan as a numbered list.
        """)
        
        # Step 2: 执行计划
        result = ""
        for step in plan.steps:
            step_result = self.execute_step(step)
            result += step_result
            
        return result
```

**优势**：
```
✅ 复杂任务分解清晰
✅ 便于理解和调试
✅ 可并行执行独立步骤
```

### 2.3 Reflection Pattern
```python
# Reflection 实现
class ReflectiveAgent:
    def reflect(self, thought: str, action: str, observation: str) -> str:
        feedback = self.llm.generate(f"""
        Evaluate the following thought-action-observation cycle:
        
        Thought: {thought}
        Action: {action}
        Observation: {observation}
        
        Is the thought logical?
        Did the action achieve the desired result?
        What should be improved?
        
        Provide constructive feedback.
        """)
        return feedback
```

---

## 三、MetaGPT 多 Agent 架构

### 3.1 核心架构
```python
# MetaGPT 多 Agent 系统
class Team:
    def __init__(self, context: Context):
        self.context = context
        self.roles = []  # 角色列表
        
    def add_role(self, role: Role):
        """添加角色"""
        self.roles.append(role)
        
    def run(self, requirement: str):
        """运行团队"""
        # 1. 产品 manager 分析需求
        product_manager = self.get_role("ProductManager")
        product_spec = product_manager.analyze(requirement)
        
        # 2. 架构师设计系统
        architect = self.get_role("Architect")
        architecture = architect.design(product_spec)
        
        # 3. 工程师实现代码
        engineer = self.get_role("Engineer")
        code = engineer.implement(architecture)
        
        # 4. 测试工程师验证
        tester = self.get_role("TestEngineer")
        test_result = tester.verify(code)
        
        return test_result
```

### 3.2 角色定义
```python
# 角色类定义
class Role:
    def __init__(self, name: str, goal: str, constraints: str = ""):
        self.name = name
        self.goal = goal
        self.constraints = constraints
        self.profile = f"""
        You are {name}.
        Your goal: {goal}
        Your constraints: {constraints}
        """
        
    def think(self, message: str) -> str:
        """思考"""
        return self.llm.generate(f"{self.profile}\n\n{message}")
    
    def act(self, thought: str) -> Action:
        """执行行动"""
        return self.parse_action(thought)
```

---

## 四、实战案例：广告竞价 Agent

### 4.1 Agent 设计
```python
# 广告竞价系统 Agent
class BiddingAgent:
    def __init__(self):
        self.tools = [
            RealtimeBiddingAPI(),      # 实时竞价接口
            UserProfileStore(),        # 用户画像存储
            BidStrategyEngine(),       # 出价策略引擎
            BudgetOptimizer(),         # 预算优化器
            FraudDetector()            # 反欺诈检测
        ]
        
    async def handle_request(self, bid_request: BidRequest) -> BidResponse:
        """处理竞价请求"""
        
        # Step 1: 用户画像查询
        user_profile = await self.user_profile_store.get(bid_request.user_id)
        
        # Step 2: 历史出价分析
        history = await self.bid_history.get(bid_request.campaign_id)
        
        # Step 3: 策略计算
        bid_price = await self.strategy_engine.calculate(
            user_profile=user_profile,
            history=history,
            request=bid_request
        )
        
        # Step 4: 预算检查
        if not await self.budget_optimizer.check(bid_request.campaign_id, bid_price):
            return BidResponse(skipped=True)
        
        # Step 5: 反欺诈检查
        fraud_score = await self.fraud_detector.score(bid_request)
        if fraud_score > 0.8:
            return BidResponse(skipped=True, reason="fraud")
        
        return BidResponse(price=bid_price, fraud_score=fraud_score)
```

### 4.2 多 Agent 协作
```python
# 多 Agent 协作架构
class AdSystemTeam:
    def __init__(self):
        self.agents = {
            "bidder": BiddingAgent(),
            "allocator": BudgetAllocator(),
            "analyzer": PerformanceAnalyzer(),
            "optimizer": StrategyOptimizer()
        }
        
    async def run_cycle(self):
        """运行一个优化周期"""
        
        # 1. 竞价 Agent 处理请求
        bid_results = await self.agents["bidder"].process_all_requests()
        
        # 2. 分配 Agent 优化预算分配
        allocation = await self.agents["allocator"].optimize(bid_results)
        
        # 3. 分析 Agent 评估效果
        insights = await self.agents["analyzer"].analyze(bid_results)
        
        # 4. 优化 Agent 调整策略
        strategies = await self.agents["optimizer"].suggest(insights)
        
        return {
            "allocation": allocation,
            "insights": insights,
            "strategies": strategies
        }
```

---

## 五、核心设计模式总结

### 5.1 工具调用模式
```
Pattern: Tool Calling
适用：需要调用外部 API 的场景
关键：工具定义要清晰，错误处理要完善
```

### 5.2 记忆管理模式
```
Pattern: Memory Management
适用：需要多轮对话的场景
关键：短期记忆（会话）+ 长期记忆（持久化）
```

### 5.3 反思优化模式
```
Pattern: Reflection & Optimization
适用：复杂任务需要自我改进的场景
关键：设计有效的评估反馈机制
```

### 5.4 多 Agent 协作模式
```
Pattern: Multi-Agent Collaboration
适用：复杂业务流程需要分工的场景
关键：角色定义清晰，接口标准化
```

---

## 六、实战经验教训

### 6.1 常见的陷阱
```
❌ 过度依赖 LLM 推理
   → 解决：明确边界，该用规则时用规则
   
❌ 工具调用链路过长
   → 解决：扁平化设计，减少中间环节
   
❌ 忽略错误恢复
   → 解决：设计 fallback 机制
   
❌ 没有成本控制
   → 解决：设置 token 预算和超时限制
```

### 6.2 最佳实践
```
✅ 明确的输入输出契约
✅ 完善的日志和监控
✅ 渐进式复杂度
✅ 人工审核关键决策
✅ A/B 测试验证效果
```

---

**核心洞察**：Agent 的本质是"感知-思考-行动"的闭环，关键是设计好每个环节的接口和容错机制。多 Agent 系统的核心是角色分工和协作协议。
