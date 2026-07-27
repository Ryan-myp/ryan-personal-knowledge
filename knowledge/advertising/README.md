# 广告平台知识库

> Google / Meta / TikTok / Amazon — 从入门到源码级

## 文档索引

| 分类 | 文档 | 说明 |
|------|------|------|
| 基础知识 | [ad-system-architecture](../ad-ads/ad-system-architecture.md) | 广告系统架构概览 |
| 深度分析 | [ad-system-architecture-deep](../ad-ads/ad-system-architecture-deep.md) | 架构源码级深度 |
| 数据分析 | [ad-analytics](../ad-ads/ad-analytics.md) | 广告数据分析 |
| 深度分析 | [ad-analytics-deep](../ad-ads/ad-analytics-deep.md) | 数据分析深度 |

## 学习路线

```
广告系统基础 (CPC/CPM/OCPM 竞价机制)
    ↓
广告平台 API (Google/Meta/TikTok/Amazon)
    ↓
竞价优化 (RTA/RTB 实时竞价)
    ↓
创意生成 (DSP Creative Generation)
    ↓
数据分析 (归因模型/增量测量)
```

---

## 自测题

### 问题 1
广告竞价中 CPC、CPM、OCPM 各适用于什么场景？

<details>
<summary>查看答案</summary>

1. **CPC (按点击付费)**: 适合品牌曝光+流量获取，控制单次点击成本
2. **CPM (按展示付费)**: 适合品牌广告，按千次展示计费
3. **OCPM (优化千次展示)**: 平台根据转化概率自动出价，适合效果广告
4. **实际选择**: 初期用 CPC 收集数据，稳定后切换到 OCPM 优化 ROI

</details>

### 问题 2
为什么广告系统要用实时竞价（RTB）而不是固定价格？

<details>
<summary>查看答案</summary>

1. **效率**: 实时竞价让广告价值反映在价格上
2. **灵活性**: 不同用户、不同场景可以不同出价
3. **公平**: 价高者得，资源分配效率最高
4. **规模化**: RTB 平台可以处理百万级/秒的竞价请求
5. **Go 实现**: 用 goroutine 池处理高并发竞价请求

</details>

### 问题 3
生产环境中常见的竞价延迟问题有哪些？如何排查和优化？

<details>
<summary>点击查看答案</summary>

**常见延迟来源**：
1. 网络延迟：跨数据中心 RPC 调用，RTT 50-200ms
2. 模型推理：CTR/CVR 模型预测，5-50ms（取决于模型大小）
3. 特征检索：Redis 查询，0.1-1ms
4. 决策逻辑：多策略评分，1-5ms

**优化方案**：
1. **特征预加载**：提前将用户特征加载到本地内存，减少 Redis 查询
2. **模型量化**：使用 TensorRT/ONNX Runtime 将模型推理加速 3-5 倍
3. **并行推理**：多模型并行处理，使用 goroutine 池并发执行
4. **降级策略**：超时阈值内未完成时返回保守出价（如基准价）
5. **本地缓存**：对不常变化的特征使用 sync.Map 缓存，<0.1ms 访问

**典型排障流程**：
1. 查看 P99 延迟指标 > 50ms 触发告警
2. 通过链路追踪（Jaeger）定位慢节点
3. 检查模型推理时间是否异常增长
4. 查看 Redis 慢查询日志
5. 分析网络延迟是否来自外部依赖

</details>
---

## Go 代码实战：广告竞价引擎核心模块

### 实时竞价请求处理

```go
package bidding

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// BidRequest 来自 Ad Exchange 的竞价请求
type BidRequest struct {
	ID        string    `json:"id"`
	Timestamp time.Time `json:"timestamp"`
	Impressions []Impression `json:"imp"`
	User        *UserSignal   `json:"user"`
	Site        *SiteInfo     `json:"site"`
	App         *AppInfo      `json:"app"`
	Device      *DeviceInfo   `json:"device"`
}

// Impression 单次展示机会
type Impression struct {
	ID       string  `json:"id"`
	Banner   *Banner `json:"banner"`
	Video    *Video  `json:"video"`
	MinCPM   float64 `json:"bidfloor"`
}

// UserSignal 用户信号（画像 + 行为）
type UserSignal struct {
	ID      string   `json:"id"`
	Demographics Demographics `json:"demographics"`
	Interests []string `json:"interests"`
	Retargeting bool   `json:"retargeting"`
}

// Demographics 人口统计学特征
type Demographics struct {
	Age     int     `json:"age"`
	Gender  string  `json:"gender`
	Income  float64 `json:"income"`
	Location Location `json:"location"`
}

// BudgetTracker 预算追踪器（线程安全）
type BudgetTracker struct {
	mu          sync.Mutex
	dailyLimit  float64
	spentToday  float64
	totalLimit  float64
	spentTotal  float64
	lastReset   time.Time
}

func NewBudgetTracker(daily, total float64) *BudgetTracker {
	return &BudgetTracker{
		dailyLimit: daily,
		totalLimit: total,
		lastReset:  time.Now(),
	}
}

// CanSpend 检查是否可以花费
func (bt *BudgetTracker) CanSpend(amount float64) bool {
	bt.mu.Lock()
	defer bt.mu.Unlock()
	
	// 每日重置检查
	if time.Since(bt.lastReset) > 24*time.Hour {
		bt.spentToday = 0
		bt.lastReset = time.Now()
	}
	
	return bt.spentToday+amount <= bt.dailyLimit &&
		bt.spentTotal+amount <= bt.totalLimit
}

