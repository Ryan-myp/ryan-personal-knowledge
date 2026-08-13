# Agent 编排框架 v2 - 资深专家深度实现

## 一、框架对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent 编排框架对比 (v2)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   框架          | 复杂度 | 学习曲线 | 灵活性 | 生产就绪 | 社区规模      │
│   ──────────────┼────────┼──────────┼────────┼──────────┼─────────────  │
│   LangGraph     | 中     | 平缓     | 高     | ✅        | ⭐⭐⭐⭐⭐    │
│   CrewAI        | 低     | 平缓     | 中     | ✅        | ⭐⭐⭐⭐      │
│   AutoGen       | 高     | 陡峭     | 极高   | ⚠️       | ⭐⭐⭐       │
│   Semantic Kernel| 中   | 平缓     | 高     | ✅        | ⭐⭐⭐⭐      │
│   LlamaIndex    | 低     | 平缓     | 中     | ✅        | ⭐⭐⭐⭐⭐    │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、LangGraph v2 实现

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    next_step: str
    tool_calls: List[dict]
    final_answer: str

class AgenticOrchestrationV2:
    """Agent编排框架v2"""
    
    def __init__(self):
        self.graph = StateGraph(AgentState)
        self.tools = {}
        self.agents = {}
        
    def add_agent(self, name: str, agent_func):
        """添加Agent"""
        self.agents[name] = agent_func
        self.graph.add_node(name, agent_func)
        
    def add_tool(self, name: str, tool_func):
        """添加工具"""
        self.tools[name] = tool_func
        
    def add_edge(self, from_node: str, to_node: str):
        """添加边"""
        self.graph.add_edge(from_node, to_node)
        
    def add_conditional_edge(self, from_node: str, condition_func: callable, paths: dict):
        """添加条件边"""
        self.graph.add_conditional_edges(from_node, condition_func, paths)
        
    def compile(self):
        """编译图"""
        return self.graph.compile()
    
    def run(self, initial_state: AgentState) -> AgentState:
        """运行Agent"""
        app = self.compile()
        return app.invoke(initial_state)
```

## 三、CrewAI v2 实现

```python
from crewai import Agent, Task, Crew, LLM
from langchain_openai import ChatOpenAI

class CrewAIV2:
    """CrewAI编排框架v2"""
    
    def __init__(self):
        self.agents = []
        self.tasks = []
        self.crew = None
        
    def create_agent(self, name: str, role: str, goal: str, backstory: str, llm=None):
        """创建Agent"""
        if llm is None:
            llm = LLM(model="gpt-4o", temperature=0.7)
            
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            verbose=True,
            allow_delegation=True,
        )
        self.agents.append(agent)
        return agent
    
    def create_task(self, name: str, agent: Agent, expected_output: str, 
                    description: str, tools=None):
        """创建任务"""
        task = Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            tools=tools or [],
        )
        self.tasks.append(task)
        return task
    
    def run(self, verbose: bool = True) -> str:
        """运行Crew"""
        self.crew = Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=verbose,
            process="sequential",  # 或 "hierarchical"
        )
        
        result = self.crew.kickoff()
        return result
```

## 四、面试高频题

### Q1: LangGraph和CrewAI有什么区别？

```
A:
1. LangGraph: 基于图的状态机，灵活可控
2. CrewAI: 基于角色的团队协作，简单直观
```

### Q2: 如何实现Agent并行？

```
A:
1. 使用async/await
2. 线程池并发
3. 分布式队列
```

## 五、自测题

1. 解释LangGraph工作原理
2. 如何实现Agent并行？
3. 如何处理Agent错误？

---

## 参考文档

- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [CrewAI](https://docs.crewai.com/)
