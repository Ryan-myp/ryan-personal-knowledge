# ReAct 深度解析 — 推理与行动交替的智能体

> 标签: `#ReAct` `#智能体` `#工具调用` `#多步推理`
> 创建日期: 2026-06-08
> 作者: Ryan

---

## 1. ReAct 是什么？

ReAct（Reasoning + Acting）是一种让 Agent **推理与行动交替进行**的模式。

### 核心思想
传统 AI 系统要么只做推理，要么只执行动作，而 ReAct 让 Agent 能够：
- **规划任务** - 将复杂任务分解为可管理的步骤
- **执行操作** - 调用工具或 API 获取信息
- **观察结果** - 评估执行效果并调整策略
- **循环优化** - 直到获得足够信息完成任务

### 工作流程
```
用户问题 → 思考(Thought) → 行动(Action) → 观察(Observation) → 思考(Thought) → ... → 最终答案
```

---

## 2. 核心挑战与解决方案

### 挑战 1: 工具选择
**问题**：如何从多个可用工具中选择最合适的？

**解决方案**：
- **工具描述** - 清晰描述每个工具的功能、参数和返回值
- **上下文匹配** - 根据当前任务状态选择工具
- **优先级排序** - 为工具设置优先级，避免选择错误

### 挑战 2: 错误处理
**问题**：工具调用失败时如何回退？

**解决方案**：
- **重试机制** - 对临时性失败进行重试
- **替代方案** - 准备备用工具或方法
- **明确反馈** - 向用户报告错误并寻求指导

### 挑战 3: 循环控制
**问题**：如何防止 Agent 陷入无限循环？

**解决方案**：
- **最大迭代次数** - 设置合理的最大循环次数
- **状态检测** - 检测重复状态并终止
- **进度跟踪** - 监控任务进度，确保向前推进

---

## 3. 关键技术实现

### 3.1 工具描述格式

```python
TOOL_DESCRIPTIONS = [
    {
        "name": "search_knowledge_base",
        "description": "搜索知识库获取相关信息",
        "parameters": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
                "required": True
            }
        }
    },
    {
        "name": "calculate",
        "description": "执行数学计算",
        "parameters": {
            "expression": {
                "type": "string",
                "description": "数学表达式",
                "required": True
            }
        }
    }
]
```

### 3.2 ReAct 控制器

```python
class ReActAgent:
    def __init__(self, tools, llm):
        self.tools = tools
        self.llm = llm
        self.history = []
        self.max_iterations = 10
    
    def process(self, question):
        """处理用户问题"""
        for i in range(self.max_iterations):
            # 1. 思考：LLM 决定下一步行动
            thought_action = self.llm.generate_thought_action(
                question,
                self.history,
                self.tools
            )
            
            # 2. 执行行动
            if thought_action.action:
                result = self.execute_tool(
                    thought_action.action,
                    thought_action.parameters
                )
                self.history.append({
                    "thought": thought_action.thought,
                    "action": thought_action.action,
                    "observation": result
                })
                
                # 3. 检查是否完成
                if self.is_complete(thought_action.thought):
                    break
            else:
                # 没有行动，直接生成答案
                break
        
        # 4. 生成最终答案
        return self.generate_final_answer(question, self.history)
    
    def execute_tool(self, action_name, parameters):
        """执行工具调用"""
        if action_name in self.tools:
            return self.tools[action_name](**parameters)
        else:
            return f"错误：未找到工具 {action_name}"
```

### 3.3 Thought-Action-Observation 模式

```python
# 典型的 ReAct 循环
def react_loop(question, tools, llm, max_steps=5):
    """
    ReAct 主循环
    :param question: 用户问题
    :param tools: 可用工具列表
    :param llm: 语言模型
    :param max_steps: 最大步数
    :return: 最终答案
    """
    history = []
    
    for step in range(max_steps):
        # 生成 Thought-Action 对
        thought_action = llm.generate_thought_action(
            question, history, tools
        )
        
        # 执行 Action
        if thought_action.action:
            observation = execute_action(
                thought_action.action,
                thought_action.parameters
            )
            history.append(f"Thought: {thought_action.thought}")
            history.append(f"Action: {thought_action.action}")
            history.append(f"Observation: {observation}")
        else:
            # 没有行动，生成最终答案
            return llm.generate_answer(question, history)
    
    # 超过最大步数，生成部分答案
    return llm.generate_partial_answer(question, history)
```

