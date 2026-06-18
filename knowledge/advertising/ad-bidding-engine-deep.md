# 竞价引擎深度：RTB 协议/出价策略/RL 竞价源码级

> 从 OpenRTB 2.6 协议到强化学习竞价，逐行解析广告竞价系统核心

---

## 第一部分：OpenRTB 2.6 协议源码级解析

### BidRequest 完整结构

```json
{
  "id": "bid-request-12345",
  "tmax": 100,
  "at": 1,
  "imp": [
    {
      "id": "imp-001",
      "banner": {
        "w": 300, "h": 250, "pos": 2,
        "api": [1, 2, 3],
        "mimes": ["image/jpeg", "image/png"],
        "topframe": 1
      },
      "video": {
        "mimes": ["video/mp4"],
        "protocols": [1, 2, 3, 4, 5, 6, 7, 8],
        "maxduration": 30,
        "startdelay": 0,
        "linearity": 1,
        "skip": 1,
        "skipmin": 5,
        "placement": 2
      },
      "bidfloor": 1.0,
      "bidfloorcur": "USD",
      "pmp": {
        "private_auctions": [
          {
            "id": "pmp-001",
            "bidders": ["dsp-001", "dsp-002"],
            "deals": [
              {
                "id": "deal-001",
                "bidfloor": 2.5,
                "bidfloorcur": "USD"
              }
            ]
          }
        ]
      }
    }
  ],
  "site": {
    "id": "site-001",
    "name": "Example News Site",
    "domain": "example.com",
    "cat": ["IAB19", "IAB19-1"],
    "page": "https://example.com/article/123",
    "publisher": {
      "id": "pub-001",
      "name": "Example Publisher"
    },
    "content": {
      "id": "content-001",
      "title": "OpenRTB Deep Dive",
      "language": "en"
    }
  },
  "device": {
    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
    "ip": "203.0.113.1",
    "make": "Apple",
    "model": "iPhone 15 Pro",
    "os": "iOS",
    "osv": "17.0",
    "h": 2340,
    "w": 1080,
    "devicetype": 1,
    "connectiontype": 0,
    "geo": {
      "lat": 37.7749,
      "lon": -122.4194,
      "city": "San Francisco",
      "region": "CA",
      "country": "US"
    }
  },
  "user": {
    "id": "user-001",
    "buyeruid": "dsp-user-001",
    "yob": 1990,
    "gender": "m",
    "keywords": "advertising,tech"
  },
  "regulations": {
    "gdpr": 1,
    "usprivacy": "1YNN"
  },
  "ext": {
    "schain": [
      {
        "asi": "example.com",
        "sid": "1234",
        "hp": 1,
        "rid": "transaction-id-001",
        "name": "Example Publisher",
        "domain": "example.com"
      }
    ]
  }
}
```

### Go 实现 BidRequest/BidResponse

