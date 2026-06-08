# 设计模式与系统架构 — Go 源码级 23 种模式、DDD、CQRS、Saga、分布式协议

> 标签: `#设计模式` `#DDD` `#CQRS` `#EventSourcing` `#Saga` `#Go` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 23 种设计模式 — Go 源码级实现

### 1.1 创建型模式（Creational）

#### 单例模式（Singleton）— Go 三种实现

```go
// 方式1: sync.Once（Go 推荐做法）
type Config struct {
    mu   sync.Mutex
    m    map[string]string
}

var (
    once   sync.Once
    config *Config
)

func GetConfig() *Config {
    once.Do(func() {
        config = &Config{m: make(map[string]string)}
        config.m["timeout"] = "30s"
    })
    return config
}

// 方式2: init() + 包级变量（最简洁）
var defaultLogger = &Logger{level: "info"}
func GetLogger() *Logger { return defaultLogger }

// sync.Once 源码剖析（src/sync/once.go）:
// type Once struct {
//     done uint32 // atomic, 0=未执行, 1=已执行
//     m    Mutex
// }
// func (o *Once) Do(f func()) {
//     if atomic.LoadUint32(&o.done) == 1 { return }
//     o.m.Lock()
//     defer o.m.Unlock()
//     if o.done == 0 { f(); atomic.StoreUint32(&o.done, 1) }
// }
//
// 关键点:
// - atomic.LoadUint32 读 done，未执行时走锁路径
// - 双检：拿到锁后还要再检查 done（其他 goroutine 可能先完成了）
// - atomic.StoreUint32 写 done，保证 happens-before 关系
// - Go 的 sync.Once 保证 f() 只执行一次，且 Do() 返回前已完成
```

#### 工厂方法 vs 抽象工厂

```go
// 场景: 广告平台的多种计费方式
package billing

type Bidder interface {
    Bid(event AdEvent) (float64, error)
}

type CPMBidder struct{}
func (b *CPMBidder) Bid(event AdEvent) (float64, error) {
    return float64(event.Impressions) * 0.001, nil
}

type CPCBidder struct{}
func (b *CPCBidder) Bid(event AdEvent) (float64, error) {
    return float64(event.Clicks) * 0.05, nil
}

type OCPMBidder struct{ TargetCPA float64 }
func (b *OCPMBidder) Bid(event AdEvent) (float64, error) {
    return event.ctr * event.cvr * b.TargetCPA * 1000, nil
}

// 工厂接口（Factory Method 模式）
type BidderFactory interface {
    CreateBidder() Bidder
}

type CPMBidderFactory struct{}
func (f *CPMBidderFactory) CreateBidder() Bidder {
    return &CPMBidder{}
}

// 使用:
type Campaign struct {
    bidder Bidder
}

func NewCampaign(factory BidderFactory) *Campaign {
    return &Campaign{
        bidder: factory.CreateBidder(),
    }
}

// 抽象工厂: 一组相关/依赖对象的家族（不限制类型）
type BiddingSystem interface {
    CreateBidder() Bidder
    CreatePacer() *BudgetPacer
    CreateTracker() *ConversionTracker
}

// Java 用多态实现抽象工厂，Go 用接口 + 工厂函数
// Go 更惯用的方式: 组合 + 接口，不使用复杂工厂模式
func NewCampaign(cfg CampaignConfig) *Campaign {
    // 直接用结构体字面量 + 默认值，替代工厂
    return &Campaign{
        Bidder: cfg.BidStrategy,       // 注入
        Pacer:  cfg.BudgetPacer,       // 注入
        Tracker: cfg.ConversionTracker, // 注入
    }
}
```

#### 建造者模式（Builder）

