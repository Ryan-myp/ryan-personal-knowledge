# Day 1: AgentExecutor — 从入门到源码级

> 学习目标: 先理解 Agent 是什么、怎么用，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 Agent 是什么？

```
Agent = 能自主做决策的智能体

它不是聊天机器人。聊天机器人是你问它答。
Agent 是你给它一个目标，它自己决定怎么做。

简单例子:
用户: "帮我查一下北京今天的天气，然后告诉我该穿什么"

Chatbot: "北京今天晴天，25度。"（只回答问题）

Agent: 
  1. 思考: 我需要查天气
  2. 行动: 调用 get_weather 工具
  3. 观察: 返回"晴天，25度"
  4. 思考: 我还需要知道穿衣建议
  5. 行动: 调用穿衣建议工具
  6. 回答: "北京今天晴天，25度。建议穿短袖。"
```

### 1.2 Agent 的 4 个核心组件

```
┌─────────────────────────────────────────┐
│              Agent 系统                   │
│                                         │
│  ┌───────────┐                          │
│  │  LLM 大脑  │ ← 推理、决策、生成        │
│  │ (Think)   │                          │
│  └─────┬─────┘                          │
│        │                               │
│  ┌─────▼─────┐   ┌──────────┐          │
│  │  记忆系统  │←─▶│  工具    │          │
│  │ (Memory)  │   │ (Tools)  │          │
│  └───────────┘   └──────────┘          │
│                                         │
│  ┌───────────┐                          │
│  │  规划器    │ ← 分解任务、安排步骤     │
│  │ (Plan)    │                          │
│  └───────────┘                          │
└─────────────────────────────────────────┘
```

### 1.3 Agent 是怎么工作的？

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 执行循环                             │
│                                                             │
│  1. 接收任务                                                 │
│     用户: "帮我查一下北京今天的天气"                           │
│         │                                                   │
│         ▼                                                   │
│  2. LLM 思考                                                 │
│     "我需要知道天气 → 我需要调用工具"                         │
│         │                                                   │
│         ▼                                                   │
│  3. 选择工具                                                 │
│     "get_weather 工具，参数: city=北京"                       │
│         │                                                   │
│         ▼                                                   │
│  4. 执行工具                                                 │
│     调用 get_weather(city="北京") → 返回 "晴天，25℃"          │
│         │                                                   │
│         ▼                                                   │
│  5. 观察结果                                                 │
│     "天气数据: 晴天，25℃"                                    │
│         │                                                   │
│         ▼                                                   │
│  6. 回到第 2 步（LLM 再次思考）                               │
│     "我拿到了天气数据 → 现在可以回答用户了"                    │
│         │                                                   │
│         ▼                                                   │
│  7. 生成最终答案                                             │
│     "北京今天天气晴朗，温度 25 摄氏度。"                       │
│         │                                                   │
│         ▼                                                   │
│  8. 返回给用户                                               │
│     ✓ 任务完成                                               │
│                                                             │
│  ⚠️ 如果循环超过 10 次，视为失败                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```python
# 安装依赖
pip install langchain langchain-openai

# 创建简单 Agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# 定义工具
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}的天气是晴天，温度 25 度"

# 创建 LLM
llm = ChatOpenAI(model="gpt-3.5-turbo")

# 创建 Agent
from langchain.agents import create_tool_calling_agent, AgentExecutor

tools = [get_weather]
agent = create_tool_calling_agent(llm, tools, None)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 运行
result = executor.invoke({"input": "北京天气怎么样？"})
print(result["output"])
```

运行后会看到：

```
Thought: The user is asking about the weather in Beijing.
I should use the get_weather tool.
Action: get_weather
Action Input: {"city": "北京"}
Observation: 北京的天气是晴天，温度 25 度
Thought: I now have the weather information for Beijing.
Final Answer: 北京天气是晴天，温度 25 度。
```

### 1.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **Agent** | 能自主做决策的智能体 |
| **工具** | Agent 调用的外部能力（搜索、计算等） |
| **记忆** | 记录之前的交互历史 |
| **ReAct** | 思考→行动→观察→思考的循环模式 |
| **max_steps** | 防止死循环，最多执行 N 步 |

---

## 第二部分：源码级深度剖析

### 2.1 AgentExecutor 的整体架构

#### 类继承关系

```
BaseSingleActionAgent
       │
       ▼
AgentExecutor (langchain/agents/load.py)
```

