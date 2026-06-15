# 广告平台实战：流量分配/频次控制/创意管理

> 流量调度策略/频次控制算法/创意A/B测试/广告位优化/实时优化

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台核心挑战

```
流量分配：如何将广告位分配给最合适的广告？
频次控制：如何避免用户对同一广告过度曝光？
创意管理：如何管理成千上万条广告创意？
A/B 测试：如何科学地比较不同策略的效果？
```

---

## 第二部分：流量分配策略

### 2.1 流量调度架构

```
用户请求 → 流量分发层 → 竞价层 → 广告选择 → 创意返回
              ↓
         策略引擎（权重/优先级/预算）
```

### 2.2 Go 实现流量分配

```go
package traffic

import (
    "context"
    "math/rand"
    "sync"
)

// TrafficAllocator 流量分配器
type TrafficAllocator struct {
    mu          sync.RWMutex
    strategies  map[string]*Strategy
    defaultStrat string
}

type Strategy struct {
    Name      string
    Weight    float64    // 权重 0-1
    Pools     []Pool
    Enabled   bool
}

type Pool struct {
    Name     string
    Ads      []*Ad
    Priority int
}

type Ad struct {
    ID          string
    CampaignID  string
    BidPrice    float64
    CTR         float64
    CVR         float64
    Status      string // active, paused, ended
}

// Allocate 分配流量
func (ta *TrafficAllocator) Allocate(ctx context.Context, req *TrafficRequest) (*Ad, error) {
    ta.mu.RLock()
    defer ta.mu.RUnlock()
    
    // 1. 选择策略
    strategy := ta.selectStrategy(req)
    if strategy == nil || !strategy.Enabled {
        return nil, ErrNoStrategy
    }
    
    // 2. 按权重分配流量
    pool := ta.selectPool(strategy, req)
    if pool == nil {
        return nil, ErrNoPool
    }
    
    // 3. 从池中选取广告
    ad := ta.selectAd(pool, req)
    if ad == nil {
        return nil, ErrNoAd
    }
    
    return ad, nil
}

func (ta *TrafficAllocator) selectStrategy(req *TrafficRequest) *Strategy {
    // 根据请求特征选择策略
    // 例如：按地区、按设备类型、按应用类型
    
    if req.Region == "us" {
        return ta.strategies["us_strategy"]
    }
    if req.DeviceType == "mobile" {
        return ta.strategies["mobile_strategy"]
    }
    
    return ta.strategies[ta.defaultStrat]
}

func (ta *TrafficAllocator) selectPool(strategy *Strategy, req *TrafficRequest) *Pool {
    // 加权随机选择池
    totalWeight := 0.0
    for _, pool := range strategy.Pools {
        totalWeight += float64(pool.Priority)
    }
    
    r := rand.Float64() * totalWeight
    cumulative := 0.0
    
    for _, pool := range strategy.Pools {
        cumulative += float64(pool.Priority)
        if r <= cumulative {
            return &pool
        }
    }
    
    return &strategy.Pools[0]
}

func (ta *TrafficAllocator) selectAd(pool *Pool, req *TrafficRequest) *Ad {
    // 按 eCPM 排序选择
    sort.Slice(pool.Ads, func(i, j int) bool {
        eCPMi := pool.Ads[i].CTR * pool.Ads[i].CVR * pool.Ads[i].BidPrice
        eCPMj := pool.Ads[j].CTR * pool.Ads[j].CVR * pool.Ads[j].BidPrice
        return eCPMi > eCPMj
    })
    
    // 返回最高 eCPM 的广告
    if len(pool.Ads) > 0 {
        return pool.Ads[0]
    }
    return nil
}
```

### 2.3 多臂老虎机算法

```go
// MultiArmedBandit 多臂老虎机
type MultiArmedBandit struct {
    arms    []Arm
    rewards map[string][]float64
}

type Arm struct {
    ID   string
    Name string
}

func (mab *MultiArmedBandit) SelectArm(epsilon float64) string {
    // ε-greedy 算法
    if rand.Float64() < epsilon {
        // 探索：随机选择
        idx := rand.Intn(len(mab.arms))
        return mab.arms[idx].ID
    }
    
    // 利用：选择期望回报最高的臂
    bestArm := ""
    bestReward := -1.0
    
    for _, arm := range mab.arms {
        avgReward := mab.averageReward(arm.ID)
        if avgReward > bestReward {
            bestReward = avgReward
            bestArm = arm.ID
        }
    }
    
    return bestArm
}

func (mab *MultiArmedBandit) UpdateReward(armID string, reward float64) {
    mab.rewards[armID] = append(mab.rewards[armID], reward)
}

func (mab *MultiArmedBandit) averageReward(armID string) float64 {
    rewards := mab.rewards[armID]
    if len(rewards) == 0 {
        return 0
    }
    
    sum := 0.0
    for _, r := range rewards {
        sum += r
    }
    
    return sum / float64(len(rewards))
}

// UCB1 算法
func (mab *MultiArmedBandit) SelectArmUCB(totalPulls int) string {
    bestArm := ""
    bestUCB := -1.0
    
    for _, arm := range mab.arms {
        n := len(mab.rewards[arm.ID])
        if n == 0 {
            return arm.ID // 未尝试过的臂优先
        }
        
        avgReward := mab.averageReward(arm.ID)
        exploration := math.Sqrt(2*math.Log(float64(totalPulls))/float64(n))
        ucb := avgReward + exploration
        
        if ucb > bestUCB {
            bestUCB = ucb
            bestArm = arm.ID
        }
    }
    
    return bestArm
}
```

---