```go
// 场景: 构建复杂的广告查询条件
type AdQuery struct {
    UserID          string
    CampaignID      string
    StartTime       time.Time
    EndTime         time.Time
    TargetInterests []string
    MinCPM          float64
    MaxCPM          float64
    ExcludeBrands   []string
}

type AdQueryBuilder struct {
    query AdQuery
}

func NewAdQuery() *AdQueryBuilder {
    return &AdQueryBuilder{query: AdQuery{}}
}

func (b *AdQueryBuilder) UserID(uid string) *AdQueryBuilder {
    b.query.UserID = uid
    return b
}

func (b *AdQueryBuilder) CampaignID(cid string) *AdQueryBuilder {
    b.query.CampaignID = cid
    return b
}

func (b *AdQueryBuilder) TimeRange(start, end time.Time) *AdQueryBuilder {
    b.query.StartTime = start
    b.query.EndTime = end
    return b
}

func (b *AdQueryBuilder) TargetInterest(interest string) *AdQueryBuilder {
    b.query.TargetInterests = append(b.query.TargetInterests, interest)
    return b
}

func (b *AdQueryBuilder) CPMRange(min, max float64) *AdQueryBuilder {
    b.query.MinCPM = min
    b.query.MaxCPM = max
    return b
}

func (b *AdQueryBuilder) Build() (*AdQuery, error) {
    if (b.query.EndTime.IsZero() || b.query.StartTime.IsZero()) {
        return nil, errors.New("time range required")
    }
    result := b.query
    return &result, nil
}

// 使用:
query, err := NewAdQuery().
    UserID("user_123").
    TimeRange(start, end).
    TargetInterest("tech").
    TargetInterest("finance").
    CPMRange(1.0, 10.0).
    Build()
```

#### 原型模式（Prototype）— Go 的 clone

```go
// 场景: 广告计划模板克隆
type AdCampaign struct {
    ID             string
    Name           string
    Budget         *Budget
    TargetInterests []string
}

func (c *AdCampaign) Clone() *AdCampaign {
    clone := *c // 浅拷贝
    // 深拷贝可变字段
    clone.Budget = &Budget{
        Total:  c.Budget.Total,
        Daily:  c.Budget.Daily,
        Currency: c.Budget.Currency,
    }
    clone.TargetInterests = make([]string, len(c.TargetInterests))
    copy(clone.TargetInterests, c.TargetInterests)
    return &clone
}
```

---

### 1.2 结构型模式（Structural）

#### 适配器模式（Adapter）— 广告平台 API 统一

```go
// 场景: 统一 Google Ads、Meta、TikTok 的 API 调用
type AdPlatformAPI interface {
    CreateCampaign(ctx context.Context, req *CreateCampaignRequest) (*Campaign, error)
    Bid(ctx context.Context, req *BidRequest) (*BidResponse, error)
    GetReport(ctx context.Context, start, end time.Time) (*Report, error)
}

// Google Ads 适配器
type GoogleAdsAdapter struct {
    client *googleads.Client
}

func (a *GoogleAdsAdapter) CreateCampaign(ctx context.Context, req *CreateCampaignRequest) (*Campaign, error) {
    // 转换为 Google Ads API 格式
    gReq := googleAdsMapper.ToGoogleRequest(req)
    resp, err := a.client.CampaignService.CreateCampaign(ctx, gReq)
    if err != nil {
        return nil, err
    }
    return googleAdsMapper.ToInternalCampaign(resp), nil
}

func (a *GoogleAdsAdapter) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    oBiddingReq := dv360Mapper.ToOpenBidding(req)
    resp, err := a.client.OpenBidding.Bid(ctx, oBiddingReq)
    if err != nil {
        return nil, err
    }
    return dv360Mapper.ToBidResponse(resp), nil
}

// 使用:
var api AdPlatformAPI = &GoogleAdsAdapter{client: googleClient}
campaign, _ := api.CreateCampaign(ctx, req)
```

#### 装饰器模式（Decorator）— 请求链式增强

