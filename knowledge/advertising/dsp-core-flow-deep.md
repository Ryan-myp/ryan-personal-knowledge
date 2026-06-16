# DSP 核心流程深度：从用户请求到广告展示的完整链路

> 真实生产级代码 + 频次控制 + 预算控制 + 广告筛选 + 性价比排序

---

## 第一部分：DSP 核心问题到底是什么？

### 你的问题，我翻译一下

```
用户打开 App → 产生一个广告请求
DSP 收到请求后需要回答：
1. 哪些广告适合这个用户？（广告筛选/定向）
2. 这些广告用户会不会看腻了？（频次控制）
3. 这些广告预算够不够？（预算控制）
4. 哪个广告的性价比最高？（eCPM 排序）
5. 怎么选才能最大化收益？（出价策略）
```

### 核心挑战

```
时间预算：整个流程必须在 50ms 内完成
数据规模：可能有 100 万个广告候选
实时性：用户画像、频次、预算都要实时查询
准确性：不能超预算、不能超频次
```

---

## 第二部分：完整架构

### 2.1 核心流程图

```
                    ┌─────────────────────────────────────┐
                    │         Bid Request (50ms)          │
                    │  user_id=123, ad_slot=banner, geo=CN│
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 1: 广告筛选 (Targeting)      │
                    │  - 用户定向：年龄/性别/兴趣          │
                    │  - 广告定向：地域/时间/设备          │
                    │  - 返回候选广告集（~1000 个）        │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 2: 频次控制 (Frequency Cap)  │
                    │  - 用户-广告对：今天看过几次？        │
                    │  - 用户-广告主对：本周看过几次？      │
                    │  - 过滤掉超频次的广告               │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 3: 预算控制 (Budget Cap)     │
                    │  - 广告主今日预算剩多少？            │
                    │  - 今日已消耗多少？                  │
                    │  - 过滤掉预算不足的广告              │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 4: CTR/CVR 预估              │
                    │  - 用户×广告的 CTR 是多少？          │
                    │  - 用户×广告的 CVR 是多少？          │
                    │  - 返回预估结果（~100 个）           │
                    └──────────────┬──────────────────────┐
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 5: 出价计算 (Bidding)        │
                    │  - 每个广告的出价是多少？            │
                    │  - oCPM：CTR × CVR × targetCPA      │
                    │  - 返回出价（~100 个）               │
                    └──────────────┬──────────────────────┐
                                   │
                    ┌──────────────▼──────────────────────┐
                    │    Step 6: 排序 & 选择               │
                    │  - 按 eCPM 排序                      │
                    │  - 选最高的那个                      │
                    │  - 返回广告                           │
                    └─────────────────────────────────────┘
```

### 2.2 各步骤耗时预算

| 步骤 | 目标耗时 | 实际耗时 | 说明 |
|------|---------|---------|------|
| 广告筛选 | 10ms | 5ms | Redis 集合操作 |
| 频次控制 | 10ms | 8ms | Redis 原子操作 |
| 预算控制 | 5ms | 3ms | Redis Lua 脚本 |
| CTR/CVR 预估 | 15ms | 10ms | 模型推理 |
| 出价计算 | 5ms | 2ms | 纯 CPU 计算 |
| 排序选择 | 5ms | 1ms | 排序 100 个元素 |
| **总计** | **50ms** | **~30ms** | **留 20ms 余量** |

---

## 第三部分：Step 1 - 广告筛选（Targeting）

### 3.1 筛选逻辑

```
用户画像：
  → 年龄：25-35
  → 性别：男
  → 城市：北京
  → 兴趣：["科技", "汽车"]
  → 最近 7 天浏览过"电动车"

广告定向条件：
  → 年龄：20-40
  → 性别：不限
  → 城市：["北京", "上海", "广州"]
  → 兴趣：["科技", "数码"]
  → 排除：最近 24 小时看过"电动车"的人

筛选结果：
  → 100 万个广告中，筛选出 ~1000 个候选广告
```

### 3.2 Go 实现

