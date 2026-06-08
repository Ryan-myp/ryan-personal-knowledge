# 设计模式与系统架构 — 源码级 23 种模式、DDD、CQRS、Saga、分布式协议

> 标签: `#设计模式` `#DDD` `#CQRS` `#EventSourcing` `#Saga` `#分布式协议` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 23 种设计模式 — 源码级实现

### 1.1 创建型模式（Creational）

#### 单例模式（Singleton）— 线程安全 + DCLP

```java
// 双重检查锁定 + volatile（Go 中的 sync.Once 类似）
public class Singleton {
    // volatile 保证禁止指令重排序
    // 否则可能出现: 分配内存 → 赋值为 null → 初始化对象（指令重排后顺序变了）
    private static volatile Singleton instance;
    
    private Singleton() {
        // 防御性编程: 防止反射破坏单例
        if (instance != null) {
            throw new RuntimeException("Use getInstance()");
        }
    }
    
    public static Singleton getInstance() {
        // 第一次检查: 避免不必要的同步开销
        if (instance == null) {
            synchronized (Singleton.class) {
                // 第二次检查: 避免重复创建
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}

// JVM 字节码分析（javap -c Singleton.class）:
// getstatic #2 // Field instance:LSingleton;
// ifnonnull L1
// monitorenter
// getstatic #2 // Field instance:LSingleton;
// ifnonnull L2
// new #3 // class Singleton
// dup
// invokespecial #4 // Method "<init>":()V
// putstatic #2 // Field instance:LSingleton;
// L2:
// monitorexit
// L1:
// getstatic #2 // Field instance:LSingleton;
// areturn
//
// 关键点: volatile 的 happens-before 保证
// - write 操作后不能重排到 read 之前
// - 确保 instance 在赋值后对象已经完全初始化
//
// 替代方案:
// 1. 静态内部类（推荐）:
//    class Singleton {
//        private static class Holder {
//            static final Singleton INSTANCE = new Singleton();
//        }
//        public static Singleton getInstance() {
//            return Holder.INSTANCE;
//        }
//    }
//    // 懒加载 + 线程安全（JVM 类加载机制保证）
//
// 2. Enum（最简洁）:
//    enum Singleton {
//        INSTANCE;
//    }
//    // 天然线程安全，防止反射攻击
//
// 3. sync.Once（Go）:
//    var once sync.Once
//    var instance *Singleton
//    func GetInstance() *Singleton {
//        once.Do(func() {
//            instance = &Singleton{}
//        })
//        return instance
//    }
```

#### 工厂方法模式（Factory Method）

```java
// 核心: 子类决定实例化哪个类
// 
// 场景: 广告平台的计费方式（CPM/CPC/oCPM）
interface AdBilling {
    double calculateCost(List<AdEvent> events);
}

class CpmBilling implements AdBilling {
    public double calculateCost(List<AdEvent> events) {
        // 按千次展示计费
        long impressions = events.stream()
            .filter(e -> e.type == IMPRESSION)
            .count();
        return impressions / 1000.0 * cpmRate;
    }
}

class CpcBilling implements AdBilling {
    public double calculateCost(List<AdEvent> events) {
        // 按点击计费
        long clicks = events.stream()
            .filter(e -> e.type == CLICK)
            .count();
        return clicks * cpcRate;
    }
}

class OcpmBilling implements AdBilling {
    public double calculateCost(List<AdEvent> events) {
        // 按目标 CPA 优化
        double targetCpa = 10.0;
        double actualCpa = calculateActualCpa(events);
        return targetCpa / actualCpa * impressions;
    }
}

// 工厂:
interface BillingFactory {
    AdBilling createBilling();
}

class CpmBillingFactory implements BillingFactory {
    public AdBilling createBilling() {
        return new CpmBilling();
    }
}

// 使用:
AdBilling billing = new CpmBillingFactory().createBilling();
double cost = billing.calculateCost(events);
```

#### 建造者模式（Builder）