```go
// 场景: 广告请求的链式增强（认证→限流→缓存→日志）
type AdHandler interface {
    Handle(ctx context.Context, req *AdRequest) (*AdResponse, error)
}

type baseHandler struct{}

func (h *baseHandler) Handle(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    return adService.GetAds(req)
}

// 认证装饰器
type authDecorator struct {
    next AdHandler
}

func (d *authDecorator) Handle(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    token := req.Header["Authorization"]
    if token == "" {
        return nil, errors.New("auth required")
    }
    if !authService.Validate(token) {
        return nil, errors.New("invalid token")
    }
    req.UserID = authService.GetUserID(token)
    return d.next.Handle(ctx, req)
}

// 限流装饰器
type rateLimitDecorator struct {
    next      AdHandler
    limiter   *rate.Limiter
}

func (d *rateLimitDecorator) Handle(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    if !d.limiter.Allow() {
        return nil, errors.New("rate limit exceeded")
    }
    return d.next.Handle(ctx, req)
}

// 缓存装饰器
type cacheDecorator struct {
    next  AdHandler
    cache *sync.Map // map[string]*AdResponse
}

func (d *cacheDecorator) Handle(ctx context.Context, req *AdRequest) (*AdResponse, error) {
    key := generateCacheKey(req)
    if cached, ok := d.cache.Load(key); ok {
        return cached.(*AdResponse), nil
    }
    resp, err := d.next.Handle(ctx, req)
    if err == nil {
        d.cache.Store(key, resp)
    }
    return resp, err
}

// 组装:
var handler AdHandler = &baseHandler{}
handler = &cacheDecorator{next: handler, cache: &sync.Map{}}
handler = &rateLimitDecorator{next: handler, limiter: rate.NewLimiter(1000, 1000)}
handler = &authDecorator{next: handler}
// 顺序: auth → rateLimit → cache → base
```

#### 代理模式（Proxy）— 懒加载缓存

```go
type AdProvider interface {
    GetAds(campaignID string) ([]Ad, error)
}

type adProviderReal struct{}

func (p *adProviderReal) GetAds(campaignID string) ([]Ad, error) {
    return adRepository.findByCampaignID(campaignID)
}

type adProviderCacheProxy struct {
    real  AdProvider
    cache sync.Map
}

func (p *adProviderCacheProxy) GetAds(campaignID string) ([]Ad, error) {
    if cached, ok := p.cache.Load(campaignID); ok {
        return cached.([]Ad), nil
    }
    ads, err := p.real.GetAds(campaignID)
    if err == nil {
        p.cache.Store(campaignID, ads)
    }
    return ads, err
}
```

---

### 1.3 行为型模式（Behavioral）

#### 策略模式（Strategy）— 竞价策略

```go
// 场景: 不同竞价策略，运行时可切换
type BiddingStrategy interface {
    CalculateBid(ctr, cvr float64, targetCPA float64) float64
}

type FirstPriceStrategy struct{}

func (s *FirstPriceStrategy) CalculateBid(ctr, cvr, targetCPA float64) float64 {
    ecpm := ctr * cvr * 1000
    return ecpm // 出价 = eCPM
}

type BudgetPacingStrategy struct {
    pacer *BudgetPacer
}

func (s *BudgetPacingStrategy) CalculateBid(ctr, cvr, targetCPA float64) float64 {
    ecpm := ctr * cvr * 1000
    factor := s.pacer.GetAdjustFactor() // 根据预算消耗调整
    return ecpm * factor
}

// 使用:
var strategy BiddingStrategy = &BudgetPacingStrategy{pacer: pacing}
bid := strategy.CalculateBid(ctr, cvr, targetCPA)
```

#### 观察者模式（Observer）— 广告事件通知

