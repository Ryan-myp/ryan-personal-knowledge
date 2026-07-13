# 实时竞价系统（RTB）深度实战：从协议到生产级 Go 实现

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证
> 广告平台技术 TL · 2026-07-13

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 RTB

```
传统广告投放 = 批发采购
  → 提前买断广告位
  → 价格固定，风险高
  → 像买房：一次性投入，长期持有

实时竞价（RTB）= 股票交易
  → 每次请求独立竞价
  → 价格动态变化
  → 像炒股：毫秒级决策，灵活调整
```

### RTB 核心流程

```
用户打开 App
  ↓
App SDK 请求广告位
  ↓
Ad Exchange（广告交易平台）
  ↓
Bid Request（竞价请求）→ JSON 格式
  ↓
DSP（需求方平台）接收请求
  ↓
1. 用户画像匹配
2. 出价策略计算
3. 生成 Bid Response（竞价响应）
  ↓
Ad Exchange 收集所有竞价
  ↓
Second Price Auction（第二价格拍卖）
  ↓
获胜者展示广告
  ↓
Impression Log（曝光日志）→ 计费
```

### 关键指标

| 指标 | 公式 | 典型值 |
|------|------|--------|
| RPM（千次收益） | (收益 / 展示数) × 1000 | $1-10 |
| CTR（点击率） | 点击数 / 展示数 | 0.5%-3% |
| CPC（单次点击成本） | 总花费 / 点击数 | $0.1-2 |
| eCPM（有效千次展示成本） | (总花费 / 展示数) × 1000 | $1-50 |
| Win Rate（胜率） | 获胜次数 / 竞价次数 | 10%-30% |

### Go 技术栈

```go
// 核心依赖
go get github.com/gorilla/mux        // HTTP 路由
go get github.com/redis/go-redis/v9  // Redis 缓存
go get github.com/confluentinc/confluent-kafka-go/kafka  // Kafka
go get github.com/segmentio/kafka-go // Kafka（备选）
go get github.com/google/uuid        // UUID 生成
go get gopkg.in/yaml.v3              // YAML 配置
```

---

## 第二部分：Bid Request 协议深度解析

### 2.1 OpenRTB 规范

OpenRTB 是 IAB（Interactive Advertising Bureau）制定的实时竞价标准协议。

**核心结构：**

```json
{
  "id": "bidrequest-12345",
  "imp": [
    {
      "id": "imp-001",
      "banner": {
        "w": 300,
        "h": 250,
        "pos": 1
      },
      "bidfloor": 0.5,
      "bidfloorcur": "USD"
    }
  ],
  "site": {
    "domain": "example.com",
    "name": "Example Site"
  },
  "device": {
    "ua": "Mozilla/5.0...",
    "ip": "192.168.1.1",
    "make": "Apple",
    "model": "iPhone 14"
  },
  "user": {
    "id": "user-12345",
    "buyeruid": "dsp-user-12345",
    "keywords": "tech,gaming"
  },
  "at": 2,
  "tmax": 100,
  "regs": {
    "ext": {
      "gdpr": 1
    }
  }
}
```

### 2.2 Go 实现：OpenRTB 请求解析