```go
package openrtb

import (
	"encoding/json"
	"fmt"
)

// Banner 横幅广告
type Banner struct {
	ID       string   `json:"id,omitempty"`
	W        int      `json:"w,omitempty"`
	H        int      `json:"h,omitempty"`
	WMin     int      `json:"wmin,omitempty"`
	HMin     int      `json:"hmin,omitempty"`
	Pos      int      `json:"pos,omitempty"` // 0=Unknown, 1=Above Fold, ...
	BType    []int    `json:"btype,omitempty"`
	BAdv     []string `json:"badv,omitempty"`
	API      int      `json:"api,omitempty"` // 1=VPAID 1.0, 2=VPAID 2.0, 3=MRAID
	Mimes    []string `json:"mimes,omitempty"`
	TopFrame *int     `json:"topframe,omitempty"`
}

// Video 视频广告
type Video struct {
	MIMEs      []string `json:"mimes,omitempty"`
	Protocols  []int    `json:"protocols,omitempty"` // VAST 1-8
	Protocol   *int     `json:"protocol,omitempty"`
	W          *int     `json:"w,omitempty"`
	H          *int     `json:"h,omitempty"`
	StartDelay *int     `json:"startdelay,omitempty"`
	Linearity  *int     `json:"linearity,omitempty"` // 1=in-stream, 2=overlay
	MaxDuration *int    `json:"maxduration,omitempty"`
	Skip       *int     `json:"skip,omitempty"` // 0=不可跳过, 1=可跳过
	SkipMin    *int     `json:"skipmin,omitempty"`
	SkipAfter  *int     `json:"skipafter,omitempty"`
	Placement  *int     `json:"placement,omitempty"`
	Badv       []string `json:"badv,omitempty"`
}

// Imp 广告位
type Imp struct {
	ID         string  `json:"id"`
	BidFloor   float64 `json:"bidfloor,omitempty"`
	BidFloorCur string  `json:"bidfloorcur,omitempty"`
	Banner     *Banner `json:"banner,omitempty"`
	Video      *Video  `json:"video,omitempty"`
}

// Device 设备信息
type Device struct {
	UA           string `json:"ua,omitempty"`
	IP           string `json:"ip,omitempty"`
	Make         string `json:"make,omitempty"`
	Model        string `json:"model,omitempty"`
	OS           string `json:"os,omitempty"`
	OSV          string `json:"osv,omitempty"`
	H            int    `json:"h,omitempty"`
	W            int    `json:"w,omitempty"`
	DevType      int    `json:"devicetype,omitempty"` // 1=Mobile, 2=Desktop, 3=Tablet
	ConnectionType int  `json:"connectiontype,omitempty"` // 0=Unknown, 1=Ethernet, ...
	Carrier      string `json:"carrier,omitempty"`
	Language     string `json:"language,omitempty"`
	Country      string `json:"country,omitempty"`
	Geo          *Geo   `json:"geo,omitempty"`
}

// Geo 地理位置
type Geo struct {
	Lat    float64 `json:"lat,omitempty"`
	Lon    float64 `json:"lon,omitempty"`
	City   string  `json:"city,omitempty"`
	Region string  `json:"region,omitempty"`
	Country string `json:"country,omitempty"`
	Metro  string  `json:"metro,omitempty"`
	Zip    string  `json:"zip,omitempty"`
}

// User 用户信息
type User struct {
	ID         string   `json:"id,omitempty"`
	BuyerUID   string   `json:"buyeruid,omitempty"`
	YOB        int      `json:"yob,omitempty"`
	Gender     string   `json:"gender,omitempty"`
	Keywords   string   `json:"keywords,omitempty"`
	CustomData string   `json:"customdata,omitempty"`
	Geo        *Geo     `json:"geo,omitempty"`
}

// Site 网站上下文
type Site struct {
	ID          string    `json:"id,omitempty"`
	Name        string    `json:"name,omitempty"`
	Domain      string    `json:"domain,omitempty"`
	Cat         []string  `json:"cat,omitempty"`
	Page        string    `json:"page,omitempty"`
	Ref         string    `json:"ref,omitempty"`
	Publisher   *Publisher `json:"publisher,omitempty"`
	Content     *Content   `json:"content,omitempty"`
}

type Publisher struct {
	ID     string `json:"id,omitempty"`
	Name   string `json:"name,omitempty"`
	Domain string `json:"domain,omitempty"`
}

type Content struct {
	ID       string `json:"id,omitempty"`
	Episode  int    `json:"episode,omitempty"`
	Season   int    `json:"season,omitempty"`
	Series   string `json:"series,omitempty"`
	Title    string `json:"title,omitempty"`
	Category string `json:"category,omitempty"`
	Language string `json:"language,omitempty"`
}

// App APP 上下文
type App struct {
	ID        string    `json:"id,omitempty"`
	Name      string    `json:"name,omitempty"`
	Bundle    string    `json:"bundle,omitempty"`
	Domain    string    `json:"domain,omitempty"`
	Cat       []string  `json:"cat,omitempty"`
	Publisher *Publisher `json:"publisher,omitempty"`
	Content   *Content   `json:"content,omitempty"`
}

// BidRequest 竞价请求
type BidRequest struct {
	ID     string   `json:"id"`
	TMax   *int     `json:"tmax,omitempty"`
	AT     *int     `json:"at,omitempty"` // 1=First Price, 2=Second Price
	Imp    []Imp    `json:"imp"`
	Site   *Site    `json:"site,omitempty"`
	App    *App     `json:"app,omitempty"`
	Device *Device  `json:"device,omitempty"`
	User   *User    `json:"user,omitempty"`
	Regs   *Regs    `json:"regulations,omitempty"`
	Ext    json.RawMessage `json:"ext,omitempty"`
}

type Regs struct {
	GDPR        *int    `json:"gdpr,omitempty"`
	USPrivacy   string  `json:"usprivacy,omitempty"`
	COPPA       *int    `json:"coppa,omitempty"`
}

// BidResponse 竞价响应
type BidResponse struct {
	ID      string     `json:"id"`
	SeatBid []SeatBid  `json:"seatbid,omitempty"`
	NURL    string     `json:"nurl,omitempty"` // Win Notice URL
	BidID   string     `json:"bidid,omitempty"`
	Cur     string     `json:"cur,omitempty"`
}

type SeatBid struct {
	Bid   []Bid    `json:"bid"`
	Seat  string   `json:"seat,omitempty"`
	Group *int     `json:"group,omitempty"`
}

type Bid struct {
	ID        string   `json:"id"`
	ImpID     string   `json:"impid"`
	Price     float64  `json:"price"`
	ADM       string   `json:"adm"`
	AdID      string   `json:"adid,omitempty"`
	ADomain   []string `json:"adomain,omitempty"`
	IURL      string   `json:"iurl,omitempty"`
	CID       string   `json:"cid,omitempty"`
	CRID      string   `json:"crid,omitempty"`
	CAT       []string `json:"cat,omitempty"`
	Dest      string   `json:"dest,omitempty"`
	LURL      string   `json:"lurl,omitempty"`
	DURL      string   `json:"durl,omitempty"`
	Attr      []int    `json:"attr,omitempty"`
	API       *int     `json:"api,omitempty"`
	MIMEs     []string `json:"mimes,omitempty"`
	Exp       *int     `json:"exp,omitempty"`
}

// ParseBidRequest 解析 BidRequest
func ParseBidRequest(data []byte) (*BidRequest, error) {
	var req BidRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("parse bid request: %w", err)
	}
	return &req, nil
}

// BuildBidResponse 构建 BidResponse
func BuildBidResponse(reqID string, impID string, price float64, adm string) (*BidResponse, error) {
	resp := BidResponse{
		ID:     fmt.Sprintf("resp-%s", reqID),
		Cur:    "USD",
		SeatBid: []SeatBid{{
			Bid: []Bid{{
				ID:      fmt.Sprintf("bid-%s", reqID),
				ImpID:   impID,
				Price:   price,
				ADM:     adm,
				ADomain: []string{"example.com"},
				CID:     "campaign-001",
				CRID:    "creative-001",
				Dest:    "https://example.com/landing",
				LURL:    "https://tracker.example.com/impression",
				DURL:    "https://tracker.example.com/click",
			}},
		}},
	}
	return &resp, nil
}
```

