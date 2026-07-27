# Knowledge Query Pitfalls

## 已知坑

1. **scenario_card min_confidence_score=999** 不走 knowledge_card 快捷路径
   - 诊断：检查 source_mode 是否为 `sqlite_candidate_subgraph`
2. **render_answer_context 的 api_docs 优先级问题**
   - 误匹配会覆盖正确 code 结果
   - 临时绕过：使用 `--scope code`
3. **extract_intent 对短中文置信度低**
   - 保留自定义 `get_scope_weights()` 作为补充
4. **目录名必须用下划线**（knowledge_search/ wiki_engine/）

## 调试方法

```bash
# 1. 检查 query 是否正确路由到 knowledge_card
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Redis cluster 怎么搭建", "scope": "code"}'

# 2. 检查 scenario_card 是否命中
# 查看 response 中的 source_mode 字段

# 3. 检查 API 文档匹配
# 查看 render_answer_context 中的 api_docs 字段
```

## Go 实现：高效 Knowledge Card 缓存

```go
package knowledge

import (
	"container/list"
	"context"
	"sync"
	"time"
)

// KnowledgeCard 知识卡片结构
type KnowledgeCard struct {
	Query     string    `json:"query"`
	Scope     string    `json:"scope"`     // "code", "api_doc", "general"
	Answer    string    `json:"answer"`
	Source    string    `json:"source"`    // source_mode
	Confidence float64  `json:"confidence"`
	CreatedAt time.Time `json:"created_at"`
	TTL       time.Duration `json:"ttl"` // 过期时间
}

// LRUCache 线程安全的 LRU + TTL 缓存
type LRUCache struct {
	mu      sync.RWMutex
	items   map[string]*list.Element // key -> list element
	queue   *list.List               // 双端链表，最近使用放 front
	capacity int                     // 最大容量
	ttl     time.Duration            // 默认 TTL
}

type cacheEntry struct {
	card     KnowledgeCard
	expires  time.Time
}

func NewLRUCache(capacity int, ttl time.Duration) *LRUCache {
	return &LRUCache{
		items:    make(map[string]*list.Element, capacity),
		queue:    list.New(),
		capacity: capacity,
		ttl:      ttl,
	}
}

// Get 获取缓存，O(1) - 未命中或过期返回 false
func (c *LRUCache) Get(ctx context.Context, key string) (KnowledgeCard, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	elem, ok := c.items[key]
	if !ok {
		return KnowledgeCard{}, false
	}

	entry := elem.Value.(*cacheEntry)
	if time.Now().After(entry.expires) {
		// 已过期，删除
		c.removeElement(elem)
		return KnowledgeCard{}, false
	}

	// 移动到 front（最近使用）
	c.queue.MoveToFront(elem)
	return entry.card, true
}

// Set 设置缓存，O(1)
func (c *LRUCache) Set(key string, card KnowledgeCard) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// 如果 key 已存在，更新
	if elem, ok := c.items[key]; ok {
		c.queue.MoveToFront(elem)
		elem.Value.(*cacheEntry).card = card
		elem.Value.(*cacheEntry).expires = time.Now().Add(card.TTL)
		return
	}

	// 容量满了，驱逐 LRU
	if c.queue.Len() >= c.capacity {
		oldest := c.queue.Back()
		c.removeElement(oldest)
	}

	// 添加新条目到 front
	entry := &cacheEntry{
		card:    card,
		expires: time.Now().Add(card.TTL),
	}
	elem := c.queue.PushFront(entry)
	c.items[key] = elem
}

func (c *LRUCache) removeElement(elem *list.Element) {
	c.queue.Remove(elem)
	entry := elem.Value.(*cacheEntry)
	delete(c.items, entry.card.Query)
}

// KnowledgeQueryRouter 查询路由 - 解决 min_confidence_score 坑
type KnowledgeQueryRouter struct {
	cache      *LRUCache
	scorer     *ConfidenceScorer
	subgraphs  map[string]*SubGraph // sqlite_candidate_subgraph
}

// RouteQuery 根据置信度智能路由
func (r *KnowledgeQueryRouter) RouteQuery(query string) (KnowledgeCard, string, error) {
	// 先查缓存
	card, cached := r.cache.Get(context.Background(), query)
	if cached {
		return card, "cache_hit", nil
	}

	// 计算置信度
	score := r.scorer.Score(query)

	var sourceMode string
	var result KnowledgeCard

	// 高置信度 → knowledge_card 快捷路径
	if score >= 0.95 {
		sourceMode = "knowledge_card"
		result = r.fetchFromKnowledgeCard(query)
	} else if score >= 0.7 {
		// 中等置信度 → sqlite_candidate_subgraph
		sourceMode = "sqlite_candidate_subgraph"
		result = r.fetchFromSubgraph(query)
	} else {
		// 低置信度 → 通用知识卡片（降级）
		sourceMode = "generic_fallback"
		result = r.fetchGeneric(query)
	}

	// 写入缓存
	if sourceMode != "generic_fallback" {
		result.Confidence = score
		result.Source = sourceMode
		result.TTL = 30 * time.Minute
		r.cache.Set(query, result)
	}

	return result, sourceMode, nil
}
```

## 相关资源

- ad-ai-coding 仓库: git.garena.com/marketing/ad_ai_coding
- query_knowledge.py 路径: ~/ad_ai_coding/tools/knowledge_query/

---

## 自测题

### 问题 1
为什么 `min_confidence_score=999` 会绕过 knowledge_card 快捷路径？

<details>
<summary>查看答案</summary>

1. **高阈值**: 999 的置信度阈值几乎不可能命中
2. **降级机制**: 命中失败时走通用知识卡片逻辑
3. **source_mode**: 此时 source_mode 会是 `sqlite_candidate_subgraph` 而非 `knowledge_card`
4. **实际影响**: 通用卡片逻辑不处理广告平台 API 查询，导致返回通用结果

</details>

### 问题 2
Go 中如何实现一个高效的 knowledge card 缓存？

<details>
<summary>查看答案</summary>

1. **LRU 缓存**: 用 map + doubly linked list 实现 O(1) 增删查
2. **TTL**: 过期知识自动清理，避免返回过时信息
3. **并发安全**: sync.RWMutex 允许多读单写
4. **预加载**: 启动时预加载高频知识卡，减少查询延迟
5. **内存限制**: 设置最大条目数，超出时驱逐最久未用的

</details>
### 问题 3
知识查询中的缓存击穿如何预防？

<details>
<summary>查看答案</summary>

1. **互斥锁**：对热点 key 使用 singleflight 或 redis lock，只允许一个线程去加载数据
2. **永不过期**：关键知识卡设置 TTL=never，逻辑过期时在后台异步刷新
3. **布隆过滤器**：用 Bloom Filter 预先拦截不存在的 key，减少缓存穿透
4. **降级保护**：当缓存层压力过高时直接返回默认值或异步写入策略
5. **预热机制**：启动时将高频知识预加载到内存，避免首次请求雪崩

</details>
