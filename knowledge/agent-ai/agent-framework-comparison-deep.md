# Agent 框架深度对比: LangGraph/CrewAI/AutoGen/Bedrock Agents

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、框架选型矩阵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Agent 框架核心能力对比                                    │
├─────────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│     维度        │  LangGraph  │   CrewAI    │   AutoGen   │ Bedrock Agents  │
├─────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ 编排模式        │ 状态图/工作流 │ 角色驱动    │ 对话驱动    │ AWS托管         │
│ 学习曲线        │ 中等        │ 低          │ 高          │ 低              │
│ 企业支持        │ 强          │ 中          │ 中          │ AWS生态         │
│ 多智能体        │ ✅          │ ✅          │ ✅✅✅      │ ✅              │
│ 工具调用        │ ✅✅        │ ✅✅        │ ✅          │ ✅              │
│ 记忆管理        │ 自定义      │ 内置        │ 内置        │ 受限            │
│ 生产就绪        │ ✅✅✅      │ ✅✅        │ ✅          │ ✅✅✅          │
│ 成本            │ 自托管      │ 自托管      │ 自托管      │ AWS付费         │
└─────────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘
```

---

## 二、LangGraph 深度解析

```python
# 文件: frameworks/langgraph_example.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    budget_spend: float
    recommendation: str

# ─── 节点定义 ───
def research_tool(state: AgentState) -> dict:
    """市场调研节点"""
    # 调用市场数据 API
    market_data = fetch_market_data()
    return {"messages": [f"市场数据: {market_data}"]}

def analyze_biddings(state: AgentState) -> dict:
    """竞价分析节点"""
    bids = analyze_bid_history()
    return {"recommendation": bids['optimal_strategy']}

def validate_budget(state: AgentState) -> dict:
    """预算校验节点"""
    budget = state['budget_spend']
    if budget > 10000:
        return {"messages": ["⚠️ 预算超限警告"]}
    return {}

# ─── 构建图 ───
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("research", research_tool)
workflow.add_node("analyze", analyze_biddings)
workflow.add_node("validate", validate_budget)

# 设置入口和条件边
workflow.set_entry_point("research")
workflow.add_edge("research", "analyze")
workflow.add_conditional_edges(
    "analyze",
    lambda x: "validate" if x['budget_spend'] < 10000 else "end",
    {"validate": "validate", "end": END}
)

# 编译
app = workflow.compile()
```

---

## 三、CrewAI 角色系统

```python
# 文件: frameworks/crewai_example.py
from crewai import Agent, Task, Crew, LLM
from tools.market_tools import search_market_data, analyze_competitors

llm = LLM(model="gpt-4", temperature=0.7)

# ─── 角色定义 ───
market_analyst = Agent(
    role="Market Research Analyst",
    goal="分析广告市场趋势和竞争对手动态",
    backstory="""你是拥有10年广告行业经验的分析师，
    擅长数据驱动的市场洞察""",
    llm=llm,
    tools=[search_market_data, analyze_competitors],
    verbose=True
)

bid_optimizer = Agent(
    role="Bidding Strategy Expert",
    goal="优化竞价策略以提升 ROI",
    backstory="专注于程序化广告竞价优化，精通 pCTR/pCVR 预估模型",
    llm=llm,
    tools=[analyze_competitors],
    verbose=True
)

# ─── 任务定义 ───
research_task = Task(
    description="分析目标市场的竞价趋势，识别机会窗口",
    expected_output="市场分析报告，包含关键洞察",
    agent=market_analyst
)

optimization_task = Task(
    description="基于市场数据制定竞价策略",
    expected_output="可执行的竞价优化方案",
    agent=bid_optimizer
)

# ─── 组建 Crew ───
crew = Crew(
    agents=[market_analyst, bid_optimizer],
    tasks=[research_task, optimization_task],
    verbose=2,
    process="sequential"  # 或 "hierarchical"
)

result = crew.kickoff()
```

---

## 四、AutoGen 多智能体协作

```python
# 文件: frameworks/autogen_example.py
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# ─── 代理定义 ───
assistant = AssistantAgent(
    name="Assistant",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "xxx"}]}
)

user_proxy = UserProxyAgent(
    name="User",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=10
)

# ─── 专家代理 ───
data_analyst = AssistantAgent(
    name="DataAnalyst",
    system_message="你擅长数据分析，可以执行 Python 代码",
    llm_config={"config_list": [{"model": "gpt-4"}]}
)

ad_expert = AssistantAgent(
    name="AdExpert",
    system_message="你是广告技术专家，精通 DSP/SSP/RTB",
    llm_config={"config_list": [{"model": "gpt-4"}]}
)

# ─── 群组聊天 ───
groupchat = GroupChat(
    agents=[user_proxy, data_analyst, ad_expert],
    messages=[],
    max_round=10
)

manager = GroupChatManager(groupchat=groupchat)

# ─── 启动对话 ───
user_proxy.initiate_chat(
    manager,
    message="分析当前竞价市场趋势，给出优化建议"
)
```

---

## 五、参考资源

```
官方文档:
├── LangGraph: https://langchain-ai.github.io/langgraph/
├── CrewAI: https://docs.crewai.com/
├── AutoGen: https://microsoft.github.io/autogen/
└── Bedrock: https://aws.amazon.com/bedrock/

实战案例:
├── LangGraph: 广告竞价策略编排
├── CrewAI: 多研究员协作分析
└── AutoGen: 代码生成与审查
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