```go
package rtb

import (
	"encoding/json"
	"fmt"
	"time"
)

// BidRequest 符合 OpenRTB 2.5 规范
type BidRequest struct {
	ID     string          `json:"id"`
	Imp    []Impression    `json:"imp"`
	Site   *Site           `json:"site,omitempty"`
	App    *App            `json:"app,omitempty"`
	Device *Device         `json:"device,omitempty"`
	User   *User           `json:"user,omitempty"`
	AT     int             `json:"at"`        // 拍卖类型：1=FPA, 2=SPA
	TMax   int             `json:"tmax"`      // 超时时间（毫秒）
	Regs   *Regulations    `json:"regs,omitempty"`
	Source *BidRequestSource `json:"source,omitempty"`
}

// Impression 广告位信息
type Impression struct {
	ID         string      `json:"id"`
	BidFloor   float64     `json:"bidfloor"`
	BidFloorCur string    `json:"bidfloorcur"`
	Banner     *Banner     `json:"banner,omitempty"`
	Video      *Video      `json:"video,omitempty"`
	Native     *Native     `json:"native,omitempty"`
	Instl      int         `json:"instl"` // 0=页面内, 1=全屏
	TagID      string      `json:"tagid"`
	Secure     int         `json:"secure"` // 1=HTTPS
	Metrics    []string    `json:"metrics"`
}

// Banner 横幅广告
type Banner struct {
	W     int   `json:"w,omitempty"`
	H     int   `json:"h,omitempty"`
	WMax  int   `json:"wmax,omitempty"`
	HMax  int   `json:"hmax,omitempty"`
	Pos   int   `json:"pos"` // 广告位置：above=1, below=2, header=3, footer=4, interstitial=5
	Top   int   `json:"top"`
	Left  int   `json:"left"`
}

// Video 视频广告
type Video struct {
	MType  []int  `json:"mtype"`  // 1=video, 2=audio
	Protos []int  `json:"protos"` // VAST 协议版本
	W      int    `json:"w"`
	H      int    `json:"h"`
	MinDur int    `json:"minduration"`
	MaxDur int    `json:"maxduration"`
	Start  int    `json:"startdelay"` // 0=pre, 1=mid, 2=post
	Placement int `json:"placement"`
}

// Native 原生广告
type Native struct {
	Request string          `json:"request"`
	Response *NativeResponse `json:"response"`
}

type NativeResponse struct {
	Assets []NativeAsset `json:"assets"`
}

type NativeAsset struct {
	ID     int    `json:"id"`
	Title  *Title `json:"title,omitempty"`
	Image  *Image `json:"img,omitempty"`
	Data   *Data  `json:"data,omitempty"`
}

type Title struct {
	Text string `json:"text"`
}

type Image struct {
	URL  string `json:"url"`
	W    int    `json:"w"`
	H    int    `json:"h"`
	Type int    `json:"type"`
}

type Data struct {
	Type  int    `json:"type"` // 1=headline, 2=desc, 3=cta, 4=sponsoredBy, 5=phone, 6=addr, 7=price, 8=body
	Value string `json:"value"`
}

// Site 网站信息
type Site struct {
	Domain string `json:"domain"`
	Name   string `json:"name"`
	Category string `json:"cat"`
	Page   string `json:"page"`
	Ref    string `json:"ref"`
}

// App App 信息
type App struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Domain string `json:"domain"`
	Category string `json:"cat"`
	SectionCategory string `json:"sectioncat"`
	AreaCategory  string `json:"area_cat"`
}

// Device 设备信息
type Device struct {
	UA       string `json:"ua"`
	IP       string `json:"ip"`
	IPv6     string `json:"ipv6"`
	Model    string `json:"model"`
	Make     string `json:"make"`
	OS       string `json:"os"`
	OSVer    string `json:"osver"`
	DeviceType int  `json:"devicetype"` // 1=手机, 2=平板, 3=桌面, 4=电视, 5=其他
	ConnectionType int `json:"connectiontype"` // 1=蜂窝, 2=WIFI, 3=以太网
	Lat    float64 `json:"lat"`
	Lon    float64 `json:"lon"`
	Geo    *Geo    `json:"geo"`
}

type Geo struct {
	Lat    float64 `json:"lat"`
	Lon    float64 `json:"lon"`
	LocType int   `json:"loc_type"` // 1=GPS, 2=WIFI, 3=IP
	City   string  `json:"city"`
	State  string  `json:"state"`
	Country string `json:"country"`
}

// User 用户信息
type User struct {
	ID       string   `json:"id"`
	BuyerUID string   `json:"buyeruid"`
	Gen      int      `json:"gen"` // 0=未知, 1=男, 2=女
	YearBrth int      `json:"yearbrth"`
	Yons     []string `json:"yons"` // 兴趣标签
}

// Regulations 法规限制
type Regulations struct {
	Ext map[string]interface{} `json:"ext,omitempty"`
	GDPR int                  `json:"gdpr"` // 0=未定义, 1=适用, 0=不适用
}

// BidRequestSource 请求来源
type BidRequestSource struct {
	Link    int    `json:"link"` // 1=共享 ID
	DSID    string `json:"dsid"` // 数据源 ID
}

// ParseBidRequest 解析 Bid Request
func ParseBidRequest(body []byte) (*BidRequest, error) {
	var req BidRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return nil, fmt.Errorf("parse bid request: %w", err)
	}
	
	// 验证必填字段
	if req.ID == "" {
		return nil, fmt.Errorf("missing request ID")
	}
	if len(req.Imp) == 0 {
		return nil, fmt.Errorf("no impressions in request")
	}
	for _, imp := range req.Imp {
		if imp.ID == "" {
			return nil, fmt.Errorf("missing impression ID")
		}
	}
	
	return &req, nil
}

// Validate 验证 Bid Request 合法性
func (r *BidRequest) Validate() error {
	// 检查拍卖类型
	if r.AT != 0 && r.AT != 1 && r.AT != 2 {
		return fmt.Errorf("invalid auction type: %d", r.AT)
	}
	
	// 检查超时时间
	if r.TMax <= 0 || r.TMax > 5000 {
		return fmt.Errorf("invalid tmax: %d (must be 1-5000ms)", r.TMax)
	}
	
	// 检查每个广告位
	for i, imp := range r.Imp {
		if imp.BidFloor < 0 {
			return fmt.Errorf("impression[%d]: negative bid floor", i)
		}
		
		// 检查广告格式
		hasFormat := imp.Banner != nil || imp.Video != nil || imp.Native != nil
		if !hasFormat {
			return fmt.Errorf("impression[%d]: no ad format specified", i)
		}
	}
	
	return nil
}

// GetTimeout 获取超时时间
func (r *BidRequest) GetTimeout() time.Duration {
	return time.Duration(r.TMax) * time.Millisecond
}
```

