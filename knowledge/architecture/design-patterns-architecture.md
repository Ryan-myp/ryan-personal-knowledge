# 设计模式与系统架构深度解析

> 标签: `#设计模式` `#DDD` `#CQRS` `#EventSourcing` `#系统架构`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 23 种设计模式实战分类

### 1.1 创建型模式（关注对象创建）

#### 单例模式（Singleton）— 线程安全版

```go
// 双重检查锁定（Double-Checked Locking）
type Singleton struct{}

var instance *Singleton
var once sync.Once

func GetInstance() *Singleton {
    once.Do(func() {
        instance = &Singleton{}
    })
    return instance
}

// 更简洁的 Go 方式（package level 变量）
var defaultClient = &HTTPClient{timeout: 30 * time.Second}
// Go 的 init() 保证线程安全，无需额外同步
```

**适用场景**：数据库连接池、配置管理器、日志器
**不适用**：有状态的单例（并发冲突）

#### 工厂方法 vs 抽象工厂

```go
// 工厂方法：一个产品等级结构
type Shape interface {
    Draw()
}

type Circle struct{}
func (c Circle) Draw() { fmt.Println("Circle") }

type Factory interface {
    CreateShape() Shape
}

type CircleFactory struct{}
func (f CircleFactory) CreateShape() Shape { return Circle{} }

// 抽象工厂：多个产品等级结构
type Button interface {
    Render()
}
type TextField interface {
    Render()
}

type GUIFactory interface {
    CreateButton() Button
    CreateTextField() TextField
}

type MacOSFactory struct{}
func (f MacOSFactory) CreateButton() Button { return MacOSButton{} }
func (f MacOSFactory) CreateTextField() TextField { return MacOSTextField{} }

type WindowsFactory struct{}
func (f WindowsFactory) CreateButton() Button { return WindowsButton{} }
func (f WindowsFactory) CreateTextField() TextField { return WindowsTextField{} }
```

#### 建造者模式（Builder）— 复杂对象构造

```go
// 链式调用
type HTTPClient struct {
    BaseURL   string
    Timeout   time.Duration
    Header    map[string]string
    Transport http.RoundTripper
}

type HTTPClientBuilder struct {
    client HTTPClient
}

func NewHTTPClientBuilder() *HTTPClientBuilder {
    return &HTTPClientBuilder{
        client: HTTPClient{
            Timeout: 30 * time.Second,
            Header:  make(map[string]string),
        },
    }
}

func (b *HTTPClientBuilder) BaseURL(url string) *HTTPClientBuilder {
    b.client.BaseURL = url
    return b
}

func (b *HTTPClientBuilder) Timeout(d time.Duration) *HTTPClientBuilder {
    b.client.Timeout = d
    return b
}

func (b *HTTPClientBuilder) AddHeader(key, value string) *HTTPClientBuilder {
    b.client.Header[key] = value
    return b
}

func (b *HTTPClientBuilder) Build() *HTTPClient {
    return &b.client
}

// 使用:
client := NewHTTPClientBuilder().
    BaseURL("https://api.example.com").
    Timeout(10 * time.Second).
    AddHeader("Authorization", "Bearer xxx").
    Build()
```

### 1.2 结构型模式（关注类/对象组合）

#### 适配器模式（Adapter）

```go
// 旧接口 vs 新接口
type LegacyAPI interface {
    GetUserData(id int) (string, error)
}

type NewAPI interface {
    GetUser(userID string) (*User, error)
}

// 适配器: 将新接口适配为旧接口
type Adapter struct {
    newAPI NewAPI
}

func (a *Adapter) GetUserData(id int) (string, error) {
    user, err := a.newAPI.GetUser(strconv.Itoa(id))
    if err != nil {
        return "", err
    }
    return user.Name, nil
}
```

#### 装饰器模式（Decorator）— Go 的接口组合优势

```go
type Reader interface {
    Read(p []byte) (int, error)
}

// 基础 Reader
type FileReader struct {
    file *os.File
}

// 装饰器 1: 带缓冲
type BufferedReader struct {
    r Reader
    buf []byte
}
func (b *BufferedReader) Read(p []byte) (int, error) {
    // 先读入 buffer，再从 buffer 读取
    return bufio.NewReader(b.r).Read(p)
}

// 装饰器 2: 带缓存
type CachingReader struct {
    r       Reader
    cache   map[string][]byte
}
func (c *CachingReader) Read(p []byte) (int, error) {
    // 先查缓存
    // 缓存未命中 → 读取原始 reader → 写缓存
    return 0, nil
}

// 链式组合
r := &CachingReader{
    r: &BufferedReader{
        r: &FileReader{file: f},
    },
}
```

#### 代理模式（Proxy）— 远程代理/缓存代理

