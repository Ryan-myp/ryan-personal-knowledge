# Day 1: Agent 核心原理 — 你必须搞懂的 3 件事

> 学习目标: 看完能给别人讲清楚 Agent 是什么、怎么工作

---

## 一、Agent 到底是什么？

### 1.1 一句话定义

```
Agent = 能自主做决策的智能体

它不是聊天机器人，聊天机器人是你问它答。
Agent 是你给它一个目标，它自己决定怎么做。
```

### 1.2 Agent vs Chatbot 的本质区别

```
Chatbot（聊天机器人）:
┌────────┐    ┌────────┐    ┌────────┐
│ 用户    │───▶│ Chatbot│───▶│ 用户    │
│ 提问    │    │ 直接回答│    │ 收到答案│
└────────┘    └────────┘    └────────┘
               单向，无状态

Agent（智能体）:
┌────────┐    ┌────────────────────────────────────┐
│ 用户     │───▶│  Agent                               │
│ 给目标   │    │  ┌──────────┐  ┌──────────┐        │
└────────┘    │  │  思考    │→│  行动    │        │
              │  └──────────┘  └──────────┘        │
              │      ↓              ↓                │
              │  ┌──────────┐  ┌──────────┐        │
              │  │  观察    │←│  工具    │        │
              │  └──────────┘  └──────────┘        │
              │         ↻ 循环直到完成任务            │
              └────────────────────────────────────┘
               循环，有状态，能调用工具
```

**关键区别**:
1. **Chatbot** 只回答问题
2. **Agent** 能主动搜索、计算、调用 API、执行代码
3. **Agent** 能处理多步骤复杂任务

### 1.3 Agent 的 4 个核心组件

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

| 组件 | 作用 | 类比人类 |
|------|------|----------|
| LLM | 推理、决策 | 大脑 |
| Memory | 记住对话历史、经验 | 记忆 |
| Tools | 调用外部能力 | 手和脚 |
| Planning | 规划步骤 | 思考能力 |

---

## 二、Agent 是怎么工作的？（核心循环）

### 2.1 Agent 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 执行循环                             │
│                                                             │
│  1. 接收任务                                                 │
│     用户: "帮我查一下北京今天的天气"                           │
│         │                                                   │
│         ▼                                                   │
│  2. LLM 思考                                                 │
│     "我需要知道天气 → 我没有这个能力 → 我需要调用工具"          │
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
│  6. 回到第2步（LLM 再次思考）                                 │
│     "我拿到了天气数据 → 现在可以回答用户了"                    │
│         │                                                   │
│         ▼                                                   │
│  7. 生成最终答案                                             │
│     "北京今天天气晴朗，温度25摄氏度。"                         │
│         │                                                   │
│         ▼                                                   │
│  8. 返回给用户                                               │
│     ✓ 任务完成                                               │
│                                                             │
│  ⚠️ 如果 2→3→4→5→6 循环超过 10 次，视为失败                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 源码级理解（必须看懂这段代码）

```python
class SimpleAgent:
    """
    简化版 Agent 实现
    
    这段代码就是 Agent 的核心逻辑，
    所有复杂的 Agent 框架（LangChain、AutoGen 等）
    底层都是这个循环。
    """
    
    def run(self, question: str, tools: list) -> str:
        history = []  # 记录每一步的交互
        max_steps = 10  # 最多执行10步
        
        for step in range(max_steps):
            # ========== 步骤 1: LLM 思考 ==========
            # 把问题和历史记录发给 LLM
            # 问它: "你打算做什么？"
            response = llm.chat(
                prompt=f"""
                用户问题: {question}
                
                你已经做的事:
                {history}
                
                你可以用的工具:
                {tools}
                
                请告诉我:
                1. 你的思考 (Thought)
                2. 你要调用的工具 (Action)
                3. 工具的参数 (Action Input)
                或者告诉我已经可以回答了 (Final Answer)
                """
            )
            
            # ========== 步骤 2: 解析 LLM 的回答 ==========
            if response.is_final_answer():
                # LLM 说它可以回答了
                return response.answer
            
            # ========== 步骤 3: 执行工具 ==========
            tool_result = execute_tool(
                tool_name=response.action,
                tool_input=response.action_input
            )
            
            # ========== 步骤 4: 记录到历史 ==========
            history.append({
                "step": step + 1,
                "thought": response.thought,
                "action": response.action,
                "result": tool_result
            })
        
        # 超过最大步数，任务失败
        return "任务执行失败：超过最大步数"
```

**你必须搞懂的 3 个问题**:

**Q1**: `history` 里存了什么？为什么需要它？
<details>
<summary>点击展开答案</summary>

`history` 存了 Agent 每一步:
- 它想了什么（thought）
- 它调了什么工具（action）
- 工具返回了什么结果（result）

**为什么需要？**
- LLM 本身没有记忆
- 每次对话都是独立的
- 必须把之前的经历喂给它，它才知道自己已经做了什么
- 否则它会重复调用同一个工具

**类比**: 你让别人帮你做一件事，如果每次说话都忘了之前做过什么，那你们永远做不完。
</details>

**Q2**: 为什么需要 `max_steps = 10`？
<details>
<summary>点击展开答案</summary>

原因有 3 个:

1. **防止死循环**
   - LLM 可能陷入循环：一直调用同一个工具
   - 比如：一直调用 get_weather("北京")
   
2. **控制成本**
   - 每次循环都要调用 LLM
   - GPT-4 调用一次约 0.03 元
   - 10 次 = 0.3 元，100 次 = 3 元
   
3. **控制延迟**
   - 每次 LLM 调用约 2 秒
   - 10 次 = 20 秒，用户等不了太久

