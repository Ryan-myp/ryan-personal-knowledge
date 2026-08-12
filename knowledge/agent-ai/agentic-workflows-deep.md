# Agentic Workflow 工作流模式深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、工作流模式对比

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agentic Workflow 模式                                │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│     模式        │    适用场景     │     复杂度      │       示例             │
├─────────────────┼─────────────────┼─────────────────┼───────────────────────┤
│ Sequential      │ 线性任务        │ ⭐              │ 数据清洗→分析→报告     │
│ Parallel        │ 独立子任务      │ ⭐⭐            │ 多语言翻译→合并        │
│ Hierarchical    │ 有依赖关系      │ ⭐⭐⭐          │ 拆解→执行→汇总        │
│ Loop            │ 迭代优化        │ ⭐⭐⭐          │ 代码生成→测试→修复     │
│ Router          │ 条件分支        │ ⭐⭐            │ 按意图分发             │
│ Subgraph        │ 嵌套工作流      │ ⭐⭐⭐⭐        │ 复杂业务编排           │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

---

## 二、Sequential 模式实现

```python
# 文件: workflows/sequential.py

from typing import List, Callable, Any
from dataclasses import dataclass
import asyncio

@dataclass
class WorkflowState:
    """工作流状态"""
    data: dict
    history: List[dict]
    errors: List[str]

class SequentialWorkflow:
    """顺序执行工作流"""
    
    def __init__(self, steps: List[Callable]):
        self.steps = steps
        
    async def execute(self, initial_state: WorkflowState) -> WorkflowState:
        state = initial_state
        
        for i, step in enumerate(self.steps):
            try:
                # 执行步骤
                result = await step(state)
                
                # 记录历史
                state.history.append({
                    "step": i,
                    "name": step.__name__,
                    "status": "success",
                    "result": result
                })
                
                # 更新状态
                state.data.update(result)
                
            except Exception as e:
                state.errors.append(f"Step {i} failed: {str(e)}")
                state.history.append({
                    "step": i,
                    "name": step.__name__,
                    "status": "failed",
                    "error": str(e)
                })
                break  # 失败中止
                
        return state


# ─── 广告创意生成工作流示例 ───

async def fetch_market_insights(state: WorkflowState) -> dict:
    """获取市场洞察"""
    insights = await generate_text(
        prompt="分析当前广告市场趋势",
        model="gpt-4"
    )
    return {"insights": insights}

async def generate_concepts(state: WorkflowState) -> dict:
    """生成创意概念"""
    concepts = await generate_text(
        prompt=f"基于市场洞察生成广告创意:\n{state.data['insights']}",
        model="gpt-4"
    )
    return {"concepts": concepts}

async def refine_copies(state: WorkflowState) -> dict:
    """优化文案"""
    refined = await generate_text(
        prompt=f"优化以下广告文案:\n{state.data['concepts']}",
        model="gpt-4"
    )
    return {"final_copies": refined}

async def validate_compliance(state: WorkflowState) -> dict:
    """合规检查"""
    valid = await check_compliance(state.data["final_copies"])
    return {"compliance_status": valid}

# 构建工作流
creative_workflow = SequentialWorkflow([
    fetch_market_insights,
    generate_concepts,
    refine_copies,
    validate_compliance
])

# 执行
initial_state = WorkflowState(data={}, history=[], errors=[])
result = await creative_workflow.execute(initial_state)
```

---

## 三、Loop 模式实现

```python
# 文件: workflows/loop.py

class LoopWorkflow:
    """循环工作流 - 带终止条件"""
    
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        
    async def execute(
        self,
        loop_body: Callable,
        condition: Callable,
        initial_state: WorkflowState
    ) -> WorkflowState:
        state = initial_state
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 执行循环体
            new_state = await loop_body(state)
            
            # 检查终止条件
            if await condition(new_state):
                state = new_state
                break
                
            state = new_state
            
        return state


# ─── 代码优化循环示例 ───

async def improve_code(state: WorkflowState) -> WorkflowState:
    """改进代码"""
    improved = await generate_text(
        prompt=f"改进以下代码:\n{state.data['code']}",
        model="claude-3-opus"
    )
    return WorkflowState(
        data={"code": improved, "iteration": state.data.get("iteration", 0) + 1},
        history=state.history,
        errors=state.errors
    )

async def is_satisfied(state: WorkflowState) -> bool:
    """检查是否满意"""
    feedback = await generate_text(
        prompt=f"这段代码是否满足需求?\n{state.data['code']}",
        model="gpt-4"
    )
    return "满意" in feedback or state.data.get("iteration", 0) >= 3

workflow = LoopWorkflow(max_iterations=5)
result = await workflow.execute(improve_code, is_satisfied, initial_state)
```

---

## 四、参考资料

```
工作流引擎:
├── LangGraph: 状态图工作流
├── Temporal: 生产级编排
└── Prefect: Python 工作流

模式参考:
├── Microsoft AutoGen: 对话驱动
├── CrewAI: 角色协作
└── LangChain Agents: 工具使用
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
