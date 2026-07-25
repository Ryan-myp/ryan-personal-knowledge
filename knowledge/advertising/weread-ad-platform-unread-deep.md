# 微信读书精华：广告平台未读完书籍蒸馏

> 来源：《互联网DSP广告揭秘》《数字广告系统》《互联网广告系统》《搜索引擎与程序化广告》《Python广告数据挖掘》《智能营销与计算广告》《程序化广告实战》《信息流广告入门》《抖音电商：巨量千川》《跨境电商B2B运营》《Google AdSense实战宝典》《Shopee跨境电商》《算法与数据中台》《在线广告》《广告营销的底层思维》《搜索引擎营销推广》《智能搜索和推荐系统》《一切从广告开始》《程序化广告：个性化精准投放实用手册》《数字广告生态》《广告的没落公关的崛起》《快消品营销动销三本套装》《奥格威谈广告》《白酒营销培训宝典》《跨境电商基础、策略与实战》《网络营销推广实战宝典》
> 状态：未读完（基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：DSP 广告系统

### DSP 核心架构

```
DSP 系统架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 竞价引擎（Bidding Engine）                                        │
│    ├── 实时竞价：毫秒级响应                                          │
│    ├── 出价策略：oCPX/CPA/CPC/CPM                                   │
│    └── 预算控制：日预算/总预算/频控                                  │
│                                                                     │
│ 2. 用户匹配（User Matching）                                         │
│    ├── ID Mapping：多渠道身份识别                                   │
│    ├── 受众定向：人群标签和细分                                     │
│    └── 频率控制：避免过度曝光                                       │
│                                                                     │
│ 3. 创意管理（Creative Management）                                   │
│    ├── 素材审核：合规性检查                                         │
│    ├── A/B 测试：创意效果对比                                       │
│    └── 动态创意：个性化内容生成                                     │
│                                                                     │
│ 4. 数据分析（Analytics）                                             │
│    ├── 实时报表：投放效果监控                                       │
│    ├── 归因分析：转化路径追踪                                       │
│    └── 优化建议：智能调优推荐                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 竞价策略

```
竞价策略对比：
┌────────────────┬────────────┬────────────┬────────────┐
│     策略       │  原理      │  优点      │  缺点      │
├────────────────┼────────────┼────────────┼────────────┤
│ CPC            │ 按点击付费 │ 成本可控   │ 质量难保   │
│ CPM            │ 按展示付费 │ 品牌曝光   │ 转化不确定 │
│ oCPM           │ 智能出价   │ 效果优化   │ 需要数据   │
│ CPA            │ 按行动付费 │ ROI 最高   │ 门槛较高   │
│ pCPA           │ 目标 CPA   │ 平衡成本   │ 复杂度高   │
└────────────────┴────────────┴────────────┴────────────┘

推荐：
• 冷启动：CPC/CPM
• 数据积累：oCPM
• 成熟期：pCPA
```

---

## 第二部分：广告数据管道

### 数据采集

```
广告数据采集：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 曝光日志                                                          │
│    ├── 时间戳：精确到毫秒                                           │
│    ├── 用户ID：匿名化处理                                           │
│    ├── 广告ID：创意标识                                             │
│    └── 设备信息：UA/IP/OS/浏览器                                    │
│                                                                     │
│ 2. 点击日志                                                          │
│    ├── 点击时间：精确到毫秒                                         │
│    ├── 点击位置：屏幕坐标                                           │
│    ├── 停留时间：页面停留                                           │
│    └── 跳转URL：点击后的目标地址                                    │
│                                                                     │
│ 3. 转化日志                                                          │
│    ├── 转化类型：下载/注册/购买/激活                                │
│    ├── 转化价值：金额/积分/等级                                     │
│    ├── 转化时间：从曝光到转化的时间差                               │
│    └── 归因窗口：7天/15天/30天                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据分析

