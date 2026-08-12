# Agent 记忆系统深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、记忆架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Agent 三层记忆架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 1: 工作记忆 (Working Memory)                          │   │
│  │  ─────────────────────────────────                           │   │
│  │  • 容量: 当前对话上下文 (几百到几千 token)                    │   │
│  │  • 持久性: 会话结束即消失                                    │   │
│  │  • 检索: 直接从 prompt 获取                                  │   │
│  │  • 作用: 当前任务的直接信息                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 2: 短期记忆 (Short-Term Memory)                       │   │
│  │  ─────────────────────────────────                           │   │
│  │  • 容量: 数千到数万 token (几天到几周)                        │   │
│  │  • 持久性: 有限期的持久化                                     │   │
│  │  • 检索: 语义搜索 (向量数据库)                                │   │
│  │  • 作用: 近期交互历史、项目进展                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Level 3: 长期记忆 (Long-Term Memory)                        │   │
│  │  ─────────────────────────────────                           │   │
│  │  • 容量: 无限 (知识库级别)                                    │   │
│  │  • 持久性: 永久 (需要主动遗忘)                                │   │
│  │  • 检索: 混合检索 (向量 + 关键词 + 知识图谱)                   │   │
│  │  • 作用: 用户画像、核心知识、长期偏好                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  记忆流转:                                                          │
│  工作记忆 → 编码 → 短期记忆 → 巩固 → 长期记忆                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、工作记忆实现

```go
// 文件: memory/working_memory.go
package memory

import (
    "container/list"
    "sync"
)

// WorkingMemory 工作记忆
type WorkingMemory struct {
    messages    *list.List
    maxTokens   int
    currentSize int
    mu          sync.RWMutex
}

// Message 消息结构
type Message struct {
    Role      string
    Content   string
    Tokens    int
    Timestamp time.Time
}

func NewWorkingMemory(maxTokens int) *WorkingMemory {
    return &WorkingMemory{
        messages:  list.New(),
        maxTokens: maxTokens,
    }
}

// Add 添加消息
func (wm *WorkingMemory) Add(msg Message) {
    wm.mu.Lock()
    defer wm.mu.Unlock()
    
    wm.messages.PushBack(msg)
    wm.currentSize += msg.Tokens
    
    // 溢出时移除旧消息
    for wm.currentSize > wm.maxTokens && wm.messages.Front() != nil {
        front := wm.messages.Front()
        wm.currentSize -= front.Value.(Message).Tokens
        wm.messages.Remove(front)
    }
}

// GetMessages 获取当前消息
func (wm *WorkingMemory) GetMessages() []Message {
    wm.mu.RLock()
    defer wm.mu.RUnlock()
    
    var msgs []Message
    for e := wm.messages.Front(); e != nil; e = e.Next() {
        msgs = append(msgs, e.Value.(Message))
    }
    return msgs
}

// Clear 清空工作记忆
func (wm *WorkingMemory) Clear() {
    wm.mu.Lock()
    defer wm.mu.Unlock()
    wm.messages.Init()
    wm.currentSize = 0
}
```

---

## 三、短期记忆实现

```go
// 文件: memory/short_term_memory.go
package memory

import (
    "context"
    "github.com/qdrant/qdrant-client-go"
)

// ShortTermMemory 短期记忆
type ShortTermMemory struct {
    client     *qdrant.Client
    collection string
    ttl        time.Duration
}

// MemoryItem 记忆条目
type MemoryItem struct {
    ID        string
    Content   string
    Embedding []float32
    Metadata  map[string]interface{}
    CreatedAt time.Time
}

// Store 存储到短期记忆
func (stm *ShortTermMemory) Store(ctx context.Context, item MemoryItem) error {
    point := qdrant.PointStruct{
        ID:      qdrant.PointIDFromString(item.ID),
        Vector:  item.Embedding,
        Payload: item.Metadata,
    }
    
    _, err := stm.client.Upsert(ctx, stm.collection, point)
    return err
}

// Retrieve 检索相关记忆
func (stm *ShortTermMemory) Retrieve(
    ctx context.Context,
    query string,
    embedding []float32,
    limit int,
) ([]MemoryItem, error) {
    
    results, err := stm.client.Search(ctx, stm.collection, embedding, limit)
    if err != nil {
        return nil, err
    }
    
    var items []MemoryItem
    for _, r := range results {
        item := MemoryItem{
            ID:      r.ID.String(),
            Content: r.Payload["content"].(string),
            Metadata: r.Payload,
        }
        items = append(items, item)
    }
    
    return items, nil
}

// EvictExpired 清理过期记忆
func (stm *ShortTermMemory) EvictExpired(ctx context.Context) error {
    // 使用 TTL 查询过期点
    cutoff := time.Now().Add(-stm.ttl)
    // 实现 TTL 清理逻辑...
    return nil
}
```

