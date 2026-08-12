# GraphQL 性能优化深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、N+1 查询问题

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      N+1 查询问题示意                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  错误做法:                                                                  │
│  ─────────                                                                 │
│  Query: { campaigns { id name ads { title } } }                           │
│                                                                             │
│  执行流程:                                                                  │
│  1. SELECT * FROM campaigns           ← 1 次查询                         │
│  2. SELECT * FROM ads WHERE campaign_id=1 ← N 次查询 (每个 campaign)      │
│  3. SELECT * FROM ads WHERE campaign_id=2 ← N 次查询                      │
│  ...                                                                        │
│                                                                             │
│  总计: 1 + N 次查询                                                        │
│                                                                             │
│  正确做法: DataLoader (批量加载)                                           │
│  ─────────────────                                                          │
│  1. SELECT * FROM campaigns              ← 1 次查询                      │
│  2. SELECT * FROM ads WHERE campaign_id IN (1,2,3,...) ← 1 次查询         │
│                                                                             │
│  总计: 2 次查询                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、DataLoader 实现

```go
// 文件: graph/dataloader/campaign_loader.go
package dataloader

import (
	"context"
	"sync"
	"time"
)

// CampaignLoader 批量加载 campaign 数据
type CampaignLoader struct {
	fetch func(ids []int) (map[int]Campaign, error)
	cache map[int]CacheEntry
	mu    sync.RWMutex
}

type CacheEntry struct {
	data      Campaign
	expiresAt time.Time
}

func NewCampaignLoader(fetchFn func([]int) (map[int]Campaign, error)) *CampaignLoader {
	return &CampaignLoader{
		fetch: fetchFn,
		cache: make(map[int]CacheEntry),
	}
}

// Load 批量加载单个 campaign
func (l *CampaignLoader) Load(ctx context.Context, id int) (*Campaign, error) {
	// 检查缓存
	l.mu.RLock()
	entry, ok := l.cache[id]
	l.mu.RUnlock()
	
	if ok && time.Now().Before(entry.expiresAt) {
		return &entry.data, nil
	}
	
	// 批量获取
	batch := NewBatch[int, Campaign](ctx, l.fetch, 100*time.Millisecond)
	result, err := batch.Load(id)
	if err != nil {
		return nil, err
	}
	
	// 写入缓存
	l.mu.Lock()
	l.cache[id] = CacheEntry{
		data:      *result,
		expiresAt: time.Now().Add(5 * time.Minute),
	}
	l.mu.Unlock()
	
	return result, nil
}

// BatchLoader 处理批量请求
type BatchLoader struct {
	pending map[int]chan *BatchRequest
	timeout time.Duration
}

func (b *BatchLoader) Load(id int) (*BatchRequest, error) {
	// 收集请求直到批量处理
	// ...
}
```

---

## 三、查询复杂度分析

```go
// 文件: graph/schema/analysis.go
package schema

import (
	"github.com/vektah/gqlparser/v2/ast"
)

// MaxDepth 最大查询深度
const MaxDepth = 10

// MaxAliases 最大别名数
const MaxAliases = 30

// Complexity 查询复杂度分析
type Complexity struct {
	Depth      int
	Aliases    int
	FieldCount int
}

func AnalyzeQuery(query string) (*Complexity, error) {
	parsed, err := gqlparser.ParseQuery(&ast.Source{Name: "query", Input: query})
	if err != nil {
		return nil, err
	}
	
	return &Complexity{
		Depth:      calculateDepth(parsed),
		Aliases:    countAliases(parsed),
		FieldCount: countFields(parsed),
	}, nil
}

func calculateDepth(operation *ast.OperationDefinition) int {
	// 递归计算深度
	// ...
}
```

---

## 四、参考资料

```
核心概念:
├── DataLoader: Facebook 批量加载库
├── GraphQL Complexity: 查询复杂度分析
└── Query Depth Limit: 深度限制

工具:
├── graphql-go: Go 实现
├──Apollo Server: Node.js 实现
└── gqlgen: Go code-first
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