```
广告数据分析：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 描述性分析                                                        │
│    ├── 汇总统计：均值/中位数/标准差                                 │
│    ├── 趋势分析：时间序列分解                                       │
│    └── 对比分析：A/B测试/同期对比                                   │
│                                                                     │
│ 2. 诊断性分析                                                        │
│    ├── 根因分析：问题定位                                           │
│    ├── 关联分析：变量间关系                                         │
│    └── 异常检测：离群点识别                                         │
│                                                                     │
│ 3. 预测性分析                                                        │
│    ├── 回归分析：数值预测                                           │
│    ├── 分类模型：转化率预测                                         │
│    └── 时间序列：趋势预测                                           │
│                                                                     │
│ 4. 处方性分析                                                        │
│    ├── 优化建议：策略推荐                                           │
│    ├── 模拟仿真：what-if分析                                       │
│    └── 决策支持：多目标优化                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：自测题

### Q1: DSP 的四个核心模块？

**A**: 竞价引擎、用户匹配、创意管理、数据分析。

### Q2: 广告数据采集的三类日志？

**A**: 曝光日志、点击日志、转化日志。

### Q3: 广告数据分析的四层？

**A**: 描述性分析、诊断性分析、预测性分析、处方性分析。

---

## Go 代码实战：DSP 核心模块实现

### 竞价引擎并发处理

```go
package dsp

import (
	"context"
	"sync"
	"time"
)

// BidRequestHandler 竞价请求处理器
type BidRequestHandler struct {
	pool       *WorkerPool
	index      *MemoryIndex
	ranker     *RankingEngine
	budgetMgr  *BudgetManager
	freqCtrl   *FrequencyController
}

// MemoryIndex 内存索引（用户→广告映射）
type MemoryIndex struct {
	mu          sync.RWMutex
	userTarget  map[string][]*Ad // user_id -> ads
	geoTarget   map[string][]*Ad // region_code -> ads
	interestMap map[string][]*Ad // interest_tag -> ads
}

func (idx *MemoryIndex) GetCandidateAds(userID string, geo string, interests []string) []*Ad {
	idx.mu.RLock()
	defer idx.mu.RUnlock()
	
	var candidates []*Ad
	
	// 1. 用户维度召回
	if ads, ok := idx.userTarget[userID]; ok {
		candidates = append(candidates, ads...)
	}
	
	// 2. 地域维度召回
	if ads, ok := idx.geoTarget[geo]; ok {
		candidates = idx.mergeCandidates(candidates, ads)
	}
	
	// 3. 兴趣维度召回
	for _, tag := range interests {
		if ads, ok := idx.interestMap[tag]; ok {
			candidates = idx.mergeCandidates(candidates, ads)
		}
	}
	
	return idx.dedup(candidates)
}

func (idx *MemoryIndex) mergeCandidates(base, new []*Ad) []*Ad {
	existing := make(map[string]bool, len(base))
	for _, ad := range base {
		existing[ad.ID] = true
	}
	for _, ad := range new {
		if !existing[ad.ID] {
			base = append(base, ad)
			existing[ad.ID] = true
		}
	}
	return base
}

func (idx *MemoryIndex) dedup(ads []*Ad) []*Ad {
	seen := make(map[string]bool, len(ads))
	result := make([]*Ad, 0, len(ads))
	for _, ad := range ads {
		if !seen[ad.ID] {
			seen[ad.ID] = true
			result = append(result, ad)
		}
	}
	return result
}

// BudgetManager 预算管理器（支持 oCPX）
type BudgetManager struct {
	mu       sync.Mutex
	campaigns map[string]*CampaignBudget
}

type CampaignBudget struct {
	ID           string
	DailyLimit   float64
	TotalLimit   float64
	DailySpent   float64
	TotalSpent   float64
	oCPXTarget   float64 // oCPA/oCPC 目标转化成本
	estimatedCVR float64 // 预估CVR用于oCPX出价
}

func (bm *BudgetManager) CalculateBid(campID string, pCTR, pCVR float64, minCPM float64) float64 {
	bm.mu.Lock()
	defer bm.mu.Unlock()
	
	cb := bm.campaigns[campID]
	
	// oCPX 出价公式: bid = target_cost × pCTR × pCVR
	if cb.oCPXTarget > 0 {
		bid := cb.oCPXTarget * pCTR * pCVR
		return max(bid, minCPM)
	}
	
	// 传统 CPC/CPM 出价
	return max(pCTR*100, minCPM)
}

// WorkerPool 工作池（限制并发度）
type WorkerPool struct {
	sem chan struct{}
	wg  sync.WaitGroup
}

func NewWorkerPool(size int) *WorkerPool {
	return &WorkerPool{
		sem: make(chan struct{}, size),
	}
}

