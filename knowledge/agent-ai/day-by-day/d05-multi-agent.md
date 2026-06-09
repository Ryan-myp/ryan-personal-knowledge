# Day 5: 多 Agent 协作模式

> 学习目标: 理解多 Agent 协作的原理和实现

---

## 一、为什么需要多 Agent？

```
单 Agent 的局限:
- 复杂任务需要分工
- 不同领域需要不同专业知识
- 串行执行效率低

多 Agent 的优势:
- 并行执行提高效率
- 互相审查提高质量
- 专业分工提升效果
```

---

## 二、4 种协作模式

```
1. 链式协作 (Pipeline)
   Agent1 → Agent2 → Agent3
   适用: 线性流程，如 研究→写作→编辑

2. 树状协作 (Tree)
        Manager
       /    |    \
    A1     A2    A3
   / \    / \    / \
  B1 B2  B3 B4  B5 B6
   适用: 并行探索，如 多路径调研

3. 图状协作 (Graph)
   A1 ↔ A2 ↔ A3
   ↑    ↓    ↑
   A4 ← A5 → A6
   适用: 复杂交互，如 辩论、谈判

4. 竞争协作 (Competition)
   A1 提案 → A2 审查 → A3 改进
   适用: 质量提升，如 代码审查
```

---

## 三、源码实现

```python
class MultiAgentSystem:
    """多 Agent 协作系统"""
    
    def __init__(self):
        self.agents = {}
        self.comm_bus = AgentCommunicationBus()
        
    def execute_task(self, task: str) -> str:
        """
        执行复杂任务
        
        1. 任务分解
        2. Agent 分配
        3. 并行执行
        4. 结果整合
        5. 质量审查
        """
        # 1. 任务分解
        subtasks = self.decompose(task)
        
        # 2. Agent 分配
        assignments = self.assign_agents(subtasks)
        
        # 3. 并行执行
        results = asyncio.gather(*[
            self.execute_subtask(assignments[i], subtasks[i])
            for i in range(len(subtasks))
        ])
        
        # 4. 结果整合
        integrated = self.integrate_results(results)
        
        # 5. 质量审查
        final = self.review(integrated)
        return final
```

---

## 四、自测

### 问题 1
什么时候适合用多 Agent？
<details>
<summary>查看答案</summary>

- 任务可分解为多个子任务
- 需要不同专业知识
- 需要互相审查提高质量
- 需要并行执行提高效率
</details>

---

*今天花 30 分钟读完 + 20 分钟设计 = 理解多 Agent*