### 2.3 逐行源码解析

**`ParseBidRequest` 函数：**

```go
func ParseBidRequest(body []byte) (*BidRequest, error) {
	var req BidRequest
	
	// json.Unmarshal 使用反射解析 JSON
	// 性能优化：可以使用 jsoniter 或 go-json 替代标准库
	if err := json.Unmarshal(body, &req); err != nil {
		return nil, fmt.Errorf("parse bid request: %w", err)
	}
	
	// 验证必填字段
	if req.ID == "" {
		return nil, fmt.Errorf("missing request ID")
	}
	
	return &req, nil
}
```

**关键点：**
1. **JSON 解析性能**：标准库 `encoding/json` 在高频场景下可能成为瓶颈
2. **内存分配**：每次解析都会分配新对象，需要对象池优化
3. **错误处理**：返回详细错误信息，便于监控和告警

**性能优化方案：**

```go
// 使用对象池减少 GC 压力
var bidRequestPool = sync.Pool{
	New: func() interface{} {
		return &BidRequest{}
	},
}

func ParseBidRequestPooled(body []byte) (*BidRequest, error) {
	req := bidRequestPool.Get().(*BidRequest)
	defer bidRequestPool.Put(req)
	
	if err := json.Unmarshal(body, req); err != nil {
		return nil, err
	}
	
	return req, nil
}
```

---

## 第三部分：出价策略深度解析

### 3.1 出价策略分类

| 策略 | 公式 | 适用场景 | 优点 | 缺点 |
|------|------|----------|------|------|
| **固定出价** | bid = fixed | 测试期 | 简单 | 不灵活 |
| **基于 eCPM** | bid = target_eCPM × pCTR | 品牌广告 | 保证效果 | 依赖 CTR 模型 |
| **基于 oCPM** | bid = target_cost × pConversion | 效果广告 | 优化转化 | 依赖 CVR 模型 |
| **动态出价** | bid = f(用户, 上下文, 预算) | 所有场景 | 灵活 | 复杂度高 |
| **强化学习** | bid = RL_agent(state) | 高级场景 | 自优化 | 训练成本高 |

### 3.2 Go 实现：出价引擎核心

