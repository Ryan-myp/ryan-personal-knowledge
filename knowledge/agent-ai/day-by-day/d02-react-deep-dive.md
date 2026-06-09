# Day 2: ReAct 模式深度 — 为什么它能"思考"？

> 学习目标: 理解 ReAct 的 Prompt 设计原理、token 管理、错误处理

---

## 一、ReAct 的 Prompt 是怎么设计的？

### 1.1 一个完整的 ReAct Prompt

```python
# 这是 LLM 收到的完整 Prompt（简化版）
prompt = f"""
你是一个智能助手。你的目标是帮助用户完成任务。

## 可用工具
{tools_description}

## 回答格式
你必须严格按照以下格式回答:

Thought: 你的思考过程
Action: 你要调用的工具名称
Action Input: 工具的参数（JSON 格式）

或者，如果你认为可以直接回答:
Thought: 你的思考过程
Final Answer: 你的最终答案

## 示例
用户问题: 北京天气怎么样？

Thought: 我需要查询北京的天气。我没有这个信息，但我有 get_weather 工具。
Action: get_weather
Action Input: {{"city": "北京"}}

Observation: 晴天，25℃

Thought: 我已经获取了天气信息，可以回答用户了。
Final Answer: 北京今天天气晴朗，温度25摄氏度。

## 当前任务
用户问题: {question}

你已经做过的:
{history}

请开始:
"""
```

### 1.2 Prompt 设计的 3 个关键技巧

```
技巧 1:  Few-Shot 示例
────────────────────────
给 LLM 一个完整的示例，告诉它:
- 该用什么格式
- 思考应该写什么
- 工具怎么用

效果: 准确率提升 30-50%

技巧 2: 工具描述要清晰
────────────────────────
每个工具都要有:
- 名称
- 参数说明
- 返回格式
- 使用场景

错误描述 → LLM 不会用或乱用
正确描述 → LLM 正确使用

技巧 3: 历史压缩
────────────────────────
history 太长会超出 token 限制
处理方式:
- 保留最近 N 步
- 摘要化早期步骤
- 只保留关键信息
```

### 1.3 工具描述的重要性

```python
# ❶ 差的工具描述
tool = {
    "name": "search",
    "description": "搜索东西"  # 太模糊！LLM 不知道什么时候用、怎么用
}

# ❷ 好的工具描述
tool = {
    "name": "search",
    "description": """
    使用网络搜索引擎获取最新信息。
    
    参数:
    - query: 搜索关键词（字符串）
    
    返回: 搜索结果摘要（字符串）
    
    适用场景: 需要最新信息、事实查询、参考资料
    不适用: 计算、天气、本地数据
    """,
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }
}
```

**关键**: 工具描述就是 LLM 的"使用说明书"。描述越清晰，LLM 用得越准。

---

## 二、Token 管理（成本控制的命脉）

### 2.1 Token 是什么？

```
Token = LLM 处理的基本单位

近似换算:
- 英文: 1 Token ≈ 0.75 单词
- 中文: 1 Token ≈ 0.5-0.8 字
- 代码: 1 Token ≈ 0.5 字符

例子:
"Hello World" = 2 tokens
"你好世界" = 4-6 tokens
```

### 2.2 一个 ReAct 循环的 Token 消耗

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

### 2.3 Token 管理策略

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

**关键**: history 越长，token 越多，成本越高。必须压缩！

---

## 三、错误处理（让 Agent 更可靠）

### 3.1 常见的 5 种错误

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

### 3.2 错误处理源码

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

**关键**: 错误信息要**具体、有用**。LLM 需要知道"为什么错"才能修正。

---

## 四、ReAct 的 Prompt 工程实战

### 4.1 基础版 Prompt

```python
# 最简单的 ReAct Prompt
prompt = f"""
你是一个智能助手。

## 任务
{question}

## 工具
{tools_description}

## 历史
{history}

## 输出格式
Thought: 你的思考
Action: 工具名
Action Input: 参数
"""
```

### 4.2 进阶版 Prompt（推荐）

```python
# 更好的 ReAct Prompt
prompt = f"""
你是一个有帮助且准确的AI助手。你的目标是解决用户的问题。

## 核心规则
1. 必须使用 Thought/Action/Action Input 格式
2. 不确定时，使用工具获取信息，不要编造
3. 工具执行失败时，尝试其他方式
4. 最多执行10步
5. 如果无法完成任务，明确说明

## 可用工具
{tools_description}

## 示例格式
Thought: 我需要查找XX信息，使用XX工具
Action: tool_name
Action Input: {{"param": "value"}}

Observation: 工具返回结果

Thought: 我获得了XX信息，现在可以回答了
Final Answer: 我的答案

## 当前任务
用户问题: {question}

## 已完成的步骤
{history}

## 请开始
Thought:
"""
```

### 4.3 Prompt 设计原则

```
✅ 好的 Prompt:
- 有明确的任务描述
- 有清晰的格式要求
- 有工具说明
- 有错误处理指引
- 有 Few-Shot 示例

❌ 差的 Prompt:
- 模糊的任务描述
- 没有格式要求
- 工具描述不清
- 没有错误处理
- 没有示例
```

---

## 五、动手验证

### 5.1 测试不同 Prompt 的效果

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
2. 最多执行5步
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

### 5.2 Token 计数实验

```python
import tiktoken

tokenizer = tiktoken.encoding_for_model("gpt-4")

# 计算不同长度的 history 消耗多少 token
test_cases = [
    "空历史",
    "1步历史",
    "3步历史", 
    "5步历史",
    "10步历史"
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

## 六、自测

### 问题 1
ReAct 的 Prompt 为什么要包含 Few-Shot 示例？
<details>
<summary>查看答案</summary>

Few-Shot 示例让 LLM 知道:
1. 应该用什么格式输出
2. 思考应该怎么写
3. 工具怎么调用

没有示例的 LLM 经常格式混乱，输出不可解析。
</details>

### 问题 2
为什么 history 需要压缩？怎么做？
<details>
<summary>查看答案</summary>

原因:
- LLM 有 token 限制（GPT-4 约 128K）
- history 越长，token 越多
- 超过限制会导致错误

压缩方法:
- 保留最近 N 步的完整信息
- 对早期步骤做摘要
- 去掉冗余信息
</details>

### 问题 3
工具描述为什么重要？给出一个好的工具描述模板。
<details>
<summary>查看答案</summary>

工具描述是 LLM 的"使用说明书"。描述不清 → LLM 不会用或乱用。

好的工具描述模板:
{
    "name": "工具名",
    "description": """
    工具用途说明
    
    参数:
    - 参数名: 类型，说明
    
    返回: 返回格式说明
    
    适用场景: 什么时候用
    不适用: 什么时候不用
    """,
    "parameters": {...}
}
</details>

---

## 七、明日预告

**Day 3**: RAG 系统原理 — 向量检索、文档切片、上下文组装

---

*今天花 30 分钟读完 + 20 分钟调试 = 真正理解 ReAct*
*答不全自测题？回去重读对应章节。*
