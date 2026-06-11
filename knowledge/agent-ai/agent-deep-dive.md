# LangChain AgentExecutor 源码深度剖析

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 一、AgentExecutor 整体架构

### 1.1 类继承关系

```
BaseSingleActionAgent
       │
       ▼
AgentExecutor (langchain/agents/load.py)
       │
       ├── input_variables: list[str]  # 输入变量名
       ├── output_parser: BaseOutputParser  # 输出解析器
       ├── llm_math_chain: Optional[LLMChain]  # 数学计算链
       ├── max_iterations: Optional[float]  # 最大迭代次数
       ├── max_execution_time: Optional[float]  # 最大执行时间
       ├── early_stopping_method: str  # 早停策略
       ├── agent: BaseSingleActionAgent  # 智能体
       ├── tools: Sequence[BaseTool]  # 工具列表
       └── verbose: bool  # 是否输出详细信息
```

### 1.2 核心数据结构

```python
# LangChain 中的核心数据结构

# AgentAction: 表示 Agent 决定执行的动作
@dataclass
class AgentAction:
    log: str  # 推理日志
    tool: str  # 工具名称
    tool_input: Union[str, Dict]  # 工具输入
    text: str  # 人类可读的描述
    message_log: Optional[List[BaseMessage]] = None  # 消息历史
    thoughts: "AgentTelemetryDict" = field(default_factory=dict)  # 推理细节

# AgentFinish: 表示 Agent 决定结束并返回结果
@dataclass
class AgentFinish:
    return_values: Dict  # 返回值
    log: str  # 推理日志

# AgentStep: 表示一次动作+观察
@dataclass
class AgentStep:
    action: AgentAction  # 执行的动作
    observation: Any  # 观察结果
```

---

## 二、核心执行逻辑 — _call 方法源码分析

### 2.1 完整源码（langchain/agents/load.py）

```python
def _call(self, inputs: dict) -> dict:
    """
    AgentExecutor 的核心执行方法
    
    执行流程:
    1. 准备输入
    2. 进入主循环
    3. 调用 agent.plan() 获取下一步动作
    4. 执行动作并获取观察结果
    5. 更新交互历史
    6. 检查终止条件
    7. 返回结果
    """
    # Step 1: 准备输入
    new_inputs = self.agent_format_instructions(inputs)
    
    # Step 2: 初始化
    stop = False
    intermediary_steps = []  # 记录 (AgentAction, observation) 对
    final_answer = None
    total_tokens = 0
    start_time = time.time()
    
    while not stop:
        # Step 3: 检查最大执行时间
        if self.max_execution_time:
            elapsed = time.time() - start_time
            if elapsed > self.max_execution_time:
                stop = True
                break
        
        # Step 4: 构建完整的输入（包含历史）
        full_inputs = self._build_full_inputs(
            new_inputs, 
            intermediary_steps
        )
        
        # Step 5: 调用 Agent 规划下一步
        agent_output = self.agent.plan(
            full_inputs,
            intermediary_steps=intermediary_steps
        )
        
        # Step 6: 统计 token 使用
        if hasattr(agent_output, "llm_output") and agent_output.llm_output:
            total_tokens += agent_output.llm_output.get("completion_tokens", 0)
        
        # Step 7: 处理 Agent 输出
        if isinstance(agent_output, AgentFinish):
            # Agent 决定返回最终结果
            final_answer = agent_output.return_values
            stop = True
            break
        elif isinstance(agent_output, AgentAction):
            # Agent 决定执行一个工具
            # 执行工具
            observation = self._execute_action(agent_output)
            
            # 记录交互历史
            intermediary_steps.append((agent_output, observation))
            
            # 检查是否达到最大迭代次数
            if self.max_iterations and len(intermediary_steps) >= self.max_iterations:
                stop = True
                break
        else:
            raise ValueError(f"Unexpected output type: {type(agent_output)}")
    
    # Step 8: 返回最终结果
    return self._format_output(final_answer, total_tokens)
```

### 2.2 关键点解析

#### 点 1: `intermediary_steps` 的作用

```
intermediary_steps 是 AgentExecutor 的核心状态变量

数据结构: List[Tuple[AgentAction, Any]]
示例: [
    (AgentAction(tool="search", input="北京天气"), "晴天，25℃"),
    (AgentAction(tool="search", input="北京湿度"), "60%"),
]

作用:
1. 传递给 agent.plan() 作为上下文
2. 让 LLM 知道之前做了什么
3. 避免重复执行
4. 控制最大迭代次数

关键: 随着循环进行，这个列表会越来越长
      最终可能超出 LLM 的 token 限制！
```

