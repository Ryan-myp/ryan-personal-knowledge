# Agent记忆系统 - 资深专家深度实现

## 一、三层记忆架构

### 1.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent记忆架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    工作记忆 (Working Memory)             │   │
│  │  • 容量：~7个信息块（人类认知极限）                        │   │
│  │  • 保持：秒级                                           │   │
│  │  • 存储：内存中                                          │   │
│  │  • 作用：当前任务上下文                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓ 编码                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    短期记忆 (Short-term Memory)          │   │
│  │  • 容量：数百条消息                                      │   │
│  │  • 保持：分钟到小时                                       │   │
│  │  • 存储：向量数据库（最近N条）                             │   │
│  │  • 作用：近期对话历史                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓ 巩固                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    长期记忆 (Long-term Memory)           │   │
│  │  • 容量：百万级                                          │   │
│  │  • 保持：永久                                           │   │
│  │  • 存储：向量数据库 + 关系数据库                         │   │
│  │  • 作用：用户偏好、知识、经验                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 记忆流转

```go
package memory

import (
    "context"
    "time"
)

// MemoryFlow 记忆流转
type MemoryFlow struct {
    working   *WorkingMemory
    shortTerm *ShortTermMemory
    longTerm  *LongTermMemory
}

// Encode 编码：工作记忆 → 短期记忆
func (mf *MemoryFlow) Encode(ctx context.Context, item MemoryItem) error {
    // 1. 存入工作记忆
    mf.working.Push(item)
    
    // 2. 如果工作记忆满载，编码到短期记忆
    if mf.working.IsFull() {
        embedding := mf.embed(item.Content)
        mf.shortTerm.Store(ctx, embedding, item)
        mf.working.Clear()
    }
    
    return nil
}

// Consolidate 巩固：短期记忆 → 长期记忆
func (mf *MemoryFlow) Consolidate(ctx context.Context) error {
    // 1. 选出值得巩固的记忆（基于重要性评分）
    importantItems := mf.shortTerm.SelectImportant(ctx, threshold=0.8)
    
    // 2. 编码到长期记忆
    for _, item := range importantItems {
        embedding := mf.embed(item.Content)
        mf.longTerm.Store(ctx, embedding, item)
        
        // 3. 从短期记忆中移除（已巩固）
        mf.shortTerm.Remove(item.ID)
    }
    
    return nil
}

// Retrieve 检索
func (mf *MemoryFlow) Retrieve(ctx context.Context, query string, topK int) []MemoryItem {
    // 1. 查询短期记忆
    shortResults := mf.shortTerm.Search(ctx, query, topK)
    
    // 2. 查询长期记忆
    longResults := mf.longTerm.Search(ctx, query, topK)
    
    // 3. RRF融合
    return mf.rrfFuse(shortResults, longResults)
}
```

---

## 二、遗忘曲线

### 2.1 Ebbinghaus遗忘模型

```python
class EbbinghausForgettingCurve:
    """艾宾浩斯遗忘曲线"""
    
    def __init__(self):
        # 遗忘曲线参数（基于Ebbinghaus实验数据）
        self.params = {
            '1分钟': 0.58,   # 1分钟后剩余58%
            '20分钟': 0.44,  # 20分钟后剩余44%
            '1小时': 0.36,   # 1小时后剩余36%
            '1天': 0.33,     # 1天后剩余33%
            '2天': 0.28,     # 2天后剩余28%
            '6天': 0.25,     # 6天后剩余25%
            '31天': 0.21,    # 31天后剩余21%
        }
    
    def calculate_retention(self, hours_since_encoding: float) -> float:
        """
        计算保留率
        
        Args:
            hours_since_encoding: 编码后经过的小时数
        
        Returns:
            剩余保留率（0-1）
        """
        # 使用指数衰减模型
        # R = e^(-t/S) 其中S是记忆强度
        
        # 简化的幂律模型
        retention = 1 / (1 + 0.04 * hours_since_encoding ** 1.25)
        
        return max(0.1, min(1.0, retention))
    
    def should_forget(self, item: MemoryItem) -> bool:
        """
        判断是否需要遗忘
        
        Args:
            item: 记忆项
        
        Returns:
            True表示应遗忘
        """
        hours_since = (datetime.now() - item.created_at).total_seconds() / 3600
        retention = self.calculate_retention(hours_since)
        
        # 保留率低于阈值则遗忘
        return retention < 0.1
```

### 2.2 主动遗忘策略

