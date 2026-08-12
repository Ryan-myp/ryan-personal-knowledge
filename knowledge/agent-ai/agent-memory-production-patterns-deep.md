# Agent 记忆系统生产模式深度实现

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 30%

---

## 一、三层记忆架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 三层记忆架构                                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Working Memory (工作记忆)                                    │   │
│  │  • 容量: 当前对话上下文 (4K-32K tokens)                       │   │
│  │  • 存储: 内存 (Redis/内存)                                     │   │
│  │  • 生命周期: 单次会话                                        │   │
│  │  • 访问: 直接读取                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ↓ 遗忘/压缩                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Short-term Memory (短期记忆)                                  │   │
│  │  • 容量: 数天到数周 (数百条记录)                               │   │
│  │  • 存储: 向量数据库 (Qdrant/Weaviate)                         │   │
│  │  • 生命周期: 自动遗忘 (Ebbinghaus 曲线)                        │   │
│  │  • 访问: 语义检索 + 时间排序                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ↓ 固化/结构化                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Long-term Memory (长期记忆)                                   │   │
│  │  • 容量: 无限                                               │   │
│  │  • 存储: 图数据库 (Neo4j) + 向量库                            │   │
│  │  • 生命周期: 持久化                                         │   │
│  │  • 访问: 知识图谱查询 + 向量检索                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、工作记忆实现

```go
// memory/working_memory.go
package memory

import (
    "container/list"
    "sync"
    "time"
)

// Message 消息结构
type Message struct {
    Role      string    `json:"role"`       // system/user/assistant
    Content   string    `json:"content"`
    Timestamp time.Time `json:"timestamp"`
    Tokens    int       `json:"tokens"`
}

// WorkingMemory 工作记忆
type WorkingMemory struct {
    mu       sync.Mutex
    messages *list.List  // 双端队列
    maxTokens int
    maxAge   time.Duration
}

// NewWorkingMemory 创建工作记忆
func NewWorkingMemory(maxTokens int, maxAge time.Duration) *WorkingMemory {
    return &WorkingMemory{
        messages:  list.New(),
        maxTokens: maxTokens,
        maxAge:    maxAge,
    }
}

// Add 添加消息
func (wm *WorkingMemory) Add(role, content string, tokens int) {
    wm.mu.Lock()
    defer wm.mu.Unlock()
    
    msg := &Message{
        Role:      role,
        Content:   content,
        Timestamp: time.Now(),
        Tokens:    tokens,
    }
    wm.messages.PushBack(msg)
    
    // 过期清理
    wm.evictExpired()
    // Token 限制
    wm.evictByTokens()
}

// GetContext 获取上下文
func (wm *WorkingMemory) GetContext() []Message {
    wm.mu.Lock()
    defer wm.mu.Unlock()
    
    var result []Message
    for e := wm.messages.Front(); e != nil; e = e.Next() {
        result = append(result, *e.Value.(*Message))
    }
    return result
}

func (wm *WorkingMemory) evictExpired() {
    cutoff := time.Now().Add(-wm.maxAge)
    for e := wm.messages.Front(); e != nil; {
        next := e.Next()
        msg := e.Value.(*Message)
        if msg.Timestamp.Before(cutoff) {
            wm.messages.Remove(e)
        }
        e = next
    }
}

func (wm *WorkingMemory) evictByTokens() {
    total := 0
    for e := wm.messages.Front(); e != nil; e = e.Next() {
        total += e.Value.(*Message).Tokens
    }
    // 从头部开始移除
    for total > wm.maxTokens && wm.messages.Front() != nil {
        total -= wm.messages.Remove(wm.messages.Front()).(*Message).Tokens
    }
}
```

---

## 三、短期记忆 (向量检索)