#### 点 2: `agent.plan()` 的调用

```python
# agent.plan() 的签名
def plan(
    self,
    inputs: dict,  # 包括 question, history, tools 等
    intermediary_steps: List[Tuple[AgentAction, Any]] = ...,
    callbacks: Callbacks = None,
) -> Union[AgentAction, AgentFinish]:
    """
    Agent 的核心规划方法
    
    输入:
    - inputs: 用户输入 + 系统提示 + 工具描述
    - intermediary_steps: 之前的交互历史
    
    输出:
    - AgentAction: 决定执行一个工具
    - AgentFinish: 决定返回最终答案
    
    内部流程:
    1. 构建 Prompt
    2. 调用 LLM
    3. 解析 LLM 输出
    4. 返回 AgentAction 或 AgentFinish
    """
```

#### 点 3: 早停策略 `early_stopping_method`

```python
# 两种早停策略

# 策略 1: "force_return"
# 达到 max_iterations 时强制返回最终答案
# 适用: 时间敏感的场景

# 策略 2: "generate"
# 达到 max_iterations 时，让 LLM 基于已有信息生成答案
# 适用: 质量优先的场景

# 源码实现
if self.early_stopping_method == "force_return":
    if len(intermediary_steps) >= self.max_iterations:
        # 强制返回最后一次观察
        last_observation = intermediary_steps[-1][1]
        return AgentFinish(
            return_values={"output": str(last_observation)},
            log="Force returned due to max iterations"
        )
elif self.early_stopping_method == "generate":
    if len(intermediary_steps) >= self.max_iterations:
        # 让 LLM 生成最终答案
        prompt = self._build_final_answer_prompt(intermediary_steps)
        final_answer = self.agent.llm.chat(prompt)
        return AgentFinish(
            return_values={"output": final_answer},
            log="Generated due to max iterations"
        )
```

---

## 三、MRKL 系统 — ReAct 的源码实现

### 3.1 MRKL 架构

```
MRKL = Modular Reasoning, Knowledge, and Language

架构组成:
┌─────────────────────────────────────────────────────┐
│                   MRKL System                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐                                    │
│  │  LLM (P())   │ ← 推理引擎                         │
│  └──────┬──────┘                                    │
│         │                                           │
│  ┌──────▼──────┐                                    │
│  │  F() 函数库  │ ← 预定义工具集合                    │
│  └─────────────┘                                    │
│                                                     │
│  工作流程:                                           │
│  1. P() 决定调用哪个 F()                             │
│  2. F() 执行并返回结果                               │
│  3. 结果反馈给 P()                                  │
│  4. 重复直到完成任务                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.2 源码级实现

```python
# langchain/agents/mrkl/prompt.py
# MRKL Prompt 模板

TEMPLATE = """Answer the following questions as best you can. 
You have access to the following tools:

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
{chat_history}
{intermediate_steps}
Thought:{agent_scratchpad}
"""

# langchain/agents/mrkl/output_parser.py
# MRKL 输出解析器

class MRKLOutputParser(BaseOutputParser[Union[AgentAction, AgentFinish]]):
    """解析 MRKL 格式的 LLM 输出"""
    
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        """
        解析 LLM 的输出
        
        解析流程:
        1. 检查是否包含 "Final Answer:"
        2. 如果是，返回 AgentFinish
        3. 否则，解析 Action 和 Action Input
        4. 返回 AgentAction
        """
        # 检查 Final Answer
        if "Final Answer:" in text:
            final_answer = text.split("Final Answer:")[-1].strip()
            return AgentFinish(
                return_values={"output": final_answer},
                log=text
            )
        
        # 解析 Action
        action_match = re.search(r"Action: (.+?)\nAction Input: (.+)", text)
        if action_match:
            action = action_match.group(1).strip()
            action_input = action_match.group(2).strip()
            return AgentAction(
                log=text,
                tool=action,
                tool_input=action_input,
                text=text
            )
        
        raise ValueError(f"Invalid format: {text}")
```

### 3.3 Token 消耗分析

```python
# 一个完整的 MRKL 循环的 Token 消耗

# 1. Prompt 模板
template_tokens = 500  # 系统提示

# 2. 工具描述
tools_description = """get_weather: Get weather information
search: Search the internet
calculate: Perform calculations"""
tool_tokens = len(tokenizer.encode(tools_description))  # ~200 tokens

# 3. 对话历史
chat_history = """User: 北京天气怎么样？
Assistant: ..."""
history_tokens = len(tokenizer.encode(chat_history))  # ~100 tokens

