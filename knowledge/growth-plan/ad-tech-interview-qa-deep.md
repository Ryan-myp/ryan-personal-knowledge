# 广告技术面试题库深度：Go/MySQL/Redis/广告系统

> 从基础到源码级，覆盖广告技术面试高频问题

---

## 第一部分：Go 语言面试题

### GMP 调度

```
Q: Go 的 GMP 调度器工作原理？
A: 
G (Goroutine): 协程，包含栈、状态、调度信息
M (Machine): 操作系统线程，执行 G
P (Processor): 处理器，管理本地 runq

调度流程：
1. 新建 G → 放入 P 的本地 runq
2. P 从 runq 取出 G 执行
3. G 阻塞时，P 创建新 M
4. P 本地队列满（256）时，一半放入全局队列
5. P 本地队列为空时，从全局队列或其他 P 偷取（work stealing）

关键优化：
• 本地队列减少锁竞争
• Work stealing 负载均衡
• Sysmon 监控长时间运行的 G
```

### 内存管理

```
Q: Go 的内存分配策略？
A:
小对象 (< 32KB):
  MCache → MSpan → MHeap → OS
  每个 P 有独立 MCache，避免锁竞争

大对象 (>= 32KB):
  MHeap → OS mmap
  直接映射到虚拟内存

零值对象:
  直接指向 zerobase

关键数据结构：
• mcache: 每 P 的本地缓存
• mspan: 连续内存块
• mheap: 全局内存堆
```

### Channel 底层

```
Q: Channel 的实现原理？
A:
结构体：
  type hchan struct {
      qcount   uint           // 队列元素个数
      dataqsiz uint           // 环形队列大小
      buf      unsafe.Pointer // 环形队列缓冲区
      elemsize uint16         // 元素大小
      closed   uint32         // 是否关闭
      elemtype *_type         // 元素类型
      sendx    uint           // 发送索引
      recvx    uint           // 接收索引
      recvq    waitq          // 等待接收的 G 队列
      sendq    waitq          // 等待发送的 G 队列
      lock     mutex          // 互斥锁
  }

操作流程：
1. 发送：锁 → 检查缓冲区 → 有空间则拷贝 → 解锁
2. 接收：锁 → 检查缓冲区 → 有数据则拷贝 → 解锁
3. 缓冲区满/空：G 进入等待队列，调度器切换
```

---

## 第二部分：MySQL 面试题

### 索引原理

```
Q: MySQL 索引为什么用 B+ 树？
A:
B+ 树优势：
1. 多叉树，高度低（3 层可存千万级数据）
2. 叶子节点链表，范围查询高效
3. 非叶子节点只存索引，内存可存更多
4. 顺序访问，磁盘 IO 友好

对比：
• B 树：非叶子节点也存数据，高度略高
• Hash：只支持等值查询
• 跳表：内存数据结构，不适合磁盘
```

### 事务隔离

```
Q: MySQL 的 MVCC 如何实现？
A:
实现机制：
1. 隐藏列：DB_TRX_ID（事务 ID）、DB_ROLL_PTR（回滚指针）
2. Undo Log：保存历史版本
3. Read View：事务快照

RR 隔离级别下的 Read View：
• 第一次 SELECT 时创建
• 可见性规则：
  - trx_id < min_trx_id → 可见
  - trx_id >= max_trx_id → 可见
  - trx_id 在活跃列表中 → 不可见
  - 否则 → 可见

RC 隔离级别：
• 每次 SELECT 都创建新的 Read View
• 所以能看到其他事务已提交的修改
```

### 锁机制

```
Q: MySQL 的锁类型？
A:
1. 全局锁：FLUSH TABLES WITH READ LOCK
2. 表级锁：LOCK TABLES
3. 行级锁：
   - 记录锁（Record Lock）：锁定索引记录
   - 间隙锁（Gap Lock）：锁定索引间隙
   - 临键锁（Next-Key Lock）：记录锁 + 间隙锁

死锁处理：
• InnoDB 自动检测死锁
• 选择回滚代价小的事务
```

---

## 第三部分：Redis 面试题

### 持久化

```
Q: RDB 和 AOF 的区别？
A:
RDB:
• 快照形式，周期性保存
• 恢复快，体积小
• 可能丢失最后一次快照后的数据

AOF:
• 命令日志，每次写都记录
• 数据更安全
• 文件大，恢复慢

生产推荐：
• 同时开启 RDB + AOF
• AOF 优先恢复
• appendfsync everysec
```