---

## 4. 实际应用场景

### 场景 1: 智能客服
- **需求**：查询订单状态、修改地址、退款等
- **实现**：ReAct 循环中调用订单系统 API
- **示例**：
  ```
  Thought: 需要查询用户订单状态
  Action: query_order(user_id="123")
  Observation: {"order_status": "shipped", "tracking_id": "XYZ789"}
  Thought: 需要将物流信息告知用户
  Action: send_message("您的订单已发货，物流单号: XYZ789")
  ```

### 场景 2: 数据分析
- **需求**：查询数据库、生成图表、撰写报告
- **实现**：ReAct 循环中调用数据库和可视化工具
- **示例**：
  ```
  Thought: 需要查询销售数据
  Action: query_db("SELECT * FROM sales WHERE month='2026-05'")
  Observation: {"data": [...]}
  Thought: 需要生成趋势图
  Action: generate_chart(data, type="line")
  Observation: {"chart_url": "https://..."}
  ```

### 场景 3: 代码调试
- **需求**：分析错误日志、定位问题、修复代码
- **实现**：ReAct 循环中调用代码分析工具和 IDE
- **示例**：
  ```
  Thought: 需要分析错误日志
  Action: analyze_logs("error.log")
  Observation: {"error_type": "NullPointerException", "line": 42}
  Thought: 需要查看第 42 行代码
  Action: get_code_snippet("file.py", 42)
  Observation: {"code": "result = obj.method()"}
  Thought: 可能 obj 为 None
  Action: add_null_check("file.py", 42)
  ```

---

## 5. 与 RAG 的结合

ReAct 和 RAG 结合使用，Agent 既能**检索知识**，又能**执行操作**：

```
用户问题 → ReAct 循环:
  1. Thought: 需要查找相关文档
  2. Action: 调用 RAG 检索工具
  3. Observation: 返回相关文档片段
  4. Thought: 需要调用 API 获取实时数据
  5. Action: 调用 API 工具
  6. Observation: 返回 API 结果
  ...
→ 综合所有信息生成最终答案
```

---

## 6. 性能优化建议

1. **并行执行** - 独立工具调用可并行执行
2. **缓存结果** - 缓存工具调用结果，避免重复执行
3. **工具预筛选** - 根据问题类型预筛选可用工具
4. **增量更新** - 逐步构建答案，而非最后一次性生成

---

## 7. 相关资源

- 参考书籍：《Agent设计模式：图解可复用智能体架构》
- 论文：ReAct: Synergizing Reasoning and Acting in Language Models
- 开源项目：LangChain, AutoGPT, BabyAGI

---

*本文基于微信读书《Agent设计模式》及相关技术文档整理*

---

## 自测题

### 问题 1
React 模式中的 Thought → Action → Observation 循环与传统的 if-then-else 控制流有什么本质区别？

<details>
<summary>查看答案</summary>

**传统 if-then-else 是硬编码逻辑**，而 React 循环是**基于观察的动态决策**：
1. **解耦**：推理和动作分离，思考部分不涉及具体实现
2. **可扩展**：新增工具只需注册，无需修改核心循环
3. **可调试**：每一步 Thought 都可以记录和回放
4. **容错**：某步失败可以 backtracking 重新思考

</details>

### 问题 2
Go 中 `Tool` 接口为什么只用 `Name()` 和 `Execute()` 两个方法而不是更多？

<details>
<summary>查看答案</summary>

**KISS 原则 + 注册表模式**：
1. `Name()` 用于注册表查找和列出所有工具
2. `Execute()` 是唯一的执行入口
3. 如果工具需要元数据（描述、参数 schema），可以单独实现 `Description()` 等方法，但核心接口保持极简
4. 越少的接口方法，实现成本越低，工具链越灵活

</details>
