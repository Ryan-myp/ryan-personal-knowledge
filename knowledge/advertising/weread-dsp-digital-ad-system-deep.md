# 微信读书精华：互联网DSP广告揭秘 + 数字广告系统 蒸馏笔记

> 来源：《互联网DSP广告揭秘：精准投放与高效转化之道》- 曲海佳
>       《数字广告系统：技术、产品与市场》- 顾明毅
> 状态：未读完（高价值，基于目录和简介蒸馏）
> 蒸馏日期：2026-06-18

---

## 第一部分：DSP 核心架构

### DSP 系统组成

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

## 第二部分：广告系统技术

### RTB 流程

```
实时竞价流程：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 请求阶段                                                          │
│    ├── 媒体请求：Ad Request                                         │
│    ├── 用户信息：User Profile                                        │
│    └── 上下文：Page Context                                          │
│                                                                     │
│ 2. 决策阶段                                                          │
│    ├── 受众匹配：Audience Matching                                  │
│    ├── 出价计算：Bid Calculation                                    │
│    └── 创意选择：Creative Selection                                 │
│                                                                     │
│ 3. 执行阶段                                                          │
│    ├── 竞价响应：Bid Response                                       │
│    ├── 中标通知：Win Notice                                         │
│    └── 创意展示：Ad Impression                                      │
│                                                                     │
│ 4. 反馈阶段                                                          │
│    ├── 点击上报：Click Tracking                                     │
│    ├── 转化上报：Conversion Tracking                                │
│    └── 效果归因：Attribution                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据管道

```
广告数据管道：
┌─────────────────────────────────────────────────────────────────────┐
│ 数据采集层：                                                        │
│ • 曝光日志：Impression Log                                         │
│ • 点击日志：Click Log                                              │
│ • 转化日志：Conversion Log                                         │
│                                                                     │
│ 数据处理层：                                                        │
│ • 实时处理：Flink/Kafka Streams                                    │
│ • 离线处理：Spark/Hive                                             │
│ • 特征工程：Feature Store                                          │
│                                                                     │
│ 数据存储层：                                                        │
│ • 热数据：Redis（用户画像、实时特征）                               │
│ • 温数据：ClickHouse（报表、分析）                                  │
│ • 冷数据：HDFS（归档、训练）                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：自测题

### Q1: DSP 的四个核心模块？

**A**: 竞价引擎、用户匹配、创意管理、数据分析。

### Q2: 竞价策略如何选择？

**A**: 冷启动用 CPC/CPM，数据积累用 oCPM，成熟期用 pCPA。

### Q3: 广告数据管道的三层？

**A**: 采集层（日志）、处理层（实时/离线）、存储层（热/温/冷）。

---

## Go 实现：DSP 竞价引擎核心

```go
package dsp

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// DSPBidEngine DSP 竞价引擎 - 从用户请求到广告展示的完整链路
type DSPBidEngine struct {
	recall    RecallEngine   // 召回
	ranking   RankingModel   // 排序模型 (DeepFM/DIN)
	bidding   BiddingStrategy // 出价策略
	freqCtrl  FreqController  // 频次控制
	budgetMgr *BudgetManager  // 预算
	cache     Cache           // Redis 缓存
}

// BidRequest DSP 侧收到的竞价请求
type BidRequest struct {
	UserID    string    `json:"user_id"`
	DeviceID  string    `json:"device_id"`
	AppID     string    `json:"app_id"`
	AdSlotID  string    `json:"ad_slot_id"`
	BidFloor  float64   `json:"bid_floor"` // 底价
	Timestamp time.Time `json:"timestamp"`
	TraceID   string    `json:"trace_id"`
}

// BidResponse DSP 返回的竞价响应
type BidResponse struct {
	BidID      string    `json:"bid_id"`
	CreativeID string    `json:"creative_id"`
	BidPrice   float64   `json:"bid_price"`
	eCPM       float64   `json:"ecpm"`
	Targeting  Targeting `json:"targeting"`
}

// Targeting 定向条件
type Targeting struct {
	Keywords []string `json:"keywords"`
	Demographics Demographics `json:"demographics"`
	Geo []GeoRegion `json:"geo"`
}

type Demographics struct {
	AgeRange string `json:"age_range"` // "18-24","25-34"
	Gender   string `json:"gender"`    // "M","F","ALL"
}

type GeoRegion struct {
	Country string `json:"country"`
	Province string `json:"province"`
	City    string `json:"city"`
}

// Bid 核心竞价方法 - P99 < 90ms
func (e *DSPBidEngine) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	start := time.Now()

	// Step 1: 获取用户画像 (Redis pipeline: user_feat + user_profile)
	userFeat, err := e.getUserFeatures(ctx, req.UserID)
	if err != nil {
		return nil, fmt.Errorf("get user features: %w", err)
	}

	// Step 2: 召回候选广告 (多路并行: vector + rule + retention + hot)
	candidates, err := e.recall.Recall(ctx, req, userFeat)
	if err != nil {
		return nil, fmt.Errorf("recall: %w", err)
	}

	// Step 3: 频次过滤 (检查用户是否已看过该广告)
	candidates = e.freqCtrl.Filter(candidates, req.UserID)

	// Step 4: 预算过滤
	candidates = e.budgetMgr.Filter(candidates)

	if len(candidates) == 0 {
		return &BidResponse{BidID: req.TraceID}, nil
	}

	// Step 5: 排序 (DeepFM 批量推理)
	scored, err := e.ranking.ScoreBatch(ctx, candidates, userFeat)
	if err != nil {
		return nil, fmt.Errorf("ranking: %w", err)
	}

	// Step 6: 出价 (根据 pCTR * pCVR * bidGoal 计算出价)
	best := scored[0] // Top-1
	bidPrice := e.bidding.Calculate(best)

	// 确保不低于底价
	if bidPrice < req.BidFloor {
		bidPrice = req.BidFloor
	}

	eCPM := bidPrice * 1000 // CPC -> CPM 换算

	latency := time.Since(start).Milliseconds()
	if latency > 90 {
		// 告警：P99 超标
		fmt.Printf("[WARN] bid latency %.2fms exceeds 90ms target\n", float64(latency))
	}

	return &BidResponse{
		BidID:      fmt.Sprintf("bid_%s", req.TraceID),
		CreativeID: best.CreativeID,
		BidPrice:   bidPrice,
		eCPM:       eCPM,
		Targeting:  best.Targeting,
	}, nil
}

// getUserFeatures 从 Redis 批量获取用户特征
func (e *DSPBidEngine) getUserFeatures(ctx context.Context, userID string) (UserFeatures, error) {
	// Redis Pipeline: HGETALL user:features:{id} + HGETALL user:profile:{id}
	pipeline := e.cache.NewPipeline()

	featKey := fmt.Sprintf("user:features:%s", userID)
	profKey := fmt.Sprintf("user:profile:%s", userID)

	pipeline.HGetAll(ctx, featKey)
	pipeline.HGetAll(ctx, profKey)

	results, err := pipeline.Exec(ctx)
	if err != nil {
		return UserFeatures{}, err
	}

	// Parse results...
	var feats UserFeatures
	_ = results
	return feats, nil
}
```

## 关键参数调优

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 召回候选集 | 500-1000 | 太多增加排序成本，太少丢失优质广告 |
| 排序 Top-K | 3-10 | 重排后展示数量 |
| 竞价超时 | 30ms | 召回阶段最大耗时 |
| Redis TTL | 30min | 用户特征缓存过期时间 |
| 预算扣减频率 | 实时 | 不能延迟，否则超投 |