AgentExecutor 是 LangChain 中 Agent 系统的核心执行类。它负责：
- 接收用户输入
- 调用 Agent 规划下一步动作
- 执行工具
- 记录交互历史
- 返回最终结果

#### 核心属性

```python
class AgentExecutor:
    """Agent 执行器"""
    
    # 输入变量名（如 question, history）
    input_variables: List[str]
    
    # 输出解析器
    output_parser: BaseOutputParser
    
    # 数学计算链（可选）
    llm_math_chain: Optional[LLMChain]
    
    # 最大迭代次数（防止死循环）
    max_iterations: Optional[float] = 15
    
    # 最大执行时间（秒）
    max_execution_time: Optional[float] = None
    
    # 早停策略
    early_stopping_method: str = "force_return"
    
    # 智能体
    agent: BaseSingleActionAgent
    
    # 工具列表
    tools: Sequence[BaseTool]
    
    # 是否输出详细信息
    verbose: bool = False
```

### 2.2 核心数据结构

#### AgentAction

```python
@dataclass
class AgentAction:
    """表示 Agent 决定执行的动作"""
    
    log: str  # 推理日志（LLM 输出的完整文本）
    tool: str  # 工具名称
    tool_input: Union[str, Dict]  # 工具输入
    text: str  # 人类可读的描述
    message_log: Optional[List[BaseMessage]] = None  # 消息历史
    thoughts: Dict = field(default_factory=dict)  # 推理细节
```

#### AgentFinish

```python
@dataclass
class AgentFinish:
    """表示 Agent 决定结束并返回结果"""
    
    return_values: Dict  # 返回值（如 {"output": "答案"}）
    log: str  # 推理日志
```

#### AgentStep

```python
@dataclass
class AgentStep:
    """表示一次动作 + 观察"""
    
    action: AgentAction  # 执行的动作
    observation: Any  # 观察结果（工具返回）
```

### 2.3 核心执行逻辑（逐行解析）

#### _call 方法源码

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
    # 把用户输入和系统提示组合
    new_inputs = self.agent_format_instructions(inputs)
    
    # Step 2: 初始化
    stop = False  # 循环终止标志
    intermediary_steps = []  # 记录 (AgentAction, observation) 对
    total_tokens = 0  # 统计 token 使用
    start_time = time.time()  # 记录开始时间
    
    # Step 3: 主循环
    while not stop:
        
        # 3.1 检查最大执行时间
        if self.max_execution_time:
            elapsed = time.time() - start_time
            if elapsed > self.max_execution_time:
                stop = True
                break
        
        # 3.2 构建完整的输入（包含历史）
        full_inputs = self._build_full_inputs(
            new_inputs, 
            intermediary_steps  # 传入之前的交互历史
        )
        
        # 3.3 调用 Agent 规划下一步
        agent_output = self.agent.plan(
            full_inputs,
            intermediary_steps=intermediary_steps
        )
        
        # 3.4 统计 token 使用
        if hasattr(agent_output, "llm_output") and agent_output.llm_output:
            total_tokens += agent_output.llm_output.get("completion_tokens", 0)
        
        # 3.5 处理 Agent 输出
        if isinstance(agent_output, AgentFinish):
            # Agent 决定返回最终结果
            final_answer = agent_output.return_values
            stop = True
            break
        elif isinstance(agent_output, AgentAction):
            # Agent 决定执行一个工具
            observation = self._execute_action(agent_output)
            
            # 记录交互历史
            intermediary_steps.append((agent_output, observation))
            
            # 检查是否达到最大迭代次数
            if self.max_iterations and len(intermediary_steps) >= self.max_iterations:
                stop = True
                break
        else:
            raise ValueError(f"Unexpected output type: {type(agent_output)}")
    
    # Step 4: 返回最终结果
    return self._format_output(
        final_answer,
        {"time": time.time() - start_time, "tokens": total_tokens}
    )