```go
type Image interface {
    Display()
}

type RealImage struct {
    filename string
}
func (r *RealImage) LoadFromDisk() {
    // 从网络/磁盘加载
}
func (r *RealImage) Display() {
    fmt.Printf("Displaying %s", r.filename)
}

// 代理: 延迟加载
type ProxyImage struct {
    image     *RealImage
    filename  string
}
func (p *ProxyImage) Display() {
    if p.image == nil {
        p.image = &RealImage{filename: p.filename}
        p.image.LoadFromDisk()  // 懒加载
    }
    p.image.Display()
}
```

### 1.3 行为型模式（关注对象间通信）

#### 策略模式（Strategy）— 广告出价策略

```go
type BidStrategy interface {
    CalculateBid(candidate *Candidate, context *Context) float64
}

// 固定出价
type FixedBidStrategy struct {
    price float64
}
func (f *FixedBidStrategy) CalculateBid(c *Candidate, ctx *Context) float64 {
    return f.price
}

// oCPX 出价
type OCPXBidStrategy struct {
    targetCostPerAction float64
    pCTR float64
    pCVR float64
}
func (o *OCPXBidStrategy) CalculateBid(c *Candidate, ctx *Context) float64 {
    return o.pCTR * o.pCVR * o.targetCostPerAction
}

// 动态出价（基于历史转化数据）
type DynamicBidStrategy struct {
    historicalConversionRate float64
    budget                   float64
}
func (d *DynamicBidStrategy) CalculateBid(c *Candidate, ctx *Context) float64 {
    // 基于实时流量和预算剩余动态调整
    return d.calcDynamicBid(ctx)
}

// 策略上下文: 支持运行时切换
type BidStrategyContext struct {
    strategy BidStrategy
}
func (c *BidStrategyContext) SetStrategy(s BidStrategy) {
    c.strategy = s
}
func (c *BidStrategyContext) ExecuteBid(cand *Candidate, ctx *Context) float64 {
    return c.strategy.CalculateBid(cand, ctx)
}
```

#### 观察者模式（Observer）— Event Bus

```go
type Event interface {
    Name() string
    Data() interface{}
}

type EventHandler func(Event) error

type EventBus struct {
    handlers map[string][]EventHandler
    mu       sync.RWMutex
}

func NewEventBus() *EventBus {
    return &EventBus{handlers: make(map[string][]EventHandler)}
}

func (eb *EventBus) Subscribe(eventType string, handler EventHandler) {
    eb.mu.Lock()
    defer eb.mu.Unlock()
    eb.handlers[eventType] = append(eb.handlers[eventType], handler)
}

func (eb *EventBus) Publish(event Event) error {
    eb.mu.RLock()
    handlers := eb.handlers[event.Name()]
    eb.mu.RUnlock()
    
    for _, h := range handlers {
        if err := h(event); err != nil {
            return err
        }
    }
    return nil
}

// 使用:
bus := NewEventBus()
bus.Subscribe("ad.impression", func(e Event) error {
    // 记录展示
    return nil
})
bus.Subscribe("ad.click", func(e Event) error {
    // 记录点击
    return nil
})
bus.Publish(&ImpressionEvent{AdID: 123})
```

#### 模板方法模式（Template Method）— 广告请求处理管线

```go
type AdPipeline interface {
    Execute(ctx *Context) (*AdResponse, error)
}

type BasePipeline struct{}

func (b *BasePipeline) Execute(ctx *Context) (*AdResponse, error) {
    // 1. 前置处理（所有管线共享）
    if err := b.validate(ctx); err != nil {
        return nil, err
    }
    
    // 2. 核心步骤（由子类实现）
    candidates, err := b.fetchCandidates(ctx)
    if err != nil {
        return nil, err
    }
    
    // 3. 排序 & 筛选
    ranked, err := b.rankAndFilter(ctx, candidates)
    if err != nil {
        return nil, err
    }
    
    // 4. 后置处理
    return b.postProcess(ctx, ranked)
}

// 子类实现具体管线
type BiddingPipeline struct{ BasePipeline }
func (b *BiddingPipeline) fetchCandidates(ctx *Context) ([]*AdCandidate, error) {
    // 竞价候选集获取
}
func (b *BiddingPipeline) rankAndFilter(ctx *Context, candidates []*AdCandidate) ([]*AdCandidate, error) {
    // eCPM 排序 + 频控过滤
}

type GuaranteePipeline struct{ BasePipeline }
func (g *GuaranteePipeline) fetchCandidates(ctx *Context) ([]*AdCandidate, error) {
    // 保量广告候选
}
```

---

## 2. DDD（领域驱动设计）

### 2.1 战略设计