### 内存淘汰

```
Q: Redis 内存淘汰策略？
A:
1. noeviction: 不淘汰，返回错误（默认）
2. allkeys-lru: 所有 key 中淘汰 LRU
3. allkeys-lfu: 所有 key 中淘汰 LFU
4. volatile-lru: 有过期时间的 key 中淘汰 LRU
5. volatile-lfu: 有过期时间的 key 中淘汰 LFU
6. volatile-ttl: 有过期时间的 key 中淘汰 TTL 最短的

广告场景推荐：
• allkeys-lru: 缓存场景
• volatile-ttl: 精确控制
```

---

## 第四部分：广告系统面试题

### 竞价系统

```
Q: RTB 竞价流程？
A:
1. 用户访问页面
2. SSP 发起竞价请求（BidRequest）
3. DSP 获取请求，构建特征
4. 预测 CTR/CVR
5. 计算出价 = CTR × CVR × target_CPA
6. 发送竞价响应（BidResponse）
7. 竞价 winner 返回广告创意
8. 展示广告，记录曝光/点击

优化要点：
• 延迟 < 100ms
• 特征缓存（Redis）
• 模型量化（TensorRT）
• 本地缓存（sync.Map）
```

### 排序模型

```
Q: DeepFM 和 DIN 的区别？
A:
DeepFM:
• 低阶 + 高阶特征自动交互
• 静态特征，不考虑用户兴趣变化
• 适合特征工程复杂的场景

DIN:
• 注意力机制捕捉用户兴趣
• 动态特征，考虑用户历史行为
• 适合有用户行为序列的场景

广告场景：
• DeepFM: 特征少、实时性要求高
• DIN: 有用户行为序列、需要个性化
```

### 实验平台

```
Q: A/B 测试怎么设计？
A:
1. 确定目标指标（CTR/CVR/GMV）
2. 计算样本量（power analysis）
3. 随机分桶（保证均匀）
4. 运行实验（至少 1-2 周）
5. 统计分析（p-value < 0.05）
6. 决策（推广/回滚/继续）

注意事项：
• 辛普森悖论
• 新奇效应（Novelty Effect）
• 季节效应
• 网络效应（社交类产品）
```

---

## 第五部分：系统设计题

```
Q: 设计一个广告竞价系统？
A:
架构设计：
┌──────────────────────────────────────────────────────┐
│ API Gateway                                          │
│ ├── 请求路由                                           │
│ ├── 限流                                              │
│ └── 认证                                              │
│                                                      │
│ Bid Engine (竞价引擎)                                  │
│ ├── 特征获取 (Redis)                                   │
│ ├── CTR/CVR 预测 (TensorRT)                           │
│ ├── 出价策略 (RL/规则)                                 │
│ └── 预算控制                                           │
│                                                      │
│ Data Pipeline                                        │
│ ├── 实时事件 (Kafka)                                  │
│ ├── 特征计算 (Flink)                                  │
│ └── 模型训练 (Spark)                                  │
│                                                      │
│ Monitoring                                           │
│ ├── Prometheus + Grafana                              │
│ └── ELK 日志                                         │
│                                                      │
│ 关键指标：                                              │
│ • P99 延迟 < 100ms                                    │
│ • 可用性 > 99.99%                                     │
│ • 竞价成功率 > 99%                                    │
└──────────────────────────────────────────────────────┘
```

---

## 第六部分：自测题

### Q1: Go 的 GC 为什么这么快？

**A**: 三色标记 + 写屏障，并发标记清扫，STW 时间极短。

### Q2: Redis 为什么单线程还这么快？

**A**: 内存操作，epoll 事件驱动，避免锁竞争和上下文切换。

### Q3: 广告竞价延迟怎么优化？

**A**: 特征缓存 + 模型量化 + 并行推理 + 本地缓存。

---

## 第七部分：生产排障题

```
Q: 线上发现 CTR 突然下降，怎么排查？
A:
1. 确认影响范围：所有广告还是部分？
2. 检查数据管道：特征是否正常更新？
3. 检查模型：是否更新了模型？
4. 检查竞价策略：出价是否变化？
5. 检查外部环境：节假日/竞品活动？
6. 检查 A/B 实验：是否有实验干扰？
7. 回滚最近的变更
8. 逐步恢复并监控
```

