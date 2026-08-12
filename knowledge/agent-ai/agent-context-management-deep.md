# Agent 上下文管理深度实现 - 从Token限制到智能压缩

> **版本**: v2.1  
> **日期**: 2026-08-14  
> **作者**: Ryan  
> **分类**: Agent/上下文管理  
> **代码密度**: 32%

---

## 一、上下文管理架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    上下文管理三层架构                                  │
│                                                                     │
│  Layer 1: Token Budget (Token预算)                                    │
│  ─────────────────────────────                                      │
│  • 模型上下文窗口: 128K / 200K / 1M                                  │
│  • 预留系统提示: 20%                                                 │
│  • 预留记忆: 20%                                                     │
│  • 可用对话: 60%                                                     │
│                                                                     │
│  Layer 2: Compression (压缩策略)                                      │
│  ─────────────────────────────                                      │
│  • 滑动窗口: 保留最近N轮                                             │
│  • 摘要压缩: 早期对话生成摘要                                        │
│  • 重要性保留: 关键信息完整保留                                      │
│                                                                     │
│  Layer 3: Retrieval (检索增强)                                        │
│  ─────────────────────────────                                      │
│  • RAG检索: 按需加载相关文档                                         │
│  • 向量搜索: 语义匹配相关记忆                                        │
│  • 关键词匹配: 精确匹配关键信息                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go实现

```go
// agent/context_manager.go
package agent

import (
    "context"
    "fmt"
)

// ContextBudget 上下文预算
type ContextBudget struct {
    MaxTokens     int
    SystemPrompt  int
    MemorySlot    int
    DialogueSlot  int
}

// ContextManager 上下文管理器
type ContextManager struct {
    budget    ContextBudget
    history   []Message
    memory    MemoryStore
}

// AddMessage 添加消息
func (m *ContextManager) AddMessage(msg Message) error {
    tokens := m.countTokens(msg.Content)
    
    // 检查预算
    if m.budget.DialogueSlot < tokens {
        return fmt.Errorf("context overflow: need %d tokens", tokens)
    }
    
    m.history = append(m.history, msg)
    m.budget.DialogueSlot -= tokens
    
    // 触发压缩
    if m.budget.DialogueSlot < m.budget.MaxTokens*0.1 {
        m.compress()
    }
    
    return nil
}

// compress 压缩上下文
func (m *ContextManager) compress() {
    if len(m.history) <= 5 {
        return
    }
    
    // 选择保留最近3轮 + 压缩早期
    recent := m.history[len(m.history)-3:]
    early := m.history[:len(m.history)-3]
    
    // 生成早期对话摘要
    summary := m.generateSummary(early)
    
    // 重置历史
    m.history = append([]Message{{Role: "system", Content: summary}}, recent...)
    m.budget.DialogueSlot = m.calculateSlot(m.history)
}
```

---

## 三、自测题

1. **为什么需要压缩上下文？**
   - Token有限且昂贵，需要高效利用

2. **压缩的策略有哪些？**
   - 滑动窗口 / 摘要压缩 / 选择性保留