// RecordSpend 记录消费
func (bt *BudgetTracker) RecordSpend(amount float64) {
	bt.mu.Lock()
	defer bt.mu.Unlock()
	bt.spentToday += amount
	bt.spentTotal += amount
}

// FrequencyCapper 频次控制（滑动窗口）
type FrequencyCapper struct {
	windowSize time.Duration
	maxFreq    int
	store      sync.Map // key: user:campaign -> count
	expiry     time.Time
}

func NewFrequencyCapper(window time.Duration, max int) *FrequencyCapper {
	return &FrequencyCapper{
		windowSize: window,
		maxFreq:    max,
		expiry:     time.Now().Add(window),
	}
}

func (fc *FrequencyCapper) ShouldShow(userID, campaignID string) bool {
	key := userID + ":" + campaignID
	
	// 过期清理（惰性）
	fc.store.Range(func(k, v interface{}) bool {
		if count, ok := v.(*int32); ok && time.Since(fc.expiry) > fc.windowSize {
			fc.store.Delete(k)
		}
		return true
	})
	
	if countPtr, loaded := fc.store.Load(key); loaded {
		count := int32(1)
		if c, ok := countPtr.(*int32); ok {
			count = *c
		}
		if count >= int32(fc.maxFreq) {
			return false
		}
		fc.store.Store(key, &count)
		return true
	}
	
	c := int32(1)
	fc.store.Store(key, &c)
	return true
}

// BidEngine 竞价引擎核心
type BidEngine struct {
	tracker   *BudgetTracker
	capper    *FrequencyCapper
	strategies []BidStrategy
	model     PredictionModel
}

func (be *BidEngine) HandleRequest(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	// 1. 频次检查
	for _, imp := range req.Impressions {
		if !be.capper.ShouldShow(req.User.ID, req.AdCampaignID) {
			return nil, fmt.Errorf("frequency capped for user %s", req.User.ID)
		}
	}
	
	// 2. 预算检查
	if !be.tracker.CanSpend(req.MaxBid) {
		return nil, fmt.Errorf("budget exhausted")
	}
	
	// 3. CTR 预测
	ctx = context.WithValue(ctx, "request", req)
CTR:
	for _, strat := range be.strategies {
		pCTR := strat.PredictCTR(ctx, req)
		if pCTR < 0.001 {
			continue
		}
		
		// 4. 出价计算
		bid := strat.CalculateBid(pCTR, req.MinCPM)
		if bid < req.MinCPM {
			continue
		}
		
		// 5. 记录消费
		be.tracker.RecordSpend(bid)
		
		return &BidResponse{
			BidPrice: bid,
			Creative: strat.SelectCreative(req),
		}, nil
	}
	
	return nil, nil // No bid
}
```

### 自测题

<details>
<summary>Q1: BudgetTracker 的每日重置为什么用惰性检查而非定时任务？生产环境如何选择？</summary>

**答案**：

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 惰性检查（本实现） | 简单、无额外线程、天然分布式友好 | 每次请求都检查时间差 | QPS < 10万 |
| 定时任务 | 精确到秒级重置 | 需要分布式锁、多实例同步 | 高并发场景 |
| Redis 原子操作 | 精确、可实时监控 | 增加 Redis 依赖 | 金融级精度 |

**关键决策**：广告预算允许 ±1分钟误差（用户不会追究），惰性检查是最优选择。但要注意 `sync.Mutex` 在高并发下可能成为瓶颈——生产环境用 `atomic.Value` 替代。

</details>

<details>
<summary>Q2: FrequencyCapper 的惰性清理在极端情况下会怎样？如何改进？</summary>

**答案**：

**问题**：如果某个 key 从未被访问，它的过期判断永远不会触发（因为惰性清理只在 Range 遍历时检查）。在高基数场景（千万级用户 × 万级广告），store 可能堆积大量过期 key。

**改进方案**：
```go
// 方案1: 采样清理（推荐）
func (fc *FrequencyCapper) maybeCleanup() {
	if rand.Intn(100) != 0 { return } // 1% 概率触发
	fc.store.Range(...) // 随机触发清理
}

// 方案2: TTL map（Redis/ZSet）
// 方案3: 分片 + 每片独立过期
}
```

</details>

<details>
<summary>Q3: BidEngine.HandleRequest 中的 CTR 预测循环有什么性能问题？如何优化到 <1ms？</summary>

**答案**：

**问题**：
1. 串行遍历策略列表——O(n) 线性扫描
2. 每个策略都要做完整预测（模型推理）
3. ctx.Value 传递请求对象有反射开销

**优化方案**：
```go
// 并行预测 + 短路
var wg sync.WaitGroup
ch := make(chan *StrategyResult, len(be.strategies))

for _, s := range be.strategies {
	wg.Add(1)
	go func(strat BidStrategy) {
		defer wg.Done()
		result := strat.PredictCTR(ctx, req)
		ch <- &StrategyResult{Strategy: strat, CTR: result}
	}(s)
}

go func() { wg.Wait(); close(ch) }()

for r := range ch {
	if r.CTR >= threshold {
		return r.Strategy.Bid(req)
	}
}
```

实际生产中用 goroutine pool（如 `workerpool` 库）限制并发数，避免惊群效应。

</details>