---

## 第二部分：出价策略深度

### 出价策略对比

```
┌────────────────┬────────────┬────────────┬────────────┬────────────┐
│     策略       │  原理      │  优点      │  缺点      │  适用场景  │
├────────────────┼────────────┼────────────┼────────────┼────────────┤
│ 固定出价       │ 手动设置   │ 简单可控   │ 不灵活     │ 小规模投放 │
│ 目标 CPA     │ 系统自动   │ 成本可控   │ 学习期长   │ 品牌广告   │
│ 目标 ROAS    │ 系统自动   │ ROI 最大化 │ 需要历史   │ 效果广告   │
│ 智能出价       │ ML 预测    │ 精准出价   │ 需要数据   │ 大规模投放 │
│ RL 竞价       │ 强化学习   │ 自适应优化 │ 复杂度高   │ 大规模实时 │
└────────────────┴────────────┴────────────┴────────────┴────────────┘
```

### 智能出价实现

```go
package bidding

import (
	"context"
	"fmt"
	"math"
)

// BidRequest 出价请求
type BidRequest struct {
	RequestID  string
	CampaignID string
	UserID     string
	DeviceID   string
	IP         string
	Platform   string
	Inventory  Inventory
	BudgetLeft float64
	TargetCPA  float64
	TargetROAS float64
}

type Inventory struct {
	AdUnitID   string
	Position   string
	Format     string // banner/video/native
	Width      int
	Height     int
	Competition string // low/medium/high
}

// BidResponse 出价响应
type BidResponse struct {
	BidPrice float64
	WinProb  float64
	Strategy string
	Reason   string
}

// SmartBidder 智能出价器
type SmartBidder struct {
	predictor   Predictor
	rlPolicy    RLPolicy
	budgetMgr   BudgetManager
}

// Predictor 预测器接口
type Predictor interface {
	PredictCTR(ctx context.Context, features map[string]interface{}) float64
	PredictCVR(ctx context.Context, features map[string]interface{}) float64
}

// RLPolicy 强化学习策略接口
type RLPolicy interface {
	SelectAction(state []float64) *RLAction
}

type RLAction struct {
	BidMultiplier float64
	Strategy      string
}

// BudgetManager 预算管理器
type BudgetManager interface {
	HasBudget(campaignID string, amount float64) bool
	RemainingBudget(campaignID string) float64
	TotalBudget(campaignID string) float64
}

// PlaceBid 执行出价决策
func (b *SmartBidder) PlaceBid(ctx context.Context, req BidRequest) (*BidResponse, error) {
	// 1. 构建特征
	features := b.extractFeatures(req)
	
	// 2. 预测 CTR 和 CVR
	ctr := b.predictor.PredictCTR(ctx, features)
	cvr := b.predictor.PredictCVR(ctx, features)
	
	// 3. 计算预期转化价值
	expectedValue := ctr * cvr * req.TargetCPA
	
	// 4. RL 策略决策
	state := b.encodeState(req, ctr, cvr)
	action := b.rlPolicy.SelectAction(state)
	
	// 5. 基础出价 = 预期价值 * RL 乘数
	baseBid := expectedValue * action.BidMultiplier
	
	// 6. 预算感知调整
	budgetRatio := req.BudgetLeft / req.TargetCPA
	if budgetRatio < 0.5 {
		baseBid *= 0.8 // 预算紧张，保守出价
	} else if budgetRatio > 2.0 {
		baseBid *= 1.2 // 预算充足，激进出价
	}
	
	// 7. 竞争感知调整
	if req.Inventory.Competition == "high" {
		baseBid *= 1.15
	} else if req.Inventory.Competition == "low" {
		baseBid *= 0.9
	}
	
	// 8. 预算检查
	if !b.budgetMgr.HasBudget(req.CampaignID, baseBid) {
		return &BidResponse{
			BidPrice: 0,
			WinProb:  0,
			Strategy: "budget_exhausted",
			Reason:   "预算已耗尽",
		}, nil
	}
	
	// 9. 计算获胜概率
	winProb := b.calculateWinProbability(baseBid, req.Inventory.Competition)
	
	return &BidResponse{
		BidPrice: baseBid,
		WinProb:  winProb,
		Strategy: action.Strategy,
		Reason:   fmt.Sprintf("CTR=%.3f CVR=%.3f EV=%.3f mult=%.2f", ctr, cvr, expectedValue, action.BidMultiplier),
	}, nil
}

func (b *SmartBidder) extractFeatures(req BidRequest) map[string]interface{} {
	return map[string]interface{}{
		"user_id":    req.UserID,
		"device_id":  req.DeviceID,
		"ip":         req.IP,
		"platform":   req.Platform,
		"ad_unit":    req.Inventory.AdUnitID,
		"position":   req.Inventory.Position,
		"format":     req.Inventory.Format,
		"competition": req.Inventory.Competition,
	}
}

func (b *SmartBidder) encodeState(req BidRequest, ctr, cvr float64) []float64 {
	return []float64{
		float64(len(req.UserID)),
		ctr,
		cvr,
		req.TargetCPA,
		req.TargetROAS,
		req.BudgetLeft,
	}
}

func (b *SmartBidder) calculateWinProbability(bidPrice float64, competition string) float64 {
	// 简化的获胜概率模型
	var baseWinProb float64
	switch competition {
	case "high":
		baseWinProb = 0.3
	case "medium":
		baseWinProb = 0.5
	default:
		baseWinProb = 0.7
	}
	
	// 出价越高，获胜概率越高（sigmoid 函数）
	normalizedBid := bidPrice / 10.0 // 归一化
	winProb := 1.0 / (1.0 + math.Exp(-5*(normalizedBid-0.5)))
	
	return baseWinProb * winProb
}
```