**最佳实践**: 大多数系统用 5-15 步。太简单的问题 3 步内解决，太复杂的问题可能需要 10 步。
</details>

**Q3**: 如果 LLM 调用了不存在的工具，怎么办？
<details>
<summary>点击展开答案</summary>

处理流程:

1. **工具执行层捕获错误**
   ```python
   try:
       result = execute_tool(tool_name, tool_input)
   except ToolNotFoundError:
       result = f"错误: 工具 '{tool_name}' 不存在"
   except ToolExecutionError as e:
       result = f"错误: {e}"
   ```

2. **错误结果作为 Observation 返回给 LLM**
   ```
   LLM: 调用 search(query="xxx")
   工具层: "错误: 工具 'search' 不存在"
   LLM: 哦，我不该用 search，我应该用 get_weather
   ```

3. **LLM 会自我纠正**
   - 这就是 Agent 比 Chatbot 强的地方
   - 它能根据错误反馈调整策略

**关键点**: 错误信息要详细，LLM 需要知道"为什么失败"才能改正。
</details>

---

## 三、ReAct 模式（Agent 的核心工作模式）

### 3.1 什么是 ReAct？

```
ReAct = Reason（推理）+ Act（行动）

为什么叫 ReAct？
- 因为它是"推理"和"行动"交替进行
- 先思考，再行动，再观察，再思考...
```

### 3.2 ReAct 循环图解

```
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

### 3.3 ReAct 的实际输出示例

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

---

## 四、你必须记住的关键点

### 4.1 Agent 的核心特征

```
✅ Agent 能：
- 自主决策（决定下一步做什么）
- 调用工具（搜索、计算、执行代码等）
- 循环执行（思考→行动→观察→再思考）
- 纠正错误（根据反馈调整策略）

❌ Agent 不能（或者说目前还不行）：
- 没有真正的"意识"
- 不是真正的"智能"
- 本质上是"高级的 if-else"
- 会幻觉（编造答案）
- 不可靠（同一问题可能不同回答）
```

### 4.2 Agent 的局限性

| 局限性 | 说明 | 影响 |
|--------|------|------|
| **幻觉** | LLM 可能编造事实 | 不可全信，需要验证 |
| **成本** | 每次调用都要花钱 | 不能无节制调用 |
| **延迟** | 每次循环 2-5 秒 | 用户等不了太久 |
| **不可靠** | 同一问题不同回答 | 不适合关键决策 |
| **token 限制** | 输入有长度限制 | 复杂任务会超限 |

---

## 五、动手验证（15 分钟）

### 5.1 运行一个简单 Agent

```bash
# 安装依赖
pip install langchain langchain-openai
```

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# ========== 1. 定义一个工具 ==========
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    # 实际项目中这里应该调用天气 API
    weather_data = {
        "北京": "晴天，25℃",
        "上海": "多云，22℃",
        "广州": "小雨，28℃"
    }
    return weather_data.get(city, "未知天气")

# ========== 2. 创建 LLM ==========
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# ========== 3. 创建 Agent ==========
from langchain.agents import create_tool_calling_agent, AgentExecutor

tools = [get_weather]
agent = create_tool_calling_agent(llm, tools, None)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ========== 4. 运行 ==========
result = executor.invoke({"input": "北京天气怎么样？"})
print("\n最终答案:", result["output"])
```

### 5.2 观察什么？

运行后看 verbose 输出，你会看到：

```
> Entering new AgentExecutor chain...
Thought: The user is asking about the weather in Beijing.
I should use the get_weather tool.
Action: get_weather
Action Input: {"city": "北京"}
Observation: 晴天，25℃
Thought: I now have the weather information for Beijing.
Final Answer: 北京天气是晴天，温度25摄氏度。

> Finished chain.
```

**你应该观察**:
1. LLM 先"思考"了什么？
2. 它调用了哪个工具？
3. 工具返回了什么？
4. LLM 怎么组合信息给出答案？

---

## 六、自测（答不上来=没懂）

### 问题 1
Agent 和 Chatbot 的本质区别是什么？
<details>
<summary>点击查看</summary>

Chatbot: 用户问 → 模型答（单向，无状态）
Agent: 用户给目标 → Agent 自主决定怎么做（循环，有状态，能调用工具）

Agent 能：思考→行动→观察→再思考，循环直到完成任务。
</details>

### 问题 2
Agent 的 `history` 为什么重要？没有会怎样？
<details>
<summary>点击查看</summary>

history 记录了 Agent 每一步的思考、行动和结果。

没有 history:
- LLM 不知道之前做了什么
- 会重复调用同一个工具
- 会遗忘中间结果
- 无法完成任务

就像让一个人做数学题，但每次问他都忘了上一步算到哪了。
</details>

### 问题 3
为什么 Agent 需要 `max_steps` 限制？
<details>
<summary>点击查看</summary>

3 个原因：
1. 防止死循环（LLM 可能卡住）
2. 控制成本（每次调用都花钱）
3. 控制延迟（用户等不了太久）

一般设 5-15 步。
</details>

### 问题 4
ReAct 是什么意思？
<details>
<summary>点击查看</summary>

ReAct = Reason（推理）+ Act（行动）

工作模式：
思考(Thought) → 行动(Action) → 观察(Observation) → 思考 → 行动 → ... → 回答

先推理决定做什么，行动后观察结果，再根据结果决定下一步。
</details>

---

## 七、明日预告

**Day 2**: ReAct 模式深入 — 为什么它能纠正错误？Prompt 怎么设计？token 怎么管理？

---

*今天花 30 分钟读完 + 15 分钟跑代码 = 真正理解 Agent 核心原理*
*答不全自测题？回去重读对应章节。*
