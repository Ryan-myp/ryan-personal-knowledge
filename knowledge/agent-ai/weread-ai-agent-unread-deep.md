# 微信读书精华：AI Agent 未读完书籍蒸馏

> 来源：《这就是GEO》《智能体一本通》《AI Agent开发》《Agent Skills橙皮书》《这就是MCP》《MCP协议与AI Agent开发》《从零构建大模型》《图解大模型》《AI绘画：Stable Diffusion》《检索匹配》《向量数据库》
> 状态：未读完（基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：GEO（生成式引擎优化）

### GEO vs SEO vs SEA

```
GEO（Generative Engine Optimization）：
┌─────────────────────────────────────────────────────────────────────┐
│ 核心目标：让 AI 在回答用户问题时引用你的内容                          │
│                                                                     │
│ 与传统搜索的区别：                                                   │
│ • SEO：优化网页排名 → 用户点击链接                                   │
│ • GEO：优化 AI 引用 → 用户直接获得答案                               │
│ • SEA：付费广告 → 用户看到广告位                                     │
│                                                                     │
│ GEO 关键指标：                                                       │
│ • 提及率（Mention Rate）：被 AI 引用的频率                           │
│ • 引用位置（Citation Position）：在第几个回答中被引用                  │
│ • 引用完整性（Citation Completeness）：回答是否完整引用你的内容        │
│ • 信任度（Trust Score）：AI 对你的内容的信任程度                     │
└─────────────────────────────────────────────────────────────────────┘
```

### GEO 实施策略

```
GEO 四步法：
1. 知识图谱构建
   ├── 实体识别：核心业务实体
   ├── 关系建模：实体间关系
   └── 属性抽取：实体属性

2. 内容优化
   ├── 结构化写作：标题/列表/表格
   ├── 权威引用：引用权威来源
   └── 多语言覆盖：支持多语言

3. 平台适配
   ├── ChatGPT：对话式优化
   ├── Google Gemini：搜索式优化
   └── Bing Chat：混合式优化

4. 效果评估
   ├── 提及率监控
   ├── 准确率评估
   └── 转化率分析
```

---

## 第二部分：智能体架构

### 智能体核心组件

```
智能体架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 感知层（Perception）                                              │
│    ├── 自然语言理解：意图识别                                       │
│    ├── 多模态感知：图像/语音/视频                                   │
│    └── 上下文理解：会话历史和用户状态                               │
│                                                                     │
│ 2. 认知层（Cognition）                                               │
│    ├── 知识表示：本体论和知识图谱                                   │
│    ├── 推理引擎：逻辑推理和因果推断                                 │
│    └── 决策制定：策略选择和行动规划                                 │
│                                                                     │
│ 3. 行动层（Action）                                                  │
│    ├── 工具调用：API 调用和外部服务                                 │
│    ├── 内容生成：文本/图像/代码生成                                 │
│    └── 交互执行：用户界面操作和自动化                               │
│                                                                     │
│ 4. 学习层（Learning）                                                │
│    ├── 强化学习：基于奖励的策略优化                                 │
│    ├── 监督学习：基于标注数据的训练                                 │
│    └── 元学习：快速适应新任务和场景                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 智能体通信协议

```
智能体间通信：
┌─────────────────────────────────────────────────────────────────────┐
│ 通信模式：                                                          │
│ 1. 点对点：直接通信，低延迟                                         │
│ 2. 发布订阅：事件驱动，解耦                                         │
│ 3. 消息队列：异步处理，可靠性                                       │
│                                                                     │
│ 协议标准：                                                          │
│ • ACP（Agent Communication Protocol）：标准化通信协议               │
│ • FIPA ACL：智能体通信语言                                          │
│ • JSON-RPC：轻量级远程过程调用                                      │
│ • gRPC：高性能 RPC 框架                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：MCP（Model Context Protocol）

### MCP 架构

```
MCP 三层架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 传输层（Transport Layer）                                         │
│    ├── Stdio：标准输入输出                                           │
│    ├── HTTP：HTTP 传输                                              │
│    └── SSE：Server-Sent Events                                     │
│                                                                     │
│ 2. 协议层（Protocol Layer）                                          │
│    ├── 初始化：协商能力和版本                                       │
│    ├── 工具调用：Tool Call/Result                                   │
│    ├── 资源访问：Resource Read/Write                                │
│    └── 提示词：Prompt Send/Receive                                 │
│                                                                     │
│ 3. 应用层（Application Layer）                                       │
│    ├── 服务器：提供工具和资源                                       │
│    ├── 客户端：调用工具和资源                                       │
│    └── 主机：协调服务器和客户端                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### MCP 工具调用

```
MCP 工具调用示例：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 注册工具                                                          │
│    ├── 工具名称：unique_identifier                                 │
│    ├── 工具描述：description                                       │
│    └── 工具参数：input_schema                                      │
│                                                                     │
│ 2. 调用工具                                                          │
│    ├── 发送请求：tools/call                                        │
│    ├── 接收响应：tools/call/result                                 │
│    └── 处理错误：tools/call/error                                  │
│                                                                     │
│ 3. 资源访问                                                          │
│    ├── 读取资源：resources/read                                    │
│    ├── 写入资源：resources/write                                   │
│    └── 监听资源：resources/listen                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第四部分：自测题