# 4. 中间步骤
intermediate_steps = """Action: get_weather
Action Input: {"city": "北京"}
Observation: 晴天，25℃"""
step_tokens = len(tokenizer.encode(intermediate_steps))  # ~100 tokens

# 5. 用户问题
question = "北京天气怎么样？"
question_tokens = len(tokenizer.encode(question))  # ~20 tokens

# 6. Agent Scratchpad（LLM 之前的思考）
agent_scratchpad = "Thought: I need to get the weather"
scratchpad_tokens = len(tokenizer.encode(agent_scratchpad))  # ~50 tokens

# 总计
total_input_tokens = (template_tokens + tool_tokens + history_tokens + 
                     step_tokens + question_tokens + scratchpad_tokens)
# ≈ 970 tokens

# 输出 Token
output_tokens = 100  # Thought + Action + Action Input

# 成本计算（GPT-3.5 Turbo）
input_cost = total_input_tokens * 0.0015 / 1000  # $0.0015/1K tokens
output_cost = output_tokens * 0.002 / 1000  # $0.002/1K tokens
total_cost = input_cost + output_cost  # ≈ $0.0017

# 10 次循环的成本
total_10_steps = total_cost * 10  # ≈ $0.017
```

---

## 四、工具调用机制 — 源码级分析

### 4.1 工具执行流程

```python
# langchain/agents/tooling/base.py
# 工具执行的核心逻辑

class BaseTool(BaseModel):
    """工具基类"""
    name: str  # 工具名称
    description: str  # 工具描述
    args_schema: Optional[Type[BaseModel]] = None  # 参数 schema
    return_direct: bool = False  # 是否直接返回结果
    
    def _run(self, *args, **kwargs) -> str:
        """工具的实际执行逻辑"""
        raise NotImplementedError
    
    async def _arun(self, *args, **kwargs) -> str:
        """异步执行"""
        raise NotImplementedError
    
    def run(self, *args, callbacks: Callbacks = None, **kwargs) -> str:
        """
        同步执行入口
        
        流程:
        1. 参数验证
        2. 调用 _run()
        3. 错误处理
        4. 返回结果
        """
        try:
            # 参数验证
            if self.args_schema:
                validated_args = self.args_schema(**kwargs)
                kwargs = validated_args.dict()
            
            # 执行工具
            result = self._run(*args, **kwargs)
            
            return result
        except Exception as e:
            # 错误处理
            return f"Error: {str(e)}"
```

### 4.2 工具调用解析

```python
# langchain/agents/tool_calling_parser.py
# Tool Calling 输出解析器

class ToolCallingOutputParser(BaseOutputParser):
    """解析 Tool Calling 格式的 LLM 输出"""
    
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        """
        解析 Tool Calling 格式
        
        格式:
        Thought: xxx
        Action: tool_name
        Action Input: {"param": "value"}
        
        或者:
        Thought: xxx
        Final Answer: xxx
        """
        # 检查 Final Answer
        if "Final Answer:" in text:
            return AgentFinish(
                return_values={"output": text.split("Final Answer:")[-1].strip()},
                log=text
            )
        
        # 解析 Action 和 Action Input
        action_match = re.search(r"Action:\s*(.+?)[\n\s]*Action Input:\s*(.+)", text, re.DOTALL)
        if action_match:
            tool_name = action_match.group(1).strip()
            tool_input_str = action_match.group(2).strip()
            
            # 解析输入（可能是 JSON 或字符串）
            try:
                tool_input = json.loads(tool_input_str)
            except json.JSONDecodeError:
                tool_input = tool_input_str
            
            return AgentAction(
                log=text,
                tool=tool_name,
                tool_input=tool_input,
                text=text
            )
        
        raise ValueError(f"Invalid format: {text}")
```

### 4.3 工具路由

```python
# langchain/agents/tooling/routing.py
# 工具路由逻辑

class ToolRouter:
    """
    工具路由器
    
    功能:
    1. 根据工具名查找工具
    2. 验证参数
    3. 执行工具
    4. 返回结果
    """
    
    def __init__(self, tools: Dict[str, BaseTool]):
        self.tools = tools
    
    def route(self, tool_name: str, tool_input: Any) -> str:
        """
        路由到指定工具
        
        流程:
        1. 检查工具是否存在
        2. 验证参数
        3. 执行工具
        4. 返回结果或错误
        """
        # 检查工具是否存在
        if tool_name not in self.tools:
            available_tools = ", ".join(self.tools.keys())
            return f"Error: Tool '{tool_name}' not found. Available tools: {available_tools}"
        
        # 获取工具
        tool = self.tools[tool_name]
        
        # 执行工具
        try:
            if isinstance(tool_input, dict):
                result = tool.run(**tool_input)
            else:
                result = tool.run(tool_input)
            return result
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"
```

---

## 五、记忆系统 — 源码级实现

### 5.1 记忆类型

```
LangChain 支持的记忆类型:

1. ConversationBufferMemory
   - 存储完整的对话历史
   - 优点: 信息完整
   - 缺点: token 消耗大

2. ConversationBufferWindowMemory
   - 只保留最近 N 轮对话
   - 优点: 控制 token 使用
   - 缺点: 丢失早期信息

3. ConversationTokenBufferMemory
   - 按 token 数量限制
   - 优点: 精确控制成本
   - 缺点: 可能切断对话

4. ConversationalSummaryMemory
   - 存储对话摘要
   - 优点: 节省 token
   - 缺点: 信息丢失

5. EntityMemory
   - 存储实体信息
   - 优点: 长期记忆
   - 缺点: 实现复杂
```

### 5.2 源码实现

```python
# langchain/memory/buffer.py
# 对话缓冲记忆

class ConversationBufferMemory(BaseMemory):
    """
    完整的对话缓冲记忆
    
    存储格式:
    human: 用户的问题
    ai: Agent 的回答
    
    示例:
    human: 北京天气怎么样？
    ai: 北京晴天，25度
    human: 那上海呢？
    ai: 上海多云，22度
    """
    
    chat_history: List[BaseMessage] = field(default_factory=list)
    
    @property
    def memory_variables(self) -> List[str]:
        return ["chat_history"]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆"""
        return {"chat_history": self.chat_history}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """保存上下文"""
        # 保存用户输入
        if "input" in inputs:
            self.chat_history.append(HumanMessage(content=inputs["input"]))
        
        # 保存 Agent 输出
        if "output" in outputs:
            self.chat_history.append(AIMessage(content=outputs["output"]))
    
    def clear(self) -> None:
        """清空记忆"""
        self.chat_history = []
```

---

## 六、生产级优化

### 6.1 Token 压缩

```python
class TokenCompressor:
    """
    Token 压缩器
    
    策略:
    1. 保留最近 N 步完整信息
    2. 早期步骤做摘要
    3. 去掉重复内容
    """
    
    def compress(self, steps: List[Tuple[AgentAction, Any]], keep_recent: int = 5) -> str:
        """
        压缩交互历史
        
        1. 保留最近 keep_recent 步
        2. 对早期步骤做摘要
        3. 返回压缩后的字符串
        """
        if len(steps) <= keep_recent:
            return self._format_steps(steps)
        
        recent = steps[-keep_recent:]
        early = steps[:-keep_recent]
        
        # 对早期步骤做摘要
        early_text = self._format_steps(early)
        summary_prompt = f"Summarize these AI actions:\n{early_text}"
        summary = llm.chat(summary_prompt)
        
        recent_text = self._format_steps(recent)
        return f"Earlier actions summarized: {summary}\nRecent actions:\n{recent_text}"
```

### 6.2 并行工具调用

```python
async def parallel_tool_call(actions: List[AgentAction], tools: Dict[str, BaseTool]) -> List[Any]:
    """
    并行执行多个工具调用
    
    适用场景:
    - 多个工具调用互不依赖
    - 需要快速获取多个信息
    
    示例:
    actions = [
        AgentAction(tool="get_weather", input={"city": "北京"}),
        AgentAction(tool="get_weather", input={"city": "上海"}),
    ]
    
    串行执行: 2 * 工具延迟
    并行执行: 1 * 工具延迟
    """
    async def execute_action(action: AgentAction) -> Tuple[AgentAction, Any]:
        tool = tools[action.tool]
        observation = await tool.arun(**action.tool_input) if isinstance(action.tool_input, dict) else await tool.arun(action.tool_input)
        return (action, observation)
    
    # 并行执行
    results = await asyncio.gather(*[execute_action(action) for action in actions])
    return list(results)
```

---

### Agent 源码级深度剖析 — Go 实现

```go
// Agent 源码级深度: LangChain Agent 核心逻辑 Go 实现
// 覆盖 Action → Observation 循环、Tool 注册、Memory
package agentdeep

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Tool 工具接口
type Tool interface {
	Name() string
	Description() string
	Execute(ctx context.Context, input string) (string, error)
}

// AgentInput Agent 输入
type AgentInput struct {
	Query    string
	Context  string
	Memory   []string
}

// AgentStep Agent 单步执行结果
type AgentStep struct {
	Action    string
	Input     string
	Observation string
}

// Agent 智能体核心
type Agent struct {
	name    string
	tools   map[string]Tool
	memory  []string
	maxSteps int
}

// NewAgent 创建 Agent
func NewAgent(name string, tools []Tool) *Agent {
	a := &Agent{
		name:     name,
		tools:    make(map[string]Tool),
		maxSteps: 10,
	}
	for _, t := range tools {
		a.tools[t.Name()] = t
	}
	return a
}

// Run 运行 Agent 主循环
func (a *Agent) Run(ctx context.Context, input AgentInput) ([]AgentStep, error) {
	steps := make([]AgentStep, 0, a.maxSteps)
	observation := ""

	for i := 0; i < a.maxSteps; i++ {
		step := AgentStep{}

		// 1. 工具调用
		toolName := a.selectTool(input, observation)
		tool, ok := a.tools[toolName]
		if !ok {
			return steps, fmt.Errorf("unknown tool: %s", toolName)
		}

		obs, err := tool.Execute(ctx, input.Query)
		if err != nil {
			return steps, err
		}

		step.Action = toolName
		step.Observation = obs
		steps = append(steps, step)
		observation = obs

		// 检查是否终止
		if a.shouldStop(obs) {
			break
		}
	}

	return steps, nil
}

func (a *Agent) selectTool(input AgentInput, observation string) string {
	// 简化: 默认第一个工具
	for name := range a.tools {
		return name
	}
	return ""
}

func (a *Agent) shouldStop(observation string) bool {
	return len(observation) > 0 && observation[0] == 'S' // 简化终止条件
}

// MemoryStore 记忆存储
type MemoryStore struct {
	shortTerm []string
	longTerm  map[string]string
	mu        sync.RWMutex
}

func (m *MemoryStore) AddShort(text string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.shortTerm = append(m.shortTerm, text)
	if len(m.shortTerm) > 100 {
		m.shortTerm = m.shortTerm[1:]
	}
}

func (m *MemoryStore) AddLong(key, value string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.longTerm[key] = value
}

func (m *MemoryStore) GetShort() []string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	result := make([]string, len(m.shortTerm))
	copy(result, m.shortTerm)
	return result
}

// ==================== 使用示例 ====================

type SearchTool struct{}

func (t *SearchTool) Name() string          { return "search" }
func (t *SearchTool) Description() string   { return "Search the web" }
func (t *SearchTool) Execute(ctx context.Context, input string) (string, error) {
	return "Search results for: " + input, nil
}

func main() {
	agent := NewAgent("researcher", []Tool{&SearchTool{}})
	input := AgentInput{Query: "What is Go?", Context: "Research context"}
	steps, err := agent.Run(context.Background(), input)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
	}
	fmt.Printf("Steps: %d\n", len(steps))
	for i, s := range steps {
		fmt.Printf("  %d: %s → %s\n", i, s.Action, s.Observation[:min(50, len(s.Observation))])
	}
}

func min(a, b int) int {
	if a < b { return a }
	return b
}
```

---

## 第六部分：自测题

### 问题 1
LangChain Agent 的主循环中，`Action → Observation` 模式的关键设计原则是什么？

<details>
<summary>查看答案</summary>

核心原则：**Agent 不是直接执行操作，而是先输出 Action（工具名+参数），由环境执行后返回 Observation，Agent 再根据 Observation 决定下一步**。

这个设计实现了：
1. **解耦**：Agent 不负责具体工具实现
2. **可观测性**：每一步 Action/Observation 都可记录
3. **容错**：工具失败时 Agent 可以尝试其他工具或回退
4. **人类在环**：可以在 Observation 阶段插入人工审核

</details>

### 问题 2
Go 的 `MemoryStore` 为什么用 `sync.RWMutex` 而不是 `sync.Mutex`？

<details>
<summary>查看答案</summary>

`RWMutex` 允许多个读操作并发执行，写操作独占。对于 MemoryStore：
- `GetShort()` 是读操作，可以被多个 goroutine 同时调用
- `AddShort()` / `AddLong()` 是写操作，需要独占

如果只用普通 `Mutex`，所有操作都会串行化，在高并发场景下性能较差。`RWMutex` 在读多写少的场景下性能更好。

</details>

### 问题 3
`ToolExecutor.ExecuteParallel` 中，为什么要在 goroutine 里用 `defer wg.Done()` 而不是在函数末尾调用？

<details>
<parameter>
<summary>查看答案</summary>

defer 确保无论函数如何返回（正常返回、panic、early return），`Done()` 都会被调用。如果在函数末尾手动调用，一旦中间有 panic 或提前 return，`Done()` 就不会被执行，导致 `Wait()` 永久阻塞。

</details>

