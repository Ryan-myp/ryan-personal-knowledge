# 推荐系统深度：召回/排序/重排/多目标 源码级

> 从百万候选到 Top-10 展示，逐行解析推荐系统全链路

---

## 第一部分：推荐系统漏斗

```
推荐漏斗：
用户请求 → 召回层（1000万 → 1000）→ 粗排层（1000 → 200）→ 精排层（200 → 50）→ 重排层（50 → 10）→ 展示

延迟预算：
召回：50ms
粗排：20ms
精排：50ms
重排：10ms
总预算：130ms
```

---

## 第二部分：召回层源码

```go
package recall

import (
	"context"
	"sort"
)

// MultiPathRecall 多路召回
type MultiPathRecall struct {
	hotRecall      *HotRecall
	cfRecall       *CFRecall
	vectorRecall   *VectorRecall
	ruleRecall     *RuleRecall
	contentRecall  *ContentRecall
}

// RecallResult 召回结果
type RecallResult struct {
	Items    []Item
	Sources  []string // 每路来源
	Scores   []float64
}

type Item struct {
	ID       string
	Score    float64
	Category string
	Brand    string
}

// Recall 执行多路召回
func (r *MultiPathRecall) Recall(ctx context.Context, userID string, topK int) (*RecallResult, error) {
	var result RecallResult
	maxPerRoute := topK * 3 // 每路取 3x，后续去重合并
	
	// 1. 并行召回
	type routeResult struct {
		items   []Item
		source  string
	}
	
	ch := make(chan routeResult, 5)
	
	go func() {
		items, _ := r.hotRecall.Recall(ctx, userID, maxPerRoute)
		ch <- routeResult{items: items, source: "hot"}
	}()
	
	go func() {
		items, _ := r.cfRecall.Recall(ctx, userID, maxPerRoute)
		ch <- routeResult{items: items, source: "cf"}
	}()
	
	go func() {
		items, _ := r.vectorRecall.Recall(ctx, userID, maxPerRoute)
		ch <- routeResult{items: items, source: "vector"}
	}()
	
	go func() {
		items, _ := r.ruleRecall.Recall(ctx, userID, maxPerRoute)
		ch <- routeResult{items: items, source: "rule"}
	}()
	
	go func() {
		items, _ := r.contentRecall.Recall(ctx, userID, maxPerRoute)
		ch <- routeResult{items: items, source: "content"}
	}()
	
	// 2. 合并去重
	seen := make(map[string]bool)
	for i := 0; i < 5; i++ {
		select {
		case res := <-ch:
			for _, item := range res.items {
				if !seen[item.ID] {
					seen[item.ID] = true
					result.Items = append(result.Items, item)
					result.Sources = append(result.Sources, res.source)
					result.Scores = append(result.Scores, item.Score)
				}
			}
		case <-ctx.Done():
			break
		}
	}
	
	// 3. 排序取 Top-K
	sort.Slice(result.Items, func(i, j int) bool {
		return result.Scores[i] > result.Scores[j]
	})
	
	if len(result.Items) > topK {
		result.Items = result.Items[:topK]
		result.Scores = result.Scores[:topK]
		result.Sources = result.Sources[:topK]
	}
	
	return &result, nil
}
```

### 向量召回（FAISS）

```go
package recall

import "github.com/yanyiwu/gojieba"

// VectorRecall 向量召回
type VectorRecall struct {
	index      *faiss.IndexFlatIP // 内积索引
	dimension  int
	vocab      *gojieba.Jieba
}

// NewVectorRecall 创建向量召回
func NewVectorRecall(dim int, items []Item) *VectorRecall {
	idx := faiss.NewIndexFlatIP(dim)
	
	// 构建向量
	mat := make([]float32, len(items)*dim)
	for i, item := range items {
		vec := item.Embedding
		copy(mat[i*dim:(i+1)*dim], vec)
	}
	
	idx.Add(len(items), mat)
	
	return &VectorRecall{
		index:     idx,
		dimension: dim,
		vocab:     gojieba.NewJieba(),
	}
}

// Recall 向量召回
func (r *VectorRecall) Recall(ctx context.Context, userID string, topK int) ([]Item, error) {
	// 1. 获取用户兴趣向量
	userVec := r.getUserVector(userID)
	
	// 2. FAISS 搜索
	dists, ids := r.index.Search(userVec, topK)
	
	// 3. 构建结果
	var items []Item
	for i, id := range ids {
		item := r.getItemByID(id)
		item.Score = float64(dists[i])
		items = append(items, item)
	}
	
	return items, nil
}

func (r *VectorRecall) getUserVector(userID string) []float32 {
	// 从 Redis 获取用户 embedding
	// 简化实现
	return make([]float32, r.dimension)
}

func (r *VectorRecall) getItemByID(id int64) Item {
	// 从缓存获取 item
	return Item{ID: "item_" + strconv.FormatInt(id, 10)}
}
```