```go
package bidding

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"
)

// BidStrategy 出价策略接口
type BidStrategy interface {
	// Calculate 计算出价
	// ctx: 上下文（含超时）
	// req: 竞价请求
	// userProfile: 用户画像
	// adCreative: 广告创意
	Calculate(ctx context.Context, req *rtb.BidRequest, userProfile *UserProfile, adCreative *AdCreative) (float64, error)
	
	// Type 返回策略类型
	Type() string
}

// UserProfile 用户画像
type UserProfile struct {
	UserID      string
	BuyerUID    string
	Demographics *Demographics
	Interests   []string
	Behavior    *BehaviorProfile
	PastConversions int
}

type Demographics struct {
	Gender   int // 0=未知, 1=男, 2=女
	AgeGroup int // 1=<18, 2=18-24, 3=25-34, 4=35-44, 5=45-54, 6=>55
	Location string
}

type BehaviorProfile struct {
	DeviceType    int // 1=手机, 2=平板, 3=桌面
	ConnectionType int // 1=蜂窝, 2=WIFI
	TimeOfDay     int // 0-23
	DayOfWeek     int // 0=周日, 6=周六
}

// AdCreative 广告创意
type AdCreative struct {
	CreativeID string
	AdType     string // banner, video, native
	TargetCTR  float64 // 预期 CTR
	TargetCVR  float64 // 预期 CVR
	Category   string
}

// FixedBidStrategy 固定出价策略
type FixedBidStrategy struct {
	Bid float64
}

func (s *FixedBidStrategy) Calculate(ctx context.Context, req *rtb.BidRequest, userProfile *UserProfile, adCreative *AdCreative) (float64, error) {
	// 检查预算
	if err := s.checkBudget(); err != nil {
		return 0, err
	}
	
	return s.Bid, nil
}

func (s *FixedBidStrategy) checkBudget() error {
	// TODO: 检查预算余额
	return nil
}

func (s *FixedBidStrategy) Type() string {
	return "fixed"
}

// TargetCPMBidStrategy 基于目标 eCPM 的出价策略
type TargetCPMBidStrategy struct {
	TargeteCPM float64
	pCTRModel  PCTRModel
	frequency  FrequencyController
}

type PCTRModel interface {
	// Predict 预测点击率
	Predict(ctx context.Context, features map[string]float64) (float64, error)
}

type FrequencyController interface {
	// GetFrequency 获取用户看到该广告的频次
	GetFrequency(ctx context.Context, userID, creativeID string) (int, error)
	// ShouldSkip 是否应该跳过（频次过高）
	ShouldSkip(ctx context.Context, userID, creativeID string, maxFreq int) bool
}

func (s *TargetCPMBidStrategy) Calculate(ctx context.Context, req *rtb.BidRequest, userProfile *UserProfile, adCreative *AdCreative) (float64, error) {
	// 1. 检查频次
	maxFreq := 3 // 同一用户最多看 3 次
	if s.frequency.ShouldSkip(ctx, userProfile.UserID, adCreative.CreativeID, maxFreq) {
		return 0, fmt.Errorf("frequency cap exceeded")
	}
	
	// 2. 预测 CTR
	features := map[string]float64{
		"user_age_group": float64(userProfile.Demographics.AgeGroup),
		"user_gender":    float64(userProfile.Demographics.Gender),
		"ad_category":    hashString(adCreative.Category),
		"time_of_day":    float64(userProfile.Behavior.TimeOfDay) / 24.0,
		"day_of_week":    float64(userProfile.Behavior.DayOfWeek) / 7.0,
	}
	
	pCTR, err := s.pCTRModel.Predict(ctx, features)
	if err != nil {
		return 0, fmt.Errorf("predict ctr: %w", err)
	}
	
	// 3. 计算出价：bid = target_eCPM × pCTR
	bid := s.TargeteCPM * pCTR
	
	// 4. 不低于底价
	minBid := req.Imp[0].BidFloor
	if bid < minBid {
		bid = minBid
	}
	
	// 5. 设置出价上限（防止超预算）
	maxBid := s.TargeteCPM * 2.0
	if bid > maxBid {
		bid = maxBid
	}
	
	return bid, nil
}

func (s *TargetCPMBidStrategy) Type() string {
	return "target_cpm"
}

// hashString 字符串哈希（用于特征离散化）
func hashString(s string) float64 {
	h := uint32(0)
	for _, c := range s {
		h = 31*h + uint32(c)
	}
	return float64(h) / math.MaxFloat32
}

// DynamicBidStrategy 动态出价策略（基于多维度特征）
type DynamicBidStrategy struct {
	pCTRModel  PCTRModel
	pCVRModel  PCVRModel
	budgetMgr  BudgetManager
	frequency  FrequencyController
}

type PCVRModel interface {
	Predict(ctx context.Context, features map[string]float64) (float64, error)
}

type BudgetManager interface {
	// GetRemainingBudget 获取剩余预算
	GetRemainingBudget(ctx context.Context, campaignID string) (float64, error)
	// ConsumeBudget 消耗预算
	ConsumeBudget(ctx context.Context, campaignID string, amount float64) error
	// IsBudgetExceeded 是否超出预算
	IsBudgetExceeded(ctx context.Context, campaignID string, bid float64) bool
}

func (s *DynamicBidStrategy) Calculate(ctx context.Context, req *rtb.BidRequest, userProfile *UserProfile, adCreative *AdCreative) (float64, error) {
	// 1. 预测 CTR 和 CVR
	ctfFeatures := map[string]float64{
		"user_age_group": float64(userProfile.Demographics.AgeGroup),
		"user_gender":    float64(userProfile.Demographics.Gender),
		"ad_category":    hashString(adCreative.Category),
	}
	
	pCTR, err := s.pCTRModel.Predict(ctx, ctfFeatures)
	if err != nil {
		return 0, fmt.Errorf("predict ctr: %w", err)
	}
	
	cvrFeatures := map[string]float64{
		"user_past_conversions": float64(userProfile.PastConversions),
		"ad_category":           hashString(adCreative.Category),
		"time_of_day":           float64(userProfile.Behavior.TimeOfDay) / 24.0,
	}
	
	pCVR, err := s.pCVRModel.Predict(ctx, cvrFeatures)
	if err != nil {
		return 0, fmt.Errorf("predict cvr: %w", err)
	}
	
	// 2. 计算目标 CPC
	targetCPC := 1.0 // 假设目标 CPC 为 $1
	targeteCPM := targetCPC * 1000 // $1000
	
	// 3. 计算出价：bid = target_eCPM × pCTR × pCVR × 1000
	// 注意：这里乘以 1000 是因为 eCPM 是千次展示成本
	bid := targeteCPM * pCTR * pCVR
	
	// 4. 检查预算
	campaignID := adCreative.CreativeID // 简化：创意 ID = Campaign ID
	if s.budgetMgr.IsBudgetExceeded(ctx, campaignID, bid) {
		return 0, fmt.Errorf("budget exceeded for campaign %s", campaignID)
	}
	
	// 5. 不低于底价
	minBid := req.Imp[0].BidFloor
	if bid < minBid {
		bid = minBid
	}
	
	return bid, nil
}

func (s *DynamicBidStrategy) Type() string {
	return "dynamic"
}
```

### 3.3 出价策略选型指南