```go
// 场景: 广告曝光/点击/转化事件，通知多个系统
type AdEvent struct {
    Type      EventType
    CampaignID string
    UserID    string
    Timestamp time.Time
}

type EventType string

const (
    IMPRESSION EventType = "impression"
    CLICK      EventType = "click"
    CONVERSION EventType = "conversion"
)

type AdEventListener interface {
    OnImpression(ctx context.Context, event AdEvent)
    OnClick(ctx context.Context, event AdEvent)
    OnConversion(ctx context.Context, event AdEvent)
}

type EventBus struct {
    listeners map[EventType][]AdEventListener
    mu        sync.RWMutex
}

func NewEventBus() *EventBus {
    return &EventBus{
        listeners: make(map[EventType][]AdEventListener),
    }
}

func (b *EventBus) Register(eventType EventType, listener AdEventListener) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.listeners[eventType] = append(b.listeners[eventType], listener)
}

func (b *EventBus) Emit(event AdEvent) {
    b.mu.RLock()
    listeners := b.listeners[event.Type]
    b.mu.RUnlock()
    
    for _, listener := range listeners {
        switch event.Type {
        case IMPRESSION:
            listener.OnImpression(context.Background(), event)
        case CLICK:
            listener.OnClick(context.Background(), event)
        case CONVERSION:
            listener.OnConversion(context.Background(), event)
        }
    }
}

// 监听器实现:
type AnalyticsListener struct { analytics AnalyticsService }
func (l *AnalyticsListener) OnImpression(ctx context.Context, event AdEvent) {
    l.analytics.TrackImpression(event)
}

type BudgetListener struct { budget BudgetService }
func (l *BudgetListener) OnConversion(ctx context.Context, event AdEvent) {
    l.budget.TrackConversion(event)
}

// 使用:
bus := NewEventBus()
bus.Register(CONVERSION, &BudgetListener{budget: budgetSvc})
bus.Register(IMPRESSION, &AnalyticsListener{analytics: analyticsSvc})
bus.Emit(AdEvent{Type: CONVERSION, CampaignID: "c1", UserID: "u1"})
// 同时通知 Budget 和 Analytics
```

#### 模板方法模式（Template Method）

```go
// 场景: 统一的竞价流程，不同子类可覆盖特定步骤
type BidProcessor interface {
    Process(ctx context.Context, ad Ad, user User, context Context) (*BidResult, error)
}

type BaseBidProcessor struct{}

func (p *BaseBidProcessor) Process(ctx context.Context, ad Ad, user User, context Context) (*BidResult, error) {
    // Step 1: 预筛选
    if !p.preFilter(ad, user, context) {
        return nil, errors.New("pre-filter failed")
    }
    // Step 2: 预测
    pctr := p.predictCTR(ad, user, context)
    pcvr := p.predictCVR(ad, user, context)
    // Step 3: 计算出价（由子类实现）
    bid := p.calculateBid(pctr, pcvr)
    // Step 4: 预算检查
    if !p.checkBudget(ad) {
        return nil, errors.New("budget exceeded")
    }
    // Step 5: 返回
    return &BidResult{AdID: ad.ID, Bid: bid, PCTR: pctr, PCVR: pcvr}, nil
}

func (p *BaseBidProcessor) preFilter(ad Ad, user User, context Context) bool {
    return ad.IsActive() && user.IsAllowed(ad)
}

func (p *BaseBidProcessor) predictCTR(ad Ad, user User, context Context) float64 {
    return ctrModel.Predict(ad, user, context)
}

func (p *BaseBidProcessor) predictCVR(ad Ad, user User, context Context) float64 {
    return cvrModel.Predict(ad, user, context)
}

func (p *BaseBidProcessor) checkBudget(ad Ad) bool {
    return budgetService.HasBudget(ad)
}

// oCPM 处理器（覆盖 calculateBid）:
type OCPMBidProcessor struct{ BaseBidProcessor; TargetCPA float64 }

func (p *OCPMBidProcessor) calculateBid(pctr, pcvr float64) float64 {
    return pctr * pcvr * p.TargetCPA * 1000 // oCPM 公式
}

// CPC 处理器（覆盖 calculateBid）:
type CPCBidProcessor struct{ BaseBidProcessor; TargetCPA float64 }

func (p *CPCBidProcessor) calculateBid(pctr, pcvr float64) float64 {
    return pcvr * p.TargetCPA // CPC 公式
}

// 使用:
var processor BidProcessor = &OCPMBidProcessor{TargetCPA: 10.0}
result, _ := processor.Process(ctx, ad, user, context)
```

---

## 2. DDD — Go 源码级实现

### 2.1 限界上下文（Bounded Context）

