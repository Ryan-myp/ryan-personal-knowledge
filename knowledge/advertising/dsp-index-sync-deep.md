# DSP 索引同步深度：数据变更 → Redis 索引实时更新

> 表结构变更处理 + Redis 索引更新策略 + 一致性保障 + 性能优化

---

## 第一部分：为什么索引同步是个大问题？

### 真实场景

```
广告主在后台操作：
1. 创建广告 → 需要把广告加入 Redis 索引
2. 更新广告定向 → 需要从旧索引删除，加入新索引
3. 暂停广告 → 需要从 Redis 索引删除
4. 删除广告 → 需要从 Redis 索引删除
5. 预算用完 → 需要暂停广告，从索引删除

问题：
- 如果索引没更新 → 用户请求时搜不到这个广告
- 如果索引更新慢了 → 用户可能看到已暂停的广告
- 如果索引更新错了 → 定向不准，浪费预算
```

### 核心挑战

```
1. 一致性：MySQL 和 Redis 必须保持一致
2. 实时性：广告变更后，索引要立刻更新
3. 性能：不能因为索引更新拖慢广告主操作
4. 幂等性：重复操作不会导致索引错误
5. 容错：Redis 挂了怎么办？
```

---

## 第二部分：索引同步架构设计

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    广告管理系统                               │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 创建广告  │  │ 更新广告  │  │ 暂停广告  │  │ 删除广告  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│       ▼              ▼              ▼              ▼         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Ad Service (Go)                         │    │
│  │                                                     │    │
│  │  1. 写入 MySQL (事务)                                │    │
│  │  2. 发送消息到 MQ (异步)                              │    │
│  │  3. 立即更新 Redis (同步，可选)                       │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Message Queue (Kafka/RabbitMQ)          │    │
│  │                                                     │    │
│  │  Topic: ad.index.sync                               │    │
│  │  Messages:                                          │    │
│  │    - CREATE: {ad_id, targeting, status}              │    │
│  │    - UPDATE: {ad_id, old_targeting, new_targeting}   │    │
│  │    - PAUSE: {ad_id}                                  │    │
│  │    - DELETE: {ad_id}                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Index Sync Service (消费者)                 │    │
│  │                                                     │    │
│  │  1. 消费 MQ 消息                                     │    │
│  │  2. 更新 Redis 索引                                  │    │
│  │  3. 重试失败的消息                                   │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Redis                              │    │
│  │                                                     │    │
│  │  ZADD ads:by_targeting:age_25_35 ad1 ad2 ad3        │    │
│  │  ZADD ads:by_targeting:city_beijing ad1 ad4 ad5     │    │
│  │  HSET ad:ad1 name "Nike" price 299 ...              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 同步策略选择

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **同步更新** | 实时性强 | 慢，阻塞广告主操作 | 小流量 |
| **异步更新（MQ）** | 快，不阻塞 | 有延迟 | **推荐** |
| **双写** | 最强一致性 | 复杂，容易不一致 | 高要求场景 |
| **最终一致性** | 最简单 | 有短暂不一致 | **大多数场景** |

**推荐方案：异步更新 + 最终一致性**

```
为什么？
1. 广告主操作不需要毫秒级同步（延迟 100ms 可接受）
2. 竞价流程有本地缓存兜底
3. 如果 Redis 挂了，可以从 MySQL 重建索引
```

---

## 第三部分：核心实现

### 3.1 广告变更消息定义

```go
package dsp

import (
    "time"
)

// AdChangeEvent 广告变更事件
type AdChangeEvent struct {
    Type       string    `json:"type"` // CREATE/UPDATE/PAUSE/DELETE
    AdID       string    `json:"ad_id"`
    AdsetID    string    `json:"adset_id"`
    CampaignID string    `json:"campaign_id"`
    AccountID  string    `json:"account_id"`
    
    // CREATE/UPDATE 时需要
    Name       string    `json:"name"`
    Status     int       `json:"status"` // 1=active, 0=paused, 2=deleted
    CreativeType string  `json:"creative_type"`
    BidFloor   float64   `json:"bid_floor"`
    
    // 定向条件（CREATE/UPDATE 时）
    Targeting  Targeting `json:"targeting"`
    
    // 更新时间
    UpdatedAt  time.Time `json:"updated_at"`
}

// Targeting 广告定向条件
type Targeting struct {
    Ages     []int     `json:"ages"`       // [20, 30] 表示 20-30 岁
    Genders  []string  `json:"genders"`    // ["M", "F"]
    Cities   []string  `json:"cities"`     // ["北京", "上海"]
    Interests []string `json:"interests"`  // ["tech", "cars"]
    Devices  []string `json:"devices"`    // ["iOS", "Android"]
    Networks []string `json:"networks"`   // ["4G", "WiFi"]
}
```