```

#### 关键点解析

##### 点 1: `intermediary_steps` 的作用

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

##### 点 2: `agent.plan()` 的调用

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

##### 点 3: 早停策略 `early_stopping_method`

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

### 2.4 Token 消耗分析

#### 一个完整循环的 Token 消耗

```
┌────────────────────────────────────────────────────────────┐
│              一次 ReAct 循环的 Token 消耗                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  输入 Token (Prompt):                                      │
│  ├── 系统提示: ~500 tokens                                 │
│  ├── 工具描述: ~500-2000 tokens（取决于工具数量）             │
│  ├── 对话历史: ~1000-5000 tokens（随循环增加）               │
│  ├── 用户问题: ~100-500 tokens                              │
│  └── 总计: ~2100-8000 tokens                               │
│                                                            │
│  输出 Token (Response):                                    │
│  ├── Thought: ~50-200 tokens                               │
│  ├── Action: ~10-50 tokens                                 │
│  ├── Action Input: ~50-500 tokens                          │
│  └── 总计: ~110-750 tokens                                 │
│                                                            │
│  成本计算 (GPT-4o):                                        │
│  ├── 输入: $2.50 / 1M tokens = $0.002-0.02                │
│  ├── 输出: $10.00 / 1M tokens = $0.001-0.008              │
│  └── 单次循环: ~$0.003-0.03                               │
│                                                            │
│  10 次循环: $0.03-0.30                                     │
│  20 次循环: $0.06-0.60                                     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

#### Token 管理策略

```python
class TokenManager:
    """Token 管理器"""
    
    def __init__(self, max_tokens=8000):
        self.max_tokens = max_tokens
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        
    def count(self, text: str) -> int:
        """计算 token 数"""
        return len(self.tokenizer.encode(text))
    
    def should_compress(self, history: list) -> bool:
        """判断是否需要压缩历史"""
        history_text = str(history)
        return self.count(history_text) > self.max_tokens * 0.7
    
    def compress_history(self, history: list, keep_recent: int = 5) -> str:
        """
        压缩历史记录
        
        策略:
        1. 保留最近 N 步的完整信息
        2. 早期步骤做摘要
        3. 去掉冗余信息
        """
        if len(history) <= keep_recent:
            return str(history)
        
        recent = history[-keep_recent:]  # 最近 N 步
        early = history[:-keep_recent]   # 早期步骤
        
        # 对早期步骤做摘要
        summary_prompt = f"""
        以下是 AI 助手之前完成的任务步骤:
        {early}
        
        请用一句话总结这些步骤的结果:
        """
        summary = llm.chat(summary_prompt)
        
        return f"之前已完成: {summary}\n最近步骤: {recent}"
```

### 2.5 工具调用机制

#### 工具执行流程

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

#### 工具路由

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
    4. 返回结果或错误
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

### 2.6 记忆系统

#### 记忆类型对比

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

#### 对话缓冲记忆源码

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
    ai: 北京晴天，25 度
    human: 那上海呢？
    ai: 上海多云，22 度
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

## 第三部分：自测

### 问题 1
AgentExecutor 的 `intermediary_steps` 为什么重要？
<details>
<summary>查看答案</summary>

1. 传递给 agent.plan() 作为上下文
2. 让 LLM 知道之前做了什么
3. 避免重复执行
4. 控制最大迭代次数

随着循环进行，这个列表会越来越长，最终可能超出 LLM 的 token 限制。
</details>

### 问题 2
两种早停策略的区别是什么？
<details>
<summary>查看答案</summary>

1. "force_return": 达到 max_iterations 时强制返回最终答案
2. "generate": 达到 max_iterations 时，让 LLM 基于已有信息生成答案

适用场景:
- force_return: 时间敏感
- generate: 质量优先
</details>

### 问题 3
Token 压缩的策略是什么？
<details>
<summary>查看答案</summary>

1. 保留最近 N 步的完整信息
2. 早期步骤做摘要
3. 去掉冗余信息
</details>

---

## 第四部分：动手验证

### 4.1 运行一个简单 Agent

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# 定义工具
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    weather_data = {
        "北京": "晴天，25℃",
        "上海": "多云，22℃",
        "广州": "小雨，28℃"
    }
    return weather_data.get(city, "未知天气")

# 创建 LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# 创建 Agent
from langchain.agents import create_tool_calling_agent, AgentExecutor

tools = [get_weather]
agent = create_tool_calling_agent(llm, tools, None)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 运行
result = executor.invoke({"input": "北京天气怎么样？"})
print("\n最终答案:", result["output"])
```

### 4.2 观察什么？

运行后看 verbose 输出，你会看到：

```
> Entering new AgentExecutor chain...
Thought: The user is asking about the weather in Beijing.
I should use the get_weather tool.
Action: get_weather
Action Input: {"city": "北京"}
Observation: 晴天，25℃
Thought: I now have the weather information for Beijing.
Final Answer: 北京天气是晴天，温度 25 摄氏度。

> Finished chain.
```

**你应该观察**:
1. LLM 先"思考"了什么？
2. 它调用了哪个工具？
3. 工具返回了什么？
4. LLM 怎么组合信息给出答案？

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