| 场景 | 推荐策略 | 理由 |
|------|----------|------|
| 品牌广告（保证曝光） | Target CPM | 优化展示量 |
| 效果广告（优化转化） | oCPM / oCPC | 优化转化成本 |
| 冷启动（无历史数据） | Fixed Bid | 简单稳定 |
| 成熟业务（有数据） | Dynamic Bid | 最大化 ROI |
| 探索期（发现新机会） | Bandit Algorithm | 平衡探索与利用 |

---

## 第四部分：竞价流程与拍卖机制

### 4.1 拍卖类型对比

| 类型 | 价格 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **第一价格（FPA）** | 最高价者付最高价 | 简单透明 | 出价策略复杂 | 程序化直接购买 |
| **第二价格（SPA）** | 最高价者付第二高价 | 鼓励真实出价 | 可能被操纵 | OpenRTB 默认 |
| **通用第二价格（GSP）** | 变体 SPA | 平衡双方利益 | 实现复杂 | 搜索引擎广告 |

### 4.2 Go 实现：竞价处理器

```go
package bidding

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
	
	"yourproject/rtb"
)

// BidResponse 竞价响应
type BidResponse struct {
	ID      string    `json:"id"`
	BidResponses []BidResponseItem `json:"bidresponses"`
}

type BidResponseItem struct {
	ID       string  `json:"id"`        // 对应 imp.id
	Bid      float64 `json:"bid"`       // 出价
	Creative *Creative `json:"creative"` // 广告创意
	SeatBid  *SeatBid `json:"seatbid"`  // 广告主 ID
}

type Creative struct {
	ID         string  `json:"id"`
	ADID       string  `json:"adid"`
	IMPTracker []string `json:"imptracker"` // 曝光追踪器
	ClickTrackers []string `json:"clicktrackers"` // 点击追踪器
	Native     *NativeResponse `json:"native,omitempty"`
	Banner     *BannerResponse `json:"banner,omitempty"`
	Video      *VideoResponse `json:"video,omitempty"`
}

type NativeResponse struct {
	Version  string          `json:"v"`
	Assets   []NativeAssetResponse `json:"assets"`
	EventTrackers []EventTracker `json:"eventtrackers"`
	Privacy  string          `json:"privacy"`
}

type EventTracker struct {
	Method int    `json:"method"` // 1=impression, 2=click
	URL    string `json:"url"`
}

type BannerResponse struct {
	Width  int    `json:"w"`
	Height int    `json:"h"`
	URL    string `json:"url"`
	HTML   string `json:"html,omitempty"` // 原生 HTML 广告
}

type VideoResponse struct {
	Width  int    `json:"w"`
	Height int    `json:"h"`
	XML    string `json:"xml"` // VAST XML
	URL    string `json:"url"` // 视频文件 URL
}

// BidEngine 竞价引擎
type BidEngine struct {
	strategies map[string]BidStrategy
	mu         sync.RWMutex
	timeout    time.Duration
}

func NewBidEngine(timeout time.Duration) *BidEngine {
	return &BidEngine{
		strategies: make(map[string]BidStrategy),
		timeout:    timeout,
	}
}

// RegisterStrategy 注册出价策略
func (e *BidEngine) RegisterStrategy(strategy BidStrategy) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.strategies[strategy.Type()] = strategy
}

// ProcessBidRequest 处理竞价请求
func (e *BidEngine) ProcessBidRequest(ctx context.Context, req *rtb.BidRequest) (*BidResponse, error) {
	// 创建带超时的上下文
	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()
	
	// 1. 获取用户画像（从 Redis 缓存）
	userProfile, err := e.getUserProfile(ctx, req.User)
	if err != nil {
		log.Printf("get user profile failed: %v", err)
		userProfile = &UserProfile{UserID: req.User.ID} // 降级：使用基础信息
	}
	
	// 2. 获取广告创意（从广告库）
	adCreatives, err := e.getAdCreatives(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("get ad creatives: %w", err)
	}
	
	// 3. 对每个广告位和创意进行竞价
	bidResponses := make([]BidResponseItem, 0, len(req.Imp)*len(adCreatives))
	
	for _, imp := range req.Imp {
		for _, creative := range adCreatives {
			// 选择出价策略
			strategy, err := e.selectStrategy(creative)
			if err != nil {
				continue
			}
			
			// 计算出价
			ctxWithCancel, cancel := context.WithTimeout(ctx, 50*time.Millisecond) // 每个创意 50ms
			bid, err := strategy.Calculate(ctxWithCancel, req, userProfile, creative)
			cancel()
			
			if err != nil {
				// 出价失败，跳过
				continue
			}
			
			// 构建竞价响应
			bidResp := BidResponseItem{
				ID:    imp.ID,
				Bid:   bid,
				Creative: &Creative{
					ID:   creative.CreativeID,
					ADID: creative.AdID,
				},
				SeatBid: &SeatBid{
					Seat: creative.AdvertiserID,
					Bid:  bid,
				},
			}
			
			bidResponses = append(bidResponses, bidResp)
		}
	}
	
	// 4. 构建最终响应
	response := &BidResponse{
		ID:           req.ID,
		BidResponses: bidResponses,
	}
	
	return response, nil
}

// getUserProfile 从缓存获取用户画像
func (e *BidEngine) getUserProfile(ctx context.Context, user *rtb.User) (*UserProfile, error) {
	// TODO: 从 Redis 获取用户画像
	// key: user:profile:{userID}
	// value: JSON 序列化
	return &UserProfile{
		UserID: user.ID,
	}, nil
}

// getAdCreatives 获取匹配的广告创意
func (e *BidEngine) getAdCreatives(ctx context.Context, req *rtb.BidRequest) ([]*AdCreative, error) {
	// TODO: 从 Elasticsearch 或内存索引获取匹配的创意
	// 匹配条件：
	// 1. 广告位格式（banner/video/native）
	// 2. 广告主定向条件（地域、年龄、性别、兴趣）
	// 3. Campaign 状态（active）
	// 4. 预算充足
	return []*AdCreative{}, nil
}

// selectStrategy 选择出价策略
func (e *BidEngine) selectStrategy(creative *AdCreative) (BidStrategy, error) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	
	// TODO: 根据 Campaign 配置选择策略
	// 策略映射存储在数据库中
	strategy := e.strategies["target_cpm"]
	if strategy == nil {
		return nil, fmt.Errorf("strategy not found")
	}
	
	return strategy, nil
}

// SeatBid 广告主出价信息
type SeatBid struct {
	Seat  string  `json:"seat"`
	Bid   float64 `json:"bid"`
}
```

