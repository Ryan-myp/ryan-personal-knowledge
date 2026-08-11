# 智能体架构深度解析

> 深入解析 Agent 系统的核心架构：规划器、执行器、记忆系统、工具调用。
> 基于 Hermes Agent 和主流 Agent 框架的实际实现。

---

## 1. Agent 核心架构

### 1.1 经典 ReAct 模式

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ReAct Loop                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Thought → Action → Observation → Thought → Action → ... → Answer  │
│    │        │         │              │         │                    │
│    ▼        ▼         ▼              ▼         ▼                    │
│  推理    工具调用   结果观察      推理     工具调用                  │
│  (LLM)   (Tool)    (System)     (LLM)    (Tool)                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 规划-执行架构

```go
type Agent struct {
    Planner    Planner      // 规划器：生成任务计划
    Executor   Executor     // 执行器：执行具体任务
    Memory     Memory       // 记忆系统：短期/长期记忆
    Tools      []Tool       // 可用工具集
}

type Planner interface {
    Plan(task string, context Context) (*Plan, error)
}

type Executor interface {
    Execute(step Step, context Context) (*Result, error)
}
```

---

## 2. 规划器设计

### 2.1 Chain of Thought (CoT)

```python
# CoT prompt 模板
COT_PROMPT = """
请逐步思考以下问题：

问题：{question}

思考过程：
1. 首先，我需要理解问题的核心...
2. 然后，我需要考虑...
3. 接下来，我会...
4. 最后，我得出结论...

答案：
"""
```

### 2.2 Tree of Thoughts (ToT)

```python
class ThoughtNode:
    def __init__(self, thought: str, parent=None):
        self.thought = thought
        self.parent = parent
        self.children = []
        self.score = 0.0
    
    def add_child(self, child: 'ThoughtNode'):
        self.children.append(child)
        child.parent = self
    
    def evaluate(self, context) -> float:
        # 评估当前思考的价值
        return self.score

class TreeOfThoughts:
    def __init__(self, llm_client, max_depth=3, branching_factor=3):
        self.llm = llm_client
        self.max_depth = max_depth
        self.branching = branching_factor
    
    def solve(self, problem: str) -> str:
        root = ThoughtNode(problem)
        self.bfs_search(root)
        return self.extract_solution(root)
    
    def bfs_search(self, root: ThoughtNode):
        queue = [root]
        
        while queue:
            node = queue.pop(0)
            
            if self.is_leaf(node) or node.depth >= self.max_depth:
                continue
            
            # 生成多个思考分支
            thoughts = self.generate_thoughts(node.thought)
            for thought in thoughts[:self.branching]:
                child = ThoughtNode(thought, node)
                child.score = self.evaluate(child)
                node.add_child(child)
                queue.append(child)
```

---

## 3. 执行器设计

### 3.1 Tool Calling

```python
class ToolCall:
    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = arguments
        self.result = None

class ToolExecutor:
    def __init__(self, tools: Dict[str, Callable]):
        self.tools = tools
    
    def execute(self, call: ToolCall) -> str:
        tool = self.tools.get(call.name)
        if not tool:
            return f"Error: Tool '{call.name}' not found"
        
        try:
            result = tool(**call.arguments)
            call.result = result
            return json.dumps(result)
        except Exception as e:
            return f"Error: {str(e)}"

# 工具注册
@tool_executor.register("read_file")
def read_file(path: str, offset: int = 1, limit: int = 100) -> dict:
    """读取文件内容"""
    with open(path, 'r') as f:
        lines = f.readlines()
    return {
        "content": "".join(lines[offset-1:offset-1+limit]),
        "total_lines": len(lines)
    }
```

### 3.2 Multi-Agent 协作

```python
class AgentTeam:
    def __init__(self):
        self.agents = {}
        self.orchestrator = Orchestrator()
    
    def add_agent(self, name: str, agent: Agent):
        self.agents[name] = agent
    
    def execute(self, task: str) -> str:
        # 1. 任务分解
        subtasks = self.orchestrator.decompose(task)
        
        # 2. 分配子任务
        results = {}
        for subtask in subtasks:
            agent_name = self.orchestrator.assign(subtask)
            agent = self.agents[agent_name]
            results[subtask.id] = agent.execute(subtask)
        
        # 3. 汇总结果
        return self.orchestrator.aggregate(results)

class Orchestrator:
    def decompose(self, task: str) -> List[Subtask]:
        # 使用 LLM 分解任务
        prompt = f"""
        将以下任务分解为子任务：
        {task}
        
        输出格式：
        - 子任务1: 描述
        - 子任务2: 描述
        """
        return self.llm.parse(prompt)
    
    def assign(self, subtask: Subtask) -> str:
        # 根据子任务特征分配 Agent
        return self.match_agent(subtask)
```

