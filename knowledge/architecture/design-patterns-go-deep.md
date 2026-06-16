# 设计模式深度：Go 语言实战

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解设计模式

```
设计模式 = 建筑蓝图

单例模式 = 只有一个厨房
工厂模式 = 自动化工厂
观察者模式 = 新闻订阅
策略模式 = 支付方式选择
适配器模式 = 电源转换器
```

### Go 语言设计模式特点

```
Go 没有继承，但有组合
Go 没有泛型（1.18+ 有了），但有接口
Go 提倡简单，不追求模式数量
```

---

## 第二部分：创建型模式

### 2.1 单例模式

```go
// 饿汉式（Go 默认就是饿汉式）
var instance = &Singleton{}

type Singleton struct{}

func GetInstance() *Singleton {
    return instance
}

// 懒汉式（需要时创建）
type LazySingleton struct {
    mu   sync.Mutex
    inst *LazySingleton
}

func (ls *LazySingleton) GetInstance() *LazySingleton {
    if ls.inst == nil {
        ls.mu.Lock()
        defer ls.mu.Unlock()
        if ls.inst == nil {
            ls.inst = &LazySingleton{}
        }
    }
    return ls.inst
}

// sync.Once（推荐）
type OnceSingleton struct{}

var once sync.Once
var instance *OnceSingleton

func GetOnceSingleton() *OnceSingleton {
    once.Do(func() {
        instance = &OnceSingleton{}
    })
    return instance
}
```

### 2.2 工厂模式

```go
// 简单工厂
type AdCreative interface {
    Render() string
}

type BannerCreative struct{}
func (b *BannerCreative) Render() string { return "Banner" }

type VideoCreative struct{}
func (v *VideoCreative) Render() string { return "Video" }

type CreativeFactory struct{}

func (f *CreativeFactory) Create(typ string) AdCreative {
    switch typ {
    case "banner":
        return &BannerCreative{}
    case "video":
        return &VideoCreative{}
    default:
        return nil
    }
}

// 抽象工厂
type AdPlatform interface {
    CreateBanner() AdCreative
    CreateVideo() AdCreative
}

type GoogleFactory struct{}
func (g *GoogleFactory) CreateBanner() AdCreative { return &GoogleBanner{} }
func (g *GoogleFactory) CreateVideo() AdCreative { return &GoogleVideo{} }

type MetaFactory struct{}
func (m *MetaFactory) CreateBanner() AdCreative { return &MetaBanner{} }
func (m *MetaFactory) CreateVideo() AdCreative { return &MetaVideo{} }
```

### 2.3 建造者模式

```go
type BidRequestBuilder struct {
    request *BidRequest
}

func NewBidRequestBuilder() *BidRequestBuilder {
    return &BidRequestBuilder{
        request: &BidRequest{
            Imps:      make([]Impression, 0),
            User:      &User{},
            Device:    &Device{},
        },
    }
}

func (b *BidRequestBuilder) WithUserID(id string) *BidRequestBuilder {
    b.request.User.ID = id
    return b
}

func (b *BidRequestBuilder) WithDevice(d Device) *BidRequestBuilder {
    b.request.Device = &d
    return b
}

func (b *BidRequestBuilder) Build() *BidRequest {
    return b.request
}
```

---

## 第三部分：结构型模式

### 3.1 适配器模式

```go
// 目标接口
type AdClient interface {
    PlaceBid(request *BidRequest) (*BidResponse, error)
}

// 适配者接口（不兼容）
type LegacyClient interface {
    Send(data []byte) ([]byte, error)
}

// 适配器
type AdClientAdapter struct {
    legacy LegacyClient
}

func (a *AdClientAdapter) PlaceBid(req *BidRequest) (*BidResponse, error) {
    data, _ := json.Marshal(req)
    resp, err := a.legacy.Send(data)
    if err != nil {
        return nil, err
    }
    
    var bidResp BidResponse
    json.Unmarshal(resp, &bidResp)
    return &bidResp, nil
}
```

### 3.2 装饰器模式

```go
type BidEngine interface {
    Execute(req *BidRequest) (*BidResponse, error)
}

type BasicBidEngine struct{}
func (b *BasicBidEngine) Execute(req *BidRequest) (*BidResponse, error) {
    // 基本竞价逻辑
    return &BidResponse{}, nil
}

// 装饰器
type LoggingDecorator struct {
    engine BidEngine
}

func (l *LoggingDecorator) Execute(req *BidRequest) (*BidResponse, error) {
    log.Printf("Bidding for user %s", req.UserID)
    resp, err := l.engine.Execute(req)
    log.Printf("Bid result: %+v", resp)
    return resp, err
}

type RateLimitDecorator struct {
    engine   BidEngine
    limiter  *rate.Limiter
}

func (r *RateLimitDecorator) Execute(req *BidRequest) (*BidResponse, error) {
    if !r.limiter.Allow() {
        return nil, fmt.Errorf("rate limited")
    }
    return r.engine.Execute(req)
}
```