---

## 第三部分：强化学习竞价

### Q-Learning 竞价实现

```go
package bidding

import (
	"math"
	"math/rand"
	"sync"
	"time"
)

// QTable Q 表
type QTable struct {
	mu       sync.RWMutex
	table    map[string]map[string]float64 // state -> action -> q_value
	learningRate    float64
	discountFactor  float64
	epsilon         float64
}

// NewQTable 创建 Q 表
func NewQTable(lr, gamma, epsilon float64) *QTable {
	return &QTable{
		table:          make(map[string]map[string]float64),
		learningRate:   lr,
		discountFactor: gamma,
		epsilon:        epsilon,
	}
}

// GetQValue 获取 Q 值
func (qt *QTable) GetQValue(state, action string) float64 {
	qt.mu.RLock()
	defer qt.mu.RUnlock()
	
	if actions, ok := qt.table[state]; ok {
		if q, ok := actions[action]; ok {
			return q
		}
	}
	return 0.0
}

// UpdateQValue 更新 Q 值
func (qt *QTable) UpdateQValue(state, action string, reward float64, nextState string) {
	qt.mu.Lock()
	defer qt.mu.Unlock()
	
	// 确保 state 存在
	if _, ok := qt.table[state]; !ok {
		qt.table[state] = make(map[string]float64)
	}
	
	// 确保 next state 存在
	if _, ok := qt.table[nextState]; !ok {
		qt.table[nextState] = make(map[string]float64)
	}
	
	// 获取当前 Q 值
	currentQ := qt.table[state][action]
	
	// 获取 next state 的最大 Q 值
	maxNextQ := 0.0
	for _, q := range qt.table[nextState] {
		if q > maxNextQ {
			maxNextQ = q
		}
	}
	
	// Q-Learning 更新公式
	// Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]
	newQ := currentQ + qt.learningRate*(reward + qt.discountFactor*maxNextQ - currentQ)
	qt.table[state][action] = newQ
}

// SelectAction ε-greedy 策略
func (qt *QTable) SelectAction(state string, actions []string) string {
	if rand.Float64() < qt.epsilon {
		// 探索：随机选择
		return actions[rand.Intn(len(actions))]
	}
	
	// 利用：选择 Q 值最大的动作
	qt.mu.RLock()
	defer qt.mu.RUnlock()
	
	bestAction := actions[0]
	bestQ := -math.MaxFloat64
	
	if actionsMap, ok := qt.table[state]; ok {
		for _, action := range actions {
			q := actionsMap[action]
			if q > bestQ {
				bestQ = q
				bestAction = action
			}
		}
	}
	
	return bestAction
}

// BidRLAgent 竞价 RL Agent
type BidRLAgent struct {
	qTable   *QTable
	actions  []string // 出价策略：["conservative", "moderate", "aggressive"]
	stateSpace []string
}

// NewBidRLAgent 创建竞价 RL Agent
func NewBidRLAgent() *BidRLAgent {
	// 定义动作空间
	actions := []string{"conservative", "moderate", "aggressive"}
	
	// 定义状态空间
	stateSpace := []string{
		"high_ctr_high_cvr", "high_ctr_low_cvr",
		"low_ctr_high_cvr", "low_ctr_low_cvr",
	}
	
	return &BidRLAgent{
		qTable:      NewQTable(0.1, 0.95, 0.1),
		actions:     actions,
		stateSpace:  stateSpace,
	}
}

// EncodeState 编码状态
func (a *BidRLAgent) EncodeState(ctr, cvr float64) string {
	if ctr > 0.03 && cvr > 0.05 {
		return "high_ctr_high_cvr"
	} else if ctr > 0.03 {
		return "high_ctr_low_cvr"
	} else if cvr > 0.05 {
		return "low_ctr_high_cvr"
	}
	return "low_ctr_low_cvr"
}

// SelectBid 选择出价策略
func (a *BidRLAgent) SelectBid(ctr, cvr float64) (string, float64) {
	state := a.EncodeState(ctr, cvr)
	action := a.qTable.SelectAction(state, a.actions)
	
	// 返回出价乘数
	var multiplier float64
	switch action {
	case "conservative":
		multiplier = 0.8
	case "moderate":
		multiplier = 1.0
	case "aggressive":
		multiplier = 1.3
	}
	
	return action, multiplier
}

// Update 更新 Q 表
func (a *BidRLAgent) Update(ctr, cvr float64, action string, reward float64) {
	nextState := a.EncodeState(ctr, cvr)
	a.qTable.UpdateQValue(action, action, reward, nextState)
}

// DecayEpsilon 衰减探索率
func (a *BidRLAgent) DecayEpsilon(factor float64) {
	a.qTable.epsilon *= factor
	if a.qTable.epsilon < 0.01 {
		a.qTable.epsilon = 0.01
	}
}
```

