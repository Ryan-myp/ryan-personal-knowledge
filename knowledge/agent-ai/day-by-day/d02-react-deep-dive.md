# Day 2: MRKL 系统 — 从入门到源码级

> 学习目标: 先理解 MRKL 是什么、怎么用，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 2.1 MRKL 是什么？

```
MRKL = Modular Reasoning, Knowledge, and Language
     = 模块化推理、知识和语言

这是一个架构模式，让 LLM 能调用外部工具。

简单理解:
LLM 本身不会搜索、不会计算、不会查数据库。
MRKL 给 LLM 装上了"手"和"脚"。

架构组成:
┌─────────────────────────────────────────────────────┐
│                   MRKL System                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐                                    │
│  │  LLM (P())   │ ← 推理引擎（大脑）                  │
│  └──────┬──────┘                                    │
│         │                                           │
│  ┌──────▼──────┐                                    │
│  │  F() 函数库  │ ← 预定义工具集合（手和脚）           │
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

### 2.2 ReAct 模式

```
ReAct = Reason（推理）+ Act（行动）

为什么叫 ReAct？
因为它是"推理"和"行动"交替进行。

执行流程图:
┌──────────────────────────────────────────────────────────────┐
│                    ReAct 循环                                 │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Thought │───▶│  Action  │───▶│Observe   │              │
│  │  思考    │    │  行动    │    │  观察    │              │
│  │          │    │          │    │          │              │
│  │ "我需要  │    │ 调用     │    │ "工具    │              │
│  │ 查天气"  │    │get_weather│   │ 返回晴天  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       ▲                                    │                │
│       │                                    ▼                │
│       │                          ┌──────────┐              │
│       └──────────────────────────│  循环判断 │              │
│                                  │          │              │
│                              ┌───┤ 继续？   │──┐            │
│                              │   └──────────┘  │            │
│                              │        │        │            │
│                              │    ┌───┴──┐     │            │
│                              │    │ 继续  │  停止│            │
│                              │    └───────┘     │            │
│                              │     │       │    │            │
│                              │     ▼       ▼    │            │
│                              │  思考   Final    │            │
│                              │  下一步   Answer │            │
│                              └─────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 一个完整的 ReAct 输出示例

假设用户问："从北京到上海的高铁要多长时间？"

```
=== Step 1 ===
Thought: 我不知道北京到上海高铁的时间，我需要搜索一下。
Action: search
Action Input: {"query": "北京到上海高铁时间"}

=== Step 2 ===
Observation: 北京南到上海虹桥的高铁约 4-6 小时
Thought: 我找到了答案，可以回答用户了。
Final Answer: 北京到上海的高铁大约需要 4-6 小时，具体取决于车次类型。
G 字头高铁最快约 4 小时 18 分钟。
```

**注意看**:
1. LLM 先"思考"（Thought）
2. 然后"行动"（Action）
3. 然后"观察"（Observation）——工具返回的结果
4. 然后再"思考"，决定下一步
5. 最后给出"最终答案"（Final Answer）

**这就是 ReAct 的核心**：思考→行动→观察→思考→...→回答

### 2.4 快速体验

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor

# 定义工具
@tool
def search(query: str) -> str:
    """搜索互联网信息"""
    return "北京到上海高铁约 4-6 小时"

@tool
def calculate(expression: str) -> str:
    """数学计算"""
    return str(eval(expression))

# 创建 LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# 创建 Agent
tools = [search, calculate]
agent = create_tool_calling_agent(llm, tools, None)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)

# 运行
result = executor.invoke({"input": "北京到上海高铁需要多长时间？"})
print(result["output"])
```

运行后你会看到完整的 ReAct 循环：

```
Thought: I need to search for the travel time between Beijing and Shanghai
Action: search
Action Input: {"query": "北京到上海高铁时间"}
Observation: 北京到上海高铁约 4-6 小时
Thought: I now know the final answer
Final Answer: 北京到上海的高铁大约需要 4-6 小时。
```

### 2.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **MRKL** | 让 LLM 调用外部工具的架构模式 |
| **ReAct** | 思考→行动→观察→思考的循环模式 |
| **Thought** | LLM 的推理过程 |
| **Action** | LLM 决定的下一步行动 |
| **Observation** | 工具执行的结果 |
| **Final Answer** | LLM 给出的最终答案 |

---

## 第二部分：源码级深度剖析

### 2.6 MRKL Prompt 模板源码

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

# 每个变量的含义:
# {tools}: 工具描述（名称 + 描述）
# {tool_names}: 工具名称列表
# {input}: 用户问题
# {chat_history}: 对话历史
# {intermediate_steps}: 中间步骤（Action/Observation）
# {agent_scratchpad}: LLM 之前的思考
```

### 2.7 工具描述生成

```python
# langchain/agents/format_scratchpad.py
# 工具描述生成逻辑

def format_tools(tools: Sequence[BaseTool]) -> str:
    """
    生成工具描述字符串
    
    格式:
    tool_name: Description of the tool. Args: {json_schema}
    
    示例:
    get_weather: Get weather information for a city. Args: {"city": "string"}
    search: Search the internet. Args: {"query": "string"}
    """
    tool_strings = []
    for tool in tools:
        args_schema = str(tool.args_schema) if tool.args_schema else ""
        tool_strings.append(f"{tool.name}: {tool.description}. Args: {args_schema}")
    return "\n".join(tool_strings)

def format_tool_names(tools: Sequence[BaseTool]) -> str:
    """生成工具名称列表"""
    return ", ".join([tool.name for tool in tools])
```