---

## 第八部分：成长建议

```
面试准备建议：
1. 基础扎实：Go/MySQL/Redis 源码级理解
2. 广告知识：竞价/排序/召回/实验
3. 系统设计：能画架构图，能说清权衡
4. 实战经验：有生产排障案例
5. 表达能力：逻辑清晰，有条理
```

## 九、Go 源码级实现：广告技术核心算法

### 9.1 竞价引擎核心实现

```go
package interview

import (
	"context"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"
)

// BidRequest 竞价请求
type BidRequest struct {
	RequestID string    `json:"request_id"`
	Timestamp time.Time `json:"timestamp"`
	User      UserSignal `json:"user"`
	Context   Context   `json:"context"`
	AdSlot    AdSlot    `json:"ad_slot"`
}

// UserSignal 用户信号
type UserSignal struct {
	UserID    string   `json:"user_id"`
	Demographics map[string]string `json:"demographics"`
	Interests []string `json:"interests"`
	Browser   string   `json:"browser"`
	Device    string   `json:"device"`
}

// Context 上下文
type Context struct {
	URL       string   `json:"url"`
	PageTitle string   `json:"page_title"`
	Keywords  []string `json:"keywords"`
	Referrer  string   `json:"referrer"`
}

// AdSlot 广告位
type AdSlot struct {
	SlotID   string `json:"slot_id"`
	Width    int    `json:"width"`
	Height   int    `json:"height"`
	Position string `json:"position"` // top, mid, bottom
	Format   string `json:"format"`   // banner, native, video
}

// BidResponse 竞价响应
type BidResponse struct {
	ResponseID  string        `json:"response_id"`
	WinningBid  *WinningBid   `json:"winning_bid,omitempty"`
	SeatBid     []SeatBid     `json:"seatbid"`
	PriceType   string        `json:"price_type"` // cpc, cpm, cpv
	LatencyMs   float64       `json:"latency_ms"`
}

// WinningBid 中标出价
type WinningBid struct {
	AdID    string  `json:"ad_id"`
	BidPrice float64 `json:"bid_price"`
	eCPM    float64 `json:"ecpm"`
	Creative  Creative `json:"creative"`
}

// SeatBid 座位出价
type SeatBid struct {
	Bid  Bid  `json:"bid"`
	Seat string `json:"seat"`
}

// Bid 出价
type Bid struct {
	ID      string  `json:"id"`
	AdID    string  `json:"ad_id"`
	Price   float64 `json:"price"`
	Creative Creative `json:"creative"`
}

// Creative 创意
type Creative struct {
	ID          string `json:"id"`
	Type        string `json:"type"`
	Width       int    `json:"width"`
	Height      int    `json:"height"`
	HTML        string `json:"html,omitempty"`
	ClickURL    string `json:"click_url"`
	TrackURLs   []string `json:"track_urls,omitempty"`
}

// BidEngine 竞价引擎
type BidEngine struct {
	mu         sync.RWMutex
	auctioneer Auctioneer
	filter     FilterChain
	ranker     Ranker
	logger     Logger
}

// NewBidEngine 创建竞价引擎
func NewBidEngine(a Auctioneer, f FilterChain, r Ranker, l Logger) *BidEngine {
	return &BidEngine{
		auctioneer: a,
		filter:     f,
		ranker:     r,
		logger:     l,
	}
}

// Process 处理竞价请求（核心流程）
func (be *BidEngine) Process(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	start := time.Now()
	
	// Step 1: 过滤（预筛选）
	candidates, err := be.filter.Apply(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("filter: %w", err)
	}
	
	if len(candidates) == 0 {
		return &BidResponse{
			ResponseID: req.RequestID,
			PriceType:  "cpm",
		}, nil
	}
	
	// Step 2: 排序（计算 eCPM）
	scored := be.ranker.ScoreCandidates(req, candidates)
	
	// Step 3: 拍卖（取最高 eCPM）
	winner, secondBest, err := be.auctioneer.ConductAuction(scored)
	if err != nil {
		return nil, fmt.Errorf("auction: %w", err)
	}
	
	latency := time.Since(start).Seconds() * 1000
	
	resp := &BidResponse{
		ResponseID: req.RequestID,
		SeatBid: []SeatBid{
			{
				Bid:  winner.Bid,
				Seat: winner.Seat,
			},
		},
		PriceType: "cpm",
		LatencyMs: latency,
	}
	
	if winner != nil {
		resp.WinningBid = &WinningBid{
			AdID:     winner.Bid.AdID,
			BidPrice: winner.Price,
			eCPM:     winner.eCPM,
			Creative: winner.Bid.Creative,
		}
	}
	
	be.logger.Infof("Bid processed: id=%s eCPM=%.4f latency=%.2fms candidates=%d",
		req.RequestID, resp.WinningBid.eCPM, latency, len(candidates))
	
	return resp, nil
}

// FilterChain 过滤器链（责任链模式）
type FilterChain struct {
	filters []BidFilter
}

// BidFilter 竞价过滤器接口
type BidFilter interface {
	Name() string
	Apply(ctx context.Context, req *BidRequest, candidates []*Candidate) ([]*Candidate, error)
}

// Apply 执行过滤器链
func (fc *FilterChain) Apply(ctx context.Context, req *BidRequest) ([]*Candidate, error) {
	candidates := GetAllCandidates(req)
	
	for _, filter := range fc.filters {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
			var err error
			candidates, err = filter.Apply(ctx, req, candidates)
			if err != nil {
				return nil, err
			}
			if len(candidates) == 0 {
				return candidates, nil
			}
		}
	}
	
	return candidates, nil
}

// Candidate 候选广告
type Candidate struct {
	AdID       string
	CampaignID string
	BidAmount  float64
	eCPM       float64
	Seat       string
	Bid        Bid
}

// Ranker 排序器
type Ranker interface {
	ScoreCandidates(req *BidRequest, candidates []*Candidate) []*ScoredCandidate
}

// ScoredCandidate 评分后的候选
type ScoredCandidate struct {
	Candidate *Candidate
	Score     float64
	Rank      int
}

// Auctioneer 拍卖器
type Auctioneer interface {
	ConductAuction(scored []*ScoredCandidate) (*ScoredCandidate, *ScoredCandidate, error)
}

// SecondPriceAuction 第二价格拍卖实现
type SecondPriceAuction struct{}

func (spa *SecondPriceAuction) ConductAuction(scored []*ScoredCandidate) (*ScoredCandidate, *ScoredCandidate, error) {
	// 按 eCPM 降序排序
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].Score > scored[j].Score
	})
	
	if len(scored) == 0 {
		return nil, nil, fmt.Errorf("no candidates")
	}
	
	winner := scored[0]
	
	// 第二价格：获胜者支付略高于第二名的价格
	var secondPrice float64
	if len(scored) > 1 {
		secondPrice = scored[1].Score
	} else {
		secondPrice = winner.Candidate.BidAmount * 0.5 // 底价
	}
	
	// 调整出价（第二价格）
	winner.Candidate.Bid.Price = secondPrice + 0.01
	winner.Candidate.eCPM = secondPrice + 0.01
	
	return winner, scored[min(1, len(scored)-1)], nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// Logger 日志接口
type Logger interface {
	Infof(fmt string, args ...interface{})
	Errorf(fmt string, args ...interface{})
}

// GetAllCandidates 获取所有候选广告（简化版）
func GetAllCandidates(req *BidRequest) []*Candidate {
	// 生产环境从缓存/数据库获取
	return []*Candidate{
		{AdID: "ad_1", CampaignID: "camp_1", BidAmount: 2.5, Seat: "dsp_1"},
		{AdID: "ad_2", CampaignID: "camp_2", BidAmount: 1.8, Seat: "dsp_2"},
		{AdID: "ad_3", CampaignID: "camp_3", BidAmount: 3.0, Seat: "dsp_1"},
	}
}
```