```go
package dsp

import (
    "context"
    "fmt"
    "time"
)

// BidRequest 竞价请求
type BidRequest struct {
    UserID   string    `json:"user_id"`
    Device   DeviceInfo `json:"device"`
    Geo      GeoInfo   `json:"geo"`
    AdSlot   AdSlotInfo `json:"slot"`
    App      AppInfo   `json:"app"`
    ImpressionID string `json:"imp_id"` // 唯一标识
    Timestamp    time.Time `json:"ts"`
}

type DeviceInfo struct {
    Model    string `json:"model"`
    OS       string `json:"os"`
    Network  string `json:"net"` // 4G/5G/WiFi
    IP       string `json:"ip"`
}

type GeoInfo struct {
    Country  string `json:"country"`
    Province string `json:"province"`
    City     string `json:"city"`
    Lat      float64 `json:"lat"`
    Lng      float64 `json:"lng"`
}

type AdSlotInfo struct {
    Width  int    `json:"w"`
    Height int    `json:"h"`
    Format string `json:"format"` // banner/native/video
}

type AppInfo struct {
    ID   string `json:"id"`
    Cat  []string `json:"cat"` // 应用类别
}

// CandidateAd 候选广告
type CandidateAd struct {
    AdID       string
    CampaignID string
    AdvertiserID string
    CreativeID string
    BidFloor   float64 // 底价
    Targeting  TargetingRule
}

// TargetingRule 广告定向规则
type TargetingRule struct {
    Ages     []int     // 年龄范围
    Genders  []string  // 性别
    Cities   []string  // 城市
    Interests []string // 兴趣标签
    Exclude  []string  // 排除标签
}

// AdSelector 广告选择器
type AdSelector struct {
    redis *RedisClient
}

// SelectCandidates 从百万广告中筛选候选
func (s *AdSelector) SelectCandidates(ctx context.Context, req *BidRequest) ([]*CandidateAd, error) {
    // 1. 获取用户画像
    userProfile, err := s.getUserProfile(ctx, req.UserID)
    if err != nil {
        // 画像获取失败，使用默认画像
        userProfile = s.getDefaultProfile()
    }
    
    // 2. 构建筛选条件
    conditions := s.buildConditions(req, userProfile)
    
    // 3. 从 Redis 获取候选广告
    // 使用 Redis Sorted Set：score = 相关性得分
    candidates, err := s.redis.ZRangeByScore(ctx, "ads:candidates", conditions)
    if err != nil {
        return nil, err
    }
    
    // 4. 解析候选广告
    ads := make([]*CandidateAd, 0, len(candidates))
    for _, candidate := range candidates {
        ad := s.parseCandidate(candidate)
        ads = append(ads, ad)
    }
    
    return ads, nil
}

// buildConditions 构建筛选条件
func (s *AdSelector) buildConditions(req *BidRequest, profile *UserProfile) TargetingConditions {
    return TargetingConditions{
        AgeRange:    profile.AgeRange,
        Genders:     profile.Genders,
        Cities:      []string{req.Geo.City},
        Interests:   profile.Interests,
        DeviceTypes: []string{req.Device.OS},
        Networks:    []string{req.Device.Network},
        AppCategories: req.App.Cat,
        SlotFormats: []string{req.AdSlot.Format},
    }
}

// getUserProfile 获取用户画像
func (s *AdSelector) getUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
    // 1. 查本地缓存
    if profile, ok := s.localCache.Get(userID); ok {
        return profile, nil
    }
    
    // 2. 查 Redis
    profile, err := s.redis.HGetAll(ctx, fmt.Sprintf("user:%s", userID))
    if err != nil {
        return nil, err
    }
    
    // 3. 回填本地缓存
    s.localCache.Set(userID, profile)
    
    return profile, nil
}
```

---

## 第四部分：Step 2 - 频次控制（Frequency Cap）

### 4.1 什么是频次控制？

```
频次控制 = 限制用户在一定时间内看到某个广告的次数

为什么需要？
1. 用户体验：避免用户看腻
2. 广告主利益：避免重复曝光浪费预算
3. 平台收益：避免同一用户反复看同一个广告

常见策略：
1. 用户-广告对：同一用户看同一广告 N 次/天
2. 用户-广告主对：同一用户看同一广告主 M 次/周
3. 用户-Campaign 对：同一用户看同一 Campaign K 次/月
```

### 4.2 Go 实现