```
广告平台限界上下文:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   竞价上下文   │  │   投放上下文   │  │   报告上下文   │
│             │  │             │  │             │
│ BidRequest  │  │ Campaign    │  │ Report      │
│ BidResponse │  │ Delivery    │  │ Metrics     │
│ BidEngine   │  │ Budget      │  │ Analytics   │
│ Auction     │  │ Pacing      │  │ Dashboard   │
└─────────────┘  └─────────────┘  └─────────────┘
       │                │                │
       └────────────────┼────────────────┘
                        │ 共享内核
              ┌─────────────────────┐
              │   用户画像上下文      │
              │                     │
              │ UserProfile         │
              │ UserInterests       │
              │ BehaviorHistory     │
              └─────────────────────┘
              
// 上下文映射:
// - 发布/订阅: 竞价上下文 → 报告上下文（通过 Kafka 事件）
// - 防腐层: 广告平台 API 适配层（隔离外部 API 变更影响）
```

### 2.2 聚合根 + 值对象

```go
// 聚合根（Aggregate Root）
type Campaign struct {
    ID       string
    Name     string
    Budget   *Budget          // 值对象
    Schedule *Schedule        // 值对象
    Status   CampaignStatus
    AdGroups []*AdGroup       // 子聚合
    events   []DomainEvent    // 待发布事件
}

func NewCampaign(name string, budget *Budget, schedule *Schedule) *Campaign {
    if budget.Total < 0 || budget.Total > 1000000 {
        panic("invalid budget")
    }
    return &Campaign{
        ID:       uuid.New().String(),
        Name:     name,
        Budget:   budget,
        Schedule: schedule,
        Status:   StatusActive,
    }
}

// 不变性约束
func (c *Campaign) Pause() error {
    if c.Status != StatusActive {
        return fmt.Errorf("only active campaigns can be paused")
    }
    c.Status = StatusPaused
    c.events = append(c.events, &CampaignPausedEvent{
        CampaignID: c.ID, Budget: c.Budget,
    })
    return nil
}

func (c *Campaign) Resume() error {
    if c.Status != StatusPaused {
        return fmt.Errorf("only paused campaigns can be resumed")
    }
    c.Status = StatusActive
    c.events = append(c.events, &CampaignResumedEvent{
        CampaignID: c.ID,
    })
    return nil
}

func (c *Campaign) UncommittedEvents() []DomainEvent {
    return c.events
}

func (c *Campaign) ClearEvents() {
    c.events = nil
}

// 值对象（不可变）: 预算
type Budget struct {
    Total    float64
    Daily    float64
    Currency string
}

func (b *Budget) Clone() *Budget {
    return &Budget{
        Total:    b.Total,
        Daily:    b.Daily,
        Currency: b.Currency,
    }
}

func (b *Budget) Equal(o *Budget) bool {
    return b.Total == o.Total && b.Daily == o.Daily && b.Currency == o.Currency
}

// 值对象: 排期
type Schedule struct {
    Start        time.Time
    End          time.Time
    DailySchedule map[int]TimeRange // 星期 → 时间段
}

func (s *Schedule) IsCurrentTimeInRange() bool {
    now := time.Now()
    if now.Before(s.Start) || now.After(s.End) {
        return false
    }
    dayOfWeek := int(now.Weekday())
    if range, ok := s.DailySchedule[dayOfWeek]; ok {
        currentTime := Time(now.Hour(), now.Minute())
        return currentTime >= range.Start && currentTime <= range.End
    }
    return true
}
```

### 2.3 领域事件

```go
// 领域事件接口
type DomainEvent interface {
    OccurredOn() time.Time
}

type CampaignBudgetExceededEvent struct {
    CampaignID string
    Budget     float64
    Spent      float64
    occurredAt time.Time
}

func (e *CampaignBudgetExceededEvent) OccurredOn() time.Time {
    return e.occurredAt
}

// 事件发布器
type DomainEventPublisher interface {
    Publish(event DomainEvent) error
}

type eventPublisherImpl struct {
    bus       *EventBus
    pending   []DomainEvent
    mu        sync.Mutex
}

func (p *eventPublisherImpl) Publish(event DomainEvent) {
    p.mu.Lock()
    defer p.mu.Unlock()
    p.pending = append(p.pending, event)
}

func (p *eventPublisherImpl) FlushAndPublish() {
    p.mu.Lock()
    defer p.mu.Unlock()
    for _, event := range p.pending {
        p.bus.EmitAdEvent(event)
    }
    p.pending = nil
}
```

