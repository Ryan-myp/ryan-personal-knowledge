# Prompt Engineering 进阶 - 资深专家深度实现

## 一、Prompt模式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Prompt 工程模式                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模式                | 示例                                           │
│   ────────────────────┼──────────────────────────────────────────────── │
│   Zero-shot           | "翻译以下句子: Hello World"                     │
│   One-shot            | "示例: ... → 结果: ...                          │
│                        新输入: ..."                                      │
│   Few-shot            | "多个示例..."                                    │
│   Chain-of-Thought    | "让我们一步一步思考..."                         │
│   Tree-of-Thought     | "考虑所有可能的解决路径..."                      │
│   Self-Consistency    | "生成多个答案，选择最常见的"                     │
│   ReAct               | "思考 → 行动 → 观察 → 思考 → ..."               │
│   Act (Agent)         | "角色: xxx, 任务: yyy, 约束: zzz"               │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、CoT实现

```python
def chain_of_thought_prompt(question: str) -> str:
    """思维链Prompt"""
    return f"""问题: {question}

请逐步思考，展示你的推理过程：

思考过程：
1. 首先，我需要理解问题的核心
2. 然后，分析可能的解决方案
3. 接着，选择最优方案
4. 最后，得出结论

答案："""

def tree_of_thought_prompt(question: str, branching_factor: int = 3) -> str:
    """思维树Prompt"""
    return f"""问题: {question}

请从以下{branching_factor}个角度思考：

角度1: 
角度2:
角度3:
...

比较各角度的优劣，选择最佳方案。

最终答案："""
```

## 三、ReAct模式

```python
class ReActAgent:
    """ReAct Agent实现"""
    
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.history = []
    
    def react(self, query: str, max_steps: int = 10) -> str:
        """ReAct推理循环"""
        for step in range(max_steps):
            # 思考
            thought = self.llm.invoke(
                f"""基于以下观察，思考下一步做什么：
                
                问题: {query}
                历史: {self.history}
                可用工具: {list(self.tools.keys())}
                
                思考："""
            )
            
            # 决定行动
            action = self.parse_action(thought)
            
            if action == "finish":
                return thought
            
            # 执行工具
            observation = self.execute_tool(action)
            
            # 更新历史
            self.history.append({
                "thought": thought,
                "action": action,
                "observation": observation,
            })
        
        return self.history[-1]["thought"]
    
    def execute_tool(self, action: dict) -> str:
        """执行工具"""
        tool_name = action["tool"]
        tool_args = action["args"]
        
        if tool_name in self.tools:
            return self.tools[tool_name](**tool_args)
        return f"工具 {tool_name} 不存在"
```

## 四、面试高频题

### Q1: CoT和ReAct有什么区别？

```
A:
1. CoT: 纯文本推理链
2. ReAct: 推理+行动循环
```

### Q2: 如何设计Few-shot示例？

```
A:
1. 覆盖典型场景
2. 难度递进
3. 多样化输入
```

## 五、自测题

1. 解释三种Prompt模式
2. 如何实现ReAct？
3. 如何设计Few-shot？

---

## 参考文档

- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [LangChain Prompt Templates](https://python.langchain.com/docs/modules/prompts/)