```go
package memory

import (
    "context"
    "time"
)

// ForgettingStrategy 遗忘策略
type ForgettingStrategy interface {
    ShouldForget(ctx context.Context, item MemoryItem) bool
    GetPriority(item MemoryItem) float64
}

// EbbinghausForgetting 艾宾浩斯遗忘
type EbbinghausForgetting struct{}

func (f *EbbinghausForgetting) ShouldForget(ctx context.Context, item MemoryItem) bool {
    age := time.Since(item.CreatedAt)
    
    // 1天内不遗忘
    if age < 24*time.Hour {
        return false
    }
    
    // 根据记忆类型和年龄决定
    switch item.Type {
    case MemoryTypeImportant:
        return age > 30*24*time.Hour
    case MemoryTypeDaily:
        return age > 7*24*time.Hour
    case MemoryTypeTransient:
        return age > 24*time.Hour
    default:
        return age > 3*24*time.Hour
    }
}

func (f *EbbinghausForgetting) GetPriority(item MemoryItem) float64 {
    age := time.Since(item.CreatedAt).Hours()
    
    // 优先级 = 重要性 * 新鲜度
    importance := map[MemoryType]float64{
        MemoryTypeImportant: 1.0,
        MemoryTypeDaily:     0.7,
        MemoryTypeTransient: 0.3,
    }[item.Type]
    
    freshness := 1.0 / (1.0 + age/24.0) // 24小时减半
    
    return importance * freshness
}
```

---

## 三、RRF融合检索

### 3.1 RRF算法实现

```python
class RRFRetrieval:
    """Reciprocal Rank Fusion (RRF) 融合检索"""
    
    def __init__(self, k: float = 60.0):
        """
        Args:
            k: RRF常数，通常取60
        """
        self.k = k
    
    def fuse(self, results: list[list[dict]], scores: list[list[float]]) -> list[dict]:
        """
        融合多个检索结果
        
        Args:
            results: 多个检索结果列表，每个元素是文档列表
            scores: 每个结果的分数列表
        
        Returns:
            融合后的结果列表
        """
        rrf_scores = {}
        
        for doc_results, doc_scores in zip(results, scores):
            for rank, (doc_id, score) in enumerate(zip(doc_results, doc_scores), 1):
                rrf_score = 1.0 / (self.k + rank)
                
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {
                        'doc': doc_id,
                        'rrf_score': 0,
                        'max_score': 0,
                        'sources': []
                    }
                
                rrf_scores[doc_id]['rrf_score'] += rrf_score
                rrf_scores[doc_id]['max_score'] = max(
                    rrf_scores[doc_id]['max_score'], score
                )
                rrf_scores[doc_id]['sources'].append({
                    'score': score,
                    'rank': rank
                })
        
        # 按RRF分数排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1]['rrf_score'],
            reverse=True
        )
        
        return [doc[1] for doc in sorted_docs]
```

### 3.2 多路召回融合

```go
package retrieval

import (
    "context"
    "sort"
)

// MultiPathRetrieval 多路召回
type MultiPathRetrieval struct {
    vectorSearch  *VectorSearch
    keywordSearch *KeywordSearch
    graphSearch   *GraphSearch
}

// Search 多路召回搜索
func (m *MultiPathRetrieval) Search(ctx context.Context, query string, topK int) []MemoryItem {
    // 1. 各路径独立检索
    vectorResults := m.vectorSearch.Search(ctx, query, topK*2)
    keywordResults := m.keywordSearch.Search(ctx, query, topK*2)
    graphResults := m.graphSearch.Search(ctx, query, topK*2)
    
    // 2. RRF融合
    allResults := [][]MemoryItem{vectorResults, keywordResults, graphResults}
    fused := m.rrfFuse(allResults, topK)
    
    return fused
}

// rrfFuse RRF融合
func (m *MultiPathRetrieval) rrfFuse(results [][]MemoryItem, topK int) []MemoryItem {
    rrfScores := make(map[string]float64)
    
    for _, path := range results {
        for rank, item := range path {
            rrfScore := 1.0 / (60.0 + float64(rank+1))
            rrfScores[item.ID] += rrfScore
        }
    }
    
    // 排序
    type scoredItem struct {
        ID      string
        Score   float64
        Item    MemoryItem
    }
    
    scored := make([]scoredItem, 0, len(rrfScores))
    for id, score := range rrfScores {
        for _, path := range results {
            for _, item := range path {
                if item.ID == id {
                    scored = append(scored, scoredItem{id, score, item})
                    break
                }
            }
        }
    }
    
    sort.Slice(scored, func(i, j int) bool {
        return scored[i].Score > scored[j].Score
    })
    
    // 返回TopK
    if len(scored) > topK {
        scored = scored[:topK]
    }
    
    result := make([]MemoryItem, len(scored))
    for i, s := range scored {
        result[i] = s.Item
    }
    
    return result
}
```

---

## 四、Qdrant集成

### 4.1 集合设计

