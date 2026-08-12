# Agent 成本优化深度实现 - Token控制与效率提升

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/成本优化  
> **代码密度**: 32%

---

## 一、Token控制策略

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Token控制三层架构                                  │
│                                                                     │
│  Layer 1: Input Optimization (输入优化)                              │
│  ─────────────────────────────                                     │
│  • Context压缩: 从历史消息提取关键信息                               │
│  • 选择性检索: 只检索相关记忆片段                                    │
│  • 摘要生成: 长对话生成摘要代替原文                                   │
│                                                                     │
│  Layer 2: Process Optimization (过程优化)                            │
│  ─────────────────────────────                                     │
│  • 并行调用: 多个工具调用并发执行                                     │
│  • 早停策略: 达到目标立即返回                                         │
│  • 缓存复用: 相同输入缓存结果                                         │
│                                                                     │
│  Layer 3: Output Optimization (输出优化)                             │
│  ─────────────────────────────                                     │
│  • 结构化输出: JSON Schema约束                                       │
│  • 流式输出: 逐步返回减少等待                                          │
│  • 增量输出: 只返回变化的部分                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、成本计算模型

```go
// agent/cost_optimizer.go
package agent

import "time"

// TokenCost Token成本
type TokenCost struct {
    InputTokens  int
    OutputTokens int
    TotalCost    float64
}

// CostCalculator 成本计算器
type CostCalculator struct {
    models map[string]ModelPrice
}

type ModelPrice struct {
    InputPerMillion  float64
    OutputPerMillion float64
}

// CalculateCost 计算成本
func (c *CostCalculator) CalculateCost(model string, inputTokens, outputTokens int) *TokenCost {
    price := c.models[model]
    
    inputCost := float64(inputTokens) / 1_000_000 * price.InputPerMillion
    outputCost := float64(outputTokens) / 1_000_000 * price.OutputPerMillion
    
    return &TokenCost{
        InputTokens:  inputTokens,
        OutputTokens: outputTokens,
        TotalCost:    inputCost + outputCost,
    }
}

// BudgetManager 预算管理
type BudgetManager struct {
    dailyBudget  float64
    monthlyBudget float64
    spentToday   float64
    spentMonth   float64
}

// CheckBudget 检查预算
func (m *BudgetManager) CheckBudget(cost float64) error {
    if m.spentToday+cost > m.dailyBudget {
        return ErrDailyBudgetExceeded
    }
    if m.spentMonth+cost > m.monthlyBudget {
        return ErrMonthlyBudgetExceeded
    }
    return nil
}
```

---

## 三、自测题

1. **如何降低Agent的Token消耗？**
   - 输入压缩 + 并行调用 + 缓存复用

2. **为什么要设置预算限制？**
   - 防止异常导致成本失控