### 4.3 竞价流程时序图

```
BidEngine                    Redis                  Elasticsearch
    |                            |                          |
    |-- 1. 获取用户画像 --------->|                          |
    |<--- 2. 用户画像 JSON -------|                          |
    |                            |                          |
    |-- 3. 查询匹配创意 ------------------------------>|
    |<---------------------------- 4. 创意列表 --------------|
    |                            |                          |
    |-- 5. 计算出价 (CTR 模型) -->| (调用外部 API)          |
    |<--- 6. pCTR 值 -------------|                          |
    |                            |                          |
    |-- 7. 计算出价 (CVR 模型) -->| (调用外部 API)          |
    |<--- 8. pCVR 值 -------------|                          |
    |                            |                          |
    |-- 9. 构建 Bid Response --------------------------------|
    |                            |                          |
    |<-- 10. 返回竞价响应 -----------------------------------|
```

---

## 第五部分：生产级优化

### 5.1 性能优化：降低延迟

**目标：P99 延迟 < 100ms**

| 优化手段 | 效果 | 实现难度 |
|----------|------|----------|
| 用户画像缓存（Redis） | -50ms | 低 |
| 创意内存索引 | -30ms | 中 |
| 并行调用 CTR/CVR 模型 | -40ms | 中 |
| 连接池复用 | -10ms | 低 |
| 异步日志 | -5ms | 低 |

**Go 实现：并行调用多个模型**

```go
// parallelPredict 并行预测 CTR 和 CVR
func parallelPredict(ctx context.Context, pctrModel PCTRModel, pcvrModel PCVRModel, features map[string]float64) (float64, float64, error) {
	type result struct {
		value float64
		err   error
	}
	
	ch := make(chan result, 2)
	
	// 并行预测 CTR
	go func() {
		pCTR, err := pctrModel.Predict(ctx, features)
		ch <- result{pCTR, err}
	}()
	
	// 并行预测 CVR
	go func() {
		pCVR, err := pcvrModel.Predict(ctx, features)
		ch <- result{pCVR, err}
	}()
	
	// 等待两个结果
	var pCTR, pCVR float64
	var err1, err2 error
	
	for i := 0; i < 2; i++ {
		res := <-ch
		if i == 0 {
			pCTR = res.value
			err1 = res.err
		} else {
			pCVR = res.value
			err2 = res.err
		}
	}
	
	if err1 != nil {
		return 0, 0, err1
	}
	if err2 != nil {
		return 0, 0, err2
	}
	
	return pCTR, pCVR, nil
}
```

### 5.2 容错设计

**降级策略：**

```go
// 1. 用户画像获取失败
if userProfile == nil {
    // 使用默认画像（无定向）
    userProfile = &UserProfile{UserID: req.User.ID}
}

// 2. CTR 模型预测失败
if pCTR < 0.001 {
    // 使用默认 CTR（行业基准）
    pCTR = 0.01 // 1%
}

// 3. 预算检查失败
if budgetErr != nil {
    // 暂时允许投放，后续扣款时再检查
    log.Printf("budget check failed, allowing bid: %v", budgetErr)
}
```

### 5.3 监控与告警

