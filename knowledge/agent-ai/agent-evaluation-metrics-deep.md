# Agent 评估指标体系深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、评估维度框架

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Agent 评估框架                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                      核心能力 (Core)                            │      │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │      │
│   │  │ 任务完成  │ │ 工具调用  │ │ 推理质量  │ │ 错误处理  │         │      │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                              │                                              │
│              ┌───────────────┼───────────────┐                            │
│              ▼               ▼               ▼                            │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                    效率指标 (Efficiency)                          │    │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │    │
│   │  │ 响应延迟  │ │ Token消耗 │ │ 迭代次数  │ │ 资源使用  │         │    │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│              ┌───────────────┼───────────────┐                            │
│              ▼               ▼               ▼                            │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                    用户体验 (Experience)                          │    │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │    │
│   │  │ 满意度   │ │ 可解释性  │ │ 安全性   │ │ 一致性   │         │    │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心指标计算

```python
# 文件: evaluation/metrics.py

from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np

@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    success: bool
    steps: List[Dict[str, Any]]
    latency_ms: float
    tokens_used: int
    error: str = None

class AgentEvaluator:
    """Agent 评估器"""
    
    def __init__(self):
        self.results: List[TaskResult] = []
        
    def evaluate(self, result: TaskResult):
        self.results.append(result)
        
    # ─── 任务完成率 ───
    def task_completion_rate(self) -> float:
        if not self.results:
            return 0.0
        completed = sum(1 for r in self.results if r.success)
        return completed / len(self.results)
    
    # ─── 平均响应延迟 ───
    def avg_latency(self) -> float:
        if not self.results:
            return 0.0
        return np.mean([r.latency_ms for r in self.results])
    
    # ─── P95 延迟 ───
    def p95_latency(self) -> float:
        if not self.results:
            return 0.0
        latencies = sorted([r.latency_ms for r in self.results])
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies)-1)]
    
    # ─── Token 效率 ───
    def tokens_per_task(self) -> float:
        if not self.results:
            return 0.0
        return np.mean([r.tokens_used for r in self.results])
    
    # ─── 工具调用准确率 ───
    def tool_call_accuracy(self) -> float:
        total_calls = 0
        correct_calls = 0
        
        for result in self.results:
            for step in result.steps:
                if 'tool_call' in step:
                    total_calls += 1
                    if step.get('tool_success'):
                        correct_calls += 1
                        
        return correct_calls / total_calls if total_calls > 0 else 0.0
    
    # ─── 综合评分 ───
    def composite_score(self) -> Dict[str, float]:
        return {
            'task_completion': self.task_completion_rate() * 100,
            'latency_score': max(0, 100 - self.avg_latency() / 10),
            'token_efficiency': max(0, 100 - self.tokens_per_task() / 100),
            'tool_accuracy': self.tool_call_accuracy() * 100,
        }
```

---

## 三、RAGAS 评估集成

```python
# 文件: evaluation/ragas_integration.py

from ragas import EvaluationDataset, evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

# ─── 构建评估数据集 ───
dataset = EvaluationDataset.from_list([
    {
        "question": "什么是 RTB 竞价流程？",
        "answer": "RTB 是实时竞价的缩写...",
        "contexts": ["程序化广告竞价技术..."],
        "ground_truth": "RTB 是 Real-Time Bidding 的缩写..."
    }
])

# ─── 执行评估 ───
results = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision]
)

# ─── 输出报告 ───
print(f"Faithfulness: {results['faithfulness']:.4f}")
print(f"Answer Relevancy: {results['answer_relevancy']:.4f}")
print(f"Context Precision: {results['context_precision']:.4f}")
```

---

## 四、参考资料

```
评估框架:
├── RAGAS: https://docs.ragas.io/
├── LangChain Evaluators: https://python.langchain.com/docs/modules/model_io/evaluation/
└── DeepEval: https://docs.deepeval.com/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
