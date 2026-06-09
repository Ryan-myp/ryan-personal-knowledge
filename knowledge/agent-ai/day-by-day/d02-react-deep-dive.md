# Day 2: MRKL 系统源码深度剖析

> 学习目标: 理解 MRKL 系统的 Prompt 设计、输出解析、错误处理

---

## 一、MRKL 系统架构

### 1.1 MRKL 是什么？

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

---

## 二、Prompt 模板源码

### 2.1 MRKL Prompt 完整源码

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

### 2.2 工具描述生成

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

### 2.3 中间步骤格式化

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

---

## 三、输出解析器源码

### 3.1 MRKL 输出解析器

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

### 3.2 Tool Calling 输出解析器

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

---

## 四、错误处理机制

### 4.1 常见的 5 种错误

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

### 4.2 错误处理源码

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

---

## 五、Token 消耗分析

### 5.1 一个 ReAct 循环的 Token 消耗

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

### 5.2 Token 管理策略

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

## 六、自测

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

*今天花 60 分钟读完 + 30 分钟调试 = 真正理解 MRKL 系统*