```java
// 场景: 构建复杂的广告查询条件
public class AdQuery {
    private final String userId;
    private final String campaignId;
    private final Date startTime;
    private final Date endTime;
    private final List<String> targetInterests;
    private final double minCpm;
    private final double maxCpm;
    private final List<String> excludeBrands;
    
    // 私有构造 + 静态 Builder
    private AdQuery(Builder builder) {
        this.userId = builder.userId;
        this.campaignId = builder.campaignId;
        this.startTime = builder.startTime;
        this.endTime = builder.endTime;
        this.targetInterests = builder.targetInterests;
        this.minCpm = builder.minCpm;
        this.maxCpm = builder.maxCpm;
        this.excludeBrands = builder.excludeBrands;
    }
    
    public static class Builder {
        private String userId;
        private String campaignId;
        private Date startTime;
        private Date endTime;
        private List<String> targetInterests = new ArrayList<>();
        private double minCpm;
        private double maxCpm;
        private List<String> excludeBrands = new ArrayList<>();
        
        public Builder userId(String userId) {
            this.userId = userId;
            return this;  // 链式调用
        }
        
        public Builder campaignId(String campaignId) {
            this.campaignId = campaignId;
            return this;
        }
        
        public Builder timeRange(Date start, Date end) {
            this.startTime = start;
            this.endTime = end;
            return this;
        }
        
        public Builder targetInterest(String interest) {
            this.targetInterests.add(interest);
            return this;
        }
        
        public Builder cpmRange(double min, double max) {
            this.minCpm = min;
            this.maxCpm = max;
            return this;
        }
        
        public AdQuery build() {
            if (startTime == null || endTime == null) {
                throw new IllegalStateException("Time range required");
            }
            return new AdQuery(this);
        }
    }
    
    // 使用:
    AdQuery query = new AdQuery.Builder()
        .userId("user_123")
        .timeRange(start, end)
        .targetInterest("tech")
        .targetInterest("finance")
        .cpmRange(1.0, 10.0)
        .build();
}
```

#### 原型模式（Prototype）— 克隆

```java
// 场景: 广告计划模板克隆
public class AdCampaign implements Cloneable {
    private String id;
    private String name;
    private Budget budget;
    private List<String> targetInterests;
    private List<String> excludeBrands;
    
    // 深拷贝（避免共享引用）
    @Override
    public AdCampaign clone() {
        try {
            AdCampaign clone = (AdCampaign) super.clone();
            // 深拷贝可变字段
            clone.budget = (Budget) this.budget.clone();
            clone.targetInterests = new ArrayList<>(this.targetInterests);
            clone.excludeBrands = new ArrayList<>(this.excludeBrands);
            return clone;
        } catch (CloneNotSupportedException e) {
            throw new AssertionError();
        }
    }
    
    // 替代: 使用序列化克隆（更安全但慢）
    public AdCampaign deepClone() throws IOException, ClassNotFoundException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ObjectOutputStream oos = new ObjectOutputStream(baos);
        oos.writeObject(this);
        oos.close();
        
        ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        ObjectInputStream ois = new ObjectInputStream(bais);
        AdCampaign clone = (AdCampaign) ois.readObject();
        ois.close();
        return clone;
    }
}
```

---

### 1.2 结构型模式（Structural）

#### 适配器模式（Adapter）— API 网关适配

```java
// 场景: 统一不同广告平台 API 的调用
interface AdPlatformApi {
    Campaign createCampaign(CreateCampaignRequest request);
    List<Campaign> getCampaigns(String userId);
    BidResponse bid(BidRequest request);
    Report getReport(Date start, Date end);
}

class GoogleAdsAdapter implements AdPlatformApi {
    // 适配 Google Ads API (gRPC/REST)
    private GoogleAdsServiceClient client;
    
    public Campaign createCampaign(CreateCampaignRequest request) {
        // 转换为 Google Ads 格式
        com.google.ads.googleads.v14.resources.Campaign campaign =
            GoogleAdsCampaignMapper.toGoogleCampaign(request);
        
        // 调用 Google Ads API
        CampaignOperation operation = CampaignOperation.newBuilder()
            .setCreate(campaign)
            .build();
        
        MutateCampaignsResponse response = 
            client.campaignServiceClient().mutateCampaigns(requestCustomerId, operation);
        
        // 转换回内部格式
        return GoogleAdsCampaignMapper.toInternalCampaign(response);
    }
    
    public BidResponse bid(BidRequest request) {
        // 转换为 Google DV360 Open Bidding 格式
        Dv360OpenBiddingRequest openBiddingReq = 
            Dv360Mapper.toOpenBidding(request);
        
        // 调用 DV360 竞价
        Dv360OpenBiddingResponse response = 
            dv360BiddingClient.bid(openBiddingReq);
        
        return Dv360Mapper.toBidResponse(response);
    }
    
    public Report getReport(Date start, Date end) {
        // 转换报告查询条件
        GetReportRequest reportReq = 
            GoogleReportMapper.toReportRequest(start, end);
        
        // 调用报告 API
        Report report = client.reportServiceClient().getReport(reportReq);
        return GoogleReportMapper.toInternalReport(report);
    }
}

// 使用:
AdPlatformApi api = new GoogleAdsAdapter();
api.createCampaign(request);
api.bid(request);
api.getReport(start, end);
```

#### 装饰器模式（Decorator）— 请求增强

