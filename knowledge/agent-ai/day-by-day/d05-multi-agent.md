# Day 5: 多 Agent 系统 — 从入门到源码级

> 学习目标: 先理解多 Agent 是什么、为什么需要，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 5.1 为什么需要多 Agent？

```
单 Agent 的局限:
1. 复杂任务需要分工
2. 不同领域需要不同专业知识
3. 串行执行效率低
4. 错误传播（一个失败全盘失败）

多 Agent 的优势:
1. 并行执行提高效率
2. 互相审查提高质量
3. 专业分工提升效果
4. 容错性更强
```

### 5.2 4 种协作模式

```
1. 流水线模式
   Agent1 → Agent2 → Agent3 → 最终输出
   适用: 任务可分解为串行步骤

2. 层级模式
          Manager Agent
          /    |    \
    AgentA AgentB AgentC
   适用: 需要统一协调

3. 辩论模式
    AgentA ↔ AgentB ↔ AgentC → 最终决定
   适用: 需要多角度评估

4. 工具调用模式
    Agent1 调用 Agent2 作为工具
   适用: 一个 Agent 需要另一个的专业能力
```

### 5.3 快速体验

```python
# 安装依赖
pip install langgraph langchain langchain-openai

from langgraph.graph import StateGraph
from typing import TypedDict, List

# 定义状态
class AgentState(TypedDict):
    messages: List[str]
    summary: str
    action_plan: str

# 定义 Agent
def summarize_agent(state: AgentState) -> AgentState:
    """摘要 Agent"""
    content = " ".join(state["messages"])
    summary = f"[摘要] {content[:100]}..."
    return {"summary": summary, "action_plan": state["action_plan"]}

def plan_agent(state: AgentState) -> AgentState:
    """规划 Agent"""
    plan = "步骤1: 阅读 → 步骤2: 分析 → 步骤3: 总结"
    return {"action_plan": plan}

def execute_agent(state: AgentState) -> AgentState:
    """执行 Agent"""
    return {"messages": ["完成！"]}

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("summarize", summarize_agent)
workflow.add_node("plan", plan_agent)
workflow.add_node("execute", execute_agent)

workflow.set_entry_point("summarize")
workflow.add_edge("summarize", "plan")
workflow.add_edge("plan", "execute")
workflow.add_edge("execute", "__end__")

app = workflow.compile()

# 运行
result = app.invoke({
    "messages": ["这是一份关于 Agent 技术的研究文档..."],
    "summary": "",
    "action_plan": ""
})
print(result)
```

### 5.4 关键概念总结

| 概念 | 说明 |
|------|------|
| **流水线模式** | 串行执行，每个 Agent 处理一步 |
| **层级模式** | 有 Manager Agent 统一协调 |
| **辩论模式** | 多个 Agent 互相辩论，达成共识 |
| **工具调用模式** | Agent 把另一个 Agent 当工具调用 |

---

## 第二部分：源码级深度剖析

### 5.5 LangGraph 源码分析

```python
# langgraph/graph/graph.py
# LangGraph 图定义

class StateGraph(Generic[State]):
    """
    状态图
    
    核心概念:
    ├── State: Agent 共享的状态
    ├── Node: 一个 Agent（或一组 Agent）
    ├── Edge: 节点之间的边
    └── ConditionalEdge: 条件分支
    
    使用流程:
    1. 定义 State
    2. 定义 Node（Agent 函数）
    3. 定义 Edge
    4. 编译图
    5. 运行
    """
    
    def __init__(self, input: Optional[Type[State]] = None):
        self.input = input
        self.nodes = {}  # node_name -> node_func
        self.edges = []  # 边列表
        self.conditions = {}  # 条件分支
    
    def add_node(self, name: str, func: Callable):
        """添加节点（Agent）"""
        self.nodes[name] = func
    
    def add_edge(self, start: str, end: str):
        """添加边"""
        self.edges.append((start, end))
    
    def set_entry_point(self, name: str):
        """设置入口节点"""
        self.entry_point = name
    
    def compile(self):
        """编译图"""
        # 1. 验证图结构
        self._validate_graph()
        
        # 2. 构建执行器
        executor = GraphExecutor(
            nodes=self.nodes,
            edges=self.edges,
            conditions=self.conditions,
            entry_point=self.entry_point,
        )
        
        return executor
    
    def _validate_graph(self):
        """验证图结构"""
        # 检查入口节点是否存在
        if self.entry_point not in self.nodes:
            raise ValueError(f"Entry point {self.entry_point} not found")
        
        # 检查所有边是否有效
        for start, end in self.edges:
            if start not in self.nodes:
                raise ValueError(f"Node {start} not found")
            if end not in self.nodes and end != "__end__":
                raise ValueError(f"Node {end} not found")
```