```go
// memory/short_term.go
package memory

import (
    "context"
    "github.com/qdrant/qdrant-client-go/qdrant"
)

// ShortTermMemory 短期记忆
type ShortTermMemory struct {
    client *qdrant.Client
    collection string
}

// AddToMemory 添加到短期记忆
func (m *ShortTermMemory) AddToMemory(ctx context.Context, msg Message, embedding []float32) error {
    point := qdrant.PointStruct{
        ID: qdrant.PointId{Num: uint64(time.Now().UnixNano())},
        Payload: map[string]*qdrant.Value{
            "role":     {Kind: &qdrant.Value_StringValue{StringValue: msg.Role}},
            "content":  {Kind: &qdrant.Value_StringValue{StringValue: msg.Content}},
            "timestamp": {Kind: &qdrant.Value_IntegerValue{IntegerValue: msg.Timestamp.Unix()}},
        },
        Vector: embedding,
    }
    
    _, err := m.client.Upsert(ctx, &qdrant.UpsertPoints{
        CollectionName: m.collection,
        Points: []qdrant.PointStruct{point},
    })
    return err
}

// Retrieve 检索相关记忆
func (m *ShortTermMemory) Retrieve(ctx context.Context, queryEmbedding []float32, k int) ([]Message, error) {
    res, err := m.client.Search(ctx, &qdrant.SearchPoints{
        CollectionName: m.collection,
        Vector:         queryEmbedding,
        Limit:          uint64(k),
        WithPayload:    true,
    })
    if err != nil {
        return nil, err
    }
    
    var messages []Message
    for _, point := range res {
        messages = append(messages, Message{
            Role:    point.Payload["role"].GetStringValue(),
            Content: point.Payload["content"].GetStringValue(),
        })
    }
    return messages, nil
}
```

---

## 四、艾宾浩斯遗忘曲线

```go
// memory/forgetting_curve.go
package memory

import "math"

// ForgettingCurve 遗忘曲线计算
type ForgettingCurve struct{}

func (fc *ForgettingCurve) Retention(elapsedHours float64) float64 {
    // Ebbinghaus 遗忘曲线: R = e^(-t/S)
    // S = 保持强度 (通常 5-20)
    const S = 5.0
    return math.Exp(-elapsedHours / S)
}

// ShouldForget 判断是否应该遗忘
func (fc *ForgettingCurve) ShouldForget(memoryTime time.Time, threshold float64) bool {
    hours := time.Since(memoryTime).Hours()
    return fc.Retention(hours) < threshold
}

// 遗忘阈值配置:
// threshold=0.1: 10% 保留率时遗忘 (约 11.5 小时)
// threshold=0.01: 1% 保留率时遗忘 (约 23 小时)
// 实际建议: 24 小时阈值 0.05 (5%)
```

---

## 五、记忆混合检索 (RRF)

```go
// memory/hybrid_retrieval.go
package memory

import (
    "sort"
)

// RRFRetrieval RRF 混合检索
type RRFRetrieval struct{}

func (r *RRFRetrieval) Fuse(results [][]ScoredMemory, k int) []ScoredMemory {
    scores := make(map[uint64]float64)
    
    for _, res := range results {
        for rank, mem := range res {
            scores[mem.ID] += 1.0 / float64(rank+60) // k=60
        }
    }
    
    // 排序
    type scored struct {
        id    uint64
        score float64
    }
    var sorted []scored
    for id, score := range scores {
        sorted = append(sorted, scored{id, score})
    }
    sort.Slice(sorted, func(i, j int) bool {
        return sorted[i].score > sorted[j].score
    })
    
    // 返回 Top-K
    var final []ScoredMemory
    for _, s := range sorted {
        if len(final) >= k {
            break
        }
        // 根据 ID 查找原始记忆
        final = append(final, ScoredMemory{ID: s.id, Score: s.score})
    }
    return final
}
```

---

## 六、自测题

1. **三层记忆的区别是什么？**
   - Working (秒级/内存), Short-term (天级/向量), Long-term (永久/图)

2. **为什么用 RRF 融合检索？**
   - 解决不同检索系统结果排序不一致问题

3. **遗忘曲线的 S 值如何调整？**
   - S 越大遗忘越慢，重要记忆增大 S