```java
// 场景: 广告请求的链式增强（认证、限流、缓存、日志）
public interface AdRequestHandler {
    AdResponse handle(AdRequest request);
}

public class AdRequestHandlerBase implements AdRequestHandler {
    public AdResponse handle(AdRequest request) {
        // 核心逻辑: 获取广告并返回
        return adService.getAds(request);
    }
}

// 装饰器基类
public abstract class AdRequestHandlerDecorator implements AdRequestHandler {
    protected AdRequestHandler delegate;
    
    public AdRequestHandlerDecorator(AdRequestHandler delegate) {
        this.delegate = delegate;
    }
    
    public final AdResponse handle(AdRequest request) {
        // 预处理
        AdRequest processedRequest = preprocess(request);
        
        // 执行核心
        AdResponse response = delegate.handle(processedRequest);
        
        // 后处理
        return postprocess(response);
    }
    
    protected AdRequest preprocess(AdRequest request) {
        return request;  // 默认无变化
    }
    
    protected AdResponse postprocess(AdResponse response) {
        return response;  // 默认无变化
    }
}

// 认证装饰器
public class AuthDecorator extends AdRequestHandlerDecorator {
    public AuthDecorator(AdRequestHandler delegate) {
        super(delegate);
    }
    
    protected AdRequest preprocess(AdRequest request) {
        // 验证 Token
        String token = request.getHeaders().get("Authorization");
        if (token == null || !authService.validate(token)) {
            throw new AuthenticationException("Invalid token");
        }
        
        // 解析用户 ID
        String userId = authService.getUserId(token);
        return new AdRequest(request.getCampaignId(), userId, request.getContext());
    }
}

// 限流装饰器
public class RateLimitDecorator extends AdRequestHandlerDecorator {
    private final RateLimiter rateLimiter;
    
    public RateLimitDecorator(AdRequestHandler delegate, RateLimiter rateLimiter) {
        super(delegate);
        this.rateLimiter = rateLimiter;
    }
    
    protected AdRequest preprocess(AdRequest request) {
        if (!rateLimiter.tryAcquire(request.getUserId())) {
            throw new RateLimitException("Rate limit exceeded");
        }
        return request;
    }
}

// 缓存装饰器
public class CacheDecorator extends AdRequestHandlerDecorator {
    private final Cache<String, AdResponse> cache;
    
    public CacheDecorator(AdRequestHandler delegate, Cache<String, AdResponse> cache) {
        super(delegate);
        this.cache = cache;
    }
    
    public AdResponse handle(AdRequest request) {
        String cacheKey = generateCacheKey(request);
        AdResponse cached = cache.getIfPresent(cacheKey);
        if (cached != null) {
            return cached;
        }
        
        AdResponse response = super.handle(request);
        cache.put(cacheKey, response);
        return response;
    }
}

// 组装:
AdRequestHandler handler = new CacheDecorator(
    new RateLimitDecorator(
        new AuthDecorator(
            new AdRequestHandlerBase())),
    cache);

AdResponse response = handler.handle(request);
// 顺序: Auth → RateLimit → Cache → Base
```

#### 代理模式（Proxy）— 懒加载广告缓存

```java
// 场景: 广告缓存代理
public interface AdProvider {
    List<Ad> getAds(String campaignId);
}

public class AdProviderReal implements AdProvider {
    public List<Ad> getAds(String campaignId) {
        // 从数据库/ES 查询
        return adRepository.findByCampaignId(campaignId);
    }
}

public class AdProviderCacheProxy implements AdProvider {
    private final AdProvider realProvider;
    private final Cache<String, List<Ad>> cache;
    
    public AdProviderCacheProxy(AdProvider realProvider, Cache<String, List<Ad>> cache) {
        this.realProvider = realProvider;
        this.cache = cache;
    }
    
    public List<Ad> getAds(String campaignId) {
        // 检查缓存
        List<Ad> cached = cache.getIfPresent(campaignId);
        if (cached != null) {
            return cached;
        }
        
        // 缓存未命中，查询真实提供者
        List<Ad> ads = realProvider.getAds(campaignId);
        cache.put(campaignId, ads);
        return ads;
    }
}
```

---

### 1.3 行为型模式（Behavioral）

#### 策略模式（Strategy）— 竞价策略

