# Prompt Engineering 深度实现 - 从Zero-shot到Chain-of-Thought

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/Prompt
> **代码密度**: 30%

---

## 一、Prompt模板库

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Prompt Engineering 模板库                         │
│                                                                     │
│  1. Zero-shot Prompt                                               │
│     ─────────────────────────────────                              │
│     直接提问，无示例                                                │
│     适用: 简单任务，通用模型                                        │
│                                                                     │
│  2. One-shot Prompt                                                │
│     ─────────────────────────────────                              │
│     一个示例                                                        │
│     适用: 格式固定，少量学习                                        │
│                                                                     │
│  3. Few-shot Prompt                                                │
│     ─────────────────────────────────                              │
│     多个示例                                                        │
│     适用: 复杂任务，特定风格                                        │
│                                                                     │
│  4. Chain-of-Thought (CoT)                                         │
│     ─────────────────────────────────                              │
│     引导逐步推理                                                    │
│     适用: 数学/逻辑/复杂推理                                        │
│                                                                     │
│  5. Self-Consistency                                                │
│     ─────────────────────────────────                              │
│     多次采样取众数                                                  │
│     适用: 需要高准确率的场景                                        │
│                                                                     │
│  6. ReAct (Reasoning + Acting)                                     │
│     ─────────────────────────────────                              │
│     思考+行动交替                                                   │
│     适用: Agent工具调用                                             │
│                                                                     │
│  7. Tree-of-Thought (ToT)                                          │
│     ─────────────────────────────────                              │
│     树状搜索                                                        │
│     适用: 复杂决策/规划                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、CoT 实现

```python
# prompts/cot.py

CHAIN_OF_THOUGHT_PROMPT = """
You are a helpful assistant. Think step by step.

Problem: {problem}

Let's think step by step:
"""

# Advanced CoT
ADVANCED_COT_PROMPT = """
Analyze the following problem systematically.

## Step 1: Understand the Problem
{step1_hint}

## Step 2: Identify Key Variables
{step2_hint}

## Step 3: Apply Relevant Principles
{step3_hint}

## Step 4: Calculate/Reason
{step4_hint}

## Step 5: Verify
{step5_hint}

Final Answer: 
"""

# Tree of Thoughts
TREE_OF_THOUGHTS_PROMPT = """
Generate {num_branches} different approaches to solve this problem.

Problem: {problem}

For each approach, analyze:
- Feasibility (1-5)
- Expected accuracy (1-5)
- Computation cost (low/medium/high)

Then select the best approach and execute it.
"""

class PromptEngine:
    """Prompt工程引擎"""
    
    def __init__(self):
        self.templates = {
            'zero_shot': ZERO_SHOT_TEMPLATE,
            'few_shot': FEW_SHOT_TEMPLATE,
            'cot': CHAIN_OF_THOUGHT_PROMPT,
            'react': REACT_TEMPLATE,
            'tot': TREE_OF_THOUGHTS_PROMPT,
        }
    
    def build_prompt(self, method: str, **kwargs) -> str:
        """构建Prompt"""
        template = self.templates[method]
        return template.format(**kwargs)
    
    def auto_select(self, task: Task) -> str:
        """自动选择Prompt方法"""
        if task.complexity == 'simple':
            return 'zero_shot'
        elif task.needs_reasoning:
            return 'cot'
        elif task.needs_tools:
            return 'react'
        elif task.is_decisive:
            return 'tot'
        else:
            return 'few_shot'
```

---

## 三、自测题

1. **CoT相比Zero-shot的优势？**
   - 引导模型分步推理，提高复杂任务准确率

2. **什么时候使用ReAct而不是纯CoT？**
   - 需要调用外部工具时