```go
package dsp

import (
    "context"
    "fmt"
    "time"
)

// FrequencyController 频次控制器
type FrequencyController struct {
    redis *RedisClient
}

// FrequencyCap 频次控制规则
type FrequencyCap struct {
    MaxCount    int           // 最大次数
    WindowType  string        // day/week/month
    WindowSize  time.Duration // 窗口大小
    Scope       string        // ad/campaign/advertiser
}

// CheckFrequency 检查频次
func (fc *FrequencyController) CheckFrequency(
    ctx context.Context,
    userID string,
    scope string, // "ad" / "campaign" / "advertiser"
    scopeID string, // 广告 ID / Campaign ID / 广告主 ID
    caps []FrequencyCap,
) (bool, []string) {
    // 1. 构建 Redis key
    keys := make([]string, len(caps))
    for i, cap := range caps {
        window := fc.getWindowKey(cap.WindowType)
        keys[i] = fmt.Sprintf("freq:%s:%s:%s:%s", scope, window, scopeID, userID)
    }
    
    // 2. 批量获取频次（pipeline）
    counts, err := fc.redis.MGet(ctx, keys...)
    if err != nil {
        return false, nil
    }
    
    // 3. 检查每个规则
    exceeded := make([]string, 0)
    for i, cap := range caps {
        count := counts[i].(int64)
        if count >= int64(cap.MaxCount) {
            exceeded = append(exceeded, fmt.Sprintf("scope=%s, max=%d, current=%d", cap.Scope, cap.MaxCount, count))
        }
    }
    
    if len(exceeded) > 0 {
        return false, exceeded
    }
    
    return true, nil
}

// RecordFrequency 记录频次
func (fc *FrequencyController) RecordFrequency(
    ctx context.Context,
    userID string,
    scope string,
    scopeID string,
    caps []FrequencyCap,
) error {
    // 1. 构建 pipeline
    pipe := fc.redis.NewPipeline()
    
    for _, cap := range caps {
        window := fc.getWindowKey(cap.WindowType)
        key := fmt.Sprintf("freq:%s:%s:%s:%s", scope, window, scopeID, userID)
        
        // 原子递增
        pipe.Incr(ctx, key)
        
        // 设置过期时间
        pipe.Expire(ctx, key, cap.WindowSize)
    }
    
    // 2. 执行 pipeline
    return pipe.Exec(ctx)
}

// getWindowKey 获取窗口 key
func (fc *FrequencyController) getWindowKey(windowType string) string {
    switch windowType {
    case "day":
        return time.Now().Format("2006-01-02")
    case "week":
        return time.Now().Format("2006-01-02") // 简化，实际需要计算周
    case "month":
        return time.Now().Format("2006-01")
    default:
        return time.Now().Format("2006-01-02")
    }
}
```

### 4.3 Redis 实现

```
# 频次控制的核心：Redis INCR + EXPIRE

# 检查频次
GET freq:ad:2024-01-15:ad123:user456
# 返回：3（今天看了 3 次）

# 记录频次
INCR freq:ad:2024-01-15:ad123:user456
EXPIRE freq:ad:2024-01-15:ad123:user456 86400  # 24 小时过期

# 原子操作（Lua 脚本）
EVAL "local count = redis.call('INCR', KEYS[1]) if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end return count" 1 freq:ad:2024-01-15:ad123:user456 86400
```

---

## 第五部分：Step 3 - 预算控制（Budget Cap）

### 5.1 预算控制的核心问题

```
预算控制 = 确保广告主不会花超预算

关键问题：
1. 如何防止超预算？（原子扣减）
2. 如何快速检查预算？（Redis）
3. 如何处理高并发？（Lua 脚本）
4. 预算用完后怎么办？（暂停广告）
```

### 5.2 Go 实现

```go
package dsp

import (
    "context"
    "fmt"
    "time"
)

// BudgetController 预算控制器
type BudgetController struct {
    redis *RedisClient
}

// BudgetCheckResult 预算检查结果
type BudgetCheckResult struct {
    Allowed    bool
    Remaining  float64 // 剩余预算
    DailySpent float64 // 今日已消耗
}

// CheckBudget 检查预算（原子操作）
func (bc *BudgetController) CheckBudget(
    ctx context.Context,
    advertiserID string,
    campaignID string,
    bidPrice float64,
) (*BudgetCheckResult, error) {
    // Lua 脚本：原子检查 + 扣减
    lua := `
        local budget_key = KEYS[1]
        local spend_key = KEYS[2]
        local bid_price = tonumber(ARGV[1])
        
        -- 获取今日已消耗
        local daily_spent = tonumber(redis.call('GET', spend_key) or '0')
        
        -- 获取总预算
        local total_budget = tonumber(redis.call('GET', budget_key) or '0')
        
        -- 检查预算
        if daily_spent + bid_price > total_budget then
            return {0, daily_spent, total_budget}
        end
        
        -- 扣减预算
        redis.call('INCRBYFLOAT', spend_key, bid_price)
        
        return {1, daily_spent + bid_price, total_budget}
    `
    
    budgetKey := fmt.Sprintf("budget:%s:%s", advertiserID, campaignID)
    spendKey := fmt.Sprintf("spend:%s:%s:%s", advertiserID, campaignID, time.Now().Format("2006-01-02"))
    
    result, err := bc.redis.Eval(ctx, lua, []string{budgetKey, spendKey}, bidPrice)
    if err != nil {
        return nil, err
    }
    
    // 解析结果
    res := result.([]interface{})
    allowed := int(res[0].(float64)) == 1
    dailySpent := res[1].(float64)
    totalBudget := res[2].(float64)
    
    return &BudgetCheckResult{
        Allowed:    allowed,
        Remaining:  totalBudget - dailySpent,
        DailySpent: dailySpent,
    }, nil
}

// PauseCampaign 暂停 Campaign（预算用完）
func (bc *BudgetController) PauseCampaign(ctx context.Context, campaignID string) error {
    return bc.redis.HSet(ctx, fmt.Sprintf("campaign:%s:status", campaignID), "status", "paused")
}
```