### 9.2 排序模型实现

```go
package interview

import "math"

// RankModel 排序模型接口
type RankModel interface {
	PredictCTR(req *BidRequest, candidate *Candidate) float64
	PredictCVR(req *BidRequest, candidate *Candidate) float64
	PredictValue(req *BidRequest, candidate *Candidate) float64
}

// DeepFMModel DeepFM 排序模型
type DeepFMModel struct {
	EmbeddingDim int
	Embeddings   map[string][][]float64 // field -> [dim]
	WideWeights  []float64              // 宽层权重
	DeepLayers   []LayerParams          // 深度网络层
	Bias         float64                // 偏置项
}

// LayerParams 网络层参数
type LayerParams struct {
	Weights [][]float64
	Bias    []float64
	Activation string // relu, sigmoid, tanh
}

// PredictCTR 预测 CTR
func (m *DeepFMModel) PredictCTR(req *BidRequest, candidate *Candidate) float64 {
	// Wide 部分：交叉特征
	wideScore := m.predictWide(req, candidate)
	
	// Deep 部分：深度特征
	deepScore := m.predictDeep(req, candidate)
	
	// FM 部分：二阶特征交互
	fmScore := m.predictFM(req, candidate)
	
	// DeepFM = Wide + FM + Deep
	logit := wideScore + fmScore + deepScore + m.Bias
	
	return sigmoid(logit)
}

func (m *DeepFMModel) predictWide(req *BidRequest, candidate *Candidate) float64 {
	features := m.extractWideFeatures(req, candidate)
	score := m.Bias
	for i, f := range features {
		if i < len(m.WideWeights) {
			score += m.WideWeights[i] * f
		}
	}
	return score
}

func (m *DeepFMModel) predictDeep(req *BidRequest, candidate *Candidate) float64 {
	features := m.extractDeepFeatures(req, candidate)
	layerOutput := features
	
	for _, layer := range m.DeepLayers {
		newOutput := make([]float64, len(layer.Weights))
		for j := range newOutput {
			sum := layer.Bias[j]
			for i, val := range layerOutput {
				if i < len(layer.Weights[j]) {
					sum += layer.Weights[j][i] * val
				}
			}
			newOutput[j] = activate(sum, layer.Activation)
		}
		layerOutput = newOutput
	}
	
	// 取最后一个神经元的输出
	return layerOutput[len(layerOutput)-1]
}

func (m *DeepFMModel) predictFM(req *BidRequest, candidate *Candidate) float64 {
	features := m.extractFMFeatures(req, candidate)
	dim := len(features)
	
	// FM: 0.5 * sum((sum(xi*vi)^2 - sum(xi^2*vi^2)))
	sumVi := make([]float64, dim)
	sumViSq := 0.0
	
	for i, xi := range features {
		vi := xi // 简化：vi = xi
		sumVi[i] += vi
		sumViSq += xi * xi * vi * vi
	}
	
	sumSquare := 0.0
	for _, v := range sumVi {
		sumSquare += v * v
	}
	
	return 0.5 * (sumSquare - sumViSq)
}

func sigmoid(x float64) float64 {
	if x > 500 { return 1.0 }
	if x < -500 { return 0.0 }
	return 1.0 / (1.0 + math.Exp(-x))
}

func activate(x float64, activation string) float64 {
	switch activation {
	case "relu":
		if x > 0 { return x }
		return 0
	case "sigmoid":
		return sigmoid(x)
	case "tanh":
		return math.Tanh(x)
	default:
		return x
	}
}

func (m *DeepFMModel) extractWideFeatures(req *BidRequest, candidate *Candidate) []float64 {
	return []float64{
		float64(len(req.Context.Keywords)),
		float64(len(req.User.Interests)),
	}
}

func (m *DeepFMModel) extractDeepFeatures(req *BidRequest, candidate *Candidate) []float64 {
	return []float64{
		float64(len(req.Context.Keywords)),
		float64(len(req.User.Interests)),
		m.hashFeature(req.Context.URL),
	}
}

func (m *DeepFMModel) extractFMFeatures(req *BidRequest, candidate *Candidate) []float64 {
	return []float64{
		float64(len(req.User.Interests)),
		float64(len(req.Context.Keywords)),
	}
}

func (m *DeepFMModel) hashFeature(s string) float64 {
	h := uint32(5381)
	for i := 0; i < len(s); i++ {
		h = h*33 ^ uint32(s[i])
	}
	return float64(h) / float64(math.MaxUint32)
}

// FeatureStore 特征存储
type FeatureStore struct {
	mu    sync.RWMutex
	cache map[string]map[string]float64 // key -> {feature_name: value}
}

func NewFeatureStore() *FeatureStore {
	return &FeatureStore{
		cache: make(map[string]map[string]float64),
	}
}

func (fs *FeatureStore) GetFeatures(key string) map[string]float64 {
	fs.mu.RLock()
	defer fs.mu.RUnlock()
	
	features, ok := fs.cache[key]
	if !ok {
		return make(map[string]float64)
	}
	
	// 深拷贝
	result := make(map[string]float64, len(features))
	for k, v := range features {
		result[k] = v
	}
	return result
}

func (fs *FeatureStore) SetFeatures(key string, features map[string]float64) {
	fs.mu.Lock()
	defer fs.mu.Unlock()
	
	fs.cache[key] = features
}
```