## 第三部分：频次控制

### 3.1 频次控制引擎

```go
package freqcap

import (
    "context"
    "time"
)

type FrequencyController struct {
    redis *redis.Client
}

type FreqRule struct {
    UserID     string
    AdID       string
    MaxImpressions int // 最大展示次数
    Window     time.Duration // 时间窗口
}

func (fc *FrequencyController) Check(ctx context.Context, rule FreqRule) (bool, int, error) {
    key := fmt.Sprintf("freq:%s:%s:%d", rule.UserID, rule.AdID, rule.Window)
    
    // 使用滑动窗口
    now := time.Now()
    windowStart := now.Add(-rule.Window)
    
    // 1. 清理过期记录
    fc.redis.ZRemRangeByScore(ctx, key, "0", fmt.Sprintf("%d", windowStart.UnixMilli()))
    
    // 2. 获取当前次数
    count, err := fc.redis.ZCard(ctx, key).Result()
    if err != nil {
        return false, 0, err
    }
    
    // 3. 检查是否超限
    if int(count) >= rule.MaxImpressions {
        return false, int(count), nil
    }
    
    // 4. 记录本次展示
    fc.redis.ZAdd(ctx, key, redis.Z{
        Score:  float64(now.UnixMilli()),
        Member: fmt.Sprintf("%d:%d", now.UnixMilli(), rand.Intn(10000)),
    })
    
    // 5. 设置过期时间
    fc.redis.Expire(ctx, key, rule.Window+time.Hour)
    
    return true, int(count) + 1, nil
}

// 批量频次控制
func (fc *FrequencyController) BatchCheck(ctx context.Context, rules []FreqRule) ([]bool, error) {
    results := make([]bool, len(rules))
    
    for i, rule := range rules {
        allowed, _, err := fc.Check(ctx, rule)
        if err != nil {
            return nil, err
        }
        results[i] = allowed
    }
    
    return results, nil
}
```

---

## 第四部分：创意管理

### 4.1 创意素材管理

```go
type CreativeManager struct {
    cache *lru.Cache
    store *CreativeStore
}

type Creative struct {
    ID          string
    CampaignID  string
    Type        string // banner, video, native
    HTML        string
    ImageURL    string
    VideoURL    string
    Headline    string
    Description string
    CTA         string
    Width       int
    Height      int
    Targeting   Targeting
}

type Targeting struct {
    AgeRange    [2]int    // [min, max]
    Genders     []string  // ["M", "F"]
    Locations   []string  // ["US", "CN"]
    Interests   []string  // ["sports", "tech"]
}

func (cm *CreativeManager) GetCreative(creativeID string) (*Creative, error) {
    // 1. 检查缓存
    if creative, ok := cm.cache.Get(creativeID); ok {
        return creative.(*Creative), nil
    }
    
    // 2. 查询数据库
    creative, err := cm.store.GetByID(creativeID)
    if err != nil {
        return nil, err
    }
    
    // 3. 缓存结果
    cm.cache.Add(creativeID, creative)
    
    return creative, nil
}

// 创意 A/B 测试
type CreativeABTest struct {
    testID     string
    variations []Creative
    weights    []float64
    metrics    map[string]*Metrics
}

type Metrics struct {
    Impressions int
    Clicks      int
    Conversions int
}

func (ab *CreativeABTest) AllocateTraffic() string {
    // 按权重分配流量
    totalWeight := 0.0
    for _, w := range ab.weights {
        totalWeight += w
    }
    
    r := rand.Float64() * totalWeight
    cumulative := 0.0
    
    for i, w := range ab.weights {
        cumulative += w
        if r <= cumulative {
            return ab.variations[i].ID
        }
    }
    
    return ab.variations[0].ID
}

func (ab *CreativeABTest) RecordMetric(creativeID string, metric string) {
    m := ab.metrics[creativeID]
    if m == nil {
        m = &Metrics{}
        ab.metrics[creativeID] = m
    }
    
    switch metric {
    case "impression":
        m.Impressions++
    case "click":
        m.Clicks++
    case "conversion":
        m.Conversions++
    }
}

func (ab *CreativeABTest) GetWinner() string {
    bestCreative := ""
    bestCTR := 0.0
    
    for id, m := range ab.metrics {
        if m.Impressions == 0 {
            continue
        }
        ctr := float64(m.Clicks) / float64(m.Impressions)
        if ctr > bestCTR {
            bestCTR = ctr
            bestCreative = id
        }
    }
    
    return bestCreative
}
```

---

## 第五部分：自测题

### 问题 1
流量分配策略有哪些？

<details>
<summary>查看答案</summary>

1. **轮询**：均匀分配
2. **加权随机**：按权重分配
3. **eCPM 优先**：选择最高 eCPM
4. **多臂老虎机**：探索 + 利用
5. **Go 实现**：TrafficAllocator

</details>

### 问题 2
频次控制为什么用 Redis ZSet？

<details>
<summary>查看答案</summary>

1. **有序集合**：按时间戳排序
2. **范围查询**：ZREMRANGEBYSCORE 清理过期
3. **原子操作**：ZADD + ZCARD 原子性
4. **滑动窗口**：精确控制时间窗口
5. **Go 实现**：redis.Z

</details>

### 问题 3
A/B 测试如何确定显著性？

<details>
<summary>查看答案</summary>

1. **假设检验**：H0: 两组无差异
2. **P 值**：< 0.05 认为显著
3. **置信区间**：95% 置信区间
4. **样本量**：需要足够的样本
5. **Go 实现**：统计检验

</details>

---

*本文档基于广告平台实战整理。*