---

## 第四部分：自测题

### Q1: OpenRTB 中 First Price 和 Second Price 竞价的区别？

**A**: First Price（at=1）出价即实际支付；Second Price（at=2）支付第二高出价。趋势是第一价格竞价越来越多，DSP 需要更精确的出价策略。

### Q2: RL 竞价相比传统出价策略的优势？

**A**: RL 竞价能自适应市场环境变化，平衡探索和利用，长期 ROI 更高。但需要足够的训练数据和计算资源。

### Q3: 出价策略中预算感知的意义？

**A**: 预算紧张时保守出价避免超支，预算充足时激进出价获取更多流量。这是保证广告主 ROI 的关键。

---

## 第五部分：生产实践

### 1. 出价策略调优

```
出价策略调优要点：
1. CTR/CVR 预测模型定期重新训练
2. RL 参数（ε/gamma/α）定期调优
3. 预算分配策略根据 ROI 动态调整
4. 竞争环境感知，实时调整出价
```

### 2. 竞价延迟优化

```
竞价延迟优化：
1. 特征缓存（Redis < 1ms）
2. 模型量化（TensorRT < 5ms）
3. 并行推理（多模型并行 < 10ms）
4. 本地缓存（sync.Map < 0.1ms）
5. 总预算：< 50ms
```

### 3. A/B 测试

```
竞价策略 A/B 测试：
1. 对照组：固定出价
2. 实验组：目标 CPA / 目标 ROAS / RL 竞价
3. 评估指标：CTR/CVR/CPA/ROAS/预算消耗率
4. 显著性检验：p-value < 0.05
5. 胜出标准：ROAS 提升 > 5%
```
