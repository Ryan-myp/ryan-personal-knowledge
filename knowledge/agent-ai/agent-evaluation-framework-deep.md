# Agent 评估框架深度实现 - 从自动化到人工审核

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/评估  
> **代码密度**: 30%

---

## 一、评估体系架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 评估四维度                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  1. Correctness (正确性)                                     │   │
│  │     • 答案准确性                                              │   │
│  │     • 事实核查                                                │   │
│  │     • 逻辑一致性                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  2. Safety (安全性)                                          │   │
│  │     • 有害内容检测                                            │   │
│  │     • 隐私泄露检测                                            │   │
│  │     • 越狱攻击检测                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  3. Efficiency (效率)                                        │   │
│  │     • 响应延迟                                                │   │
│  │     • Token消耗                                               │   │
│  │     • 工具调用次数                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  4. User Satisfaction (用户满意度)                             │   │
│  │     • 人工评分                                                │   │
│  │     • 点赞/点踩                                               │   │
│  │     • 任务完成率                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、自动化评估

```python
# agent/evaluation/automated.py
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class EvaluationResult:
    dimension: str  # correctness/safety/efficiency
    score: float    # 0-1
    details: str
    passed: bool

class AutomatedEvaluator:
    """自动化评估器"""
    
    def __init__(self):
        self.evaluators = {
            'correctness': CorrectnessEvaluator(),
            'safety': SafetyEvaluator(),
            'efficiency': EfficiencyEvaluator(),
        }
    
    async def evaluate(self, task: Task, output: str) -> List[EvaluationResult]:
        """评估单个输出"""
        results = []
        
        # 正确性评估
        correctness = await self.evaluators['correctness'].evaluate(task, output)
        results.append(correctness)
        
        # 安全性评估
        safety = await self.evaluators['safety'].evaluate(output)
        results.append(safety)
        
        # 效率评估
        efficiency = self.evaluators['efficiency'].evaluate(output)
        results.append(efficiency)
        
        return results
    
    def aggregate(self, results: List[EvaluationResult]) -> dict:
        """聚合评估结果"""
        scores = {r.dimension: r.score for r in results}
        
        # 加权平均
        weights = {
            'correctness': 0.4,
            'safety': 0.3,
            'efficiency': 0.2,
            'user_satisfaction': 0.1,
        }
        
        weighted_score = sum(
            scores.get(d, 0) * w 
            for d, w in weights.items()
        )
        
        return {
            'scores': scores,
            'weighted': weighted_score,
            'passed': all(r.passed for r in results),
        }


class CorrectnessEvaluator:
    """正确性评估"""
    
    async def evaluate(self, task: Task, output: str) -> EvaluationResult:
        # 使用LLM作为judge
        prompt = self.build_prompt(task, output)
        judge_response = await self.llm.evaluate(prompt)
        
        # 评分
        score = self.parse_score(judge_response)
        
        return EvaluationResult(
            dimension='correctness',
            score=score,
            details=judge_response,
            passed=score >= 0.7,
        )


class SafetyEvaluator:
    """安全性评估"""
    
    def evaluate(self, output: str) -> EvaluationResult:
        # 关键词检测
        unsafe_keywords = self.load_keywords()
        hits = [k for k in unsafe_keywords if k in output]
        
        # LLM判断
        llm_result = self.llm_classify(output)
        
        score = 0.0 if hits or llm_result == 'unsafe' else 1.0
        
        return EvaluationResult(
            dimension='safety',
            score=score,
            details=f"keywords:{hits}, llm:{llm_result}",
            passed=score == 1.0,
        )
```

---

## 三、自测题

1. **为什么需要自动化+人工混合评估？**
   - 自动化效率高但可能误判，人工准确但成本高

2. **正确性评估的挑战？**
   - 主观性、多标准、边界情况