```java
// 场景: 不同竞价策略
interface BiddingStrategy {
    double calculateBid(Ad ad, User user, Context context);
}

class FirstPriceStrategy implements BiddingStrategy {
    public double calculateBid(Ad ad, User user, Context context) {
        double expectedEcpm = ad.pCTR * ad.pCVR * 1000;
        // 第一价格: 出价 = eCPM * confidence
        return expectedEcpm * ad.confidence;
    }
}

class SecondPriceStrategy implements BiddingStrategy {
    public double calculateBid(Ad ad, User user, Context context) {
        double expectedEcpm = ad.pCTR * ad.pCVR * 1000;
        // 第二价格: 出价 = eCPM（诚实出价）
        return expectedEcpm;
    }
}

class BudgetPacingStrategy implements BiddingStrategy {
    private final BudgetPacer pacer;
    
    public BudgetPacingStrategy(BudgetPacer pacer) {
        this.pacer = pacer;
    }
    
    public double calculateBid(Ad ad, User user, Context context) {
        double baseBid = ad.pCTR * ad.pCVR * 1000;
        // 根据预算消耗调整出价
        return baseBid * pacer.getAdjustFactor(ad);
    }
}

// 使用:
BiddingStrategy strategy = new BudgetPacingStrategy(pacer);
double bid = strategy.calculateBid(ad, user, context);
```

#### 观察者模式（Observer）— 事件驱动

```java
// 场景: 广告事件通知
interface AdEventListener {
    void onAdImpression(AdEvent event);
    void onAdClick(AdEvent event);
    void onAdConversion(AdEvent event);
}

class AdEventListenerRegistry {
    private final Map<Class<?>, List<AdEventListener>> listeners = new HashMap<>();
    
    public void register(Class<?> eventType, AdEventListener listener) {
        listeners.computeIfAbsent(eventType, k -> new ArrayList<>()).add(listener);
    }
    
    public void fireEvent(AdEvent event) {
        List<AdEventListener> listeners = listeners.get(event.getClass());
        if (listeners != null) {
            for (AdEventListener listener : listeners) {
                listener.onAdImpression(event);
            }
        }
    }
}

class AnalyticsListener implements AdEventListener {
    public void onAdImpression(AdEvent event) {
        analyticsService.track(event);
    }
    public void onAdClick(AdEvent event) {
        analyticsService.trackClick(event);
    }
    public void onAdConversion(AdEvent event) {
        analyticsService.trackConversion(event);
    }
}

class BudgetListener implements AdEventListener {
    public void onAdImpression(AdEvent event) {
        budgetService.trackImpression(event);
    }
    public void onAdConversion(AdEvent event) {
        budgetService.trackConversion(event);
    }
}

// 注册:
AdEventListenerRegistry registry = new AdEventListenerRegistry();
registry.register(AdImpressionEvent.class, new AnalyticsListener());
registry.register(AdImpressionEvent.class, new BudgetListener());

// 触发:
AdImpressionEvent event = new AdImpressionEvent(...);
registry.fireEvent(event);
// 同时通知 Analytics 和 Budget 监听器
```

#### 模板方法模式（Template Method）

```java
// 场景: 统一的竞价流程
abstract class BidProcessor {
    // 模板方法（final 防止被子类覆盖）
    public final BidResult processBid(Ad ad, User user, Context context) {
        // Step 1: 预筛选
        if (!preFilter(ad, user, context)) {
            return BidResult.rejected("Pre-filter failed");
        }
        
        // Step 2: 预测
        double pctr = predictCTR(ad, user, context);
        double pcvr = predictCVR(ad, user, context);
        
        // Step 3: 计算出价（由子类实现）
        double bid = calculateBid(pctr, pcvr);
        
        // Step 4: 预算检查
        if (!checkBudget(ad)) {
            return BidResult.rejected("Budget exceeded");
        }
        
        // Step 5: 记录日志
        logBid(ad, user, bid);
        
        // Step 6: 返回结果
        return BidResult.success(ad, bid, pctr, pcvr);
    }
    
    // 可被子类覆盖的步骤
    protected abstract double calculateBid(double pctr, double pcvr);
    
    // 默认实现
    protected boolean preFilter(Ad ad, User user, Context context) {
        return ad.isActive() && user.isAllowed(ad);
    }
    
    protected double predictCTR(Ad ad, User user, Context context) {
        return ctrModel.predict(ad, user, context);
    }
    
    protected double predictCVR(Ad ad, User user, Context context) {
        return cvrModel.predict(ad, user, context);
    }
    
    protected boolean checkBudget(Ad ad) {
        return budgetService.hasEnoughBudget(ad);
    }
    
    protected void logBid(Ad ad, User user, double bid) {
        logger.info("Bid: ad={}, bid={}", ad.getId(), bid);
    }
}

// 具体实现:
class OcpmBidProcessor extends BidProcessor {
    protected double calculateBid(double pctr, double pcvr) {
        // oCPM: eCPM = pCTR × pCVR × TargetCPA × 1000
        return pctr * pcvr * targetCPA * 1000;
    }
}

class CpcBidProcessor extends BidProcessor {
    protected double calculateBid(double pctr, double pcvr) {
        // CPC: 出价 = pCVR × TargetCPA
        return pcvr * targetCPA;
    }
}
```

---