### 3.2 索引更新逻辑

```go
package dsp

import (
    "context"
    "fmt"
    "strings"
    "time"
)

// IndexSyncer 索引同步器
type IndexSyncer struct {
    redis    *RedisClient
    db       *Database
    retryMax int // 最大重试次数
}

// HandleEvent 处理广告变更事件
func (s *IndexSyncer) HandleEvent(ctx context.Context, event *AdChangeEvent) error {
    switch event.Type {
    case "CREATE":
        return s.handleCreate(ctx, event)
    case "UPDATE":
        return s.handleUpdate(ctx, event)
    case "PAUSE":
        return s.handlePause(ctx, event)
    case "DELETE":
        return s.handleDelete(ctx, event)
    default:
        return fmt.Errorf("unknown event type: %s", event.Type)
    }
}

// handleCreate 处理创建事件
func (s *IndexSyncer) handleCreate(ctx context.Context, event *AdChangeEvent) error {
    // 1. 从数据库获取完整的广告信息
    ad, err := s.db.GetAd(ctx, event.AdID)
    if err != nil {
        return fmt.Errorf("failed to get ad: %v", err)
    }
    
    // 2. 获取广告组的定向条件
    adset, err := s.db.GetAdset(ctx, ad.AdsetID)
    if err != nil {
        return fmt.Errorf("failed to get adset: %v", err)
    }
    
    // 3. 合并定向条件（广告组定向 + 广告定向）
    targeting := mergeTargeting(adset.Targeting, ad.Targeting)
    
    // 4. 更新 Redis 索引
    return s.updateIndex(ctx, event.AdID, targeting, ad.Status)
}

// handleUpdate 处理更新事件
func (s *IndexSyncer) handleUpdate(ctx context.Context, event *AdChangeEvent) error {
    // 1. 获取旧的定向条件（用于删除旧索引）
    oldTargeting, err := s.db.GetAdTargeting(ctx, event.AdID)
    if err != nil {
        return fmt.Errorf("failed to get old targeting: %v", err)
    }
    
    // 2. 获取新的定向条件
    newTargeting := event.Targeting
    
    // 3. 删除旧索引
    if err := s.removeIndex(ctx, event.AdID, oldTargeting); err != nil {
        return fmt.Errorf("failed to remove old index: %v", err)
    }
    
    // 4. 添加新索引
    if err := s.updateIndex(ctx, event.AdID, newTargeting, event.Status); err != nil {
        return fmt.Errorf("failed to add new index: %v", err)
    }
    
    return nil
}

// handlePause 处理暂停事件
func (s *IndexSyncer) handlePause(ctx context.Context, event *AdChangeEvent) error {
    // 1. 获取广告的定向条件
    targeting, err := s.db.GetAdTargeting(ctx, event.AdID)
    if err != nil {
        return fmt.Errorf("failed to get targeting: %v", err)
    }
    
    // 2. 从所有索引中删除
    return s.removeIndex(ctx, event.AdID, targeting)
}

// handleDelete 处理删除事件
func (s *IndexSyncer) handleDelete(ctx context.Context, event *AdChangeEvent) error {
    // 同 handlePause，从索引中删除
    return s.handlePause(ctx, event)
}

// updateIndex 更新索引（核心方法）
func (s *IndexSyncer) updateIndex(ctx context.Context, adID string, targeting Targeting, status int) error {
    if status != 1 { // 只有 active 状态的广告才加入索引
        return nil
    }
    
    // 1. 写入广告详情（Hash）
    err := s.redis.HMSet(ctx, fmt.Sprintf("ad:%s", adID), map[string]interface{}{
        "name":         targeting.Name,
        "bid_floor":    targeting.BidFloor,
        "creative_type": targeting.CreativeType,
        "status":       1,
        "updated_at":   time.Now().Format(time.RFC3339),
    })
    if err != nil {
        return err
    }
    
    // 2. 更新年龄索引（Sorted Set）
    for _, age := range targeting.Ages {
        key := fmt.Sprintf("ads:by_targeting:age_%d", age)
        err := s.redis.ZAdd(ctx, key, adID, 0)
        if err != nil {
            return err
        }
    }
    
    // 3. 更新城市索引
    for _, city := range targeting.Cities {
        key := fmt.Sprintf("ads:by_targeting:city_%s", city)
        err := s.redis.ZAdd(ctx, key, adID, 0)
        if err != nil {
            return err
        }
    }
    
    // 4. 更新兴趣索引
    for _, interest := range targeting.Interests {
        key := fmt.Sprintf("ads:by_targeting:interest_%s", interest)
        err := s.redis.ZAdd(ctx, key, adID, 0)
        if err != nil {
            return err
        }
    }
    
    // 5. 更新设备索引
    for _, device := range targeting.Devices {
        key := fmt.Sprintf("ads:by_targeting:device_%s", device)
        err := s.redis.ZAdd(ctx, key, adID, 0)
        if err != nil {
            return err
        }
    }
    
    // 6. 更新网络索引
    for _, network := range targeting.Networks {
        key := fmt.Sprintf("ads:by_targeting:network_%s", network)
        err := s.redis.ZAdd(ctx, key, adID, 0)
        if err != nil {
            return err
        }
    }
    
    return nil
}

// removeIndex 删除索引
func (s *IndexSyncer) removeIndex(ctx context.Context, adID string, targeting Targeting) error {
    // 删除年龄索引
    for _, age := range targeting.Ages {
        key := fmt.Sprintf("ads:by_targeting:age_%d", age)
        s.redis.ZRem(ctx, key, adID)
    }
    
    // 删除城市索引
    for _, city := range targeting.Cities {
        key := fmt.Sprintf("ads:by_targeting:city_%s", city)
        s.redis.ZRem(ctx, key, adID)
    }
    
    // 删除兴趣索引
    for _, interest := range targeting.Interests {
        key := fmt.Sprintf("ads:by_targeting:interest_%s", interest)
        s.redis.ZRem(ctx, key, adID)
    }
    
    // 删除设备索引
    for _, device := range targeting.Devices {
        key := fmt.Sprintf("ads:by_targeting:device_%s", device)
        s.redis.ZRem(ctx, key, adID)
    }
    
    // 删除网络索引
    for _, network := range targeting.Networks {
        key := fmt.Sprintf("ads:by_targeting:network_%s", network)
        s.redis.ZRem(ctx, key, adID)
    }
    
    // 删除广告详情
    s.redis.Del(ctx, fmt.Sprintf("ad:%s", adID))
    
    return nil
}
```