---

## 3. CQRS + Event Sourcing

### 3.1 CQRS 架构

```
┌─────────────┐        ┌─────────────┐
│   Command   │        │   Query     │
│   Model     │        │   Model     │
└──────┬──────┘        └──────┬──────┘
       │                      │
       ▼                      ▼
  ┌──────────┐         ┌──────────┐
  │ Event    │         │ Material-│
  │ Store    │         │  ized View│
  └──────────┘         └──────────┘
       │
       ▼
  ┌──────────┐
  │ Read DB  │
  └──────────┘

// 命令处理:
type CampaignCreateCommandHandler struct {
    repo   CampaignRepository
    pub    DomainEventPublisher
}

func (h *CampaignCreateCommandHandler) Handle(ctx context.Context, cmd CreateCampaignCmd) error {
    campaign := NewCampaign(cmd.Name, cmd.Budget, cmd.Schedule)
    campaign.Pause() // 先暂停，再激活
    h.repo.Save(campaign)
    for _, event := range campaign.UncommittedEvents() {
        h.pub.Publish(event)
    }
    campaign.ClearEvents()
    return nil
}

// 查询处理:
type CampaignReportQueryHandler struct {
    queryRepo CampaignReportRepository
}

func (h *CampaignReportQueryHandler) Handle(query CampaignReportQuery) (*Report, error) {
    return h.queryRepo.FindByCampaignID(query.CampaignID)
}
```

### 3.2 事件溯源（Event Sourcing）

```go
// 事件存储
type EventStore interface {
    Append(aggregateID string, events []DomainEvent) error
    Load(aggregateID string) ([]DomainEvent, error)
}

// 事件溯源仓库
type eventSourcingRepository struct {
    store EventStore
}

func (r *eventSourcingRepository) Load(id string) (*Campaign, error) {
    events, err := r.store.Load(id)
    if err != nil {
        return nil, err
    }
    campaign := &Campaign{ID: id}
    for _, event := range events {
        campaign.Apply(event)
    }
    return campaign, nil
}

func (r *eventSourcingRepository) Save(campaign *Campaign) error {
    events := campaign.UncommittedEvents()
    if len(events) > 0 {
        err := r.store.Append(campaign.ID, events)
        campaign.ClearEvents()
        return err
    }
    return nil
}

// 聚合根应用事件
func (c *Campaign) Apply(event DomainEvent) {
    switch e := event.(type) {
    case *CampaignCreatedEvent:
        c.Name = e.Name
        c.Status = StatusActive
    case *CampaignPausedEvent:
        c.Status = StatusPaused
    case *CampaignBudgetUpdatedEvent:
        c.Budget = e.NewBudget
    }
}
```

---

## 4. Saga 模式 — 分布式事务

### 4.1 Saga 编排（Orchestration）

```go
// 场景: 创建广告计划 + 分配预算 + 发送通知
type campaignCreationOrchestrator struct {
    campaignSvc   CampaignService
    budgetSvc     BudgetService
    notificationSvc NotificationService
}

type SagaStep struct {
    Name     string
    Payload  interface{}
    Compensate func(interface{}) error
}

func (o *campaignCreationOrchestrator) CreateCampaign(
    ctx context.Context, req *CreateCampaignRequest,
) (string, error) {
    steps := []SagaStep{
        {
            Name: "create_campaign",
            Payload: nil,
            Compensate: func(p interface{}) error {
                return o.campaignSvc.DeleteCampaign(ctx, p.(string))
            },
        },
        {
            Name: "allocate_budget",
            Payload: nil,
            Compensate: func(p interface{}) error {
                return o.budgetSvc.ReleaseBudget(ctx, p.(string))
            },
        },
        {
            Name: "send_notification",
            Payload: nil,
            Compensate: func(p interface{}) error {
                return nil // 通知无需补偿
            },
        },
    }
    
    var completed []interface{}
    
    // 正向执行
    for _, step := range steps {
        var payload interface{}
        var err error
        
        switch step.Name {
        case "create_campaign":
            cid, err := o.campaignSvc.CreateCampaign(ctx, req)
            payload = cid
            completed = append(completed, cid)
        case "allocate_budget":
            cid := completed[0].(string)
            err = o.budgetSvc.AllocateBudget(ctx, cid, req.Budget)
        case "send_notification":
            cid := completed[0].(string)
            err = o.notificationSvc.SendCampaignCreated(ctx, cid)
        }
        
        if err != nil {
            // 补偿: 反向执行
            for i := len(completed) - 1; i >= 0; i-- {
                steps[i].Compensate(completed[i])
            }
            return "", fmt.Errorf("saga failed at %s: %w", step.Name, err)
        }
    }
    
    return completed[0].(string), nil
}
```