## 2. DDD — 源码级实现

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
// - 发布/订阅: 竞价上下文 → 报告上下文（通过事件）
// - 共享内核: 用户画像上下文 ↔ 竞价上下文（共享模型）
// - 反腐化层: 广告平台 API 层（适配外部平台 API）
```

### 2.2 聚合根 + 值对象

```java
// 聚合根（Aggregate Root）
public class Campaign {
    private final String id;
    private final String name;
    private final Budget budget;  // 值对象
    private final List<String> targetInterests;
    private final Schedule schedule;  // 值对象
    private final List<AdGroup> adGroups;  // 子聚合
    private final CampaignStatus status;  // 值对象
    
    private Campaign(String id, String name, Budget budget,
                     List<String> targetInterests, Schedule schedule) {
        this.id = id;
        this.name = name;
        this.budget = budget;
        this.targetInterests = targetInterests;
        this.schedule = schedule;
        this.adGroups = new ArrayList<>();
        this.status = CampaignStatus.ACTIVE;
        
        // 不变性约束
        if (budget.getTotal() < 0) {
            throw new IllegalArgumentException("Budget must be >= 0");
        }
        if (budget.getTotal() > 1000000) {
            throw new IllegalArgumentException("Budget too large");
        }
    }
    
    public static Campaign create(String name, Budget budget, Schedule schedule) {
        return new Campaign(UUID.randomUUID().toString(), name, budget,
                           new ArrayList<>(), schedule);
    }
    
    // 行为方法（而非 getter/setter）
    public void addAdGroup(AdGroup adGroup) {
        adGroup.setCampaign(this);
        this.adGroups.add(adGroup);
    }
    
    public void pause() {
        if (this.status != CampaignStatus.ACTIVE) {
            throw new IllegalStateException("Can only pause active campaigns");
        }
        this.status = CampaignStatus.PAUSED;
        // 发布领域事件
        addDomainEvent(new CampaignPausedEvent(this.id, this.budget));
    }
    
    public void resume() {
        if (this.status != CampaignStatus.PAUSED) {
            throw new IllegalStateException("Can only resume paused campaigns");
        }
        this.status = CampaignStatus.ACTIVE;
        addDomainEvent(new CampaignResumedEvent(this.id));
    }
    
    // 值对象: 预算
    public Budget getBudget() { return budget; }
    
    public List<AdGroup> getAdGroups() { return Collections.unmodifiableList(adGroups); }
    
    public CampaignStatus getStatus() { return status; }
}

// 值对象（不可变）
public class Budget {
    private final double total;
    private final double daily;
    private final Currency currency;
    
    public Budget(double total, double daily, Currency currency) {
        if (total < 0 || daily < 0) {
            throw new IllegalArgumentException("Budget cannot be negative");
        }
        this.total = total;
        this.daily = daily;
        this.currency = currency;
    }
    
    // 不可变: 所有操作返回新 Budget
    public Budget withAdded(double amount) {
        return new Budget(total + amount, daily, currency);
    }
    
    public Budget withCurrency(Currency newCurrency) {
        return new Budget(total, daily, newCurrency);
    }
    
    // 值比较: 相等的值对象认为相等
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Budget budget = (Budget) o;
        return Double.compare(budget.total, total) == 0 &&
               Double.compare(budget.daily, daily) == 0 &&
               currency == budget.currency;
    }
    
    @Override
    public int hashCode() {
        return Objects.hash(total, daily, currency);
    }
}

// 值对象: 广告计划排期
public class Schedule {
    private final Date startDate;
    private final Date endDate;
    private final Map<Integer, TimeRange> dailySchedule;  // 星期 → 时间段
    
    public Schedule(Date start, Date end, Map<Integer, TimeRange> dailySchedule) {
        this.startDate = start;
        this.endDate = end;
        this.dailySchedule = dailySchedule;
    }
    
    public boolean isCurrentDateInRange() {
        Date now = new Date();
        return now.after(startDate) && now.before(endDate);
    }
    
    public boolean isCurrentTimeInRange() {
        Calendar cal = Calendar.getInstance();
        int dayOfWeek = cal.get(Calendar.DAY_OF_WEEK);
        TimeRange range = dailySchedule.get(dayOfWeek);
        if (range == null) return true;  // 无排期 = 全天
        Time now = Time.ofNow();
        return now >= range.getStart() && now <= range.getEnd();
    }
}
```

### 2.3 领域事件

```java
// 领域事件:
public interface DomainEvent {
    Instant occurredOn();
}

public class CampaignBudgetExceededEvent implements DomainEvent {
    private final String campaignId;
    private final double budget;
    private final double spent;
    private final Instant occurredOn;
    