### 3.3 一致性保障

```go
package dsp

import (
    "context"
    "fmt"
    "time"
)

// ConsistencyChecker 一致性检查器
type ConsistencyChecker struct {
    redis *RedisClient
    db    *Database
}

// CheckAndFix 检查并修复不一致
func (c *ConsistencyChecker) CheckAndFix(ctx context.Context) error {
    // 1. 从 MySQL 获取所有 active 广告
    ads, err := c.db.GetAllActiveAds(ctx)
    if err != nil {
        return err
    }
    
    // 2. 从 Redis 获取所有索引中的广告
    redisAds := make(map[string]bool)
    for _, key := range c.redis.Keys(ctx, "ads:by_targeting:*") {
        members, _ := c.redis.ZRange(ctx, key, 0, -1)
        for _, ad := range members {
            redisAds[ad] = true
        }
    }
    
    // 3. 对比不一致
    for _, ad := range ads {
        if !redisAds[ad.ID] {
            // MySQL 有，Redis 没有 → 添加
            c.addAdToIndex(ctx, ad)
        }
    }
    
    for adID := range redisAds {
        exists, _ := c.db.AdExists(ctx, adID)
        if !exists {
            // Redis 有，MySQL 没有 → 删除
            c.removeAdFromIndex(ctx, adID)
        }
    }
    
    return nil
}

// addAdToIndex 添加广告到索引
func (c *ConsistencyChecker) addAdToIndex(ctx context.Context, ad *Ad) error {
    targeting, err := c.db.GetAdTargeting(ctx, ad.ID)
    if err != nil {
        return err
    }
    
    // 复用 IndexSyncer 的逻辑
    syncer := &IndexSyncer{redis: c.redis, db: c.db}
    return syncer.updateIndex(ctx, ad.ID, targeting, 1)
}

// removeAdFromIndex 从索引删除广告
func (c *ConsistencyChecker) removeAdFromIndex(ctx context.Context, adID string) error {
    targeting, err := c.db.GetAdTargeting(ctx, adID)
    if err != nil {
        return err
    }
    
    syncer := &IndexSyncer{redis: c.redis, db: c.db}
    return syncer.removeIndex(ctx, adID, targeting)
}
```

### 3.4 定时同步任务