---

## 4. 记忆系统

### 4.1 三层记忆架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        记忆系统架构                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: Sensory Memory (瞬时记忆)                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  持续时间: < 1秒                                              │   │
│  │  容量: 巨大但快速衰减                                          │   │
│  │  用途: 原始输入数据的临时存储                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                     注意过滤                                      │
│                           ▼                                         │
│  Layer 2: Working Memory (工作记忆)                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  持续时间: 秒 - 分钟                                          │   │
│  │  容量: 有限（7±2 个chunk）                                    │   │
│  │  用途: 当前任务相关的信息处理                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                     编码巩固                                      │
│                           ▼                                         │
│  Layer 3: Long-term Memory (长期记忆)                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  持续时间: 分钟 - 终身                                        │   │
│  │  容量: 理论上无限                                             │   │
│  │  用途: 持久化知识、技能、经验                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 向量数据库存储

```python
class VectorMemory:
    def __init__(self, embedding_model, vector_db):
        self.embedding = embedding_model
        self.db = vector_db
    
    def store(self, memory: Memory):
        # 1. 生成嵌入向量
        embedding = self.embedding.encode(memory.content)
        
        # 2. 存储到向量数据库
        self.db.insert(
            id=memory.id,
            embedding=embedding,
            metadata=memory.metadata
        )
    
    def recall(self, query: str, k: int = 5) -> List[Memory]:
        # 1. 生成查询向量
        query_embedding = self.embedding.encode(query)
        
        # 2. 相似度检索
        results = self.db.search(
            vector=query_embedding,
            k=k
        )
        
        # 3. 返回相关记忆
        return [self.db.get(r.id) for r in results]
```

---

## 5. Hermes Agent 实现

### 5.1 核心循环

```python
class AIAgent:
    def __init__(self, config):
        self.config = config
        self.tools = ToolRegistry()
        self.memory = MemorySystem()
    
    def chat(self, message: str) -> str:
        """简单的对话接口"""
        messages = self.build_messages(message)
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=self.tools.schemas
        )
        return self.process_response(response)
    
    def run_conversation(self, user_message: str) -> dict:
        """完整的对话循环"""
        messages = self.build_messages(user_message)
        
        while True:
            # 1. LLM 调用
            response = self.call_llm(messages)
            
            # 2. 检查结果
            if response.tool_calls:
                # 3. 工具调用
                for tool_call in response.tool_calls:
                    result = self.execute_tool(tool_call)
                    messages.append(self.tool_result_message(result))
            else:
                # 4. 最终回复
                return {
                    "response": response.content,
                    "messages": messages,
                    "iterations": len(messages)
                }
```

### 5.2 工具注册

```python
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.schemas = []
    
    def register(self, name: str, schema: dict, handler: Callable):
        """注册工具"""
        self.tools[name] = handler
        self.schemas.append(schema)
    
    def execute(self, name: str, arguments: dict) -> str:
        """执行工具"""
        handler = self.tools.get(name)
        if not handler:
            return f"Error: Tool '{name}' not found"
        
        try:
            result = handler(**arguments)
            return json.dumps(result)
        except Exception as e:
            return f"Error: {str(e)}"

# 示例：注册工具
registry.register(
    name="read_file",
    schema={
        "name": "read_file",
        "description": "Read file content",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    },
    handler=read_file_handler
)
```

---

## 6. 最佳实践

### 6.1 Prompt 设计原则

1. **角色明确**：定义清晰的 agent 角色
2. **目标具体**：明确的任务目标
3. **约束清晰**：指定输出格式和限制
4. **示例充分**：提供 few-shot 示例

### 6.2 工具设计原则

1. **单一职责**：每个工具只做一件事
2. **幂等性**：重复调用结果一致
3. **错误处理**：完善的错误反馈
4. **文档完整**：清晰的参数和返回值说明

### 6.3 性能优化

1. **缓存**：缓存重复查询结果
2. **并行**：独立工具调用并行执行
3. **超时**：设置合理的超时限制
4. **降级**：失败时优雅降级

---

## 7. 总结

### 7.1 架构对比

| 框架 | 规划器 | 执行器 | 记忆系统 | 工具调用 |
|------|--------|--------|----------|----------|
| LangChain | ReAct | Chain | 内置 | ✅ |
| AutoGPT | ToT | 循环 | 向量库 | ✅ |
| Hermes | 自定义 | 循环 | 文件系统 | ✅ |
| Claude | CoT | 循环 | 上下文 | ✅ |

### 7.2 设计要点

1. **模块化**：规划、执行、记忆分离
2. **可扩展**：工具插件化
3. **可观测**：完整的日志和监控
4. **容错性**：失败重试和降级

---

*最后更新：2026-08-11*
*作者：Ryan*