---

## 5. 分布式协议深度

### 5.1 CAP 定理

```
CAP 定理: 一致性（Consistency）、可用性（Availability）、分区容错性（Partition Tolerance）
不可能同时满足三个，最多满足两个。

证明:
1. 网络分区 P 发生（节点 A 和 B 不能通信）
2. 节点 A 收到写请求:
   - 满足 C: 必须将写入传播到其他节点 → 需等待网络恢复
   - 但这违反 A: 节点 A 在等待期间不能响应
3. 结论: C + A + P 不能同时满足

实际选择:
1. CP: ZooKeeper、HBase、Redis Cluster（分区时拒绝服务）
2. AP: Cassandra、DynamoDB、Eureka（分区时返回旧数据）
3. CA: 单节点数据库（不适用分布式系统）
```

### 5.2 Raft 协议（Go 实现）

```go
// Raft 节点状态
type NodeState int

const (
    Follower NodeState = iota
    Candidate
    Leader
)

type RaftNode struct {
    state         NodeState
    currentTerm   int
    votedFor      string
    log           []LogEntry
    commitIndex   int
    lastApplied  int
    
    // Leader 状态
    nextIndex   map[string]int // follower → 下一个要发送的 index
    matchIndex  map[string]int // follower → 已复制的最高 index
    peers       []string
    stopChan    chan struct{}
}

func (r *RaftNode) startElection() {
    r.currentTerm++
    r.state = Candidate
    r.votedFor = r.selfID()
    
    votes := 1 // 投给自己
    
    for _, peer := range r.peers {
        r.sendRequestVote(peer, r.currentTerm, r.votedFor)
    }
}

func (r *RaftNode) becomeLeader() {
    r.state = Leader
    // 初始化 nextIndex 和 matchIndex
    for _, peer := range r.peers {
        r.nextIndex[peer] = len(r.log) + 1
        r.matchIndex[peer] = 0
    }
    go r.heartbeatLoop()
}

func (r *RaftNode) heartbeatLoop() {
    ticker := time.NewTicker(heartbeatInterval)
    defer ticker.Stop()
    for {
        select {
        case <-ticker.C:
            r.sendAppendEntriesAll()
        case <-r.stopChan:
            return
        }
    }
}

func (r *RaftNode) sendAppendEntriesAll() {
    for _, peer := range r.peers {
        prevLogIndex := r.nextIndex[peer] - 1
        prevLogTerm := r.log[prevLogIndex].Term
        entries := r.log[r.nextIndex[peer]:]
        
        r.sendAppendEntries(peer, r.currentTerm, r.selfID(),
            prevLogIndex, prevLogTerm, entries, r.commitIndex)
    }
}

// Raft 日志复制:
// 1. Client → Leader: WriteRequest(key, value)
// 2. Leader → append(log): 追加到本地日志
// 3. Leader → Followers: AppendEntries(logEntry)
// 4. Followers → Leader: AppendEntriesResponse(matchIndex)
// 5. Leader → majority: 多数确认 → commitIndex++
// 6. Leader → Client: WriteResponse
```

---

*本文档基于 Go 实现的设计模式、DDD、CQRS、Saga、Raft 源码整理*

