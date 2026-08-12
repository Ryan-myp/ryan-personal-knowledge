# Agent 多轮对话深度实现 - 上下文管理与策略

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/多轮对话  
> **代码密度**: 30%

---

## 一、上下文管理

```
┌─────────────────────────────────────────────────────────────────────┐
│                    多轮对话上下文管理                                  │
│                                                                     │
│  Strategy 1: Sliding Window (滑动窗口)                               │
│  ─────────────────────────────                                      │
│  • 保留最近N轮对话                                                   │
│  • 优点: 简单高效                                                    │
│  • 缺点: 可能丢失早期关键信息                                        │
│                                                                     │
│  Strategy 2: Summary Buffer (摘要缓冲)                               │
│  ─────────────────────────────                                      │
│  • 早期对话生成摘要                                                   │
│  • 保留近期完整对话                                                  │
│  • 优点: 平衡记忆和成本                                              │
│                                                                     │
│  Strategy 3: Selective Retention (选择性保留)                         │
│  ─────────────────────────────                                      │
│  • 基于重要性评分保留                                                │
│  • 关键决策点完整保留                                                │
│  • 优点: 信息密度高                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go实现

```go
// agent/multi_turn.go
package agent

import (
    "context"
)

// DialogueState 对话状态
type DialogueState struct {
    SessionID   string
    Turns       []Turn
    Context     Context
    Summary     string
}

// Turn 对话轮次
type Turn struct {
    Role       string
    Content    string
    Timestamp  time.Time
    Tokens     int
    Cost       float64
}

// ContextManager 上下文管理器
type ContextManager struct {
    maxTokens int
    windowSize int
}

// AddTurn 添加对话轮次
func (m *ContextManager) AddTurn(state *DialogueState, turn Turn) {
    state.Turns = append(state.Turns, turn)
    
    // 检查token限制
    totalTokens := m.countTokens(state.Turns)
    if totalTokens > m.maxTokens {
        m.compact(state)
    }
}

// compact 上下文压缩
func (m *ContextManager) compact(state *DialogueState) {
    // 滑动窗口
    if len(state.Turns) > m.windowSize {
        state.Turns = state.Turns[len(state.Turns)-m.windowSize:]
    }
}
```

---

## 三、自测题

1. **滑动窗口的缺点？**
   - 可能丢失早期关键信息

2. **如何平衡上下文长度和成本？**
   - 摘要缓冲策略

