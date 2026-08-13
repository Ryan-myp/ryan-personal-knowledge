# Agent 评估体系 - 资深专家深度实现

## 一、评估维度

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Agent 评估维度                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   维度            | 指标                  | 评估方法                    │
│   ────────────────┼──────────────────────┼─────────────────────────────│
│   准确性          | F1 Score             | 测试集验证                    │
│   效率            | 平均响应时间          | 性能测试                      │
│   可靠性          | 成功率               | 故障注入测试                    │
│   适应性          | 泛化能力             | 跨领域测试                      │
│   安全性          | 无害率               | 红队测试                       │
│   用户体验        | CSAT得分             | 用户调研                       │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、评估实现

```python
import json
import numpy as np
from typing import List, Dict, Any
from datasets import Dataset

class AgentEvaluator:
    """Agent评估器"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        
    def evaluate_accuracy(self, test_cases: List[Dict]) -> Dict:
        """评估准确性"""
        correct = 0
        total = len(test_cases)
        details = []
        
        for case in test_cases:
            agent_response = self.run_agent(case["query"])
            expected = case["expected"]
            
            # 计算准确率
            is_correct = self.calculate_similarity(agent_response, expected)
            if is_correct:
                correct += 1
            
            details.append({
                "query": case["query"],
                "expected": expected,
                "actual": agent_response,
                "correct": is_correct,
            })
        
        return {
            "accuracy": correct / total,
            "total": total,
            "correct": correct,
            "details": details,
        }
    
    def evaluate_efficiency(self, test_cases: List[Dict]) -> Dict:
        """评估效率"""
        response_times = []
        
        for case in test_cases:
            start = time.time()
            self.run_agent(case["query"])
            elapsed = time.time() - start
            response_times.append(elapsed)
        
        return {
            "avg_response_time": np.mean(response_times),
            "p50_response_time": np.percentile(response_times, 50),
            "p95_response_time": np.percentile(response_times, 95),
            "p99_response_time": np.percentile(response_times, 99),
        }
    
    def evaluate_safety(self, test_cases: List[Dict]) -> Dict:
        """评估安全性"""
        safe_count = 0
        total = len(test_cases)
        
        for case in test_cases:
            response = self.run_agent(case["query"])
            if not self.is_harmful(response):
                safe_count += 1
        
        return {
            "safety_rate": safe_count / total,
            "harmful_count": total - safe_count,
        }
    
    def run_agent(self, query: str) -> str:
        """运行Agent"""
        # 实际Agent调用逻辑
        pass
    
    def calculate_similarity(self, response: str, expected: str) -> bool:
        """计算相似度"""
        # 可以使用LLM评估或字符串匹配
        pass
    
    def is_harmful(self, response: str) -> bool:
        """检测有害内容"""
        harmful_keywords = ["hate", "violence", "discrimination"]
        return any(keyword in response.lower() for keyword in harmful_keywords)
```

## 三、RAGAS评估

```python
from ragas import EvaluationDataset, evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

# 准备评估数据集
dataset = EvaluationDataset.from_json("test_cases.json")

# 定义评估指标
metrics = [
    faithfulness,      # 忠实度: 答案是否基于上下文
    answer_relevancy,  # 相关性: 答案是否与问题相关
    context_precision, # 上下文精确度
]

# 执行评估
result = evaluate(dataset, metrics=metrics)

print(f"Faithfulness: {result['faithfulness']}")
print(f"Answer Relevancy: {result['answer_relevancy']}")
print(f"Context Precision: {result['context_precision']}")
```

## 四、面试高频题

### Q1: 如何评估Agent准确性？

```
A:
1. 构建测试集
2. 对比预期输出
3. 计算F1 Score
```

### Q2: 如何评估安全性？

```
A:
1. 红队测试
2. 有害内容检测
3. 边界case测试
```

## 五、自测题

1. 解释评估维度
2. 如何实现RAGAS评估？
3. 如何设计测试用例？

---

## 参考文档

- [RAGAS](https://docs.ragas.io/)
- [LangSmith](https://smith.langchain.com/)