```
限界上下文（Bounded Context）:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   广告系统    │    │   投放系统    │    │   结算系统    │
│              │    │              │    │              │
│ AdContext    │───▶│ CampaignCtx  │───▶│ BillingCtx   │
│              │    │              │    │              │
│ - Ad         │    │ - Plan       │    │ - Invoice    │
│ - Campaign   │    │ - Budget     │    │ - Settlement │
│ - Creative   │    │ - Schedule   │    │ - Report     │
└──────────────┘    └──────────────┘    └──────────────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                    共享内核（Shared Kernel）
                 广告ID / 用户ID / 时间戳
```

### 2.2 战术设计：聚合根 + 实体 + 值对象

```go
// 聚合根: Campaign（广告系列）
type Campaign struct {
    ID         CampaignID
    Name       string
    Budget     Budget
    Status     CampaignStatus
    Schedule   Schedule
    Bidding    BiddingStrategy
    targets    []Target
    creativeIDs []CreativeID
    updatedAt  time.Time
}

// 值对象: 不可变，用值比较
type Budget struct {
    Amount money.Money
    Type   BudgetType  // Daily/Total/Lifetime
}

type BiddingStrategy struct {
    Type       BidType  // oCPM/oCPC/CPC
    MaxBid     money.Money
    MinBid     money.Money
    Pacing     PacingStrategy
}

// 实体: 有唯一 ID
type Ad struct {
    ID          AdID
    CampaignID  CampaignID
    Status      AdStatus
    Impressions int64
    Clicks      int64
    Conversions int64
}

// 领域事件
type CampaignBudgetUpdated struct {
    CampaignID CampaignID
    OldBudget  Budget
    NewBudget  Budget
    Timestamp  time.Time
}

// 聚合内部方法: 保证不变量
func (c *Campaign) UpdateBudget(newBudget Budget) error {
    if newBudget.Amount <= 0 {
        return ErrInvalidBudget
    }
    if newBudget.Amount > c.Budget.Amount * 5 {
        return ErrBudgetTooLarge  // 不能超过原预算 5 倍
    }
    
    oldBudget := c.Budget
    c.Budget = newBudget
    c.updatedAt = time.Now()
    
    // 发布领域事件
    domainEvent := CampaignBudgetUpdated{
        CampaignID: c.ID,
        OldBudget:  oldBudget,
        NewBudget:  newBudget,
        Timestamp:  time.Now(),
    }
    return domainEvent.Publish()
}
```

### 2.3 应用层 + 领域层分离

```go
// 应用层: 编排业务流程
type CampaignService struct {
    campaignRepo  repository.CampaignRepository
    budgetRepo    repository.BudgetRepository
    eventPublisher EventPublisher
}

func (s *CampaignService) CreateCampaign(input CreateCampaignInput) (*Campaign, error) {
    // 1. 验证输入
    if err := input.Validate(); err != nil {
        return nil, err
    }
    
    // 2. 创建聚合根
    campaign := Campaign{
        ID:   GenerateID(),
        Name: input.Name,
        Budget: Budget{
            Amount: input.Budget,
            Type:   Daily,
        },
        Status: Draft,
    }
    
    // 3. 持久化
    if err := s.campaignRepo.Save(&campaign); err != nil {
        return nil, err
    }
    
    // 4. 发布事件
    s.eventPublisher.Publish(CampaignCreated{
        CampaignID: campaign.ID,
        Timestamp:  time.Now(),
    })
    
    return &campaign, nil
}
```

---

## 3. CQRS + Event Sourcing

### 3.1 CQRS（命令查询职责分离）

```
Command (写):    Query (读):
    │                  │
    ▼                  ▼
Write Model       Read Model
    │                  │
    ▼                  ▼
Command Handler   Query Handler
    │                  │
    ▼                  ▼
Domain Model      Projections
    │                  │
    ▼                  ▼
Event Store      Cache / Materialized View
```

```go
// 命令
type CreateCampaignCommand struct {
    UserID    string
    Name      string
    Budget    money.Money
    StartDate time.Time
}

// 查询
type GetCampaignQuery struct {
    CampaignID string
    UserID     string
}

// 投影（Projection）: 从事件流生成读模型
type CampaignProjection struct {
    ID         string
    Name       string
    Budget     money.Money
    Spent      money.Money
    Impressions int64
    Clicks     int64
}

// 事件处理: 更新投影
func (p *CampaignProjectionHandler) Handle(event CampaignBudgetUpdated) {
    projection := p.loadOrCreateProjection(event.CampaignID)
    projection.Budget = event.NewBudget
    p.saveProjection(projection)
}

func (p *CampaignProjectionHandler) Handle(event ImpressionRecorded) {
    projection := p.loadOrCreateProjection(event.CampaignID)
    projection.Impressions++
    p.saveProjection(projection)
}
```