```go
// Metrics 监控指标
type Metrics struct {
	requestCount    *prometheus.CounterVec
	bidCount        *prometheus.CounterVec
	winCount        *prometheus.CounterVec
	avgBidPrice     *prometheus.HistogramVec
	p99Latency      *prometheus.HistogramVec
	errorRate       *prometheus.CounterVec
}

func NewMetrics(registry *prometheus.Registry) *Metrics {
	return &Metrics{
		requestCount: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "rtb_request_total",
				Help: "Total RTB requests",
			},
			[]string{"status"},
		),
		p99Latency: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "rtb_p99_latency_ms",
				Help:    "P99 latency in milliseconds",
				Buckets: prometheus.ExponentialBuckets(1, 2, 10),
			},
			[]string{"strategy"},
		),
	}
}

// RecordMetrics 记录监控指标
func (m *Metrics) RecordMetrics(strategy string, latency time.Duration, success bool) {
	status := "success"
	if !success {
		status = "error"
	}
	
	m.requestCount.WithLabelValues(status).Inc()
	m.p99Latency.WithLabelValues(strategy).Observe(float64(latency.Milliseconds()))
}
```

---

## 第六部分：生产排障案例

### 6.1 案例：竞价延迟飙升

**故障现象：**
```
P99 延迟从 50ms 飙升到 500ms
错误率上升到 5%
```

**排查步骤：**

```bash
# 1. 检查 Redis 延迟
redis-cli --latency-history

# 2. 检查 Elasticsearch 查询耗时
GET _profile?human=true

# 3. 检查 GC 停顿
go tool trace trace.out | grep gc
```

**根因分析：**
```
问题：Elasticsearch 查询超时
原因：索引碎片化严重，查询效率下降
解决：重建索引 + 调整分片数量
```

**修复代码：**

```go
// 优化前：同步查询
creatives, err := esClient.Search(index).Query(query).Do(ctx)

// 优化后：异步查询 + 超时控制
ctx, cancel := context.WithTimeout(ctx, 20*time.Millisecond)
defer cancel()

creatives, err = esClient.Search(index).Query(query).Do(ctx)
if err != nil {
    // 降级：使用内存缓存
    creatives = m.creativeCache.GetMatching(req)
}
```

### 6.2 案例：出价过高导致预算耗尽

**故障现象：**
```
Campaign 预算在 2 小时内耗尽
正常应该持续 24 小时
```

**根因分析：**
```
问题：CTR 模型预测偏差
原因：训练数据过时，pCTR 普遍偏高
解决：重新训练模型 + 添加出价上限
```

**修复代码：**

```go
// 添加出价上限保护
maxBid := campaign.Budget / campaign.DurationHours * 3600 * 0.1
// 0.1 = 每小时内出价不超过预算的 10%

if bid > maxBid {
    bid = maxBid
    log.Printf("capping bid: %.2f -> %.2f", originalBid, bid)
}
```

### 6.3 案例：Redis 缓存穿透

**故障现象：**
```
大量无效用户 ID 请求
Redis CPU 使用率 100%
```

**根因分析：**
```
问题：恶意请求大量随机用户 ID
原因：没有对不存在的数据做缓存
解决：布隆过滤器 + 空值缓存
```

**修复代码：**

```go
// 布隆过滤器检查
if !m.bloomFilter.Exists(userID) {
    // 用户不存在，快速返回
    return nil, fmt.Errorf("user not found")
}

// 空值缓存（TTL 5 分钟）
cacheKey := fmt.Sprintf("user:profile:%s", userID)
if m.redis.Exists(cacheKey) {
    value, _ := m.redis.Get(cacheKey).Result()
    if value == "__NULL__" {
        return nil, fmt.Errorf("user profile not available")
    }
    // 反序列化用户画像
    userProfile := deserialize(value)
    return userProfile, nil
}
```

---

## 第七部分：Trade-off 分析与决策指南

### 7.1 技术方案对比

| 维度 | 方案 A：单体服务 | 方案 B：微服务 | 方案 C：Serverless |
|------|------------------|----------------|-------------------|
| 延迟 | 20ms | 50ms | 100ms |
| 吞吐量 | 10K QPS | 100K QPS | 1M QPS |
| 成本 | 低 | 中 | 高 |
| 复杂度 | 低 | 高 | 中 |
| 适用场景 | 小规模 | 中大规模 | 大规模波动 |

### 7.2 拍卖机制选择

| 场景 | 推荐机制 | 理由 |
|------|----------|------|
| 公开竞价 | Second Price | 鼓励真实出价 |
| 私有竞价 | First Price | 简单透明 |
| 混合竞价 | GSP | 平衡双方利益 |

---

## 第八部分：自测题

### 8.1 深度题 1：为什么 RTB 要求低延迟？

**问题：**
如果竞价延迟超过 200ms，会发生什么？如何优化？

