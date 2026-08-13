# Agent 记忆系统 v2 - 资深专家深度实现

## 一、三层记忆架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      三层记忆架构                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  短期记忆 (Working Memory)                                         │   │
│   │  • 容量: 数千token                                                  │   │
│   │  • 有效期: 当前对话                                                  │   │
│   │  • 实现: Context Window                                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  长期记忆 (Long-term Memory)                                       │   │
│   │  • 容量: 无限                                                      │   │
│   │  • 有效期: 永久                                                    │   │
│   │  • 实现: Vector DB + Knowledge Graph                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  程序记忆 (Procedural Memory)                                      │   │
│   │  • 技能: 可复用的任务模板                                            │   │
│   │  • 策略: 最佳实践模式                                                │   │
│   │  • 实现: Skill Registry + Tool Library                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、记忆管理实现

```go
package memory

import (
    "context"
    "sync"
    "time"
)

// ShortTermMemory 短期记忆
type ShortTermMemory struct {
    mu      sync.RWMutex
    entries []MemoryEntry
    maxLen  int
}

// LongTermMemory 长期记忆
type LongTermMemory struct {
    vectorDB *VectorStore
    graphDB  *KnowledgeGraph
}

// MemoryEntry 记忆条目
type MemoryEntry struct {
    ID        string    `json:"id"`
    Content   string    `json:"content"`
    Type      string    `json:"type"` // fact, event, skill
    Timestamp time.Time `json:"timestamp"`
    Weight    float64   `json:"weight"`
}

// Add 添加短期记忆
func (m *ShortTermMemory) Add(entry MemoryEntry) {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    m.entries = append(m.entries, entry)
    
    // 超过容量，迁移到长期记忆
    if len(m.entries) > m.maxLen {
        m.flushToLongTerm()
    }
}

// flushToLongTerm 刷新到长期记忆
func (m *ShortTermMemory) flushToLongTerm() {
    // 迁移最后10%到长期记忆
    cutoff := len(m.entries) * 9 / 10
    toSave := m.entries[cutoff:]
    m.entries = m.entries[:cutoff]
    
    // 存入向量数据库
    for _, entry := range toSave {
        m.vectorDB.Index(entry.Content, entry.Type)
    }
}

// Retrieve 检索记忆
func (m *LongTermMemory) Retrieve(query string, topK int) []MemoryEntry {
    // 向量检索
    vectorResults := m.vectorDB.Search(query, topK)
    
    // 图谱检索
    graphResults := m.graphDB.Query(query)
    
    // RRF融合
    return m.rrfFuse(vectorResults, graphResults, topK)
}

// RRF  Reciprocal Rank Fusion
func (m *LongTermMemory) rrfFuse(vector, graph []MemoryEntry, k int) []MemoryEntry {
    scores := make(map[string]float64)
    
    for i, entry := range vector {
        scores[entry.ID] += 1.0 / (k + i + 1)
    }
    for i, entry := range graph {
        scores[entry.ID] += 1.0 / (k + i + 1)
    }
    
    // 排序返回
    return sortByScore(scores)
}
```

## 三、遗忘曲线实现

```python
import math
from datetime import datetime

class ForgettingCurve:
    """艾宾浩斯遗忘曲线"""
    
    def __init__(self):
        # 遗忘速率参数
        self.rate = 0.5  # 每小时遗忘率
        
    def calculate_retention(self, hours_since_encode):
        """计算保留率"""
        # Ebbinghaus公式: R = e^(-t/S)
        retention = math.exp(-hours_since_encode / (1.0 / self.rate))
        return max(0.0, min(1.0, retention))
    
    def should_retrieve(self, entry, current_time):
        """判断是否需要重新检索"""
        encoded_at = entry['timestamp']
        hours_since = (current_time - encoded_at).total_seconds() / 3600
        
        retention = self.calculate_retention(hours_since)
        
        # 保留率低于阈值，需要重新检索
        return retention < 0.3
    
    def reinforce(self, entry):
        """强化记忆（降低遗忘率）"""
        entry['strength'] = min(1.0, entry.get('strength', 0.5) + 0.1)
        entry['last_retrieved'] = datetime.now()
```

## 四、面试高频题

### Q1: 如何实现记忆迁移？

```
A:
1. 设置容量上限
2. 超限时触发迁移
3. 使用遗忘曲线评估重要性
```

### Q2: 如何处理记忆冲突？

```
A:
1. 时间戳优先
2. 置信度加权
3. 人工确认机制
```

## 五、自测题

1. 解释三层记忆架构
2. 如何实现遗忘曲线？
3. 如何处理记忆冲突？

---

## 参考文档

- [Mem0](https://github.com/mem0ai/mem0)
- [LangChain Memory](https://python.langchain.com/docs/modules/memory/)