### 3.2 Event Sourcing 实现

```go
// 事件接口
type DomainEvent interface {
    EventType() string
    AggregateID() string
    Timestamp() time.Time
}

// 具体事件
type CampaignCreated struct {
    AggregateID string
    UserID      string
    Name        string
    Budget      money.Money
    Timestamp   time.Time
}

type BudgetUpdated struct {
    AggregateID string
    OldBudget   money.Money
    NewBudget   money.Money
    Timestamp   time.Time
}

// 事件存储
type EventStore interface {
    Append(events []DomainEvent) error
    GetEvents(aggregateID string) ([]DomainEvent, error)
    GetSnapshot(aggregateID string) (interface{}, error)
}

// 聚合根实现
type EventSourcedAggregate struct {
    ID          string
    Version     int
    Events      []DomainEvent
    state       map[string]interface{}
}

func (a *EventSourcedAggregate) Apply(events []DomainEvent) {
    for _, e := range events {
        switch ev := e.(type) {
        case CampaignCreated:
            a.state["name"] = ev.Name
            a.state["budget"] = ev.Budget
        case BudgetUpdated:
            a.state["budget"] = ev.NewBudget
        }
    }
    a.Version += len(events)
}

func (a *EventSourcedAggregate) Save(events []DomainEvent) error {
    a.Events = append(a.Events, events...)
    a.Apply(events)
    return a.eventStore.Append(events)
}
```

### 3.3 Saga 模式（分布式事务）

```go
// 跨多个微服务的补偿事务
type CampaignCreationSaga struct {
    campaignSvc  CampaignService
    budgetSvc    BudgetService
    notifySvc    NotificationService
}

func (s *CampaignCreationSaga) Execute(cmd CreateCampaignCommand) error {
    // 1. 创建广告系列
    campaign, err := s.campaignSvc.CreateCampaign(cmd)
    if err != nil {
        return err
    }
    
    // 2. 冻结预算
    err = s.budgetSvc.FreezeBudget(campaign.UserID, cmd.Budget)
    if err != nil {
        // 补偿: 删除广告系列
        s.campaignSvc.Delete(campaign.ID)
        return err
    }
    
    // 3. 发送通知
    err = s.notifySvc.SendNotification(campaign.UserID, "campaign.created")
    if err != nil {
        // 补偿: 解冻预算
        s.budgetSvc.UnfreezeBudget(campaign.UserID, cmd.Budget)
        s.campaignSvc.Delete(campaign.ID)
        return err
    }
    
    return nil
}
```

---

## 4. 架构模式

### 4.1 微服务架构模式

```
┌─────────────────────────────────────────────────────────────┐
│                       API Gateway                            │
│                   (Kong / Nginx)                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ 广告服务     │ │ 投放服务     │ │ 结算服务     │
    │             │ │             │ │             │
    │ REST/gRPC   │ │ REST/gRPC   │ │ REST/gRPC   │
    │             │ │             │ │             │
    │ Event Bus   │ │ Event Bus   │ │ Event Bus   │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │ 广告数据库   │ │ 投放数据库   │ │ 结算数据库   │
    └─────────────┘ └─────────────┘ └─────────────┘

    关键原则:
    - 每个服务独立部署，独立数据库
    - 服务间通过事件/消息通信（最终一致性）
    - API Gateway 统一入口，鉴权、限流、路由
```

### 4.2 容量规划

```
公式:
  QPS = 日活用户 × 人均请求数 / (86400 × 平均活跃时段比例)
  
  单实例 QPS = 总 QPS / 实例数 × 安全系数(1.5~2.0)
  
  实例数 = ceil(总 QPS / 单实例QPS / 安全系数)

例如: 日活 100 万, 人均 100 请求, 活跃时段 8h
  QPS = 100万 × 100 / (8 × 3600) ≈ 3472 QPS
  假设单实例 500 QPS，安全系数 2.0:
  实例数 = ceil(3472 / 500 / 2.0) = 4 个实例
```

### 4.3 容灾架构

```
Level 1: 单机多副本（单机 → 多实例）
Level 2: 同城双活（A zone + B zone，同步复制）
Level 3: 异地多活（Region A + Region B，异步复制）

数据一致性:
  - 强一致: Raft/Paxos（适合用户数据）
  - 最终一致: 异步复制 + 冲突解决（适合日志数据）
  
故障切换:
  1. 健康检查 → 检测失败
  2. DNS/负载均衡切换 → 新实例
  3. 数据恢复 → 从副本同步
  4. 流量恢复 → 逐步恢复
```

---

*本文档整理自《设计模式》《实现领域驱动设计》《数据密集型应用系统设计》*