func (wp *WorkerPool) Submit(ctx context.Context, fn func() error) error {
	wp.sem <- struct{}{}
	wp.wg.Add(1)
	
	go func() {
		defer wp.wg.Done()
		defer func() { <-wp.sem }()
		_ = fn()
	}()
	return nil
}

// Pipeline 竞价流水线
func (h *BidRequestHandler) ProcessBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	// Stage 1: 召回候选广告（内存索引，<1ms）
	candidates := h.index.GetCandidateAds(req.UserID, req.Geo, req.Interests)
	
	// Stage 2: 频次控制过滤（内存+布隆过滤器）
	filtered := make([]*Ad, 0, len(candidates))
	for _, ad := range candidates {
		if h.freqCtrl.Check(ad.CampaignID, req.UserID) {
			filtered = append(filtered, ad)
		}
	}
	
	// Stage 3: 粗排（特征计算 + 轻量模型，<5ms）
	type scoredAd struct {
		ad     *Ad
		score  float64
		pCTR   float64
		pCVR   float64
	}
	scored := make([]scoredAd, 0, len(filtered))
	for _, ad := range filtered {
		pCTR := h.ranker.PredictCTR(ctx, ad, req)
		pCVR := h.ranker.PredictCVR(ctx, ad, req)
		bid := h.budgetMgr.CalculateBid(ad.CampaignID, pCTR, pCVR, ad.MinCPM)
		if bid >= ad.MinCPM {
			scored = append(scored, scoredAd{ad, bid, pCTR, pCVR})
		}
	}
	
	// Stage 4: 精排 + 重排（<10ms）
	topN := h.ranker.SortAndRerank(scored, req)
	
	// Stage 5: 返回最高分
	if len(topN) == 0 {
		return nil, nil
	}
	
	return &BidResponse{
		BidPrice: topN[0].score,
		Creative: topN[0].ad.Creative,
	}, nil
}
```

### 自测题

<details>
<summary>Q1: MemoryIndex 的 mergeCandidates 为什么用 map[string]bool 做去重而不是先合并再遍历？</summary>

**答案**：

**时间复杂度对比**：
| 方法 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 先合并再去重 | O(n×m) | O(n+m) | 每次 append 后线性搜索已存在ID |
| map 边合并在去重 | O(n+m) | O(n+m) | 单次哈希查找 O(1) |

生产环境用 `map[string]bool` 是标准做法。但注意：**预分配容量** `make(map[string]bool, len(base)+len(new))` 可以避免扩容开销。在竞价引擎中，每次纳秒都重要。

</details>

<details>
<summary>Q2: oCPX 出价公式 `bid = target_cost × pCTR × pCVR` 在 pCVR 极低时会导致什么问题？如何解决？</summary>

**答案**：

**问题**：当 pCVR < 0.001（千分之一）时，出价会趋近于 0，导致广告永远拿不到展示——即使 target_cost=50元，pCTR=0.02，pCVR=0.0001 → bid=0.0001元，低于任何 minCPM。

**解决方案**：
```go
// 方案1: 设置出价下限
bid := max(cb.oCPXTarget*pCTR*pCVR, minCPM)

// 方案2: CVR 平滑（加拉普拉斯平滑）
smoothCVR := (estimatedConversions + 1) / (estimatedImpressions + 2)

// 方案3: 探索-利用平衡（Bandit算法）
// 对新广告给予探索机会，不纯依赖 pCVR
```

实际生产中三种方案组合使用：平滑 + 下限 + 探索。

</details>

<details>
<summary>Q3: WorkerPool 的 sem channel 方案相比 sync.WaitGroup 有什么优势？什么场景应该用哪个？</summary>

**答案**：

| 特性 | sem channel | sync.WaitGroup |
|------|-------------|----------------|
| 并发控制 | ✅ 天然限流 | ❌ 需要额外机制 |
| 背压 | ✅ channel 满时阻塞 | ❌ 无背压 |
| 优雅关闭 | ✅ context 取消 | ⚠️ 需配合 channel |
| 简单等待 | ⚠️ 需 wg.Wait() | ✅ 直接 Wait() |

**选择原则**：
- **竞价引擎**：必须用 sem channel（限制 goroutine 数防止 OOM）
- **一次性批处理**：用 WaitGroup（如批量更新预算）
- **生产级**：sem + WaitGroup 组合使用

</details>
