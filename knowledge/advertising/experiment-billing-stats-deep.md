# 广告实验在召回/计费/统计中的落地

> 实验如何嵌入召回链路 + 计费方式 + 统计对账

---

## 第一部分：实验在召回架构中的体现

### 1.1 召回链路中嵌入实验

```
正常流程：
用户请求 → 多路召回 → 粗排 → 精排 → 竞价 → 返回

嵌入实验后：
用户请求 → 分流实验 → 根据实验组选择召回策略 → 多路召回 → 粗排 → 精排 → 竞价 → 返回
                                    │
                                    └── 对照组：传统召回
                                    └── 实验组 A：向量召回
                                    └── 实验组 B：混合召回
```

### 1.2 代码实现

```go
package dsp

import (
    "context"
    "sync"
)

// ExperimentAwareRecaller 实验感知的召回器
type ExperimentAwareRecaller struct {
    allocator  *ExperimentAllocator
    recallers  map[string]Recaller // groupName -> Recaller
    collector  *ExperimentCollector
}

// Recall 召回（带实验）
func (r *ExperimentAwareRecaller) Recall(ctx context.Context, req *BidRequest, userID string) ([]*Ad, error) {
    // 1. 分流到实验组
    groups, err := r.allocator.Assign(userID, "recall_strategy")
    if err != nil {
        // 默认使用对照组
        groups = map[string]string{"recall_strategy": "control"}
    }
    
    // 2. 根据实验组选择不同的召回策略
    var allCandidates []*Ad
    var mu sync.Mutex
    var wg sync.WaitGroup
    
    for groupName, recaller := range r.recallers {
        // 检查该路是否在当前实验中
        group, ok := groups["recall_strategy"]
        if !ok || group != groupName {
            continue
        }
        
        wg.Add(1)
        go func(name string, recaller Recaller) {
            defer wg.Done()
            
            candidates, err := recaller.Recall(ctx, req)
            if err != nil {
                log.Error("recaller %s failed: %v", name, err)
                return
            }
            
            mu.Lock()
            allCandidates = append(allCandidates, candidates...)
            mu.Unlock()
            
            // 记录指标
            r.collector.RecordImpression("recall_strategy", name, userID, len(candidates))
        }(groupName, recaller)
    }
    
    wg.Wait()
    
    // 3. 去重合并
    allCandidates = deduplicate(allCandidates)
    
    return allCandidates, nil
}
```

### 1.3 不同召回策略的实验

```go
// 实验配置
recallExperiment := &Experiment{
    ID:      "recall_strategy",
    Name:    "召回策略对比",
    Enabled: true,
    Buckets: []Bucket{
        {ID: "control", Weight: 300, Name: "control"},     // 30%：传统关键词召回
        {ID: "vector", Weight: 300, Name: "vector"},       // 30%：向量召回
        {ID: "hybrid", Weight: 400, Name: "hybrid"},       // 40%：混合召回
    },
}

// 注册召回器
recallers := map[string]Recaller{
    "control": &KeywordRecaller{store: adStore},     // 传统关键词召回
    "vector":  &VectorRecaller{store: adStore},       // 向量召回（embedding）
    "hybrid":  &HybridRecaller{store: adStore},       // 混合召回
}

engine := &ExperimentAwareRecaller{
    allocator:  experimentAllocator,
    recallers:  recallers,
    collector:  experimentCollector,
}
```

### 1.4 实验对粗排/精排的影响

```go
// 实验也影响排序模型
type ExperimentAwareRanker struct {
    allocator *ExperimentAllocator
    models    map[string]*Model // groupName -> Model
}

// Rank 排序（带实验）
func (r *ExperimentAwareRanker) Rank(ctx context.Context, ads []*Ad, userID string) ([]*BidResult, error) {
    // 1. 分流到实验组
    groups, _ := r.allocator.Assign(userID, "ranking_model")
    group := groups["ranking_model"]
    
    // 2. 使用对应实验组的模型
    model, ok := r.models[group]
    if !ok {
        model = r.models["control"]
    }
    
    // 3. 执行排序
    results := model.Predict(ads, userID)
    
    // 4. 记录指标
    for _, result := range results {
        r.collector.RecordClick("ranking_model", group, userID, result.AdID)
    }
    
    return results, nil
}
```

---

## 第二部分：计费方式

### 2.1 广告计费模式