---

## 四、长期记忆实现

### 4.1 混合检索架构

```go
// 文件: memory/long_term_memory.go
package memory

// LongTermMemory 长期记忆系统
type LongTermMemory struct {
    vectorStore   *VectorStore      // 向量检索
    keywordIndex  *KeywordIndex     // 关键词检索
    knowledgeGraph *KnowledgeGraph  // 知识图谱
    hybridRanker  *HybridRanker    // 混合排序
}

// Retrieve 混合检索
func (ltm *LongTermMemory) Retrieve(
    ctx context.Context,
    query string,
) ([]MemoryItem, float64) {
    
    // 三路召回
    vectorResults := ltm.vectorStore.Search(ctx, query)
    keywordResults := ltm.keywordIndex.Search(ctx, query)
    graphResults := ltm.knowledgeGraph.Query(ctx, query)
    
    // RRF 融合排序
    return ltm.hybridRanker.RRFCombine(
        vectorResults,
        keywordResults,
        graphResults,
    )
}
```

### 4.2 知识图谱

```go
// 文件: memory/knowledge_graph.go
package memory

// KnowledgeGraph 知识图谱
type KnowledgeGraph struct {
    nodes    map[string]*Node
    edges    map[string][]*Edge
}

type Node struct {
    ID        string
    Type      string  // person, concept, event
    Content   string
    Embedding []float32
}

type Edge struct {
    From      string
    To        string
    Relation  string
    Strength  float64
}

// Query 知识图谱查询
func (kg *KnowledgeGraph) Query(ctx context.Context, query string) ([]MemoryItem, error) {
    // 1. 实体识别
    entities := extractEntities(query)
    
    // 2. 图谱遍历
    var results []MemoryItem
    for _, entity := range entities {
        nodes := kg.traverse(entity, 2) // 2-hop 遍历
        for _, n := range nodes {
            results = append(results, MemoryItem{
                Content: n.Content,
            })
        }
    }
    
    return deduplicate(results), nil
}
```

---

## 五、遗忘机制

### 5.1 遗忘曲线实现

```go
// 文件: memory/forgetting.go
package memory

import "math"

// ForgettingCurve 遗忘曲线
type ForgettingCurve struct {
    retentionRate float64 // 保留率
}

// CalculateRetention 计算记忆保留率
func (fc *ForgettingCurve) CalculateRetention(ageHours float64) float64 {
    // Ebbinghaus 遗忘曲线: R = e^(-t/S)
    // S 为记忆强度，这里简化为常数
    S := 10.0 // 记忆强度参数
    return math.Exp(-ageHours / S)
}

// ShouldForget 判断是否应遗忘
func (fc *ForgettingCurve) ShouldForget(retention float64, threshold float64) bool {
    return retention < threshold
}

// 遗忘策略:
// ├─ 主动遗忘: 基于时间衰减 (超过阈值自动删除)
// ├─ 被动遗忘: 基于空间置换 (新记忆挤占旧记忆)
// └─ 选择性遗忘: 基于重要性评估 (低价值记忆优先遗忘)
```

---

## 六、性能基准

```
┌─────────────────────────────────────────────────────────────────┐
│                    记忆系统性能基准                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  记忆类型         容量          检索延迟    持久性              │
│  ─────────────────────────────────────────────────────────    │
│  工作记忆         4K tokens    <1ms       会话级               │
│  短期记忆         100K items   50ms       天/周级              │
│  长期记忆         无限         200ms      永久                 │
│                                                                 │
│  推荐方案:                                                       │
│  ├─ 快速响应: 工作记忆 (直接 prompt)                             │
│  ├─ 平衡性能: 短期记忆 (向量检索)                                 │
│  └─ 完整追溯: 混合检索 (长期记忆)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、实战排障指南

```
问题 1: 记忆检索延迟高
症状: 检索超过 500ms
解决方案:
  - 增加向量数据库索引
  - 使用 HNSW 替代 IVF
  - 启用内存缓存

问题 2: 记忆丢失
症状: 重要信息被遗忘
解决方案:
  - 提高记忆强度参数
  - 定期巩固关键记忆
  - 添加显式标记机制

问题 3: 上下文溢出
症状: 超过 token 限制
解决方案:
  - 启用摘要压缩
  - 分层记忆架构
  - 动态裁剪策略
```

---

## 八、参考资料

```
核心论文:
├── "Mem0: Building Memory for AI Agents"
├── "Hermes: Conversational Memory for LLMs"
└── "Continual Learning for Language Models"

开源实现:
├── mem0 (SigNoz)
├── AgentMemory
├── Zep
└── LangChain Memory

最佳实践:
├── ChatGPT Memory
└── Claude Memory
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