---

## 第六部分：Step 4-6 - CTR/CVR 预估 + 出价 + 排序

### 6.1 完整流程

```go
// Bidder 竞价引擎
type Bidder struct {
    selector       *AdSelector
    frequencyCtrl  *FrequencyController
    budgetCtrl     *BudgetController
    predictor      *Predictor
    strategy       *BiddingStrategy
}

// Bid 执行竞价
func (b *Bidder) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // Step 1: 广告筛选
    candidates, err := b.selector.SelectCandidates(ctx, req)
    if err != nil || len(candidates) == 0 {
        return nil, fmt.Errorf("no candidates")
    }
    
    // Step 2: 频次控制
    filtered := make([]*CandidateAd, 0)
    for _, ad := range candidates {
        allowed, _ := b.frequencyCtrl.CheckFrequency(ctx, req.UserID, "ad", ad.AdID, []FrequencyCap{
            {MaxCount: 5, WindowType: "day", WindowSize: 24 * time.Hour, Scope: "ad"},
            {MaxCount: 20, WindowType: "week", WindowSize: 7 * 24 * time.Hour, Scope: "ad"},
        })
        if allowed {
            filtered = append(filtered, ad)
        }
    }
    
    // Step 3: 预算控制
    budgetFiltered := make([]*CandidateAd, 0)
    for _, ad := range filtered {
        result, err := b.budgetCtrl.CheckBudget(ctx, ad.AdvertiserID, ad.CampaignID, ad.BidFloor)
        if err == nil && result.Allowed {
            budgetFiltered = append(budgetFiltered, ad)
        }
    }
    
    if len(budgetFiltered) == 0 {
        return nil, fmt.Errorf("no ads with budget")
    }
    
    // Step 4: CTR/CVR 预估
    predictions := b.predictor.BatchPredict(ctx, budgetFiltered, req)
    
    // Step 5: 出价计算
    bids := make([]*BidResponse, 0, len(predictions))
    for i, ad := range budgetFiltered {
        pred := predictions[i]
        bidPrice := b.strategy.Calculate(ad, pred.CTR, pred.CVR, req.Impression.BidFloor)
        
        eCPM := pred.CTR * pred.CVR * bidPrice * 1000
        
        bids = append(bids, &BidResponse{
            AdID:       ad.AdID,
            CreativeID: ad.CreativeID,
            BidPrice:   bidPrice,
            CTR:        pred.CTR,
            CVR:        pred.CVR,
            eCPM:       eCPM,
        })
    }
    
    // Step 6: 排序选择
    // 按 eCPM 降序排序
    sort.Slice(bids, func(i, j int) bool {
        return bids[i].eCPM > bids[j].eCPM
    })
    
    return bids[0], nil
}
```

---

## 第七部分：生产排障案例

### 7.1 频次控制导致误杀

```
现象：某些广告主投诉广告无法投放

排查：
1. 检查频次规则
2. 检查 Redis 数据
3. 检查用户画像

根因：
→ 频次窗口计算错误（用了 week 而不是 day）
→ 导致某些广告被过度限制

修复：
→ 修正窗口计算
→ 添加频次规则监控告警
```

### 7.2 预算扣减非原子导致超扣

```
现象：广告主投诉预算扣多了

排查：
1. 检查预算扣减逻辑
2. 检查并发情况
3. 检查 Redis 数据

根因：
→ 两个请求同时 CheckBudget
→ 都看到预算充足
→ 都扣减了
→ 总扣减 > 预算

修复：
→ 使用 Lua 脚本保证原子性
→ Check + Deduct 在一个脚本中完成
```

---

## 第八部分：自测题

### 问题 1
DSP 的核心流程是什么？

<details>
<summary>查看答案</summary>

1. **广告筛选**：从百万广告中选候选
2. **频次控制**：过滤超频次的广告
3. **预算控制**：过滤预算不足的广告
4. **CTR/CVR 预估**：预测点击率和转化率
5. **出价计算**：计算每个广告的出价
6. **排序选择**：按 eCPM 排序，选最高的
</details>

### 问题 2
频次控制用什么实现？

<details>
<summary>查看答案</summary>

1. **Redis INCR**：原子递增
2. **Redis EXPIRE**：设置过期时间
3. **Lua 脚本**：原子操作
4. **Pipeline**：批量操作
5. **窗口类型**：day/week/month
</details>

### 问题 3
如何防止预算超扣？

<details>
<summary>查看答案</summary>

1. **Lua 脚本**：Check + Deduct 原子操作
2. **Redis INCRBYFLOAT**：原子扣减
3. **设置预算上限**：防止无限扣减
4. **监控告警**：预算接近上限时告警
5. **暂停 Campaign**：预算用完自动暂停
</details>

---

*本文档基于 DSP 生产实战整理。*