```go
package dsp

import (
    "context"
    "time"
)

// SyncScheduler 同步调度器
type SyncScheduler struct {
    checker *ConsistencyChecker
    ticker  *time.Ticker
}

// Start 启动定时同步
func (s *SyncScheduler) Start(ctx context.Context) {
    s.ticker = time.NewTicker(5 * time.Minute) // 每 5 分钟检查一次
    
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            case <-s.ticker.C:
                // 检查并修复不一致
                if err := s.checker.CheckAndFix(ctx); err != nil {
                    // 记录错误，但不影响其他操作
                    log.Error("consistency check failed: %v", err)
                }
            }
        }
    }()
}

// Stop 停止定时同步
func (s *SyncScheduler) Stop() {
    s.ticker.Stop()
}
```

---

## 第四部分：性能优化

### 4.1 Pipeline 批量操作

```go
// 优化前：每个索引单独操作（N 次网络往返）
func (s *IndexSyncer) updateIndexSlow(ctx context.Context, adID string, targeting Targeting) error {
    for _, age := range targeting.Ages {
        key := fmt.Sprintf("ads:by_targeting:age_%d", age)
        s.redis.ZAdd(ctx, key, adID, 0) // 1 次网络往返
    }
    for _, city := range targeting.Cities {
        key := fmt.Sprintf("ads:by_targeting:city_%s", city)
        s.redis.ZAdd(ctx, key, adID, 0) // 1 次网络往返
    }
    // ... 更多索引
    return nil
}

// 优化后：Pipeline 批量操作（1 次网络往返）
func (s *IndexSyncer) updateIndexFast(ctx context.Context, adID string, targeting Targeting) error {
    pipe := s.redis.Pipeline()
    
    for _, age := range targeting.Ages {
        key := fmt.Sprintf("ads:by_targeting:age_%d", age)
        pipe.ZAdd(ctx, key, redis.Z{Member: adID, Score: 0})
    }
    
    for _, city := range targeting.Cities {
        key := fmt.Sprintf("ads:by_targeting:city_%s", city)
        pipe.ZAdd(ctx, key, redis.Z{Member: adID, Score: 0})
    }
    
    // 一次性执行所有操作
    _, err := pipe.Exec(ctx)
    return err
}
```

### 4.2 性能对比

```
测试场景：更新 100 个索引

优化前：
→ 100 次网络往返
→ 每往返 1ms
→ 总耗时：100ms

优化后：
→ 1 次网络往返（Pipeline）
→ 总耗时：1ms

提升：100 倍！
```

---

## 第五部分：生产排障案例

### 5.1 索引不一致

```
现象：广告主创建广告后，竞价引擎搜不到

排查：
1. 检查 MySQL：广告存在，status=1
2. 检查 Redis：ads:by_targeting:* 中没有该广告
3. 检查 MQ：消息是否发送成功
4. 检查消费者：是否消费成功

根因：
→ MQ 消息丢失（未开启持久化）
→ 消费者处理失败，但未重试

解决方案：
1. MQ 开启持久化
2. 消费者实现重试机制
3. 定时同步任务兜底
```

### 5.2 索引更新延迟

```
现象：广告主暂停广告后，用户还能看到

排查：
1. 检查暂停操作是否成功
2. 检查 MQ 消息是否发送
3. 检查消费者处理延迟

根因：
→ 消费者处理慢（Redis 连接池耗尽）
→ 消息积压

解决方案：
1. 增加 Redis 连接池大小
2. 增加消费者并行度
3. 监控 MQ 积压量
```

---

## 第六部分：自测题

### 问题 1
广告变更后，如何保证 Redis 索引同步？

<details>
<summary>查看答案</summary>

1. **异步更新**：MySQL 事务 + MQ 消息
2. **消费者**：消费 MQ 消息，更新 Redis 索引
3. **一致性检查**：定时任务对比 MySQL 和 Redis
4. **Pipeline**：批量操作，减少网络 RTT
5. **重试机制**：消费失败时重试
</details>

### 问题 2
如何防止索引不一致？

<details>
<summary>查看答案</summary>

1. **定时同步**：每 5 分钟检查一次
2. **幂等操作**：重复更新不会导致错误
3. **监控告警**：不一致时告警
4. **手动修复**：提供修复命令
5. **回滚机制**：支持回滚索引
</details>

### 问题 3
为什么用 Pipeline 而不是逐个操作？

<details>
<summary>查看答案</summary>

1. **网络 RTT**：Pipeline 1 次，逐个 N 次
2. **性能**：Pipeline 快 100 倍
3. **原子性**：Pipeline 内的操作原子执行
4. **连接数**：Pipeline 减少连接数
5. **适用场景**：批量操作都用 Pipeline
</details>

---

*本文档基于 DSP 索引同步生产实战整理。*