### 3.3 代理模式

```go
type AdServer interface {
    ServeBid(req *BidRequest) (*BidResponse, error)
}

type RealAdServer struct{}
func (r *RealAdServer) ServeBid(req *BidRequest) (*BidResponse, error) {
    // 真实逻辑
    return &BidResponse{}, nil
}

// 缓存代理
type CacheProxy struct {
    real    *RealAdServer
    cache   *Cache
}

func (c *CacheProxy) ServeBid(req *BidRequest) (*BidResponse, error) {
    key := req.Key()
    
    if resp, ok := c.cache.Get(key); ok {
        return resp, nil
    }
    
    resp, err := c.real.ServeBid(req)
    if err != nil {
        return nil, err
    }
    
    c.cache.Set(key, resp)
    return resp, nil
}
```

---

## 第四部分：行为型模式

### 4.1 策略模式

```go
type PricingStrategy interface {
    Calculate(basePrice float64) float64
}

type CPMPricing struct{}
func (c *CPMPricing) Calculate(basePrice float64) float64 {
    return basePrice
}

type CPCPricing struct{}
func (c *CPCPricing) Calculate(basePrice float64) float64 {
    return basePrice * 0.8 // CPC 折扣
}

type OCMPricing struct{}
func (o *OCMPricing) Calculate(basePrice float64) float64 {
    return basePrice * 1.2 // oCPM 溢价
}

type Bidder struct {
    strategy PricingStrategy
}

func (b *Bidder) Bid(basePrice float64) float64 {
    return b.strategy.Calculate(basePrice)
}
```

### 4.2 观察者模式

```go
type Observer interface {
    Update(event Event)
}

type Subject struct {
    observers []Observer
}

func (s *Subject) Attach(o Observer) {
    s.observers = append(s.observers, o)
}

func (s *Subject) Notify(event Event) {
    for _, o := range s.observers {
        o.Update(event)
    }
}

// 使用示例
type BidEngine struct {
    subject *Subject
}

func (b *BidEngine) Execute(req *BidRequest) (*BidResponse, error) {
    resp, err := b.doBid(req)
    
    // 通知所有观察者
    b.subject.Notify(Event{
        Type: "bid_completed",
        Data: resp,
    })
    
    return resp, err
}
```

### 4.3 责任链模式

```go
type Middleware interface {
    Next() Middleware
    Handle(req *Request) (*Response, error)
}

type AuthMiddleware struct {
    next Middleware
}

func (a *AuthMiddleware) Next() Middleware { return a.next }
func (a *AuthMiddleware) Handle(req *Request) (*Response, error) {
    // 验证身份
    if !a.verifyAuth(req) {
        return nil, fmt.Errorf("unauthorized")
    }
    return a.next.Handle(req)
}

type RateLimitMiddleware struct {
    next Middleware
}

func (r *RateLimitMiddleware) Next() Middleware { return r.next }
func (r *RateLimitMiddleware) Handle(req *Request) (*Response, error) {
    // 限流
    if !r.allow(req) {
        return nil, fmt.Errorf("rate limited")
    }
    return r.next.Handle(req)
}
```

---

## 第五部分：生产排障案例

### 5.1 单例模式问题

```
现象：竞态条件导致双重初始化

排查：
1. 检查是否用了 sync.Once
2. 检查双重检查锁定

根因：懒汉式没有加锁

解决方案：
1. 使用 sync.Once
2. 使用饿汉式
```

### 5.2 观察者模式问题

```
现象：内存泄漏

排查：
1. 检查是否注册了观察者
2. 检查是否注销了观察者

根因：观察者没有被移除

解决方案：
1. 使用 weak reference
2. 显式注销
```

---

## 第六部分：自测题

### 问题 1
Go 中如何实现单例模式？

<details>
<summary>查看答案</summary>

1. **饿汉式**：包级别变量
2. **懒汉式**：双重检查锁定
3. **sync.Once**：推荐方式
4. **注意事项**：并发安全
5. **Go 实现**：OnceSingleton

</details>

### 问题 2
策略模式和工厂模式的区别？

<details>
<summary>查看答案</summary>

1. **策略**：运行时切换算法
2. **工厂**：创建对象
3. **策略**：关注行为
4. **工厂**：关注创建
5. **Go 实现**：PricingStrategy

</details>

### 问题 3
装饰器模式的优势？

<details>
<summary>查看答案</summary>

1. **动态添加**：运行时添加功能
2. **组合优于继承**
3. **透明**：对客户端透明
4. **可叠加**：多个装饰器
5. **Go 实现**：LoggingDecorator

</details>

---

*本文档基于设计模式原理整理。*