```
1. CPC（Cost Per Click）：按点击计费
   → 用户点击广告才扣费
   → 广告主愿意为点击付费

2. CPM（Cost Per Mille）：按千次展示计费
   → 广告展示就扣费
   → 广告主愿意为曝光付费

3. oCPM（Optimized CPM）：按转化目标计费
   → 系统预估 CTR × CVR 来计算出价
   → eCPM = CTR × CVR × targetCPA × 1000
   → 广告主愿意为转化付费

4. CPA（Cost Per Action）：按转化计费
   → 用户完成转化才扣费
   → 广告主风险最低
```

### 2.2 oCPM 计费实现

```go
package dsp

import (
    "fmt"
)

// BillingEngine 计费引擎
type BillingEngine struct {
    bidStrategy string // CPC/CPM/oCPM
    targetCPA   float64
}

// CalculateBid 计算出价
func (be *BillingEngine) CalculateBid(ctr, cvr, bidFloor float64) (float64, error) {
    switch be.bidStrategy {
    case "CPC":
        // CPC：直接使用广告主出价
        return be.calculateCPC(bidFloor), nil
        
    case "CPM":
        // CPM：千次展示计费
        return be.calculateCPM(bidFloor), nil
        
    case "oCPM":
        // oCPM：基于预估转化出价
        return be.calculateoCPM(ctr, cvr, bidFloor), nil
        
    default:
        return 0, fmt.Errorf("unknown bid strategy: %s", be.bidStrategy)
    }
}

// calculateCPC CPC 出价
func (be *BillingEngine) calculateCPC(bidFloor float64) float64 {
    // CPC：直接使用广告主出价
    return bidFloor
}

// calculateCPM CPM 出价
func (be *BillingEngine) calculateCPM(bidFloor float64) float64 {
    // CPM：千次展示计费，假设每次点击 1 元，CTR 0.01
    // CPM = CPC × CTR × 1000
    cpc := bidFloor
    ctr := 0.01 // 假设 CTR
    return cpc * ctr * 1000
}

// calculateoCPM oCPM 出价
func (be *BillingEngine) calculateoCPM(ctr, cvr, bidFloor float64) float64 {
    // oCPM：eCPM = CTR × CVR × targetCPA × 1000
    eCPM := ctr * cvr * be.targetCPA * 1000
    
    // 保底：不低于底价
    if eCPM < bidFloor {
        eCPM = bidFloor
    }
    
    return eCPM
}

// RecordBilling 记录计费
func (be *BillingEngine) RecordBilling(adID, campaignID string, bidPrice float64, eventType string) error {
    // eventType: impression/click/conversion
    billingRecord := &BillingRecord{
        AdID:        adID,
        CampaignID:  campaignID,
        BidPrice:    bidPrice,
        EventType:   eventType,
        Timestamp:   time.Now(),
    }
    
    // 写入 Kafka（异步）
    billingKafkaProducer.Send("ad.billing", billingRecord)
    
    return nil
}
```

### 2.3 计费流程

```
竞价成功 → 记录展示 → 用户点击 → 记录点击 → 用户转化 → 记录转化

1. 展示计费（CPM）：
   → 广告展示时，记录一次展示
   → 计费 = eCPM / 1000

2. 点击计费（CPC）：
   → 用户点击时，记录一次点击
   → 计费 = CPC 出价

3. 转化计费（oCPM/CPA）：
   → 用户转化时，记录一次转化
   → 计费 = targetCPA
```

---

## 第三部分：统计对账

### 3.1 统计指标

```
广告主需要看到：
1. 消耗：花了多少钱
2. 展示：广告展示了多少次
3. 点击：被点击了多少次
4. 转化：产生了多少转化
5. CTR：点击率 = 点击/展示
6. CVR：转化率 = 转化/点击
7. CPA：单次转化成本 = 消耗/转化
8. ROI：投资回报率 = 转化价值/消耗

平台需要看到：
1. 收入：赚了多少钱
2. eCPM：每千次展示收入
3. 填充率：广告填充比例
4. 竞价成功率：竞价成功/竞价请求
```

### 3.2 统计实现