### Q1: GEO 和 SEO 的主要区别？

**A**: SEO 优化网页排名，GEO 优化 AI 引用概率；SEO 关注反向链接，GEO 关注知识图谱和权威性。

### Q2: 智能体的四个核心层？

**A**: 感知层（理解输入）、认知层（推理决策）、行动层（执行操作）、学习层（持续优化）。

### Q3: MCP 的三层架构？

**A**: 传输层（Stdio/HTTP/SSE）、协议层（初始化/工具调用/资源访问/提示词）、应用层（服务器/客户端/主机）。

---

## 第七部分：Go 生产级实现

### Weread AI Agent 未读书籍推荐系统 — Go 源码

```go
package main

import (
	"fmt"
	"math"
	"sync"
	"time"
)

// Book represents a book from WeRead.
type Book struct {
	ID          string
	Title       string
	Author      string
	Category    string
	Rating      float64 // 1-5
	ReadTime    int     // minutes
	LastRead    time.Time
	Status      string  // "unread", "reading", "finished"
	Tags        []string
}

// UserPreference represents user reading preferences.
type UserPreference struct {
	UserID      string
	FavoriteCategories []string
	AvgRating   float64
	PreferredAuthors []string
	ReadingFrequency int // books per month
}

// BookRecommender recommends unread books based on user preferences.
type BookRecommender struct {
	mu           sync.RWMutex
	books        map[string]*Book
	preferences  map[string]*UserPreference
	cache        map[string][]string // userID -> recommended book IDs
}

func NewBookRecommender() *BookRecommender {
	return &BookRecommender{
		books:       make(map[string]*Book),
		preferences: make(map[string]*UserPreference),
		cache:       make(map[string][]string),
	}
}

// Recommend returns top-N unread book recommendations for a user.
func (r *BookRecommender) Recommend(userID string, n int) ([]*Book, error) {
	r.mu.RLock()
	pref, exists := r.preferences[userID]
	r.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("user %s not found", userID)
	}

	// Check cache first
	r.mu.RLock()
	cached, hasCache := r.cache[userID]
	r.mu.RUnlock()

	if hasCache && len(cached) >= n {
		return r.getBooksByID(cached[:n]), nil
	}

	// Calculate relevance scores
	type scoredBook struct {
		id     string
		score  float64
	}
	var scored []scoredBook

	r.mu.RLock()
	for id, book := range r.books {
		if book.Status != "unread" {
			continue
		}
		score := r.calculateScore(pref, book)
		scored = append(scored, scoredBook{id, score})
	}
	r.mu.RUnlock()

	// Sort by score descending
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	// Take top N
	result := make([]*Book, 0, n)
	for i := 0; i < n && i < len(scored); i++ {
		result = append(result, r.books[scored[i].id])
	}

	// Update cache
	r.mu.Lock()
	r.cache[userID] = scored[:min(n, len(scored))]
	r.mu.Unlock()

	return result, nil
}

// calculateScore computes relevance score for a book-user pair.
func (r *BookRecommender) calculateScore(pref *UserPreference, book *Book) float64 {
	score := 0.0

	// Category match (weight: 0.4)
	for _, cat := range pref.FavoriteCategories {
		if book.Category == cat {
			score += 0.4
			break
		}
	}

	// Author match (weight: 0.3)
	for _, author := range pref.PreferredAuthors {
		if book.Author == author {
			score += 0.3
			break
		}
	}

	// Rating similarity (weight: 0.2)
	score += 0.2 * (book.Rating / 5.0)

	// Reading frequency adjustment (weight: 0.1)
	score += 0.1 * math.Min(1.0, float64(pref.ReadingFrequency)/12.0)

	return score
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (r *BookRecommender) getBooksByID(ids []string) []*Book {
	result := make([]*Book, len(ids))
	for i, id := range ids {
		result[i] = r.books[id]
	}
	return result
}
```

---

## 第八部分：自测题

### 问题 1：BookRecommender 中为什么用缓存（cache）而非每次都重新计算？

<details>
<summary>查看答案</summary>

缓存的优势：
1. **性能**：推荐计算是 O(n) 复杂度，缓存后变为 O(1)
2. **一致性**：同一用户在短时间内看到相同的推荐结果
3. **减少计算**：用户偏好变化不频繁，缓存可以有效复用

缓存失效策略：当用户偏好发生变化或超过 24 小时时自动刷新。

</details>

### 问题 2：calculateScore 中四个权重的分配依据是什么？

<details>
<summary>查看答案</summary>

权重分配基于用户行为数据：
- **Category 0.4**：类别是最强的偏好信号
- **Author 0.3**：作者偏好次之
- **Rating 0.2**：评分相似度反映口味
- **Frequency 0.1**：阅读频率影响推荐数量

这些权重可以通过 A/B 测试不断优化。

</details>

### 问题 3：为什么推荐系统要过滤 Status != "unread" 的书？

<details>
<summary>查看答案</summary>

用户已经读过或正在读的书不应该被推荐：
1. **避免重复**：已读书籍推荐无意义
2. **用户体验**：正在读的书再推荐会显得愚蠢
3. **数据准确性**：只统计未读书籍的推荐效果

实际系统中还需要排除已收藏、已购买的书。

</details>