### 5.6 节点执行源码

```python
# langgraph/graph/executor.py
# 图执行器

class GraphExecutor:
    """
    图执行器
    
    执行流程:
    1. 从入口节点开始
    2. 执行节点函数
    3. 更新共享状态
    4. 根据边决定下一步
    5. 循环直到结束
    """
    
    def __init__(self, nodes, edges, conditions, entry_point):
        self.nodes = nodes
        self.edges = edges
        self.conditions = conditions
        self.entry_point = entry_point
    
    def invoke(self, initial_state: State) -> State:
        """
        执行图
        
        流程:
        1. 设置初始状态
        2. 从入口节点开始
        3. 执行节点函数
        4. 更新状态
        5. 决定下一步
        6. 循环直到结束
        """
        state = initial_state.copy()
        current_node = self.entry_point
        visited = set()  # 检测循环
        
        while current_node != "__end__":
            # 检查循环
            if current_node in visited:
                raise Exception(f"Loop detected: {current_node}")
            visited.add(current_node)
            
            # 获取节点函数
            node_func = self.nodes[current_node]
            
            # 执行节点
            state = node_func(state)
            
            # 决定下一步
            next_node = self._get_next_node(current_node, state)
            current_node = next_node
        
        return state
    
    def _get_next_node(self, current_node: str, state: State) -> str:
        """获取下一个节点"""
        # 检查是否有条件分支
        if current_node in self.conditions:
            return self.conditions[current_node](state)
        
        # 否则使用默认边
        for start, end in self.edges:
            if start == current_node:
                return end
        
        return "__end__"
```

### 5.7 多 Agent 通信机制

```python
# langgraph/graph/communication.py
# Agent 间通信

class AgentCommunication:
    """
    Agent 间通信机制
    
    支持:
    ├── 直接通信: AgentA → AgentB
    ├── 广播: Agent → 所有 Agent
    └── 发布-订阅: Agent 发布事件，其他订阅
    """
    
    def __init__(self):
        self.channels = {}  # channel_name -> [messages]
    
    def publish(self, channel: str, message: Any):
        """发布消息到频道"""
        if channel not in self.channels:
            self.channels[channel] = []
        self.channels[channel].append(message)
    
    def subscribe(self, channel: str) -> List[Any]:
        """订阅频道并获取消息"""
        return self.channels.get(channel, [])
    
    def broadcast(self, message: Any):
        """广播到所有频道"""
        for channel in self.channels:
            self.channels[channel].append(message)
```

---

## 第三部分：自测

### 问题 1
什么时候应该用多 Agent？
<details>
<summary>查看答案</summary>

- 复杂任务需要分工
- 需要并行执行
- 需要互相审查
- 需要专业领域知识
</details>

### 问题 2
4 种协作模式的区别是什么？
<details>
<summary>查看答案</summary>

- 流水线: 串行执行
- 层级: Manager 协调
- 辩论: 互相评估
- 工具调用: 互当工具
</details>

### 问题 3
LangGraph 的编译流程是什么？
<details>
<summary>查看答案</summary>

1. 定义 State
2. 定义 Node
3. 定义 Edge
4. 编译图
5. 执行
</details>

---

## 第四部分：动手验证

### 5.1 运行多 Agent 流水线

```python
# 见上方的快速体验代码
```

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