    public CampaignBudgetExceededEvent(String campaignId, double budget, double spent) {
        this.campaignId = campaignId;
        this.budget = budget;
        this.spent = spent;
        this.occurredOn = Instant.now();
    }
    
    public String getCampaignId() { return campaignId; }
    public double getBudget() { return budget; }
    public double getSpent() { return spent; }
    public Instant getOccurredOn() { return occurredOn; }
}

// 事件发布器:
public interface DomainEventPublisher {
    void publish(DomainEvent event);
}

public class DomainEventPublisherImpl implements DomainEventPublisher {
    private final List<DomainEvent> pendingEvents = new ArrayList<>();
    private final EventBus eventBus;
    
    @Transactional
    public void publish(DomainEvent event) {
        pendingEvents.add(event);
        // 事务提交后发布
        eventBus.publish(event);
    }
    
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void publishPendingEvents() {
        for (DomainEvent event : pendingEvents) {
            eventBus.publish(event);
        }
        pendingEvents.clear();
    }
}

// 事件处理器:
public class BudgetExceededEventHandler implements ApplicationListener<CampaignBudgetExceededEvent> {
    public void onApplicationEvent(CampaignBudgetExceededEvent event) {
        // 1. 暂停预算
        campaignRepository.pause(event.getCampaignId());
        
        // 2. 通知用户
        notificationService.sendAlert(event.getCampaignId(), "Budget exceeded");
        
        // 3. 记录日志
        auditLogService.log("Campaign budget exceeded", event);
    }
}
```

---

## 3. CQRS + Event Sourcing

### 3.1 CQRS 架构

```
┌─────────────┐        ┌─────────────┐
│   Command   │        │   Query     │
│   Model     │        │   Model     │
│             │        │             │
│ Write Model │        │ Read Model  │
│             │        │             │
│ Campaign    │        │ Report      │
│ Budget      │        │ Analytics   │
│ Delivery    │        │ Dashboard   │
└──────┬──────┘        └──────┬──────┘
       │                      │
       │ CommandHandler       │ QueryHandler
       │                      │
       ▼                      ▼
  ┌──────────┐         ┌──────────┐
  │ Event    │         │ Material-│
  │ Store    │         │  ized View│
  │          │         │ (DB)     │
  └──────────┘         └──────────┘
       │
       │ Event Projection
       ▼
  ┌──────────┐
  │ Read DB  │
  │ (Report) │
  └──────────┘
  
// 命令处理:
class CampaignCreateCommandHandler {
    public void handle(CampaignCreateCommand command) {
        // 1. 创建聚合根
        Campaign campaign = Campaign.create(
            command.getName(),
            new Budget(command.getTotalBudget(), command.getDailyBudget(), command.getCurrency()),
            new Schedule(command.getStartDate(), command.getEndDate(), command.getDailySchedule())
        );
        
        // 2. 添加到仓库
        campaignRepository.save(campaign);
        
        // 3. 发布事件
        eventPublisher.publish(new CampaignCreatedEvent(
            campaign.getId(), command.getName(), command.getTotalBudget()
        ));
    }
}

// 查询处理:
class CampaignReportQueryHandler {
    public CampaignReport handle(CampaignReportQuery query) {
        // 从读模型（报告表）直接查询
        ReportReport report = reportRepository.findByCampaignId(query.getCampaignId());
        return mapToReport(report);
    }
}

// 投影（Projection）:
class CampaignCreatedProjection implements EventHandler<CampaignCreatedEvent> {
    public void handle(CampaignCreatedEvent event) {
        // 更新读模型
        reportRepository.save(new CampaignReport(
            event.getCampaignId(),
            event.getCampaignName(),
            0,  // 初始 spend = 0
            0,  // impressions = 0
            0   // clicks = 0
        ));
    }
}
```

### 3.2 事件溯源（Event Sourcing）

```java
// 事件溯源: 不存储状态，存储事件
// 
// 传统: 直接存 Campaign.status = ACTIVE
// 溯源: 存 CampaignCreated 事件，恢复时回放事件重建状态
//
// 事件存储:
interface EventStore {
    void append(String aggregateId, List<DomainEvent> events);
    List<DomainEvent> load(String aggregateId);
}

// 事件溯源仓库:
class EventSourcingCampaignRepository implements CampaignRepository {
    private final EventStore eventStore;
    private final Map<String, List<DomainEvent>> inMemoryStore = new ConcurrentHashMap<>();
    
    public Campaign load(String id) {
        // 1. 加载事件
        List<DomainEvent> events = eventStore.load(id);
        
        // 2. 创建空聚合
        Campaign campaign = Campaign.empty(id);
        
        // 3. 回放事件重建状态
        for (DomainEvent event : events) {
            campaign.apply(event);
        }
        
        return campaign;
    }
    
