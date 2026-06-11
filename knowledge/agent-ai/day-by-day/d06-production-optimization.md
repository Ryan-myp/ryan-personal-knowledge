---
*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*

---

### Agent 生产优化的 Go 实现

```go
package agentprod

import (
	"fmt"
	"sync"
	"time"
)

type TokenCounter struct {
	promptTokens     int
	completionTokens int
	totalTokens      int
	mu               sync.Mutex
}

func (tc *TokenCounter) RecordPrompt(n int) {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	tc.promptTokens += n
	tc.totalTokens += n
}

func (tc *TokenCounter) RecordCompletion(n int) {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	tc.completionTokens += n
	tc.totalTokens += n
}

func (tc *TokenCounter) Stats() (int, int, int) {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	return tc.promptTokens, tc.completionTokens, tc.totalTokens
}

type Cache struct {
	items map[string]cacheEntry
	mu    sync.RWMutex
}

type cacheEntry struct {
	key     string
	value   string
	created time.Time
	ttl     time.Duration
}

func NewCache() *Cache { return &Cache{items: make(map[string]cacheEntry)} }

func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	entry, ok := c.items[key]
	if !ok || time.Now().After(entry.created.Add(entry.ttl)) {
		delete(c.items, key)
		return "", false
	}
	return entry.value, true
}

func (c *Cache) Set(key, value string, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[key] = cacheEntry{key: key, value: value, created: time.Now(), ttl: ttl}
}

func main() {
	tc := &TokenCounter{}
	tc.RecordPrompt(100)
	tc.RecordCompletion(50)
	p, c, t := tc.Stats()
	fmt.Printf("Tokens: prompt=%d, completion=%d, total=%d\n", p, c, t)

	cache := NewCache()
	cache.Set("query_1", "RAG answer", 5*time.Minute)
	if v, ok := cache.Get("query_1"); ok { fmt.Printf("Cache hit: %s\n", v) }
}
```

---

## 自测题

### 问题 1
生产环境中 Token 计数为什么要在 Agent 层而不是 LLM API 层？

<details>
<summary>查看答案</summary>

1. API 层返回的 token 统计是单次调用的，不跨轮次
2. Agent 层可以累计整个对话的历史 token
3. 便于做预算控制和成本分析
4. 可以精确到每个 tool call 的 token 消耗

</details>

### 问题 2
Go 的 Cache 结构中 TTL 过期策略为什么不用定期清理？

<details>
<summary>查看答案</summary>

1. 定期清理需要后台 goroutine 持续运行
2. 惰性删除（Lazy Eviction）在 Get 时检查 TTL，零额外开销
3. 对于高并发场景，惰性删除减少锁竞争
4. 缺点是内存中可能有短暂过期的数据，但通常可接受

</details>