```go
package memory

import (
    "context"
    "github.com/qdrant/qdrant-client-go"
)

// QdrantMemoryStore Qdrant记忆存储
type QdrantMemoryStore struct {
    client *qdrant.Client
}

// 集合命名规范
const (
    CollectionWorking  = "working_memory"
    CollectionShortTerm = "short_term_memory"
    CollectionLongTerm  = "long_term_memory"
)

// 向量维度
const VectorDim = 1536  // text-embedding-3-small

// SetupCollections 创建集合
func (s *QdrantMemoryStore) SetupCollections(ctx context.Context) error {
    collections := []string{
        CollectionWorking,
        CollectionShortTerm,
        CollectionLongTerm,
    }
    
    for _, name := range collections {
        _, err := s.client.CreateCollection(ctx, &qdrant.CreateCollection{
            CollectionName: name,
            Vectors: &qdrant.VectorParams{
                Size:     VectorDim,
                Distance: qdrant.Distance_Cosine,
            },
        })
        if err != nil && !strings.Contains(err.Error(), "already exists") {
            return err
        }
    }
    
    return nil
}
```

### 4.2 点结构

```go
// MemoryPoint 记忆点
type MemoryPoint struct {
    ID        string         `json:"id"`
    Content   string         `json:"content"`
    Type      MemoryType     `json:"type"`
    Importance float64       `json:"importance"`
    CreatedAt time.Time      `json:"created_at"`
    UpdatedAt time.Time      `json:"updated_at"`
    Metadata  map[string]any `json:"metadata"`
}

// ToQdrantPoint 转换为Qdrant点
func (m *MemoryPoint) ToQdrantPoint(vector []float32) *qdrant.PointStruct {
    return qdrant.NewPointStruct(
        m.ID,
        vector,
        qdrant.NewPayload(
            "content", m.Content,
            "type", string(m.Type),
            "importance", m.Importance,
            "created_at", m.CreatedAt.Unix(),
            "updated_at", m.UpdatedAt.Unix(),
        ),
    )
}
```

---

## 五、性能优化

### 5.1 缓存策略

```go
package memory

import (
    "github.com/patrickmn/go-cache"
    "time"
)

// MemoryCache 记忆缓存
type MemoryCache struct {
    working  *cache.Cache  // 工作记忆缓存（短时）
    hotItems *cache.Cache  // 热项缓存（中时）
}

func NewMemoryCache() *MemoryCache {
    return &MemoryCache{
        working: cache.New(5*time.Minute, 10*time.Minute),
        hotItems: cache.New(1*time.Hour, 2*time.Hour),
    }
}

// Get 获取记忆
func (c *MemoryCache) Get(key string) (*MemoryItem, bool) {
    // 1. 先查工作记忆缓存
    if item, found := c.working.Get(key); found {
        return item.(*MemoryItem), true
    }
    
    // 2. 再查热项缓存
    if item, found := c.hotItems.Get(key); found {
        return item.(*MemoryItem), true
    }
    
    return nil, false
}

// Set 设置记忆
func (c *MemoryCache) Set(key string, item *MemoryItem, expiration time.Duration) {
    c.working.Set(key, item, expiration)
    
    // 如果是重要记忆，也存入热项缓存
    if item.Importance > 0.8 {
        c.hotItems.Set(key, item, 1*time.Hour)
    }
}
```

### 5.2 批量操作

```go
// BatchStore 批量存储
func (s *QdrantMemoryStore) BatchStore(ctx context.Context, items []MemoryItem) error {
    points := make([]*qdrant.PointStruct, len(items))
    
    for i, item := range items {
        vector := s.embed(item.Content)
        points[i] = item.ToQdrantPoint(vector)
    }
    
    _, err := s.client.Upsert(ctx, &qdrant.Upsert{
        CollectionName: CollectionShortTerm,
        Points: points,
    })
    
    return err
}
```

---

## 六、自测题

### 6.1 基础题

1. 解释三层记忆架构中每层的容量、保持时间和存储方式
2. Ebbinghaus遗忘曲线中，为什么24小时是遗忘的关键节点？
3. RRF融合相比简单加权平均有什么优势？

### 6.2 进阶题

1. 设计一个记忆重要性评分系统，考虑以下因素：
   - 用户显式标记的重要性
   - 记忆的访问频率
   - 记忆的时间衰减
   - 记忆与其他记忆的关联性

2. 如何实现记忆的"提取练习"效应？
   - 定期检索已存储的记忆
   - 提高记忆的保留率
   - 防止过度遗忘

3. 设计一个跨会话的记忆共享机制：
   - 多个Agent实例共享同一套记忆
   - 支持记忆的同步和冲突解决
   - 保证数据一致性

---

## 参考文档

- [Agent Memory System Deep Implementation](./agent-memory-system-deep.md)
- [RAG Advanced Optimization](./rag-advanced-optimization-deep.md)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