    public void save(Campaign campaign) {
        // 1. 收集未提交的事件
        List<DomainEvent> newEvents = campaign.getUncommittedEvents();
        
        // 2. 存储事件
        eventStore.append(campaign.getId(), newEvents);
        
        // 3. 清空未提交事件
        campaign.clearUncommittedEvents();
    }
}

// 聚合根应用事件:
public class Campaign {
    private List<DomainEvent> uncommittedEvents = new ArrayList<>();
    
    // 应用事件（恢复状态）
    void apply(CampaignCreatedEvent event) {
        this.id = event.getCampaignId();
        this.name = event.getCampaignName();
        this.status = CampaignStatus.ACTIVE;
    }
    
    void apply(CampaignPausedEvent event) {
        this.status = CampaignStatus.PAUSED;
    }
    
    void apply(CampaignBudgetUpdatedEvent event) {
        this.budget = event.getNewBudget();
    }
    
    // 记录事件
    void addDomainEvent(DomainEvent event) {
        uncommittedEvents.add(event);
    }
    
    List<DomainEvent> getUncommittedEvents() {
        return Collections.unmodifiableList(uncommittedEvents);
    }
    
    void clearUncommittedEvents() {
        uncommittedEvents.clear();
    }
}
```

---

## 4. Saga 模式 — 分布式事务

### 4.1 Saga 编排（Orchestration）

```java
// 场景: 创建广告计划 + 分配预算 + 发送通知
// 跨多个服务的分布式事务:
// 1. CampaignService: 创建广告计划
// 2. BudgetService: 分配预算
// 3. NotificationService: 发送通知
//
// Saga 编排器:
class CampaignCreationOrchestrator {
    private final CampaignService campaignService;
    private final BudgetService budgetService;
    private final NotificationService notificationService;
    private final SagaRepository sagaRepository;
    
    public SagaResult createCampaign(String userId, CampaignRequest request) {
        // 创建 Saga 实例
        SagaInstance saga = sagaRepository.create(
            "CampaignCreationSaga",
            userId
        );
        
        try {
            // Step 1: 创建广告计划
            String campaignId = campaignService.createCampaign(userId, request);
            saga.addStep("create_campaign", campaignId, null);
            
            // Step 2: 分配预算
            Budget budget = new Budget(request.getTotalBudget(), request.getDailyBudget());
            budgetService.allocateBudget(userId, budget);
            saga.addStep("allocate_budget", null, null);
            
            // Step 3: 发送通知
            notificationService.sendCampaignCreatedNotification(userId, campaignId);
            saga.addStep("send_notification", null, null);
            
            // 所有步骤完成
            saga.complete();
            return SagaResult.success(campaignId);
            
        } catch (Exception e) {
            // 补偿: 反向执行
            compensate(saga);
            saga.abort();
            throw new CampaignCreationFailedException(e);
        }
    }
    
    private void compensate(SagaInstance saga) {
        // 反向补偿: 从最后一步开始回滚
        int stepIndex = saga.getCompletedSteps().size() - 1;
        
        while (stepIndex >= 0) {
            Step completedStep = saga.getCompletedSteps().get(stepIndex);
            String compensationResult = null;
            
            try {
                switch (completedStep.getName()) {
                    case "send_notification":
                        compensationResult = notificationService.cancelCampaignNotification(
                            completedStep.getPayload());
                        break;
                        
                    case "allocate_budget":
                        compensationResult = budgetService.releaseBudget(
                            completedStep.getUserId(), completedStep.getPayload());
                        break;
                        
                    case "create_campaign":
                        compensationResult = campaignService.deleteCampaign(
                            completedStep.getPayload());
                        break;
                }
            } catch (Exception e) {
                // 补偿失败，记录人工干预
                saga.recordCompensationFailure(completedStep, e);
            }
            
            stepIndex--;
        }
    }
}
```

### 4.2 Saga 协调（Choreography）

```java
// 场景: 广告计划创建后，自动触发后续流程
// 
// 步骤:
// 1. CampaignService → 发布 CampaignCreatedEvent
// 2. BudgetService 监听 → 分配预算 → 发布 BudgetAllocatedEvent
// 3. NotificationService 监听 → 发送通知
// 4. AnalyticsService 监听 → 更新分析报告
//
// 事件驱动:
// CampaignCreatedEvent → BudgetAllocatedEvent → NotificationSentEvent
//                                                    ↓
//                                           AnalyticsUpdatedEvent