### 2.8 中间步骤格式化

```python
# langchain/agents/format_scratchpad.py
# 中间步骤格式化

def format_intermediate_steps(
    intermediate_steps: List[Tuple[AgentAction, str]]
) -> str:
    """
    格式化中间步骤为字符串
    
    格式:
    Thought: <thought>
    Action: <action>
    Action Input: <input>
    Observation: <observation>
    Thought: <next_thought>
    
    示例:
    Thought: I need to get the weather
    Action: get_weather
    Action Input: {"city": "北京"}
    Observation: 晴天，25℃
    Thought: I now have the weather information
    """
    log = ""
    for action, observation in intermediate_steps:
        log += f"\nThought: {action.log}"
        log += f"\nAction: {action.tool}"
        log += f"\nAction Input: {json.dumps(action.tool_input)}"
        log += f"\nObservation: {observation}"
        log += "\nThought:"
    return log
```

### 2.9 输出解析器源码

#### MRKL 输出解析器

```python
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

#### Tool Calling 输出解析器

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

### 2.10 错误处理机制

#### 常见的 5 种错误

```
1. 工具不存在
   LLM: call search(query="xxx")
   错误: 没有 'search' 工具
   
2. 参数错误
   LLM: call get_weather()
   错误: 缺少 required 参数 'city'
   
3. 工具执行超时
   LLM: call google_search(query="xxx")
   错误: 请求超时（>30s）
   
4. LLM 输出格式错误
   LLM: 我调用了search工具
   错误: 没有按 Thought/Action/Action Input 格式输出
   
5. 无限循环
   LLM 一直调用同一个工具
   错误: 超过 max_steps
```

#### 错误处理源码

```python
def execute_with_error_handling(action, tools, llm):
    """
    带错误处理的工具执行
    
    处理流程:
    1. 验证工具是否存在
    2. 验证参数是否正确
    3. 执行工具（带超时）
    4. 格式化错误信息
    5. 如果出错，让 LLM 自己修正
    """
    
    # 1. 检查工具是否存在
    if action.tool not in tools:
        error_msg = f"错误: 工具 '{action.tool}' 不存在"
        return {
            "is_error": True,
            "message": error_msg,
            "hint": f"可用工具: {list(tools.keys())}"
        }
    
    # 2. 验证参数
    try:
        validated_input = validate_input(action.tool, action.input)
    except ValidationError as e:
        error_msg = f"参数错误: {e}"
        return {
            "is_error": True,
            "message": error_msg,
            "hint": f"正确格式: {get_tool_schema(action.tool)}"
        }
    
    # 3. 执行工具（带超时）
    try:
        result = tools[action.tool](validated_input)
        return {"is_error": False, "result": result}
    except TimeoutError:
        return {
            "is_error": True,
            "message": f"工具执行超时 (>30s)",
            "hint": "请稍后重试或换用其他工具"
        }
    except Exception as e:
        return {
            "is_error": True,
            "message": f"执行失败: {str(e)}",
            "hint": "请检查输入或尝试其他方式"
        }
```

### 2.11 Token 消耗分析

#### 一个 ReAct 循环的 Token 消耗

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

---

## 第三部分：自测

### 问题 1
MRKL 系统的 Prompt 模板中，每个变量是什么？
<details>
<summary>查看答案</summary>

- {tools}: 工具描述（名称 + 描述）
- {tool_names}: 工具名称列表
- {input}: 用户问题
- {chat_history}: 对话历史
- {intermediate_steps}: 中间步骤（Action/Observation）
- {agent_scratchpad}: LLM 之前的思考
</details>

### 问题 2
输出解析器的解析流程是什么？
<details>
<summary>查看答案</summary>

1. 检查是否包含 "Final Answer:"
2. 如果是，返回 AgentFinish
3. 否则，解析 Action 和 Action Input
4. 返回 AgentAction
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

### 4.1 测试不同 Prompt 的效果

```python
# 测试 1: 简单 Prompt
simple_prompt = f"""
回答: {question}
工具: {tools_description}
历史: {history}
"""

# 测试 2: 详细 Prompt
detailed_prompt = f"""
你是一个智能助手。

## 任务
{question}

## 规则
1. 使用 Thought/Action/Action Input 格式
2. 最多执行 5 步
3. 工具不存在时不要使用

## 工具
{tools_description}

## 历史
{history}

请开始:
Thought:
"""

# 对比结果
result1 = llm.chat(simple_prompt)
result2 = llm.chat(detailed_prompt)

print("简单 Prompt 结果:", result1)
print("详细 Prompt 结果:", result2)
```

**观察**: 详细 Prompt 的准确率明显更高。

### 4.2 Token 计数实验

```python
import tiktoken

tokenizer = tiktoken.encoding_for_model("gpt-4")

# 计算不同长度的 history 消耗多少 token
test_cases = [
    "空历史",
    "1 步历史",
    "3 步历史", 
    "5 步历史",
    "10 步历史"
]

for case in test_cases:
    # 模拟不同长度的 history
    history = f"[{'step' * 100}]" if "10" in case else f"[{'step' * (int(case[0]) * 100)}]"
    prompt = f"""
    任务: 测试
    历史: {history}
    """
    tokens = len(tokenizer.encode(prompt))
    cost = tokens * 0.000003  # GPT-4 输入价格
    print(f"{case}: {tokens} tokens, ~${cost:.4f}")
```

**观察**: 随着 history 增长，token 消耗快速增长。5 步后成本明显上升。

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
