# Agent AI 面试题库深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 面试/Agent  
> **题目数**: 20 道高频题

---

## 一、基础概念

### Q1: 什么是 Agent？它与普通 LLM 应用有什么区别？

```typescript
// Agent 架构
interface Agent {
  // 核心组件
  llm: LLM;                    // 大脑
  memory: MemorySystem;        // 记忆
  tools: ToolRegistry;         // 工具集
  planner: Planner;            // 规划器
  
  // 运行循环
  async run(task: string): Result {
    while (!task.complete) {
      // 1. 观察
      const observation = this.observe();
      
      // 2. 思考
      const thought = await this.think(observation);
      
      // 3. 行动
      const action = await this.act(thought);
      
      // 4. 更新记忆
      this.memory.store(observation, action);
    }
    return task.result;
  }
}
```

**答案要点:**
- 普通 LLM: 一次输入→一次输出，无状态
- Agent: 循环执行 observe→think→act，有记忆和工具
- Agent 能自主决策、调用工具、维护状态

---

### Q2: ReAct 模式的工作原理？

```python
# ReAct: Reasoning + Acting
# 交替进行 Thought 和 Action

thought_1 = "用户需要查询天气，我需要调用 weather_tool"
action_1 = call_tool("weather", {"city": "北京"})
observation_1 = {"temp": 25, "weather": "晴天"}

thought_2 = "已获取天气信息，可以直接回答"
action_2 = None  # 结束
observation_2 = "回答用户"
```

**答案要点:**
- Thought: 推理步骤
- Action: 调用工具
- Observation: 工具返回结果
- 循环直到得出结论

---

## 二、记忆系统

### Q3: 记忆系统的三种类型？

```go
// 记忆分类
type MemoryType string

const (
    WorkingMemory  MemoryType = "working"   // 工作记忆：当前任务
    ShortTermMemory MemoryType = "short"    // 短期记忆：近期交互
    LongTermMemory  MemoryType = "long"     // 长期记忆：持久知识
)

// 遗忘曲线
func shouldForget(entry *MemoryEntry, now time.Time) bool {
    elapsed := now.Sub(entry.CreatedAt)
    retention := math.Exp(-elapsed.Seconds() / 86400) // 24小时半衰期
    return retention < 0.1
}
```

---

### Q4: 向量检索的工作原理？

```typescript
// 向量检索流程
interface VectorSearch {
  // 1. Embedding
  const queryVec = await embed(query);
  
  // 2. 相似度计算
  const scores = memories.map(m => ({
    id: m.id,
    score: cosineSimilarity(queryVec, m.vector)
  }));
  
  // 3. 排序返回 Top-K
  return scores.sort((a, b) => b.score - a.score).slice(0, 5);
}

// cosine similarity
function cosineSimilarity(a: number[], b: number[]): number {
  const dot = a.reduce((sum, v, i) => sum + v * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, v) => sum + v * v, 0));
  const normB = Math.sqrt(b.reduce((sum, v) => sum + v * v, 0));
  return dot / (normA * normB);
}
```

---

## 三、工具调用

### Q5: 工具调用的完整流程？

```
用户问题
    ↓
┌─────────────┐
│  LLM 推理    │ → 决定调用哪个工具
└─────────────┘
    ↓
┌─────────────┐
│  工具注册表  │ → 查找工具实现
└─────────────┘
    ↓
┌─────────────┐
│  执行工具    │ → 调用外部 API/函数
└─────────────┘
    ↓
┌─────────────┐
│  结果返回    │ → 格式化结果
└─────────────┘
    ↓
┌─────────────┐
│  最终回答    │ → LLM 生成自然语言
└─────────────┘
```

---

### Q6: 如何设计一个安全的工具调用系统？

```go
// 安全工具调用
type ToolCall struct {
    Name      string            `json:"name"`
    Arguments map[string]interface{} `json:"arguments"`
}

type ToolRegistry struct {
    tools map[string]Tool
    policy *AccessPolicy
}

// 访问控制
func (r *ToolRegistry) Execute(ctx context.Context, call ToolCall) (interface{}, error) {
    tool, ok := r.tools[call.Name]
    if !ok {
        return nil, fmt.Errorf("tool not found")
    }
    
    // 检查权限
    if !r.policy.Check(ctx, call.Name) {
        return nil, ErrPermissionDenied
    }
    
    // 执行并捕获异常
    defer func() {
        if r := recover(); r != nil {
            log.Printf("Tool %s panic: %v", call.Name, r)
        }
    }()
    
    return tool.Execute(ctx, call.Arguments)
}
```

---

## 四、框架实现

### Q7: LangGraph 的核心概念？

```python
# LangGraph 图结构
from langgraph.graph import StateGraph, END

# 定义状态
class GraphState(TypedDict):
    messages: list
    tools_used: list
    result: str

# 定义节点
async def chatbot(state):
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}

async def tool_use(state):
    tool_call = parse_tool_call(state["messages"][-1])
    result = await execute_tool(tool_call)
    return {"tools_used": [tool_call], "result": result}

# 构建图
graph = StateGraph(GraphState)
graph.add_node("chatbot", chatbot)
graph.add_node("tool_use", tool_use)
graph.add_edge("chatbot", "tool_use")
graph.add_edge("tool_use", "chatbot")
graph.set_end_point("chatbot", END)

app = graph.compile()
```

---

## 五、20道高频题汇总

| # | 题目 | 难度 | 考点 |
|---|------|------|------|
| 1 | Agent vs LLM 应用 | ⭐⭐⭐ | 基础概念 |
| 2 | ReAct 模式原理 | ⭐⭐⭐ | 核心架构 |
| 3 | 记忆系统分类 | ⭐⭐⭐ | 记忆设计 |
| 4 | 向量检索原理 | ⭐⭐⭐ | 检索技术 |
| 5 | 工具调用流程 | ⭐⭐⭐ | 系统集成 |
| 6 | 安全工具设计 | ⭐⭐⭐⭐ | 安全实践 |
| 7 | LangGraph 概念 | ⭐⭐⭐⭐ | 框架使用 |
| 8 | CrewAI vs LangGraph | ⭐⭐⭐ | 框架对比 |
| 9 | MCP 协议设计 | ⭐⭐⭐⭐ | 协议理解 |
| 10 | Multi-Agent 协作 | ⭐⭐⭐⭐ | 高级架构 |
| 11 | RAG vs Agent | ⭐⭐⭐ | 技术选型 |
| 12 | 幻觉检测 | ⭐⭐⭐ | 质量问题 |
| 13 | Token 优化 | ⭐⭐ | 成本控制 |
| 14 | 上下文窗口 | ⭐⭐⭐ | 技术限制 |
| 15 | Prompt Engineering | ⭐⭐⭐ | 提示设计 |
| 16 | Function Calling | ⭐⭐⭐ | API 使用 |
| 17 | Streaming 实现 | ⭐⭐⭐ | 实时交互 |
| 18 | 错误处理 | ⭐⭐⭐ | 健壮性 |
| 19 | 性能监控 | ⭐⭐⭐ | 可观测性 |
| 20 | 部署架构 | ⭐⭐⭐⭐ | 工程实践 |

---

## 六、自测题

1. **Agent 的三大核心组件是什么？**
   - LLM (大脑)、Memory (记忆)、Tools (工具)

2. **ReAct 循环的执行顺序？**
   - Thought → Action → Observation → ...

3. **向量检索的核心优势？**
   - 语义相似度匹配，不受关键词限制