class BudgetAllocationListener {
    @KafkaListener(topics = "campaign-events", groupId = "budget-service")
    public void handle(CampaignCreatedEvent event) {
        try {
            // 分配预算
            Budget budget = new Budget(event.getTotalBudget(), event.getDailyBudget());
            budgetService.allocateBudget(event.getUserId(), budget);
            
            // 发布 BudgetAllocatedEvent
            eventPublisher.publish(new BudgetAllocatedEvent(
                event.getCampaignId(),
                event.getUserId(),
                budget.getTotal()
            ));
        } catch (Exception e) {
            // 预算分配失败 → 发布 CampaignBudgetFailedEvent
            eventPublisher.publish(new CampaignBudgetFailedEvent(
                event.getCampaignId(), event.getUserId(), e.getMessage()));
        }
    }
}
```

---

## 5. 分布式协议深度

### 5.1 CAP 定理证明

```
CAP 定理: 一致性（Consistency）、可用性（Availability）、分区容错性（Partition Tolerance）
不可能同时满足三个，最多满足两个。

证明:
假设一个分布式系统 C、A、P 都满足。
1. 发生网络分区 P（节点 A 和 B 不能通信）
2. 节点 A 收到写请求:
   - 满足 C: 必须将写入传播到其他节点 → 需要等待网络恢复
   - 但这违反 A: 节点 A 在等待期间不能响应其他请求
3. 结论: C + A + P 不能同时满足

实际选择:
1. CP: 一致性 + 分区容错性
   - 示例: ZooKeeper、HBase、Redis Cluster
   - 特点: 分区时拒绝服务（牺牲 A）
   
2. AP: 可用性 + 分区容错性
   - 示例: Cassandra、DynamoDB、Eureka
   - 特点: 分区时返回旧数据（牺牲 C）

3. CA: 一致性 + 可用性（无分区）
   - 示例: 单节点数据库
   - 特点: 不适用分布式系统
```

### 5.2 Raft 协议源码

```java
// Raft 共识协议实现:
//
// 节点状态:
enum NodeState {
    FOLLOWER,    // 默认状态，接收 Leader 心跳
    CANDIDATE,   // 竞选 Leader
    LEADER       // Leader 处理客户端请求
}

class RaftNode {
    private NodeState state = NodeState.FOLLOWER;
    private int currentTerm;
    private String votedFor;  // 投票给哪个节点
    private List<LogEntry> log = new ArrayList<>();
    private int commitIndex;
    private int lastApplied;
    
    // Leader 状态
    private Map<String, Integer> nextIndex = new HashMap<>();
    private Map<String, Integer> matchIndex = new HashMap<>();
    
    // 选举:
    void startElection() {
        currentTerm++;
        state = NodeState.CANDIDATE;
        votedFor = thisNodeId;
        
        // 投票给自���
        int votes = 1;
        
        // 向所有其他节点请求投票
        for (String peer : peers) {
            RequestVoteRequest request = new RequestVoteRequest(
                thisNodeId, currentTerm, votedFor, log.size(), log.lastEntry().getIndex()
            );
            rpcClient.send(peer, request, response -> {
                if (response.voted) {
                    votes++;
                    if (votes > peers.size() / 2) {
                        becomeLeader();
                    }
                }
            });
        }
    }
    
    // Leader 心跳:
    void heartbeat() {
        for (String peer : peers) {
            AppendEntriesRequest request = new AppendEntriesRequest(
                currentTerm, thisNodeId,
                commitIndex,
                getNextEntries(peer)
            );
            rpcClient.send(peer, request, response -> {
                if (response.success) {
                    matchIndex.put(peer, response.matchIndex);
                    nextIndex.put(peer, response.matchIndex + 1);
                } else {
                    // 心跳失败，减少 nextIndex
                    nextIndex.put(peer, Math.max(0, nextIndex.get(peer) - 1));
                }
            });
        }
        // 定期心跳
        scheduleHeartbeat();
    }
    
    // 追加日志:
    void appendEntry(LogEntry entry) {
        log.add(entry);
        
        // 复制到所有 follower
        for (String peer : peers) {
            AppendEntriesRequest request = new AppendEntriesRequest(
                currentTerm, thisNodeId,
                commitIndex,
                List.of(entry)
            );
            rpcClient.send(peer, request, response -> {
                if (response.matchIndex >= commitIndex) {
                    // 多数副本确认 → 提交
                    if (response.matchIndex > commitIndex) {
                        commitIndex = response.matchIndex;
                        applyCommitted();
                    }
                }
            });
        }
    }
}

// Raft 日志复制:
// 1. Client → Leader: WriteRequest(key, value)
// 2. Leader → log.append(): 追加到本地日志
// 3. Leader → Followers: AppendEntries(logEntry)
// 4. Followers → Leader: AppendEntriesResponse(success)
// 5. Leader → majority: 多数确认 → commitIndex++
// 6. Leader → Client: WriteResponse(success)
```

---

*本文档基于设计模式、DDD、CQRS、Saga、Raft 源码整理，覆盖 23 种模式 + 分布式架构*