<details>
<summary>点击查看详细答案</summary>

**答案：**

**影响：**
1. **用户体验下降**：页面加载卡顿
2. **广告填充率降低**：超时请求被丢弃
3. **竞价劣势**：高延迟导致错过竞价窗口

**优化方案：**
1. **预加载用户画像**：在请求到达前预取
2. **内存索引**：创意数据放在内存而非数据库
3. **并行调用**：CTR/CVR 模型并行预测
4. **边缘计算**：在离用户最近的节点部署竞价服务

</details>

### 8.2 深度题 2：第二价格拍卖的缺陷

**问题：**
第二价格拍卖有什么缺陷？为什么 Google Ads 改用第一价格？

<details>
<summary>点击查看详细答案</summary>

**答案：**

**第二价格拍卖缺陷：**
1. **非真实出价**： bidder 会低于真实价值出价
2. **复杂性**：需要复杂的出价策略调整
3. **透明度低**：广告主不知道实际支付价格

**第一价格优势：**
1. **简单透明**：出价即支付
2. **真实反映价值**： bidder 出多少付多少
3. **易于优化**：出价策略更直观

**行业趋势：**
- 2019 年 Google Ads 全面转向第一价格
- DSP 需要重新优化出价策略（通常出价 = 真实价值 × 0.8-0.9）

</details>

### 8.3 深度题 3：如何防止竞价欺诈？

**问题：**
RTB 系统中常见的欺诈类型有哪些？如何检测？

<details>
<summary>点击查看详细答案</summary>

**答案：**

**常见欺诈类型：**
1. **点击欺诈**：机器人模拟用户点击
2. **曝光欺诈**：不可见广告位计入展示
3. **流量欺诈**：虚假流量刷量
4. **Cookie  stuffing**：隐藏 iframe 设置 cookie

**检测方法：**
1. **行为分析**：检测非人类行为模式
2. **设备指纹**：识别模拟器/虚拟机
3. **IP 信誉**：黑名单 IP 过滤
4. **时序分析**：检测异常请求频率
5. **交叉验证**：对比多方数据源

**Go 实现示例：**
```go
func DetectFraud(req *rtb.BidRequest) bool {
    // 检查 IP 信誉
    if isBlacklistedIP(req.Device.IP) {
        return true
    }
    
    // 检查请求频率
    if isAbnormalFrequency(req.User.ID) {
        return true
    }
    
    // 检查设备指纹
    if isBotDevice(req.Device.UA) {
        return true
    }
    
    return false
}
```

</details>

---

## 第九部分：与知识库的对照

### 已有内容
- `knowledge/advertising/`：广告平台核心业务（139 文件）
- `knowledge/ad-ads/ad-data-platform-deep.md`：广告数据平台
- `knowledge/ad-ads/ad-iam-deep.md`：身份认证与权限管理
- `knowledge/reference/ad-distributed-arch.md`：分布式架构

### 本文件补充
- ✅ OpenRTB 协议完整解析
- ✅ 出价策略（固定/Target CPM/oCPM/动态）
- ✅ 竞价引擎核心实现
- ✅ 拍卖机制（FPA/SPA/GSP）
- ✅ 生产级优化（延迟/容错/监控）
- ✅ 生产排障案例

### 缺失内容（待补充）
- 归因分析模型（Last Click/First Click/Multi-Touch）— 建议新建 `knowledge/ad-ads/attribution-models-deep.md`
- 反作弊系统 — 建议新建 `knowledge/ad-ads/fraud-detection-deep.md`
- 预算与频次控制 — 建议新建 `knowledge/ad-ads/budget-frequency-deep.md`

---

## 附录：RTB 系统架构全景图

```
┌─────────────────────────────────────────────────────────────┐
│                        Ad Exchange                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ SSP      │  │ Ad Server│  │ Auction  │  │ Logging  │   │
│  │ (供给方) │  │          │  │ Engine   │  │ System   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │        │
└───────┼──────────────┼──────────────┼──────────────┼────────┘
        │              │              │              │
   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
   │ Media   │   │ DSP     │   │ Data    │   │ Analytics│
   │ Partners│   │ (需求方)│   │ Providers│  │ Platform │
   └─────────┘   └────┬────┘   └─────────┘   └─────────┘
                      │
              ┌───────┴───────┐
              │  Bid Engine   │
              │  ┌─────────┐  │
              │  │ Strategy│  │
              │  │ Manager │  │
              │  └────┬────┘  │
              │  ┌────┴────┐  │
              │  │ PCTR/P  │  │
              │  │ CVR Mod │  │
              │  └────┬────┘  │
              │  ┌────┴────┐  │
              │  │Budget/  │  │
              │  │FreqCtrl │  │
              │  └─────────┘  │
              └───────────────┘
```

---

> **深度等级**：🟢深（~1200 行，含源码级 Go 代码、生产排障、对比分析）
> **最后更新**：2026-07-13