```go
package dsp

import (
    "sync/atomic"
)

// StatsCollector 统计收集器
type StatsCollector struct {
    // 实时指标（内存）
    impressions  atomic.Int64
    clicks       atomic.Int64
    conversions  atomic.Int64
    revenue      atomic.Float64
    
    // 按广告主统计
    advertiserStats map[string]*AdvertiserStats
    
    // 按广告系列统计
    campaignStats map[string]*CampaignStats
}

type AdvertiserStats struct {
    AdvertiserID string
    Spend        atomic.Float64
    Impressions  atomic.Int64
    Clicks       atomic.Int64
    Conversions  atomic.Int64
}

type CampaignStats struct {
    CampaignID   string
    Spend        atomic.Float64
    Impressions  atomic.Int64
    Clicks       atomic.Int64
    Conversions  atomic.Int64
    Budget       float64
}

// RecordImpression 记录展示
func (sc *StatsCollector) RecordImpression(advertiserID, campaignID string) {
    sc.impressions.Add(1)
    sc.advertiserStats[advertiserID].Impressions.Add(1)
    sc.campaignStats[campaignID].Impressions.Add(1)
}

// RecordClick 记录点击
func (sc *StatsCollector) RecordClick(advertiserID, campaignID string) {
    sc.clicks.Add(1)
    sc.advertiserStats[advertiserID].Clicks.Add(1)
    sc.campaignStats[campaignID].Clicks.Add(1)
}

// RecordConversion 记录转化
func (sc *StatsCollector) RecordConversion(advertiserID, campaignID string, value float64) {
    sc.conversions.Add(1)
    sc.revenue.Add(value)
    sc.advertiserStats[advertiserID].Conversions.Add(1)
    sc.campaignStats[campaignID].Conversions.Add(1)
}

// GetStats 获取统计结果
func (sc *StatsCollector) GetStats() map[string]interface{} {
    impressions := sc.impressions.Load()
    clicks := sc.clicks.Load()
    conversions := sc.conversions.Load()
    revenue := sc.revenue.Load()
    
    ctr := float64(clicks) / float64(impressions) * 100
    cvr := float64(conversions) / float64(clicks) * 100
    cpa := revenue / float64(conversions)
    
    return map[string]interface{}{
        "impressions": impressions,
        "clicks":      clicks,
        "conversions": conversions,
        "revenue":     revenue,
        "ctr":         ctr,
        "cvr":         cvr,
        "cpa":         cpa,
    }
}
```

### 3.3 对账流程

```
实时统计（内存）→ 分钟级聚合（Kafka）→ 小时级持久化（MySQL）→ 天级对账（报表）

1. 实时统计：
   → Go map 中累加指标
   → 每 1 分钟刷新到 Redis

2. 分钟级聚合：
   → Kafka Consumer 消费指标事件
   → 按广告主/广告系列聚合
   → 写入 Redis

3. 小时级持久化：
   → 每小时将 Redis 数据同步到 MySQL
   → 保证数据不丢失

4. 天级对账：
   → 每天凌晨对账
   → 广告主后台显示 → 平台后台显示 → 财务系统显示
   → 差异 > 0.1% 告警
```

### 3.4 对账实现

```go
package dsp

import (
    "context"
    "fmt"
)

// Reconciler 对账器
type Reconciler struct {
    redis  *RedisClient
    db     *Database
    threshold float64 // 差异阈值
}

// DailyReconcile 每日对账
func (rc *Reconciler) DailyReconcile(ctx context.Context, date string) error {
    // 1. 获取广告主后台的消耗
    platformSpend, err := rc.getPlatformSpend(ctx, date)
    if err != nil {
        return err
    }
    
    // 2. 获取财务系统的消耗
    financeSpend, err := rc.getFinanceSpend(ctx, date)
    if err != nil {
        return err
    }
    
    // 3. 获取 MySQL 的消耗
    dbSpend, err := rc.getDBSpend(ctx, date)
    if err != nil {
        return err
    }
    
    // 4. 对比
    diff1 := math.Abs(platformSpend - financeSpend) / financeSpend
    diff2 := math.Abs(platformSpend - dbSpend) / dbSpend
    
    if diff1 > rc.threshold {
        log.Warn("platform vs finance diff > %.2f%%: %.2f vs %.2f", 
            rc.threshold*100, platformSpend, financeSpend)
    }
    
    if diff2 > rc.threshold {
        log.Warn("platform vs db diff > %.2f%%: %.2f vs %.2f", 
            rc.threshold*100, platformSpend, dbSpend)
    }
    
    return nil
}

// getPlatformSpend 获取平台后台消耗
func (rc *Reconciler) getPlatformSpend(ctx context.Context, date string) (float64, error) {
    // 从 Redis 获取当天所有广告的消耗
    key := fmt.Sprintf("daily_spend:%s", date)
    return rc.redis.HGetFloat64(ctx, key, "total")
}

// getFinanceSpend 获取财务系统消耗
func (rc *Reconciler) getFinanceSpend(ctx context.Context, date string) (float64, error) {
    // 从财务系统 API 获取
    // ...
    return 0, nil
}

// getDBSpend 获取 MySQL 消耗
func (rc *Reconciler) getDBSpend(ctx context.Context, date string) (float64, error) {
    var spend float64
    err := rc.db.QueryRow("SELECT SUM(consume) FROM billing WHERE date = ?", date).Scan(&spend)
    return spend, err
}
```