### 9.3 A/B 测试统计引擎

```go
package interview

import (
	"math"
	"time"
)

// ABTest A/B 测试
type ABTest struct {
	TestID       string
	Variants     []Variant
	Allocation   map[string]float64 // variant -> weight
	StartedAt    time.Time
	MinSamples   int
	Confidence   float64 // 目标置信度，默认 0.95
}

// Variant 变体
type Variant struct {
	ID   string
	Name string
}

// MetricResult 指标结果
type MetricResult struct {
	VariantID   string
	Impressions int
	Clicks      int
	Conversions int
	Revenue     float64
	Cost        float64
}

// TestAnalyzer 测试分析器
type TestAnalyzer struct {
	test *ABTest
}

// Analyze 分析测试结果
func (ta *TestAnalyzer) Analyze(results []MetricResult) *AnalysisOutput {
	output := &AnalysisOutput{
		Variants: make([]VariantAnalysis, len(results)),
	}
	
	for i, r := range results {
		va := VariantAnalysis{
			VariantID:   r.VariantID,
			Impressions: r.Impressions,
			Clicks:      r.Clicks,
			Conversions: r.Conversions,
			Revenue:     r.Revenue,
			Cost:        r.Cost,
		}
		
		// 计算各项指标
		if r.Impressions > 0 {
			va.CTR = float64(r.Clicks) / float64(r.Impressions)
			va.CVR = float64(r.Conversions) / float64(r.Clicks)
			va.CPM = r.Cost / float64(r.Impressions) * 1000
		}
		if r.Clicks > 0 {
			va.CPC = r.Cost / float64(r.Clicks)
		}
		if r.Cost > 0 {
			va.ROAS = r.Revenue / r.Cost
			va.CPA = r.Cost / float64(r.Conversions)
		}
		
		// 统计显著性检验
		va.PValue = ta.zTest(r.Clicks, r.Impressions)
		va.Significant = va.PValue < 0.05
		
		output.Variants[i] = va
	}
	
	// 确定 Winner
	output.Winner = output.findWinner()
	
	return output
}

// zTest Z 检验比较两个比例的差异
func (ta *TestAnalyzer) zTest(clicksA, impressionsA int) float64 {
	if impressionsA == 0 {
		return 1.0
	}
	
	pA := float64(clicksA) / float64(impressionsA)
	
	// 与基准（所有变体的平均）比较
	pBar := 0.05 // 假设基准 CTR 5%
	n := float64(impressionsA)
	
	// 标准误
	SE := math.Sqrt(pBar*(1-pBar)/n)
	if SE == 0 {
		return 1.0
	}
	
	z := (pA - pBar) / SE
	
	// 简化 p-value 计算
	return 2 * (1 - normalCDF(math.Abs(z)))
}

// normalCDF 正态分布累积函数（近似）
func normalCDF(x float64) float64 {
	// Abramowitz and Stegun 近似
	a1, a2, a3, a4 := 0.254829592, -0.284496736, 1.421413741, -1.453152027
	c := 0.3275911
	
	sign := 1.0
	if x < 0 {
		sign = -1
	}
	x = math.Abs(x)
	
	t := 1.0 / (1.0 + c*x)
	y := 1.0 - (((((a4*t+a3)*t)+a2)*t)+a1)*t*math.Exp(-x*x/2)
	
	return 0.5 * (1.0 + sign*y)
}

// VariantAnalysis 变体分析结果
type VariantAnalysis struct {
	VariantID   string
	Impressions int
	Clicks      int
	Conversions int
	Revenue     float64
	Cost        float64
	CTR         float64
	CVR         float64
	CPC         float64
	CPM         float64
	ROAS        float64
	CPA         float64
	PValue      float64
	Significant bool
}

// AnalysisOutput 分析输出
type AnalysisOutput struct {
	Variants []VariantAnalysis
	Winner   *VariantAnalysis
}

func (ao *AnalysisOutput) findWinner() *VariantAnalysis {
	var best *VariantAnalysis
	for i := range ao.Variants {
		if best == nil || ao.Variants[i].ROAS > best.ROAS {
			best = &ao.Variants[i]
		}
	}
	return best
}
```