---

## 第三部分：粗排层

```go
package rank

// CoarseRanker 粗排器
type CoarseRanker struct {
	model *LRModel // 逻辑回归模型
}

// Rank 粗排
func (r *CoarseRanker) Rank(items []Item, topK int) []Item {
	for i := range items {
		items[i].Score = r.model.Predict(items[i].Features)
	}
	
	sort.Slice(items, func(i, j int) bool {
		return items[i].Score > items[j].Score
	})
	
	if len(items) > topK {
		return items[:topK]
	}
	return items
}
```

---

## 第四部分：精排层（DeepFM）

```go
package rank

// FineRanker 精排器
type FineRanker struct {
	model *DeepFMModel
}

// Rank 精排
func (r *FineRanker) Rank(items []Item, topK int) []Item {
	for i := range items {
		items[i].Score = r.model.Predict(items[i].Features)
	}
	
	sort.Slice(items, func(i, j int) bool {
		return items[i].Score > items[j].Score
	})
	
	if len(items) > topK {
		return items[:topK]
	}
	return items
}
```

---

## 第五部分：重排层（MMR）

```go
package rerank

import "math"

// MMR Reranker
type MMR struct {
	lambda float64 // 相关性权重
}

func NewMMR(lambda float64) *MMR {
	return &MMR{lambda: lambda}
}

// Rerank MMR 重排
func (r *MMR) Rerank(items []Item, topK int) []Item {
	if len(items) <= topK {
		return items
	}
	
	var selected []Item
	remaining := make([]Item, len(items))
	copy(remaining, items)
	
	// 1. 选择第一个（最高分）
	bestIdx := 0
	for i := 1; i < len(remaining); i++ {
		if remaining[i].Score > remaining[bestIdx].Score {
			bestIdx = i
		}
	}
	selected = append(selected, remaining[bestIdx])
	remaining = append(remaining[:bestIdx], remaining[bestIdx+1:]...)
	
	// 2. 迭代选择
	for len(selected) < topK && len(remaining) > 0 {
		var bestItem Item
		var bestScore float64 = -math.MaxFloat64
		
		for _, item := range remaining {
			relevance := item.Score
			
			// 多样性：与已选物品的最大相似度
			maxSim := 0.0
			for _, sel := range selected {
				sim := r.similarity(item, sel)
				if sim > maxSim {
					maxSim = sim
				}
			}
			
			// MMR 分数
			score := r.lambda*relevance - (1-r.lambda)*maxSim
			
			if score > bestScore {
				bestScore = score
				bestItem = item
			}
		}
		
		selected = append(selected, bestItem)
		
		// 从 remaining 移除
		for i, item := range remaining {
			if item.ID == bestItem.ID {
				remaining = append(remaining[:i], remaining[i+1:]...)
				break
			}
		}
	}
	
	return selected
}

func (r *MMR) similarity(a, b Item) float64 {
	if a.Category == b.Category {
		return 0.0
	}
	return 1.0
}
```

---

## 第六部分：自测题

### Q1: 为什么需要多路召回？

**A**: 单一路召回覆盖不全。热门召回抓流行，CF 抓相似用户，向量召回抓语义相似，规则召回抓业务逻辑。多路互补。

### Q2: MMR 的 λ 怎么选？

**A**: λ 接近 1 偏重相关性，接近 0 偏重多样性。通常 0.7-0.9。通过 A/B 测试选择最优值。

### Q3: 粗排和精排的区别？

**A**: 粗排用简单模型（LR/小树），快速过滤；精排用复杂模型（DeepFM/DIN），精准打分。

---

## 第七部分：生产实践

### 1. 延迟优化

```
延迟优化要点：
1. 并行召回：多路并行，取最快
2. 特征缓存：Redis 读取 < 1ms
3. 模型量化：TensorRT 加速 < 5ms
4. 本地缓存：sync.Map < 0.1ms
```

### 2. 缓存策略

```
缓存策略：
1. L1: 本地缓存（sync.Map，TTL 30s）
2. L2: Redis Cluster（TTL 5min）
3. L3: MySQL/TiKV（持久化）
```

### 3. A/B 测试

```
A/B 测试要点：
1. 用户分桶：随机均匀分配
2. 指标：CTR/CVR/GMV/NDCG
3. 显著性：p-value < 0.05
4. 时长：至少 1-2 个完整周期
```