---

## 第四部分：实验 + 计费 + 统计的联动

### 4.1 实验分组计费

```
实验 A：竞价策略
→ 对照组：传统 oCPM
→ 实验组：新 oCPM v2

每个实验组独立计费：
→ 对照组消耗：¥10,000
→ 实验组消耗：¥12,000

每个实验组独立统计：
→ 对照组：eCPM ¥50, CTR 1.0%, CVR 2.0%
→ 实验组：eCPM ¥55, CTR 1.2%, CVR 2.5%

结论：新策略 eCPM 提升 10%，统计显著，全量
```

### 4.2 实验指标自动计算

```go
// 实验自动计算
type ExperimentReport struct {
    ExperimentID string
    Groups       map[string]*GroupReport
}

type GroupReport struct {
    Impressions  int64
    Clicks       int64
    Conversions  int64
    Spend        float64
    eCPM         float64
    CTR          float64
    CVR          float64
    CPA          float64
    Significant  bool // 是否显著
    ZScore       float64 // Z 值
}

// GenerateReport 生成实验报告
func (r *ExperimentReport) GenerateReport() error {
    groups := r.Groups
    control := groups["control"]
    experiment := groups["experiment"]
    
    // 计算指标
    controlCTR := float64(control.Clicks) / float64(control.Impressions)
    experimentCTR := float64(experiment.Clicks) / float64(experiment.Impressions)
    
    // 显著性检验
    zScore, significant := StatisticalTest{}.ZTest(
        controlCTR, experimentCTR,
        float64(control.Impressions), float64(experiment.Impressions),
    )
    
    control.CTR = controlCTR
    experiment.CTR = experimentCTR
    control.Significant = significant
    experiment.Significant = significant
    control.ZScore = zScore
    experiment.ZScore = zScore
    
    // 生成报告
    report := fmt.Sprintf(`
实验报告：%s
对照组：CTR %.2f%%, eCPM ¥%.2f
实验组：CTR %.2f%%, eCPM ¥%.2f
Z 值：%.2f
显著性：%v
结论：%s
`, r.ExperimentID,
        controlCTR*100, control.eCPM,
        experimentCTR*100, experiment.eCPM,
        zScore, significant,
        getConclusion(significant, experimentCTR > controlCTR),
    )
    
    log.Info(report)
    
    return nil
}
```

---

## 第五部分：自测题

### 问题 1
实验如何在召回架构中体现？

<details>
<summary>查看答案</summary>

1. **分流**：用户请求先到分流器，确定实验组
2. **策略选择**：根据实验组选择召回策略
3. **并行执行**：不同实验组使用不同的召回器
4. **指标记录**：每路召回独立记录指标
5. **效果对比**：实验结束后对比各路的 eCPM/CTR
</details>

### 问题 2
oCPM 计费的公式是什么？

<details>
<summary>查看答案</summary>

1. **eCPM = CTR × CVR × targetCPA × 1000**
2. **CTR**：点击率预估
3. **CVR**：转化率预估
4. **targetCPA**：广告主愿意为一次转化支付的金额
5. **保底**：eCPM 不低于广告主设置的底价
</details>

### 问题 3
如何保证计费对账准确？

<details>
<summary>查看答案</summary>

1. **实时统计**：Go map 中累加
2. **分钟级聚合**：Kafka 消费，写入 Redis
3. **小时级持久化**：Redis → MySQL
4. **天级对账**：平台后台 vs 财务系统 vs MySQL
5. **差异告警**：差异 > 0.1% 告警
</details>

---

*本文档基于广告实验/计费/统计生产实战整理。*